"""Test hồi quy cho tool layer.

Đây là những kiểm chứng TẤT ĐỊNH mà cả hệ thống dựa vào. Nếu chúng sai thì Verifier
tầng T1 sai, và tầng T1 lại là tầng có quyền bác bỏ sớm không cần hỏi LLM — sai ở đây
lan ra toàn hệ thống mà không có gì chặn lại.

    pytest tests/ -v
"""

from __future__ import annotations

import pytest

from vimultiagent.tools import chem_tool, sympy_tool, units_tool
from vimultiagent.tools.registry import run_tool


# ---------------------------------------------------------------------------
# SymPy
# ---------------------------------------------------------------------------


def test_solve_quadratic():
    r = sympy_tool.solve_equation("x^2 - 5*x + 6 = 0", "x")
    assert r["ok"] and r["count"] == 2
    assert {s["exact"] for s in r["solutions"]} == {"2", "3"}


@pytest.mark.parametrize("x,expected", [(2, True), (3, True), (5, False), (0, False)])
def test_substitution_check(x, expected):
    r = sympy_tool.check_substitution("x^2 - 5*x + 6 = 0", {"x": x})
    assert r["ok"] and r["satisfied"] is expected


def test_equivalence_handles_different_forms():
    # Học sinh viết sqrt(2)/2, đáp án ghi 1/sqrt(2) — phải tính là đúng
    assert sympy_tool.are_equivalent("sqrt(2)/2", "1/sqrt(2)")["equivalent"]
    assert sympy_tool.are_equivalent("1/2", "0.5")["equivalent"]
    assert not sympy_tool.are_equivalent("1/2", "1/3")["equivalent"]


def test_definite_integral():
    r = sympy_tool.integrate("x^2 + 2*x", "x", "0", "3")
    assert r["ok"] and abs(r["numeric"] - 18.0) < 1e-9


def test_parses_latex_junk():
    """Model sinh LaTeX bẩn là chuyện thường — parser phải chịu được."""
    r = sympy_tool.evaluate(r"\frac{1}{2} + \frac{1}{2}")
    assert r["ok"] and abs(r["numeric"] - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Pint — kiểm thứ nguyên
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not units_tool.available(), reason="chưa cài pint")
def test_dimension_compatible():
    r = units_tool.check_dimension("20 m/s", "km/h")
    assert r["ok"] and r["compatible"] and abs(r["magnitude"] - 72.0) < 1e-6


@pytest.mark.skipif(not units_tool.available(), reason="chưa cài pint")
def test_dimension_mismatch_detected():
    r = units_tool.check_dimension("20 m/s", "N")
    assert r["ok"] and not r["compatible"]


@pytest.mark.skipif(not units_tool.available(), reason="chưa cài pint")
def test_pendulum_formula_dimensions():
    """T = 2π√(m/k) phải ra giây; quên căn thì ra giây² và phải bị bắt."""
    ok = units_tool.check_formula_dimensions("2*pi*sqrt(0.4 kg / (100 N/m))", "s")
    assert ok["compatible"] and abs(ok["value"] - 0.3974) < 1e-3

    bad = units_tool.check_formula_dimensions("2*pi*(0.4 kg / (100 N/m))", "s")
    assert not bad["compatible"]


def test_symbolic_formula_is_skipped_not_failed():
    """Biểu thức còn ký hiệu (chưa thay số) phải trả `applicable: False`.

    Đây là hồi quy cho một lỗi thật: Pint đọc 'm' thành mét và 'k' thành kelvin,
    nên "2*pi*sqrt(m/k)" được phân tích "thành công" ra thứ nguyên vô nghĩa và
    Verifier huỷ oan một lời giải ĐÚNG.
    """
    r = units_tool.check_formula_dimensions("2*pi*sqrt(m/k)", "s")
    assert r["ok"] and r.get("applicable") is False
    assert "compatible" not in r, "không được báo sai thứ nguyên khi chưa kiểm được"


# ---------------------------------------------------------------------------
# Hoá học
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "formula,mass",
    [("H2SO4", 98.072), ("CaCO3", 100.087), ("Al2(SO4)3", 342.132),
     ("CuSO4.5H2O", 249.677), ("C6H12O6", 180.156)],
)
def test_molar_mass(formula, mass):
    r = chem_tool.molar_mass(formula)
    assert r["ok"] and abs(r["molar_mass"] - mass) < 0.01


def test_parse_nested_parentheses():
    assert chem_tool.parse_formula("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2}
    assert chem_tool.parse_formula("CuSO4.5H2O") == {"Cu": 1, "S": 1, "O": 9, "H": 10}


def test_balance_simple():
    r = chem_tool.balance_equation(["Fe", "O2"], ["Fe2O3"])
    assert r["ok"] and r["balanced"] and r["coefficients"] == [4, 3, 2]


def test_balance_redox():
    r = chem_tool.balance_equation(
        ["KMnO4", "HCl"], ["KCl", "MnCl2", "Cl2", "H2O"]
    )
    assert r["ok"] and r["balanced"] and r["coefficients"] == [2, 16, 2, 2, 5, 8]


def test_conservation_catches_violation():
    good = chem_tool.check_conservation([("Fe", 4), ("O2", 3)], [("Fe2O3", 2)])
    assert good["conserved"]

    bad = chem_tool.check_conservation([("Fe", 4), ("O2", 2)], [("Fe2O3", 2)])
    assert not bad["conserved"] and "O" in bad["detail"]


def test_moles_from_mass():
    r = chem_tool.moles(mass_g=9.8, formula="H2SO4")
    assert r["ok"] and abs(r["moles"] - 0.09993) < 1e-4


# ---------------------------------------------------------------------------
# Registry — không bao giờ được ném exception ra ngoài
# ---------------------------------------------------------------------------


def test_registry_unknown_tool_returns_error_not_raise():
    tc = run_tool("khong_ton_tai", {})
    assert not tc.ok and "Không có tool" in (tc.error or "")


def test_registry_bad_args_returns_error_not_raise():
    tc = run_tool("molar_mass", {"sai_tham_so": "X"})
    assert not tc.ok and tc.error


def test_registry_extracts_verification_flags():
    """Verifier T1 đọc `flags` chứ không parse chuỗi — flag phải được bóc ra."""
    tc = run_tool("check_substitution", {"equation": "x^2 - 4 = 0", "assignments": {"x": 2}})
    assert tc.ok and tc.flags.get("satisfied") is True

    tc2 = run_tool("check_conservation",
                   {"reactants": [("Fe", 1)], "products": [("Fe2O3", 1)]})
    assert tc2.flags.get("conserved") is False
