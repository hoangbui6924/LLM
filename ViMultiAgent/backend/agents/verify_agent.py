"""Verify Agent — mục 3.4.

Đây là agent quyết định độ tin cậy của cả hệ thống, và nó **không tin LLM**.

Thứ tự kiểm tra có chủ đích: chạy các phép kiểm TẤT ĐỊNH trước (tính lại bằng
SymPy, soát thứ nguyên, soát bảo toàn nguyên tố), rồi mới đưa kết quả đó cho LLM
đọc. Làm ngược lại thì LLM sẽ "đồng ý" với lời giải sai — mô hình 8B rất dễ bị
cuốn theo lập luận trôi chảy.

Một phép kiểm tất định thất bại là FAIL, bất kể LLM nói gì.
"""

from __future__ import annotations

import re

from agents import recompute_agent
from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Check, Plan, Solution, VerifyReport
from tools import chem_tool, sympy_tool, units_tool

SYSTEM = """Bạn là Verify Agent. Bạn KHÔNG giải lại bài, chỉ soi lỗi.

Bạn nhận đề bài, lời giải từng bước, và kết quả của các phép kiểm tự động đã chạy.

Trả JSON:
- verdict: "PASS" nếu lời giải đúng | "FAIL" nếu có lỗi thực sự | "UNCERTAIN" nếu không đủ căn cứ
- checks: danh sách kiểm tra bạn đã thực hiện, mỗi mục gồm kind ("llm_review"),
  passed (true/false), step_id (số bước có lỗi, không có thì null), detail_vi
- first_error_step: id bước SAI ĐẦU TIÊN, không có lỗi thì null
- suggestion_vi: chỉ dẫn NGẮN để sửa đúng chỗ đó
- confidence: 0..1

Cách soi:
- Kiểm tra logic từng bước có suy ra được từ bước trước không.
- Kiểm tra đáp số có trả lời đúng câu hỏi của đề không (hỏi vận tốc mà đáp ra quãng đường là FAIL).
- Kiểm tra đơn vị và điều kiện xác định.
- Nếu các phép kiểm tự động đã báo sai, bạn PHẢI kết luận FAIL.

KHI NÀO KHÔNG ĐƯỢC BÁO FAIL — đọc kỹ, đây là lỗi hay mắc nhất:
- Hai con số BẰNG NHAU nhưng viết khác cách: 2 và 2,000 và 2.0 là MỘT. PASS.
- Làm tròn hợp lệ: 0,6283 viết thành 0,63 là ĐÚNG. 7,7333 thành 7,73 là ĐÚNG.
- Dùng dấu phẩy hay dấu chấm thập phân đều được.
- Thiếu đơn vị ở bước trung gian, miễn đáp số cuối có đơn vị đúng.
- Trình bày vắn tắt, gộp bước, thứ tự khác cách bạn quen.
Chỉ FAIL khi KẾT QUẢ SAI VỀ GIÁ TRỊ hoặc lập luận dẫn tới kết quả sai.
Nếu bạn định viết "sai số 0" hay "lệch 0%" thì đó chính là PASS, không phải FAIL.
"""

# Bắt phương trình phản ứng dạng "Fe + O2 -> Fe3O4" trong lời giải Hoá.
_REACTION = re.compile(r"([A-Za-z0-9()\s\+\.]+?)\s*(?:->|→|=>|\\rightarrow)\s*([A-Za-z0-9()\s\+\.]+)")


# ---------------------------------------------------------------------------
# Các phép kiểm tất định — không tốn token nào
# ---------------------------------------------------------------------------


def _check_arithmetic(sol: Solution) -> list[Check]:
    """SymPy tính lại từng bước. Chỉ kết luận sai khi CẢ HAI vế đọc ra được số.

    Ngưỡng 1% là cố ý: model làm tròn 0,39738 -> 0,397 là hợp lệ, không phải lỗi.
    Báo oan một bước đúng thì tai hại hơn bỏ sót, vì nó kích hoạt vòng giải lại.
    """
    out: list[Check] = []
    for st in sol.steps:
        expr, res = (st.expression or "").strip(), (st.result or "").strip()
        if not expr or not res:
            continue
        rhs = expr.split("=")[-1] if "=" in expr else expr
        a = sympy_tool.evaluate(rhs)
        b = sympy_tool.evaluate(res)
        if not (a.get("ok") and b.get("ok")):
            continue
        va, vb = a.get("numeric"), b.get("numeric")
        if va is None or vb is None:
            continue
        scale = max(1e-9, abs(va))
        if abs(va - vb) / scale > 0.01:
            out.append(
                Check(
                    kind="sympy",
                    passed=False,
                    step_id=st.id,
                    detail_vi=(
                        f"Tính lại vế phải được {va:.6g} nhưng bước ghi {vb:.6g}."
                    ),
                )
            )
    if not out:
        out.append(Check(kind="sympy", passed=True, detail_vi="Số học các bước khớp."))
    return out


def _check_units(plan: Plan, sol: Solution) -> list[Check]:
    """Soát thứ nguyên đáp số — chỉ áp cho Vật lý, nơi sai đơn vị là sai thật."""
    if plan.subject != "physics" or not units_tool.available():
        return []
    want = None
    for u in plan.unknowns:
        want = u.unit or units_tool.expected_unit_for(u.description_vi or u.symbol)
        if want:
            break
    if not want or not sol.final_answer:
        return []
    r = units_tool.check_dimension(sol.final_answer, want)
    if not r.get("ok"):
        return []
    return [
        Check(
            kind="unit",
            passed=bool(r.get("compatible", True)),
            detail_vi=r.get("detail", f"Đáp số cần có đơn vị quy về {want}."),
        )
    ]


# Tách hệ số khỏi công thức: "3Fe" -> ("Fe", 3), "Fe" -> ("Fe", 1), "2H2O" -> ("H2O", 2).
# Chỉ số ĐẦU chuỗi mới là hệ số; số nằm trong công thức là chỉ số nguyên tử.
_HE_SO = re.compile(r"^\s*(\d+)?\s*([A-Za-z][A-Za-z0-9()]*)\s*$")


def _tach_he_so(ve: str) -> list[tuple[str, int]] | None:
    ra: list[tuple[str, int]] = []
    for hang in ve.split("+"):
        m = _HE_SO.match(hang)
        if not m:
            return None
        ra.append((m.group(2), int(m.group(1) or 1)))
    return ra or None


def _check_chemistry(sol: Solution) -> list[Check]:
    """Soát bảo toàn nguyên tố trên phương trình phản ứng tìm được trong lời giải."""
    for st in sol.steps:
        m = _REACTION.search(st.expression or "")
        if not m:
            continue
        trai = _tach_he_so(m.group(1))
        phai = _tach_he_so(m.group(2))
        if not trai or not phai:
            continue
        r = chem_tool.check_conservation(trai, phai)
        if not r.get("ok"):
            continue

        dat = bool(r.get("conserved", True))
        chi_tiet = r.get("detail", "Đã soát bảo toàn nguyên tố.")

        # Sai hệ số thì không chỉ báo sai — đưa luôn phương trình ĐÚNG vào phản
        # hồi. `balance_equation` giải bằng không gian null của ma trận nguyên tố,
        # tất định, không đoán. Model đang sai tỉ lệ hợp thức sẽ nhận được hệ số
        # đúng ở vòng giải lại thay vì đoán lần nữa.
        if not dat:
            can_bang = chem_tool.balance_equation(
                [f for f, _ in trai], [f for f, _ in phai]
            )
            if can_bang.get("ok") and can_bang.get("balanced"):
                chi_tiet += (
                    f" Phương trình đúng phải là: {can_bang['equation']}."
                    " Hãy lấy tỉ lệ mol theo đúng các hệ số này."
                )

        return [Check(kind="conservation", passed=dat, step_id=st.id, detail_vi=chi_tiet)]
    return []


def _check_answer_present(sol: Solution) -> list[Check]:
    if not sol.steps:
        return [Check(kind="consistency", passed=False, detail_vi="Lời giải không có bước nào.")]
    if not sol.final_answer.strip():
        return [Check(kind="consistency", passed=False, detail_vi="Không có đáp số cuối.")]
    return []


def deterministic_checks(plan: Plan, sol: Solution) -> list[Check]:
    checks: list[Check] = []
    checks += _check_answer_present(sol)
    checks += _check_arithmetic(sol)
    checks += _check_units(plan, sol)
    if plan.subject == "chemistry":
        checks += _check_chemistry(sol)
    return checks


# ---------------------------------------------------------------------------


async def run(
    plan: Plan,
    sol: Solution,
    doc_lap: recompute_agent.KetQua | None = None,
) -> tuple[VerifyReport, AgentSpan | None]:
    checks = deterministic_checks(plan, sol)

    # Mắt thứ hai: giá trị do SymPy tính từ ĐỀ GỐC, độc lập với lời giải. Đây là
    # phép kiểm duy nhất bắt được lỗi chọn sai công thức ngay từ bước đầu — các
    # phép kiểm ở trên chỉ soát tính nhất quán nội bộ của lời giải.
    # Manager đã tính sẵn song song với Subject Agent nên ở đây không tốn thêm giây nào.
    goi_y_dap_an = ""
    if doc_lap is not None:
        check_rc = recompute_agent.compare(doc_lap, sol.final_answer)
        if check_rc is not None:
            checks.append(check_rc)
        goi_y_dap_an = doc_lap.mo_ta()

    failed = [c for c in checks if not c.passed]

    # Lời giải rỗng thì không cần tiêu token để biết là hỏng.
    if not sol.steps or not sol.final_answer.strip():
        return (
            VerifyReport(
                verdict="FAIL",
                checks=checks,
                first_error_step=None,
                suggestion_vi="Hãy giải lại từ đầu, trình bày đủ các bước và ghi rõ đáp số.",
                confidence=0.9,
            ),
            None,
        )

    auto = "\n".join(
        f"- [{c.kind}] {'ĐẠT' if c.passed else 'KHÔNG ĐẠT'}"
        + (f" (bước {c.step_id})" if c.step_id else "")
        + f": {c.detail_vi}"
        for c in checks
    ) or "- (không có phép kiểm tự động nào chạy được)"

    task = (
        f"Đề bài:\n{plan.normalized_question}\n\n"
        f"Lời giải cần soi:\n{sol.as_text()}\n\n"
        f"Kết quả các phép kiểm tự động:\n{auto}"
    )

    report, span = await run_structured(
        name="verify_agent",
        system=SYSTEM,
        task=task,
        out_type=VerifyReport,
        model=config.MODEL_HEAVY,
        max_tokens=config.MAX_TOKENS_VERIFY,
    )
    if report is None:
        report = VerifyReport(
            verdict="FAIL" if failed else "UNCERTAIN",
            suggestion_vi="Verify Agent không phản hồi được.",
            confidence=0.2,
        )

    # Gộp phép kiểm tất định vào báo cáo, và để chúng có quyền phủ quyết.
    report.checks = checks + [c for c in report.checks if c.kind == "llm_review"]
    if failed:
        report.verdict = "FAIL"
        if report.first_error_step is None:
            report.first_error_step = next((c.step_id for c in failed if c.step_id), None)
        if not report.suggestion_vi:
            report.suggestion_vi = failed[0].detail_vi
        if goi_y_dap_an:
            report.suggestion_vi += f" Giá trị công cụ tính được: {goi_y_dap_an}."
        report.confidence = max(report.confidence, 0.8)
    return report, span
