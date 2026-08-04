"""Đối chứng A0/A1 — một tác tử duy nhất.

Bảng kết quả của báo cáo chỉ có ý nghĩa khi so được với thứ gì đó. A0 (một model,
chain-of-thought, không công cụ, không kiểm chứng) là mức sàn: nó trả lời câu hỏi
"toàn bộ bộ máy đa tác tử có thật sự đáng công không?".

A1 (self-consistency) là đối chứng khó hơn và quan trọng hơn: nó trả lời "hay chỉ
cần lấy mẫu nhiều lần rồi bỏ phiếu là đủ?". Nếu A1 sát A7 thì luận điểm của đề tài yếu.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel

from vimultiagent.core.llm import LLMClient
from vimultiagent.core.prompts import BASELINE_COT_SYSTEM, BASELINE_COT_USER
from vimultiagent.core.schemas import Trace


class CoTOut(BaseModel):
    reasoning_vi: str = ""
    final_answer: str = ""
    mcq_choice: str | None = None


async def single_cot(problem: str, profile: str | None = None) -> dict[str, Any]:
    """A0 — một lượt gọi LLM, không công cụ, không kiểm chứng."""
    trace = Trace(strategy="baseline_cot", profile=profile or "cloud_default")
    async with LLMClient(profile=profile) as client:
        messages = [
            {"role": "system", "content": BASELINE_COT_SYSTEM},
            {"role": "user", "content": BASELINE_COT_USER.format(problem=problem)},
        ]
        try:
            # Dùng cấu hình model của solver_math cho MỌI miền — baseline không
            # được hưởng lợi từ việc định tuyến chuyên ngành, đó chính là điều đang đo.
            out, spans = await client.chat_json("solver_math", messages, CoTOut, profile=profile)
            trace.spans.extend(spans)
            return {
                "final_answer": out.final_answer,
                "mcq_choice": out.mcq_choice,
                "explanation_text": out.reasoning_vi,
                "verdict": None,
                "trace": trace,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "final_answer": "", "mcq_choice": None, "explanation_text": "",
                "verdict": None, "trace": trace, "error": f"{type(e).__name__}: {e}",
            }


async def self_consistency(
    problem: str, n: int = 5, profile: str | None = None
) -> dict[str, Any]:
    """A1 — lấy mẫu n lần ở nhiệt độ cao rồi bỏ phiếu đa số theo đáp số."""
    trace = Trace(strategy=f"baseline_sc{n}", profile=profile or "cloud_default")
    async with LLMClient(profile=profile) as client:
        messages = [
            {"role": "system", "content": BASELINE_COT_SYSTEM},
            {"role": "user", "content": BASELINE_COT_USER.format(problem=problem)},
        ]

        async def one(temp: float) -> CoTOut | None:
            try:
                out, spans = await client.chat_json(
                    "solver_math", messages, CoTOut, profile=profile, temperature=temp
                )
                trace.spans.extend(spans)
                return out
            except Exception:  # noqa: BLE001
                return None

        # Nhiệt độ phải KHÁC NHAU, nếu không cache sẽ trả về cùng một kết quả n lần
        # và "self-consistency" trở thành một phép đo vô nghĩa.
        temps = [0.3 + 0.15 * i for i in range(n)]
        outs = [o for o in await asyncio.gather(*[one(t) for t in temps]) if o is not None]

    if not outs:
        return {"final_answer": "", "mcq_choice": None, "explanation_text": "",
                "verdict": None, "trace": trace, "error": "tất cả các mẫu đều lỗi"}

    votes: dict[str, int] = {}
    for o in outs:
        key = (o.mcq_choice or o.final_answer or "").strip().lower()
        votes[key] = votes.get(key, 0) + 1
    winner = max(votes, key=lambda k: votes[k])
    best = next(o for o in outs if (o.mcq_choice or o.final_answer or "").strip().lower() == winner)

    return {
        "final_answer": best.final_answer,
        "mcq_choice": best.mcq_choice,
        "explanation_text": best.reasoning_vi,
        "verdict": None,
        "trace": trace,
        "error": None,
        "meta": {"votes": votes, "agreement": votes[winner] / len(outs), "n": len(outs)},
    }
