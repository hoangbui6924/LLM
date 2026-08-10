# ViMultiAgent

Hệ thống đa tác tử giải bài tập STEM (Toán – Lý – Hoá) bằng tiếng Việt.
Chạy **hoàn toàn ngoại tuyến**, không dùng API key của bất kỳ dịch vụ nào.

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

## 3. Khởi động hằng ngày

Cần **ba** thứ chạy cùng lúc. Mở ba cửa sổ terminal.

### Cửa sổ 1 — Ollama

```powershell
ollama serve
```

Nếu đã cài Ollama dạng ứng dụng nền (có biểu tượng ở khay hệ thống) thì bỏ qua
bước này, nó đã chạy sẵn. Kiểm tra:

```powershell
ollama ps
```

### Cửa sổ 2 — Backend

```powershell
cd E:\DeepLearning\ViMultiAgent\backend
python -m uvicorn main:app --port 8000
```

Chờ đến khi thấy dòng `Application startup complete`. Lần khởi động đầu mất
thêm vài giây để nạp PhoBERT vào RAM.

Kiểm tra: mở <http://localhost:8000/api/health> — phải thấy JSON có `"status":"ok"`.

### Cửa sổ 3 — Frontend

```powershell
cd E:\DeepLearning\ViMultiAgent\frontend
npm run dev
```

Mở <http://localhost:5173>.

---

## 4. Dùng thử

Trang chủ có ba nút **Toán / Lý / Hoá** điền sẵn câu hỏi mẫu. Bấm **Giải bài**
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
cd E:\DeepLearning\ViMultiAgent\backend

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
| `VMA_SLA_SECONDS` | `150` | Mốc thời gian mục tiêu cho một lượt hỏi |
| `VMA_MAX_RETRY_ROUNDS` | `1` | Số lần Verify được bắt giải lại |
| `VMA_AGENTS_SUY_NGHI` | `recompute` | Agent nào được bật chế độ suy nghĩ của Qwen3 |

Đổi `.env` xong phải **khởi động lại backend** thì mới có hiệu lực.
