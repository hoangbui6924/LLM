"""Tác tử KIỂM TRA — trái tim của đề tài.

Bốn tầng, xếp theo giá tăng dần. Tầng rẻ chạy trước và có quyền kết luận sớm:

  T0  ViSTEM-PRM   — model đã huấn luyện, ~30ms, không tốn token
  T1  Tất định     — SymPy/Pint/bảo toàn nguyên tố, ~5ms, KHÔNG BAO GIỜ SAI
  T2  Giải lại     — model KHÁC HỌ giải độc lập, không nhìn lời giải cũ
  T3  Soát bước    — model KHÁC HỌ tìm bước sai đầu tiên

Ràng buộc thiết kế quan trọng nhất: **model của Verifier phải khác họ với Solver.**
Nếu dùng cùng model, ta chỉ đang đo mức độ một model đồng ý với chính nó — thiên
lệch xác nhận, không phải kiểm chứng. Đây chính là ablation A3 của báo cáo.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..core.llm import LLMClient
from ..core.prompts import (
    VERIFIER_INDEPENDENT_SYSTEM,
    VERIFIER_INDEPENDENT_USER,
    VERIFIER_STEPWISE_SYSTEM,
    VERIFIER_STEPWISE_USER,
)
from ..core.schemas import (
    AgentSpan,
    ProblemSpec,
    Solution,
    Verdict,
    VerdictItem,
    VerificationReport,
)
from ..core.answer_match import answers_match
from ..core.config import get_settings
from ..tools import recompute, sympy_tool, units_tool
from .solver import format_tool_evidence
from pydantic import BaseModel


class _IndependentOut(BaseModel):
    reasoning_brief_vi: str = ""
    final_answer: str = ""
    mcq_choice: str | None = None
    confidence: float = 0.5


class _StepwiseOut(BaseModel):
    verdict: str = "UNCERTAIN"
    first_error_step: int | None = None
    error_type: str = "none"
    detail_vi: str = ""
    suggested_fix_vi: str = ""
    confidence: float = 0.5


# ---------------------------------------------------------------------------
# T1 — kiểm chứng tất định (không LLM)
# ---------------------------------------------------------------------------


def verify_t1(spec: ProblemSpec, sol: Solution) -> list[VerdictItem]:
    """Đọc cờ kiểm chứng từ các lượt gọi công cụ + tự chạy thêm vài kiểm tra.

    Không tốn token nào. Mỗi lỗi bắt được ở đây là 2 lượt gọi LLM tiết kiệm được.
    """
    items: list[VerdictItem] = []

    # (a) Cờ từ công cụ mà Solver đã tự gọi
    for step in sol.steps:
        for tc in step.tool_calls:
            if not tc.ok:
                # Tool lỗi nghĩa là LLM gọi sai THAM SỐ, KHÔNG phải lời giải sai.
                # Ghi lại để phân tích nhưng không tính là bằng chứng bác bỏ —
                # nhầm hai thứ này sẽ huỷ oan hàng loạt lời giải đúng.
                items.append(
                    VerdictItem(
                        step_id=step.id, check_type="symbolic", passed=True,
                        detail_vi=f"(bỏ qua) công cụ '{tc.tool}' không chạy được: {tc.error}",
                    )
                )
                continue
            for flag, ctype, msg in (
                ("satisfied", "substitution", "Thế nghiệm vào phương trình KHÔNG thoả"),
                ("conserved", "conservation", "VI PHẠM bảo toàn nguyên tố"),
                ("compatible", "dimensional", "SAI THỨ NGUYÊN"),
                ("balanced", "conservation", "Không cân bằng được phương trình"),
                ("equivalent", "symbolic", "Hai biểu thức KHÔNG tương đương"),
            ):
                if flag in tc.flags:
                    ok = bool(tc.flags[flag])
                    items.append(
                        VerdictItem(
                            step_id=step.id, check_type=ctype, passed=ok,  # type: ignore[arg-type]
                            detail_vi=(tc.result if ok else f"{msg}: {tc.result}"),
                        )
                    )

    # (b) Vật lý: đáp số có đúng thứ nguyên của đại lượng cần tìm không?
    #     Verifier TỰ chạy, không tin Solver đã tự kiểm.
    if spec.domain == "physics" and sol.unit and units_tool.available():
        expected = None
        for u in spec.unknowns:
            expected = u.unit or units_tool.expected_unit_for(u.description_vi)
            if expected:
                break
        if expected:
            r = units_tool.check_dimension(f"1 {sol.unit}", expected)
            if r.get("ok"):
                items.append(
                    VerdictItem(
                        check_type="dimensional", passed=bool(r["compatible"]),
                        detail_vi=(
                            f"Đơn vị đáp số '{sol.unit}' khớp đại lượng cần tìm ({expected})."
                            if r["compatible"]
                            else f"Đáp số có đơn vị '{sol.unit}' nhưng đề hỏi đại lượng "
                                 f"đơn vị '{expected}' — SAI THỨ NGUYÊN."
                        ),
                    )
                )

    # (c) Trắc nghiệm: đáp án chọn có nằm trong 4 phương án không
    if spec.question_type == "mcq" and spec.choices:
        ok = bool(sol.mcq_choice and sol.mcq_choice.upper() in spec.choices)
        items.append(
            VerdictItem(
                check_type="symbolic", passed=ok,
                detail_vi=(
                    f"Đã chọn phương án {sol.mcq_choice}."
                    if ok
                    else f"Không chọn được phương án hợp lệ (nhận '{sol.mcq_choice}')."
                ),
            )
        )

    # (b2) SymPy tính lại mọi bước quy được về số. Đây là tầng bắt lỗi `arithmetic` —
    # loại lỗi mà PRM đo được recall chỉ 77,4 % vì phát hiện nó đòi hỏi thực sự tính
    # lại, thứ một bộ phân loại văn bản không làm được. Hai tầng bù nhau, không chồng.
    # Cũng bắt luôn "lời giải tự mâu thuẫn": các bước dẫn tới một số, đáp số là số khác.
    items.extend(i for i in recompute.check_solution(sol) if not i.passed)

    # (d) Toán: nếu đề là phương trình và đáp số là số -> thế ngược vào đề
    if spec.domain == "math" and spec.normalized_latex and "=" in spec.normalized_latex:
        target = sol.final_answer_latex or sol.final_answer
        if target:
            symbol = spec.unknowns[0].symbol if spec.unknowns else "x"
            r = sympy_tool.check_substitution(spec.normalized_latex, {symbol: target})
            if r.get("ok"):
                items.append(
                    VerdictItem(
                        check_type="substitution", passed=bool(r["satisfied"]),
                        detail_vi=(
                            f"Thế {symbol}={target} vào đề: thoả mãn."
                            if r["satisfied"]
                            else f"Thế {symbol}={target} vào phương trình gốc KHÔNG thoả "
                                 f"(sai số {r.get('residual')})."
                        ),
                    )
                )
    return items


# ---------------------------------------------------------------------------
# T0 — ViSTEM-PRM (nạp lười, thiếu checkpoint thì bỏ qua)
# ---------------------------------------------------------------------------


def verify_t0(spec: ProblemSpec, sol: Solution) -> list[VerdictItem]:
    """Tầng PRM. Hai chế độ, đặt trong configs/app.yaml -> prm.mode:

      blocking  — PRM bác bỏ thì lời giải bị coi là FAIL
      advisory  — PRM vẫn chấm và vẫn hiện trên timeline, NHƯNG không tự bác bỏ

    Vì sao mặc định là `advisory`: PRM hiện được huấn luyện HOÀN TOÀN trên lời giải
    sinh từ template. Trên lời giải thật của Solver (diễn đạt khác, có LaTeX) nó lệch
    phân phối và cho P(đúng) ≈ 0 với cả lời giải đúng. Đo được: 91,3 % recall trong
    phân phối, nhưng báo oan lời giải thật đầu tiên đem ra thử.

    Chỉ chuyển sang `blocking` sau khi huấn luyện lại có trộn lời giải thật từ
    memory pool và đo lại trên tập giữ kín.
    """
    try:
        from ..models.prm.infer import get_prm  # noqa: PLC0415

        prm = get_prm()
        if prm is None:
            return []
        items = prm.score_solution(spec.raw_text, sol)
        mode = str(get_settings().prm.get("mode", "advisory")).lower()
        if mode != "blocking":
            # Đổi luôn check_type, không chỉ ép passed=True. Trước đây timeline hiện
            # "✓ prm" cho MỌI lời giải kể cả khi PRM chấm trượt — người dùng đọc thành
            # "đã có một tầng kiểm chứng đạt", trong khi tầng đó đang bị tước quyền
            # bác bỏ. Một tầng không được phép nói "không" thì dấu tick của nó vô nghĩa.
            for it in items:
                it.check_type = "prm_advisory"
                if not it.passed:
                    it.passed = True
                    it.detail_vi = "(tham khảo, chưa dùng để bác bỏ) " + it.detail_vi
        return items
    except Exception:  # noqa: BLE001
        # Chưa huấn luyện PRM là chuyện bình thường ở giai đoạn đầu — bỏ qua êm.
        return []


# ---------------------------------------------------------------------------
# T2 / T3 — kiểm bằng LLM khác họ
# ---------------------------------------------------------------------------


async def verify_t2(
    client: LLMClient, spec: ProblemSpec, sol: Solution, profile: str | None = None
) -> tuple[VerdictItem, str | None, list[AgentSpan]]:
    messages = [
        {"role": "system", "content": VERIFIER_INDEPENDENT_SYSTEM},
        {"role": "user", "content": VERIFIER_INDEPENDENT_USER.format(problem=spec.raw_text)},
    ]
    try:
        out, spans = await client.chat_json("verifier", messages, _IndependentOut, profile=profile)
    except Exception as e:  # noqa: BLE001
        return (
            VerdictItem(check_type="independent", passed=True,
                        detail_vi=f"Không chạy được kiểm tra độc lập ({e}); bỏ qua."),
            None, [],
        )

    # Trắc nghiệm thì so nhãn; còn lại so bằng bộ so khớp dùng chung với bộ eval.
    # KHÔNG được tự viết logic so sánh ở đây: một cài đặt riêng sẽ lệch khỏi bộ chấm,
    # và mọi bất đồng giả đều biến thành một vòng repair thừa.
    if sol.mcq_choice and out.mcq_choice:
        agree = sol.mcq_choice.strip().upper() == out.mcq_choice.strip().upper()
    else:
        agree = answers_match(sol.final_answer, out.final_answer)

    return (
        VerdictItem(
            check_type="independent", passed=agree,
            detail_vi=(
                f"Lời giải độc lập cho cùng đáp án ({out.final_answer})."
                if agree
                else f"BẤT ĐỒNG: lời giải độc lập cho '{out.final_answer}', "
                     f"lời giải đang xét cho '{sol.final_answer}'. {out.reasoning_brief_vi}"
            ),
            score=out.confidence,
        ),
        out.final_answer,
        spans,
    )


async def verify_t3(
    client: LLMClient, spec: ProblemSpec, sol: Solution, profile: str | None = None
) -> tuple[VerdictItem, _StepwiseOut | None, list[AgentSpan]]:
    messages = [
        {"role": "system", "content": VERIFIER_STEPWISE_SYSTEM},
        {
            "role": "user",
            "content": VERIFIER_STEPWISE_USER.format(
                problem=spec.raw_text,
                solution=sol.as_plain_text(),
                tool_evidence=format_tool_evidence(sol),
            ),
        },
    ]
    try:
        out, spans = await client.chat_json("verifier", messages, _StepwiseOut, profile=profile)
    except Exception as e:  # noqa: BLE001
        return (
            VerdictItem(check_type="stepwise", passed=True,
                        detail_vi=f"Không chạy được soát bước ({e}); bỏ qua."),
            None, [],
        )
    passed = out.verdict.upper() == "PASS"
    return (
        VerdictItem(
            step_id=out.first_error_step, check_type="stepwise", passed=passed,
            detail_vi=out.detail_vi or ("Soát từng bước: không thấy lỗi." if passed else "Có lỗi."),
            score=out.confidence,
        ),
        out, spans,
    )


# ---------------------------------------------------------------------------
# Hợp nhất
# ---------------------------------------------------------------------------


async def verify(
    client: LLMClient,
    spec: ProblemSpec,
    sol: Solution,
    tiers: list[str],
    profile: str | None = None,
) -> tuple[VerificationReport, list[AgentSpan]]:
    report = VerificationReport()
    spans: list[AgentSpan] = []

    if "T0" in tiers:
        report.items.extend(verify_t0(spec, sol))
    if "T1" in tiers:
        report.items.extend(verify_t1(spec, sol))

    # T1 bác bỏ thì DỪNG NGAY. Kiểm chứng tất định không thể sai, nên gọi thêm LLM
    # chỉ tốn tiền và thời gian để nghe lại điều đã biết chắc.
    hard_fail = [
        i for i in report.items
        if not i.passed and i.check_type in {"substitution", "conservation", "dimensional"}
    ]
    if hard_fail:
        report.verdict = Verdict.FAIL
        report.first_error_step = next((i.step_id for i in hard_fail if i.step_id), None)
        report.suggested_fix_vi = hard_fail[0].detail_vi
        report.confidence = 0.95
        return report, spans

    tasks = []
    if "T2" in tiers:
        tasks.append(verify_t2(client, spec, sol, profile))
    if "T3" in tiers:
        tasks.append(verify_t3(client, spec, sol, profile))

    stepwise: _StepwiseOut | None = None
    if tasks:
        # T2 và T3 độc lập nhau -> chạy song song, tiết kiệm ~3 giây mỗi bài.
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                continue
            item = r[0]
            report.items.append(item)
            spans.extend(r[2])
            if item.check_type == "independent":
                report.independent_answer = r[1]
                report.agreement = item.passed
            elif item.check_type == "stepwise":
                stepwise = r[1]
                if stepwise and stepwise.first_error_step is not None:
                    report.first_error_step = stepwise.first_error_step
                if stepwise and stepwise.suggested_fix_vi:
                    report.suggested_fix_vi = stepwise.suggested_fix_vi

    failed = [i for i in report.items if not i.passed]
    if not failed:
        report.verdict = Verdict.PASS
        report.confidence = 0.9 if report.agreement else 0.75
    elif len(failed) == 1 and failed[0].check_type == "independent":
        # Chỉ bất đồng đáp số, soát bước không tìm ra lỗi cụ thể -> chưa đủ cơ sở
        # để bác bỏ. UNCERTAIN là kết luận trung thực hơn FAIL ở đây.
        report.verdict = Verdict.UNCERTAIN
        report.confidence = 0.45
    elif len(failed) == 1 and failed[0].check_type == "stepwise" and report.agreement:
        # Trường hợp đối xứng: chỉ T3 kêu, trong khi T2 KHÁC HỌ đã giải độc lập và ra
        # cùng đáp số, và mọi kiểm tra tất định đều đạt. Một mình T3 không đủ để bác bỏ.
        #
        # Đã quan sát trực tiếp: bài Fe + HCl có prm ✓ symbolic ✓ independent ✓
        # stepwise ✗ -> ba thắng một vẫn ra FAIL, độ tin cậy 32%, và người dùng nhận
        # một cảnh báo đỏ cho lời giải có đáp số đúng. Lý do T3 đưa ra khi đó còn là
        # bịa ("số mol phải là một số nguyên").
        #
        # UNCERTAIN giữ được điều đáng giữ: vẫn báo cho người dùng là có vấn đề ở
        # phần lập luận, nhưng không tuyên bố sai một đáp số đã được xác nhận độc lập.
        report.verdict = Verdict.UNCERTAIN
        report.confidence = 0.6
        report.suggested_fix_vi = (
            "Đáp số được một model khác họ xác nhận độc lập, nhưng phần lập luận có "
            f"điểm đáng ngờ: {failed[0].detail_vi}"
        )
    else:
        report.verdict = Verdict.FAIL
        report.confidence = 0.8

    return report, spans
