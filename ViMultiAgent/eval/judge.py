"""Chấm chất lượng sư phạm bằng LLM-judge.

    python eval/judge.py --report eval/reports/20260804_120000_full.json

KPI của đề tài: "Explanation quality (10 giáo viên judge, Likert 5) ≥ 4/5".
Không mời được 10 giáo viên trong 5 ngày, nên làm hai tầng:

  1. LLM-judge chấm TOÀN BỘ tập — cho ra số liệu dày.
  2. Người chấm 20 mẫu — dùng để ĐO ĐỘ TIN CẬY của LLM-judge, không phải để thay thế.

Chỉ báo cáo điểm LLM-judge kèm hệ số tương quan với người chấm. Báo điểm LLM-judge
trần trụi mà không có đối chiếu là điều hội đồng sẽ vặn ngay.

Judge dùng model KHÁC HỌ với model sinh lời giải — cùng model thì nó chấm chính
tác phẩm của mình, và thiên lệch đó đã được ghi nhận rõ trong tài liệu.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402

from vimultiagent.core.llm import LLMClient  # noqa: E402
from vimultiagent.core.prompts import JUDGE_SYSTEM, JUDGE_USER  # noqa: E402

CRITERIA = ("correctness", "completeness", "clarity", "pedagogy", "formatting")


class JudgeOut(BaseModel):
    correctness: int = 3
    completeness: int = 3
    clarity: int = 3
    pedagogy: int = 3
    formatting: int = 3
    overall: int = 3
    rationale_vi: str = ""


def explanation_to_text(exp: dict[str, Any] | None) -> str:
    if not exp:
        return ""
    parts: list[str] = []
    if exp.get("restated_problem_vi"):
        parts.append(f"Đề bài yêu cầu: {exp['restated_problem_vi']}")
    if exp.get("prerequisites"):
        parts.append("Kiến thức cần dùng:\n" + "\n".join(f"- {p}" for p in exp["prerequisites"]))
    for i, s in enumerate(exp.get("steps") or [], 1):
        parts.append(
            f"Bước {i}. {s.get('title_vi', '')}\n{s.get('narrative_vi', '')}\n"
            f"{s.get('latex', '')}\nTại sao: {s.get('why_vi', '')}"
        )
    if exp.get("final_answer_vi"):
        parts.append(f"Đáp án: {exp['final_answer_vi']}")
    if exp.get("sanity_check_vi"):
        parts.append(f"Kiểm tra hợp lý: {exp['sanity_check_vi']}")
    if exp.get("common_mistakes"):
        parts.append("Lỗi thường gặp:\n" + "\n".join(f"- {m}" for m in exp["common_mistakes"]))
    return "\n\n".join(parts)


async def judge_one(
    client: LLMClient, problem: str, explanation: str, reference: str | None = None
) -> JudgeOut | None:
    if not explanation.strip():
        return None
    ref_block = f"ĐÁP ÁN THAM CHIẾU: {reference}\n\n" if reference else ""
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {
            "role": "user",
            "content": JUDGE_USER.format(
                problem=problem, reference_block=ref_block, explanation=explanation[:6000]
            ),
        },
    ]
    try:
        out, _ = await client.chat_json("judge", messages, JudgeOut)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ judge lỗi: {e}")
        return None


async def run(report_path: Path, dataset_path: Path, limit: int | None) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = report["rows"][:limit] if limit else report["rows"]

    problems = {
        json.loads(l)["id"]: json.loads(l)
        for l in dataset_path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    }

    # Bản báo cáo của run_bench không lưu explanation đầy đủ; chạy lại để lấy.
    print(f"Chấm {len(rows)} lời giải…")
    results: list[dict[str, Any]] = []

    async with LLMClient() as client:
        sem = asyncio.Semaphore(3)

        async def one(row: dict[str, Any]) -> None:
            item = problems.get(row["id"])
            if not item:
                return
            async with sem:
                exp_text = row.get("explanation_text") or explanation_to_text(row.get("explanation"))
                if not exp_text:
                    return
                out = await judge_one(client, item["problem"], exp_text, item.get("answer"))
                if out:
                    results.append(
                        {"id": row["id"], "domain": row["domain"], "correct": row.get("correct"),
                         **out.model_dump()}
                    )
                    print(f"  {row['id']:<5} overall={out.overall} "
                          f"(đúng={out.correctness} rõ={out.clarity} sư phạm={out.pedagogy})")

        await asyncio.gather(*[one(r) for r in rows])

    if not results:
        print("Không chấm được mẫu nào — bản báo cáo có lưu explanation không?")
        return

    print(f"\n{'=' * 60}\nĐIỂM CHẤT LƯỢNG SƯ PHẠM (Likert 1-5, n={len(results)})\n{'=' * 60}")
    summary: dict[str, Any] = {"n": len(results)}
    for c in (*CRITERIA, "overall"):
        vals = [r[c] for r in results]
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        summary[c] = {"mean": round(mean, 3), "std": round(sd, 3),
                      "pct_ge4": round(sum(1 for v in vals if v >= 4) / len(vals), 3)}
        flag = "✓" if mean >= 4.0 else "✗"
        print(f"  {flag} {c:<14} {mean:.2f} ± {sd:.2f}   (≥4: {summary[c]['pct_ge4']:.0%})")

    # Lời giải ĐÚNG và lời giải SAI có được chấm khác nhau không? Nếu không, judge
    # đang chấm văn phong chứ không chấm nội dung — và điểm của nó vô nghĩa.
    corr = [r["overall"] for r in results if r.get("correct")]
    wrong = [r["overall"] for r in results if r.get("correct") is False]
    if corr and wrong:
        print(f"\n  Lời giải đúng: {statistics.mean(corr):.2f} | "
              f"lời giải sai: {statistics.mean(wrong):.2f} "
              f"(chênh {statistics.mean(corr) - statistics.mean(wrong):+.2f})")
        summary["discrimination"] = round(statistics.mean(corr) - statistics.mean(wrong), 3)

    out_path = report_path.with_name(report_path.stem + "_judge.json")
    out_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nĐã ghi: {out_path}")
    print(f"KPI ≥4/5: {'ĐẠT ✓' if summary['overall']['mean'] >= 4.0 else 'CHƯA ĐẠT ✗'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--dataset", default=str(ROOT / "eval" / "datasets" / "seed_thpt.jsonl"))
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    asyncio.run(run(Path(a.report), Path(a.dataset), a.limit))


if __name__ == "__main__":
    main()
