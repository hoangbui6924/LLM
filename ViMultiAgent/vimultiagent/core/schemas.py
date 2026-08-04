"""Hợp đồng dữ liệu giữa các tác tử.

Nguyên tắc: KHÔNG tác tử nào truyền văn bản tự do cho tác tử khác. Mọi thông điệp
đều là một model có kiểu ở đây. Đây là điểm mượn từ MetaGPT (structured message)
và là thứ duy nhất giữ cho hệ thống debug được khi có 6 tác tử cùng chạy.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Kiểu cơ bản
# ---------------------------------------------------------------------------

Domain = Literal["math", "physics", "chemistry"]
QuestionType = Literal["mcq", "numeric", "symbolic", "proof"]


class _NullTolerant(BaseModel):
    """Coi `null` như chuỗi rỗng cho các trường văn bản.

    Model nhỏ (3B chạy cục bộ) rất hay trả `"final_answer": null` thay vì `""`.
    Pydantic mặc định từ chối, gây retry rồi hỏng cả lời giải — mất hàng chục giây
    cho một khác biệt không có ý nghĩa gì. Chấp nhận cả hai dạng.
    """

    @model_validator(mode="before")
    @classmethod
    def _none_to_empty(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for name, field in cls.model_fields.items():
            if data.get(name, "") is None and field.annotation is str:
                data[name] = ""
        return data


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class Quantity(BaseModel):
    """Một đại lượng trích từ đề bài. Tách value/unit là có chủ đích: lỗi đơn vị
    là nguồn sai phổ biến nhất của Vật lý, và chỉ bắt được khi đơn vị là dữ liệu
    có cấu trúc chứ không nằm lẫn trong chuỗi."""

    symbol: str = Field(description="ký hiệu, vd 'v_0'")
    value: float | None = Field(default=None)
    unit: str | None = Field(default=None, description="vd 'm/s'")
    description_vi: str = Field(default="")


# ---------------------------------------------------------------------------
# 1. ANALYZER
# ---------------------------------------------------------------------------


class ProblemSpec(_NullTolerant):
    domain: Domain
    subtopic: str = Field(default="", description="vd 'dao_dong_dieu_hoa'")
    question_type: QuestionType = "numeric"
    givens: list[Quantity] = Field(default_factory=list)
    unknowns: list[Quantity] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    choices: dict[str, str] | None = None
    normalized_latex: str = ""
    subgoals: list[str] = Field(default_factory=list)
    ambiguity_flags: list[str] = Field(
        default_factory=list,
        description="đề thiếu dữ kiện / mơ hồ — cho phép hệ thống hỏi lại thay vì đoán bừa",
    )
    confidence: float = 0.5

    # không do LLM sinh, orchestrator gắn vào sau
    raw_text: str = ""
    routed_by: Literal["llm", "prm_router"] = "llm"


# ---------------------------------------------------------------------------
# 2. RETRIEVER
# ---------------------------------------------------------------------------


class KnowledgeChunk(BaseModel):
    id: str
    domain: Domain
    subtopic: str
    title: str
    content: str
    applicable_when: str = ""
    pitfalls: str = ""
    score: float = 0.0


class SolvedExample(BaseModel):
    id: str
    domain: Domain
    subtopic: str
    problem: str
    solution_sketch: str          # tóm tắt ngắn — dùng làm few-shot lúc chạy
    final_answer: str
    score: float = 0.0
    # Văn bản ĐẦY ĐỦ của từng bước, ghép bằng đúng hàm mà PRM dùng lúc suy luận.
    # Không có trường này thì `solution_sketch` (vốn chỉ nối goal_vi) là thứ duy nhất
    # chảy vào dữ liệu huấn luyện PRM — tức model học trên văn bản trơ và bị hỏi trên
    # văn bản có LaTeX. Kế hoạch "trộn lời giải thật vào" sẽ hỏng âm thầm vì lý do đó.
    steps: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    knowledge: list[KnowledgeChunk] = Field(default_factory=list)
    examples: list[SolvedExample] = Field(default_factory=list)
    backend: str = "hybrid"


# ---------------------------------------------------------------------------
# 3. SOLVER
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    result: str = ""
    error: str | None = None
    duration_ms: float = 0.0
    flags: dict[str, Any] = Field(
        default_factory=dict,
        description="Cờ kiểm chứng đã bóc sẵn (satisfied/conserved/compatible/...). "
        "Verifier tầng T1 đọc trường này thay vì parse chuỗi — kết luận tất định "
        "phải là dữ liệu có kiểu, không phải văn bản.",
    )


class SolutionStep(_NullTolerant):
    id: int
    goal_vi: str = Field(description="bước này nhằm làm gì, bằng tiếng Việt")
    knowledge_ref: list[str] = Field(
        default_factory=list,
        description="id chunk kiến thức đã dùng — vừa để truy vết, vừa là nhãn "
        "huấn luyện cho phần fine-tune embedding sau này",
    )
    expression_latex: str = ""
    result_latex: str = ""
    justification_vi: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class Solution(_NullTolerant):
    steps: list[SolutionStep] = Field(default_factory=list)
    final_answer: str = ""
    final_answer_latex: str = ""
    mcq_choice: str | None = None
    unit: str | None = None
    self_confidence: float = 0.5

    def as_plain_text(self) -> str:
        """Dạng phẳng để đưa vào Verifier / PRM."""
        lines = []
        for s in self.steps:
            lines.append(f"Bước {s.id}: {s.goal_vi}")
            if s.expression_latex:
                lines.append(f"  Biến đổi: {s.expression_latex}")
            if s.result_latex:
                lines.append(f"  Kết quả: {s.result_latex}")
            if s.justification_vi:
                lines.append(f"  Lý do: {s.justification_vi}")
        lines.append(f"Đáp án: {self.final_answer}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. VERIFIER
# ---------------------------------------------------------------------------

CheckType = Literal[
    "prm",           # T0 — model huấn luyện, rẻ nhất
    "prm_advisory",  # T0 ở chế độ tham khảo — KHÔNG có quyền bác bỏ, không được
                     # hiển thị như một tầng đã kiểm chứng đạt (xem verifier.verify_t0)
    "symbolic",      # T1 — SymPy
    "dimensional",   # T1 — Pint
    "conservation",  # T1 — bảo toàn nguyên tố (Hoá)
    "substitution",  # T1 — thế ngược vào đề
    "independent",   # T2 — model khác họ giải lại
    "stepwise",      # T3 — model khác họ soát từng bước
]


class VerdictItem(BaseModel):
    step_id: int | None = None
    check_type: CheckType
    passed: bool
    detail_vi: str = ""
    score: float | None = None


class VerificationReport(BaseModel):
    verdict: Verdict = Verdict.UNCERTAIN
    items: list[VerdictItem] = Field(default_factory=list)
    first_error_step: int | None = None
    suggested_fix_vi: str | None = None
    independent_answer: str | None = None
    agreement: bool = False
    confidence: float = 0.5

    def feedback_for_solver(self) -> str:
        """Phản hồi đưa ngược lại Solver ở vòng repair. Phải cụ thể — nói 'sai rồi'
        chung chung thì Solver chỉ diễn đạt lại cùng lỗi cũ."""
        parts: list[str] = []
        if self.first_error_step is not None:
            parts.append(f"Lời giải sai bắt đầu từ BƯỚC {self.first_error_step}.")
        for it in self.items:
            if not it.passed and it.detail_vi:
                loc = f" (bước {it.step_id})" if it.step_id is not None else ""
                parts.append(f"- [{it.check_type}]{loc} {it.detail_vi}")
        if self.suggested_fix_vi:
            parts.append(f"Gợi ý sửa: {self.suggested_fix_vi}")
        if self.independent_answer:
            parts.append(
                f"Một lời giải độc lập cho đáp án khác: {self.independent_answer}. "
                "Hãy kiểm tra lại xem ai đúng."
            )
        return "\n".join(parts) if parts else "Lời giải chưa được xác nhận."


# ---------------------------------------------------------------------------
# 5. EXPLAINER
# ---------------------------------------------------------------------------


class ExplainStep(_NullTolerant):
    title_vi: str
    narrative_vi: str
    latex: str = ""
    why_vi: str = ""


class Explanation(_NullTolerant):
    restated_problem_vi: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[ExplainStep] = Field(default_factory=list)
    final_answer_vi: str = ""
    sanity_check_vi: str = ""
    common_mistakes: list[str] = Field(default_factory=list)
    practice_hint: str = ""


# ---------------------------------------------------------------------------
# Vết thực thi — đầu ra HẠNG NHẤT, không phải log phụ.
# Toàn bộ số liệu độ trễ trong báo cáo lấy từ đây.
# ---------------------------------------------------------------------------


class AgentSpan(BaseModel):
    agent: str
    model: str | None = None
    started_at: float = 0.0
    duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    ok: bool = True
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    # --- Vì sao lượt gọi này lâu -------------------------------------------
    # Không có ba trường này thì phần lớn độ trễ là hộp đen: một lượt kiểm chứng
    # đo được 73,2 giây trong khi chỉ sinh vài trăm token, và không có cách nào
    # biết đó là chờ hạn mức, thử lại schema, hay model thật sự chậm. Ba nguyên
    # nhân đó đòi ba cách xử lý hoàn toàn khác nhau.
    attempts: int = 1                      # số lần gọi HTTP thực tế
    wait_ms: float = 0.0                   # thời gian NGỦ vì backoff 429
    retry_reasons: list[str] = Field(default_factory=list)


class Trace(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = Field(default_factory=time.time)
    spans: list[AgentSpan] = Field(default_factory=list)
    strategy: str = "balanced"
    profile: str = "cloud_default"
    repair_rounds: int = 0
    cache_hit: bool = False

    @property
    def total_ms(self) -> float:
        return (time.time() - self.started_at) * 1000.0

    @property
    def total_cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.spans)

    @property
    def total_tokens(self) -> int:
        return sum(s.prompt_tokens + s.completion_tokens for s in self.spans)

    def by_agent_ms(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for s in self.spans:
            out[s.agent] = out.get(s.agent, 0.0) + s.duration_ms
        return out


# ---------------------------------------------------------------------------
# Kết quả cuối — F(q) -> (a, E, v, c, τ)
# ---------------------------------------------------------------------------


class SolveResult(BaseModel):
    spec: ProblemSpec | None = None          # phân tích đề
    solution: Solution | None = None         # a — đáp án + các bước
    explanation: Explanation | None = None   # E — lời giải sư phạm
    verification: VerificationReport | None = None  # v
    confidence: float = 0.0                  # c
    trace: Trace = Field(default_factory=Trace)  # τ
    warning_vi: str | None = None            # gắn khi verify thất bại sau max_repair
    error: str | None = None
