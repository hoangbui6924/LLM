"""Hình học Agent — mục 3.3.

Phụ trách nhánh Hình học của chương trình Toán THPT: hình phẳng, hình không gian
và hình học toạ độ.
"""

from __future__ import annotations

from agents import subject
from core.schemas import AgentSpan, Plan, Solution

NAME = "hinh_hoc_agent"


async def run(plan: Plan, feedback: str | None = None) -> tuple[Solution, AgentSpan]:
    return await subject.solve("hinh_hoc", plan, feedback)
