"""Chạy toàn bộ pipeline với LLM giả.

Giá trị của test này: nó bắt lỗi LẮP RÁP (sai tên trường, sai luồng, sai điều kiện
vòng repair) mà không cần API key và không tốn một đồng nào. Những lỗi đó nếu để lọt
sẽ chỉ lộ ra khi đang chạy benchmark thật — lúc đó vừa tốn tiền vừa tốn thời gian.

    pytest tests/test_pipeline_mock.py -v
"""

from __future__ import annotations

import json

import pytest

from vimultiagent.core.llm import LLMClient
from vimultiagent.core.schemas import AgentSpan, Verdict
from vimultiagent.graph.orchestrator import Orchestrator

PROBLEM = "Một con lắc lò xo có khối lượng 400 g và độ cứng 100 N/m. Tính chu kỳ dao động."

ANALYZER_JSON = {
    "domain": "physics", "subtopic": "con_lac_lo_xo", "question_type": "numeric",
    "givens": [{"symbol": "m", "value": 400, "unit": "g", "description_vi": "khối lượng"},
               {"symbol": "k", "value": 100, "unit": "N/m", "description_vi": "độ cứng"}],
    "unknowns": [{"symbol": "T", "value": None, "unit": "s", "description_vi": "chu kỳ dao động"}],
    "constraints": [], "choices": None, "normalized_latex": "",
    "subgoals": ["Đổi đơn vị", "Áp dụng T = 2π√(m/k)"],
    "ambiguity_flags": [], "confidence": 0.9,
}

SOLVER_JSON = {
    "steps": [
        {"id": 1, "goal_vi": "Đổi đơn vị về hệ SI", "knowledge_ref": ["p_doi_don_vi"],
         "expression_latex": "m = 400\\,g = 0{,}4\\,kg", "result_latex": "m = 0.4 kg",
         "justification_vi": "Công thức chu kỳ yêu cầu khối lượng tính bằng kg.",
         "tool_calls": []},
        {"id": 2, "goal_vi": "Áp dụng công thức chu kỳ", "knowledge_ref": ["p_con_lac_lo_xo"],
         "expression_latex": "T = 2\\pi\\sqrt{m/k}", "result_latex": "T \\approx 0.397 s",
         "justification_vi": "Công thức chu kỳ con lắc lò xo.",
         "tool_calls": [{"tool": "check_formula_dimensions",
                         "args": {"expression": "2*pi*sqrt(0.4 kg / (100 N/m))",
                                  "expected_unit": "s"}}]},
    ],
    "final_answer": "0,397 s", "final_answer_latex": "T \\approx 0{,}397\\,s",
    "mcq_choice": None, "unit": "s", "self_confidence": 0.85,
}

VERIFIER_INDEP_JSON = {
    "reasoning_brief_vi": "T = 2π√(0,4/100) ≈ 0,397 s.",
    "final_answer": "0,397 s", "mcq_choice": None, "confidence": 0.9,
}

VERIFIER_STEP_JSON = {
    "verdict": "PASS", "first_error_step": None, "error_type": "none",
    "detail_vi": "Không phát hiện lỗi.", "suggested_fix_vi": "", "confidence": 0.88,
}

EXPLAINER_JSON = {
    "restated_problem_vi": "Bài cho khối lượng và độ cứng, hỏi chu kỳ dao động.",
    "prerequisites": ["Chu kỳ con lắc lò xo: T = 2π√(m/k)"],
    "steps": [{"title_vi": "Đổi đơn vị", "narrative_vi": "400 g = 0,4 kg.",
               "latex": "m = 0{,}4\\,kg", "why_vi": "Công thức cần đơn vị SI."},
              {"title_vi": "Thay số", "narrative_vi": "Thay vào công thức.",
               "latex": "T = 2\\pi\\sqrt{0{,}4/100}", "why_vi": "Áp dụng trực tiếp."}],
    "final_answer_vi": "T ≈ 0,397 s",
    "sanity_check_vi": "Khoảng 0,4 giây là hợp lý với con lắc lò xo thường gặp.",
    "common_mistakes": ["Quên đổi gam sang kilôgam"],
    "practice_hint": "Thử với m = 100 g, k = 40 N/m.",
}

ROUTES = {
    "analyzer": ANALYZER_JSON,
    "solver_physics": SOLVER_JSON,
    "solver_math": SOLVER_JSON,
    "solver_chemistry": SOLVER_JSON,
    "explainer": EXPLAINER_JSON,
}


@pytest.fixture(autouse=True)
def no_prm(monkeypatch):
    """Tắt tầng T0 trong mọi test mock.

    Test phải cho cùng kết quả dù máy đã huấn luyện PRM hay chưa. Để PRM tự bật khi
    thấy checkpoint sẽ khiến test đỏ/xanh tuỳ trạng thái thư mục — thứ tệ nhất
    trong một bộ test.
    """
    import vimultiagent.agents.verifier as V
    monkeypatch.setattr(V, "verify_t0", lambda spec, sol: [])


@pytest.fixture
def mock_llm(monkeypatch):
    """Thay LLMClient.chat bằng bộ định tuyến trả JSON có sẵn.

    Verifier gọi hai lần với cùng agent name 'verifier' nhưng khác system prompt,
    nên phân biệt bằng nội dung prompt — đúng như cách hệ thống thật phân biệt.
    """
    calls: list[str] = []

    async def fake_chat(self, agent, messages, **kw):  # noqa: ANN001
        calls.append(agent)
        system = messages[0]["content"]
        if agent == "verifier":
            payload = VERIFIER_INDEP_JSON if "ĐỘC LẬP" in system else VERIFIER_STEP_JSON
        else:
            payload = ROUTES.get(agent, {})
        span = AgentSpan(agent=agent, model="mock/test", duration_ms=1.0,
                         prompt_tokens=100, completion_tokens=50)
        return json.dumps(payload, ensure_ascii=False), span

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    return calls


@pytest.mark.asyncio
async def test_full_pipeline_passes(mock_llm):
    result = await Orchestrator(remember=False, strategy="balanced").solve(PROBLEM)

    assert result.error is None
    assert result.spec is not None and result.spec.domain == "physics"
    assert result.solution is not None and result.solution.final_answer == "0,397 s"
    assert result.verification is not None
    assert result.verification.verdict == Verdict.PASS
    assert result.verification.agreement is True
    assert result.explanation is not None and len(result.explanation.steps) == 2
    assert result.confidence > 0.8
    assert result.warning_vi is None


@pytest.mark.asyncio
async def test_tools_actually_run(mock_llm):
    """Solver khai báo check_formula_dimensions -> orchestrator phải THỰC SỰ chạy nó
    và Verifier T1 phải đọc được cờ kết quả."""
    result = await Orchestrator(remember=False, strategy="balanced").solve(PROBLEM)

    tool_calls = [tc for s in result.solution.steps for tc in s.tool_calls]
    assert tool_calls, "không có tool nào được chạy"
    tc = tool_calls[0]
    assert tc.ok and tc.flags.get("compatible") is True

    dim_checks = [i for i in result.verification.items if i.check_type == "dimensional"]
    assert dim_checks and all(i.passed for i in dim_checks)


@pytest.mark.asyncio
async def test_all_agents_invoked(mock_llm):
    await Orchestrator(remember=False, strategy="balanced").solve(PROBLEM)
    assert "analyzer" in mock_llm
    assert "solver_physics" in mock_llm
    assert mock_llm.count("verifier") == 2, "phải chạy cả T2 và T3"
    assert "explainer" in mock_llm


@pytest.mark.asyncio
async def test_repair_loop_triggers_on_failure(monkeypatch):
    """Verifier báo FAIL -> phải chạy vòng sửa, và cảnh báo phải xuất hiện nếu
    vẫn không sửa được."""
    fail_step = {**VERIFIER_STEP_JSON, "verdict": "FAIL", "first_error_step": 2,
                 "detail_vi": "Sai công thức.", "error_type": "formula"}
    disagree = {**VERIFIER_INDEP_JSON, "final_answer": "0,2 s"}

    async def fake_chat(self, agent, messages, **kw):  # noqa: ANN001
        system = messages[0]["content"]
        if agent == "verifier":
            payload = disagree if "ĐỘC LẬP" in system else fail_step
        else:
            payload = ROUTES.get(agent, {})
        return json.dumps(payload, ensure_ascii=False), AgentSpan(agent=agent, model="mock/test")

    monkeypatch.setattr(LLMClient, "chat", fake_chat)

    result = await Orchestrator(remember=False, strategy="balanced").solve(PROBLEM)
    assert result.verification.verdict == Verdict.FAIL
    assert result.trace.repair_rounds == 1, "phải thử sửa đúng 1 lần ở chế độ balanced"
    assert result.warning_vi is not None, "phải cảnh báo khi không kiểm chứng được"
    assert result.confidence < 0.5
    # Explainer vẫn phải chạy — thà đưa lời giải kèm cảnh báo còn hơn màn hình trắng
    assert result.explanation is not None


@pytest.mark.asyncio
async def test_fast_strategy_skips_llm_verification(mock_llm):
    """Chế độ fast chỉ dùng T1 (tất định) -> không được gọi verifier LLM lần nào."""
    await Orchestrator(remember=False, strategy="fast").solve(PROBLEM)
    assert mock_llm.count("verifier") == 0


@pytest.mark.asyncio
async def test_explainer_cannot_change_the_answer(monkeypatch):
    """Ràng buộc bất biến: Explainer chỉ diễn giải, không được sửa đáp số."""
    bad_exp = {**EXPLAINER_JSON, "final_answer_vi": "T ≈ 99 s"}

    async def fake_chat(self, agent, messages, **kw):  # noqa: ANN001
        system = messages[0]["content"]
        if agent == "verifier":
            payload = VERIFIER_INDEP_JSON if "ĐỘC LẬP" in system else VERIFIER_STEP_JSON
        elif agent == "explainer":
            payload = bad_exp
        else:
            payload = ROUTES.get(agent, {})
        return json.dumps(payload, ensure_ascii=False), AgentSpan(agent=agent, model="mock/test")

    monkeypatch.setattr(LLMClient, "chat", fake_chat)

    result = await Orchestrator(remember=False, strategy="balanced").solve(PROBLEM)
    assert "0,397" in result.explanation.final_answer_vi, \
        "đáp số của Explainer phải bị ép về đáp số đã kiểm chứng"
