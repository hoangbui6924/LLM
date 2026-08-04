"""Bộ điều phối SOP — MetaGPT-inspired.

Vì sao TỰ VIẾT thay vì dùng LangGraph/AutoGen: đồ thị của hệ thống này là một chuỗi
tuyến tính kèm ĐÚNG MỘT vòng lặp có điều kiện. Cài đặt trực tiếp mất ~200 dòng,
không thêm phụ thuộc nào, và mọi mili-giây đều đo được — thứ mà phần thực nghiệm
của báo cáo cần. Khái niệm mượn từ MetaGPT (chuyên biệt hoá vai trò + thông điệp có
kiểu + quy trình chuẩn); phần cài đặt là của dự án.

Luồng:
    cache → analyzer → retriever → solver → verifier
                                      ↑         ↓ FAIL (k < max_repair)
                                      └── repair ┘
                                                ↓
                                            explainer → ghi bộ nhớ
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from ..agents import analyzer, explainer, retriever, solver, verifier
from ..core.config import get_settings
from ..core.llm import LLMClient
from ..core.schemas import (
    AgentSpan,
    ProblemSpec,
    RetrievalResult,
    SolveResult,
    Solution,
    SolvedExample,
    Trace,
    Verdict,
    VerificationReport,
)

# Nhãn tiếng Việt hiển thị trên timeline của frontend
AGENT_LABELS = {
    "analyzer": "Phân tích đề",
    "retriever": "Truy hồi kiến thức",
    "solver": "Giải bài",
    "verifier": "Kiểm chứng",
    "repair": "Sửa lỗi",
    "explainer": "Soạn lời giảng",
}


class Orchestrator:
    def __init__(
        self,
        profile: str | None = None,
        strategy: str | None = None,
        remember: bool = True,
    ) -> None:
        self.s = get_settings()
        self.profile = profile or self.s.profile
        self.strategy_name = strategy or self.s.strategy
        self.cfg = self.s.strategy_cfg(self.strategy_name)
        # Tắt khi chạy test hoặc benchmark: memory pool là dữ liệu huấn luyện cho
        # phần sau, đổ lời giải giả hoặc lời giải của tập đánh giá vào đó sẽ làm
        # hỏng cả hai.
        self.remember = remember

    # ------------------------------------------------------------------
    # API chính: chạy và phát sự kiện (dùng cho SSE)
    # ------------------------------------------------------------------

    @staticmethod
    async def _step(coro: Any, deadline: float, what: str) -> Any:
        """Chạy một bước với hạn chót CHUNG của cả lượt giải.

        Cấp cho mỗi bước phần thời gian CÒN LẠI, không chia theo tỉ lệ cố định.
        Chia tỉ lệ là sai: bước nhanh không dùng hết phần của mình thì phần đó bị
        vứt đi, còn bước chậm bị cắt oan dù tổng vẫn còn dư — đã xảy ra thật
        (Phân tích đề bị cắt ở 60 giây trong khi cả lượt mới chạy 60/300 giây).
        """
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            raise TimeoutError(f"Hết thời gian trước khi chạy '{what}'")
        try:
            return await asyncio.wait_for(coro, timeout=remaining)
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Bước '{what}' bị cắt: cả lượt giải vượt quá {remaining:.0f} giây còn lại"
            ) from e


    async def stream(self, problem: str) -> AsyncIterator[dict[str, Any]]:
        """Phát sự kiện theo tiến độ.

        Có TRẦN THỜI GIAN TỔNG. Không có nó thì một lượt gọi treo sẽ treo mãi, và
        người dùng ngồi nhìn màn hình 'đang chạy' vô thời hạn — đã xảy ra thật.
        Thà trả về lời giải dở dang kèm lý do còn hơn không trả về gì.
        """
        budget = float(self.s.limits.get("total_timeout_s", 300))
        deadline = time.monotonic() + budget
        trace = Trace(strategy=self.strategy_name, profile=self.profile)
        result = SolveResult(trace=trace)

        def ev(kind: str, agent: str, **kw: Any) -> dict[str, Any]:
            return {
                "type": kind,
                "agent": agent,
                "label": AGENT_LABELS.get(agent, agent),
                "elapsed_ms": round(trace.total_ms, 1),
                **kw,
            }

        async with LLMClient(profile=self.profile) as client:
            try:
                # ---- 1. Phân tích đề ------------------------------------
                yield ev("agent_start", "analyzer")
                if self.cfg.get("llm_analyzer", True):
                    spec, spans = await self._step(
                        analyzer.analyze(client, problem, profile=self.profile),
                        deadline, 'Phân tích đề')
                else:
                    spec, spans = analyzer.analyze_heuristic(problem), []
                trace.spans.extend(spans)
                result.spec = spec
                yield ev(
                    "agent_end", "analyzer",
                    data={
                        "domain": spec.domain,
                        "subtopic": spec.subtopic,
                        "question_type": spec.question_type,
                        "givens": [q.model_dump() for q in spec.givens],
                        "unknowns": [q.model_dump() for q in spec.unknowns],
                        "ambiguity_flags": spec.ambiguity_flags,
                    },
                )

                # ---- 2. Truy hồi ----------------------------------------
                retrieval = RetrievalResult()
                if self.cfg.get("use_retrieval", True):
                    yield ev("agent_start", "retriever")
                    rcfg = self.s.retrieval
                    retrieval, rspan = retriever.retrieve(
                        spec,
                        top_k_knowledge=int(self.cfg.get(
                            "top_k_knowledge", rcfg.get("top_k_knowledge", 4))),
                        top_k_examples=int(rcfg.get("top_k_examples", 2)),
                    )
                    trace.spans.append(rspan)
                    yield ev(
                        "agent_end", "retriever",
                        data={
                            "knowledge": [
                                {"id": c.id, "title": c.title, "score": round(c.score, 3)}
                                for c in retrieval.knowledge
                            ],
                            "n_examples": len(retrieval.examples),
                            "backend": retrieval.backend,
                        },
                    )

                # ---- 3-4. Giải + kiểm, có vòng sửa ----------------------
                sol: Solution | None = None
                report: VerificationReport | None = None
                max_repair = int(self.cfg.get("max_repair", 1))
                tiers = list(self.cfg.get("verify_tiers", ["T1"]))
                n_samples = int(self.cfg.get("n_solver_samples", 1))

                for k in range(max_repair + 1):
                    agent_name = "solver" if k == 0 else "repair"
                    yield ev("agent_start", agent_name, round=k)

                    if k == 0 and n_samples > 1:
                        sol, spans, meta = await self._step(
                            solver.solve_self_consistent(
                                client, spec, retrieval, n=n_samples, profile=self.profile),
                            deadline, 'Giải bài (self-consistency)')
                        trace.spans.extend(spans)
                        yield ev("agent_end", agent_name, round=k,
                                 data={"self_consistency": meta,
                                       "final_answer": sol.final_answer,
                                       "n_steps": len(sol.steps)})
                    else:
                        sol, spans = await self._step(solver.solve(
                            client, spec, retrieval, profile=self.profile,
                            previous=sol if k > 0 else None,
                            feedback=report if k > 0 else None,
                            use_tools=not self.cfg.get("disable_tools", False),
                            # Vòng sửa dùng nhiệt độ cao hơn: lặp lại đúng hướng
                            # đã sai thì vô nghĩa, cần model đi hướng khác.
                            temperature=0.2 if k == 0 else 0.6,
                        ), deadline, 'Giải bài')
                        trace.spans.extend(spans)
                        yield ev(
                            "agent_end", agent_name, round=k,
                            data={
                                "final_answer": sol.final_answer,
                                "mcq_choice": sol.mcq_choice,
                                "n_steps": len(sol.steps),
                                "n_tool_calls": sum(len(s.tool_calls) for s in sol.steps),
                                "steps": [
                                    {
                                        "id": s.id, "goal_vi": s.goal_vi,
                                        "expression_latex": s.expression_latex,
                                        "result_latex": s.result_latex,
                                        "tools": [
                                            {"tool": t.tool, "ok": t.ok, "result": t.result[:200]}
                                            for t in s.tool_calls
                                        ],
                                    }
                                    for s in sol.steps
                                ],
                            },
                        )

                    result.solution = sol

                    yield ev("agent_start", "verifier", round=k)
                    report, vspans = await self._step(
                        verifier.verify(client, spec, sol, tiers, profile=self.profile),
                        deadline, 'Kiểm chứng')
                    trace.spans.extend(vspans)
                    result.verification = report
                    yield ev(
                        "agent_end", "verifier", round=k,
                        data={
                            "verdict": report.verdict.value,
                            "first_error_step": report.first_error_step,
                            "agreement": report.agreement,
                            "independent_answer": report.independent_answer,
                            "items": [i.model_dump() for i in report.items],
                        },
                    )

                    if report.verdict == Verdict.PASS:
                        break
                    if k < max_repair:
                        trace.repair_rounds = k + 1
                        yield ev("repair_needed", "repair", round=k,
                                 feedback=report.feedback_for_solver()[:600])

                assert sol is not None and report is not None

                # ---- 5. Soạn lời giảng ----------------------------------
                yield ev("agent_start", "explainer")
                exp, espans = await self._step(
                    explainer.explain(client, spec, sol, retrieval, report, profile=self.profile),
                    deadline, 'Soạn lời giảng')
                trace.spans.extend(espans)
                result.explanation = exp
                yield ev("agent_end", "explainer", data=exp.model_dump())

                # ---- 6. Chốt kết quả ------------------------------------
                result.confidence = self._confidence(report, sol)
                if report.verdict != Verdict.PASS:
                    result.warning_vi = (
                        "Hệ thống KHÔNG xác nhận được lời giải này sau "
                        f"{trace.repair_rounds} lần thử lại. Hãy đối chiếu kỹ trước khi tin."
                    )

                # Ghi vào memory pool — chỉ khi đã PASS. Đây là cơ chế tự khá lên
                # của hệ thống, và cũng là nguồn dữ liệu cho phần huấn luyện.
                # Chỉ ghi khi có kiểm chứng TẤT ĐỊNH đạt (SymPy/Pint/bảo toàn),
                # không chỉ dựa vào verdict của LLM. Pool từng bị nhiễm đáp án SAI
                # ("1,12 lít" cho bài đúng là 2,24) vì tin verdict của model 3B.
                det_ok = any(
                    i.passed and i.check_type in {"substitution", "conservation", "dimensional"}
                    for i in report.items
                )
                if report.verdict == Verdict.PASS and det_ok and self.remember:
                    self._remember(spec, sol)

            except Exception as e:  # noqa: BLE001
                result.error = f"{type(e).__name__}: {e}"
                yield ev("error", "system", message=result.error)

        yield {
            "type": "done",
            "result": result.model_dump(mode="json"),
            "summary": {
                "total_ms": round(trace.total_ms, 1),
                "by_agent_ms": {k: round(v, 1) for k, v in trace.by_agent_ms().items()},
                "total_tokens": trace.total_tokens,
                "cost_usd": round(trace.total_cost_usd, 5),
                "repair_rounds": trace.repair_rounds,
                "cached_calls": sum(1 for s in trace.spans if s.cached),
                # Phân rã ĐỘ TRỄ KHÔNG PHẢI DO SINH TOKEN. Một lượt kiểm chứng từng
                # đo được 73,2 giây trong khi chỉ sinh vài trăm token; nếu không tách
                # ra thì không biết nên đi sửa hạn mức, sửa schema, hay đổi model.
                "wait_ms": round(sum(s.wait_ms for s in trace.spans), 1),
                "extra_attempts": sum(max(0, s.attempts - 1) for s in trace.spans),
                "schema_retries": sum(
                    1 for s in trace.spans if s.meta.get("schema_attempt", 1) > 1
                ),
                "retry_reasons": sorted(
                    {r for s in trace.spans for r in s.retry_reasons}
                ),
            },
        }

    # ------------------------------------------------------------------

    async def solve(self, problem: str) -> SolveResult:
        """Chạy không streaming — dùng cho benchmark."""
        final: dict[str, Any] | None = None
        async for ev in self.stream(problem):
            if ev["type"] == "done":
                final = ev
        assert final is not None
        return SolveResult.model_validate(final["result"])

    # ------------------------------------------------------------------

    @staticmethod
    def _confidence(report: VerificationReport, sol: Solution) -> float:
        """Độ tin cậy hiệu chỉnh. Có chủ đích đặt NẶNG vào kết quả kiểm chứng chứ
        không phải vào self_confidence của Solver — model tự chấm mình thì luôn
        lạc quan, đó là điều đã biết rõ."""
        base = {Verdict.PASS: 0.85, Verdict.UNCERTAIN: 0.45, Verdict.FAIL: 0.2}[report.verdict]
        if report.agreement:
            base += 0.1
        det = [i for i in report.items if i.check_type in {"substitution", "conservation", "dimensional"}]
        if det and all(i.passed for i in det):
            base += 0.05
        base += 0.05 * (sol.self_confidence - 0.5)
        return max(0.0, min(1.0, base))

    @staticmethod
    def _remember(spec: ProblemSpec, sol: Solution) -> None:
        try:
            from ..memory.store import get_store  # noqa: PLC0415
            from ..models.prm.data_build import step_text  # noqa: PLC0415

            sketch = " → ".join(s.goal_vi for s in sol.steps if s.goal_vi)[:600]
            get_store().add_example(
                SolvedExample(
                    id=f"ex_{int(time.time() * 1000)}",
                    domain=spec.domain,
                    subtopic=spec.subtopic,
                    problem=spec.raw_text[:1000],
                    solution_sketch=sketch,
                    final_answer=sol.final_answer,
                    # Ghi bằng ĐÚNG hàm mà PRM dùng lúc suy luận. `solution_sketch`
                    # ở trên chỉ nối goal_vi nên hợp cho few-shot, nhưng dùng nó làm
                    # dữ liệu huấn luyện PRM thì sai phân phối ngay từ gốc.
                    steps=[step_text(s) for s in sol.steps],
                )
            )
        except Exception:  # noqa: BLE001
            pass  # ghi bộ nhớ hỏng không được ảnh hưởng tới lời giải đã trả cho học sinh


async def solve_problem(
    problem: str, profile: str | None = None, strategy: str | None = None
) -> SolveResult:
    return await Orchestrator(profile=profile, strategy=strategy).solve(problem)
