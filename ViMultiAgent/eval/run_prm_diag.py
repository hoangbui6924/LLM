"""Chẩn đoán ViSTEM-PRM trên LỜI GIẢI THẬT của Solver.

    python -m eval.run_prm_diag

Vì sao cần script này: mọi con số hiện có của PRM (F1 0,952 · recall 91,3 %) đều đo
trên lời giải sinh từ template — cùng bộ sinh đã tạo ra dữ liệu huấn luyện. Đó là
đánh giá TRONG phân phối, và nó không trả lời được câu hỏi duy nhất đang chặn tầng
T0 khỏi chế độ `blocking`: **PRM chấm lời giải thật của Solver như thế nào?**

Nguồn dữ liệu là cache LLM trên đĩa (`.cache/llm/`). Mọi lượt gọi Solver trong các
lần chạy benchmark đều nằm đó — lời giải thật, miễn phí, không cần chạy lại benchmark
và không tốn một token nào. Nhãn đúng/sai lấy bằng cách ghép đáp số của lời giải với
cột `pred`/`correct` trong báo cáo benchmark.

Ra hai thứ:
  1. Phân bố P(đúng) cho lời giải ĐÚNG và lời giải SAI — nếu hai phân bố chồng nhau
     thì PRM vô dụng trên phân phối thật, bất kể F1 trong phân phối đẹp đến đâu.
  2. Ngưỡng hiện hành (`prm.reject_threshold`) sẽ gây ra bao nhiêu báo oan.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vimultiagent.core.answer_match import answers_match
from vimultiagent.core.llm import extract_json
from vimultiagent.core.schemas import Solution

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "llm"
REPORTS = ROOT / "eval" / "reports"
DATASETS = ROOT / "eval" / "datasets"


# ---------------------------------------------------------------------------
# Thu thập
# ---------------------------------------------------------------------------


def load_problems() -> dict[str, dict[str, Any]]:
    """id -> bản ghi đề bài, gộp mọi tập dữ liệu có mặt."""
    out: dict[str, dict[str, Any]] = {}
    for f in DATASETS.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                out[d["id"]] = d
    return out


def load_rows() -> list[dict[str, Any]]:
    """Các dòng kết quả của lần chạy benchmark GẦN NHẤT có đủ nhãn."""
    reports = sorted(REPORTS.glob("*_full.json"))
    if not reports:
        return []
    data = json.loads(reports[-1].read_text(encoding="utf-8"))
    return data.get("rows", [])


def mine_solutions() -> list[Solution]:
    """Bóc mọi lời giải Solver ra khỏi cache LLM.

    Cache không lưu prompt, nên ở đây ta chỉ lấy được lời giải — việc ghép ngược
    về đề bài làm ở `attach_labels` thông qua đáp số.
    """
    sols: list[Solution] = []
    for f in sorted(CACHE.glob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            obj = extract_json(payload.get("text", ""))
        except Exception:  # noqa: BLE001
            continue
        if "steps" not in obj or "final_answer" not in obj:
            continue  # Analyzer / Explainer / Verifier — không phải Solver
        try:
            sols.append(Solution.model_validate(obj))
        except Exception:  # noqa: BLE001
            continue
    return sols


def attach_labels(
    sols: list[Solution], rows: list[dict[str, Any]], problems: dict[str, dict[str, Any]]
) -> list[tuple[Solution, str, bool]]:
    """Ghép (lời giải, đề bài, đúng/sai).

    Ghép bằng ĐÁP SỐ chứ không bằng thứ tự: cache không giữ thứ tự chạy, và một đề
    có thể có nhiều lời giải (vòng sửa). Dùng chung `answers_match` với bộ chấm —
    tự viết logic so sánh riêng ở đây là đúng cái lỗi đã ghi trong docs/04-ket-qua.md.
    """
    out: list[tuple[Solution, str, bool]] = []
    for sol in sols:
        for row in rows:
            pid = row.get("id")
            prob = problems.get(pid)
            if not prob:
                continue
            pred = str(row.get("pred") or "")
            hit = answers_match(sol.final_answer, pred)
            if not hit and sol.mcq_choice and row.get("pred_choice"):
                hit = sol.mcq_choice.strip().upper() == str(row["pred_choice"]).strip().upper()
            if hit:
                out.append((sol, prob["problem"], bool(row.get("correct"))))
                break
    return out


# ---------------------------------------------------------------------------
# Chấm
# ---------------------------------------------------------------------------


def summarise(vals: list[float]) -> str:
    if not vals:
        return "(không có mẫu)"
    v = sorted(vals)
    n = len(v)
    return (
        f"n={n}  min={v[0]:.3f}  p25={v[n // 4]:.3f}  trung vị={v[n // 2]:.3f}  "
        f"p75={v[3 * n // 4]:.3f}  max={v[-1]:.3f}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu", help="cpu (mặc định) hoặc cuda")
    args = ap.parse_args()

    problems = load_problems()
    rows = load_rows()
    sols = mine_solutions()
    labelled = attach_labels(sols, rows, problems)

    print("=" * 78)
    print("CHẨN ĐOÁN ViSTEM-PRM TRÊN LỜI GIẢI THẬT")
    print("=" * 78)
    print(f"Đề bài trong các tập:        {len(problems)}")
    print(f"Dòng benchmark có nhãn:      {len(rows)}")
    print(f"Lời giải Solver bóc từ cache:{len(sols):>4}")
    print(f"Ghép được nhãn đúng/sai:     {len(labelled):>4}")
    if not labelled:
        print("\nKhông ghép được mẫu nào — chạy benchmark trước, hoặc cache đã bị xoá.")
        return

    from vimultiagent.core.config import get_settings
    from vimultiagent.models.prm.infer import PRM

    cfg = get_settings().prm
    ckpt = ROOT / cfg.get("checkpoint", "checkpoints/prm")
    prm = PRM(ckpt, device=args.device, max_length=int(cfg.get("max_length", 256)))
    thr = float(cfg.get("reject_threshold", 0.55))
    print(f"Checkpoint: {ckpt.name} trên {prm.device} · ngưỡng hiện hành = {thr}\n")

    ok_scores: list[float] = []
    bad_scores: list[float] = []
    detail: list[tuple[str, bool, float, int]] = []

    for sol, problem, correct in labelled:
        steps = [prm._step_text(s) for s in sol.steps]  # noqa: SLF001
        if not steps:
            continue
        probs = prm.score_steps(problem, steps)
        worst = min(probs)
        (ok_scores if correct else bad_scores).append(worst)
        detail.append((sol.final_answer[:28], correct, worst, len(steps)))

    print("P(đúng) THẤP NHẤT trên các bước — đây là con số quyết định bác bỏ hay không")
    print(f"  Lời giải ĐÚNG : {summarise(ok_scores)}")
    print(f"  Lời giải SAI  : {summarise(bad_scores)}")

    # Nếu ngưỡng hiện hành đem áp vào phân phối thật thì chuyện gì xảy ra?
    fp = sum(1 for v in ok_scores if v < thr)
    tp = sum(1 for v in bad_scores if v < thr)
    print(f"\nÁp ngưỡng {thr} lên phân phối THẬT:")
    print(f"  Báo oan lời giải đúng : {fp}/{len(ok_scores)}"
          + (f"  ({fp / len(ok_scores):.0%})" if ok_scores else ""))
    print(f"  Bắt được lời giải sai : {tp}/{len(bad_scores)}"
          + (f"  ({tp / len(bad_scores):.0%})" if bad_scores else ""))

    print("\nChi tiết từng lời giải:")
    print(f"  {'đáp số':<30} {'nhãn':<6} {'P(đúng) min':>12} {'#bước':>6}")
    for ans, correct, worst, n in sorted(detail, key=lambda x: x[2]):
        print(f"  {ans:<30} {'ĐÚNG' if correct else 'SAI':<6} {worst:>12.4f} {n:>6}")

    out = REPORTS / "prm_diag_real.json"
    out.write_text(
        json.dumps(
            {
                "n_matched": len(labelled),
                "threshold": thr,
                "correct_scores": ok_scores,
                "incorrect_scores": bad_scores,
                "false_alarm_rate": (fp / len(ok_scores)) if ok_scores else None,
                "detection_rate": (tp / len(bad_scores)) if bad_scores else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nĐã ghi {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
