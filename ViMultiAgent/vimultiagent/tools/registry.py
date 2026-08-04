"""Sổ đăng ký công cụ — nơi duy nhất tác tử gọi tool.

Có chủ đích KHÔNG dùng exec() mã do LLM sinh trong đường chạy chính. Tất cả tool
đều là hàm có chữ ký cố định, tham số validate được. Đánh đổi: kém linh hoạt hơn
Program-of-Thought tự do. Đổi lại: không có lỗ hổng thực thi mã, không có lỗi cú
pháp lúc chạy, và mỗi lượt gọi tool đều ghi được vào trace để phân tích.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..core.schemas import ToolCall
from . import chem_tool, sympy_tool, units_tool

# tên tool -> (hàm, mô tả cho LLM)
TOOLS: dict[str, tuple[Callable[..., dict[str, Any]], str]] = {
    # --- Toán ---
    "solve_equation": (
        sympy_tool.solve_equation,
        "Giải phương trình. args: {equation: str, symbol: str='x'}",
    ),
    "solve_system": (
        sympy_tool.solve_system,
        "Giải hệ phương trình. args: {equations: list[str], symbols: list[str]}",
    ),
    "simplify": (sympy_tool.simplify, "Rút gọn biểu thức. args: {expr: str}"),
    "evaluate": (
        sympy_tool.evaluate,
        "Tính giá trị số. args: {expr: str, assignments: dict[str,float]=None}",
    ),
    "differentiate": (
        sympy_tool.differentiate,
        "Đạo hàm. args: {expr: str, symbol: str='x', order: int=1}",
    ),
    "integrate": (
        sympy_tool.integrate,
        "Nguyên hàm/tích phân. args: {expr, symbol='x', lower=None, upper=None}",
    ),
    "check_substitution": (
        sympy_tool.check_substitution,
        "KIỂM CHỨNG: thế nghiệm vào phương trình. args: {equation: str, assignments: dict}",
    ),
    "are_equivalent": (
        sympy_tool.are_equivalent,
        "Hai biểu thức có tương đương không. args: {expr_a: str, expr_b: str}",
    ),
    # --- Vật lý ---
    "check_dimension": (
        units_tool.check_dimension,
        "KIỂM CHỨNG thứ nguyên. args: {value_with_unit: str, expected_unit: str}",
    ),
    "convert_unit": (
        units_tool.convert,
        "Đổi đơn vị. args: {value: float, from_unit: str, to_unit: str}",
    ),
    "check_formula_dimensions": (
        units_tool.check_formula_dimensions,
        "Tính biểu thức có đơn vị + kiểm thứ nguyên. args: {expression: str, expected_unit: str}",
    ),
    # --- Hoá học ---
    "molar_mass": (chem_tool.molar_mass, "Khối lượng mol. args: {formula: str}"),
    "balance_equation": (
        chem_tool.balance_equation,
        "Cân bằng phương trình. args: {reactants: list[str], products: list[str]}",
    ),
    "check_conservation": (
        chem_tool.check_conservation,
        "KIỂM CHỨNG bảo toàn nguyên tố. args: {reactants: list[[formula,coef]], products: ...}",
    ),
    "moles": (
        chem_tool.moles,
        "Tính mol. args: {mass_g, formula} | {volume_l, molarity} | {volume_stp_l}",
    ),
}

# Tool nào phù hợp với miền nào — giữ cho prompt ngắn và sắc, không nhồi 15 tool
# vào system prompt của bài Hoá.
DOMAIN_TOOLS: dict[str, list[str]] = {
    "math": [
        "solve_equation", "solve_system", "simplify", "evaluate",
        "differentiate", "integrate", "check_substitution", "are_equivalent",
    ],
    "physics": [
        "solve_equation", "solve_system", "evaluate", "simplify",
        "check_dimension", "convert_unit", "check_formula_dimensions",
    ],
    "chemistry": [
        "molar_mass", "balance_equation", "check_conservation", "moles",
        "solve_equation", "solve_system", "evaluate",
    ],
}


# Khoá kết quả mang ý nghĩa "KIỂM CHỨNG ĐẠT / KHÔNG ĐẠT".
# Verifier T1 chỉ cần đọc mấy cờ này là kết luận được, không cần LLM.
VERIFY_FLAGS = (
    "satisfied",    # check_substitution — thế nghiệm có thoả không
    "conserved",    # check_conservation — bảo toàn nguyên tố
    "compatible",   # check_dimension    — đúng thứ nguyên
    "equivalent",   # are_equivalent     — hai biểu thức tương đương
    "balanced",     # balance_equation   — cân bằng được
    "match",        # compare_numeric
)


def tools_prompt(domain: str) -> str:
    """Mô tả tool để nhét vào system prompt của Solver."""
    names = DOMAIN_TOOLS.get(domain, list(TOOLS))
    return "\n".join(f"- {n}: {TOOLS[n][1]}" for n in names if n in TOOLS)


def run_tool(name: str, args: dict[str, Any]) -> ToolCall:
    """Chạy một tool, luôn trả ToolCall (không bao giờ ném exception ra ngoài —
    tác tử phải thấy được lỗi để tự sửa, chứ không phải làm sập cả pipeline)."""
    t0 = time.time()
    if name not in TOOLS:
        return ToolCall(
            tool=name, args=args, ok=False,
            error=f"Không có tool '{name}'. Các tool hợp lệ: {', '.join(TOOLS)}",
            duration_ms=0.0,
        )
    fn = TOOLS[name][0]
    try:
        res = fn(**args)
        ok = bool(res.get("ok", True))
        detail = res.get("detail") or res.get("error") or ""
        summary = detail if detail else str({k: v for k, v in res.items() if k != "ok"})
        return ToolCall(
            tool=name, args=args, ok=ok,
            result=summary[:1500],
            error=None if ok else res.get("error"),
            duration_ms=(time.time() - t0) * 1000.0,
            flags={k: res[k] for k in VERIFY_FLAGS if k in res},
        )
    except TypeError as e:
        return ToolCall(
            tool=name, args=args, ok=False,
            error=f"Sai tham số cho '{name}': {e}. Kỳ vọng: {TOOLS[name][1]}",
            duration_ms=(time.time() - t0) * 1000.0,
        )
    except Exception as e:  # noqa: BLE001
        return ToolCall(
            tool=name, args=args, ok=False,
            error=f"{type(e).__name__}: {e}",
            duration_ms=(time.time() - t0) * 1000.0,
        )


def run_tools(calls: list[dict[str, Any]]) -> list[ToolCall]:
    out: list[ToolCall] = []
    for c in calls:
        name = c.get("tool") or c.get("name") or ""
        args = c.get("args") or {}
        out.append(run_tool(name, args))
    return out
