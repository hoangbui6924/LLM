"""Kiểm bộ kiểm chứng tất định bằng SymPy.

Bộ này phải thoả ba điều, và điều thứ ba khó nhất:

  1. Đáp án ĐÚNG  -> `dat is True`
  2. Đáp án SAI   -> `dat is False`
  3. Không đủ căn cứ -> `dat is None`, TUYỆT ĐỐI không đoán

Điều 3 quan trọng vì đây là phép kiểm TẤT ĐỊNH — kết luận của nó có quyền phủ
quyết cả Verify Agent. Một lần báo oan ở đây là kích hoạt vòng giải lại vô ích,
hoặc tệ hơn, ghi đè một lời giải đúng.

Ba chủ đề Toán sai NẶNG NHẤT trên bộ đề khó (tích phân từng phần 3/3, giới hạn
3/3, tiếp tuyến 3/3) đều nằm trong tầm kiểm của module này — đó là lý do nó ra đời.
"""

from __future__ import annotations

import pytest

from tools import kiem_symbolic as ks


class TestDaoHam:
    def test_dung_tai_diem(self):
        # y = x^3 - 3x^2 + 2x, y'(1) = 3 - 6 + 2 = -1
        r = ks.kiem("dao_ham", "-1", ham_goc="x**3 - 3*x**2 + 2*x", bien="x", diem="1")
        assert r.dat is True

    def test_sai_tai_diem(self):
        r = ks.kiem("dao_ham", "5", ham_goc="x**3 - 3*x**2 + 2*x", bien="x", diem="1")
        assert r.dat is False
        assert "-1" in r.gia_tri_dung

    def test_dap_an_dang_bieu_thuc(self):
        r = ks.kiem("dao_ham", "3*x**2 - 6*x + 2", ham_goc="x**3 - 3*x**2 + 2*x")
        assert r.dat is True

    def test_bieu_thuc_viet_khac_dang_van_dung(self):
        r = ks.kiem("dao_ham", "2 - 6*x + 3*x**2", ham_goc="x**3 - 3*x**2 + 2*x")
        assert r.dat is True


class TestTichPhan:
    def test_co_can_dung(self):
        # ∫[0→1] (3x^2 + 2x) dx = 1 + 1 = 2
        r = ks.kiem("tich_phan", "2", ham_goc="3*x**2 + 2*x",
                    can_duoi="0", can_tren="1")
        assert r.dat is True

    def test_co_can_sai(self):
        r = ks.kiem("tich_phan", "5", ham_goc="3*x**2 + 2*x",
                    can_duoi="0", can_tren="1")
        assert r.dat is False

    def test_tich_phan_tung_phan(self):
        """Chủ đề sai 3/3 trên bộ đề khó — phải bắt được."""
        # ∫[0→1] x*e^x dx = 1
        r = ks.kiem("tich_phan", "1", ham_goc="x*exp(x)", can_duoi="0", can_tren="1")
        assert r.dat is True

    def test_tich_phan_tung_phan_sai(self):
        r = ks.kiem("tich_phan", "2.718", ham_goc="x*exp(x)", can_duoi="0", can_tren="1")
        assert r.dat is False

    def test_nguyen_ham_khong_can(self):
        r = ks.kiem("tich_phan", "x**3 + x**2", ham_goc="3*x**2 + 2*x")
        assert r.dat is True


class TestGioiHan:
    def test_gioi_han_huu_han(self):
        # lim (x^2 - 1)/(x - 1) khi x -> 1 = 2
        r = ks.kiem("gioi_han", "2", ham_goc="(x**2 - 1)/(x - 1)", diem="1")
        assert r.dat is True

    def test_gioi_han_sai(self):
        r = ks.kiem("gioi_han", "0", ham_goc="(x**2 - 1)/(x - 1)", diem="1")
        assert r.dat is False

    def test_gioi_han_vo_cuc(self):
        # lim (sqrt(2x^2 + x) - sqrt(2)x) khi x -> +oo = 1/(2*sqrt(2))
        r = ks.kiem("gioi_han", "sqrt(2)/4",
                    ham_goc="sqrt(2*x**2 + x) - sqrt(2)*x", diem="oo")
        assert r.dat is True


class TestTiepTuyen:
    def test_tiep_tuyen_dung(self):
        # y = x^2 + 3x + 5 tại x = 2: y' = 2x+3 = 7, y(2) = 15 -> y = 7x + 1
        r = ks.kiem("tiep_tuyen", "7*x + 1", ham_goc="x**2 + 3*x + 5", diem="2")
        assert r.dat is True

    def test_tiep_tuyen_sai_he_so_goc(self):
        r = ks.kiem("tiep_tuyen", "5*x + 5", ham_goc="x**2 + 3*x + 5", diem="2")
        assert r.dat is False

    def test_tiep_tuyen_quen_cong_tung_do(self):
        """Lỗi hay gặp nhất: quên cộng y(x0)."""
        r = ks.kiem("tiep_tuyen", "7*x - 14", ham_goc="x**2 + 3*x + 5", diem="2")
        assert r.dat is False


class TestPhuongTrinh:
    """Thế nghiệm ngược — phép kiểm mà sympy_tool gọi là quan trọng nhất."""

    def test_nghiem_dung(self):
        r = ks.kiem("phuong_trinh", "3", ham_goc="x**2 - 5*x + 6 = 0")
        assert r.dat is True

    def test_nghiem_sai(self):
        r = ks.kiem("phuong_trinh", "4", ham_goc="x**2 - 5*x + 6 = 0")
        assert r.dat is False

    def test_nhieu_nghiem_deu_dung(self):
        r = ks.kiem("phuong_trinh", "2; 3", ham_goc="x**2 - 5*x + 6 = 0")
        assert r.dat is True

    def test_mot_nghiem_ngoai_lai(self):
        """Nghiệm ngoại lai phải bị bắt — đây là lỗi kinh điển của bài logarit."""
        r = ks.kiem("phuong_trinh", "2; 5", ham_goc="x**2 - 5*x + 6 = 0")
        assert r.dat is False

    def test_dang_x_bang(self):
        r = ks.kiem("phuong_trinh", "x = 3", ham_goc="x**2 - 5*x + 6 = 0")
        assert r.dat is True


class TestKhongDoanBua:
    """Không đủ căn cứ thì phải trả None, không được đoán."""

    @pytest.mark.parametrize(
        "loai, dap_an, ham_goc",
        [
            ("hoa_hoc", "5", "x**2"),        # loại không hỗ trợ
            ("dao_ham", "", "x**2"),         # thiếu đáp án
            ("dao_ham", "5", ""),            # thiếu hàm gốc
            ("gioi_han", "5", "x**2"),       # thiếu điểm
            ("tiep_tuyen", "5", "x**2"),     # thiếu hoành độ
            ("phuong_trinh", "3", ""),       # thiếu phương trình
        ],
    )
    def test_tra_none(self, loai, dap_an, ham_goc):
        assert ks.kiem(loai, dap_an, ham_goc=ham_goc).dat is None

    def test_ham_goc_hong_khong_nem_loi(self):
        assert ks.kiem("dao_ham", "5", ham_goc="!!!hỏng@@@", diem="1").dat is None

    def test_dap_an_bang_chu_khong_ket_luan(self):
        assert ks.kiem("dao_ham", "tăng dần", ham_goc="x**2", diem="1").dat is None


class TestChotChanLoaiKiem:
    """Loại bài model khai phải khớp từ khoá trong đề — chốt chặn báo oan.

    Ca sinh ra bộ test này: đo trên 150 bài, 34 lời giải ĐÚNG bị Verify kêu FAIL,
    và 33 trong số đó do model gán nhầm `loai_kiem`. Điển hình là đề "Cho
    f(x) = 3x^2 + 5x - 1, tính f(3)" bị gán "dao_ham" — SymPy tính đạo hàm tại 3
    được 23 trong khi đáp án đúng là giá trị hàm số 41, rồi kết luận lời giải sai.

    Phép kiểm tất định có quyền phủ quyết cả Verify Agent, nên nó phải CHẮC.
    Trích xuất sai loại bài thì thà bỏ qua còn hơn phán bừa.
    """

    @pytest.mark.parametrize(
        "loai, de_bai",
        [
            ("dao_ham", "Tính đạo hàm của hàm số y = x^3 tại x = 1"),
            ("tich_phan", "Tính tích phân I = ∫ từ 0 đến 1 của x·e^x dx"),
            ("tich_phan", "Tìm nguyên hàm của hàm số y = 3x^2"),
            ("gioi_han", "Tính giới hạn của biểu thức khi x tiến tới vô cùng"),
            ("phuong_trinh", "Giải phương trình x^2 - 5x + 6 = 0"),
            ("tiep_tuyen", "Viết phương trình tiếp tuyến tại điểm có hoành độ x = 2"),
        ],
    )
    def test_nhan_khi_de_dung_loai(self, loai, de_bai):
        from agents.recompute_agent import _loai_kiem_hop_le
        assert _loai_kiem_hop_le(loai, de_bai) is True

    @pytest.mark.parametrize(
        "loai, de_bai, vi_sao",
        [
            ("dao_ham", "Cho hàm số f(x) = 3x^2 + 5x - 1. Tính f(3).",
             "tính GIÁ TRỊ hàm số, không phải đạo hàm"),
            ("dao_ham", "Cho cấp số nhân u1 = 3, công bội q = 2. Tính số hạng thứ 5.",
             "cấp số nhân, không liên quan đạo hàm"),
            ("dao_ham", "Cho khối chóp đáy hình vuông cạnh 3, chiều cao 9. Tính thể tích.",
             "hình học không gian"),
            ("tich_phan", "Tính thể tích khối lăng trụ đứng", "không có tích phân nào"),
            ("tiep_tuyen", "Tìm giá trị cực đại của hàm số", "cực trị, không phải tiếp tuyến"),
            ("phuong_trinh", "Tính khối lượng Fe3O4 thu được", "bài Hoá"),
        ],
    )
    def test_tu_choi_khi_de_khac_loai(self, loai, de_bai, vi_sao):
        from agents.recompute_agent import _loai_kiem_hop_le
        assert _loai_kiem_hop_le(loai, de_bai) is False, vi_sao

    def test_loai_khong_ton_tai(self):
        from agents.recompute_agent import _loai_kiem_hop_le
        assert _loai_kiem_hop_le("hoa_hoc", "bất kỳ đề nào") is False
        assert _loai_kiem_hop_le("", "Tính đạo hàm") is False
