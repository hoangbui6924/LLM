"""Hợp đồng dữ liệu giữa các agent.

Mọi agent nhận một Pydantic model và trả một Pydantic model — không agent nào truyền
"văn bản tự do" cho agent khác. Đây là thứ khiến hệ thống debug được và đo được: khi
lời giải sai, ta biết chính xác agent nào trả ra dữ liệu gì.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Subject = Literal["math", "physics", "chemistry"]
QuestionType = Literal["mcq", "numeric", "symbolic", "proof"]


class _Tolerant(BaseModel):
    """LLM hay trả `null` cho trường chuỗi. Nuốt lỗi đó thay vì để cả lượt hỏng."""

    @classmethod
    def model_validate(cls, obj: Any, **kw: Any):  # type: ignore[override]
        if isinstance(obj, dict):
            obj = {
                k: ("" if v is None and _is_str_field(cls, k) else v)
                for k, v in obj.items()
            }
        return super().model_validate(obj, **kw)


def _is_str_field(model: type[BaseModel], name: str) -> bool:
    f = model.model_fields.get(name)
    return f is not None and f.annotation is str


# ---------------------------------------------------------------------------
# 1. Planner — phân tích và chuẩn hoá đề
# ---------------------------------------------------------------------------


class Quantity(_Tolerant):
    symbol: str = ""
    value: float | None = None
    unit: str | None = None
    description_vi: str = ""


class Plan(_Tolerant):
    """Đầu ra của Planner Agent."""

    subject: Subject = "math"
    topic: str = ""                       # "dao_dong_dieu_hoa", "tich_phan"
    question_type: QuestionType = "numeric"
    givens: list[Quantity] = Field(default_factory=list)
    unknowns: list[Quantity] = Field(default_factory=list)
    choices: dict[str, str] | None = None
    normalized_question: str = ""
    steps_outline: list[str] = Field(default_factory=list)
    confidence: float = 0.5

    raw_question: str = ""                # điền lại ở tầng trên, không do LLM sinh


# ---------------------------------------------------------------------------
# 2. Router — chọn Subject Agent
# ---------------------------------------------------------------------------


class Route(BaseModel):
    subject: Subject
    agent_name: str                       # "math_agent" | "physics_agent" | ...
    reason_vi: str = ""
    confidence: float = 0.5
    # Router quyết định theo ba nguồn, xếp theo thứ tự ưu tiên:
    #   phobert — bộ phân loại học sâu do nhóm huấn luyện, ~30 ms
    #   rule    — luật từ khoá, 0 ms, dùng khi chưa huấn luyện PhoBERT
    #   llm     — hỏi mô hình ngôn ngữ, 2-4 giây, chỉ khi hai cách trên không chắc
    decided_by: Literal["phobert", "rule", "llm"] = "rule"
    # Độ tin cậy do PhoBERT trả về, để đối chiếu khi phân tích lỗi.
    phobert_confidence: float | None = None


# ---------------------------------------------------------------------------
# 3. Subject Agent — lời giải
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    result: str = ""
    error: str | None = None
    flags: dict[str, Any] = Field(default_factory=dict)


class SolutionStep(_Tolerant):
    id: int = 0
    goal_vi: str = ""                     # bước này nhằm làm gì
    expression: str = ""                  # phép biến đổi, LaTeX trần
    result: str = ""                      # kết quả bước, kèm đơn vị
    reason_vi: str = ""                   # vì sao được phép làm vậy
    tool_calls: list[ToolCall] = Field(default_factory=list)


class Solution(_Tolerant):
    # min_length=1: đo được model buột ra đáp số với steps rỗng và confidence 1.0,
    # khiến toàn bộ tầng kiểm chứng mất tác dụng vì không có gì để kiểm. Ràng buộc
    # này đi thẳng vào grammar JSON của Ollama nên model KHÔNG THỂ sinh mảng rỗng —
    # mạnh hơn mọi lời dặn trong prompt.
    steps: list[SolutionStep] = Field(default_factory=list, min_length=1)
    final_answer: str = ""                # CHỈ đáp số + đơn vị
    final_answer_latex: str = ""
    mcq_choice: str | None = None
    unit: str | None = None
    confidence: float = 0.5

    def as_text(self) -> str:
        """Dạng văn bản phẳng để đưa cho Verify Agent đọc."""
        out = []
        for s in self.steps:
            line = f"Bước {s.id}: {s.goal_vi}"
            if s.expression:
                line += f"\n  {s.expression}"
            if s.result:
                line += f"\n  => {s.result}"
            if s.reason_vi:
                line += f"\n  ({s.reason_vi})"
            out.append(line)
        out.append(f"Đáp án: {self.final_answer}")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# 4. Verify Agent
# ---------------------------------------------------------------------------

Verdict = Literal["PASS", "FAIL", "UNCERTAIN"]
CheckKind = Literal["sympy", "unit", "conservation", "consistency", "llm_review"]


class Check(BaseModel):
    kind: CheckKind
    passed: bool
    step_id: int | None = None
    detail_vi: str = ""


class VerifyReport(BaseModel):
    verdict: Verdict = "UNCERTAIN"
    checks: list[Check] = Field(default_factory=list)
    first_error_step: int | None = None
    suggestion_vi: str = ""
    confidence: float = 0.5

    def feedback(self) -> str:
        """Phản hồi gửi ngược cho Subject Agent khi phải giải lại."""
        lines = [f"Kết luận kiểm tra: {self.verdict}"]
        for c in self.checks:
            if not c.passed:
                where = f" (bước {c.step_id})" if c.step_id else ""
                lines.append(f"- [{c.kind}]{where} {c.detail_vi}")
        if self.suggestion_vi:
            lines.append(f"Gợi ý sửa: {self.suggestion_vi}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Explain Agent
# ---------------------------------------------------------------------------


class Explanation(_Tolerant):
    """Explain Agent KHÔNG sinh đáp án mới, chỉ trình bày lại cho học sinh."""

    restated_vi: str = ""
    steps_markdown: str = ""              # Markdown + LaTeX, stream thẳng ra frontend
    final_answer_vi: str = ""
    common_mistakes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Đo lường — đầu ra hạng nhất, không phải log phụ
# ---------------------------------------------------------------------------


class AgentSpan(BaseModel):
    agent: str
    model: str | None = None
    started_at: float = Field(default_factory=time.time)
    duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    ok: bool = True
    error: str | None = None
    # Vì sao lượt gọi này lâu: chờ, thử lại schema, hay model thật sự chậm.
    attempts: int = 1
    retry_reasons: list[str] = Field(default_factory=list)


class Trace(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = Field(default_factory=time.time)
    spans: list[AgentSpan] = Field(default_factory=list)
    retry_rounds: int = 0

    @property
    def total_ms(self) -> float:
        return (time.time() - self.started_at) * 1000.0

    def by_agent_ms(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for s in self.spans:
            out[s.agent] = out.get(s.agent, 0.0) + s.duration_ms
        return out

    @property
    def total_tokens(self) -> int:
        return sum(s.prompt_tokens + s.completion_tokens for s in self.spans)


class BaiTuongTu(BaseModel):
    """Bài tập cùng dạng sinh ra sau khi giải xong, để học sinh tự luyện.

    `dap_an` luôn do Python tính từ tham số của chính đề bài, không do LLM khai —
    xem `agents/sinh_bai_tuong_tu.py`. Vì vậy trường này tin được, khác hẳn đáp số
    trong `Solution` vốn phải qua cả tầng kiểm chứng mới dám tin.
    """

    de_bai: str = ""
    dap_an: str = ""
    don_vi: str = ""
    topic: str = ""
    muc_do: str = ""                      # NB | TH | VD | VDC
    goi_y: str = ""                       # công thức cần dùng, không phải lời giải
    nguon: str = "mau_tat_dinh"


class SolveResult(BaseModel):
    question: str = ""
    plan: Plan | None = None
    route: Route | None = None
    solution: Solution | None = None
    verify: VerifyReport | None = None
    explanation: Explanation | None = None
    trace: Trace = Field(default_factory=Trace)
    warning_vi: str = ""
    error: str | None = None
