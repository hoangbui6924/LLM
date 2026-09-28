# ViMultiAgent

Hệ thống đa tác tử giải bài tập **Toán THPT** bằng tiếng Việt.
Chạy **hoàn toàn ngoại tuyến**, không dùng API key của bất kỳ dịch vụ nào.

### Bộ tài liệu

| File | Trả lời câu hỏi |
|---|---|
| **README.md** (file này) | Chạy nhanh thế nào? |
| [INSTALL.md](INSTALL.md) | Cài trên máy mới thế nào? |
| [HUONGDAN.md](HUONGDAN.md) | Dùng và vận hành thế nào? API, script, cấu hình, kịch bản demo |
| [TAILIEU.md](TAILIEU.md) | Bên trong hoạt động ra sao? |
| [GIAITRINH.md](GIAITRINH.md) | Giải trình cho hội đồng: dataset, thời gian train, đối chiếu chỉ số |

---

## 1. Cần có sẵn trên máy

| Thứ | Bản đang dùng | Kiểm tra bằng lệnh |
|---|---|---|
| Python | 3.13 | `python --version` |
| Node.js | 22 | `node -v` |
| Ollama | 0.32+ | `ollama --version` |

Nếu thiếu Ollama: tải tại <https://ollama.com/download>.

---

## 2. Cài lần đầu

Xem hướng dẫn đầy đủ ở **[INSTALL.md](INSTALL.md)** — có cả yêu cầu phần cứng,
cách cài phần học sâu, bảng tra lỗi và danh sách kiểm tra trước khi demo.

Tóm tắt cho ai đã quen:

```powershell
ollama pull qwen3:4b

cd backend
python -m pip install -r requirements.txt
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ml.txt
python ml/train_phobert.py          # ~12 phút, sinh ra mô hình PhoBERT

cd ../frontend
npm install

cd ..
copy .env.example .env
```

## 3. Khởi động

### Cách thường dùng — bấm một file

Bấm đúp **`chay.bat`** ở thư mục gốc. Nó tự làm bốn việc: đặt `OLLAMA_MODELS`,
bật Ollama nếu chưa chạy, build giao diện nếu chưa có `frontend/dist`, rồi khởi
động backend và mở trình duyệt.

Mở <http://localhost:8000>. Đóng cửa sổ terminal là tắt chương trình.

Cả giao diện lẫn API nằm chung cổng 8000 — backend tự phục vụ `frontend/dist`,
nên **không cần chạy Vite song song** nữa.

> **Model nằm ở ổ E**, không phải thư mục mặc định `C:\Users\...\.ollama`.
> Chạy Ollama bằng tay thì phải đặt trước:
> `$env:OLLAMA_MODELS = "E:\DeepLearning\Ollama\models"`
> Thiếu biến này Ollama sẽ báo không có model và đòi tải lại 2,5 GB.

### Cách thủ công

```powershell
# 1. Ollama (bỏ qua nếu đã chạy nền, kiểm bằng `ollama ps`)
$env:OLLAMA_MODELS = "E:\DeepLearning\Ollama\models"
ollama serve

# 2. Build giao diện — chỉ cần làm lại khi sửa frontend
cd E:\DeepLearning\LLM\ViMultiAgent\frontend
npm run build

# 3. Backend, phục vụ luôn giao diện
cd ..\backend
python -m uvicorn main:app --port 8000
```

Chờ đến khi thấy dòng `Application startup complete`. Lần khởi động đầu mất thêm
vài giây để nạp PhoBERT vào RAM.

Kiểm tra: mở <http://localhost:8000/api/health> — phải thấy JSON có `"status":"ok"`.

### Chế độ phát triển giao diện

Khi đang sửa frontend và cần nạp nóng, chạy thêm Vite ở cửa sổ riêng:

```powershell
cd E:\DeepLearning\LLM\ViMultiAgent\frontend
npm run dev     # cổng 5173, tự chuyển tiếp /api sang cổng 8000
```

Mở <http://localhost:5173>. Backend vẫn phải chạy sẵn ở cổng 8000.

---

## 4. Dùng thử

Trang chủ có ba nút **Đại số / Giải tích / Hình học** điền sẵn câu hỏi mẫu. Bấm **Giải bài**
rồi quan sát:

* thanh tiến trình sáng dần qua từng agent: Planner → Router → Subject → Verify → Explain
* thẻ **Bài tập tương tự** ở cuối: sinh đề luyện cùng dạng, đáp án bảo đảm đúng
* lời giải chảy chữ theo thời gian thực ở khung dưới
* dòng cuối báo tổng thời gian và có đạt mốc KPI không

Gõ `Ctrl + Enter` trong ô nhập để gửi nhanh.

---

## 5. Khi có lỗi

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Backend trả lỗi 500` | Ollama chưa chạy | Mở Ollama, chạy `ollama ps` để xác nhận |
| Cổng 8000 báo bận | Còn server cũ đang chạy | `Get-NetTCPConnection -LocalPort 8000` rồi `Stop-Process -Id <PID>` |
| Trang trắng ở 5173 | Chưa `npm install` | Chạy lại `npm install` |
| Trả lời rất chậm | Model tràn khỏi GPU | `ollama ps` xem cột PROCESSOR; dưới 100% GPU là đang chạy một phần trên CPU |
| Lần hỏi đầu lâu bất thường | Ollama đang nạp model | Bình thường, mất 8–15 giây; các lượt sau nhanh hơn nhiều |

---

## 6. Chạy kiểm thử và đo đạc

```powershell
cd E:\DeepLearning\LLM\ViMultiAgent\backend

# Kiểm thử các công cụ tất định (không cần Ollama)
python -m pytest

# Đo hiệu năng thật, có chấm đúng/sai tự động
python scripts/bench.py --n 3

# So sánh ba phương pháp phân loại môn học
python ml/compare.py
```

---

## 7. Cấu trúc thư mục

```
ViMultiAgent/
├── backend/
│   ├── agents/          8 agent: planner, router, 3 subject, verify, explain,
│   │                    recompute, sinh bài tương tự
│   │   ├── manager.py   điều phối toàn luồng, phát sự kiện SSE
│   │   └── base.py      lớp vỏ chung dựng trên AutoGen + Ollama
│   ├── tools/           SymPy, hoá học, đơn vị, trọng tài số học
│   ├── ml/              dataset + PhoBERT phân loại môn học
│   ├── core/            schema, cấu hình, SQLite
│   ├── api/routes.py    REST + SSE
│   └── main.py          điểm khởi động FastAPI
├── frontend/            React + TypeScript + Vite, hiển thị Markdown + KaTeX
└── yeucaumoi.md         đề bài gốc
```

---

## 8. Điều chỉnh cấu hình

Sửa trong file `.env` ở thư mục gốc:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `VMA_MODEL_HEAVY` | `qwen3:4b` | Mô hình cho Subject Agent và Verify |
| `VMA_MODEL_LIGHT` | `qwen3:4b` | Mô hình cho Planner, Router, Explain |
| `VMA_SLA_SECONDS` | `45` | Mốc thời gian mục tiêu cho một lượt hỏi |
| `VMA_MAX_RETRY_ROUNDS` | `0` | Số lần Verify được bắt giải lại (mặc định tắt) |
| `VMA_AGENTS_SUY_NGHI` | *(rỗng)* | Agent nào được bật chế độ suy nghĩ của Qwen3 |

Đổi `.env` xong phải **khởi động lại backend** thì mới có hiệu lực.

Bảng đầy đủ mọi biến, kèm hậu quả đo được khi bật/tắt từng cờ: xem
[HUONGDAN.md](HUONGDAN.md) mục 5.
