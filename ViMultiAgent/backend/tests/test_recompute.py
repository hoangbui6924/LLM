"""Kiểm thử so sánh đáp số của bộ tính lại độc lập.

Ca sinh ra bộ test này: đề "viết phương trình tiếp tuyến" đi qua TOÀN BỘ tầng
kiểm chứng mà không phép kiểm nào chạy được, vì mọi phép so sánh đều chỉ làm việc
với số. Hệ thống trả `y = 5x - 5` trong khi đúng là `y = -x + 7`, và không tầng
nào phát hiện.
"""

from __future__ import annotations

import pytest

from agents.recompute_agent import KetQua, _boc_ve_phai, _con_ky_hieu_tu_do, compare


class TestConKyHieuTuDo:
    """Chặn kết quả tính lại DỞ DANG.

    Ca sinh ra bộ test này: đo trên 150 bài thấy cơ chế cứu đáp án LÀM HỎNG 10 bài
    trong khi chỉ cứu được 8. Sáu ca hỏng cùng một kiểu — bộ tính lại dừng ở nguyên
    hàm chưa thay cận (`x*(3*x + 4)` cho bài tích phân có cận) hoặc ở chính hàm số
    chưa tìm cực trị (`x + 25/x`), rồi thứ dở dang đó được đem đè lên đáp số ĐÚNG
    của Subject Agent.
    """

    @pytest.mark.parametrize(
        "bieu_thuc",
        [
            "x*(3*x + 4)",       # nguyên hàm chưa thay cận
            "x*(x + 1)",
            "x**3 - 3*x + 1",    # chính hàm số, chưa tìm GTLN
            "x + 25/x",          # chưa áp dụng Cauchy
        ],
    )
    def test_bat_ket_qua_do_dang(self, bieu_thuc):
        assert _con_ky_hieu_tu_do(bieu_thuc) is True

    @pytest.mark.parametrize(
        "bieu_thuc",
        ["232/3", "5.6/56*22.4", "sqrt(73)", "2*pi*2*0.05", "-1"],
    )
    def test_bieu_thuc_tinh_duoc_thi_cho_qua(self, bieu_thuc):
        assert _con_ky_hieu_tu_do(bieu_thuc) is False

    def test_rong_va_hong_coi_nhu_do_dang(self):
        # Không đọc được thì không đủ căn cứ để tin — thà bỏ còn hơn đè bừa.
        assert _con_ky_hieu_tu_do("") is True
        assert _con_ky_hieu_tu_do("   ") is True
        assert _con_ky_hieu_tu_do("!!!hong") is True

    def test_dap_so_bieu_thuc_that_van_con_an(self):
        """Phương trình tiếp tuyến ĐÚNG là có `x` — nên hàm này không đủ để quyết.

        Chốt chặn thật nằm ở `question_type != "symbolic"` phía ngoài: chỉ đề hỏi
        MỘT CON SỐ mới bị chặn.
        """
        assert _con_ky_hieu_tu_do("-x + 7") is True


class TestBocVeTrai:
    def test_bo_y_bang(self):
        assert _boc_ve_phai("y = -x + 7") == "-x + 7"

    def test_bo_ky_hieu_ham(self):
        assert _boc_ve_phai("f'(x) = 2x") == "2x"

    def test_khong_co_ve_trai_thi_giu_nguyen(self):
        assert _boc_ve_phai("-x + 7") == "-x + 7"

    def test_khong_pha_dau_bang_trong_bieu_thuc(self):
        # Không được cắt nhầm khi vế trái không phải một ký hiệu đơn.
        assert _boc_ve_phai("2 + 3") == "2 + 3"


class TestSoSanhBieuThuc:
    def _kq(self) -> KetQua:
        return KetQua(bieu_thuc="-1*(x - 2) + 5", approach_vi="tiếp tuyến")

    def test_dung_du_viet_khac_dang(self):
        for dap_an in ("y = -x + 7", "-x+7", "y = -(x-2)+5", "7 - x"):
            c = compare(self._kq(), dap_an)
            assert c is not None and c.passed, dap_an

    def test_bat_duoc_dap_an_sai(self):
        c = compare(self._kq(), "y = 5x - 5")
        assert c is not None and not c.passed
        assert "5x - 5" in c.detail_vi or "5*x" in c.detail_vi

    def test_dap_an_rong_thi_khong_ket_luan(self):
        assert compare(self._kq(), "") is None

    def test_khong_co_ket_qua_thi_khong_ket_luan(self):
        assert compare(KetQua(), "y = -x + 7") is None


class TestSoSanhSo:
    def test_khop_trong_dung_sai(self):
        kq = KetQua(gia_tri=0.6283185, unit="m/s")
        c = compare(kq, "0.628 m/s")
        assert c is not None and c.passed

    def test_lech_qua_nguong(self):
        kq = KetQua(gia_tri=7.7333, unit="gam")
        c = compare(kq, "2.4 gam")
        assert c is not None and not c.passed

    def test_uu_tien_so_khi_co_ca_hai(self):
        kq = KetQua(gia_tri=5.0, bieu_thuc="x + 1")
        assert kq.mo_ta() == "5"


class TestPlannerGiuSoLieu:
    """Chống lỗi model chép sai số liệu của đề.

    Ca thật đo được: qwen3:4b chép `x = 5cos(10πt)` thành `x = 5cos(1:0πt)` và
    `R = 110 Ω` thành `R = 1:110 Ω`. Đáp án lệch 10 lần mà không tầng kiểm chứng
    nào phát hiện, vì tất cả đều đối chiếu với đề ĐÃ HỎNG.
    """

    def test_bat_duoc_so_bi_chen_dau_hai_cham(self):
        from agents.planner import _giu_nguyen_so_lieu

        assert not _giu_nguyen_so_lieu("x = 5cos(10πt) cm", "x = 5cos(1:0πt) cm")
        assert not _giu_nguyen_so_lieu("R = 110 Ω", "R = 1:110 Ω")

    def test_chap_nhan_chuan_hoa_khong_doi_so(self):
        from agents.planner import _giu_nguyen_so_lieu

        assert _giu_nguyen_so_lieu(
            "Một vật dao động với biên độ 5 cm, tần số 2 Hz.",
            "Vật dao động điều hoà, biên độ 5 cm, tần số 2 Hz. Tính vận tốc cực đại.",
        )

    def test_bat_duoc_so_bi_mat(self):
        from agents.planner import _giu_nguyen_so_lieu

        assert not _giu_nguyen_so_lieu("Cho hình chóp đáy 5,6 và cao 3", "Cho hình chóp đáy 5,6")

    def test_bat_duoc_so_bi_doi_gia_tri(self):
        from agents.planner import _giu_nguyen_so_lieu

        assert not _giu_nguyen_so_lieu("R = 110 Ω", "R = 100 Ω")


# ---------------------------------------------------------------------------
# Đường tích hợp cấu trúc -> kiểm chứng.
#
# Vì sao có nhóm test này: P3 thêm ba dạng hình học và test của `kiem_symbolic`
# đều XANH, nhưng phép kiểm KHÔNG BAO GIỜ chạy được trên thực tế. Lý do là các
# test đó gọi thẳng `kiem_symbolic.kiem()`, còn đường thật phải đi qua `KetQua`
# rồi mới tới `compare()` — và chính chỗ nối ấy hỏng ở hai điểm:
#
#   1. `compute()` kiểm tay `loai_kiem and ham_goc`, trong khi hình học không
#      dùng `ham_goc`. Mọi bài thể tích rơi vào `bieu_thuc_rong`.
#   2. Đáp số hình học kèm đơn vị (`20.0 đv³`) làm SymPy đọc `đv` thành ký hiệu
#      tự do, phép kiểm im lặng bỏ qua.
#
# Bài học: test đơn vị cho tầng dưới KHÔNG thay được test cho chỗ nối.
# ---------------------------------------------------------------------------


class TestCauTrucHinhHoc:
    @pytest.mark.parametrize(
        "kw",
        [
            dict(loai_kiem="the_tich", hinh="chop", tham_so="12;5"),
            dict(loai_kiem="the_tich", hinh="lap_phuong", tham_so="4"),
            dict(loai_kiem="kc_hai_diem", diem="1;2;3", diem2="4;6;3"),
            dict(loai_kiem="kc_diem_mp", ham_goc="x+2y-2z+1=0", diem="1;2;3"),
        ],
    )
    def test_du_truong_thi_co_cau_truc(self, kw):
        """Hình học KHÔNG dùng `ham_goc`, nên không được đòi trường đó."""
        assert KetQua(**kw).co_cau_truc is True

    @pytest.mark.parametrize(
        "kw",
        [
            dict(loai_kiem="the_tich", hinh="chop"),           # thiếu tham_so
            dict(loai_kiem="the_tich", tham_so="12;5"),        # thiếu hinh
            dict(loai_kiem="kc_hai_diem", diem="1;2;3"),       # thiếu diem2
            dict(loai_kiem="kc_diem_mp", diem="1;2;3"),        # thiếu mặt phẳng
        ],
    )
    def test_thieu_truong_thi_khong_co_cau_truc(self, kw):
        assert KetQua(**kw).co_cau_truc is False

    def test_dai_so_van_doi_ham_goc(self):
        assert KetQua(loai_kiem="dao_ham", ham_goc="x**2").co_cau_truc is True
        assert KetQua(loai_kiem="dao_ham", diem="1").co_cau_truc is False


class TestCompareHinhHoc:
    """`compare()` phải kết luận được, kể cả khi đáp án kèm đơn vị."""

    @pytest.mark.parametrize(
        "dap_an", ["20", "20.0", "20 cm^3", "20.0 đv³", "20 đvtt", "20 đơn vị thể tích"]
    )
    def test_the_tich_dung_du_kem_don_vi(self, dap_an):
        kq = KetQua(loai_kiem="the_tich", hinh="chop", tham_so="12;5")
        c = compare(kq, dap_an)
        assert c is not None and c.passed is True

    def test_the_tich_sai_thi_bat_duoc(self):
        kq = KetQua(loai_kiem="the_tich", hinh="chop", tham_so="12;5")
        c = compare(kq, "60 cm^3")
        assert c is not None and c.passed is False

    def test_khoang_cach_diem_mat_phang(self):
        kq = KetQua(loai_kiem="kc_diem_mp", ham_goc="2x - y + 2z - 3 = 0", diem="1;2;3")
        c = compare(kq, "1")
        assert c is not None and c.passed is True

    def test_quen_tri_tuyet_doi_ra_am(self):
        kq = KetQua(loai_kiem="kc_diem_mp", ham_goc="2x - y + 2z - 3 = 0", diem="1;2;3")
        c = compare(kq, "-1")
        assert c is not None and c.passed is False

    def test_hinh_la_thi_khong_ket_luan(self):
        kq = KetQua(loai_kiem="the_tich", hinh="khoi_bat_ky", tham_so="1;2")
        assert compare(kq, "20") is None


class TestTheTichMoHo:
    """Chốt chặn cho ca báo oan đã đo được.

    Đề "khối chóp đáy là hình vuông CẠNH 3, cao 9" bị mô hình khai
    `hinh="chop", tham_so="3; 9"` — điền cạnh vào ô diện tích. SymPy tính 9 rồi
    PHỦ QUYẾT đáp án đúng 27. Phép kiểm tất định có quyền phủ quyết nên nó phải
    CHẮC; không chắc thì im lặng.
    """

    def test_day_ta_bang_hinh_dang_thi_tu_choi(self):
        from agents.recompute_agent import _the_tich_mo_ho
        assert _the_tich_mo_ho(
            "chop", "Cho khối chóp có đáy là hình vuông cạnh 3 và chiều cao 9"
        ) is True

    def test_de_cho_san_dien_tich_thi_nhan(self):
        from agents.recompute_agent import _the_tich_mo_ho
        assert _the_tich_mo_ho(
            "chop", "Tính thể tích khối chóp có diện tích đáy 12 và chiều cao 5"
        ) is False

    def test_bien_the_ro_rang_thi_luon_nhan(self):
        from agents.recompute_agent import _the_tich_mo_ho
        assert _the_tich_mo_ho(
            "chop_day_vuong", "Cho khối chóp đáy hình vuông cạnh 3, cao 9"
        ) is False

    def test_hinh_khong_qua_dien_tich_thi_khong_lien_quan(self):
        from agents.recompute_agent import _the_tich_mo_ho
        assert _the_tich_mo_ho("lap_phuong", "Hình lập phương cạnh 4") is False
        assert _the_tich_mo_ho("cau", "Khối cầu bán kính 3") is False


class TestBienTheTheTich:
    def test_chop_day_vuong_tinh_dung(self):
        from tools.kiem_symbolic import kiem
        r = kiem(loai="the_tich", dap_an="27", hinh="chop_day_vuong", tham_so="3;9")
        assert r.dat is True

    def test_chop_day_vuong_bat_duoc_sai(self):
        from tools.kiem_symbolic import kiem
        r = kiem(loai="the_tich", dap_an="9", hinh="chop_day_vuong", tham_so="3;9")
        assert r.dat is False

    def test_lang_tru_day_vuong(self):
        from tools.kiem_symbolic import kiem
        r = kiem(loai="the_tich", dap_an="20", hinh="lang_tru_day_vuong", tham_so="2;5")
        assert r.dat is True
