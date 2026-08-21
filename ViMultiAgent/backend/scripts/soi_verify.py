"""Soi Verify Agent trên những bài cụ thể — công cụ chẩn đoán, không phải đo đạc.

Chạy:  python scripts/soi_verify.py ds_nb_007 hh_th_012

In ra toàn bộ lời giải và TỪNG PHÉP KIỂM của Verify, kèm phép kiểm nào không đạt.
Dùng khi bench báo một bài bị "báo oan" (đáp án đúng mà Verify kêu FAIL) và cần
biết chính xác tầng nào kêu sai.

Bench chỉ ghi verdict cuối, không ghi lý do — mà lý do mới là thứ sửa được.
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents import planner, recompute_agent, router, verify_agent  # noqa: E402
from agents.manager import _SUBJECT_AGENTS  # noqa: E402
from core import config  # noqa: E402
from tools import arbiter  # noqa: E402

DE = GOC / "eval" / "data" / "de_chuan.csv"


def doc_bai(cac_ma: list[str]) -> list[dict]:
    with DE.open(encoding="utf-8-sig", newline="") as f:
        tat_ca = list(csv.DictReader(f))
    tra = {r["id"]: r for r in tat_ca}
    ra = []
    for ma in cac_ma:
        if ma in tra:
            ra.append(tra[ma])
        else:
            print(f"(không thấy bài {ma})")
    return ra


async def soi(bai: dict) -> None:
    print("=" * 74)
    print(f"{bai['id']}  [{bai['level']}] {bai['subject']} / {bai['topic']}")
    print("=" * 74)
    print(f"Đề   : {bai['question']}")
    chuan = bai["answer_value"] or bai["answer_expr"]
    print(f"Chuẩn: {chuan} {bai['answer_unit']}".rstrip())
    print()

    plan, _ = await planner.run(bai["question"])
    route, _ = await router.run(plan)
    plan.subject = route.subject
    print(f"Router -> {route.agent_name} ({route.decided_by})")

    agent_mod = _SUBJECT_AGENTS.get(route.agent_name)
    (sol, sspan), (doc_lap, _) = await asyncio.gather(
        agent_mod.run(plan, None),
        recompute_agent.compute(plan, timeout=config.TIMEOUT_RECOMPUTE),
    )
    sua = arbiter.enforce(sol)
    if sua:
        print(f"Trọng tài SymPy sửa {len(sua)} bước: " + "; ".join(s.mo_ta() for s in sua))

    print(f"\n--- LỜI GIẢI ({len(sol.steps)} bước) ---")
    for st in sol.steps:
        print(f"  Bước {st.id}: {st.goal_vi}")
        if st.expression:
            print(f"     expression = {st.expression!r}")
        if st.result:
            print(f"     result     = {st.result!r}")
    print(f"  ĐÁP SỐ: {sol.final_answer!r}   (confidence {sol.confidence})")

    print(f"\n--- BỘ TÍNH LẠI ĐỘC LẬP ---")
    if doc_lap.co_gia_tri:
        print(f"  giá trị  : {doc_lap.mo_ta()!r}")
        print(f"  cách làm : {doc_lap.approach_vi}")
        kt = recompute_agent.compare(doc_lap, sol.final_answer)
        print(f"  đối chiếu: {'ĐẠT' if kt and kt.passed else 'KHÔNG ĐẠT' if kt else '(không kết luận)'}")
        if kt:
            print(f"             {kt.detail_vi}")
    else:
        print("  (không tính được)")

    print(f"\n--- PHÉP KIỂM TẤT ĐỊNH ---")
    for c in verify_agent.deterministic_checks(plan, sol):
        print(f"  [{'ĐẠT ' if c.passed else 'HỎNG'}] {c.kind:<12} bước {c.step_id}: {c.detail_vi}")

    report, _ = await verify_agent.run(plan, sol, doc_lap)
    print(f"\n--- KẾT LUẬN VERIFY: {report.verdict} ---")
    for c in report.checks:
        print(f"  [{'ĐẠT ' if c.passed else 'HỎNG'}] {c.kind:<12} bước {c.step_id}: {c.detail_vi}")
    if report.suggestion_vi:
        print(f"  Gợi ý sửa: {report.suggestion_vi}")
    print()


async def main(cac_ma: list[str]) -> int:
    bai = doc_bai(cac_ma)
    if not bai:
        print("Cách dùng: python scripts/soi_verify.py <mã bài> [<mã bài> ...]")
        return 2
    for b in bai:
        await soi(b)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
