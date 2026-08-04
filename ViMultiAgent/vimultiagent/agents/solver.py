"""Tác tử GIẢI chuyên ngành (Toán / Vật lý / Hoá học).

Một lượt gọi LLM sinh toàn bộ lời giải KÈM các lượt gọi công cụ mà nó muốn dùng để
tự chứng minh. Ta chạy công cụ sau đó, và kết quả trở thành bằng chứng cho Verifier
tầng T1.

Vì sao không để LLM gọi công cụ rồi suy nghĩ tiếp (vòng lặp ReAct nhiều lượt):
mỗi vòng thêm ~2-4 giây, và với ngân sách 45 giây cho cả pipeline 6 tác tử thì
không đủ chỗ. Đánh đổi này được ghi nhận rõ; vòng repair bù lại phần lớn thiệt hại.
"""

from __future__ import annotations

from typing import Any

from ..core.llm import LLMClient
from ..core.prompts import SOLVER_REPAIR_USER, SOLVER_USER, solver_system
from ..core.schemas import (
    AgentSpan,
    ProblemSpec,
    RetrievalResult,
    Solution,
    VerificationReport,
)
from ..tools import recompute
from ..tools.registry import run_tools, tools_prompt

AGENT_BY_DOMAIN = {
    "math": "solver_math",
    "physics": "solver_physics",
    "chemistry": "solver_chemistry",
}


def _fmt_quantities(qs: list[Any]) -> str:
    if not qs:
        return "(không có)"
    return "; ".join(
        f"{q.symbol}"
        + (f" = {q.value}" if q.value is not None else "")
        + (f" {q.unit}" if q.unit else "")
        + (f" ({q.description_vi})" if q.description_vi else "")
        for q in qs
    )


def _fmt_knowledge(r: RetrievalResult) -> str:
    if not r.knowledge:
        return "(kho kiến thức trống — hãy dựa vào hiểu biết của bạn)"
    return "\n".join(
        f"[{c.id}] {c.title}\n  {c.content}"
        + (f"\n  Dùng khi: {c.applicable_when}" if c.applicable_when else "")
        + (f"\n  ⚠ Bẫy: {c.pitfalls}" if c.pitfalls else "")
        for c in r.knowledge
    )


def _fmt_examples(r: RetrievalResult) -> str:
    if not r.examples:
        return ""
    body = "\n".join(
        f"- Đề: {e.problem[:250]}\n  Hướng giải: {e.solution_sketch[:350]}\n  Đáp án: {e.final_answer}"
        for e in r.examples
    )
    return f"\nBÀI TƯƠNG TỰ ĐÃ GIẢI ĐÚNG (tham khảo cách làm, KHÔNG chép đáp án):\n{body}\n"


def _execute_tools(sol: Solution) -> list[dict[str, Any]]:
    """Chạy các công cụ mà Solver khai báo, ghi kết quả ngược vào từng bước."""
    evidence: list[dict[str, Any]] = []
    for step in sol.steps:
        if not step.tool_calls:
            continue
        requested = [{"tool": tc.tool, "args": tc.args} for tc in step.tool_calls]
        executed = run_tools(requested)
        step.tool_calls = executed
        for tc in executed:
            evidence.append(
                {
                    "step": step.id,
                    "tool": tc.tool,
                    "ok": tc.ok,
                    "result": tc.result,
                    "error": tc.error,
                    "flags": tc.flags,
                }
            )
    return evidence


def format_tool_evidence(sol: Solution) -> str:
    """Bằng chứng công cụ, định dạng cho Verifier đọc."""
    lines: list[str] = []
    for step in sol.steps:
        for tc in step.tool_calls:
            status = "OK" if tc.ok else "LỖI"
            lines.append(f"[bước {step.id}] {tc.tool} -> {status}: {tc.result or tc.error}")
    if not lines:
        return "BẰNG CHỨNG CÔNG CỤ: (lời giải không dùng công cụ nào)"
    return "BẰNG CHỨNG CÔNG CỤ (kết quả tính toán tất định, đáng tin hơn lập luận):\n" + "\n".join(lines)


async def solve(
    client: LLMClient,
    spec: ProblemSpec,
    retrieval: RetrievalResult,
    *,
    profile: str | None = None,
    temperature: float | None = None,
    previous: Solution | None = None,
    feedback: VerificationReport | None = None,
    use_tools: bool = True,
) -> tuple[Solution, list[AgentSpan]]:
    """Giải bài. Truyền `previous` + `feedback` để chạy vòng sửa lỗi.

    `use_tools=False` dùng cho ablation A4 — Solver vẫn được phép *khai báo* lượt gọi
    công cụ (giữ nguyên prompt để so sánh công bằng), nhưng ta không chạy chúng, nên
    Verifier T1 không có bằng chứng tất định nào để dựa vào.
    """
    domain = spec.domain
    agent = AGENT_BY_DOMAIN.get(domain, "solver_math")
    system = solver_system(domain, tools_prompt(domain))

    if previous is not None and feedback is not None:
        user = SOLVER_REPAIR_USER.format(
            problem=spec.raw_text,
            previous_solution=previous.as_plain_text(),
            feedback=feedback.feedback_for_solver(),
            tool_evidence=format_tool_evidence(previous),
        )
    else:
        choices_block = ""
        if spec.choices:
            opts = "\n".join(f"  {k}. {v}" for k, v in sorted(spec.choices.items()))
            choices_block = f"- Phương án:\n{opts}\n"
        user = SOLVER_USER.format(
            problem=spec.raw_text,
            domain=domain,
            subtopic=spec.subtopic or "(chưa xác định)",
            question_type=spec.question_type,
            givens=_fmt_quantities(spec.givens),
            unknowns=_fmt_quantities(spec.unknowns),
            constraints="; ".join(spec.constraints) or "(không có)",
            choices_block=choices_block,
            knowledge=_fmt_knowledge(retrieval),
            examples_block=_fmt_examples(retrieval),
        )

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    sol, spans = await client.chat_json(
        agent, messages, Solution, profile=profile, temperature=temperature
    )

    if use_tools:
        _execute_tools(sol)
        # SymPy làm trọng tài: mọi kết quả bước tính lại được thì con số cuối cùng
        # là của SymPy, không phải của model. `_execute_tools` ở trên chỉ chạy công
        # cụ mà model TỰ KHAI — và model 3B thường quên khai, nên tới đây phần lớn
        # phép tính vẫn là nhẩm trong đầu.
        fixes = recompute.enforce(sol)
        if fixes:
            # Không sửa im lặng: ghi vào bước để Verifier và giao diện nói được là
            # đã sửa gì. Người dùng phải đối chiếu được.
            for f in fixes:
                st = next((s for s in sol.steps if s.id == f["step_id"]), None)
                if st is not None:
                    st.justification_vi = (
                        f"{st.justification_vi} "
                        f"[SymPy tính lại: {f['old_result']} -> {f['new_result']}]"
                    ).strip()
    else:
        for st in sol.steps:
            st.tool_calls = []

    # Giữ nhất quán giữa mcq_choice và final_answer — hai trường này mâu thuẫn
    # nhau là lỗi hay gặp, và nó làm hỏng việc chấm tự động ở bộ eval.
    if spec.question_type == "mcq" and spec.choices:
        if sol.mcq_choice and sol.mcq_choice.upper() in spec.choices:
            sol.mcq_choice = sol.mcq_choice.upper()
        elif sol.final_answer:
            for k, v in spec.choices.items():
                if v.strip() and v.strip().lower() in sol.final_answer.lower():
                    sol.mcq_choice = k
                    break
    return sol, spans


async def solve_self_consistent(
    client: LLMClient,
    spec: ProblemSpec,
    retrieval: RetrievalResult,
    n: int = 3,
    *,
    profile: str | None = None,
) -> tuple[Solution, list[AgentSpan], dict[str, Any]]:
    """Lấy mẫu n lời giải rồi bỏ phiếu theo đáp số (self-consistency).

    Dùng ở chế độ `rigorous` và làm baseline A1 trong ablation — để trả lời câu hỏi
    "đa tác tử có thật sự hơn việc chỉ lấy mẫu nhiều lần không?".
    """
    import asyncio

    temps = [0.2, 0.7, 1.0][:n] + [0.7] * max(0, n - 3)
    results = await asyncio.gather(
        *[
            solve(client, spec, retrieval, profile=profile, temperature=t)
            for t in temps[:n]
        ],
        return_exceptions=True,
    )

    sols: list[Solution] = []
    spans: list[AgentSpan] = []
    for r in results:
        if isinstance(r, BaseException):
            continue
        s, sp = r
        sols.append(s)
        spans.extend(sp)

    if not sols:
        raise RuntimeError("Tất cả các lần lấy mẫu của Solver đều thất bại")

    votes: dict[str, int] = {}
    for s in sols:
        key = (s.mcq_choice or s.final_answer or "").strip().lower()
        votes[key] = votes.get(key, 0) + 1
    winner = max(votes, key=lambda k: votes[k])
    best = next(
        (s for s in sols if (s.mcq_choice or s.final_answer or "").strip().lower() == winner),
        sols[0],
    )
    meta = {"n_samples": len(sols), "votes": votes, "agreement": votes[winner] / len(sols)}
    best.self_confidence = max(best.self_confidence, meta["agreement"])
    return best, spans, meta
