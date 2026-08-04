"""Trình chạy benchmark + ablation.

    python eval/run_bench.py --config full                  # hệ đầy đủ
    python eval/run_bench.py --config cot                   # baseline A0
    python eval/run_bench.py --config all --limit 10        # chạy hết, 10 bài đầu
    python eval/run_bench.py --config no_verifier,same_family

Kết quả ghi ra eval/reports/. Vì lớp LLM cache mọi lượt gọi ra đĩa, chạy lại cùng
một cấu hình gần như miễn phí — hãy tận dụng khi làm bảng kết quả cho báo cáo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.baselines import self_consistency, single_cot  # noqa: E402
from eval.metrics import aggregate, score_item, verifier_prf  # noqa: E402
from vimultiagent.graph.orchestrator import Orchestrator  # noqa: E402

DATASETS = {
    "seed": ROOT / "eval" / "datasets" / "seed_thpt.jsonl",
    "hard": ROOT / "eval" / "datasets" / "hard_thpt.jsonl",
}
REPORTS = ROOT / "eval" / "reports"

# ---------------------------------------------------------------------------
# Ablation — mỗi mục trả lời một câu hỏi cụ thể của báo cáo
# ---------------------------------------------------------------------------

ABLATIONS: dict[str, dict[str, Any]] = {
    "cot": {
        "label": "A0 · Single-agent CoT",
        "kind": "baseline_cot",
        "question": "Mức sàn — không đa tác tử, không công cụ, không kiểm chứng",
    },
    "sc5": {
        "label": "A1 · CoT + Self-Consistency (n=5)",
        "kind": "baseline_sc",
        "n": 5,
        "question": "Đa tác tử có hơn việc chỉ lấy mẫu nhiều lần không?",
    },
    "no_verifier": {
        "label": "A2 · Đủ hệ, BỎ Verifier",
        "kind": "system", "strategy": "fast",
        "overrides": {"verify_tiers": [], "max_repair": 0},
        "question": "Verifier đóng góp bao nhiêu điểm accuracy?",
    },
    "same_family": {
        "label": "A3 · Verifier CÙNG họ model với Solver",
        "kind": "system", "strategy": "balanced", "profile": "ablation_same_family",
        "question": "GIẢ THUYẾT TRUNG TÂM: khác họ model có thật sự tốt hơn?",
    },
    "no_tools": {
        "label": "A4 · Đủ hệ, BỎ công cụ",
        "kind": "system", "strategy": "balanced",
        "overrides": {"verify_tiers": ["T2", "T3"], "disable_tools": True},
        "question": "SymPy/Pint đóng góp bao nhiêu?",
    },
    "no_rag": {
        "label": "A5 · Đủ hệ, BỎ truy hồi",
        "kind": "system", "strategy": "balanced",
        "overrides": {"use_retrieval": False},
        "question": "Memory pool đóng góp bao nhiêu?",
    },
    "no_prm": {
        "label": "A6 · Đủ hệ, BỎ ViSTEM-PRM (tầng T0)",
        "kind": "system", "strategy": "balanced",
        "overrides": {"verify_tiers": ["T1", "T2", "T3"]},
        "question": "Model đã huấn luyện đóng góp bao nhiêu?",
    },
    "full": {
        "label": "A7 · HỆ ĐẦY ĐỦ",
        "kind": "system", "strategy": "balanced",
        "question": "Kết quả cuối cùng",
    },
    "rigorous": {
        "label": "A8 · Hệ đầy đủ, chế độ rigorous",
        "kind": "system", "strategy": "rigorous",
        "question": "Trần trên khi không giới hạn độ trễ",
    },
}


def load_dataset(
    name: str = "seed", limit: int | None = None, domain: str | None = None
) -> list[dict[str, Any]]:
    """`name` là 'seed', 'hard', hoặc 'all' (gộp cả hai)."""
    names = list(DATASETS) if name == "all" else [name]
    items: list[dict[str, Any]] = []
    for n in names:
        p = DATASETS.get(n)
        if p is None:
            raise SystemExit(f"Không có dataset '{n}'. Có: {', '.join(DATASETS)}, all")
        if not p.exists():
            raise SystemExit(
                f"Chưa có dataset: {p}\nChạy: python scripts/build_dataset"
                f"{'_hard' if n == 'hard' else ''}.py"
            )
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                d["dataset"] = n
                items.append(d)
    if domain:
        items = [i for i in items if i["domain"] == domain]
    return items[:limit] if limit else items


async def run_one(item: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    kind = cfg["kind"]
    row: dict[str, Any] = {
        "id": item["id"], "domain": item["domain"], "subtopic": item.get("subtopic", ""),
        "type": item.get("type", "numeric"),
    }

    try:
        if kind == "baseline_cot":
            out = await single_cot(item["problem"], profile=cfg.get("profile"))
            trace = out["trace"]
            row.update(
                pred=out["final_answer"], pred_choice=out["mcq_choice"],
                verdict=None, repair_rounds=0, error=out["error"],
                explanation_text=out["explanation_text"],
            )
        elif kind == "baseline_sc":
            out = await self_consistency(item["problem"], n=cfg.get("n", 5), profile=cfg.get("profile"))
            trace = out["trace"]
            row.update(
                pred=out["final_answer"], pred_choice=out["mcq_choice"],
                verdict=None, repair_rounds=0, error=out["error"],
                explanation_text=out["explanation_text"],
            )
        else:
            # remember=False: tập đánh giá TUYỆT ĐỐI không được lọt vào memory pool,
            # vì pool vừa là few-shot lúc chạy vừa là dữ liệu huấn luyện về sau.
            orch = Orchestrator(profile=cfg.get("profile"),
                                strategy=cfg.get("strategy", "balanced"), remember=False)
            for k, v in (cfg.get("overrides") or {}).items():
                orch.cfg[k] = v
            res = await orch.solve(item["problem"])
            trace = res.trace
            sol = res.solution
            row.update(
                pred=sol.final_answer if sol else "",
                pred_choice=sol.mcq_choice if sol else None,
                verdict=res.verification.verdict.value if res.verification else None,
                repair_rounds=trace.repair_rounds,
                confidence=res.confidence,
                error=res.error,
                # Lưu lại để eval/judge.py chấm chất lượng sư phạm mà không phải
                # chạy lại toàn bộ pipeline (tốn tiền và tốn thời gian).
                explanation=res.explanation.model_dump() if res.explanation else None,
                # Cùng lý do, cho Solution: mỗi lần chạy benchmark là một mẻ lời giải
                # THẬT kèm nhãn đúng/sai — đúng thứ dữ liệu mà PRM đang thiếu để thoát
                # khỏi chế độ advisory. Không lưu thì mỗi lần chạy là một lần vứt đi
                # (đã phải đi mining .cache/llm để có 8 mẫu — xem eval/run_prm_diag.py).
                solution=sol.model_dump() if sol else None,
            )

        row["latency_ms"] = (time.time() - t0) * 1000.0
        row["tokens"] = trace.total_tokens
        row["cost_usd"] = trace.total_cost_usd
        row["by_agent_ms"] = {k: round(v, 1) for k, v in trace.by_agent_ms().items()}
        row["cached"] = sum(1 for s in trace.spans if s.cached)
    except Exception as e:  # noqa: BLE001
        row.update(pred="", pred_choice=None, verdict=None, repair_rounds=0,
                   error=f"{type(e).__name__}: {e}", latency_ms=(time.time() - t0) * 1000.0,
                   tokens=0, cost_usd=0.0)

    row.update(score_item(row.get("pred"), row.get("pred_choice"), item))
    return row


async def run_config(name: str, items: list[dict[str, Any]], concurrency: int) -> dict[str, Any]:
    cfg = ABLATIONS[name]
    print(f"\n{'=' * 72}\n▶ {cfg['label']}\n  {cfg['question']}\n{'=' * 72}")

    sem = asyncio.Semaphore(concurrency)

    async def guarded(it: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            r = await run_one(it, cfg)
            mark = "✓" if r["correct"] else "✗"
            err = f"  ⚠ {r['error'][:60]}" if r.get("error") else ""
            print(f"  {mark} {r['id']:<5} {r['domain']:<10} "
                  f"pred={str(r.get('pred'))[:26]:<26} gold={r['gold']:<10} "
                  f"{r['latency_ms'] / 1000:5.1f}s{err}")
            return r

    rows = await asyncio.gather(*[guarded(it) for it in items])
    summary = aggregate(list(rows))
    summary["verifier"] = verifier_prf(list(rows))
    summary["config"] = name
    summary["label"] = cfg["label"]

    print(f"\n  → Accuracy {summary['accuracy']:.1%} ({summary['correct']}/{summary['n']}) "
          f"| p50 {summary['latency_p50_ms'] / 1000:.1f}s "
          f"| p95 {summary['latency_p95_ms'] / 1000:.1f}s "
          f"| ≤45s {summary['within_45s']:.0%} "
          f"| ${summary['total_cost_usd']:.4f}")
    if summary["verifier"]["tp"] + summary["verifier"]["fn"] > 0:
        v = summary["verifier"]
        print(f"    Verifier: P={v['precision']:.2f} R={v['recall']:.2f} F1={v['f1']:.2f}")
    for d, s in summary["by_domain"].items():
        print(f"    {d:<10} {s['accuracy']:.1%} ({s['correct']}/{s['n']})")

    return {"summary": summary, "rows": list(rows)}


async def main_async(args: argparse.Namespace) -> None:
    items = load_dataset(args.dataset, args.limit, args.domain)
    configs = list(ABLATIONS) if args.config == "all" else [c.strip() for c in args.config.split(",")]
    for c in configs:
        if c not in ABLATIONS:
            raise SystemExit(f"Không có cấu hình '{c}'. Có: {', '.join(ABLATIONS)}")

    print(f"Dataset: {len(items)} bài | Cấu hình: {', '.join(configs)}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_out: dict[str, Any] = {}

    for c in configs:
        all_out[c] = await run_config(c, items, args.concurrency)
        (REPORTS / f"{stamp}_{args.dataset}_{c}.json").write_text(
            json.dumps(all_out[c], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- bảng tổng hợp: dán thẳng vào báo cáo ----
    print(f"\n{'=' * 96}\nBẢNG TỔNG HỢP\n{'=' * 96}")
    hdr = f"{'Cấu hình':<42}{'Acc':>8}{'p50(s)':>9}{'p95(s)':>9}{'≤45s':>7}{'V-F1':>7}{'$':>9}"
    print(hdr + "\n" + "-" * 96)
    lines = [hdr, "-" * 96]
    for c in configs:
        s = all_out[c]["summary"]
        line = (f"{s['label']:<42}{s['accuracy']:>7.1%}"
                f"{s['latency_p50_ms'] / 1000:>9.1f}{s['latency_p95_ms'] / 1000:>9.1f}"
                f"{s['within_45s']:>7.0%}{s['verifier']['f1']:>7.2f}"
                f"{s['total_cost_usd']:>9.4f}")
        print(line)
        lines.append(line)

    md = REPORTS / f"{stamp}_summary.md"
    md.write_text(
        "# Kết quả benchmark ViMultiAgent\n\n"
        f"- Thời điểm: {datetime.now():%Y-%m-%d %H:%M}\n"
        f"- Số bài: {len(items)}\n\n```\n" + "\n".join(lines) + "\n```\n\n"
        + "\n".join(
            f"- **{ABLATIONS[c]['label']}** — {ABLATIONS[c]['question']}\n"
            f"  - Accuracy: {all_out[c]['summary']['accuracy']:.1%}"
            f" | theo môn: "
            + ", ".join(f"{d} {v['accuracy']:.0%}" for d, v in all_out[c]["summary"]["by_domain"].items())
            for c in configs
        ),
        encoding="utf-8",
    )
    print(f"\nBáo cáo: {md}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="full", help="tên cấu hình, 'all', hoặc danh sách cách nhau bởi dấu phẩy")
    p.add_argument("--dataset", default="seed", choices=["seed", "hard", "all"],
                   help="seed = dễ (đối chứng), hard = nhiều bước có bẫy")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--domain", default=None, choices=["math", "physics", "chemistry"])
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--list", action="store_true")
    args = p.parse_args()

    if args.list:
        for k, v in ABLATIONS.items():
            print(f"{k:<16} {v['label']:<44} {v['question']}")
        return
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
