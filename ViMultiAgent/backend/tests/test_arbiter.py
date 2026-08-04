"""Kiểm thử trọng tài số học.

Module `arbiter` GHI ĐÈ lời giải, nên rủi ro lớn nhất không phải bỏ sót lỗi mà là
**sửa nhầm một bước đúng**. Phần lớn test dưới đây kiểm đúng chiều đó: những
trường hợp trọng tài PHẢI để yên.
"""

from __future__ import annotations

from core.schemas import Solution, SolutionStep
from tools import arbiter


def _sol(*buoc: tuple[str, str], dap_an: str = "") -> Solution:
    return Solution.model_construct(
        steps=[
            SolutionStep(id=i, goal_vi="", expression=e, result=r)
            for i, (e, r) in enumerate(buoc, start=1)
        ],
        final_answer=dap_an,
        confidence=0.5,
    )


class TestSuaLoiThat:
    def test_sai_dau(self):
        """Đúng ca bài Toán đã đo: 3-6+2 = -1 nhưng model ghi 1."""
        sol = _sol(("3*1**2 - 6*1 + 2", "1"), dap_an="1")
        sua = arbiter.enforce(sol)
        assert len(sua) == 1
        assert sol.steps[0].result == "-1"
        assert sol.final_answer == "-1"

    def test_sai_so_hoc_thuong(self):
        sol = _sol(("5.6/56", "0.2"))
        sua = arbiter.enforce(sol)
        assert len(sua) == 1 and sol.steps[0].result == "0.1"

    def test_giu_don_vi_khi_sua(self):
        sol = _sol(("0.05*2*3.141592653589793*2", "0.314 m/s"), dap_an="0.314 m/s")
        arbiter.enforce(sol)
        assert sol.steps[0].result.endswith("m/s")
        assert sol.steps[0].result.startswith("0.628")
        assert sol.final_answer.endswith("m/s")

    def test_lay_ve_phai_cua_dang_thuc(self):
        sol = _sol(("v = 2*3", "7"))
        sua = arbiter.enforce(sol)
        assert len(sua) == 1 and sol.steps[0].result == "6"


class TestPhaiDeYen:
    """Những ca mà can thiệp là sai. Đây mới là phần quan trọng."""

    def test_lam_tron_hop_le_khong_bi_dung(self):
        # 1/3 = 0,333333... ; model ghi 0,333 là hợp lệ.
        sol = _sol(("1/3", "0.333"))
        assert arbiter.enforce(sol) == []
        assert sol.steps[0].result == "0.333"

    def test_con_ky_hieu_tu_do_thi_bo_qua(self):
        # Công thức tổng quát chưa thay số — không đủ căn cứ để kết luận.
        sol = _sol(("A*omega", "0.628"))
        assert arbiter.enforce(sol) == []

    def test_ket_qua_khong_phai_so_thi_bo_qua(self):
        sol = _sol(("2+2", "bốn"))
        assert arbiter.enforce(sol) == []

    def test_bieu_thuc_hong_khong_lam_sap(self):
        sol = _sol(("((( ", "5"))
        assert arbiter.enforce(sol) == []

    def test_buoc_rong_bo_qua(self):
        sol = _sol(("", ""), ("  ", "3"))
        assert arbiter.enforce(sol) == []

    def test_dap_an_khac_buoc_cuoi_thi_khong_dung_vao(self):
        """Bước cuối sai nhưng đáp số là con số khác — có thể model đã tự sửa.

        Ghi đè lúc này là đoán mò, phải để nguyên cho Verify xử lý.
        """
        sol = _sol(("2*3", "7"), dap_an="99")
        arbiter.enforce(sol)
        assert sol.steps[0].result == "6"
        assert sol.final_answer == "99"


class TestLatexBan:
    def test_dau_thap_phan_kieu_latex(self):
        """`0{,}397` không gỡ thì đọc thành 0 và trọng tài báo oan bước đúng."""
        sol = _sol(("0.39738", "0{,}397"))
        assert arbiter.enforce(sol) == []

    def test_dau_phay_thap_phan_viet_nam(self):
        sol = _sol(("7.73", "7,73"))
        assert arbiter.enforce(sol) == []

    def test_khoang_trang_latex(self):
        sol = _sol((r"2 \, + \, 2", "4"))
        assert arbiter.enforce(sol) == []
