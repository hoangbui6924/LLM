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
SLA_SECONDS = _float("VMA_SLA_SECONDS", 45.0)
# Một lượt gọi CÓ suy nghĩ tốn 24-40 giây, gấp 5 lần lượt không suy nghĩ.
AGENT_TIMEOUT = _float("VMA_AGENT_TIMEOUT", 60.0)
# Hạn riêng cho bộ tính lại. Vai này nay chỉ TRÍCH XUẤT cấu trúc bài toán nên chạy
# hết ~5 giây; 20 giây là rộng rãi. Trước đây nó phải tự suy luận ra đáp số và cần
# tới 55 giây — xem ghi chú ở AGENTS_SUY_NGHI bên dưới.
TIMEOUT_RECOMPUTE = _float("VMA_TIMEOUT_RECOMPUTE", 20.0)

# Agent nào được bật chế độ suy nghĩ của Qwen3. MẶC ĐỊNH TẮT HẾT.
#
# Bộ tính lại nay chỉ TRÍCH XUẤT cấu trúc bài toán để SymPy tự giải, nó không còn
# phải suy luận nên không cần suy nghĩ. Bật lại thì vai này tốn 41,6 giây thay vì
# 5,1 và TRỞ THÀNH đường găng — đo được 149/150 bài có recompute chậm hơn Subject
# Agent, tức cơ chế chạy song song mất hết tác dụng.
#
# ĐỪNG bật cho Subject Agent: đo được nó làm MỌI THỨ TỆ ĐI — 1/6 đúng thay vì 3/9,
# và 5/6 lượt trả lời giải rỗng. Khối <think> tính chung vào hạn mức num_predict,
# ăn hết 1500-2000 token nên phần JSON bị cắt cụt và parse hỏng.
#
# Planner, Router, Explain không suy luận số học nên bật cho chúng là đốt thời gian
# vô ích.
AGENTS_SUY_NGHI = {
    a.strip()
    for a in os.getenv("VMA_AGENTS_SUY_NGHI", "").split(",")
    if a.strip()
}
# Số vòng Subject -> Verify -> giải lại. 1 nghĩa là được sửa đúng một lần.
# MẶC ĐỊNH TẮT. Đo A/B trên cùng 20 bài: có vòng giải lại 17/20 đúng, không có
# 18/20 — nó cứu được 1 bài nhưng làm hỏng 2, và tốn thêm 5 giây mỗi lượt.
# Nguyên nhân: vòng này do Verify kích hoạt, mà Verify báo oan 18-28%, nên phần lớn
# lần giải lại là đi SỬA MỘT LỜI GIẢI VỐN ĐÃ ĐÚNG.
# Đặt 1 để bật lại — mã nguồn vòng sửa sai vẫn còn nguyên.
MAX_RETRY_ROUNDS = _int("VMA_MAX_RETRY_ROUNDS", 0)

# Loại bỏ kết quả tính lại còn DỞ DANG.
#
# ĐO ĐƯỢC trên bộ đề 150 bài: cơ chế cứu đáp án kích hoạt 22 lần, cứu đúng 8 bài
# nhưng LÀM HỎNG 10 bài — lỗ ròng. Sáu ca hỏng có chung một khuôn mẫu: bộ tính lại
# trả về nguyên hàm chưa thay cận (`x*(3*x + 4)`) hoặc chính hàm số chưa tìm min
# (`x + 25/x`), trong khi đề hỏi MỘT CON SỐ. `KetQua.co_gia_tri` coi mọi biểu thức
# khác rỗng là hợp lệ, nên Manager lấy thứ dở dang đó đè lên đáp số ĐÚNG.
#
# Bật cờ này thì: đề hỏi đáp số bằng số mà kết quả còn ký hiệu tự do => coi như bộ
# tính lại bó tay, không dùng. Đề hỏi biểu thức (phương trình tiếp tuyến) thì vẫn
# nhận bình thường.
#
# Đặt 0 để tắt, dùng khi cần đối chứng A/B với mốc nền.
LOC_TINH_LAI_DO_DANG = os.getenv("VMA_LOC_TINH_LAI_DO_DANG", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)

# Còn ít hơn ngần này giây thì không khởi động vòng giải lại nữa: một vòng tốn
# ~20 giây (Subject + Verify) và Explain phía sau cần thêm ~15 giây.
NGUONG_GIAI_LAI = _float("VMA_NGUONG_GIAI_LAI", 40.0)

# Bỏ bước hỏi LLM của Verify khi các phép kiểm TẤT ĐỊNH đã đủ căn cứ.
#
# ĐO ĐƯỢC trên 150 bài ở cấu hình C: lượt gọi LLM của Verify tốn 6,5 giây, trong
# khi tỉ lệ phát hiện sai của nó chỉ 31,2% — nó gần như không mang thêm thông tin.
# Có 106/150 bài mà mọi phép kiểm tất định đều sạch; bỏ qua LLM ở đúng những bài
# đó cắt trung bình 4,6 giây mỗi lượt.
#
# Điều kiện bỏ qua CỐ Ý CHẶT: không chỉ cần "không có phép kiểm nào hỏng" mà còn
# phải có bộ tính lại độc lập XÁC NHẬN đáp số. Không có xác nhận độc lập thì việc
# "mọi phép kiểm đều đạt" có thể chỉ nghĩa là chẳng phép kiểm nào chạy được.
BO_QUA_LLM_REVIEW = os.getenv("VMA_BO_QUA_LLM_REVIEW", "1").strip().lower() not in (
    "0", "false", "no",
)

# ---- Memory pool (mục 2 của đề bài) ---------------------------------------
#
# Hai nửa bật/tắt riêng vì rủi ro rất khác nhau:
#
# * Kho định lý — nội dung soạn sẵn, cố định, chỉ chèn công thức chuẩn SGK vào
#   prompt. Rủi ro thấp, lợi ích rõ: mô hình 4B nhớ công thức không đáng tin.
#
# * Kho lời giải — tích luỹ từ chính những lượt đã qua kiểm chứng. Đây là thứ
#   khiến hệ thống khá lên khi dùng nhiều. Rủi ro cao hơn: ví dụ mẫu lệch đề có
#   thể dẫn model đi sai, và nếu vừa GHI vừa ĐỌC trong cùng một lần đo thì độ
#   chính xác trôi dần theo thời gian, làm phép đo mất tính dừng.
#   Đặt VMA_LUU_LOI_GIAI_MAU=0 để đo trên một kho đứng yên.
DUNG_KHO_DINH_LY = os.getenv("VMA_DUNG_KHO_DINH_LY", "1").strip().lower() not in (
    "0", "false", "no",
)
DUNG_KHO_LOI_GIAI = os.getenv("VMA_DUNG_KHO_LOI_GIAI", "1").strip().lower() not in (
    "0", "false", "no",
)
LUU_LOI_GIAI_MAU = os.getenv("VMA_LUU_LOI_GIAI_MAU", "1").strip().lower() not in (
    "0", "false", "no",
)

TEMPERATURE = _float("VMA_TEMPERATURE", 0.2)
# HẠ từ 8192 xuống 4096. Bộ nhớ đệm ngữ cảnh tỉ lệ thuận với tham số này và nó ăn
# VRAM thật: `ollama ps` báo 3,3 GB ở 8192 nhưng chỉ 2,9 GB ở 4096, trong khi trọng
# số model chỉ 2,5 GB.
#
# ĐO ĐƯỢC nhu cầu thật: prompt dài nhất (Subject Agent có memory pool) là ~620
# token, cộng trần đầu ra 1100 thành ~1720 token. 4096 vẫn dư 2,4 lần.
#
# Đo 20 bài ở 4096: thời gian 30,5s so với 30,0s ở 8192, model vẫn nằm TRỌN trong
# GPU. Tiết kiệm 400 MB VRAM mà không mất gì — đủ để máy 4 GB chạy được.
#
# Nếu thấy lời giải bị cắt giữa chừng ở bài rất dài thì nới lại lên 8192.
NUM_CTX = _int("VMA_NUM_CTX", 4096)

# Trần token đầu ra cho từng vai. Đây là công cụ giữ SLA hiệu quả nhất: ở tốc độ
# đo được ~74 token/giây, tổng 2100 token của cả luồng rơi vào khoảng 28 giây.
# Cắt quá tay thì lời giải bị cụt giữa chừng, nên các con số dưới đây là mức đủ
# rộng cho bài THPT thông thường.
# ĐỪNG HẠ XUỐNG 250. Đã thử và ĐO ĐƯỢC hậu quả trên cùng 20 bài:
#
#     Planner 400 -> 18/20 đúng (90,0%), Subject Agent chạy 12,4s
#     Planner 250 -> 13/20 đúng (65,0%), Subject Agent chạy  7,7s
#
# Mất 5 bài để đổi lấy 2,6 giây. Subject Agent nhanh lên KHÔNG phải vì nó giỏi hơn
# mà vì nó nhận được ít thông tin hơn — Planner bị cắt cụt nên `givens`, `unknowns`
# và `steps_outline` thiếu, có lúc JSON hỏng hẳn và rơi về bản dự phòng rỗng.
#
# Vận dụng cao tụt từ 2/2 xuống 0/2. Chất lượng đọc đề quyết định mọi thứ phía sau;
# đây là chỗ tiết kiệm token đắt nhất trong cả luồng.
MAX_TOKENS_PLANNER = _int("VMA_MAX_TOKENS_PLANNER", 400)
MAX_TOKENS_ROUTER = _int("VMA_MAX_TOKENS_ROUTER", 150)
# Bật suy nghĩ thì khối <think> ăn vào cùng ngân sách num_predict, nên phải
# nới trần cho Subject và bộ tính lại, nếu không lời giải bị cắt cụt giữa chừng.
MAX_TOKENS_SUBJECT = _int("VMA_MAX_TOKENS_SUBJECT", 1100)
MAX_TOKENS_VERIFY = _int("VMA_MAX_TOKENS_VERIFY", 350)
# NỚI từ 700 lên 900. ĐO ĐƯỢC trên 150 bài: 81/150 lời giảng (54%) chạm đúng trần
# 700 token, tức bị cắt giữa chừng. Chỉ số 2 của đề tài là điểm giáo viên chấm cho
# lời giảng — đưa một bài giảng cụt cho người chấm thì hỏng chỉ số đó chắc chắn.
#
# Giá phải trả: ~2,7 giây mỗi lượt. Đổi lại vừa cắt được 4,6 giây ở bước bỏ LLM
# review của Verify, nên tổng thời gian vẫn giảm.
MAX_TOKENS_EXPLAIN = _int("VMA_MAX_TOKENS_EXPLAIN", 900)
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
