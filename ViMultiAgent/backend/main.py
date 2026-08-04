"""Điểm khởi động FastAPI.

Chạy:  python -m uvicorn main:app --reload --port 8000   (từ trong thư mục backend)
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Cho phép `from core...`, `from agents...` khi chạy trực tiếp bằng uvicorn.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes import router  # noqa: E402
from core import config, db  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    # Hâm nóng PhoBERT ngay lúc khởi động. Nạp mô hình vào RAM tốn ~6,7 giây; để
    # lười thì toàn bộ chi phí đó rơi vào người dùng ĐẦU TIÊN, ăn mất 15% ngân
    # sách 45 giây của họ. Các lượt sau chỉ còn ~40 ms.
    await asyncio.to_thread(_ham_nong)
    yield


def _ham_nong() -> None:
    try:
        from ml import classifier

        if classifier.available():
            classifier.du_doan("Tính đạo hàm của hàm số y = x^2")
    except Exception:  # noqa: BLE001 — không có PhoBERT thì Router tự lùi về luật
        pass


app = FastAPI(
    title="ViMultiAgent",
    description="Hệ thống đa tác tử giải bài tập STEM bằng tiếng Việt.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "ViMultiAgent", "docs": "/docs", "health": "/api/health"}
