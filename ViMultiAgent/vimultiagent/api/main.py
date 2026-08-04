"""FastAPI + SSE.

Dùng SSE chứ không WebSocket: luồng dữ liệu ở đây một chiều (server -> client),
SSE tự động kết nối lại, và không cần thư viện phía client. Ít mã hơn, ít hỏng hơn.

Chạy:  python -m uvicorn vimultiagent.api.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..core.config import get_settings
from ..graph.orchestrator import Orchestrator

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"

app = FastAPI(title="ViMultiAgent", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class SolveRequest(BaseModel):
    problem: str
    strategy: str | None = None
    profile: str | None = None


@app.get("/")
async def index() -> FileResponse:
    f = FRONTEND / "index.html"
    if not f.exists():
        raise HTTPException(404, "Chưa có frontend/index.html")
    return FileResponse(f)


@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    from ..memory.store import get_store

    providers = s.available_providers()
    usable = [k for k, v in providers.items() if v]
    return {
        "status": "ok" if usable else "no_provider",
        "profile": s.profile,
        "strategy": s.strategy,
        "providers": providers,
        "usable_providers": usable,
        "memory": get_store(use_dense=False).stats(),
        "hint": (
            None
            if usable
            else "Chưa có provider nào dùng được. Điền GROQ_API_KEY vào .env, "
            "hoặc đặt VMA_PROFILE=local_offline nếu đang chạy Ollama."
        ),
    }


@app.post("/api/solve")
async def solve(req: SolveRequest) -> dict:
    """Giải không streaming — tiện cho script và kiểm thử."""
    if not req.problem.strip():
        raise HTTPException(400, "Đề bài trống")
    orch = Orchestrator(profile=req.profile, strategy=req.strategy)
    result = await orch.solve(req.problem)
    return result.model_dump(mode="json")


@app.post("/api/solve/stream")
async def solve_stream(req: SolveRequest) -> EventSourceResponse:
    """Giải có streaming — mỗi tác tử bắt đầu/kết thúc phát một sự kiện.

    Đây là thứ làm cho tính 'đa tác tử' NHÌN THẤY ĐƯỢC khi demo, thay vì chỉ là
    một câu khẳng định trong slide.
    """
    if not req.problem.strip():
        raise HTTPException(400, "Đề bài trống")

    async def gen():
        orch = Orchestrator(profile=req.profile, strategy=req.strategy)
        t0 = time.time()
        try:
            async for event in orch.stream(req.problem):
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            yield {
                "event": "error",
                "data": json.dumps(
                    {"type": "error", "message": f"{type(e).__name__}: {e}",
                     "elapsed_ms": (time.time() - t0) * 1000},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(gen())


@app.get("/api/examples")
async def examples() -> list[dict]:
    """Đề mẫu cho nút bấm nhanh lúc demo — đừng gõ tay trước hội đồng."""
    return [
        {
            "domain": "physics",
            "label": "Vật lý — Con lắc lò xo",
            "problem": "Một con lắc lò xo gồm vật nhỏ khối lượng 400 g và lò xo có độ cứng "
                       "100 N/m dao động điều hòa. Chu kỳ dao động của con lắc là bao nhiêu?\n"
                       "A. 0,4 s\nB. 0,2 s\nC. 0,63 s\nD. 0,1 s",
        },
        {
            "domain": "math",
            "label": "Toán — Tích phân",
            "problem": "Tính tích phân I = ∫ từ 0 đến 3 của (x² + 2x) dx.\n"
                       "A. 18\nB. 15\nC. 9\nD. 12",
        },
        {
            "domain": "chemistry",
            "label": "Hóa — Kim loại + axit",
            "problem": "Cho 5,6 gam Fe tác dụng hoàn toàn với dung dịch HCl dư. "
                       "Thể tích khí H₂ thu được ở điều kiện tiêu chuẩn là bao nhiêu?\n"
                       "A. 2,24 lít\nB. 1,12 lít\nC. 3,36 lít\nD. 4,48 lít",
        },
        {
            "domain": "physics",
            "label": "Vật lý — Giao thoa ánh sáng",
            "problem": "Trong thí nghiệm Young về giao thoa ánh sáng, hai khe cách nhau 1 mm, "
                       "màn quan sát cách hai khe 2 m, ánh sáng đơn sắc có bước sóng 600 nm. "
                       "Khoảng vân giao thoa là bao nhiêu?",
        },
        {
            "domain": "math",
            "label": "Toán — Cực trị hàm số",
            "problem": "Cho hàm số y = x³ - 3x² + 2. Tìm giá trị cực đại của hàm số.",
        },
    ]
