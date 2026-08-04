"""Tác tử SINH BÀI GIẢI SƯ PHẠM.

Tách khỏi Solver có chủ đích: prompt tối ưu để RA ĐÁP ÁN ĐÚNG (ngắn, ký hiệu dày,
gọi công cụ liên tục) ngược hoàn toàn với prompt tối ưu để HỌC SINH LỚP 12 HIỂU.
Ép một tác tử làm cả hai thì hỏng cả hai.

Ràng buộc bất biến: Explainer KHÔNG được đổi đáp số. Ràng buộc này được kiểm bằng
assertion sau khi sinh, không chỉ nhắc trong prompt — nhắc trong prompt là mong đợi,
kiểm sau khi sinh mới là bảo đảm.
"""

from __future__ import annotations

from ..core.latex import clean_latex, clean_prose
from ..core.llm import LLMClient
from ..core.prompts import EXPLAINER_SYSTEM, EXPLAINER_USER
from ..core.schemas import (
    AgentSpan,
    Explanation,
    ExplainStep,
    ProblemSpec,
    RetrievalResult,
    Solution,
    VerificationReport,
)


def _knowledge_block(r: RetrievalResult | None) -> str:
    if not r or not r.knowledge:
        return ""
    body = "\n".join(f"- {c.title}: {c.content}" for c in r.knowledge[:3])
    return f"KIẾN THỨC NỀN (dùng cho mục 'cần biết trước'):\n{body}\n"


async def explain(
    client: LLMClient,
    spec: ProblemSpec,
    sol: Solution,
    retrieval: RetrievalResult | None = None,
    report: VerificationReport | None = None,
    profile: str | None = None,
) -> tuple[Explanation, list[AgentSpan]]:
    messages = [
        {"role": "system", "content": EXPLAINER_SYSTEM},
        {
            "role": "user",
            "content": EXPLAINER_USER.format(
                problem=spec.raw_text,
                final_answer=sol.final_answer or sol.mcq_choice or "",
                solution=sol.as_plain_text(),
                knowledge_block=_knowledge_block(retrieval),
            ),
        },
    ]

    degraded: str | None = None
    try:
        exp, spans = await client.chat_json("explainer", messages, Explanation, profile=profile)
    except Exception as e:  # noqa: BLE001
        # Explainer hỏng thì vẫn phải trả được thứ gì đó cho học sinh — dựng lời
        # giải thô từ các bước của Solver còn hơn trả về màn hình trắng.
        #
        # NHƯNG phải NÓI RÕ là đang ở chế độ suy giảm. Trước đây chỗ này nuốt lỗi
        # im lặng, nên khi hết quota người dùng chỉ thấy lời giải cụt lủn mà không
        # hiểu vì sao — và đi tìm lỗi ở nhầm chỗ.
        degraded = f"{type(e).__name__}: {e}"
        exp = Explanation(
            restated_problem_vi=spec.raw_text[:400],
            steps=[
                ExplainStep(
                    title_vi=s.goal_vi or f"Bước {s.id}",
                    narrative_vi=s.justification_vi,
                    latex=s.expression_latex or s.result_latex,
                    why_vi=s.justification_vi,
                )
                for s in sol.steps
            ],
            final_answer_vi=sol.final_answer,
            common_mistakes=[],
        )
        spans = []

    # Dọn LaTeX trước khi xuống frontend. Model bọc `$...$` vào trường `latex` (mà
    # frontend đã bọc `\[ \]` sẵn) hoặc viết `"\times"` một gạch (JSON nuốt thành TAB)
    # đều làm công thức hiện nguyên văn màu đỏ — đã quan sát được trên màn hình thật.
    for st in exp.steps:
        st.latex = clean_latex(st.latex)
        st.narrative_vi = clean_prose(st.narrative_vi)
        st.why_vi = clean_prose(st.why_vi)
        st.title_vi = clean_prose(st.title_vi)
    exp.restated_problem_vi = clean_prose(exp.restated_problem_vi)
    exp.final_answer_vi = clean_prose(exp.final_answer_vi)
    exp.sanity_check_vi = clean_prose(exp.sanity_check_vi)
    exp.practice_hint = clean_prose(exp.practice_hint)
    exp.prerequisites = [clean_prose(p) for p in exp.prerequisites]
    exp.common_mistakes = [clean_prose(m) for m in exp.common_mistakes]

    # Bảo đảm cứng: Explainer không được sửa đáp số.
    truth = (sol.mcq_choice or sol.final_answer or "").strip()
    if truth and truth.lower() not in (exp.final_answer_vi or "").lower():
        exp.final_answer_vi = (
            f"{sol.final_answer}"
            + (f" (Phương án {sol.mcq_choice})" if sol.mcq_choice else "")
        )

    if degraded:
        exp.common_mistakes = [
            f"⚠️ Không soạn được lời giảng đầy đủ ({degraded[:160]}). "
            "Phần dưới là các bước thô từ tác tử Giải.",
            *exp.common_mistakes,
        ]

    if report and report.verdict.value != "PASS":
        note = "⚠️ Lời giải này CHƯA được kiểm chứng độc lập — hãy đối chiếu lại với thầy cô."
        exp.common_mistakes = [note, *exp.common_mistakes]

    return exp, spans
