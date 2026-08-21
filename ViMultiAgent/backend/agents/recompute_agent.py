"""Tính lại độc lập — mắt thứ hai cho Verify Agent.

Vấn đề đã đo được
-----------------
Phép kiểm SymPy ban đầu chỉ đối chiếu `expression` với `result` TRONG CÙNG một
bước. Model viết sai công thức ngay từ đầu thì hai vế vẫn khớp nhau, và kiểm tra
báo ĐẠT. Kết quả thực nghiệm: 3/3 bài mẫu sai đáp số mà Verify vẫn cho PASS 2 bài.

Nói cách khác, phép kiểm cũ đo *tính nhất quán*, không đo *tính đúng đắn*.

Cách làm ở đây
--------------
Yêu cầu model viết MỘT biểu thức đóng — công thức đã thay số — mà giá trị của nó
chính là đáp số. Model không được tự tính; **SymPy tính**. Sau đó so với đáp số
mà Subject Agent đưa ra.

Đây đúng tinh thần mục 8 của đề bài: LLM quyết định LÀM GÌ (chọn công thức),
công cụ quyết định KẾT QUẢ LÀ BAO NHIÊU.

Giới hạn cần biết: cách này bắt được lỗi số học và lỗi thay số, và bắt được cả
trường hợp hai lần suy luận độc lập cho ra hai công thức khác nhau. Nó KHÔNG bắt
được lỗi khái niệm mà model mắc nhất quán ở cả hai lần — khi đó cả hai cùng sai
giống nhau. Vì vậy kết luận trả về là "hai nguồn khớp/lệch", không phải "đúng".
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Check, Plan
from tools import kiem_symbolic, sympy_tool


class RecomputeSpec(BaseModel):
    """Công thức đóng do model viết, để SymPy tính hộ."""

    expression: str = Field(default="", description="Biểu thức SymPy đã thay số")
    unit: str = ""
    approach_vi: str = ""
    solvable: bool = True

    # ---- Trích xuất cấu trúc để SymPy tự giải lại ---------------------------
    #
    # Đây là đường thứ HAI, mạnh hơn hẳn `expression`. Với `expression`, model
    # phải tự suy luận ra công thức đã thay số — việc khó, và đo được là chỉ dùng
    # được ở ~16% số bài dù tốn 42 giây.
    #
    # Với mấy trường dưới đây, model chỉ cần CHÉP LẠI đề bài dưới dạng máy đọc
    # được: hàm nào, biến nào, tại điểm nào. Việc dễ hơn nhiều, không cần suy nghĩ.
    # Rồi SymPy tự lấy đạo hàm, tự tính tích phân, tự thế nghiệm — tất định, vài
    # mili giây, không bao giờ sai.
    #
    # Đúng triết lý dự án: LLM quyết định LÀM GÌ, SymPy quyết định RA BAO NHIÊU.
    loai_kiem: str = Field(
        default="",
        description="dao_ham | tich_phan | gioi_han | phuong_trinh | tiep_tuyen | rỗng",
    )
    ham_goc: str = ""
    bien: str = "x"
    diem: str = ""
    can_duoi: str = ""
    can_tren: str = ""


SYSTEM = """Bạn là bộ tính lại độc lập. Bạn KHÔNG trình bày lời giải.

QUAN TRỌNG NHẤT — nếu đề thuộc một trong năm dạng dưới đây, hãy CHÉP LẠI ĐỀ dưới
dạng máy đọc được. Đừng tính gì cả, công cụ sẽ tự giải:

- Tính đạo hàm  -> loai_kiem="dao_ham",  ham_goc=hàm số, bien="x", diem=điểm (nếu có)
- Tính tích phân -> loai_kiem="tich_phan", ham_goc=hàm dưới dấu tích phân,
                    can_duoi và can_tren (nếu là tích phân xác định)
- Tính giới hạn -> loai_kiem="gioi_han", ham_goc=biểu thức, diem=điểm tiến tới
                    (viết "oo" cho vô cùng)
- Giải phương trình -> loai_kiem="phuong_trinh", ham_goc="vế trái = vế phải"
- Viết phương trình tiếp tuyến -> loai_kiem="tiep_tuyen", ham_goc=hàm số,
                    diem=hoành độ tiếp điểm

Ví dụ:
Đề "Tính đạo hàm của y = x^3 - 3x^2 + 2x tại x = 1"
-> loai_kiem: "dao_ham", ham_goc: "x**3 - 3*x**2 + 2*x", bien: "x", diem: "1"

Đề "Tính tích phân I = ∫ từ 0 đến 1 của x·e^x dx"
-> loai_kiem: "tich_phan", ham_goc: "x*exp(x)", bien: "x", can_duoi: "0", can_tren: "1"

Đề "Cho y = x^2 + 3x + 5. Viết phương trình tiếp tuyến tại x = 2"
-> loai_kiem: "tiep_tuyen", ham_goc: "x**2 + 3*x + 5", bien: "x", diem: "2"

Đề "Giải phương trình x^2 - 5x + 6 = 0"
-> loai_kiem: "phuong_trinh", ham_goc: "x**2 - 5*x + 6 = 0", bien: "x"

Nếu đề KHÔNG thuộc năm dạng trên (bài hình học không gian, bài toạ độ, bài đếm,
bài xác suất) thì để loai_kiem rỗng và làm theo phần dưới đây.

---

Nhiệm vụ dự phòng: đọc đề, chọn công thức đúng, THAY SỐ vào, rồi trả về MỘT biểu
thức duy nhất mà giá trị của nó chính là đáp số.

TUYỆT ĐỐI KHÔNG tự tính ra con số cuối. Công cụ sẽ tính. Việc của bạn là viết
đúng công thức đã thay số.

Trả JSON:
- expression: biểu thức theo cú pháp SymPy/Python. Dùng pi, sqrt(), exp(), log().
  Chỉ chứa số và phép toán, KHÔNG chứa ký hiệu chưa biết giá trị.
- unit: đơn vị của kết quả, không có thì để rỗng
- approach_vi: một câu ngắn nêu công thức đã dùng
- solvable: false nếu đề không quy được về một biểu thức

Ví dụ:
Đề "Tính đạo hàm của y = x^3 - 3x^2 + 2x tại x = 1"
-> expression: "3*1**2 - 6*1 + 2"
   unit: ""
   approach_vi: "y' = 3x^2 - 6x + 2, thay x = 1"

Đề "Khối chóp có diện tích đáy 12 và chiều cao 5. Tính thể tích"
-> expression: "12*5/3"
   unit: ""
   approach_vi: "V = (1/3)*S_đáy*h"

Đề "Trong Oxyz, tính khoảng cách từ A(1;2;3) đến mặt phẳng x + 2y - 2z + 1 = 0"
-> expression: "Abs(1 + 2*2 - 2*3 + 1)/sqrt(1**2 + 2**2 + (-2)**2)"
   unit: ""
   approach_vi: "d = |ax0 + by0 + cz0 + d|/sqrt(a^2 + b^2 + c^2)"

Đề "Có bao nhiêu cách chọn 3 học sinh từ 10 học sinh"
-> expression: "binomial(10, 3)"
   unit: ""
   approach_vi: "Tổ hợp C(10,3), không kể thứ tự"

Khi đáp số KHÔNG phải một con số mà là BIỂU THỨC (phương trình tiếp tuyến, đạo
hàm, nguyên hàm, nghiệm theo tham số), vẫn viết một biểu thức duy nhất — phần vế
phải, theo biến của đề. Đừng ghi "y =" ở đầu.

Đề "Cho y = (x^2+1)/(x-1). Viết phương trình tiếp tuyến tại điểm có hoành độ x = 2"
-> expression: "-1*(x - 2) + 5"
   unit: ""
   approach_vi: "y(2) = 5; y' = (x^2-2x-1)/(x-1)^2, y'(2) = -1; tiếp tuyến y = y'(2)(x-2) + y(2)"
"""


# Đáp số dạng biểu thức hay được viết kèm vế trái: "y = -x + 7", "f'(x) = 2x".
# Chỉ cần vế phải để so sánh.
_VE_TRAI = re.compile(r"^\s*[A-Za-z][A-Za-z0-9_']*\s*(\([^)]*\))?\s*=\s*")


def _boc_ve_phai(s: str) -> str:
    return _VE_TRAI.sub("", (s or "").strip())


def _so_sanh_bieu_thuc(bieu_thuc_cong_cu: str, dap_an_model: str) -> Check | None:
    """So hai BIỂU THỨC bằng rút gọn tượng trưng, không phải so chuỗi.

    `-x + 7` và `-(x - 2) + 5` là một, `5x - 5` thì không. So chuỗi không phân
    biệt được, `sympy.simplify(a - b) == 0` thì có.
    """
    a, b = _boc_ve_phai(bieu_thuc_cong_cu), _boc_ve_phai(dap_an_model)
    if not a or not b:
        return None
    kq = sympy_tool.are_equivalent(a, b)
    if not kq.get("ok"):
        return None
    if kq.get("equivalent"):
        return Check(
            kind="sympy",
            passed=True,
            detail_vi=f"Biểu thức độc lập rút gọn về `{a}`, tương đương đáp số.",
        )
    return Check(
        kind="sympy",
        passed=False,
        detail_vi=f"Tính lại độc lập cho `{a}` nhưng lời giải ghi `{b}`.",
    )


_SO_DAN_DAU = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)")


def _doc_so(s: str) -> float | None:
    """Đọc số từ đáp án có thể kèm đơn vị.

    `sympy_tool.evaluate("12.5 cm^3")` đọc `cm` thành ký hiệu tự do nên KHÔNG ra
    số — mà đáp án hình học thường kèm đơn vị độ dài, diện tích hoặc thể tích.
    Chỉ dựa vào SymPy thì phép so sánh này im lặng bỏ qua phần lớn bài hình, đúng
    loại lỗi câm tệ nhất.
    """
    if not s or not s.strip():
        return None
    r = sympy_tool.evaluate(s)
    if r.get("ok") and r.get("numeric") is not None:
        return float(r["numeric"])
    m = _SO_DAN_DAU.match(s.strip().replace(",", "."))
    return float(m.group(1)) if m else None


def _so_sanh(gia_tri_cong_cu: float, dap_an_model: str) -> Check | None:
    """So đáp số của Subject Agent với giá trị SymPy tính từ công thức độc lập."""
    doc_duoc = _doc_so(dap_an_model)
    if doc_duoc is None:
        # Đáp án bằng chữ, không có số nào để so — không kết luận.
        return None
    vb = doc_duoc
    thang = max(1e-9, abs(gia_tri_cong_cu))
    lech = abs(gia_tri_cong_cu - vb) / thang
    if lech <= 0.01:
        return Check(
            kind="sympy",
            passed=True,
            detail_vi=f"Tính lại độc lập cho {gia_tri_cong_cu:.6g}, khớp đáp số.",
        )
    return Check(
        kind="sympy",
        passed=False,
        detail_vi=(
            f"Tính lại độc lập cho {gia_tri_cong_cu:.6g} nhưng lời giải ghi "
            f"{vb:.6g} (lệch {lech * 100:.1f}%)."
        ),
    )


# Từ khoá BẮT BUỘC phải có trong đề thì `loai_kiem` mới được chấp nhận.
#
# ĐO ĐƯỢC trên 150 bài: 34 lời giải ĐÚNG bị Verify kêu FAIL, và 33 trong số đó là
# do model gán nhầm `loai_kiem`. Ca điển hình: đề "Cho f(x) = 3x^2 + 5x - 1, tính
# f(3)" bị gán "dao_ham", SymPy tính đạo hàm tại 3 được 23 trong khi đáp án đúng là
# giá trị hàm số 41 — rồi kết luận lời giải sai.
#
# Phép kiểm tất định có quyền phủ quyết, nên nó phải CHẮC. Trích xuất sai loại bài
# thì thà bỏ qua còn hơn phán bừa.
_TU_KHOA_LOAI = {
    "dao_ham": ("đạo hàm", "dao ham", "y'", "f'", "đạo hàm cấp"),
    "tich_phan": ("tích phân", "tich phan", "nguyên hàm", "nguyen ham", "∫"),
    "gioi_han": ("giới hạn", "gioi han", "lim", "tiến tới", "tien toi", "dần tới"),
    "phuong_trinh": ("giải phương trình", "giai phuong trinh", "nghiệm", "nghiem"),
    "tiep_tuyen": ("tiếp tuyến", "tiep tuyen"),
}


def _loai_kiem_hop_le(loai: str, de_bai: str) -> bool:
    """Đề bài có thật sự thuộc loại mà model khai không.

    Chỉ nhận khi đề CHỨA từ khoá đặc trưng. Model 4B trích xuất sai loại khá
    thường xuyên, và mỗi lần sai là một lần Verify báo oan lời giải đúng.
    """
    tu = _TU_KHOA_LOAI.get(loai)
    if not tu:
        return False
    thap = (de_bai or "").lower()
    return any(t in thap for t in tu)


def _con_ky_hieu_tu_do(bieu_thuc: str) -> bool:
    """Biểu thức còn ẩn chưa biết giá trị hay không.

    `x*(3*x + 4)` còn `x` => chưa tính xong. `232/3` thì không còn gì.
    Parse hỏng cũng coi là còn ẩn: không đọc được thì không đủ căn cứ để tin.
    """
    if not bieu_thuc.strip():
        return True
    try:
        return bool(sympy_tool.parse(bieu_thuc).free_symbols)
    except Exception:  # noqa: BLE001
        return True


class KetQua(BaseModel):
    """Kết quả tính độc lập, tính MỘT LẦN cho mỗi câu hỏi rồi dùng lại.

    Trường `ly_do_hong` để chẩn đoán, không dùng cho logic. ĐO ĐƯỢC: vai này ngốn
    41,6 giây (62% tổng thời gian) nhưng chỉ đưa ra kết luận dùng được ở ~16% số
    bài — cần biết 84% còn lại hỏng ở khâu nào mới sửa được.

    Hai dạng, vì không phải đáp số nào cũng là con số:
      * `gia_tri`  — đáp số bằng số (vận tốc, khối lượng, giá trị đạo hàm tại điểm)
      * `bieu_thuc` — đáp số là BIỂU THỨC (phương trình tiếp tuyến, nguyên hàm...)

    Bỏ sót dạng thứ hai là lỗi đã gặp thật: câu "viết phương trình tiếp tuyến" đi
    qua toàn bộ tầng kiểm chứng mà không phép kiểm nào chạy được, vì tất cả đều
    chỉ so sánh số.
    """

    gia_tri: float | None = None
    bieu_thuc: str = ""
    unit: str = ""
    approach_vi: str = ""
    # "" nghĩa là chạy trót lọt. Các giá trị: khong_ra_json, model_bo_tay,
    # bieu_thuc_rong, sympy_khong_doc_duoc, con_ky_hieu_tu_do.
    ly_do_hong: str = ""

    # Cấu trúc bài toán để SymPy TỰ GIẢI LẠI — mạnh hơn `gia_tri` vì không phụ
    # thuộc việc model có tự tính đúng hay không. Rỗng khi đề không thuộc năm dạng
    # kiểm được.
    loai_kiem: str = ""
    ham_goc: str = ""
    bien: str = "x"
    diem: str = ""
    can_duoi: str = ""
    can_tren: str = ""

    @property
    def co_cau_truc(self) -> bool:
        return bool(self.loai_kiem and self.ham_goc)

    @property
    def co_gia_tri(self) -> bool:
        return self.gia_tri is not None or bool(self.bieu_thuc.strip())

    def mo_ta(self) -> str:
        if self.gia_tri is not None:
            return f"{self.gia_tri:.6g}" + (f" {self.unit}" if self.unit else "")
        return self.bieu_thuc.strip()


async def compute(
    plan: Plan, timeout: float | None = None
) -> tuple[KetQua, AgentSpan | None]:
    """Tính đáp số độc lập TỪ ĐỀ BÀI — không cần biết Subject Agent giải ra gì.

    Vì chỉ phụ thuộc `plan`, hàm này chạy SONG SONG với Subject Agent được. Đó là
    lý do nó tách khỏi `compare`: xếp nối tiếp thì tốn thêm 5-8 giây mỗi vòng,
    còn chạy song song thì gần như miễn phí về thời gian thực.
    """
    spec, span = await run_structured(
        name="recompute",
        system=SYSTEM,
        task=f"Đề bài:\n{plan.normalized_question}",
        out_type=RecomputeSpec,
        model=config.MODEL_HEAVY,
        max_tokens=config.MAX_TOKENS_RECOMPUTE,
        timeout=timeout,
    )
    if spec is None:
        return KetQua(ly_do_hong="khong_ra_json"), span

    # Cấu trúc bài toán được ưu tiên: nó cho phép SymPy TỰ GIẢI LẠI thay vì tin
    # con số model tự tính. Giữ kèm cả `expression` nếu có, hai đường bổ trợ nhau.
    # Chốt chặn: loại bài model khai phải khớp từ khoá trong ĐỀ GỐC. Không khớp
    # thì bỏ hẳn cấu trúc, rơi về đường `expression` như cũ.
    loai = (spec.loai_kiem or "").strip()
    de_goc = f"{plan.raw_question} {plan.normalized_question}"
    if loai and not _loai_kiem_hop_le(loai, de_goc):
        loai = ""

    cau_truc = dict(
        loai_kiem=loai,
        ham_goc=(spec.ham_goc or "").strip(),
        bien=(spec.bien or "x").strip() or "x",
        diem=(spec.diem or "").strip(),
        can_duoi=(spec.can_duoi or "").strip(),
        can_tren=(spec.can_tren or "").strip(),
    )

    if not spec.solvable:
        return KetQua(ly_do_hong="model_bo_tay", **cau_truc), span
    if not spec.expression.strip():
        # Không có biểu thức nhưng CÓ cấu trúc thì vẫn dùng được — SymPy tự giải.
        if cau_truc["loai_kiem"] and cau_truc["ham_goc"]:
            return KetQua(approach_vi=spec.approach_vi, **cau_truc), span
        return KetQua(ly_do_hong="bieu_thuc_rong", **cau_truc), span

    tinh = sympy_tool.evaluate(spec.expression)
    if not tinh.get("ok"):
        return (
            KetQua(approach_vi=spec.approach_vi, ly_do_hong="sympy_khong_doc_duoc",
                   **cau_truc),
            span,
        )

    if tinh.get("numeric") is not None:
        return (
            KetQua(
                gia_tri=float(tinh["numeric"]),
                unit=spec.unit,
                approach_vi=spec.approach_vi,
                **cau_truc,
            ),
            span,
        )

    # Không quy được về số nhưng SymPy vẫn đọc được: đáp số dạng biểu thức.
    # `exact` là bản đã rút gọn, dùng nó để so sánh cho ổn định.
    bieu_thuc = str(tinh.get("exact") or spec.expression).strip()

    # Chặn kết quả DỞ DANG. Đề hỏi một con số mà biểu thức còn ký hiệu tự do thì
    # bộ tính lại chưa làm xong việc — nó dừng ở nguyên hàm chưa thay cận, hoặc ở
    # chính hàm số chưa tìm cực trị. Nhận bừa thứ đó là tai hại: Manager sẽ lấy nó
    # đè lên đáp số ĐÚNG của Subject Agent (đo được 6 lần trên 150 bài).
    #
    # Trả rỗng thay vì trả bừa: không có mắt thứ hai còn hơn có một mắt nhìn sai.
    if config.LOC_TINH_LAI_DO_DANG and plan.question_type != "symbolic":
        if _con_ky_hieu_tu_do(bieu_thuc):
            return (
                KetQua(approach_vi=spec.approach_vi, ly_do_hong="con_ky_hieu_tu_do",
                       **cau_truc),
                span,
            )

    return (
        KetQua(
            bieu_thuc=bieu_thuc,
            unit=spec.unit,
            approach_vi=spec.approach_vi,
            **cau_truc,
        ),
        span,
    )


def _kiem_bang_cau_truc(kq: KetQua, final_answer: str) -> Check | None:
    """Cho SymPy TỰ GIẢI LẠI bài toán rồi đối chiếu — mạnh hơn mọi cách khác.

    Khác biệt cốt lõi so với `_so_sanh`: ở đó ta tin con số mà model tính ra; ở đây
    SymPy tự lấy đạo hàm, tự tính tích phân, tự thế nghiệm. Model chỉ chép lại đề.

    Đây là phép kiểm duy nhất bắt được lỗi mà cả Subject Agent lẫn bộ tính lại cùng
    mắc — trường hợp hai lần suy luận cùng sai giống nhau, vốn là lỗ hổng đã ghi rõ
    trong phần giới hạn ở đầu file này.
    """
    if not kq.co_cau_truc or not final_answer.strip():
        return None

    r = kiem_symbolic.kiem(
        loai=kq.loai_kiem,
        dap_an=_boc_ve_phai(final_answer),
        ham_goc=kq.ham_goc,
        bien=kq.bien,
        diem=kq.diem,
        can_duoi=kq.can_duoi,
        can_tren=kq.can_tren,
    )
    if r.dat is None:
        return None
    return Check(kind="sympy", passed=r.dat, detail_vi=r.mo_ta)


def compare(kq: KetQua, final_answer: str) -> Check | None:
    """So kết quả độc lập với đáp số của Subject Agent.

    Không tự động ghi đè đáp số — ghi đè mù là cách nhanh nhất để biến một lời
    giải đúng thành sai. Chỉ báo lệch và gợi ý giá trị cho vòng giải lại.
    """
    # Ưu tiên tuyệt đối cho phép kiểm bằng cấu trúc: SymPy tự giải lại thì không
    # phụ thuộc việc model có tính đúng hay không.
    theo_cau_truc = _kiem_bang_cau_truc(kq, final_answer)
    if theo_cau_truc is not None:
        return theo_cau_truc

    if not kq.co_gia_tri or not final_answer.strip():
        return None
    if kq.gia_tri is not None:
        check = _so_sanh(kq.gia_tri, final_answer)
    else:
        check = _so_sanh_bieu_thuc(kq.bieu_thuc, final_answer)
    if check is not None and not check.passed and kq.approach_vi:
        check.detail_vi += f" Công thức dùng: {kq.approach_vi}"
    return check
