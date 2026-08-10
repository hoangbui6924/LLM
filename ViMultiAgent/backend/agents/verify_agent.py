"""Verify Agent — mục 3.4.

Đây là agent quyết định độ tin cậy của cả hệ thống, và nó **không tin LLM**.

Thứ tự kiểm tra có chủ đích: chạy các phép kiểm TẤT ĐỊNH trước (tính lại bằng
SymPy, soát thứ nguyên, soát bảo toàn nguyên tố), rồi mới đưa kết quả đó cho LLM
đọc. Làm ngược lại thì LLM sẽ "đồng ý" với lời giải sai — mô hình 8B rất dễ bị
cuốn theo lập luận trôi chảy.

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


# Đuôi đơn vị dính sau con số ở trường `result`. Phải bóc trước khi đọc số, nếu
# không SymPy coi "mol" là ký hiệu tự do và cả phép kiểm bị bỏ qua im lặng.
_DUOI_DON_VI = re.compile(
    r"\s*(g/mol|mol/l|kmol|mol|kg|g|lít|lit|ml|m/s\^?2|m/s|km/h|cm|mm|km|nm|m"
    r"|giây|s|phút|giờ|h|N|J|kJ|W|Pa|atm|K|Hz|rad/s|rad|độ|%)\s*$",
    re.IGNORECASE,
)

# Ký hiệu khối lượng mol model hay viết: MNa2O, M_Na2O, M(Na2O) — sau chuẩn hoá
# thì cả ba về cùng dạng MNa2O.
_KY_HIEU_KHOI_LUONG_MOL = re.compile(r"^M([A-Z][A-Za-z0-9]*)$")

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
    if ten in bang:
        return bang[ten]
    khop = _KY_HIEU_KHOI_LUONG_MOL.match(ten)
    if khop:
        tinh = chem_tool.molar_mass(khop.group(1))
        if tinh.get("ok"):
            return float(tinh["molar_mass"])
    return None


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
    """0,2 -> 0.2. Chỉ đổi dấu phẩy nằm GIỮA hai chữ số, không đụng dấu ngăn cách."""
    return re.sub(r"(?<=\d),(?=\d)", ".", s)


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
    (`mNa2O = nNa2O * MNa2O`) và chỉ để con số ở trường `result`. Bản cũ đọc thẳng
    vế phải, gặp toàn ký hiệu tự do nên `numeric` là None và **bỏ qua bước đó** —
    rồi vẫn báo "số học các bước khớp". Đo trên một bài Hoá thật: cả 4 bước đều bị
    bỏ qua, lời giải ghi 0,1 × 62 = 3,8 (đúng phải là 6,2) mà vẫn PASS trót lọt.

    Hai nguồn giá trị để thế:
      1. Vế trái các bước TRƯỚC — `nNa2O` lấy từ kết quả bước 3.
      2. Ký hiệu khối lượng mol `M<công thức>` — tra bảng nguyên tử khối, tất định.

    Thế ở mức VĂN BẢN chứ không qua SymPy, vì `implicit_multiplication_application`
    xé `nNa2O` thành `n*N*a**2*O` và ký hiệu ghép sẽ không bao giờ khớp bảng.

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


# Khối lượng mol model tự khai: "M(Fe3O4) = 232", "M_{Fe_3O_4}=232", "M (NaOH) = 40".
_KHOI_LUONG_MOL = re.compile(
    r"M\s*_?\s*[\(\{\[]\s*([A-Za-z][A-Za-z0-9()\._\{\}\s]*?)\s*[\)\}\]]\s*=\s*"
    r"([0-9]+(?:[.,][0-9]+)?)"
)


def _don_gian_cong_thuc(s: str) -> str:
    """`Fe_3O_4` và `Fe_{3}O_{4}` đều về `Fe3O4`.

    Model viết công thức hoá học bằng cú pháp LaTeX vì prompt bảo viết LaTeX trần.
    Không gỡ chỉ số dưới thì `parse_formula` không đọc nổi và phép kiểm im lặng
    bỏ qua — đúng loại lỗi câm tệ nhất.
    """
    return re.sub(r"[_\{\}\s]", "", s or "")


def _check_khoi_luong_mol(sol: Solution) -> list[Check]:
    """Soát mọi khối lượng mol model tự khai, bằng bảng nguyên tử khối.

    Vì sao cần: `chem_tool.molar_mass` tất định và không bao giờ sai, nhưng trước
    đây không agent nào gọi tới — model 4B phải tự nhớ M(Fe3O4) = 232 và nhớ sai
    thì hỏng cả bài mà không tầng nào phát hiện. Đây là lỗi Hoá hay gặp nhất.

    Trả kèm GIÁ TRỊ ĐÚNG vào phần mô tả, giống cách `balance_equation` làm với hệ
    số, để vòng giải lại có cái mà sửa thay vì đoán tiếp.
    """
    if not config.KIEM_KHOI_LUONG_MOL:
        return []

    ra: list[Check] = []
    da_soat: set[str] = set()

    for st in sol.steps:
        for nguon in (st.expression, st.result, st.goal_vi, st.reason_vi):
            for khop in _KHOI_LUONG_MOL.finditer(nguon or ""):
                cong_thuc = _don_gian_cong_thuc(khop.group(1))
                if not cong_thuc or cong_thuc in da_soat:
                    continue
                try:
                    khai = float(khop.group(2).replace(",", "."))
                except ValueError:
                    continue

                tinh = chem_tool.molar_mass(cong_thuc)
                if not tinh.get("ok"):
                    continue  # không phải công thức hoá học hợp lệ, bỏ qua
                da_soat.add(cong_thuc)

                dung = float(tinh["molar_mass"])
                lech = abs(dung - khai) / max(1e-9, dung)
                if lech <= config.DUNG_SAI_KHOI_LUONG_MOL:
                    continue

                ra.append(
                    Check(
                        kind="conservation",
                        passed=False,
                        step_id=st.id,
                        detail_vi=(
                            f"SAI KHỐI LƯỢNG MOL: lời giải ghi M({cong_thuc}) = {khai:g} "
                            f"nhưng tính từ bảng nguyên tử khối được {dung:.4g} g/mol "
                            f"(lệch {lech * 100:.1f}%). Hãy dùng {dung:.4g} và tính lại "
                            f"mọi bước phụ thuộc giá trị này."
                        ),
                    )
                )

    if not ra and da_soat:
        ra.append(
            Check(
                kind="conservation",
                passed=True,
                detail_vi=f"Khối lượng mol đúng cho: {', '.join(sorted(da_soat))}.",
            )
        )
    return ra


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
        checks += _check_khoi_luong_mol(sol)
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
