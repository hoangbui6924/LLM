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
            ("dai_so", "dao_ham", "Tính đạo hàm của hàm số y = x^3 tại x = 1", "n·x^(n-1)"),
            ("dai_so", "", "Tìm giá trị nhỏ nhất của biểu thức x + 25/x", "Cauchy"),
            ("dai_so", "tich_phan", "Tính tích phân của x^2 từ 0 đến 3", "F(b) - F(a)"),
            ("hinh_hoc", "hinh_hoc_khong_gian", "Tính thể tích khối chóp tứ giác đều", "1/3"),
            ("hinh_hoc", "", "Tính khoảng cách từ điểm đến mặt phẳng trong Oxyz", "√(a²+b²+c²)"),
            ("hinh_hoc", "hinh_hoc_phang", "Cho tam giác có ba cạnh 3, 4, 5. Tính diện tích tam giác", "Heron"),
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
        assert kho_dinh_ly.doan_van("dai_so", "", cau_hoi) == ""
        assert kho_dinh_ly.doan_van("hinh_hoc", "", cau_hoi) == ""

    def test_gioi_han_so_muc(self):
        """Nhiều hơn 3 mục thì loãng và tốn token prefill cho mọi lượt."""
        muc = kho_dinh_ly.tra_cuu(
            "dai_so", "dao_ham",
            "Tính đạo hàm nguyên hàm tích phân giới hạn tiệm cận cực trị logarit xác suất",
        )
        assert len(muc) <= kho_dinh_ly.SO_MUC_TOI_DA

    def test_mon_la_tra_rong(self):
        assert kho_dinh_ly.tra_cuu("sinh_hoc", "", "quang hợp") == []

    def test_chiu_duoc_thieu_dau(self):
        assert kho_dinh_ly.doan_van("hinh_hoc", "", "the tich khoi chop") != ""


# ---------------------------------------------------------------------------
# Kho lời giải
# ---------------------------------------------------------------------------


@pytest.fixture()
def kho(tmp_path, monkeypatch):
    """Trỏ kho vào DB tạm để test không chạm dữ liệu thật."""
    monkeypatch.setattr(kho_loi_giai, "DB_PATH", tmp_path / "test.db")
    return kho_loi_giai


_BUOC = [
    {"id": 1, "goal_vi": "Tính đạo hàm", "expression": "y' = 3*x**2", "result": "3"},
    {"id": 2, "goal_vi": "Tính khối lượng", "expression": "m = 0.1*40", "result": "3"},
]


class TestKhoLoiGiai:
    def test_luu_va_tim_lai(self, kho):
        assert kho.luu("Tính đạo hàm của y = x^3 tại x = 1", "dai_so",
                       "dao_ham", _BUOC, "3") is True
        thay = kho.tim("dai_so", "dao_ham", "Tính đạo hàm của y = x^3 tại x = 2")
        assert len(thay) == 1
        assert thay[0]["final_answer"] == "3"

    def test_khong_tra_ve_chinh_no(self, kho):
        """Lấy lại chính câu đang giải thì hệ thống chỉ chép đáp án, không còn giải."""
        cau = "Tính đạo hàm của y = x^3 tại x = 1"
        kho.luu(cau, "dai_so", "dao_ham", _BUOC, "3")
        assert kho.tim("dai_so", "dao_ham", cau) == []

    def test_khac_mon_thi_khong_lay(self, kho):
        kho.luu("Tính đạo hàm của y = x^3 tại x = 1", "dai_so",
                "dao_ham", _BUOC, "3")
        assert kho.tim("hinh_hoc", "dao_ham", "Tính đạo hàm của y = x^3") == []

    def test_khong_lien_quan_thi_khong_lay(self, kho):
        kho.luu("Tính đạo hàm của y = x^3 tại x = 1", "dai_so",
                "dao_ham", _BUOC, "3")
        assert kho.tim("dai_so", "tich_phan", "Tính tích phân của x^2") == []

    def test_tu_choi_du_lieu_thieu(self, kho):
        assert kho.luu("", "dai_so", "t", _BUOC, "3") is False
        assert kho.luu("Đề gì đó", "dai_so", "t", [], "3") is False
        assert kho.luu("Đề gì đó", "dai_so", "t", _BUOC, "") is False

    def test_luu_lai_cung_cau_thi_ghi_de(self, kho):
        """Chạy bench lặp trên cùng bộ đề không được làm kho phình."""
        cau = "Tính đạo hàm của y = x^3 tại x = 1"
        for _ in range(3):
            kho.luu(cau, "dai_so", "dao_ham", _BUOC, "3")
        assert kho.thong_ke()["tong"] == 1

    def test_kho_rong_khong_gay_loi(self, kho):
        assert kho.tim("dai_so", "abc", "câu hỏi bất kỳ") == []
        assert kho.doan_van("dai_so", "abc", "câu hỏi bất kỳ") == ""

    def test_doan_van_nhac_khong_duoc_chep(self, kho):
        kho.luu("Tính đạo hàm của y = x^3 tại x = 1", "dai_so",
                "dao_ham", _BUOC, "3")
        van = kho.doan_van("dai_so", "dao_ham", "Tính đạo hàm của y = x^3 tại x = 2")
        assert "không chép đáp số" in van

    def test_db_hong_khong_lam_do_luot_giai(self, kho, tmp_path):
        """Kho hỏng thì giải như cũ, tuyệt đối không được ném lỗi lên trên."""
        import pytest as _pt

        kho.DB_PATH = tmp_path / "khong_ton_tai" / "x" / "y.db"
        # Thư mục cha tạo được nên vẫn chạy; điều cần bảo đảm là KHÔNG ném lỗi.
        assert kho.tim("dai_so", "t", "câu hỏi") == []
