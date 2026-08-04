"""Physics Agent — mục 3.3."""

from __future__ import annotations

from agents import subject
from core.schemas import AgentSpan, Plan, Solution

NAME = "physics_agent"


async def run(plan: Plan, feedback: str | None = None) -> tuple[Solution, AgentSpan]:
    return await subject.solve("physics", plan, feedback)
