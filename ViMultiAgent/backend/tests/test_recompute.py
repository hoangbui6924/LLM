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
