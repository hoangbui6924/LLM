"""Công cụ Hoá học — không phụ thuộc thư viện ngoài (chempy không hỗ trợ Python 3.13
ổn định, và một dự án 5 ngày không nên đánh cược vào đó).

Tự cài đặt hai thứ:
  1. Khối lượng mol — parser công thức có ngoặc lồng + ngậm nước (CuSO4.5H2O)
  2. Cân bằng phương trình — bài toán không gian null của ma trận nguyên tố,
     giải bằng SymPy. Đây là kiểm chứng TẤT ĐỊNH: bảo toàn nguyên tố không phải
     ý kiến, nó đúng hoặc sai.
"""

from __future__ import annotations

import re
from typing import Any

import sympy as sp

# Khối lượng nguyên tử — đủ phủ chương trình Hoá THPT.
ATOMIC_MASS: dict[str, float] = {
    "H": 1.008, "He": 4.003, "Li": 6.94, "Be": 9.012, "B": 10.81, "C": 12.011,
    "N": 14.007, "O": 15.999, "F": 18.998, "Ne": 20.180, "Na": 22.990,
    "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06,
    "Cl": 35.45, "Ar": 39.948, "K": 39.098, "Ca": 40.078, "Sc": 44.956,
    "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845,
    "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38, "Ga": 69.723,
    "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904, "Kr": 83.798,
    "Rb": 85.468, "Sr": 87.62, "Y": 88.906, "Zr": 91.224, "Nb": 92.906,
    "Mo": 95.95, "Ag": 107.868, "Cd": 112.414, "In": 114.818, "Sn": 118.710,
    "Sb": 121.760, "Te": 127.60, "I": 126.904, "Xe": 131.293, "Cs": 132.905,
    "Ba": 137.327, "La": 138.905, "W": 183.84, "Pt": 195.084, "Au": 196.967,
    "Hg": 200.592, "Tl": 204.38, "Pb": 207.2, "Bi": 208.980, "Ra": 226.0,
    "Th": 232.038, "U": 238.029,
}

_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)|(\()|(\))(\d*)")


def parse_formula(formula: str) -> dict[str, int]:
    """Đếm nguyên tố trong công thức. Hỗ trợ ngoặc lồng và muối ngậm nước.

    'Ca(OH)2'      -> {'Ca':1,'O':2,'H':2}
    'CuSO4.5H2O'   -> {'Cu':1,'S':1,'O':9,'H':10}
    'Al2(SO4)3'    -> {'Al':2,'S':3,'O':12}
    """
    formula = formula.strip().replace(" ", "")
    if not formula:
        raise ValueError("Công thức rỗng")

    # tách phần ngậm nước: 'CuSO4.5H2O' -> ['CuSO4', '5H2O']
    parts = re.split(r"[.·]", formula)
    total: dict[str, int] = {}

    for part in parts:
        if not part:
            continue
        m = re.match(r"^(\d+)(.*)$", part)
        mult, body = (int(m.group(1)), m.group(2)) if m else (1, part)
        counts = _parse_group(body)
        for el, n in counts.items():
            total[el] = total.get(el, 0) + n * mult
    return total


def _parse_group(s: str) -> dict[str, int]:
    stack: list[dict[str, int]] = [{}]
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            stack.append({})
            i += 1
        elif ch == ")":
            i += 1
            num = ""
            while i < len(s) and s[i].isdigit():
                num += s[i]
                i += 1
            mult = int(num) if num else 1
            if len(stack) < 2:
                raise ValueError(f"Ngoặc không cân trong '{s}'")
            grp = stack.pop()
            for el, n in grp.items():
                stack[-1][el] = stack[-1].get(el, 0) + n * mult
        else:
            m = re.match(r"([A-Z][a-z]?)(\d*)", s[i:])
            if not m or not m.group(1):
                raise ValueError(f"Ký tự lạ '{s[i]}' trong công thức '{s}'")
            el = m.group(1)
            if el not in ATOMIC_MASS:
                raise ValueError(f"Không biết nguyên tố '{el}'")
            n = int(m.group(2)) if m.group(2) else 1
            stack[-1][el] = stack[-1].get(el, 0) + n
            i += len(m.group(0))
    if len(stack) != 1:
        raise ValueError(f"Ngoặc không cân trong '{s}'")
    return stack[0]


def molar_mass(formula: str) -> dict[str, Any]:
    try:
        counts = parse_formula(formula)
        m = sum(ATOMIC_MASS[el] * n for el, n in counts.items())
        breakdown = " + ".join(
            f"{el}({ATOMIC_MASS[el]}×{n})" for el, n in sorted(counts.items())
        )
        return {
            "ok": True,
            "formula": formula,
            "molar_mass": round(m, 4),
            "composition": counts,
            "detail": f"M({formula}) = {breakdown} = {m:.3f} g/mol",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def balance_equation(reactants: list[str], products: list[str]) -> dict[str, Any]:
    """Cân bằng phương trình bằng không gian null của ma trận nguyên tố.

    Với mỗi nguyên tố ta có một phương trình bảo toàn. Nghiệm nguyên dương nhỏ nhất
    của hệ thuần nhất chính là bộ hệ số. Đây là cách làm tất định — không đoán.
    """
    try:
        species = list(reactants) + list(products)
        if len(species) < 2:
            return {"ok": False, "error": "Cần ít nhất 2 chất"}

        parsed = [parse_formula(s) for s in species]
        elements = sorted({el for p in parsed for el in p})

        rows = []
        for el in elements:
            row = []
            for idx, p in enumerate(parsed):
                n = p.get(el, 0)
                row.append(n if idx < len(reactants) else -n)
            rows.append(row)

        M = sp.Matrix(rows)
        ns = M.nullspace()
        if not ns:
            return {
                "ok": True,
                "balanced": False,
                "detail": "Không tìm được hệ số — phương trình có thể sai chất.",
            }
        vec = ns[0]
        denoms = [sp.Rational(x).q for x in vec]
        lcm = sp.ilcm(*denoms) if len(denoms) > 1 else denoms[0]
        coeffs = [int(sp.Rational(x) * lcm) for x in vec]

        if any(c < 0 for c in coeffs):
            coeffs = [-c for c in coeffs]
        g = sp.igcd(*coeffs) if len(coeffs) > 1 else coeffs[0]
        if g and g > 1:
            coeffs = [c // g for c in coeffs]

        if any(c <= 0 for c in coeffs):
            return {
                "ok": True,
                "balanced": False,
                "detail": "Nghiệm có hệ số không dương — phương trình không hợp lệ.",
            }

        nr = len(reactants)
        left = " + ".join(
            f"{c if c > 1 else ''}{s}" for c, s in zip(coeffs[:nr], reactants)
        )
        right = " + ".join(
            f"{c if c > 1 else ''}{s}" for c, s in zip(coeffs[nr:], products)
        )
        return {
            "ok": True,
            "balanced": True,
            "coefficients": coeffs,
            "reactant_coeffs": coeffs[:nr],
            "product_coeffs": coeffs[nr:],
            "equation": f"{left} → {right}",
            "detail": f"Cân bằng: {left} → {right}",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def check_conservation(
    reactants: list[tuple[str, int]], products: list[tuple[str, int]]
) -> dict[str, Any]:
    """KIỂM CHỨNG TẤT ĐỊNH cho Verifier: một phương trình đã ghi hệ số có bảo toàn
    nguyên tố không. Không cần LLM, không sai bao giờ."""
    try:
        left: dict[str, int] = {}
        right: dict[str, int] = {}
        for f, c in reactants:
            for el, n in parse_formula(f).items():
                left[el] = left.get(el, 0) + n * c
        for f, c in products:
            for el, n in parse_formula(f).items():
                right[el] = right.get(el, 0) + n * c

        mismatches = []
        for el in sorted(set(left) | set(right)):
            a, b = left.get(el, 0), right.get(el, 0)
            if a != b:
                mismatches.append(f"{el}: vế trái {a} ≠ vế phải {b}")

        return {
            "ok": True,
            "conserved": not mismatches,
            "left": left,
            "right": right,
            "detail": (
                "Bảo toàn nguyên tố ✓"
                if not mismatches
                else "VI PHẠM BẢO TOÀN NGUYÊN TỐ: " + "; ".join(mismatches)
            ),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def moles(mass_g: float | None = None, formula: str | None = None,
          volume_l: float | None = None, molarity: float | None = None,
          volume_stp_l: float | None = None) -> dict[str, Any]:
    """Tính số mol theo 3 đường: khối lượng, dung dịch, khí ở đktc."""
    try:
        if mass_g is not None and formula:
            mm = molar_mass(formula)
            if not mm["ok"]:
                return mm
            n = mass_g / mm["molar_mass"]
            return {"ok": True, "moles": n,
                    "detail": f"n = m/M = {mass_g}/{mm['molar_mass']:.3f} = {n:.5f} mol"}
        if volume_l is not None and molarity is not None:
            n = volume_l * molarity
            return {"ok": True, "moles": n,
                    "detail": f"n = C·V = {molarity}×{volume_l} = {n:.5f} mol"}
        if volume_stp_l is not None:
            n = volume_stp_l / 22.4
            return {"ok": True, "moles": n,
                    "detail": f"n = V/22,4 = {volume_stp_l}/22,4 = {n:.5f} mol (đktc)"}
        return {"ok": False, "error": "Thiếu dữ kiện để tính mol"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
