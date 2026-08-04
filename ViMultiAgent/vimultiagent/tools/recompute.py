"""SymPy làm TRỌNG TÀI SỐ HỌC — con số cuối cùng do công cụ quyết định, không do model.

Nguyên tắc "LLM quyết định LÀM GÌ, công cụ quyết định KẾT QUẢ BAO NHIÊU" cho tới nay
mới chỉ nằm trong prompt. Trong code, `solver._execute_tools` chỉ chạy những công cụ mà
model TỰ KHAI BÁO — model 3B thường quên khai, và con số cuối vẫn là số nó nhẩm trong
đầu. Chính PRM của dự án đã đo ra hậu quả: recall lỗi `arithmetic` chỉ 77,4 % trong khi
bốn loại lỗi còn lại đều ~100 %, vì phát hiện sai số học đòi hỏi thực sự tính lại.

Module này tính lại, không xin phép. Chi phí ~5 ms cho cả lời giải.

---------------------------------------------------------------------------
NGUYÊN TẮC THẬN TRỌNG — module này SỬA lời giải, nên sai một lần là hỏng thật
---------------------------------------------------------------------------
Chỉ can thiệp khi CHẮC CHẮN, tức khi thoả toàn bộ:
  1. vế phải của `expression_latex` quy được về MỘT SỐ THUẦN (không còn ký hiệu tự do)
  2. `result_latex` cũng đọc ra được một số
  3. hai số lệch nhau QUÁ ngưỡng làm tròn

Không thoả điều nào thì để nguyên. Bỏ sót một lỗi số học thì còn T1/T2/T3 phía sau;
sửa nhầm một bước đúng thì không ai cứu được, vì lời giải đã bị viết đè.

Ngưỡng 1 % có chủ đích: model làm tròn hợp lệ (0,39738 -> 0,397) là chuyện bình thường
và KHÔNG được coi là lỗi. Sai số học thật thì lệch hàng chục phần trăm trở lên.
"""

from __future__ import annotations

import math
import re
from typing import Any

from ..core.schemas import Solution, SolutionStep, VerdictItem
from . import sympy_tool

# Lệch dưới ngưỡng này là làm tròn, không phải lỗi.
REL_TOL = 0.01

_LEADING_NUM = re.compile(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")
# Dấu phẩy thập phân kiểu Việt Nam: chỉ đổi khi nằm GIỮA hai chữ số, để không phá
# dấu phẩy ngăn cách tham số hàm.
_VN_DECIMAL = re.compile(r"(?<=\d),(?=\d)")


# LaTeX bọc dấu thập phân trong ngoặc nhọn để canh khoảng cách: `0{,}397`. Không gỡ
# thì `0{,}397` bị đọc thành `0`, và trọng tài kết luận mâu thuẫn với `0.397` —
# BÁO OAN một lời giải đúng. Bộ test pipeline sẵn có bắt được đúng ca này.
_TEX_DECIMAL = re.compile(r"\{\s*([.,])\s*\}")
# Khoảng trắng LaTeX: `\,` `\;` `\!` `\ ` — vô nghĩa về mặt số học.
_TEX_SPACE = re.compile(r"\\[,;!:> ]")


def _normalize(s: str) -> str:
    s = s or ""
    s = _TEX_DECIMAL.sub(r"\1", s)
    s = _TEX_SPACE.sub(" ", s)
    s = _VN_DECIMAL.sub(".", s)
    return s.strip()


def expression_value(expr: str) -> float | None:
    """Tính vế phải của một BIỂU THỨC. Chặt: còn ký hiệu tự do thì trả None.

    Không được nới lỏng hàm này. Với "V = n \\times 22,4" mà lùi về "đọc con số đầu
    tiên" thì sẽ nhận 22,4 làm kết quả của bước — một con số hoàn toàn sai, rồi ghi
    đè lên lời giải. Không tính được thì phải im lặng.
    """
    e = _normalize(expr)
    if not e:
        return None
    # Chỉ lấy vế phải của dấu `=` cuối: "n = m/M = 5.6/56" -> "5.6/56"
    if "=" in e:
        e = e.rsplit("=", 1)[1].strip()
    if not e:
        return None
    try:
        parsed = sympy_tool.parse(e)
        if getattr(parsed, "free_symbols", set()):
            return None  # còn ký hiệu -> không phải phép tính số học thuần
        val = float(parsed.evalf())
        return None if math.isnan(val) or math.isinf(val) else val
    except Exception:  # noqa: BLE001
        return None


def stated_value(text: str) -> float | None:
    """Đọc con số mà model TUYÊN BỐ. Lỏng hơn: `result_latex` và `final_answer`
    hầu như luôn kèm đơn vị ("2,24 lít", "0,1 mol"), và sympy sẽ coi đơn vị là ký
    hiệu tự do. Ở đây con số dẫn đầu chính là thứ ta cần, nên lấy thẳng nó.

    An toàn vì hàm này chỉ đọc thứ model KHẲNG ĐỊNH, không dùng để tính ra kết quả.
    """
    e = _normalize(text)
    if not e:
        return None
    if "=" in e:
        e = e.rsplit("=", 1)[1].strip()
    exact = expression_value(e)
    if exact is not None:
        return exact
    m = _LEADING_NUM.search(e)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def _differs(a: float, b: float) -> bool:
    return not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-9)


def _format(v: float) -> str:
    """Viết lại số theo lối Việt Nam, bỏ đuôi 0 thừa."""
    s = f"{v:.6g}"
    if "e" not in s and "E" not in s and "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


# ---------------------------------------------------------------------------
# Kiểm và sửa
# ---------------------------------------------------------------------------


def audit_step(step: SolutionStep) -> dict[str, Any] | None:
    """Đối chiếu kết quả model ghi với kết quả SymPy tính. None = không kết luận được."""
    computed = expression_value(step.expression_latex)
    if computed is None:
        return None
    stated = stated_value(step.result_latex)
    if stated is None:
        return None
    if not _differs(computed, stated):
        return None
    return {
        "step_id": step.id,
        "expression": step.expression_latex,
        "stated": stated,
        "computed": computed,
        "rel_error": abs(computed - stated) / max(abs(computed), 1e-12),
    }


def enforce(sol: Solution) -> list[dict[str, Any]]:
    """Ghi ĐÈ kết quả sai của từng bước bằng kết quả SymPy tính.

    Trả danh sách các lần sửa, để Verifier và giao diện nói được là đã sửa gì —
    sửa im lặng thì người dùng mất khả năng đối chiếu.
    """
    fixes: list[dict[str, Any]] = []
    for step in sol.steps:
        bad = audit_step(step)
        if bad is None:
            continue
        old = step.result_latex
        step.result_latex = _format(bad["computed"])
        # Giữ lại phần đơn vị nếu bản cũ có: "1,12 lít" -> "2,24 lít"
        unit = re.sub(_LEADING_NUM, "", _normalize(old), count=1).strip()
        if unit and len(unit) <= 20:
            step.result_latex = f"{step.result_latex} {unit}"
        bad["old_result"] = old
        bad["new_result"] = step.result_latex
        fixes.append(bad)
    return fixes


def check_solution(sol: Solution) -> list[VerdictItem]:
    """Kiểm tra TẤT ĐỊNH cho Verifier tầng T1. Không sửa gì, chỉ báo cáo.

    Hai loại kiểm:
      (a) từng bước: kết quả ghi có khớp phép tính không
      (b) toàn cục: `final_answer` có khớp kết quả của bước CUỐI không
    """
    items: list[VerdictItem] = []

    for step in sol.steps:
        bad = audit_step(step)
        if bad is None:
            continue
        items.append(
            VerdictItem(
                step_id=step.id, check_type="substitution", passed=False,
                detail_vi=(
                    f"SAI SỐ HỌC: biểu thức {step.expression_latex} cho "
                    f"{_format(bad['computed'])}, nhưng bước ghi "
                    f"{_format(bad['stated'])}."
                ),
            )
        )

    # (b) Lời giải tự mâu thuẫn: các bước dẫn tới một số, đáp số lại là số khác.
    # Đây là kiểu hỏng TỆ NHẤT với sản phẩm giáo dục — học sinh làm theo từng bước
    # sẽ ra kết quả khác đáp án. Đã xảy ra thật: bài Fe + HCl có bước 3 cho
    # n(H₂) = 0,05 mol trong khi đáp số 2,24 lít ứng với 0,1 mol.
    if sol.steps:
        last = stated_value(sol.steps[-1].result_latex)
        final = stated_value(sol.final_answer_latex or sol.final_answer)
        if last is not None and final is not None and _differs(last, final):
            items.append(
                VerdictItem(
                    step_id=sol.steps[-1].id, check_type="substitution", passed=False,
                    detail_vi=(
                        f"LỜI GIẢI TỰ MÂU THUẪN: bước cuối cho {_format(last)}, "
                        f"nhưng đáp số ghi {_format(final)}. Học sinh làm theo các "
                        f"bước sẽ ra kết quả khác đáp án."
                    ),
                )
            )

    if not items:
        items.append(
            VerdictItem(
                check_type="symbolic", passed=True,
                detail_vi="SymPy tính lại các bước: không thấy sai lệch số học.",
            )
        )
    return items
