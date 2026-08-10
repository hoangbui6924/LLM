"""Kiểm hàm chấm của bench — nơi đã sinh ra hai lỗi làm sai lệch số liệu.

Cả hai lỗi đều thuộc loại nguy hiểm nhất: chúng không làm chương trình đổ, chỉ
lặng lẽ dịch con số trong báo cáo. Phát hiện được là nhờ mở từng bài "sai" ra đọc.

  1. Bóc số dẫn đầu thay vì TÍNH biểu thức -> `5/36` đọc thành 5, `√73` thành 73.
     Chấm oan 4 lời giải đúng, dìm accuracy 2,7 điểm phần trăm.
  2. So số trần, không quy đổi đơn vị -> `0,0018 m` bị coi là khác `1,8 mm`.

Bench nằm ở scripts/ nên phải nạp bằng importlib.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("bench_mod", GOC / "scripts" / "bench.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDocSo:
    """Đáp số viết dạng phân số hay căn thức là HỢP LỆ, phải tính chứ không bóc."""

    @pytest.mark.parametrize(
        "chuoi, mong_doi",
        [
            ("5/36", 0.138889),
            ("64/3", 21.333333),
            ("37/44", 0.840909),
            ("√73", 8.544004),
            ("sqrt(73)", 8.544004),
            ("2/4", 0.5),
        ],
    )
    def test_tinh_bieu_thuc(self, bench, chuoi, mong_doi):
        assert bench._doc_so(chuoi) == pytest.approx(mong_doi, rel=1e-4)

    @pytest.mark.parametrize(
        "chuoi, mong_doi",
        [
            ("0,628 m/s", 0.628),      # dấu phẩy thập phân kiểu Việt Nam
            ("7.73 gam", 7.73),
            ("50 Ω", 50.0),
            ("2.24 lit", 2.24),
            ("-1", -1.0),
        ],
    )
    def test_bo_duoi_don_vi(self, bench, chuoi, mong_doi):
        assert bench._doc_so(chuoi) == pytest.approx(mong_doi, rel=1e-6)


    @pytest.mark.parametrize(
        "chuoi, mong_doi",
        [
            ("2/9 e^3 + 1/9", 4.574564),        # `e` là cơ số tự nhiên, không phải ẩn
            ("3e^4/16", 10.237153),
            (r"\frac{15}{\sqrt{308}}", 0.854704),   # rac lồng \sqrt
            (r"\frac{5e^{6} + 1}{9}", 224.238219),     # ngoặc nhọn lồng trong tử
        ],
    )
    def test_dang_chinh_xac_va_latex(self, bench, chuoi, mong_doi):
        """Bài càng khó, hệ thống càng hay trả lời ở dạng chính xác thay vì thập phân.

        Đo trên bộ đề khó: 4 bài bị chấm oan vì lý do này, TẤT CẢ đều ở mức vận
        dụng cao — kéo tụt riêng nhóm đó 5,4 điểm phần trăm.
        """
        assert bench._doc_so(chuoi) == pytest.approx(mong_doi, rel=1e-4)

    def test_chuoi_rong(self, bench):
        assert bench._doc_so("") is None
        assert bench._doc_so("   ") is None


class TestChamSoCoDonVi:
    """Cùng một giá trị viết bằng đơn vị khác nhau phải được tính là ĐÚNG."""

    def test_met_va_milimet(self, bench):
        assert bench._cham_so("0.0018 m", 1.8, "mm") is True

    def test_cung_don_vi(self, bench):
        assert bench._cham_so("1.8 mm", 1.8, "mm") is True

    def test_ky_hieu_ohm(self, bench):
        assert bench._cham_so("50 Ω", 50.0, "Ohm") is True

    def test_sai_that_van_bi_bat(self, bench):
        """Quy đổi đơn vị không được nới tay cho đáp số sai thật."""
        assert bench._cham_so("11.2 lit", 5.6, "lit") is False
        assert bench._cham_so("800 kg/m^3", 4.0, "g/cm^3") is False

    def test_dung_sai_lam_tron(self, bench):
        assert bench._cham_so("0.63", 0.6283, "") is True       # lệch 0,3%
        assert bench._cham_so("0.70", 0.6283, "") is False      # lệch 11%


class TestChamBieuThuc:
    """Đáp số dạng biểu thức: so bằng rút gọn tượng trưng, không so chuỗi."""

    def test_khac_dang_van_tuong_duong(self, bench):
        assert bench._cham_bieu_thuc("7*(x - 2) + 15", "7*x + 1") is True

    def test_co_ve_trai(self, bench):
        assert bench._cham_bieu_thuc("y = 7*x + 1", "7*x + 1") is True

    def test_khac_that(self, bench):
        assert bench._cham_bieu_thuc("99*x + 1", "7*x + 1") is False
