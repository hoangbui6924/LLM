"""Kiểm thử các công cụ tất định — chạy không cần Ollama.

Đây là tầng đáng tin nhất của hệ thống: SymPy cho kết quả xác định, nên phải khoá
chặt bằng test. Nếu tầng này sai thì Verify Agent mất luôn khả năng phân định
đúng sai.
"""

from __future__ import annotations

import pytest

from tools import sympy_tool


class TestSymPy:
    def test_giai_phuong_trinh_bac_hai(self):
        r = sympy_tool.solve_equation("x^2 - 5x + 6 = 0", "x")
        assert r["ok"]
        nghiem = sorted(s["numeric"] for s in r["solutions"])
        assert nghiem == pytest.approx([2.0, 3.0])

    def test_dao_ham(self):
        r = sympy_tool.differentiate("x^3 - 3*x^2 + 2*x", "x")
        assert r["ok"]
        # Thay x = 1 vào đạo hàm phải ra -1. Đây đúng là bài mà model hay sai.
        v = sympy_tool.evaluate(r["result"], {"x": 1})
        assert v["numeric"] == pytest.approx(-1.0)

    def test_tich_phan_xac_dinh(self):
        r = sympy_tool.integrate("x^2", "x", "0", "3")
        assert r["ok"] and r["numeric"] == pytest.approx(9.0)

    def test_the_nghiem_nguoc_bat_duoc_nghiem_sai(self):
        dung = sympy_tool.check_substitution("x^2 - 5*x + 6 = 0", {"x": 2})
        sai = sympy_tool.check_substitution("x^2 - 5*x + 6 = 0", {"x": 5})
        assert dung["satisfied"] is True
        assert sai["satisfied"] is False

    def test_tuong_duong_chap_nhan_cach_viet_khac(self):
        assert sympy_tool.are_equivalent("1/2", "0.5")["equivalent"] is True
        assert sympy_tool.are_equivalent("sqrt(2)/2", "1/sqrt(2)")["equivalent"] is True

    def test_doc_duoc_latex_ban(self):
        # Model hay sinh LaTeX lẫn lộn; parser phải chịu được.
        r = sympy_tool.evaluate(r"\frac{1}{2} + \frac{1}{2}")
        assert r["ok"] and r["numeric"] == pytest.approx(1.0)

    def test_bieu_thuc_hong_khong_lam_sap(self):
        r = sympy_tool.evaluate("(((")
        assert r["ok"] is False and "error" in r


class TestTachTu:
    """PhoBERT bắt buộc dùng văn bản đã tách từ — khoá lại để không ai gỡ nhầm."""

    def test_tach_tu_ghep(self):
        from ml.segment import tach_tu

        ra = tach_tu("Tính vận tốc cực đại của vật")
        assert "_" in ra, "underthesea phải nối từ ghép bằng gạch dưới"

    def test_cau_rong(self):
        from ml.segment import tach_tu

        assert tach_tu("") == ""
