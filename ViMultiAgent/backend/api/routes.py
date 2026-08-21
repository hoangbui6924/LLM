"""REST API — cầu nối giữa React và Multi-Agent Manager.

Điểm đáng chú ý: `/api/solve` trả **SSE** chứ không phải JSON một cục. Một lượt
chạy mất 20-45 giây; nếu bắt người dùng chờ trắng màn hình suốt thời gian đó thì
sản phẩm coi như hỏng, dù đáp án có đúng. Với SSE, tiến trình từng agent và chữ
của Explain Agent chảy về ngay khi có.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from agents import manager, sinh_bai_tuong_tu
from core import config, db

router = APIRouter(prefix="/api")


class SolveRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class BaiTuongTuRequest(BaseModel):
    """Nhận sẵn `mon`/`topic` mà Planner đã xác định ở lượt giải trước.

    Cố ý không chạy lại Planner: nó tốn ~4 giây và thông tin đó đã có trong kết
    quả mà giao diện đang giữ. Nhờ vậy endpoint này trả về gần như tức thì.
    """

    mon: str = "dai_so"
    topic: str = ""
    cau_hoi_goc: str = ""
    muc: str = ""


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_heavy": config.MODEL_HEAVY,
        "model_light": config.MODEL_LIGHT,
        "ollama": config.OLLAMA_HOST,
        "sla_seconds": config.SLA_SECONDS,
        "tools": {
            "sympy": True,
        },
    }


@router.post("/solve")
async def solve(req: SolveRequest) -> EventSourceResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi rỗng.")

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            async for ev in manager.solve_stream(question):
                yield {"event": ev.get("type", "message"), "data": json.dumps(ev, ensure_ascii=False)}
        except Exception as e:  # noqa: BLE001
            yield {
                "event": "error",
                "data": json.dumps(
                    {"type": "error", "message": f"{type(e).__name__}: {e}"},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(gen())


@router.post("/solve_sync")
async def solve_sync(req: SolveRequest) -> dict[str, Any]:
    """Bản chờ trọn gói — tiện cho kiểm thử bằng curl và cho phần đo hiệu năng."""
    result = await manager.solve(req.question.strip())
    return result.model_dump(mode="json")


@router.post("/bai_tuong_tu")
async def bai_tuong_tu(req: BaiTuongTuRequest) -> dict[str, Any]:
    """Sinh một bài cùng dạng. Không gọi LLM nên tính bằng mili giây.

    Tách khỏi `/api/solve` là có chủ đích: gộp vào sẽ cộng thẳng thời gian sinh đề
    vào chỉ số độ trễ end-to-end đang đo.
    """
    bai = sinh_bai_tuong_tu.sinh(
        mon=req.mon, topic=req.topic, cau_hoi_goc=req.cau_hoi_goc, muc=req.muc
    )
    if bai is None:
        return {"co": False, "ly_do": "Chưa có mẫu đề nào cho dạng bài này."}
    return {"co": True, "bai": bai.model_dump()}


@router.get("/history")
async def history(limit: int = 20) -> list[dict[str, Any]]:
    return db.recent(min(max(limit, 1), 100))


@router.get("/stats")
async def stats() -> dict[str, Any]:
    return db.stats()
