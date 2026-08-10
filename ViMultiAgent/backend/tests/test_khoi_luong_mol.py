"""Kiểm phép soát khối lượng mol — vá lỗ hổng kiến thức bảng tuần hoàn.

Ca sinh ra bộ test này: người dùng thử hệ thống rồi báo "Hoá thường sai do không
nắm vững bảng tuần hoàn nên cân bằng sai hoặc có khối lượng mol sai". Soi lại mã
nguồn thì đúng — `chem_tool.molar_mass` tồn tại và tất định, nhưng KHÔNG agent
nào gọi tới. Model 4B phải tự nhớ M(Fe3O4) = 232, và nhớ sai thì hỏng cả bài mà
không tầng kiểm chứng nào phát hiện.

Hai yêu cầu ngược chiều nhau mà phép kiểm phải thoả cùng lúc:

  * KHÔNG báo oan cách làm tròn của sách giáo khoa (Cu = 64 thay vì 63,546)
  * VẪN bắt được lỗi nhớ nhầm chất hoặc cộng sai

Ngưỡng 1,5% là chỗ đứng giữa: đo được lệch tối đa 0,71% ở Cu, còn lỗi thật
thường lệch hàng chục phần trăm.
"""

from __future__ import annotations

import pytest

from agents.verify_agent import _check_khoi_luong_mol, _don_gian_cong_thuc
from core.schemas import Solution, SolutionStep


def _sol(*bieu_thuc: str) -> Solution:
    return Solution.model_construct(
        steps=[
            SolutionStep(id=i + 1, expression=e, result="", goal_vi="", reason_vi="")
            for i, e in enumerate(bieu_thuc)
        ],
        final_answer="x",
        confidence=0.5,
    )


def _co_bat_loi(*bieu_thuc: str) -> bool:
    return any(not c.passed for c in _check_khoi_luong_mol(_sol(*bieu_thuc)))


class TestDonGianCongThuc:
    """Model viết công thức bằng cú pháp LaTeX vì prompt bảo viết LaTeX trần."""

    @pytest.mark.parametrize(
        "vao, ra",
        [
            ("Fe_3O_4", "Fe3O4"),
            ("Fe_{3}O_{4}", "Fe3O4"),
            ("H2SO4", "H2SO4"),
            ("Ca(OH)_2", "Ca(OH)2"),
            ("CuSO_4 . 5H_2O", "CuSO4.5H2O"),
        ],
    )
    def test_go_chi_so_duoi(self, vao, ra):
        assert _don_gian_cong_thuc(vao) == ra


class TestChapNhanLamTronSGK:
    """Sách giáo khoa cho H=1, O=16, Cu=64 — phải coi là ĐÚNG, không phải lỗi."""

    @pytest.mark.parametrize(
        "bieu_thuc",
        [
            "M(Fe3O4) = 232",     # chính xác 231,531
            "M(H2SO4) = 98",      # chính xác 98,072
            "M(CaCO3) = 100",     # chính xác 100,086
            "M(CuSO4) = 160",     # chính xác 159,602 — Cu lệch nhiều nhất
            "M(NaCl) = 58,5",     # dấu phẩy thập phân kiểu Việt Nam
            "M(NaOH) = 40",
        ],
    )
    def test_khong_bao_oan(self, bieu_thuc):
        assert _co_bat_loi(bieu_thuc) is False


class TestBatLoiThat:
    @pytest.mark.parametrize(
        "bieu_thuc, vi_sao",
        [
            ("M(Fe3O4) = 160", "nhầm sang Fe2O3"),
            ("M(H2SO4) = 89", "đảo chữ số"),
            ("M(NaOH) = 23", "chỉ lấy khối lượng Na"),
            ("M(CaCO3) = 56", "nhầm sang CaO"),
        ],
    )
    def test_bat_duoc(self, bieu_thuc, vi_sao):
        assert _co_bat_loi(bieu_thuc) is True, vi_sao

    def test_bao_kem_gia_tri_dung(self):
        """Phải đưa giá trị ĐÚNG vào phản hồi để vòng giải lại có cái mà sửa."""
        loi = [c for c in _check_khoi_luong_mol(_sol("M(Fe3O4) = 160")) if not c.passed]
        assert loi and "231" in loi[0].detail_vi

    def test_doc_duoc_cu_phap_latex(self):
        assert _co_bat_loi("M_{Fe_3O_4} = 160") is True


class TestKhongPhaHongViecKhac:
    def test_loi_giai_khong_nhac_khoi_luong_mol(self):
        assert _check_khoi_luong_mol(_sol("v = 2*3", "s = 10")) == []

    def test_ky_hieu_la_khong_gay_loi(self):
        # `M(x)` không phải công thức hoá học — bỏ qua, đừng ném lỗi.
        assert _check_khoi_luong_mol(_sol("M(Xyz) = 5")) == []

    def test_lap_lai_cung_chat_chi_soat_mot_lan(self):
        ks = _check_khoi_luong_mol(_sol("M(Fe3O4) = 160", "M(Fe3O4) = 160"))
        assert len([c for c in ks if not c.passed]) == 1
