"""Đo KPI "tỉ lệ tác tử checker phát hiện sai ≥ 85%".

    python eval/run_mutation_test.py --n 60                    # đủ 4 tầng
    python eval/run_mutation_test.py --n 200 --tiers T0,T1     # không cần API key

Cách đo: lấy lời giải ĐÚNG (sinh từ template, đúng theo định nghĩa), tiêm MỘT lỗi
đã biết, rồi hỏi Verifier. Ta biết chính xác đáp án nên recall đo được, không phải ước lượng.

Đồng thời chạy cả lời giải KHÔNG bị tiêm lỗi để đo precision. Chỉ báo recall là
gian lận: một Verifier luôn nói "SAI" sẽ đạt recall 100%.

Bảng recall theo TỪNG LOẠI LỖI là kết quả có giá trị nhất — nó cho thấy tầng tất
định (T1) gánh loại lỗi nào và tầng LLM (T2/T3) gánh loại nào.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vimultiagent.agents.verifier import verify  # noqa: E402
from vimultiagent.core.llm import LLMClient  # noqa: E402
from vimultiagent.core.schemas import ProblemSpec, Solution, SolutionStep  # noqa: E402
from vimultiagent.models.prm import mutate, synth  # noqa: E402

REPORTS = ROOT / "eval" / "reports"


def to_solution(item: dict[str, Any], steps: list[str]) -> tuple[ProblemSpec, Solution]:
    spec = ProblemSpec(
        domain=item["domain"], subtopic=item.get("subtopic", ""),
        question_type="numeric", raw_text=item["problem"], confidence=1.0,
    )
    sol = Solution(
        steps=[SolutionStep(id=i + 1, goal_vi=s, justification_vi=s) for i, s in enumerate(steps)],
        final_answer=item["answer"], unit=item.get("unit"), self_confidence=0.8,
    )
    return spec, sol


async def check_one(
    client: LLMClient, spec: ProblemSpec, sol: Solution, tiers: list[str]
) -> tuple[str, float]:
    t0 = time.time()
    report, _ = await verify(client, spec, sol, tiers)
    return report.verdict.value, (time.time() - t0) * 1000.0


async def run(n: int, tiers: list[str], seed: int) -> None:
    rng = random.Random(seed)
    items = synth.generate(n, seed=seed)

    cases: list[dict[str, Any]] = []
    for it in items:
        # bản sạch -> dùng đo precision
        cases.append({"item": it, "steps": it["steps"], "mutated": False,
                      "mutation_type": "none", "error_step": None})
        m = mutate.mutate_solution(it["steps"], rng)
        if m:
            cases.append({"item": it, "steps": m["steps"], "mutated": True,
                          "mutation_type": m["mutation_type"], "error_step": m["error_step"],
                          "description": m["description"]})

    print(f"Kiểm {len(cases)} trường hợp "
          f"({sum(1 for c in cases if c['mutated'])} có lỗi tiêm, "
          f"{sum(1 for c in cases if not c['mutated'])} sạch) | tầng: {','.join(tiers)}")

    results: list[dict[str, Any]] = []
    async with LLMClient() as client:
        sem = asyncio.Semaphore(3)

        async def one(c: dict[str, Any], idx: int) -> None:
            spec, sol = to_solution(c["item"], c["steps"])
            async with sem:
                try:
                    verdict, ms = await check_one(client, spec, sol, tiers)
                except Exception as e:  # noqa: BLE001
                    verdict, ms = f"ERROR:{type(e).__name__}", 0.0
            flagged = verdict in ("FAIL", "UNCERTAIN")
            hit = flagged == c["mutated"]
            results.append({
                "idx": idx, "domain": c["item"]["domain"], "mutated": c["mutated"],
                "mutation_type": c["mutation_type"], "verdict": verdict,
                "flagged": flagged, "correct_judgement": hit, "latency_ms": round(ms, 1),
            })
            if (idx + 1) % 20 == 0:
                print(f"  … {idx + 1}/{len(cases)}")

        await asyncio.gather(*[one(c, i) for i, c in enumerate(cases)])

    # ---- chỉ số ----
    mutated = [r for r in results if r["mutated"]]
    clean = [r for r in results if not r["mutated"]]
    tp = sum(1 for r in mutated if r["flagged"])
    fn = len(mutated) - tp
    fp = sum(1 for r in clean if r["flagged"])
    tn = len(clean) - fp

    recall = tp / len(mutated) if mutated else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    lat = sorted(r["latency_ms"] for r in results)

    print(f"\n{'=' * 64}\nKẾT QUẢ KIỂM CHỨNG (tầng {','.join(tiers)})\n{'=' * 64}")
    print(f"  Tỉ lệ phát hiện lỗi (recall) : {recall:.1%}   "
          f"{'✓ ĐẠT KPI ≥85%' if recall >= 0.85 else '✗ CHƯA ĐẠT KPI 85%'}")
    print(f"  Precision (không báo oan)    : {precision:.1%}")
    print(f"  F1                           : {f1:.3f}")
    print(f"  TP={tp}  FN={fn} (bỏ sót)  FP={fp} (báo oan)  TN={tn}")
    print(f"  Độ trễ trung vị              : {lat[len(lat) // 2]:.0f} ms")

    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "caught": 0})
    for r in mutated:
        by_type[r["mutation_type"]]["n"] += 1
        by_type[r["mutation_type"]]["caught"] += int(r["flagged"])

    print(f"\n  {'Loại lỗi':<14}{'Bắt được':>10}{'Recall':>9}")
    print("  " + "-" * 33)
    rows_md = []
    for mt, v in sorted(by_type.items(), key=lambda x: -x[1]["n"]):
        rec = v["caught"] / v["n"] if v["n"] else 0.0
        print(f"  {mt:<14}{v['caught']:>4}/{v['n']:<5}{rec:>9.1%}")
        rows_md.append(f"| {mt} | {v['caught']}/{v['n']} | {rec:.1%} |")

    by_dom: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "caught": 0})
    for r in mutated:
        by_dom[r["domain"]]["n"] += 1
        by_dom[r["domain"]]["caught"] += int(r["flagged"])
    print(f"\n  {'Môn':<14}{'Bắt được':>10}{'Recall':>9}")
    print("  " + "-" * 33)
    for d, v in by_dom.items():
        print(f"  {d:<14}{v['caught']:>4}/{v['n']:<5}{v['caught'] / v['n']:>9.1%}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORTS / f"{stamp}_mutation_{'_'.join(tiers)}.json"
    out.write_text(
        json.dumps({
            "tiers": tiers, "n_cases": len(cases),
            "recall": round(recall, 4), "precision": round(precision, 4), "f1": round(f1, 4),
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "latency_median_ms": lat[len(lat) // 2] if lat else 0,
            "by_mutation_type": {k: dict(v) for k, v in by_type.items()},
            "by_domain": {k: dict(v) for k, v in by_dom.items()},
            "results": results,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nĐã ghi: {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="số lời giải gốc")
    ap.add_argument("--tiers", default="T0,T1,T2,T3",
                    help="T0,T1 chạy được KHÔNG cần API key")
    ap.add_argument("--seed", type=int, default=123)
    a = ap.parse_args()
    asyncio.run(run(a.n, [t.strip() for t in a.tiers.split(",")], a.seed))


if __name__ == "__main__":
    main()
