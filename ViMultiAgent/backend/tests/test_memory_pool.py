"""Kiểm memory pool — mục (2) của đề bài.

Hai kho, hai nhóm rủi ro khác nhau, nên kiểm khác nhau:

* `kho_dinh_ly`  — phải tra ĐÚNG khi có liên quan và trả RỖNG khi không. Chèn công
                   thức lạc đề còn tệ hơn không chèn gì, vì nó dẫn model đi sai.
* `kho_loi_giai` — phải không bao giờ làm hỏng lượt giải, và không được trả về
                   chính câu hỏi đang giải (nếu không hệ thống chỉ chép đáp án cũ).

Mọi test đụng cơ sở dữ liệu đều trỏ vào file tạm, không chạm `vimultiagent.db`.
"""

from __future__ import annotations

import pytest

from memory import kho_dinh_ly, kho_loi_giai


# ---------------------------------------------------------------------------
# Kho định lý
# ---------------------------------------------------------------------------


class TestKhoDinhLy:
    @pytest.mark.parametrize(
        "subject, topic, cau_hoi, phai_co",
        [
            ("chemistry", "tinh_theo_pthh",
             "Đốt cháy 5,6 gam Fe trong O2 dư thu được Fe3O4", "HỆ SỐ"),
            ("chemistry", "", "Hoà tan 5,4 gam Al vào dung dịch HCl dư", "H₂"),
            ("physics", "giao_thoa_anh_sang",
             "Thí nghiệm Y-âng khoảng cách hai khe 1 mm", "λD/a"),
            ("physics", "", "Con lắc lò xo có độ cứng 100 N/m", "√(k/m)"),
            ("math", "hinh_hoc_khong_gian", "Tính thể tích khối chóp tứ giác đều", "1/3"),
            ("math", "", "Tìm giá trị nhỏ nhất của biểu thức x + 25/x", "Cauchy"),
        ],
    )
    def test_tra_dung_cong_thuc(self, subject, topic, cau_hoi, phai_co):
        van = kho_dinh_ly.doan_van(subject, topic, cau_hoi)
        assert phai_co in van, f"tra ra: {van[:200]}"

    @pytest.mark.parametrize(
        "cau_hoi",
        ["Hôm nay trời đẹp quá", "Xin chào bạn khoẻ không", ""],
    )
    def test_khong_lien_quan_thi_tra_rong(self, cau_hoi):
        """Thà không chèn gì còn hơn chèn công thức lạc đề."""
        assert kho_dinh_ly.doan_van("math", "", cau_hoi) == ""
        assert kho_dinh_ly.doan_van("physics", "", cau_hoi) == ""

    def test_gioi_han_so_muc(self):
        """Nhiều hơn 3 mục thì loãng và tốn token prefill cho mọi lượt."""
        muc = kho_dinh_ly.tra_cuu(
            "chemistry", "so_mol",
            "Tính số mol nồng độ dung dịch khối lượng mol phản ứng axit bazơ pH điện phân",
        )
        assert len(muc) <= kho_dinh_ly.SO_MUC_TOI_DA

    def test_mon_la_tra_rong(self):
        assert kho_dinh_ly.tra_cuu("sinh_hoc", "", "quang hợp") == []

    def test_chiu_duoc_thieu_dau(self):
        assert kho_dinh_ly.doan_van("physics", "", "con lac lo xo do cung") != ""


# ---------------------------------------------------------------------------
# Kho lời giải
# ---------------------------------------------------------------------------


@pytest.fixture()
def kho(tmp_path, monkeypatch):
    """Trỏ kho vào DB tạm để test không chạm dữ liệu thật."""
    monkeypatch.setattr(kho_loi_giai, "DB_PATH", tmp_path / "test.db")
    return kho_loi_giai


_BUOC = [
    {"id": 1, "goal_vi": "Tính số mol", "expression": "n = 2.4/24", "result": "0.1 mol"},
    {"id": 2, "goal_vi": "Tính khối lượng", "expression": "m = 0.1*40", "result": "4 gam"},
]


class TestKhoLoiGiai:
    def test_luu_va_tim_lai(self, kho):
        assert kho.luu("Đốt cháy 2,4 gam Mg thu được MgO", "chemistry",
                       "tinh_theo_pthh", _BUOC, "4 gam") is True
        thay = kho.tim("chemistry", "tinh_theo_pthh", "Đốt cháy 5,6 gam Fe thu được Fe3O4")
        assert len(thay) == 1
        assert thay[0]["final_answer"] == "4 gam"

    def test_khong_tra_ve_chinh_no(self, kho):
        """Lấy lại chính câu đang giải thì hệ thống chỉ chép đáp án, không còn giải."""
        cau = "Đốt cháy 2,4 gam Mg thu được MgO"
        kho.luu(cau, "chemistry", "tinh_theo_pthh", _BUOC, "4 gam")
        assert kho.tim("chemistry", "tinh_theo_pthh", cau) == []

    def test_khac_mon_thi_khong_lay(self, kho):
        kho.luu("Đốt cháy 2,4 gam Mg thu được MgO", "chemistry",
                "tinh_theo_pthh", _BUOC, "4 gam")
        assert kho.tim("physics", "tinh_theo_pthh", "Đốt cháy 5,6 gam Fe") == []

    def test_khong_lien_quan_thi_khong_lay(self, kho):
        kho.luu("Đốt cháy 2,4 gam Mg thu được MgO", "chemistry",
                "tinh_theo_pthh", _BUOC, "4 gam")
        assert kho.tim("chemistry", "dien_phan", "Điện phân dung dịch CuSO4") == []

    def test_tu_choi_du_lieu_thieu(self, kho):
        assert kho.luu("", "chemistry", "t", _BUOC, "4 gam") is False
        assert kho.luu("Đề gì đó", "chemistry", "t", [], "4 gam") is False
        assert kho.luu("Đề gì đó", "chemistry", "t", _BUOC, "") is False

    def test_luu_lai_cung_cau_thi_ghi_de(self, kho):
        """Chạy bench lặp trên cùng bộ đề không được làm kho phình."""
        cau = "Đốt cháy 2,4 gam Mg thu được MgO"
        for _ in range(3):
            kho.luu(cau, "chemistry", "tinh_theo_pthh", _BUOC, "4 gam")
        assert kho.thong_ke()["tong"] == 1

    def test_kho_rong_khong_gay_loi(self, kho):
        assert kho.tim("chemistry", "abc", "câu hỏi bất kỳ") == []
        assert kho.doan_van("chemistry", "abc", "câu hỏi bất kỳ") == ""

    def test_doan_van_nhac_khong_duoc_chep(self, kho):
        kho.luu("Đốt cháy 2,4 gam Mg thu được MgO", "chemistry",
                "tinh_theo_pthh", _BUOC, "4 gam")
        van = kho.doan_van("chemistry", "tinh_theo_pthh", "Đốt cháy 5,6 gam Fe thu được Fe3O4")
        assert "không chép đáp số" in van

    def test_db_hong_khong_lam_do_luot_giai(self, kho, tmp_path):
        """Kho hỏng thì giải như cũ, tuyệt đối không được ném lỗi lên trên."""
        import pytest as _pt

        kho.DB_PATH = tmp_path / "khong_ton_tai" / "x" / "y.db"
        # Thư mục cha tạo được nên vẫn chạy; điều cần bảo đảm là KHÔNG ném lỗi.
        assert kho.tim("chemistry", "t", "câu hỏi") == []
