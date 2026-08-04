"""SymPy làm trọng tài số học.

Module này SỬA lời giải, nên bộ test chia làm hai nửa và nửa thứ hai quan trọng hơn:
  - nửa 1: có bắt được lỗi thật không
  - nửa 2: có ĐỂ YÊN những thứ không được đụng vào không
"""

from __future__ import annotations

from vimultiagent.core.schemas import Solution, SolutionStep
from vimultiagent.tools import recompute


def _step(i: int, expr: str, res: str, goal: str = "bước") -> SolutionStep:
    return SolutionStep(id=i, goal_vi=goal, expression_latex=expr, result_latex=res)


def _sol(steps: list[SolutionStep], answer: str = "") -> Solution:
    return Solution(steps=steps, final_answer=answer)


# --- nửa 1: bắt lỗi --------------------------------------------------------


def test_bắt_sai_số_học_đơn_giản() -> None:
    bad = recompute.audit_step(_step(1, "n = 5,6/56", "0,2"))
    assert bad is not None
    assert abs(bad["computed"] - 0.1) < 1e-9
    assert abs(bad["stated"] - 0.2) < 1e-9


def test_ghi_đè_kết_quả_sai_và_giữ_đơn_vị() -> None:
    sol = _sol([_step(1, "V = 0,1 \\times 22,4", "1,12 lít")])
    fixes = recompute.enforce(sol)
    assert len(fixes) == 1
    assert sol.steps[0].result_latex == "2,24 lít"   # số sửa, đơn vị giữ


def test_hiểu_được_latex_frac() -> None:
    bad = recompute.audit_step(_step(1, "n = \\frac{5,6}{56}", "0,5"))
    assert bad is not None and abs(bad["computed"] - 0.1) < 1e-9


def test_lấy_vế_phải_của_dấu_bằng_cuối() -> None:
    bad = recompute.audit_step(_step(1, "n = m/M = 5,6/56", "0,3"))
    assert bad is not None and abs(bad["computed"] - 0.1) < 1e-9


def test_bắt_lời_giải_tự_mâu_thuẫn() -> None:
    """Đúng kiểu hỏng của bài Fe + HCl: bước cuối ra một số, đáp số là số khác."""
    sol = _sol([_step(1, "n = 5,6/56", "0,1"),
                _step(2, "V = 0,05 \\times 22,4", "1,12")], answer="2,24 lít")
    items = recompute.check_solution(sol)
    fails = [i for i in items if not i.passed]
    assert any("TỰ MÂU THUẪN" in i.detail_vi for i in fails)


# --- nửa 2: KHÔNG được đụng vào --------------------------------------------


def test_làm_tròn_hợp_lệ_không_bị_coi_là_lỗi() -> None:
    """0,39738... -> 0,397 là làm tròn đúng, không phải sai số học."""
    assert recompute.audit_step(_step(1, "T = 2*3.14159*sqrt(0.4/100)", "0,397")) is None


def test_biểu_thức_còn_ký_hiệu_thì_bỏ_qua() -> None:
    """Không quy được về số thuần thì tuyệt đối không kết luận."""
    assert recompute.audit_step(_step(1, "n = m/M", "0,1")) is None
    assert recompute.audit_step(_step(1, "V = n \\times 22,4", "2,24")) is None


def test_thiếu_dữ_liệu_thì_bỏ_qua() -> None:
    assert recompute.audit_step(_step(1, "", "0,1")) is None
    assert recompute.audit_step(_step(1, "5,6/56", "")) is None
    assert recompute.audit_step(_step(1, "biểu thức không parse được ###", "0,1")) is None


def test_bước_đúng_không_bị_sửa() -> None:
    sol = _sol([_step(1, "n = 5,6/56", "0,1 mol"),
                _step(2, "V = 0,1 \\times 22,4", "2,24 lít")], answer="2,24 lít")
    before = [s.result_latex for s in sol.steps]
    assert recompute.enforce(sol) == []
    assert [s.result_latex for s in sol.steps] == before


def test_lời_giải_đúng_cho_verdict_đạt() -> None:
    sol = _sol([_step(1, "n = 5,6/56", "0,1"),
                _step(2, "V = 0,1 \\times 22,4", "2,24")], answer="2,24 lít")
    assert all(i.passed for i in recompute.check_solution(sol))


def test_lời_giải_toàn_ký_hiệu_không_bị_báo_oan() -> None:
    """Lời giải trình bày thuần công thức là hợp lệ — không được kết luận gì."""
    sol = _sol([_step(1, "n = m/M", "n(Fe)"),
                _step(2, "V = n \\times V_{đktc}", "V")], answer="2,24 lít")
    assert all(i.passed for i in recompute.check_solution(sol))
    assert recompute.enforce(sol) == []


def test_lời_giải_rỗng_không_gây_lỗi() -> None:
    assert recompute.enforce(_sol([])) == []
    assert all(i.passed for i in recompute.check_solution(_sol([])))


def test_hiểu_dấu_thập_phân_kiểu_latex() -> None:
    r"""LaTeX bọc dấu phẩy để canh khoảng cách: `0{,}397`. Không gỡ thì đọc ra 0,
    và trọng tài báo oan lời giải đúng. Bộ test pipeline đã bắt được đúng ca này."""
    assert abs(recompute.stated_value(r"T \approx 0{,}397\,s") - 0.397) < 1e-9
    assert abs(recompute.stated_value(r"m = 400\,g = 0{,}4\,kg") - 0.4) < 1e-9


def test_không_báo_oan_lời_giải_con_lắc_thật() -> None:
    """Đúng dữ liệu của tests/test_pipeline_mock.py."""
    sol = _sol(
        [
            _step(1, r"m = 400\,g = 0{,}4\,kg", "m = 0.4 kg"),
            _step(2, r"T = 2\pi\sqrt{m/k}", r"T \approx 0.397 s"),
        ],
        answer="0,397 s",
    )
    sol.final_answer_latex = r"T \approx 0{,}397\,s"
    assert all(i.passed for i in recompute.check_solution(sol))
    assert recompute.enforce(sol) == []
