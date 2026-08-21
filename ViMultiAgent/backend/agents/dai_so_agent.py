"""Đại số Agent — mục 3.3.

Phụ trách nhánh Đại số & Giải tích của chương trình Toán THPT.
"""

from __future__ import annotations

from agents import subject
from core.schemas import AgentSpan, Plan, Solution

NAME = "dai_so_agent"


async def run(plan: Plan, feedback: str | None = None) -> tuple[Solution, AgentSpan]:
    return await subject.solve("dai_so", plan, feedback)
