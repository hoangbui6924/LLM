# Hướng dẫn cài đặt ViMultiAgent

Dành cho người lấy dự án về máy mới. Làm tuần tự từ trên xuống, khoảng **30–45 phút**,
phần lớn là chờ tải.

Hệ thống chạy **hoàn toàn ngoại tuyến sau khi cài xong** — không cần API key của
bất kỳ dịch vụ nào. Chỉ cần mạng lúc tải thư viện và mô hình.

---

## 0. Máy cần đáp ứng gì

### Bắt buộc

| Thứ | Yêu cầu | Ghi chú |
|---|---|---|
| Hệ điều hành | Windows 10/11, macOS, hoặc Linux | Hướng dẫn này viết cho Windows |
| Ổ trống | **12 GB** | Model 2,5 GB + thư viện + PhoBERT 0,5 GB |
| RAM | 8 GB, nên có 16 GB | |
| Python | **3.11 trở lên** | Đang phát triển trên 3.13 |
| Node.js | **20 trở lên** | Đang phát triển trên 22 |

### Card đồ hoạ

Không có GPU **vẫn chạy được**, chỉ chậm. Số đo thực tế trên RTX 3060 Laptop 6 GB:

| Phần cứng | Tốc độ sinh | Một câu hỏi mất |
|---|---|---|
| GPU 6 GB, model nằm trọn | 74 token/giây | **70–80 giây** |
| GPU 6 GB, model 8B tràn 27% sang CPU | 16 token/giây | ~250 giây |
| Chỉ CPU | 5–10 token/giây | 5–10 phút |

Mốc thời gian mục tiêu của đề tài là **150 giây**. Máy có GPU từ 6 GB VRAM trở lên
thì đạt thoải mái.

---

## 1. Cài phần mềm nền

### 1.1. Python

Tải tại <https://www.python.org/downloads/>.

> **Quan trọng khi cài trên Windows:** tích ô **“Add Python to PATH”** ở màn hình
> đầu tiên. Quên bước này thì mọi lệnh `python` sau đây đều báo không tìm thấy.

Kiểm tra:

```powershell
python --version
```

Phải hiện `Python 3.11.x` trở lên.

### 1.2. Node.js

Tải bản **LTS** tại <https://nodejs.org/>.

```powershell
node -v
npm -v
```

### 1.3. Ollama

Đây là phần chạy mô hình ngôn ngữ trên máy. Tải tại <https://ollama.com/download>.

Cài xong Ollama tự chạy nền, có biểu tượng ở khay hệ thống. Kiểm tra:

```powershell
ollama --version
```

### 1.4. Git

<https://git-scm.com/downloads>

---

## 2. Lấy mã nguồn

```powershell
git clone https://github.com/hoangbui6924/LLM.git
cd LLM\ViMultiAgent
```

Mọi lệnh phía dưới chạy từ thư mục `ViMultiAgent` này.

---

## 3. Tải mô hình ngôn ngữ

```powershell
ollama pull qwen3:4b
```

Khoảng **2,5 GB**, tuỳ mạng mất 5–20 phút. Đây là mô hình sinh lời giải.

Kiểm tra:

```powershell
ollama list
```

Phải thấy dòng `qwen3:4b`.

> **Máy có GPU từ 10 GB VRAM trở lên** thì nên dùng thêm `ollama pull qwen3:8b`
> để lời giải chính xác hơn, rồi sửa `.env` ở bước 6. Máy 6 GB thì **đừng** —
> model 8B tràn một phần sang CPU và chậm gấp 4,5 lần.

---

## 4. Cài thư viện backend

```powershell
cd backend
python -m pip install -r requirements.txt
```

Khoảng 3–5 phút.

---

## 5. Cài phần học sâu (tuỳ chọn nhưng nên làm)

Đây là bộ phân loại môn học PhoBERT — phần nhóm tự huấn luyện. **Bỏ qua cũng
được**, hệ thống vẫn chạy đủ và Router tự lùi về luật từ khoá, chỉ kém chính xác
hơn ở những câu không có từ khoá đặc trưng.

### 5.1. Cài thư viện

Hai lệnh, **đừng gộp làm một**:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ml.txt
```

> **Vì sao phải chỉ định `whl/cpu`:** gõ `pip install torch` trơn sẽ kéo về bản
> CUDA nặng khoảng 2,5 GB, và trên máy VRAM thấp nó còn tranh bộ nhớ với Ollama.
> PhoBERT chỉ 135 triệu tham số, chạy CPU mất 40 mili giây mỗi câu — thừa nhanh.

### 5.2. Huấn luyện mô hình

Trọng số PhoBERT **không nằm trong repo** vì nặng 515 MB, vượt giới hạn 100 MB
mỗi file của GitHub. Phải tự huấn luyện lại:

```powershell
python ml/train_phobert.py
```

Mất khoảng **12 phút trên CPU**. Lần đầu tải thêm mô hình nền PhoBERT ~540 MB.
Không cần tắt Ollama vì việc này chạy trên CPU.

Kết quả mong đợi, in ra cuối màn hình:

```
Độ chính xác trên test: 0.94
  seed       47/47 = 1.0000
  template   67/67 = 1.0000
  hard       36/45 = 0.8000
```

Dataset đã có sẵn trong repo (`ml/data/`), **không cần** chạy `build_dataset.py`.
Chỉ chạy lệnh đó nếu muốn dựng lại dữ liệu từ đầu.

### 5.3. Xem bảng so sánh ba phương pháp

```powershell
python ml/compare.py
```

In ra bảng đối chiếu luật từ khoá / TF-IDF + Logistic Regression / PhoBERT, tách
riêng nhóm câu khó. Đây là số liệu chính cho phần học sâu trong báo cáo.

---

## 6. Tạo file cấu hình

Từ thư mục `ViMultiAgent`:

```powershell
copy .env.example .env
```

**Không cần sửa gì** — mọi giá trị mặc định đều chạy được.

Vài tham số đáng biết khi cần chỉnh:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `VMA_MODEL_HEAVY` | `qwen3:4b` | Model cho Subject Agent và Verify |
| `VMA_MODEL_LIGHT` | `qwen3:4b` | Model cho Planner, Router, Explain |
| `VMA_SLA_SECONDS` | `150` | Mốc thời gian mục tiêu một lượt hỏi |
| `VMA_MAX_RETRY_ROUNDS` | `1` | Số lần Verify được bắt giải lại |

> Đổi `.env` xong phải **khởi động lại backend** mới có hiệu lực.
>
> Máy khoẻ (VRAM ≥ 10 GB) thì đổi cả hai dòng model sang `qwen3:8b`. **Đừng đặt
> hai dòng khác model nhau** nếu VRAM không chứa nổi cả hai — Ollama sẽ nạp đi
> nạp lại, mỗi lần mất ~10 giây, chậm hơn nhiều so với dùng chung một model.

---

## 7. Cài thư viện frontend

```powershell
cd ..\frontend
npm install
```

Khoảng 2–3 phút.

---

## 8. Chạy chương trình

Cần **ba** thứ chạy cùng lúc. Mở ba cửa sổ PowerShell riêng.

### Cửa sổ 1 — Ollama

Nếu Ollama đã chạy nền (có biểu tượng khay hệ thống) thì **bỏ qua**. Kiểm tra bằng:

```powershell
ollama ps
```

Không thấy gì thì chạy:

```powershell
ollama serve
```

### Cửa sổ 2 — Backend

```powershell
cd LLM\ViMultiAgent\backend
python -m uvicorn main:app --port 8000
```

Chờ đến khi hiện `Application startup complete`. Lần đầu mất thêm vài giây nạp
PhoBERT vào RAM.

### Cửa sổ 3 — Frontend

```powershell
cd LLM\ViMultiAgent\frontend
npm run dev
```

Mở trình duyệt tại <http://localhost:5173>.

---

## 9. Kiểm tra cài đặt thành công

### 9.1. Backend sống chưa

Mở <http://localhost:8000/api/health>, phải thấy:

```json
{
  "status": "ok",
  "model_heavy": "qwen3:4b",
  "sla_seconds": 150.0,
  "tools": { "sympy": true, "units": true }
}
```

### 9.2. Chạy bộ kiểm thử

```powershell
cd backend
python -m pytest
```

Phải thấy **58 test đạt**. Bộ này không cần Ollama, chạy trong khoảng 20 giây.

### 9.3. Giải thử một bài

Trên giao diện, bấm nút **Lý** để điền đề mẫu rồi bấm **Giải bài**. Quan sát:

- Năm vai sáng dần: Planner → Router → Subject → Verify → Explain
- Lời giải chảy chữ theo thời gian thực
- Đáp án hiện to bên cột phải kèm nhãn *Đã kiểm chứng*
- Dòng cuối báo tổng thời gian, khoảng 70–90 giây trên máy có GPU

**Câu hỏi đầu tiên luôn lâu bất thường** (thêm 10–15 giây) vì Ollama phải nạp
model 2,5 GB lên GPU. Các lượt sau nhanh hơn nhiều. Đừng tưởng hệ thống treo.

### 9.4. Đo hiệu năng đầy đủ

```powershell
python scripts/bench.py --n 3
```

Chạy 9 lượt trên ba môn, tự chấm đúng sai và in thống kê. Mất khoảng 12 phút.
Đừng dùng giao diện trong lúc này — các request tranh cùng một GPU và làm sai số đo.

---

## 10. Khi gặp lỗi

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `python` không phải lệnh hợp lệ | Quên tích “Add Python to PATH” | Cài lại Python, nhớ tích ô đó |
| Cổng 8000 báo đang bận | Còn server cũ chạy nền | Xem mục 10.1 |
| Giao diện trắng ở cổng 5173 | Chưa `npm install` | Làm lại bước 7 |
| Bấm Giải bài không có phản hồi | Backend chưa chạy | Kiểm tra cửa sổ 2 và `/api/health` |
| Backend báo lỗi kết nối Ollama | Ollama chưa chạy | `ollama ps`, nếu trống thì `ollama serve` |
| Trả lời cực chậm (trên 3 phút) | Model chạy trên CPU | `ollama ps`, xem cột PROCESSOR — dưới 100% GPU là đang tràn |
| Router luôn báo “Quyết định bằng luật” | Chưa huấn luyện PhoBERT | Làm bước 5.2, hoặc bỏ qua nếu không cần |
| `ModuleNotFoundError: torch` | Chưa cài phần học sâu | Bước 5.1, hoặc bỏ qua — hệ thống vẫn chạy |

### 10.1. Giải phóng cổng 8000

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id <PID vừa thấy> -Force
```

Nếu vẫn bận sau khi dừng, nguyên nhân thường là chế độ `--reload` sinh tiến trình
con giữ socket. Dừng luôn tiến trình `python.exe` còn lại:

```powershell
Get-Process python | Select-Object Id, StartTime
Stop-Process -Id <PID> -Force
```

---

## 11. Cấu trúc thư mục

```
ViMultiAgent/
├── backend/
│   ├── agents/              7 agent + bộ điều phối
│   │   ├── manager.py       điều phối toàn luồng, phát sự kiện SSE
│   │   ├── planner.py       phân tích đề
│   │   ├── router.py        chọn môn: PhoBERT → luật → LLM
│   │   ├── math_agent.py    ─┐
│   │   ├── physics_agent.py  ├ ba Subject Agent, chung khung subject.py
│   │   ├── chemistry_agent.py┘
│   │   ├── verify_agent.py  kiểm chứng
│   │   ├── recompute_agent.py  tính lại độc lập, chạy song song
│   │   └── explain_agent.py giảng bài, streaming
│   ├── tools/               SymPy, hoá học, đơn vị, trọng tài số học
│   ├── ml/                  dataset + huấn luyện PhoBERT
│   │   ├── data/            810 câu đã gán nhãn, chia sẵn train/val/test
│   │   └── phobert_router/  trọng số — SINH RA sau bước 5.2, không có trong repo
│   ├── core/                schema, cấu hình, SQLite, cứu JSON
│   ├── tests/               58 test
│   ├── scripts/bench.py     đo hiệu năng có chấm điểm tự động
│   └── main.py              điểm khởi động FastAPI
├── frontend/                React + TypeScript + Vite + KaTeX
├── .env.example             mẫu cấu hình
└── yeucaumoi.md             đề bài gốc
```

---

## 12. Danh sách kiểm tra trước khi demo

- [ ] `ollama ps` thấy `qwen3:4b`, cột PROCESSOR ghi **100% GPU**
- [ ] `/api/health` trả `"status": "ok"`
- [ ] `python -m pytest` đạt 58/58
- [ ] Giải thử một bài mỗi môn, xem đủ năm vai chạy
- [ ] Đã hỏi trước một câu bất kỳ để Ollama nạp model — tránh lượt demo đầu bị chậm
- [ ] Nếu cần khoe phần học sâu: chạy sẵn `python ml/compare.py` và chụp lại bảng
