"""Công cụ tính toán tượng trưng.

Triết lý xuyên suốt dự án: **LLM quyết định LÀM GÌ, SymPy quyết định KẾT QUẢ LÀ BAO NHIÊU.**
LLM sai số học liên tục nhưng chọn hướng giải khá tốt; SymPy thì ngược lại.

Hàm quan trọng nhất ở đây không phải `solve` mà là `check_substitution` — thế nghiệm
ngược vào phương trình gốc. Đó là kiểm chứng TẤT ĐỊNH, không cần token nào, và bắt
được phần lớn lỗi đại số.
"""

from __future__ import annotations

import math
import re
import signal
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,  # cho phép '^' như trong LaTeX học sinh hay viết
)

# Tên hàm/hằng tiếng Việt hoặc viết tắt mà model hay sinh ra.
_ALIASES = {
    "ln": "log",
    "lg": "log",
    "tg": "tan",
    "cotg": "cot",
    "arctg": "atan",
    "căn": "sqrt",
    "π": "pi",
    "∞": "oo",
}


# Ký hiệu tổ hợp - chỉnh hợp của sách giáo khoa Việt Nam. Chỉ nhận khi CẢ HAI
# tham số là số nguyên: `C(5,2)` là tổ hợp, còn `A(1,2)` trong bài toạ độ thì
# viết bằng dấu chấm phẩy `A(1;2)` nên không dính. Giới hạn vào số nguyên khiến
# khả năng nhận nhầm gần như bằng không.
_TO_HOP = re.compile(r"\bC\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_CHINH_HOP = re.compile(r"\bA\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def dau_phay_thap_phan(s: str) -> str:
    """Đổi dấu phẩy thập phân kiểu Việt Nam (`0,5`) thành dấu chấm (`0.5`).

    KHÔNG đụng vào dấu phẩy ngăn tham số trong lời gọi hàm.

    Vì sao cần cẩn thận đến vậy — đây là lỗi đã đo được, và nó âm thầm:

        `C(5,2)/C(8,2)`   model viết, ĐÚNG
        `C(5.2)/C(8.2)`   đổi dấu phẩy vì nó nằm giữa hai chữ số
        `C*5.2/C*8.2`     SymPy bật nhân ngầm, `C` thành ký hiệu tự do
        `((C*5.2)/C)*8.2` nhân chia cùng độ ưu tiên, tính trái sang phải
        `42.64`           chữ `C` triệt tiêu

    SymPy không hề báo lỗi, nó trả về một con số trông rất hợp lý. Trọng tài số
    học tin ngay và ghi đè lên `0.357143` — vốn là đáp án ĐÚNG của bài xác suất.

    Bản cũ tưởng đã chặn bằng cách chỉ đổi dấu phẩy nằm giữa hai chữ số, nhưng
    `C(5,2)` rơi đúng vào khuôn đó. Muốn chặn thật thì phải biết dấu phẩy đang
    nằm trong ngoặc của một lời gọi hàm hay không — tức phải duyệt có trạng thái,
    biểu thức chính quy không đủ sức.
    """
    ra: list[str] = []
    trong_ham: list[bool] = []  # ngăn xếp: ngoặc hiện tại có phải lời gọi hàm không

    for i, ch in enumerate(s):
        if ch == "(":
            j = i - 1
            while j >= 0 and s[j].isspace():
                j -= 1
            # Ngoặc đi ngay sau một CHỮ CÁI mới là lời gọi hàm. Sau chữ số thì đó
            # là phép nhân ngầm: `2(x+1)`.
            trong_ham.append(j >= 0 and (s[j].isalpha() or s[j] == "_"))
            ra.append(ch)
        elif ch == ")":
            if trong_ham:
                trong_ham.pop()
            ra.append(ch)
        elif ch == "," and trong_ham and trong_ham[-1]:
            ra.append(ch)  # dấu phẩy ngăn tham số — giữ nguyên
        elif (
            ch == ","
            and 0 < i < len(s) - 1
            and s[i - 1].isdigit()
            and s[i + 1].isdigit()
        ):
            ra.append(".")
        else:
            ra.append(ch)

    return "".join(ra)


def _preprocess(s: str) -> str:
    s = s.strip()
    # bỏ vỏ LaTeX thường gặp
    s = s.replace("\\left", "").replace("\\right", "")
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", s)
    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", s)
    s = re.sub(r"\\(cdot|times)", "*", s)
    s = s.replace("\\", "")
    s = s.replace("{", "(").replace("}", ")")
    # Dịch ký hiệu tổ hợp - chỉnh hợp TRƯỚC khi SymPy nhìn thấy. Không dịch thì
    # nhân ngầm xé `C(5,2)` ra và cho kết quả vô nghĩa. Dịch rồi thì trọng tài
    # kiểm được luôn mọi bài tổ hợp - xác suất, thay vì bỏ qua.
    s = _TO_HOP.sub(r"binomial(\1,\2)", s)
    s = _CHINH_HOP.sub(r"(factorial(\1)/factorial((\1)-(\2)))", s)
    for k, v in _ALIASES.items():
        s = re.sub(rf"\b{re.escape(k)}\b", v, s)
    return s


def parse(expr: str) -> sp.Expr:
    """Parse biểu thức, chịu được LaTeX bẩn mà model hay sinh."""
    return parse_expr(_preprocess(expr), transformations=_TRANSFORMS, evaluate=True)


def _split_equation(eq: str) -> tuple[sp.Expr, sp.Expr]:
    if "=" not in eq:
        return parse(eq), sp.Integer(0)
    lhs, rhs = eq.split("=", 1)
    return parse(lhs), parse(rhs)


# ---------------------------------------------------------------------------
# Các phép toán
# ---------------------------------------------------------------------------


def solve_equation(equation: str, symbol: str = "x") -> dict[str, Any]:
    """Giải phương trình. Trả cả nghiệm dạng ký hiệu lẫn số thực."""
    try:
        lhs, rhs = _split_equation(equation)
        sym = sp.Symbol(symbol)
        sols = sp.solve(sp.Eq(lhs, rhs), sym, dict=False)
        if not isinstance(sols, list):
            sols = [sols]
        out = []
        for s in sols:
            item: dict[str, Any] = {"exact": sp.sstr(s), "latex": sp.latex(s)}
            try:
                v = complex(sp.N(s))
                item["numeric"] = v.real if abs(v.imag) < 1e-12 else None
                item["is_real"] = abs(v.imag) < 1e-12
            except Exception:
                item["numeric"] = None
                item["is_real"] = None
            out.append(item)
        return {"ok": True, "solutions": out, "count": len(out)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def check_substitution(equation: str, assignments: dict[str, float | str]) -> dict[str, Any]:
    """KIỂM CHỨNG TẤT ĐỊNH: thế giá trị vào phương trình, xem hai vế có bằng nhau.

    Đây là hàm giá trị nhất của cả module. Với bài trắc nghiệm ta còn có thể thế
    lần lượt 4 đáp án để tìm đáp án đúng mà không cần tin lời giải của LLM.
    """
    try:
        lhs, rhs = _split_equation(equation)
        subs = {sp.Symbol(k): parse(str(v)) for k, v in assignments.items()}
        diff = sp.simplify((lhs - rhs).subs(subs))
        try:
            num = complex(sp.N(diff))
            residual = abs(num)
            ok = residual < 1e-6
        except Exception:
            ok = bool(sp.simplify(diff) == 0)
            residual = 0.0 if ok else float("inf")
        return {
            "ok": True,
            "satisfied": bool(ok),
            "residual": residual,
            "detail": f"Sai số khi thế vào: {residual:.3e}",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def are_equivalent(expr_a: str, expr_b: str) -> dict[str, Any]:
    """Hai biểu thức có tương đương không. Dùng để chấm bài tự luận: học sinh viết
    `1/2` còn đáp án là `0.5`, hoặc `sqrt(2)/2` vs `1/sqrt(2)` — đều phải tính là đúng."""
    try:
        a, b = parse(expr_a), parse(expr_b)
        if sp.simplify(a - b) == 0:
            return {"ok": True, "equivalent": True, "how": "symbolic"}
        # so số học khi rút gọn tượng trưng bó tay
        try:
            va, vb = complex(sp.N(a)), complex(sp.N(b))
            close = abs(va - vb) < 1e-6 * max(1.0, abs(va))
            return {"ok": True, "equivalent": bool(close), "how": "numeric"}
        except Exception:
            return {"ok": True, "equivalent": False, "how": "failed"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def evaluate(expr: str, assignments: dict[str, float] | None = None) -> dict[str, Any]:
    try:
        e = parse(expr)
        if assignments:
            e = e.subs({sp.Symbol(k): v for k, v in assignments.items()})
        val = sp.N(e)
        try:
            f = float(val)
        except (TypeError, ValueError):
            f = None
        return {"ok": True, "exact": sp.sstr(sp.simplify(e)), "numeric": f, "latex": sp.latex(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def simplify(expr: str) -> dict[str, Any]:
    try:
        e = sp.simplify(parse(expr))
        return {"ok": True, "result": sp.sstr(e), "latex": sp.latex(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def differentiate(expr: str, symbol: str = "x", order: int = 1) -> dict[str, Any]:
    try:
        d = sp.diff(parse(expr), sp.Symbol(symbol), order)
        return {"ok": True, "result": sp.sstr(d), "latex": sp.latex(d)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def integrate(
    expr: str, symbol: str = "x", lower: str | None = None, upper: str | None = None
) -> dict[str, Any]:
    try:
        sym = sp.Symbol(symbol)
        e = parse(expr)
        if lower is not None and upper is not None:
            r = sp.integrate(e, (sym, parse(lower), parse(upper)))
        else:
            r = sp.integrate(e, sym)
        out: dict[str, Any] = {"ok": True, "result": sp.sstr(r), "latex": sp.latex(r)}
        try:
            out["numeric"] = float(sp.N(r))
        except (TypeError, ValueError):
            out["numeric"] = None
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def solve_system(equations: list[str], symbols: list[str]) -> dict[str, Any]:
    try:
        eqs = []
        for eq in equations:
            lhs, rhs = _split_equation(eq)
            eqs.append(sp.Eq(lhs, rhs))
        syms = [sp.Symbol(s) for s in symbols]
        sol = sp.solve(eqs, syms, dict=True)
        return {
            "ok": True,
            "solutions": [{sp.sstr(k): sp.sstr(v) for k, v in d.items()} for d in sol],
            "count": len(sol),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def compare_numeric(a: str, b: str, rel_tol: float = 1e-3) -> dict[str, Any]:
    """So khớp đáp số có dung sai — dùng cho chấm tự động ở bộ eval."""
    try:
        va = float(sp.N(parse(a)))
        vb = float(sp.N(parse(b)))
        ok = math.isclose(va, vb, rel_tol=rel_tol, abs_tol=1e-9)
        return {"ok": True, "match": ok, "a": va, "b": vb}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
