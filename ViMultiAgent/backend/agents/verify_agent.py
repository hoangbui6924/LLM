"""Verify Agent — mục 3.4.

Đây là agent quyết định độ tin cậy của cả hệ thống, và nó **không tin LLM**.

Thứ tự kiểm tra có chủ đích: chạy các phép kiểm TẤT ĐỊNH trước (SymPy tính lại
từng bước, SymPy tự giải lại bài từ đề gốc), rồi mới đưa kết quả đó cho LLM đọc.
Làm ngược lại thì LLM sẽ "đồng ý" với lời giải sai — mô hình nhỏ rất dễ bị cuốn
theo lập luận trôi chảy.

Một phép kiểm tất định thất bại là FAIL, bất kể LLM nói gì.
"""

from __future__ import annotations

import math
import re

import sympy as sp

from agents import recompute_agent
from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Check, Plan, Solution, VerifyReport
from tools import sympy_tool

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
- Kiểm tra đáp số có trả lời đúng câu hỏi của đề không (hỏi giá trị nhỏ nhất mà
  đáp ra giá trị lớn nhất là FAIL; hỏi thể tích mà đáp ra diện tích đáy là FAIL).
- Kiểm tra điều kiện xác định và việc loại nghiệm ngoại lai.
- Với bài hình học, kiểm đáp số có hợp lệ không: độ dài, diện tích, thể tích và
  khoảng cách phải KHÔNG ÂM.
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

# Đuôi đơn vị dính sau con số ở trường `result`. Phải bóc trước khi đọc số, nếu
# không SymPy coi "cm" là ký hiệu tự do và cả phép kiểm bị bỏ qua im lặng.
#
# Đề Toán THPT dùng ít đơn vị hơn hẳn đề Lý - Hoá: chỉ còn đơn vị độ dài, diện
# tích, thể tích và số đo góc.
_DUOI_DON_VI = re.compile(
    r"\s*(cm\^?3|cm\^?2|m\^?3|m\^?2|dm\^?3|dm|cm|mm|km|m"
    r"|đơn vị thể tích|đơn vị diện tích|đơn vị|rad|độ|%)\s*$",
    re.IGNORECASE,
)

# Tên ký hiệu hợp lệ để đưa vào bảng tra.
_TEN_KY_HIEU = re.compile(r"[A-Za-z][A-Za-z0-9]*")

# Token chữ trong biểu thức. Tên hàm/hằng của SymPy thì để nguyên, không thế.
_TOKEN_CHU = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_DE_NGUYEN = frozenset(
    {"sqrt", "log", "ln", "exp", "abs", "pi", "e", "sin", "cos", "tan", "cot", "oo"}
)


def _chuan_hoa_ky_hieu(s: str) -> str:
    """Đưa mọi cách viết chỉ số dưới về một dạng: m_{Na_2O}, M(Na2O) -> mNa2O."""
    s = s.strip().replace("\\", "")
    s = re.sub(r"[_{}()\[\]\s]", "", s)
    return s


def _so_hoc_thuan(bieu_thuc: str) -> float | None:
    """Parse rồi đòi ra một con số. Còn ký hiệu tự do, hay ra tuple, thì trả None.

    Phải chặn tuple: SymPy đọc "0,2" kiểu Việt Nam thành cặp `(0, 2)` chứ không
    báo lỗi, và tuple không có `free_symbols` nên bản đầu ném AttributeError.
    """
    try:
        v = sympy_tool.parse(bieu_thuc)
    except Exception:
        return None
    if not isinstance(v, sp.Expr) or v.free_symbols:
        return None
    try:
        return float(v.evalf())
    except (TypeError, ValueError):
        return None


def _doc_so_ket_qua(s: str) -> float | None:
    """Đọc số từ trường `result`, thử cả bản còn đuôi đơn vị lẫn bản đã bóc."""
    s = _dau_phay_thap_phan((s or "").strip())
    if not s:
        return None
    for ung_vien in (s, _DUOI_DON_VI.sub("", s)):
        if not ung_vien.strip():
            continue
        gt = _so_hoc_thuan(ung_vien)
        if gt is not None:
            return gt
    return None


def _tra_ky_hieu(ten: str, bang: dict[str, float]) -> float | None:
    return bang.get(ten)


def _tinh_sau_khi_the(bieu_thuc: str, bang: dict[str, float]) -> float | None:
    """Thế giá trị vào mọi ký hiệu rồi tính. Thiếu một ký hiệu là trả None."""
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", bieu_thuc)
    s = _chuan_hoa_dau_nhan(_dau_phay_thap_phan(s))
    if not s.strip():
        return None

    def _the(khop: re.Match[str]) -> str:
        ten = khop.group(0)
        if ten in _DE_NGUYEN:
            return ten
        gt = _tra_ky_hieu(ten, bang)
        if gt is None:
            raise _ThieuKyHieu(ten)
        return f"({gt!r})"

    try:
        s = _TOKEN_CHU.sub(_the, s)
    except _ThieuKyHieu:
        return None
    return _so_hoc_thuan(s)


def _lech_do_doi_don_vi(va: float, vb: float) -> bool:
    """Lệch đúng một luỹ thừa của 10 thì coi là đổi đơn vị, KHÔNG phải sai số học.

    Ca thật phải chặn: bước 1 ghi `A = 6 cm`, bước 3 dùng `v = A*omega` với A tính
    bằng mét. Thế thẳng 6 vào được 120 trong khi bước ghi 1,2 — lời giải hoàn toàn
    đúng, chỉ là ký hiệu đổi đơn vị giữa chừng mà bảng tra không biết.

    Cái giá phải trả: bỏ sót lỗi lệch đúng 10 lần (6,2 viết nhầm thành 0,62). Chấp
    nhận được, vì nguyên tắc của tầng kiểm chứng này là báo oan tai hại hơn bỏ sót
    — báo oan làm hỏng cả lời giải đúng, còn bỏ sót chỉ là không cải thiện.
    """
    if va == 0 or vb == 0:
        return False
    ty_le = abs(va / vb)
    if ty_le < 1:
        ty_le = 1 / ty_le
    mu = round(math.log10(ty_le))
    return mu >= 1 and abs(ty_le - 10.0**mu) / 10.0**mu < 0.01


def _dau_phay_thap_phan(s: str) -> str:
    """0,2 -> 0.2, nhưng KHÔNG đụng dấu phẩy ngăn tham số hàm.

    Dùng chung bộ đổi có trạng thái với trọng tài số học — bản cũ ở đây cũng là
    `(?<=\\d),(?=\\d)` nên mắc đúng lỗi biến `C(5,2)` thành `C(5.2)`.
    Xem `sympy_tool.dau_phay_thap_phan`.
    """
    return sympy_tool.dau_phay_thap_phan(s)


def _chuan_hoa_dau_nhan(s: str) -> str:
    """Bỏ vỏ LaTeX, gộp chỉ số dưới vào tên ký hiệu, giữ nguyên cấu trúc phép toán.

    Chỉ gộp ngoặc nhọn ĐI SAU dấu gạch dưới. Ngoặc nhọn khác phải để nguyên cho
    SymPy đọc — xoá bừa thì `sqrt{2}` thành `sqrt2`, một ký hiệu vô nghĩa.
    """
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("×", "*")
    s = s.replace("\\left", "").replace("\\right", "").replace("\\", "")
    for _ in range(3):  # chỉ số dưới lồng nhau: n_{Na_2O} -> nNa2O
        moi = re.sub(r"_\{([A-Za-z0-9_]*)\}", lambda m: m.group(1).replace("_", ""), s)
        if moi == s:
            break
        s = moi
    return re.sub(r"_([A-Za-z0-9]+)", r"\1", s)


class _ThieuKyHieu(Exception):
    """Gặp ký hiệu không tra được giá trị — dừng thế, bỏ qua bước."""


# ---------------------------------------------------------------------------
# Các phép kiểm tất định — không tốn token nào
# ---------------------------------------------------------------------------


def _check_arithmetic(sol: Solution) -> list[Check]:
    """SymPy tính lại từng bước, THẾ giá trị các ký hiệu vào trước khi tính.

    Vì sao phải thế ký hiệu: model gần như luôn viết vế phải bằng CÔNG THỨC CHỮ
    (`V = Sday * h / 3`) và chỉ để con số ở trường `result`. Bản cũ đọc thẳng vế
    phải, gặp toàn ký hiệu tự do nên `numeric` là None và **bỏ qua bước đó** — rồi
    vẫn báo "số học các bước khớp". Đo được: mọi bước của một bài đều bị bỏ qua,
    lời giải nhân sai một tích mà vẫn PASS trót lọt.

    Nguồn giá trị để thế: vế trái các bước TRƯỚC — `Sday` lấy từ kết quả bước 2.

    Thế ở mức VĂN BẢN chứ không qua SymPy, vì `implicit_multiplication_application`
    xé `Sday` thành `S*d*a*y` và ký hiệu ghép sẽ không bao giờ khớp bảng.

    Ngưỡng 1% là cố ý: model làm tròn 0,39738 -> 0,397 là hợp lệ, không phải lỗi.
    Báo oan một bước đúng thì tai hại hơn bỏ sót, vì nó kích hoạt vòng giải lại.
    Thiếu dù chỉ một ký hiệu là bỏ qua bước — thà không kiểm còn hơn kiểm bừa.
    """
    out: list[Check] = []
    bang: dict[str, float] = {}  # ký hiệu -> giá trị, gom dần theo thứ tự các bước
    da_kiem = 0

    for st in sol.steps:
        expr, res = (st.expression or "").strip(), (st.result or "").strip()
        vb = _doc_so_ket_qua(res)
        if not expr or vb is None:
            continue

        rhs_txt = expr.split("=")[-1] if "=" in expr else expr
        va = _tinh_sau_khi_the(rhs_txt, bang)
        if va is not None and not _lech_do_doi_don_vi(va, vb):
            da_kiem += 1
            scale = max(1e-9, abs(va))
            if abs(va - vb) / scale > 0.01:
                out.append(
                    Check(
                        kind="sympy",
                        passed=False,
                        step_id=st.id,
                        detail_vi=(
                            f"SAI SỐ HỌC ở bước {st.id}: thế số vào `{rhs_txt.strip()}` "
                            f"được {va:.6g} nhưng bước ghi {vb:.6g}. "
                            f"Hãy dùng {va:.6g} và tính lại mọi bước phụ thuộc."
                        ),
                    )
                )

        # Ghi ký hiệu vế trái vào bảng cho các bước sau dùng — kể cả khi bước này
        # không kiểm được, vì kết quả của nó vẫn là dữ kiện cho bước kế tiếp.
        if "=" in expr:
            ten = _chuan_hoa_ky_hieu(expr.split("=")[0])
            if _TEN_KY_HIEU.fullmatch(ten):
                bang[ten] = vb

    if not out:
        out.append(
            Check(
                kind="sympy",
                passed=True,
                detail_vi=(
                    f"Số học khớp ở {da_kiem}/{len(sol.steps)} bước thế được số."
                    if da_kiem
                    else "Không bước nào đủ dữ kiện để tính lại — chưa kiểm được số học."
                ),
            )
        )
    return out


# Đại lượng hình học không bao giờ âm. Bắt theo mô tả của ẩn cần tìm, vì đề Toán
# hiếm khi ghi đơn vị vào `unknowns`.
_DAI_LUONG_DUONG = (
    "thể tích", "diện tích", "độ dài", "khoảng cách", "bán kính", "chu vi",
    "đường cao", "chiều cao", "cạnh",
)


def _check_hinh_hoc(plan: Plan, sol: Solution) -> list[Check]:
    """Soát tính hợp lệ hình học của đáp số — thay chỗ của phép soát thứ nguyên.

    Đề Toán gần như không ràng buộc đơn vị, nên soát thứ nguyên là vô nghĩa ở đây.
    Cái thật sự bắt được lỗi ở Hình học là DẤU: thể tích, diện tích, độ dài và
    khoảng cách không bao giờ âm.

    Đây là lỗi có thật và tất định — model 4B nhầm dấu khi thay số vào công thức
    khoảng cách từ điểm đến mặt phẳng (quên dấu giá trị tuyệt đối ở tử), hoặc trừ
    ngược hai toạ độ khi tính độ dài. Phép kiểm này không tốn token nào.
    """
    if plan.subject != "hinh_hoc" or not sol.final_answer.strip():
        return []

    mo_ta = " ".join(
        (u.description_vi or u.symbol or "") for u in plan.unknowns
    ).lower()
    if not any(t in mo_ta for t in _DAI_LUONG_DUONG):
        return []

    gia_tri = _doc_so_ket_qua(sol.final_answer)
    if gia_tri is None or gia_tri >= 0:
        return []
    return [
        Check(
            kind="consistency",
            passed=False,
            detail_vi=(
                f"ĐÁP SỐ ÂM cho một đại lượng hình học ({mo_ta.strip()}): "
                f"{gia_tri:.6g}. Thể tích, diện tích, độ dài và khoảng cách luôn "
                "không âm — hãy soát lại dấu khi thay số, thường là quên giá trị "
                "tuyệt đối hoặc trừ ngược thứ tự."
            ),
        )
    ]


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
    checks += _check_hinh_hoc(plan, sol)
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
    check_rc: Check | None = None
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

    # ---- Đường tắt: phép kiểm tất định đã đủ căn cứ thì khỏi tiêu 6,5 giây ----
    #
    # Chỉ đi tắt khi thoả CẢ HAI:
    #   1. không phép kiểm tất định nào hỏng
    #   2. bộ tính lại ĐỘC LẬP đã xác nhận đáp số
    #
    # Điều kiện 2 là mấu chốt. Thiếu nó thì "mọi phép kiểm đều đạt" có thể chỉ
    # nghĩa là chẳng phép kiểm nào chạy được — bài Toán không có bước nào quy được
    # về số thì `_check_arithmetic` vẫn trả về "Số học các bước khớp".
    xac_nhan_doc_lap = check_rc is not None and check_rc.passed
    if config.BO_QUA_LLM_REVIEW and not failed and xac_nhan_doc_lap:
        return (
            VerifyReport(
                verdict="PASS",
                checks=checks,
                suggestion_vi="",
                confidence=0.85,
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
