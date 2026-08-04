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
from tools import sympy_tool


class RecomputeSpec(BaseModel):
    """Công thức đóng do model viết, để SymPy tính hộ."""

    expression: str = Field(default="", description="Biểu thức SymPy đã thay số")
    unit: str = ""
    approach_vi: str = ""
    solvable: bool = True


SYSTEM = """Bạn là bộ tính lại độc lập. Bạn KHÔNG trình bày lời giải.

Nhiệm vụ: đọc đề, chọn công thức đúng, THAY SỐ vào, rồi trả về MỘT biểu thức duy
nhất mà giá trị của nó chính là đáp số.

TUYỆT ĐỐI KHÔNG tự tính ra con số cuối. Công cụ sẽ tính. Việc của bạn là viết
đúng công thức đã thay số.

Trả JSON:
- expression: biểu thức theo cú pháp SymPy/Python. Dùng pi, sqrt(), exp(), log().
  Chỉ chứa số và phép toán, KHÔNG chứa ký hiệu chưa biết giá trị.
- unit: đơn vị của kết quả, không có thì để rỗng
- approach_vi: một câu ngắn nêu công thức đã dùng
- solvable: false nếu đề không quy được về một biểu thức

Ví dụ:
Đề "Vật dao động điều hoà biên độ 5 cm, tần số 2 Hz, tính vận tốc cực đại"
-> expression: "0.05*2*pi*2"
   unit: "m/s"
   approach_vi: "v_max = A*omega = A*2*pi*f, đổi 5 cm = 0,05 m"

Đề "Tính đạo hàm của y = x^3 - 3x^2 + 2x tại x = 1"
-> expression: "3*1**2 - 6*1 + 2"
   unit: ""
   approach_vi: "y' = 3x^2 - 6x + 2, thay x = 1"

Đề "Đốt cháy 5,6 gam Fe thu Fe3O4"
-> expression: "5.6/56/3*232"
   unit: "gam"
   approach_vi: "n(Fe) = 5,6/56; theo 3Fe -> Fe3O4 thì n(Fe3O4) = n(Fe)/3; nhân M = 232"

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

    `sympy_tool.evaluate("0.628 m/s")` đọc `m` và `s` thành ký hiệu tự do nên
    KHÔNG ra số — mà gần như mọi đáp án Lý và Hoá đều kèm đơn vị. Chỉ dựa vào
    SymPy thì phép so sánh này im lặng bỏ qua phần lớn bài, đúng loại lỗi câm
    đã gặp vài lần hôm nay.
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


class KetQua(BaseModel):
    """Kết quả tính độc lập, tính MỘT LẦN cho mỗi câu hỏi rồi dùng lại.

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
    if spec is None or not spec.solvable or not spec.expression.strip():
        return KetQua(), span

    tinh = sympy_tool.evaluate(spec.expression)
    if not tinh.get("ok"):
        return KetQua(approach_vi=spec.approach_vi), span

    if tinh.get("numeric") is not None:
        return (
            KetQua(
                gia_tri=float(tinh["numeric"]),
                unit=spec.unit,
                approach_vi=spec.approach_vi,
            ),
            span,
        )

    # Không quy được về số nhưng SymPy vẫn đọc được: đáp số dạng biểu thức.
    # `exact` là bản đã rút gọn, dùng nó để so sánh cho ổn định.
    return (
        KetQua(
            bieu_thuc=str(tinh.get("exact") or spec.expression).strip(),
            unit=spec.unit,
            approach_vi=spec.approach_vi,
        ),
        span,
    )


def compare(kq: KetQua, final_answer: str) -> Check | None:
    """So kết quả độc lập với đáp số của Subject Agent.

    Không tự động ghi đè đáp số — ghi đè mù là cách nhanh nhất để biến một lời
    giải đúng thành sai. Chỉ báo lệch và gợi ý giá trị cho vòng giải lại.
    """
    if not kq.co_gia_tri or not final_answer.strip():
        return None
    if kq.gia_tri is not None:
        check = _so_sanh(kq.gia_tri, final_answer)
    else:
        check = _so_sanh_bieu_thuc(kq.bieu_thuc, final_answer)
    if check is not None and not check.passed and kq.approach_vi:
        check.detail_vi += f" Công thức dùng: {kq.approach_vi}"
    return check
