"""Điểm khởi động FastAPI.

Chạy:  python -m uvicorn main:app --reload --port 8000   (từ trong thư mục backend)
"""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Cho phép `from core...`, `from agents...` khi chạy trực tiếp bằng uvicorn.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.routes import router  # noqa: E402
from core import config, db  # noqa: E402

# Bản build của giao diện. Có thư mục này thì backend tự phục vụ luôn, cả hệ thống
# gói về MỘT tiến trình trên MỘT cổng.
GIAO_DIEN = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    # Hâm nóng PhoBERT ngay lúc khởi động. Nạp mô hình vào RAM tốn ~6,7 giây; để
    # lười thì toàn bộ chi phí đó rơi vào người dùng ĐẦU TIÊN, ăn mất 15% ngân
    # sách 45 giây của họ. Các lượt sau chỉ còn ~40 ms.
    await asyncio.to_thread(_ham_nong)
    # Hâm nóng nốt model ngôn ngữ — cùng một lý do, nhưng đắt hơn nhiều.
    await _ham_nong_ollama()
    yield


def _ham_nong() -> None:
    """Nạp sẵn PhoBERT, và KÊU TO nếu không có nó.

    Vì sao phải kêu: mô hình đã fine-tune nặng 515 MB nên bị .gitignore chặn —
    GitHub từ chối mọi tệp trên 100 MB. Bản clone về vì thế KHÔNG có mô hình, và
    `classifier.available()` trả False rồi Router lùi êm ru về luật từ khoá.

    Lùi êm chính là vấn đề: máy vẫn chạy, vẫn ra đáp án, không một dòng lỗi nào —
    chỉ có tầng học sâu biến mất mà không ai biết. Một dòng cảnh báo lúc khởi động
    rẻ hơn nhiều so với việc phát hiện ra điều đó khi đang bảo vệ đồ án.
    """
    try:
        from ml import classifier

        if classifier.available():
            classifier.du_doan("Tính đạo hàm của hàm số y = x^2")
            print("[ViMultiAgent] PhoBERT router: đã nạp, tầng 1 hoạt động.")
            return
        _canh_bao_thieu_phobert("chưa có thư mục ml/phobert_router")
    except Exception as e:  # noqa: BLE001 — thiếu thư viện thì Router vẫn lùi về luật
        _canh_bao_thieu_phobert(f"nạp lỗi: {e}")


async def _ham_nong_ollama() -> None:
    """Nạp sẵn model ngôn ngữ vào VRAM trước khi có người hỏi.

    Vì sao đáng làm — P1 trong `PHUONGAN_TOCDO.md`:

    Ollama nạp model theo kiểu lười: lần gọi ĐẦU TIÊN phải đọc 2,5 GB trọng số từ
    đĩa lên VRAM, mất 8-15 giây. Toàn bộ chi phí đó rơi vào đúng lượt hỏi đầu —
    tức đúng lượt người chấm bấm khi demo. Đo được một lượt giải mất 33,8 giây
    trong đó Planner chiếm 12,6 giây, và phần lớn con số bất thường ấy nhiều khả
    năng là chi phí nạp model chứ không phải Planner chậm.

    Chuyển chi phí đó sang lúc khởi động: backend chậm thêm ~10 giây một lần, đổi
    lại mọi lượt hỏi đều gặp model đã nóng.

    Gửi `prompt` rỗng với `num_predict: 0` — Ollama hiểu đây là lệnh NẠP model chứ
    không sinh chữ, nên không tốn thời gian suy luận.

    Hỏng thì bỏ qua, tuyệt đối không chặn khởi động: máy chưa bật Ollama vẫn phải
    vào được giao diện để đọc hướng dẫn.
    """
    ten_model = list(dict.fromkeys([config.MODEL_HEAVY, config.MODEL_LIGHT]))
    try:
        import ollama

        client = ollama.AsyncClient(host=config.OLLAMA_HOST)
        for ten in ten_model:
            t0 = time.perf_counter()
            await client.generate(model=ten, prompt="", options={"num_predict": 0})
            giay = time.perf_counter() - t0
            print(f"[ViMultiAgent] Ollama: {ten} đã nạp vào VRAM ({giay:.1f}s).")
    except Exception as e:  # noqa: BLE001 — không có Ollama thì vẫn cho khởi động
        print(
            f"\n[ViMultiAgent] CẢNH BÁO: không hâm nóng được Ollama ({e}).\n"
            "  Chương trình vẫn chạy, nhưng LƯỢT HỎI ĐẦU TIÊN sẽ chậm thêm\n"
            "  8-15 giây do phải nạp model. Kiểm tra: ollama ps\n"
        )


def _canh_bao_thieu_phobert(vi_sao: str) -> None:
    print(
        f"\n[ViMultiAgent] CẢNH BÁO: KHÔNG có PhoBERT router ({vi_sao}).\n"
        "  Router sẽ chạy bằng luật từ khoá + LLM. Chương trình vẫn giải được bài,\n"
        "  nhưng định tuyến kém chính xác hơn và chậm hơn khi luật không khớp.\n"
        "  Huấn luyện lại (~15 phút, có GPU): python ml/train_phobert.py\n"
        "  Xem mục 5 trong INSTALL.md.\n"
    )


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


# ---------------------------------------------------------------------------
# Giao diện
#
# THỨ TỰ Ở ĐÂY LÀ BẮT BUỘC: `include_router` phải chạy TRƯỚC `app.mount("/")`.
# Mount vào "/" bắt mọi đường dẫn, đặt trước thì nó nuốt luôn cả `/api/...` và
# `/docs` — backend im lặng trả về index.html cho mọi lời gọi API.
#
# Có `frontend/dist` thì phục vụ nó, cả hệ thống còn MỘT tiến trình trên MỘT cổng:
# người chấm mở http://localhost:8000 là xong, không cần chạy Vite song song.
# Chưa build thì giữ nguyên endpoint JSON cũ để chế độ dev (Vite cổng 5173 proxy
# sang đây) không bị ảnh hưởng.
#
# `html=True` cho phép trả index.html khi truy cập thư mục. Giao diện không dùng
# router phía client nên chừng đó là đủ, không cần thêm SPA fallback.
if (GIAO_DIEN / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(GIAO_DIEN), html=True), name="ui")
else:

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "ViMultiAgent",
            "docs": "/docs",
            "health": "/api/health",
            "ghi_chu": "Chưa có frontend/dist — chạy `npm run build` trong thư mục frontend.",
        }
