"""So khớp đáp án — dùng CHUNG cho Verifier (lúc chạy) và bộ eval (lúc chấm).

Vì sao phải dùng chung: ban đầu chỉ bộ eval có logic này, còn Verifier tự so chuỗi
bằng `.split()[0]`. Hậu quả đo được: Solver trả "Khối lượng muối tạo thành là 8,2 g",
Verifier độc lập trả "8,2 gam" — hai đáp án GIỐNG NHAU nhưng bị coi là bất đồng.
Trên tập 30 bài, lỗi này gây 20/30 FAIL giả, kéo theo 22 vòng repair thừa và đẩy
độ trễ trung vị từ ~40 s lên ~100 s.

Bài học: hai chỗ cùng trả lời câu hỏi "hai đáp án này có bằng nhau không" thì phải
là cùng một đoạn mã. Hai cài đặt độc lập sẽ lệch nhau, và chỗ lệch nằm im cho tới
khi nó phá hỏng số liệu.
"""

from __future__ import annotations

import math
import re

_UNIT_WORDS = (
    r"(m/s2|m/s\^2|rad/s|g/mol|km/h|m/s|mm|cm|km|nm|µm|μm|kg|mol|lít|lit|ml|"
    r"ohm|Ω|Hz|MeV|eV|gam|giây|ngày|s|m|g|L|N|J|W|V|A|F|H|C|K|%)"
)

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")

# Cụm dẫn tiếng Việt mà model hay thêm vào trước đáp số.
_LEAD = re.compile(
    r"^.*?(?:là|bằng|thu được|kết quả|đáp án|đáp số|vậy|do đó|suy ra)\s*:?\s*",
    re.IGNORECASE,
)


def normalize_answer(s: str | None) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    s = s.replace("×10^", "e").replace("×10", "e").replace("·10", "e").replace("x10", "e")
    s = re.sub(r"\s*\^\s*", "^", s)
    s = s.translate(_SUPERSCRIPTS)
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)          # dấu phẩy thập phân kiểu Việt Nam
    s = s.replace("−", "-").replace("–", "-")
    return " ".join(s.split())


def strip_prose(s: str) -> str:
    """Bóc đáp số ra khỏi câu văn.

    'Khối lượng muối thu được là 8,2 gam' -> '8.2 gam'
    Cần thiết vì prompt không ép được model trả lời cụt lủn một cách đáng tin.
    """
    s = normalize_answer(s)
    if not s:
        return ""
    stripped = _LEAD.sub("", s).strip()
    # Chỉ chấp nhận nếu phần còn lại vẫn có số — nếu không, cụm dẫn chính là đáp án
    # (ví dụ đáp án chữ như "mọi m").
    return stripped if re.search(r"\d", stripped) else s


def _clean(s: str) -> str:
    s = strip_prose(s)
    s = re.sub(r"^[a-zà-ỹ_]{1,3}\s*=\s*", "", s)   # 'x = 8' -> '8', 'y = 2' -> '2'
    return re.sub(_UNIT_WORDS + r"\b", " ", s).strip()


def symbolic_value(s: str) -> float | None:
    """Đánh giá đáp án như BIỂU THỨC. Cần cho `e - 1`, `1/6`, `3 + sqrt(5)`, `π/4`."""
    c = _clean(s)
    if not c:
        return None
    c = re.sub(r"(?<![0-9a-z.])e(?![0-9a-z])", "E", c)   # 'e' đứng riêng = số Euler
    c = c.replace("π", "pi").replace("√", "sqrt")
    try:
        from ..tools import sympy_tool  # noqa: PLC0415

        v = sympy_tool.evaluate(c)
        if v.get("ok") and v.get("numeric") is not None:
            return float(v["numeric"])
    except Exception:  # noqa: BLE001
        pass
    return None


def extract_number(s: str) -> float | None:
    v = symbolic_value(s)
    if v is not None:
        return v
    c = _clean(s)
    m = re.search(r"-?\d+\.?\d*\s*e\s*-?\d+", c)
    if m:
        try:
            return float(m.group().replace(" ", ""))
        except ValueError:
            pass
    m = re.search(r"-?\d+\.?\d*", c)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


def answers_match(pred: str | None, gold: str | None, rel_tol: float = 0.02) -> bool:
    """Hai đáp án có cùng nghĩa không.

    `rel_tol` mặc định 2%: bài THPT hay làm tròn (g = 10 hoặc 9,8), đòi khớp tuyệt
    đối sẽ phạt oan lời giải đúng.
    """
    p, g = normalize_answer(pred), normalize_answer(gold)
    if not p or not g:
        return False
    if p == g:
        return True

    pn, gn = extract_number(p), extract_number(g)
    if pn is not None and gn is not None:
        if gn == 0:
            return abs(pn) < 1e-9
        return abs(pn - gn) / max(abs(gn), 1e-12) <= rel_tol

    a, b = _clean(p), _clean(g)
    if a and b:
        if a == b:
            return True
        try:
            from ..tools import sympy_tool  # noqa: PLC0415

            r = sympy_tool.are_equivalent(a, b)
            return bool(r.get("ok") and r.get("equivalent"))
        except Exception:  # noqa: BLE001
            return False
    return False


def is_unit_error(pred: str | None, gold: str | None) -> bool:
    """Sai đúng một luỹ thừa 10 -> gần như chắc chắn là lỗi quy đổi đơn vị."""
    pn, gn = extract_number(pred or ""), extract_number(gold or "")
    if pn is None or gn is None or gn == 0 or pn == 0:
        return False
    ratio = abs(pn / gn)
    return any(abs(ratio - k) / k < 0.02 for k in (1e-6, 1e-3, 1e-2, 1e-1, 10, 100, 1e3, 1e6))
