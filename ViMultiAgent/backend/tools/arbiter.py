"""Trọng tài số học — SymPy quyết định mọi con số, không phải model.

Vì sao cần
----------
Prompt đã dặn "công cụ tính, model đừng tự nhẩm", nhưng dặn không có hiệu lực:
model 4B vẫn tự cộng trong đầu và vẫn sai. Đo được trên ba bài mẫu — sai dấu
(-1 thành 1) và làm tròn giữa chừng (7,73 thành 7,84).

Module này không xin phép. Với mỗi bước, nếu vế phải của `expression` quy được
về MỘT SỐ THUẦN thì giá trị đó ghi đè lên `result` của model. Chi phí vài mili
giây cho cả lời giải.

Nguyên tắc thận trọng — module này SỬA lời giải nên sai một lần là hỏng thật
------------------------------------------------------------------------------
Chỉ can thiệp khi thoả TOÀN BỘ:

  1. vế phải của `expression` quy được về một số, không còn ký hiệu tự do
  2. `result` cũng đọc ra được một số
  3. hai số lệch nhau QUÁ ngưỡng làm tròn

Thiếu điều nào thì để nguyên. Bỏ sót một lỗi thì còn Verify Agent phía sau; sửa
nhầm một bước đúng thì không ai cứu được, vì lời giải đã bị viết đè.

Ngưỡng 1% có chủ đích: model làm tròn 0,39738 thành 0,397 là hợp lệ, KHÔNG phải
lỗi. Sai số học thật thì lệch hàng chục phần trăm, hoặc sai dấu.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from core.schemas import Solution
from tools import sympy_tool

# Lệch dưới mức này là làm tròn hợp lệ, không đụng vào.
DUNG_SAI = 0.01

# LaTeX bọc dấu thập phân để canh khoảng cách: `0{,}397`. Không gỡ thì đọc thành
# `0` và trọng tài kết luận mâu thuẫn với `0.397` — báo oan một bước đúng.
_TEX_THAP_PHAN = re.compile(r"\{\s*([.,])\s*\}")
# Khoảng trắng LaTeX: \, \; \! \  — vô nghĩa về mặt số học.
_TEX_KHOANG = re.compile(r"\\[,;!:> ]")
# Dấu phẩy thập phân: dùng bộ đổi CÓ TRẠNG THÁI của `sympy_tool`, không dùng biểu
# thức chính quy.
#
# Bản cũ ở đây là `(?<=\d),(?=\d)` với chú thích "chỉ đổi khi nằm giữa hai chữ số
# để không phá dấu phẩy ngăn tham số hàm" — nhưng `C(5,2)` rơi đúng vào khuôn đó,
# và hậu quả là trọng tài ghi đè 0,357143 (ĐÚNG) thành 42,64. Xem ghi chú đầy đủ
# ở `sympy_tool.dau_phay_thap_phan`.


class SuaChua(BaseModel):
    """Một lần trọng tài ghi đè giá trị của model."""

    step_id: int
    bieu_thuc: str
    gia_tri_model: str
    gia_tri_dung: str

    def mo_ta(self) -> str:
        return (
            f"Bước {self.step_id}: model ghi {self.gia_tri_model}, "
            f"SymPy tính ra {self.gia_tri_dung}"
        )


def _chuan_hoa(s: str) -> str:
    s = s or ""
    s = _TEX_THAP_PHAN.sub(r"\1", s)
    s = _TEX_KHOANG.sub(" ", s)
    s = sympy_tool.dau_phay_thap_phan(s)
    return s.strip()


def _ve_phai(bieu_thuc: str) -> str:
    """Lấy phần cần tính. `v = 2*3` thì tính `2*3`, không tính cả đẳng thức."""
    return bieu_thuc.split("=")[-1] if "=" in bieu_thuc else bieu_thuc


def _doc_so(s: str) -> float | None:
    """Đọc một số từ chuỗi có thể lẫn đơn vị. `7.73 gam` -> 7.73."""
    if not s:
        return None
    r = sympy_tool.evaluate(_chuan_hoa(s))
    if r.get("ok") and r.get("numeric") is not None:
        return float(r["numeric"])
    # Đáp số thường kèm đơn vị nên SymPy parse hỏng. Bóc số dẫn đầu.
    m = re.match(r"\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", _chuan_hoa(s))
    return float(m.group(1)) if m else None


def _dinh_dang(v: float) -> str:
    """Viết lại số cho giống cách người ta trình bày, không dính đuôi float."""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.6g}"


def _lech_qua_nguong(a: float, b: float) -> bool:
    thang = max(1e-9, abs(a))
    return abs(a - b) / thang > DUNG_SAI


# Tên đứng ngay trước dấu mở ngoặc, tức một lời gọi hàm.
_LOI_GOI_HAM = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

# Hàm SymPy hiểu được. Ngoài danh sách này thì trọng tài không có căn cứ.
_HAM_BIET = frozenset(
    {
        "sqrt", "log", "ln", "exp", "abs", "Abs", "sin", "cos", "tan", "cot",
        "asin", "acos", "atan", "sinh", "cosh", "tanh", "floor", "ceiling",
        "binomial", "factorial", "gcd", "lcm", "Max", "Min", "root", "sign",
    }
)


def _co_ham_la(bieu_thuc: str) -> bool:
    """Biểu thức có lời gọi hàm mà SymPy không hiểu hay không.

    Đây là lưới an toàn thứ hai, sau khi `dau_phay_thap_phan` đã hết phá cú pháp.

    Vì sao vẫn cần: nhân ngầm của SymPy biến MỌI tên lạ thành ký hiệu tự do rồi
    nhân với phần trong ngoặc. Gặp `f(2)` nó cho ra `2*f`, gặp `P(A)/P(B)` nó rút
    gọn thành `A/B`. Không bao giờ báo lỗi, chỉ lặng lẽ trả về thứ vô nghĩa — và
    trọng tài thì có quyền GHI ĐÈ đáp án, nên tin nhầm ở đây là hỏng cả bài.

    Thà bỏ qua một bước còn hơn ghi đè bừa: bỏ qua thì đáp án của model giữ
    nguyên, ghi đè sai thì mất luôn đáp án đúng.
    """
    return any(
        ten not in _HAM_BIET for ten in _LOI_GOI_HAM.findall(bieu_thuc or "")
    )


def enforce(sol: Solution) -> list[SuaChua]:
    """Tính lại từng bước và ghi đè khi model sai. Trả danh sách chỗ đã sửa.

    Sửa TẠI CHỖ trên `sol`, kể cả `final_answer` nếu bước cuối bị sửa.
    """
    da_sua: list[SuaChua] = []

    for st in sol.steps:
        bieu_thuc = _chuan_hoa(st.expression)
        ket_qua = _chuan_hoa(st.result)
        if not bieu_thuc or not ket_qua:
            continue

        ve_phai = _ve_phai(bieu_thuc)
        if _co_ham_la(ve_phai):
            continue  # ký hiệu SymPy không hiểu => con số ra được là vô nghĩa

        tinh = sympy_tool.evaluate(ve_phai)
        if not tinh.get("ok") or tinh.get("numeric") is None:
            continue  # còn ký hiệu tự do, hoặc parse hỏng => không đủ căn cứ

        cua_model = _doc_so(ket_qua)
        if cua_model is None:
            continue

        dung = float(tinh["numeric"])
        if not _lech_qua_nguong(dung, cua_model):
            continue

        moi = _dinh_dang(dung)
        # Giữ lại đơn vị mà model đã ghi — chỉ thay phần số.
        duoi = re.sub(r"^\s*[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?\s*", "", ket_qua).strip()
        st.result = f"{moi} {duoi}".strip() if duoi else moi
        da_sua.append(
            SuaChua(
                step_id=st.id,
                bieu_thuc=st.expression,
                gia_tri_model=_dinh_dang(cua_model),
                gia_tri_dung=moi,
            )
        )

    _dong_bo_dap_an(sol, da_sua)
    return da_sua


def _dong_bo_dap_an(sol: Solution, da_sua: list[SuaChua]) -> None:
    """Nếu bước CUỐI bị sửa và đáp số đang lặp lại giá trị cũ thì sửa theo.

    Chỉ đụng vào đáp số khi nó khớp đúng con số sai của bước cuối. Đáp số là thứ
    người dùng đọc, ghi đè nhầm ở đây là tai hại nhất.
    """
    if not da_sua or not sol.steps:
        return
    cuoi = sol.steps[-1]
    sua_cuoi = next((s for s in da_sua if s.step_id == cuoi.id), None)
    if sua_cuoi is None:
        return

    trong_dap_an = _doc_so(sol.final_answer)
    if trong_dap_an is None:
        return
    if not _lech_qua_nguong(float(sua_cuoi.gia_tri_model), trong_dap_an):
        duoi = re.sub(
            r"^\s*[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?\s*", "", _chuan_hoa(sol.final_answer)
        ).strip()
        sol.final_answer = (
            f"{sua_cuoi.gia_tri_dung} {duoi}".strip() if duoi else sua_cuoi.gia_tri_dung
        )
        sol.final_answer_latex = sua_cuoi.gia_tri_dung
