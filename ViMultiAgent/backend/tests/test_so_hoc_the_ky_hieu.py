"""Kiểm phép soát số học có THẾ ký hiệu — `verify_agent._check_arithmetic`.

Ca sinh ra bộ test này
----------------------
Chạy thử giao diện, đề "đốt cháy hoàn toàn 4,6 gam Na trong O2 dư". Lời giải viết:

    Bước 2: nNa    = mNa/MNa        -> 0,2 mol   (đúng)
    Bước 3: nNa2O  = nNa/2          -> 0,1 mol   (đúng)
    Bước 4: mNa2O  = nNa2O * MNa2O  -> 3,8 g     (SAI, phải là 6,2)

Verify vẫn kết luận "số học các bước khớp". Lý do: bản cũ đọc thẳng vế phải bằng
SymPy, gặp toàn ký hiệu tự do nên `numeric` là None và bỏ qua bước — cả 4 bước đều
bị bỏ qua, rồi vẫn báo PASS. Phép kiểm không sai kết luận, nó **không hề chạy**.

Ba điều bộ này phải giữ:
  1. Thế được giá trị từ các bước TRƯỚC và từ bảng nguyên tử khối -> bắt được lỗi.
  2. Không báo oan khi ký hiệu đổi đơn vị giữa chừng (cm -> m).
  3. Thiếu dù một ký hiệu thì BỎ QUA, không đoán.
"""

from __future__ import annotations

import pytest

from agents import verify_agent as V
from core.schemas import Solution, SolutionStep


def _sol(*buoc: tuple[str, str]) -> Solution:
    return Solution(
        steps=[SolutionStep(id=i, expression=e, result=r)
               for i, (e, r) in enumerate(buoc, start=1)],
        final_answer=buoc[-1][1],
    )


def _loi(sol: Solution) -> list[int]:
    """Trả id các bước bị báo sai."""
    return [c.step_id for c in V._check_arithmetic(sol) if not c.passed]


class TestBatDuocLoiThat:
    def test_ca_trong_anh_chup_man_hinh(self):
        """24 x 5 / 3 = 40 chứ không phải 60 — phải bắt đúng bước 4."""
        sol = _sol(
            ("Đáy là hình chữ nhật 6 x 4", ""),
            ("Sday = 6*4", "24 cm2"),
            ("h = 5", "5 cm"),
            ("V = Sday*h/3", "60 cm^3"),
        )
        assert _loi(sol) == [4]

    def test_cung_bai_nhung_dung_thi_khong_bao(self):
        sol = _sol(
            ("Đáy là hình chữ nhật 6 x 4", ""),
            ("Sday = 6*4", "24 cm2"),
            ("h = 5", "5 cm"),
            ("V = Sday*h/3", "40 cm^3"),
        )
        assert _loi(sol) == []

    def test_viet_dang_latex_co_chi_so_duoi(self):
        """Chỉ số dưới lồng nhau `S_{day}` phải gộp về `Sday` mới tra được."""
        sol = _sol(
            ("S_{day} = 6*4", "24"),
            ("h = 5", "5"),
            ("V = S_{day}*h/3", "60"),
        )
        assert _loi(sol) == [3]

class TestKhongBaoOan:
    def test_doi_don_vi_giua_chung_khong_bi_bao_sai(self):
        """A ghi 6 cm ở bước 1, dùng bằng mét ở bước 2 — lời giải ĐÚNG.

        Thế thẳng ra 120 trong khi bước ghi 1,2. Lệch đúng 100 lần nên phải hiểu
        là đổi đơn vị, không phải sai số học.
        """
        sol = _sol(
            ("A = 6", "6 cm"),
            ("omega = 20", "20 rad/s"),
            ("vmax = A * omega", "1,2 m/s"),
        )
        assert _loi(sol) == []

    def test_lam_tron_hop_le(self):
        sol = _sol(
            ("a = 1", "1"),
            ("b = a/3", "0,333"),
        )
        assert _loi(sol) == []

    def test_thieu_ky_hieu_thi_bo_qua_chu_khong_doan(self):
        """`mNa` chưa từng được định nghĩa — không được kết luận gì về bước này."""
        sol = _sol(("nNa = mNa/MNa", "0,2 mol"))
        assert _loi(sol) == []

    def test_dap_an_bang_chu_khong_ket_luan(self):
        sol = _sol(("ket_luan = tang", "hàm số đồng biến"))
        assert _loi(sol) == []

    def test_buoc_khong_co_dau_bang_van_an_toan(self):
        sol = _sol(("2Na + 1/2O2 -> Na2O", ""))
        assert _loi(sol) == []


class TestBaoCaoTrungThuc:
    """Không kiểm được bước nào thì phải NÓI RA, không được báo 'khớp'.

    Đây chính là chỗ bản cũ gây hại nhất: nó bỏ qua sạch rồi vẫn ghi 'số học các
    bước khớp', khiến Verify Agent đọc vào và yên tâm kết luận PASS.
    """

    def test_khong_kiem_duoc_thi_noi_ro(self):
        sol = _sol(("nNa = mNa/MNa", "0,2 mol"))
        (c,) = V._check_arithmetic(sol)
        assert c.passed is True
        assert "chưa kiểm được" in c.detail_vi

    def test_kiem_duoc_thi_bao_so_buoc(self):
        """Bước `a = 3` cũng tính được (vế phải đã là số), nên đếm cả hai."""
        sol = _sol(("a = 3", "3"), ("b = a * 4", "12"))
        (c,) = V._check_arithmetic(sol)
        assert c.passed is True
        assert "2/2" in c.detail_vi

    def test_dem_dung_khi_co_buoc_khong_kiem_duoc(self):
        sol = _sol(("Sday = 6*4", "24"), ("V = Sday*h/3", "40"))
        (c,) = V._check_arithmetic(sol)
        assert "1/2" in c.detail_vi


class TestDocSoKetQua:
    @pytest.mark.parametrize(
        "chuoi, mong_doi",
        [
            ("12,5 cm^3", 12.5),
            ("40 cm2", 40.0),
            ("6,2", 6.2),
            ("3,5 m", 3.5),
            ("60 độ", 60.0),
            ("-1", -1.0),
            ("1/2", 0.5),
        ],
    )
    def test_doc_duoc(self, chuoi, mong_doi):
        assert V._doc_so_ket_qua(chuoi) == pytest.approx(mong_doi)

    @pytest.mark.parametrize("chuoi", ["", "đồng biến", "x + 1", None])
    def test_khong_doc_duoc_tra_none(self, chuoi):
        assert V._doc_so_ket_qua(chuoi) is None
