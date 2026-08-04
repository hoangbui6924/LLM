"""Hai lớp hỏng của LaTeX do LLM sinh, cả hai đều quan sát được trên màn hình thật.

Lớp 1 — escape KHÔNG hợp lệ với JSON (`\\[`, `\\alpha`): `json.loads` ném lỗi và bỏ cả
lượt, kéo theo 3 lần thử lại của `chat_json`.
Lớp 2 — escape HỢP LỆ với JSON nhưng sai ý định (`\\times` -> TAB + "imes"): parse
trót lọt, hỏng âm thầm, công thức hiện nguyên văn màu đỏ trên giao diện.
"""

from __future__ import annotations

from vimultiagent.core.latex import clean_latex, clean_prose
from vimultiagent.core.llm import extract_json


# --- Lớp 1: escape không hợp lệ, phải parse được thay vì ném lỗi ------------


def test_extract_json_vá_được_escape_latex_hỏng() -> None:
    raw = '{"latex": "\\[x^2\\]", "a": "\\alpha + \\sqrt{2}"}'
    out = extract_json(raw)
    assert out["latex"] == r"\[x^2\]"
    assert out["a"] == r"\alpha + \sqrt{2}"


def test_extract_json_vá_được_khi_có_lời_dẫn_bao_quanh() -> None:
    raw = 'Đây là kết quả:\n{"latex": "\\alpha \\cdot \\gamma"}\nHết.'
    assert extract_json(raw)["latex"] == r"\alpha \cdot \gamma"


def test_ranh_giới_hai_lớp_hỏng() -> None:
    r"""`\b` LÀ escape hợp lệ của JSON, nên `\beta` không thuộc lớp 1: nó parse trót
    lọt thành backspace + "eta". Đây chính là kiểu hỏng âm thầm nguy hiểm hơn — và
    nó phải được lớp 2 (`clean_latex`) dọn. Test này khoá lại sự phối hợp của hai lớp.
    """
    parsed = extract_json('{"latex": "\\beta + 1"}')["latex"]
    assert parsed == "\x08eta + 1"          # lớp 1 không đụng vào, đúng như thiết kế
    assert clean_latex(parsed) == r"\beta + 1"  # lớp 2 khôi phục


def test_json_đúng_chuẩn_không_bị_đụng_vào() -> None:
    raw = r'{"ok": "đã escape đúng: \\frac", "n": 1, "s": "dòng\nmới"}'
    out = extract_json(raw)
    assert out["ok"] == r"đã escape đúng: \frac"
    assert out["s"] == "dòng\nmới"
    assert out["n"] == 1


# --- Lớp 2: escape hợp lệ nhưng sai ý định, phải dọn được -------------------


def test_khôi_phục_dấu_gạch_chéo_bị_json_nuốt() -> None:
    # Đúng chuỗi đã hiện trên màn hình: "$V = n imes V_{đktc}$"
    assert clean_latex("$V = n \times V_{đktc}$") == r"V = n \times V_{đktc}"
    assert clean_latex("$n(Fe) = \x0crac{m}{M}$") == r"n(Fe) = \frac{m}{M}"


def test_bóc_dấu_phân_cách_thừa() -> None:
    # Frontend đã bọc \[ \] quanh trường `latex`; model bọc thêm sẽ thành \[$...$\]
    # và KaTeX in mã nguồn ra màu đỏ.
    assert clean_latex(r"\[x^2 + 1\]") == "x^2 + 1"
    assert clean_latex("$$E = mc^2$$") == "E = mc^2"
    assert clean_latex("$n = 0,1$") == "n = 0,1"


def test_latex_sạch_giữ_nguyên() -> None:
    assert clean_latex("n = 5,6 / 56 = 0,1") == "n = 5,6 / 56 = 0,1"
    assert clean_latex(None) == ""
    assert clean_latex("") == ""


def test_văn_xuôi_giữ_dấu_đô_la_nhưng_vẫn_sửa_escape() -> None:
    # Trong văn xuôi thì $...$ là hợp lệ — frontend có cấu hình render nó.
    out = clean_prose("Ta có $x = \x0crac{1}{2}$ nên suy ra ...")
    assert out == r"Ta có $x = \frac{1}{2}$ nên suy ra ..."
