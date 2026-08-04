"""Chấm tự động.

Logic so khớp đáp án nằm ở `vimultiagent.core.answer_match` và được DÙNG CHUNG với
Verifier lúc chạy. Đây là chủ ý: nếu bộ chấm và Verifier trả lời khác nhau cho câu
hỏi "hai đáp án này có bằng nhau không", thì mọi con số trong báo cáo đều đáng ngờ.
"""

from __future__ import annotations

from typing import Any

from vimultiagent.core.answer_match import (  # noqa: F401
    answers_match,
    extract_number,
    is_unit_error,
    normalize_answer,
    symbolic_value,
)


def score_item(pred_answer: str | None, pred_choice: str | None, item: dict[str, Any]) -> dict[str, Any]:
    """Chấm một bài. MCQ ưu tiên so nhãn; nếu không có nhãn thì lùi về so giá trị."""
    gold = item.get("answer")
    gold_val = item.get("answer_value")

    if item.get("type") == "mcq":
        if pred_choice:
            correct = pred_choice.strip().upper() == str(gold).strip().upper()
        else:
            correct = answers_match(pred_answer, gold_val)
        matched_by = "choice" if pred_choice else "value"
    else:
        correct = answers_match(pred_answer, gold) or answers_match(pred_answer, gold_val)
        matched_by = "value"

    return {
        "correct": bool(correct),
        "matched_by": matched_by,
        "unit_error": (not correct) and is_unit_error(pred_answer, gold_val),
        "pred": pred_answer,
        "pred_choice": pred_choice,
        "gold": gold,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    correct = sum(1 for r in rows if r.get("correct"))
    lat = sorted(r.get("latency_ms", 0.0) for r in rows)

    def pct(p: float) -> float:
        if not lat:
            return 0.0
        return lat[min(int(p * len(lat)), len(lat) - 1)]

    by_domain: dict[str, dict[str, int]] = {}
    for r in rows:
        d = r.get("domain", "?")
        by_domain.setdefault(d, {"n": 0, "correct": 0})
        by_domain[d]["n"] += 1
        by_domain[d]["correct"] += int(bool(r.get("correct")))

    return {
        "n": n,
        "accuracy": round(correct / n, 4),
        "correct": correct,
        "unit_errors": sum(1 for r in rows if r.get("unit_error")),
        "latency_p50_ms": round(pct(0.5), 1),
        "latency_p95_ms": round(pct(0.95), 1),
        "latency_mean_ms": round(sum(lat) / len(lat), 1) if lat else 0.0,
        "within_45s": round(sum(1 for x in lat if x <= 45000) / len(lat), 4) if lat else 0.0,
        "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in rows), 4),
        "total_tokens": sum(r.get("tokens", 0) for r in rows),
        "verdict_dist": {
            v: sum(1 for r in rows if r.get("verdict") == v)
            for v in ("PASS", "FAIL", "UNCERTAIN")
        },
        "repair_rate": round(sum(1 for r in rows if r.get("repair_rounds", 0) > 0) / n, 4),
        "by_domain": {
            d: {**v, "accuracy": round(v["correct"] / v["n"], 4)} for d, v in by_domain.items()
        },
    }


# ---------------------------------------------------------------------------
# Chỉ số của Verifier — Precision/Recall/F1
# ---------------------------------------------------------------------------


def verifier_prf(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Verifier có phát hiện đúng những lời giải sai không?

    Quy ước: "positive" = Verifier BÁO SAI (FAIL/UNCERTAIN).
      TP: báo sai & thực sự sai   |  FP: báo sai & thực ra đúng  (đắt: loại oan lời giải tốt)
      FN: báo đạt & thực ra sai   (đắt hơn: đưa lời giải sai cho học sinh)
    """
    tp = fp = fn = tn = 0
    for r in rows:
        flagged = r.get("verdict") in ("FAIL", "UNCERTAIN")
        wrong = not r.get("correct")
        if flagged and wrong:
            tp += 1
        elif flagged and not wrong:
            fp += 1
        elif not flagged and wrong:
            fn += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "detection_rate": round(rec, 4),  # KPI "tỉ lệ tác tử checker phát hiện sai"
    }
