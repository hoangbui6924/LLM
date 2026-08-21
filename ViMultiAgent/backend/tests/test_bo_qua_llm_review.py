"""Kiểm đường tắt của Verify — bỏ bước hỏi LLM khi phép kiểm tất định đã đủ căn cứ.

Vì sao có đường tắt: đo trên 150 bài ở cấu hình C, lượt gọi LLM của Verify tốn 6,5
giây nhưng tỉ lệ phát hiện sai chỉ 31,2% — gần như không thêm thông tin. Có
106/150 bài mà mọi phép kiểm tất định đều sạch.

Vì sao phải kiểm kỹ: đây là thay đổi có thể âm thầm cho lời giải SAI đi qua. Điều
kiện đi tắt cố ý chặt — ngoài "không phép kiểm nào hỏng" còn phải có bộ tính lại
ĐỘC LẬP xác nhận đáp số. Thiếu vế thứ hai thì "mọi phép kiểm đều đạt" có thể chỉ
nghĩa là chẳng phép kiểm nào chạy được.
"""

from __future__ import annotations

import asyncio

import pytest

from agents import verify_agent
from agents.recompute_agent import KetQua
from core import config
from core.schemas import Plan, Solution, SolutionStep


def _sol(dap_an: str = "0.1", expr: str = "n = 5.6/56", kq: str = "0.1") -> Solution:
    return Solution.model_construct(
        steps=[SolutionStep(id=1, goal_vi="Tính đạo hàm", expression=expr, result=kq)],
        final_answer=dap_an,
        confidence=0.8,
    )


def _plan() -> Plan:
    return Plan(
        subject="dai_so",
        topic="dao_ham",
        normalized_question="Tính đạo hàm của y = x^2 tại x = 0,05",
        raw_question="Tính đạo hàm của y = x^2 tại x = 0,05",
    )


def _chay(plan, sol, doc_lap):
    return asyncio.run(verify_agent.run(plan, sol, doc_lap))


class TestDiTat:
    def test_khop_doc_lap_thi_khong_goi_llm(self, monkeypatch):
        """Bộ tính lại xác nhận + không phép kiểm nào hỏng => PASS ngay, span None."""
        monkeypatch.setattr(config, "BO_QUA_LLM_REVIEW", True)

        def _khong_duoc_goi(*a, **kw):
            raise AssertionError("Đã đi tắt thì KHÔNG được gọi LLM")

        monkeypatch.setattr(verify_agent, "run_structured", _khong_duoc_goi)

        report, span = _chay(_plan(), _sol("0.1"), KetQua(gia_tri=0.1, unit=""))
        assert report.verdict == "PASS"
        assert span is None, "đi tắt thì không có span vì không gọi model"


class TestKhongDuocDiTat:
    """Bốn tình huống bắt buộc phải hỏi LLM, không được tự cho qua."""

    def test_khong_co_bo_tinh_lai(self, monkeypatch):
        """Không có xác nhận độc lập => 'mọi phép kiểm đạt' không đủ căn cứ."""
        monkeypatch.setattr(config, "BO_QUA_LLM_REVIEW", True)
        goi = {"n": 0}

        async def _gia(*a, **kw):
            goi["n"] += 1
            return None, None

        monkeypatch.setattr(verify_agent, "run_structured", _gia)
        _chay(_plan(), _sol("0.1"), None)
        assert goi["n"] == 1, "không có bộ tính lại thì PHẢI hỏi LLM"

    def test_bo_tinh_lai_khong_ra_gia_tri(self, monkeypatch):
        monkeypatch.setattr(config, "BO_QUA_LLM_REVIEW", True)
        goi = {"n": 0}

        async def _gia(*a, **kw):
            goi["n"] += 1
            return None, None

        monkeypatch.setattr(verify_agent, "run_structured", _gia)
        _chay(_plan(), _sol("0.1"), KetQua())     # rỗng, không tính được
        assert goi["n"] == 1

    def test_doc_lap_lech_dap_so(self, monkeypatch):
        """Bộ tính lại ra số KHÁC => phải hỏi LLM, và kết luận là FAIL."""
        monkeypatch.setattr(config, "BO_QUA_LLM_REVIEW", True)
        goi = {"n": 0}

        async def _gia(*a, **kw):
            goi["n"] += 1
            return None, None

        monkeypatch.setattr(verify_agent, "run_structured", _gia)
        report, _ = _chay(_plan(), _sol("0.1"), KetQua(gia_tri=99.0, unit=""))
        assert goi["n"] == 1
        assert report.verdict == "FAIL"

    def test_tat_co_thi_luon_goi_llm(self, monkeypatch):
        """Cờ tắt => quay về hành vi cũ, dùng khi cần đối chứng A/B."""
        monkeypatch.setattr(config, "BO_QUA_LLM_REVIEW", False)
        goi = {"n": 0}

        async def _gia(*a, **kw):
            goi["n"] += 1
            return None, None

        monkeypatch.setattr(verify_agent, "run_structured", _gia)
        _chay(_plan(), _sol("0.1"), KetQua(gia_tri=0.1, unit=""))
        assert goi["n"] == 1


class TestLoiGiaiRongVanBiBat:
    def test_khong_co_buoc_nao(self, monkeypatch):
        """Lời giải rỗng phải FAIL trước cả đường tắt, không tiêu token nào."""
        monkeypatch.setattr(config, "BO_QUA_LLM_REVIEW", True)
        monkeypatch.setattr(
            verify_agent, "run_structured",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("không được gọi")),
        )
        rong = Solution.model_construct(steps=[], final_answer="", confidence=0.0)
        report, span = _chay(_plan(), rong, KetQua(gia_tri=0.1))
        assert report.verdict == "FAIL"
        assert span is None
