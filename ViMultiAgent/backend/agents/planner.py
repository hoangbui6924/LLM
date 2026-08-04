"""Planner Agent — mục 3.1.

Việc của Planner không phải giải, mà là *đọc hiểu đề*: tách dữ kiện, xác định
ẩn cần tìm, chuẩn hoá câu hỏi lộn xộn của học sinh thành phát biểu gọn gàng.
Chất lượng của toàn hệ thống phụ thuộc nặng vào bước này — Subject Agent giải
sai đề thì mọi bước sau đều vô nghĩa.
"""

from __future__ import annotations

import re

from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Plan

SYSTEM = """Bạn là Planner Agent của hệ thống giải bài tập STEM tiếng Việt.

Nhiệm vụ: PHÂN TÍCH đề bài, KHÔNG giải.

Bạn phải trả về JSON đúng schema với các trường:
- subject: "math" | "physics" | "chemistry"
- topic: chủ đề ngắn không dấu, ví dụ "tich_phan", "dao_dong_dieu_hoa", "phan_ung_oxi_hoa"
- question_type: "mcq" nếu có phương án A/B/C/D | "numeric" nếu hỏi giá trị số |
  "symbolic" nếu hỏi biểu thức | "proof" nếu yêu cầu chứng minh
- givens: danh sách dữ kiện, mỗi dữ kiện gồm symbol, value, unit, description_vi
- unknowns: đại lượng cần tìm, cùng định dạng
- choices: nếu là trắc nghiệm thì {"A": "...", "B": "...", "C": "...", "D": "..."}, không thì null
- normalized_question: phát biểu lại đề một câu, rõ ràng, giữ nguyên mọi số liệu
- steps_outline: 2-5 bước định hướng NGẮN, chỉ nêu hướng làm, tuyệt đối không tính toán
- confidence: 0..1

Quy tắc:
- Giữ nguyên đơn vị gốc, đừng tự đổi đơn vị.
- Không bịa thêm dữ kiện không có trong đề.
- Nếu đề thiếu dữ kiện, vẫn trả kết quả và hạ confidence xuống dưới 0.4.
"""

# Bắt nhanh dạng trắc nghiệm để không phụ thuộc hoàn toàn vào LLM.
_MCQ = re.compile(r"(^|\s)[ABCD][\.\)]\s", re.MULTILINE)


async def run(question: str) -> tuple[Plan, AgentSpan]:
    plan, span = await run_structured(
        name="planner",
        system=SYSTEM,
        task=f"Đề bài:\n{question}",
        out_type=Plan,
        model=config.MODEL_LIGHT,
        max_tokens=config.MAX_TOKENS_PLANNER,
    )
    if plan is None:
        # Không có Planner thì vẫn phải đi tiếp: coi như bài toán chưa phân tích.
        plan = Plan(normalized_question=question, confidence=0.0)
    plan.raw_question = question
    if not plan.normalized_question:
        plan.normalized_question = question
    # Luật cứng đè lên phán đoán của LLM khi dấu hiệu quá rõ.
    if len(_MCQ.findall(question)) >= 3:
        plan.question_type = "mcq"
    return plan, span
