"""Multi-Agent Manager — điều phối toàn bộ luồng ở mục 4.

    User -> Planner -> Router -> Subject Agent -> SymPy -> Verify -> Explain -> User

Manager là một *async generator*: nó phát sự kiện ra ngoài ngay khi từng agent
xong việc, thay vì chờ trọn gói rồi mới trả. Nhờ vậy frontend vẽ được tiến trình
"Planner ✓ Router ✓ Math Agent ✓..." theo thời gian thực, đúng yêu cầu mục 10.

Hai điều Manager chịu trách nhiệm mà không agent nào lo:

* **Ngân sách thời gian.** KPI là 45 giây cho cả lượt. Trước mỗi bước tốn kém,
  Manager kiểm tra còn đủ giờ không; hết giờ thì bỏ bước tinh chỉnh và đi thẳng
  tới Explain — trả lời chậm mà đủ còn hơn trả lời trống.
* **Vòng sửa sai.** Verify báo FAIL thì Subject Agent giải lại kèm phản hồi,
  tối đa `MAX_RETRY_ROUNDS` lần.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from agents import (
    chemistry_agent,
    explain_agent,
    math_agent,
    physics_agent,
    planner,
    recompute_agent,
    router,
    verify_agent,
)
from core import config, db
from memory import kho_loi_giai
from tools import arbiter
from core.schemas import (
    AgentSpan,
    Explanation,
    Plan,
    Route,
    Solution,
    SolveResult,
    Trace,
    VerifyReport,
)

_SUBJECT_AGENTS = {
    "math_agent": math_agent,
    "physics_agent": physics_agent,
    "chemistry_agent": chemistry_agent,
}

_NHAN = {
    "planner": "Planner",
    "router": "Router",
    "math_agent": "Math Agent",
    "physics_agent": "Physics Agent",
    "chemistry_agent": "Chemistry Agent",
    "verify_agent": "Verify",
    "explain_agent": "Explain",
}


def label(name: str) -> str:
    return _NHAN.get(name, name)


async def solve_stream(question: str) -> AsyncIterator[dict[str, Any]]:
    """Chạy cả luồng, phát sự kiện từng bước."""
    t_start = time.perf_counter()
    trace = Trace()
    result = SolveResult(question=question, trace=trace)

    def remaining() -> float:
        return config.SLA_SECONDS - (time.perf_counter() - t_start)

    def record(span: AgentSpan | None) -> None:
        if span is not None:
            trace.spans.append(span)

    # ---- 1. Planner --------------------------------------------------------
    yield {"type": "agent", "name": "planner", "label": label("planner"), "status": "start"}
    plan, span = await planner.run(question)
    record(span)
    result.plan = plan
    yield {
        "type": "agent",
        "name": "planner",
        "label": label("planner"),
        "status": "done",
        "ok": span.ok,
        "ms": round(span.duration_ms),
        "detail": plan.normalized_question,
    }

    # ---- 2. Router ---------------------------------------------------------
    yield {"type": "agent", "name": "router", "label": label("router"), "status": "start"}
    route, rspan = await router.run(plan)
    record(rspan)
    result.route = route
    plan.subject = route.subject
    yield {
        "type": "agent",
        "name": "router",
        "label": label("router"),
        "status": "done",
        "ok": True,
        "ms": round(rspan.duration_ms) if rspan else 0,
        "detail": f"{route.agent_name} — {route.reason_vi}",
    }

    # ---- 3. Subject Agent + 4. Verify (có vòng sửa sai) --------------------
    agent_mod = _SUBJECT_AGENTS.get(route.agent_name, math_agent)
    solution: Solution | None = None
    report: VerifyReport | None = None
    feedback: str | None = None

    # Bộ tính lại độc lập chỉ cần `plan`, không cần lời giải — nên cho chạy SONG
    # SONG với Subject Agent. Nối tiếp thì tốn thêm 5-8 giây mỗi vòng kiểm; song
    # song thì gần như miễn phí. Kết quả tính một lần rồi dùng cho mọi vòng, vì
    # đề bài không đổi giữa các vòng giải lại.
    doc_lap: recompute_agent.KetQua | None = None

    for round_i in range(config.MAX_RETRY_ROUNDS + 1):
        is_retry = round_i > 0
        yield {
            "type": "agent",
            "name": route.agent_name,
            "label": label(route.agent_name),
            "status": "start",
            "retry": is_retry,
        }
        if doc_lap is None:
            (solution, sspan), (doc_lap, rc_span) = await asyncio.gather(
                agent_mod.run(plan, feedback),
                recompute_agent.compute(plan, timeout=config.TIMEOUT_RECOMPUTE),
            )
            record(rc_span)
            # Chẩn đoán bộ tính lại. Vai này ngốn 62% tổng thời gian mà chỉ dùng
            # được ở ~16% số bài — phát ra đây để bench ghi lại và tìm ra 84% còn
            # lại hỏng ở khâu nào.
            yield {
                "type": "recompute_info",
                "co_gia_tri": doc_lap.co_gia_tri,
                "ly_do_hong": doc_lap.ly_do_hong,
                "giay": round(rc_span.duration_ms / 1000.0, 1) if rc_span else 0.0,
                "mo_ta": doc_lap.mo_ta() if doc_lap.co_gia_tri else "",
            }
        else:
            solution, sspan = await agent_mod.run(plan, feedback)
        record(sspan)

        # Trọng tài số học chạy NGAY sau Subject Agent, trước cả Verify: mọi con
        # số quy được về số thuần đều do SymPy quyết định. Vài mili giây, không
        # tốn token. Verify nhờ vậy soi lời giải đã sạch số học, chỉ còn lo lập luận.
        sua_chua = arbiter.enforce(solution)
        if sua_chua:
            yield {
                "type": "arbiter",
                "count": len(sua_chua),
                "items": [s.mo_ta() for s in sua_chua],
            }

        yield {
            "type": "agent",
            "name": route.agent_name,
            "label": label(route.agent_name),
            "status": "done",
            "ok": sspan.ok,
            "ms": round(sspan.duration_ms),
            "detail": solution.final_answer or "(chưa ra đáp số)",
            "retry": is_retry,
            "sympy_fixed": len(sua_chua),
        }

        yield {"type": "agent", "name": "verify_agent", "label": label("verify_agent"), "status": "start"}
        report, vspan = await verify_agent.run(plan, solution, doc_lap)
        record(vspan)
        yield {
            "type": "agent",
            "name": "verify_agent",
            "label": label("verify_agent"),
            "status": "done",
            "ok": report.verdict != "FAIL",
            "ms": round(vspan.duration_ms) if vspan else 0,
            "verdict": report.verdict,
            "detail": _verify_detail(report),
        }

        if report.verdict != "FAIL":
            break
        if round_i >= config.MAX_RETRY_ROUNDS:
            break
        # Còn đủ giờ mới cho giải lại. Đo thực tế: một vòng tốn ~20 giây (Subject
        # 10-15 + Verify 5-8), và Explain phía sau cần thêm ~15 giây. Ngưỡng 20
        # giây cũ quá lỏng nên có lượt chạm 94,3 giây, vượt trần 90.
        if remaining() < config.NGUONG_GIAI_LAI:
            result.warning_vi = "Hết ngân sách thời gian nên không giải lại lần nữa."
            break
        trace.retry_rounds += 1
        feedback = report.feedback()
        yield {"type": "retry", "round": trace.retry_rounds, "reason": report.suggestion_vi}

    # ---- Chốt đáp án: công cụ có tiếng nói cuối cùng ------------------------
    #
    # Hai tình huống, cùng một nguyên tắc "model quyết định LÀM GÌ, công cụ quyết
    # định RA BAO NHIÊU":
    #
    # 1. Subject Agent không ra được đáp số nào (bị cắt token, quá hạn, JSON hỏng)
    # 2. Ra đáp số nhưng KHÔNG qua được kiểm chứng, và công cụ tính ra số khác
    #
    # Cả hai đều lấy giá trị của bộ tính lại độc lập, kèm cảnh báo rõ ràng.
    #
    # Trường hợp 2 là bài học đo được trên môn Hoá: Subject Agent kiên định trả
    # 2,4 gam qua cả hai vòng, trong khi bộ tính lại ra 7,73 gam — đúng. Trước đây
    # ta giữ 2,4 chỉ vì nó đến từ agent "chính", tức vứt đi câu trả lời đúng đang
    # cầm trong tay.
    #
    # Lời giải ĐÃ qua kiểm chứng thì tuyệt đối không đụng vào.
    co_cong_cu = doc_lap is not None and doc_lap.co_gia_tri
    if solution is not None and co_cong_cu:
        assert doc_lap is not None
        khong_co_dap_so = not solution.final_answer.strip()
        lech = (
            report is not None
            and report.verdict == "FAIL"
            and (kt := recompute_agent.compare(doc_lap, solution.final_answer)) is not None
            and not kt.passed
        )

        if khong_co_dap_so or lech:
            cu = solution.final_answer.strip()
            solution.final_answer = doc_lap.mo_ta()
            solution.confidence = min(solution.confidence, 0.4 if cu else 0.35)
            result.warning_vi = (
                (
                    f"Lời giải từng bước cho {cu}, nhưng không qua được kiểm chứng. "
                    if cu
                    else "Không dựng được lời giải từng bước. "
                )
                + f"Đáp án hiển thị là {solution.final_answer}, do công cụ tính "
                + f"độc lập từ đề ({doc_lap.approach_vi}). Hãy đối chiếu kỹ."
            )
            yield {
                "type": "cuu_dap_an",
                "gia_tri": solution.final_answer,
                "cach_lam": doc_lap.approach_vi,
            }

    result.solution = solution
    result.verify = report
    if report and report.verdict == "FAIL" and not result.warning_vi:
        result.warning_vi = (
            "Lời giải chưa qua được bước kiểm chứng. Hãy đọc kỹ và tự đối chiếu lại."
        )

    # ---- Chốt đáp án cho người dùng, TRƯỚC khi giảng bài -------------------
    #
    # Đáp số đã xong hẳn ở đây: Subject giải, trọng tài sửa số, Verify kiểm, cơ chế
    # cứu đã chạy. Explain chỉ diễn đạt lại, KHÔNG được đổi đáp số.
    #
    # Trước đây frontend chỉ nhận đáp án ở sự kiện `done`, tức sau khi giảng xong —
    # ĐO ĐƯỢC: bắt người dùng chờ thêm 10,6 giây để đọc một con số đã có sẵn. Phát
    # riêng ở đây cắt đúng khoản đó khỏi thời gian chờ, không tốn gì.
    if solution is not None:
        yield {
            "type": "dap_an",
            "gia_tri": solution.final_answer,
            "latex": solution.final_answer_latex,
            "mcq": solution.mcq_choice,
            "verdict": report.verdict if report else "",
            "confidence": (report.confidence if report else solution.confidence),
            "warning": result.warning_vi,
        }

    # ---- 5. Explain (streaming) -------------------------------------------
    yield {"type": "agent", "name": "explain_agent", "label": label("explain_agent"), "status": "start"}
    t_ex = time.perf_counter()
    chunks: list[str] = []
    # Explain là bước CUỐI nên nó gánh trách nhiệm giữ trần 90 giây: chỉ được
    # tiêu đúng phần thời gian còn lại, trừ 2 giây cho việc lưu và đóng luồng.
    # Chữ đang chảy mà hết giờ thì cắt — người dùng đã đọc được phần đầu, còn
    # hơn là vượt trần.
    han_explain = max(5.0, remaining() - 2.0)
    # Có đáp án là trình bày, kể cả khi không dựng được các bước — người dùng cần
    # câu trả lời, không cần biết tầng nào bên trong đã hỏng.
    if solution and (solution.steps or solution.final_answer.strip()):
        # `asyncio.timeout` chặn CỨNG. Kiểm hạn giữa các chunk là chưa đủ: nếu
        # model chậm ra token đầu tiên thì vòng lặp nằm chờ và trôi qua mốc —
        # đo được 3/9 lượt vượt 90 giây vì đúng chỗ này.
        try:
            async with asyncio.timeout(han_explain):
                async for piece in explain_agent.stream(plan, solution, report):
                    chunks.append(piece)
                    yield {"type": "token", "text": piece}
        except TimeoutError:
            het = (
                "\n\n_(Hết ngân sách thời gian, phần giảng bị cắt. "
                "Đáp án ở trên vẫn giữ nguyên.)_"
            )
            chunks.append(het)
            yield {"type": "token", "text": het}
    else:
        msg = "Hệ thống chưa giải được bài này. Hãy thử diễn đạt lại đề rõ hơn."
        chunks.append(msg)
        yield {"type": "token", "text": msg}

    ex_ms = (time.perf_counter() - t_ex) * 1000.0
    trace.spans.append(AgentSpan(agent="explain_agent", model=config.MODEL_LIGHT, duration_ms=ex_ms))
    markdown = "".join(chunks)
    result.explanation = Explanation(
        steps_markdown=markdown,
        final_answer_vi=solution.final_answer if solution else "",
    )
    yield {
        "type": "agent",
        "name": "explain_agent",
        "label": label("explain_agent"),
        "status": "done",
        "ok": True,
        "ms": round(ex_ms),
    }

    # ---- Kết thúc ----------------------------------------------------------
    total_ms = (time.perf_counter() - t_start) * 1000.0
    try:
        db.save(
            question=question,
            answer=(solution.final_answer if solution else ""),
            subject=plan.subject,
            verdict=(report.verdict if report else ""),
            duration_ms=total_ms,
        )
    except Exception:  # noqa: BLE001 — lưu lịch sử hỏng không được làm hỏng câu trả lời
        pass

    # Cất lời giải vào memory pool — CHỈ khi đã qua kiểm chứng. Lưu lời giải sai là
    # tự đầu độc: lần sau nó được lấy ra làm ví dụ mẫu và nhân bản cái sai.
    if (
        config.LUU_LOI_GIAI_MAU
        and report is not None
        and report.verdict == "PASS"
        and solution is not None
        and not result.warning_vi          # có cảnh báo nghĩa là đáp án chưa chắc
    ):
        kho_loi_giai.luu(
            question=question,
            subject=plan.subject,
            topic=plan.topic,
            steps=[s.model_dump(mode="json") for s in solution.steps],
            final_answer=solution.final_answer,
        )

    yield {
        "type": "done",
        "total_ms": round(total_ms),
        "within_sla": total_ms <= config.SLA_SECONDS * 1000.0,
        "warning": result.warning_vi,
        "result": result.model_dump(mode="json"),
    }


def _verify_detail(report: VerifyReport) -> str:
    bad = [c for c in report.checks if not c.passed]
    if not bad:
        return "Mọi phép kiểm đều đạt."
    return bad[0].detail_vi or "Phát hiện lỗi."


async def solve(question: str) -> SolveResult:
    """Bản không streaming — dùng cho kiểm thử và đo hiệu năng."""
    final: dict[str, Any] | None = None
    async for ev in solve_stream(question):
        if ev.get("type") == "done":
            final = ev
    if final is None:
        return SolveResult(question=question, error="khong co ket qua")
    return SolveResult.model_validate(final["result"])
