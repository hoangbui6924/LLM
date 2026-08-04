"""Tác tử TRUY HỒI — không dùng LLM, nên gần như miễn phí về độ trễ.

Truy vấn được ghép từ ProblemSpec chứ không phải text đề thô: subtopic + mô tả các
đại lượng + subgoals. Sau khi Analyzer đã bóc tách, những trường này mô tả bài toán
chính xác hơn nhiều so với đề gốc vốn đầy số liệu cụ thể gây nhiễu truy hồi.
"""

from __future__ import annotations

import time

from ..core.schemas import AgentSpan, ProblemSpec, RetrievalResult
from ..memory.store import get_store


def build_query(spec: ProblemSpec) -> str:
    parts = [spec.subtopic.replace("_", " "), *spec.subgoals]
    parts += [q.description_vi for q in spec.unknowns if q.description_vi]
    parts += [q.description_vi for q in spec.givens if q.description_vi]
    query = " ".join(p for p in parts if p).strip()
    # Spec nghèo thông tin (Analyzer lỗi) -> lùi về đề gốc.
    return query if len(query) > 15 else spec.raw_text[:500]


def retrieve(
    spec: ProblemSpec, top_k_knowledge: int = 4, top_k_examples: int = 2
) -> tuple[RetrievalResult, AgentSpan]:
    t0 = time.time()
    span = AgentSpan(agent="retriever", started_at=t0)
    try:
        store = get_store()
        q = build_query(spec)
        res = RetrievalResult(
            knowledge=store.search_knowledge(
                q, domain=spec.domain, subtopic=spec.subtopic, k=top_k_knowledge
            ),
            examples=store.search_examples(q, domain=spec.domain, k=top_k_examples),
            backend=store.backend,
        )
        span.meta = {
            "query": q[:200],
            "n_knowledge": len(res.knowledge),
            "n_examples": len(res.examples),
            "backend": store.backend,
        }
    except Exception as e:  # noqa: BLE001
        res = RetrievalResult()
        span.ok = False
        span.error = str(e)[:200]
    span.duration_ms = (time.time() - t0) * 1000.0
    return res, span
