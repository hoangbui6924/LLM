"""Kiểm thử so sánh đáp số của bộ tính lại độc lập.

Ca sinh ra bộ test này: đề "viết phương trình tiếp tuyến" đi qua TOÀN BỘ tầng
kiểm chứng mà không phép kiểm nào chạy được, vì mọi phép so sánh đều chỉ làm việc
với số. Hệ thống trả `y = 5x - 5` trong khi đúng là `y = -x + 7`, và không tầng
nào phát hiện.
"""

from __future__ import annotations

from agents.recompute_agent import KetQua, _boc_ve_phai, compare


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
