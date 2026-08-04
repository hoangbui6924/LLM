"""Cấu hình chạy — đọc từ .env, có mặc định chạy được ngay khi không có .env.

Nguyên tắc: hệ thống chạy offline hoàn toàn, chỉ với Ollama trên máy. Dự án
KHÔNG dùng bất kỳ API key bên ngoài nào — không Wolfram, không Groq, không
OpenAI. Mọi năng lực đều phải tự chạy được trên máy chấm bài.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


# ---- Ollama ---------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Đo trên RTX 3060 Laptop 6 GB:
#   qwen3:8b -> 6,0 GB, chỉ nhét được 73% vào GPU -> 16,3 tok/s -> cả luồng ~80 giây
#   qwen3:4b -> 3,2 GB, nằm trọn GPU            -> 74,1 tok/s -> cả luồng ~22 giây
# KPI của đề tài là 45 giây, nên 4b là lựa chọn duy nhất chạy được trên máy này.
#
# Vì sao KHÔNG trộn 8b cho Subject và 4b cho các agent còn lại: hai model cộng lại
# 9,2 GB, vượt 6 GB VRAM. Ollama sẽ đẩy model này ra để nạp model kia, mỗi lần đổi
# tốn ~10 giây. Luồng có 4 lần đổi vai => mất trắng 40 giây chỉ để nạp.
MODEL_HEAVY = os.getenv("VMA_MODEL_HEAVY", "qwen3:4b")
MODEL_LIGHT = os.getenv("VMA_MODEL_LIGHT", "qwen3:4b")

# ---- Ngân sách thời gian --------------------------------------------------
SLA_SECONDS = _float("VMA_SLA_SECONDS", 150.0)
# Một lượt gọi CÓ suy nghĩ tốn 24-40 giây, gấp 5 lần lượt không suy nghĩ.
AGENT_TIMEOUT = _float("VMA_AGENT_TIMEOUT", 60.0)
# Bộ tính lại bật suy nghĩ nên là lượt gọi đắt nhất. ĐO ĐƯỢC trên bài Hoá: nó
# suy luận ĐÚNG tỉ lệ hợp thức nhưng mất ~31 giây, nên hạn 32 giây cắt hụt 2/3
# số lượt. Nới lên 42 giây: mất khả năng giải lại (ngưỡng 38 giây) nhưng đổi lại
# có đáp án đúng — đánh đổi đáng giá, vì vòng giải lại vốn không sửa nổi lỗi
# khái niệm.
TIMEOUT_RECOMPUTE = _float("VMA_TIMEOUT_RECOMPUTE", 55.0)

# Ngân sách 90 giây cho phép BẬT LẠI chế độ suy nghĩ của Qwen3 — thứ đã phải tắt
# khi mốc còn 45 giây. Khối <think> chính là nơi model kiểm lại phép tính, nên
# đây là đòn bẩy độ chính xác lớn nhất còn lại trên phần cứng này.
#
# Nhưng chỉ bật cho hai vai THỰC SỰ LÀM TOÁN. Planner (đọc đề), Router (phân môn)
# và Explain (diễn đạt lại) không suy luận số học, bật cho chúng là đốt 60 giây
# vô ích.
# ĐO ĐƯỢC: bật suy nghĩ cho Subject Agent làm MỌI THỨ TỆ ĐI — 1/6 đúng thay vì
# 3/9, và 5/6 lượt trả lời giải rỗng. Lý do: khối <think> tính chung vào hạn mức
# num_predict, ăn hết 1500-2000 token nên phần JSON bị cắt cụt, parse hỏng.
# Nới hạn mức lên 4000 thì mỗi lượt tốn 54 giây ở 74 tok/s, năm agent nối tiếp
# là vỡ ngân sách.
#
# Chỉ bật cho `recompute`, vì hai lý do:
#   * nó chạy SONG SONG với Subject Agent nên thời gian chồng lên nhau
#   * đầu ra chỉ là một biểu thức, hạn mức token dễ thở
# Đây đúng chỗ cần suy luận nhất: chọn công thức và tỉ lệ hợp thức.
AGENTS_SUY_NGHI = {
    a.strip()
    for a in os.getenv("VMA_AGENTS_SUY_NGHI", "recompute").split(",")
    if a.strip()
}
# Số vòng Subject -> Verify -> giải lại. 1 nghĩa là được sửa đúng một lần.
MAX_RETRY_ROUNDS = _int("VMA_MAX_RETRY_ROUNDS", 1)

# Còn ít hơn ngần này giây thì không khởi động vòng giải lại nữa: một vòng tốn
# ~20 giây (Subject + Verify) và Explain phía sau cần thêm ~15 giây.
NGUONG_GIAI_LAI = _float("VMA_NGUONG_GIAI_LAI", 40.0)

TEMPERATURE = _float("VMA_TEMPERATURE", 0.2)
NUM_CTX = _int("VMA_NUM_CTX", 8192)

# Trần token đầu ra cho từng vai. Đây là công cụ giữ SLA hiệu quả nhất: ở tốc độ
# đo được ~74 token/giây, tổng 2100 token của cả luồng rơi vào khoảng 28 giây.
# Cắt quá tay thì lời giải bị cụt giữa chừng, nên các con số dưới đây là mức đủ
# rộng cho bài THPT thông thường.
MAX_TOKENS_PLANNER = _int("VMA_MAX_TOKENS_PLANNER", 400)
MAX_TOKENS_ROUTER = _int("VMA_MAX_TOKENS_ROUTER", 150)
# Bật suy nghĩ thì khối <think> ăn vào cùng ngân sách num_predict, nên phải
# nới trần cho Subject và bộ tính lại, nếu không lời giải bị cắt cụt giữa chừng.
MAX_TOKENS_SUBJECT = _int("VMA_MAX_TOKENS_SUBJECT", 1100)
MAX_TOKENS_VERIFY = _int("VMA_MAX_TOKENS_VERIFY", 350)
MAX_TOKENS_EXPLAIN = _int("VMA_MAX_TOKENS_EXPLAIN", 700)
# Bộ tính lại chỉ viết một biểu thức, không cần dài.
# Có suy nghĩ nên cần rộng: ~1800 token cho <think> + ~200 cho biểu thức.
MAX_TOKENS_RECOMPUTE = _int("VMA_MAX_TOKENS_RECOMPUTE", 2200)

# ---- Cơ sở dữ liệu --------------------------------------------------------
DB_PATH = Path(os.getenv("VMA_DB_PATH", str(ROOT / "vimultiagent.db")))

# ---- CORS -----------------------------------------------------------------
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("VMA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
