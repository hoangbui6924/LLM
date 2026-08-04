"""Kiểm thử bộ cứu JSON bị cắt.

Rủi ro của module này giống `arbiter`: không phải cứu hụt, mà là **cứu bậy** —
tạo ra dữ liệu trông hợp lệ nhưng sai. Phần lớn test dưới đây kiểm đúng chiều đó.
"""

from __future__ import annotations

from core.json_cuu import cuu


class TestNguyenVen:
    def test_json_du_thi_tra_nguyen(self):
        assert cuu('{"a": 1, "b": [2, 3]}') == {"a": 1, "b": [2, 3]}

    def test_bo_rac_dau_chuoi(self):
        assert cuu('Đây là kết quả: {"a": 1}') == {"a": 1}


class TestCuuDuoc:
    def test_cat_giua_chuoi_ky_tu(self):
        tho = '{"steps":[{"id":1,"goal_vi":"Tính đạo hàm","expression":"y\' = 3x^2 - 6x'
        kq = cuu(tho)
        assert kq is not None
        assert len(kq["steps"]) == 1
        assert kq["steps"][0]["goal_vi"] == "Tính đạo hàm"
        # Trường bị cắt dở phải bị loại, không được giữ một nửa.
        assert "expression" not in kq["steps"][0]

    def test_cat_sau_mot_phan_tu_tron_ven(self):
        tho = '{"steps":[{"id":1,"result":"a"},{"id":2,"result":"b"},{"id":3'
        kq = cuu(tho)
        assert kq is not None and len(kq["steps"]) == 2
        assert kq["steps"][1]["id"] == 2

    def test_cat_sau_dau_phay(self):
        tho = '{"a": 1, "b": 2,'
        assert cuu(tho) == {"a": 1, "b": 2}

    def test_cat_giua_so(self):
        tho = '{"a": 1, "b": 234'
        kq = cuu(tho)
        assert kq is not None and kq["a"] == 1

    def test_long_nhieu_tang(self):
        tho = '{"x":{"y":{"z":[1,2,3],"w":"xong"},"v":"dang viet do dang'
        kq = cuu(tho)
        assert kq is not None
        assert kq["x"]["y"]["z"] == [1, 2, 3]
        assert kq["x"]["y"]["w"] == "xong"


class TestKhongDuocCuuBay:
    def test_chuoi_rong(self):
        assert cuu("") is None

    def test_khong_co_json(self):
        assert cuu("model tra loi bang van xuoi khong co JSON") is None

    def test_moi_mo_ngoac(self):
        assert cuu("{") is None

    def test_khong_phai_object(self):
        assert cuu("[1, 2, 3]") is None

    def test_dau_ngoac_kep_thoat_khong_lam_lech(self):
        tho = '{"a": "co dau \\" ben trong", "b": 2, "c": "dang viet'
        kq = cuu(tho)
        assert kq is not None
        assert kq["a"] == 'co dau " ben trong'
        assert kq["b"] == 2
        assert "c" not in kq

    def test_ngoac_trong_chuoi_khong_tinh(self):
        """Dấu { } nằm trong chuỗi ký tự không được tính vào ngăn xếp ngoặc."""
        tho = '{"bieu_thuc": "\\\\frac{1}{2}", "ket_qua": "0.5", "x": "do dang'
        kq = cuu(tho)
        assert kq is not None
        assert kq["ket_qua"] == "0.5"
