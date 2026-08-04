"""Kiểm tra đơn vị & thứ nguyên cho Vật lý (Pint).

Vì sao đáng có riêng một module: sai đơn vị là lỗi phổ biến nhất của bài Vật lý
THPT (cm vs m, mA vs A, ms vs s), và nó bắt được **tất định** — không cần LLM,
không tốn token, không bao giờ sai. Mỗi lỗi bắt được ở đây là một lượt gọi LLM
verifier tiết kiệm được.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any

try:
    import pint

    _PINT_OK = True
except ImportError:  # pragma: no cover
    _PINT_OK = False


@lru_cache(maxsize=1)
def _ureg() -> Any:
    ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
    try:
        ureg.formatter.default_format = "~P"      # pint >= 0.24
    except AttributeError:                        # pragma: no cover
        ureg.default_format = "~P"
    return ureg


# Ký hiệu đơn vị tiếng Việt / SGK -> ký hiệu Pint hiểu được.
_UNIT_ALIASES = {
    "ohm": "ohm",
    "Ω": "ohm",
    "độ": "degree",
    "rad/s": "radian/second",
    "vòng/s": "turn/second",
    "vòng/phút": "turn/minute",
    "lít": "liter",
    "l": "liter",
    "gam": "gram",
    "g": "gram",
    "kg": "kilogram",
    "s": "second",
    "giây": "second",
    "phút": "minute",
    "giờ": "hour",
    "N": "newton",
    "J": "joule",
    "W": "watt",
    "V": "volt",
    "A": "ampere",
    "F": "farad",
    "H": "henry",
    "Hz": "hertz",
    "Pa": "pascal",
    "eV": "electron_volt",
    "MeV": "megaelectron_volt",
    "u": "atomic_mass_constant",
}


def normalize_unit(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if u in _UNIT_ALIASES:
        return _UNIT_ALIASES[u]
    # thay thế từng token
    def repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        return _UNIT_ALIASES.get(tok, tok)

    return re.sub(r"[A-Za-zΩ_]+", repl, u)


def available() -> bool:
    return _PINT_OK


def check_dimension(value_with_unit: str, expected_unit: str) -> dict[str, Any]:
    """Đại lượng có đúng thứ nguyên mong đợi không.

    Ví dụ: check_dimension("20 m/s", "km/h") -> compatible=True (chỉ khác hệ số)
           check_dimension("20 m/s", "N")    -> compatible=False (SAI THỨ NGUYÊN)
    """
    if not _PINT_OK:
        return {"ok": False, "error": "Chưa cài pint"}
    try:
        ureg = _ureg()
        q = ureg.Quantity(normalize_unit(value_with_unit))
        target = ureg.Unit(normalize_unit(expected_unit))
        compatible = q.dimensionality == target.dimensionality
        out: dict[str, Any] = {
            "ok": True,
            "compatible": bool(compatible),
            "dimensionality": str(q.dimensionality),
            "expected_dimensionality": str(target.dimensionality),
        }
        if compatible:
            conv = q.to(target)
            out["converted"] = f"{conv.magnitude:.6g} {conv.units}"
            out["magnitude"] = float(conv.magnitude)
            out["detail"] = f"Đúng thứ nguyên. {q} = {conv}"
        else:
            out["detail"] = (
                f"SAI THỨ NGUYÊN: '{value_with_unit}' có thứ nguyên {q.dimensionality}, "
                f"nhưng '{expected_unit}' cần {target.dimensionality}."
            )
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def convert(value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    if not _PINT_OK:
        return {"ok": False, "error": "Chưa cài pint"}
    try:
        ureg = _ureg()
        q = value * ureg.Unit(normalize_unit(from_unit))
        c = q.to(normalize_unit(to_unit))
        return {
            "ok": True,
            "value": float(c.magnitude),
            "unit": str(c.units),
            "detail": f"{q} = {c}",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _desugar_math(s: str) -> str:
    """Pint chỉ hiểu số học thuần: `sqrt` và `pi` với nó là 'đơn vị lạ'.

    Công thức Vật lý THPT đầy `2π√(m/k)`, nên phải khử đường trước khi đưa vào Pint:
    sqrt(X) -> (X)**0.5, pi -> giá trị số.
    """
    s = re.sub(r"\b(pi|π)\b", repr(math.pi), s)

    # sqrt(...) -> (...)**0.5, quét ngoặc cân bằng để chịu được lồng nhau
    while True:
        m = re.search(r"\bsqrt\s*\(", s)
        if not m:
            break
        start = m.end() - 1           # vị trí '('
        depth = 0
        end = -1
        for i in range(start, len(s)):
            if s[i] == "(":
                depth += 1
            elif s[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            break                      # ngoặc không cân — để Pint tự báo lỗi
        s = s[: m.start()] + "(" + s[start + 1 : end] + ")**0.5" + s[end + 1 :]
    return s


# Ký hiệu vật lý một chữ cái trùng tên đơn vị SI. Đây là nguồn nhầm lẫn nguy hiểm:
# Pint đọc 'm' thành mét, 'K' thành kelvin, 'A' thành ampe — nên biểu thức ký hiệu
# như "2*pi*sqrt(m/k)" sẽ được "phân tích thành công" nhưng ra thứ nguyên vô nghĩa.
_AMBIGUOUS = set("mkKAaCFHNTVWJLRsSgtGP")


def _has_free_symbols(expr: str) -> bool:
    """Biểu thức còn ký hiệu chưa thay số (nên không kiểm thứ nguyên được)?

    Quy ước của vật lý: đơn vị luôn gắn với một con số — "0,4 kg", "100 N/m".
    Nên chỉ cần hỏi: có chỗ nào là <số> ngay trước <đơn vị> không?

      "0.4 kilogram / (100 newton/m)"  -> có "0.4 kilogram"  -> kiểm được
      "2*sqrt(m/k)"                    -> không có           -> KHÔNG kiểm được

    Cố gắng soi từng token thì hỏng ở đơn vị ghép: chữ 'm' trong "N/m" đứng sau
    dấu '/', không đứng sau số, nhưng nó vẫn là đơn vị hợp lệ.
    """
    cleaned = re.sub(r"\b(pi|sqrt|exp|log|ln|sin|cos|tan|abs)\b", " ", expr)
    return re.search(r"\d\s*\*?\s*[A-Za-zΩ]", cleaned) is None


def check_formula_dimensions(expression: str, expected_unit: str) -> dict[str, Any]:
    """Đánh giá một biểu thức có kèm đơn vị rồi so thứ nguyên.

    Ví dụ: check_formula_dimensions("2*pi*sqrt(0.4 kg / (100 N/m))", "s")

    Trả `applicable: False` khi biểu thức còn ký hiệu chưa thay số. Điều này quan
    trọng hơn vẻ ngoài: Verifier tầng T1 có quyền bác bỏ sớm mà không hỏi LLM, nên
    một kiểm tra KHÔNG áp dụng được mà lại báo FAIL sẽ huỷ oan lời giải đúng và kéo
    theo một vòng repair vô ích.
    """
    if not _PINT_OK:
        return {"ok": False, "error": "Chưa cài pint"}
    expr_n = _desugar_math(normalize_unit(expression))
    if _has_free_symbols(expr_n):
        return {
            "ok": True, "applicable": False,
            "detail": f"Bỏ qua kiểm thứ nguyên: '{expression}' còn ký hiệu chưa thay số. "
                      f"Hãy gọi lại với giá trị kèm đơn vị, ví dụ '0.4 kg / (100 N/m)'.",
        }
    try:
        ureg = _ureg()
        q = ureg.parse_expression(expr_n)
        target = ureg.Unit(normalize_unit(expected_unit))
        compatible = q.dimensionality == target.dimensionality
        res: dict[str, Any] = {"ok": True, "compatible": bool(compatible)}
        if compatible:
            c = q.to(target)
            res["value"] = float(c.magnitude)
            res["detail"] = f"{expression} = {c}"
        else:
            res["detail"] = (
                f"SAI THỨ NGUYÊN: biểu thức cho {q.dimensionality}, cần {target.dimensionality}"
            )
        return res
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# Thứ nguyên chuẩn của các đại lượng Vật lý THPT — dùng để Verifier tự tra
# mà không cần hỏi LLM "vận tốc có đơn vị gì".
STANDARD_UNITS: dict[str, str] = {
    "quãng đường": "m", "vận tốc": "m/s", "gia tốc": "m/s^2",
    "khối lượng": "kg", "lực": "N", "công": "J", "năng lượng": "J",
    "công suất": "W", "áp suất": "Pa", "chu kỳ": "s", "tần số": "Hz",
    "tần số góc": "rad/s", "biên độ": "m", "bước sóng": "m",
    "điện tích": "C", "cường độ dòng điện": "A", "hiệu điện thế": "V",
    "điện trở": "ohm", "điện dung": "F", "độ tự cảm": "H",
    "cảm kháng": "ohm", "dung kháng": "ohm", "tổng trở": "ohm",
    "độ cứng": "N/m", "momen lực": "N*m", "động lượng": "kg*m/s",
}


def expected_unit_for(quantity_name_vi: str) -> str | None:
    key = quantity_name_vi.strip().lower()
    for k, v in STANDARD_UNITS.items():
        if k in key:
            return v
    return None
