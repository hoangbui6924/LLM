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

### Card đồ hoạ — đây là yếu tố quyết định

Mô hình `qwen3:4b` chiếm **2,9 GB VRAM** ở cấu hình mặc định (`num_ctx=4096`).

| Phần cứng | Tốc độ sinh | Một câu hỏi mất |
|---|---|---|
| **GPU từ 4 GB, model nằm trọn** | **74 token/giây** | **~30 giây** |
| GPU dưới 4 GB, model tràn một phần | ~25 token/giây | 1,5–2 phút |
| Chỉ CPU | 5–10 token/giây | 5–10 phút |

**Điều kiện quyết định là model có nằm TRỌN trong GPU hay không**, chứ không phải
dung lượng VRAM tuyệt đối. Kiểm tra bằng `ollama ps` — cột PROCESSOR phải ghi
**100% GPU**. Dưới 100% nghĩa là đang tràn sang CPU và mọi số đo thời gian sẽ không
khớp báo cáo.

Số liệu trong báo cáo — trung bình 30 giây, **600/600 lượt dưới mốc 45 giây** — đo
trên RTX 3060 Laptop 6 GB.

> **VRAM chật quá thì hạ tiếp:** đặt `VMA_NUM_CTX=1900` trong `.env` — mức này đã
> **đo thật**, còn 2,7 GB, độ dài lời giảng không đổi (644 chunk so với 647, cùng
> cực đại 901). Không hạ thấp hơn: nhu cầu thật ~1720 token, xuống dưới là bắt đầu
> cắt lời giảng ở những bài nhiều bước.

> **Máy mạnh cũng đừng vội đổi sang `qwen3:8b`** nếu VRAM dưới 10 GB. Model 8B nặng
> 6,0 GB, tràn 27% xuống CPU và tốc độ tụt còn 16 token/giây — chậm gấp 4,5 lần.

### Ghi chú về ổ đĩa trên Windows

Ollama lưu model vào `C:\Users\<tên bạn>\.ollama`, **không phải** thư mục dự án.
Nếu ổ C sắp đầy, hãy dọn trước khi tải model.

---

## 1. Cài phần mềm nền

### 1.1. Python

Tải tại <https://www.python.org/downloads/>.

> **Quan trọng khi cài trên Windows:** tích ô **"Add Python to PATH"** ở màn hình
> đầu tiên. Quên bước này thì mọi lệnh `python` sau đây đều báo không tìm thấy.

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

Cài xong Ollama tự chạy nền, có biểu tượng ở khay hệ thống.

```powershell
ollama --version
```

### 1.4. Git

<https://git-scm.com/downloads>

---

## 2. Lấy mã nguồn

```powershell
git clone <đường dẫn repo>
cd ViMultiAgent
```

Mọi lệnh phía dưới chạy từ thư mục `ViMultiAgent` này.

---

## 3. Tải mô hình ngôn ngữ

```powershell
ollama pull qwen3:4b
```

Khoảng **2,5 GB**, tuỳ mạng mất 5–20 phút.

```powershell
ollama list
```

Phải thấy dòng `qwen3:4b`.

---

## 4. Cài thư viện backend

```powershell
cd backend
python -m pip install -r requirements.txt
```

Khoảng 3–5 phút.

---

## 5. Cài và huấn luyện phần học sâu

Đây là bộ phân loại môn học PhoBERT — **phần nhóm tự huấn luyện**, và là yếu tố học
sâu của đề tài.

### 5.1. Cài thư viện

Hai lệnh, **đừng gộp làm một**:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ml.txt
```

> **Vì sao phải chỉ định `whl/cpu`:** gõ `pip install torch` trơn sẽ kéo về bản
> CUDA nặng khoảng 2,5 GB, và trên máy VRAM thấp nó còn tranh bộ nhớ với Ollama.
> PhoBERT chỉ 135 triệu tham số, chạy CPU mất ~50 mili giây mỗi câu — thừa nhanh.

### 5.2. Huấn luyện mô hình — BƯỚC BẮT BUỘC

Trọng số PhoBERT **không nằm trong repo** vì nặng 517 MB, vượt giới hạn 100 MB mỗi
file của GitHub. Phải tự huấn luyện lại:

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

> **Bỏ qua bước này thì sao?** Hệ thống **vẫn chạy đủ**, Router tự lùi về luật từ
> khoá. Nhưng đo được trên 150 bài: **94,7% quyết định định tuyến hiện do PhoBERT
> đảm nhiệm**. Bỏ nó đi là mất phần học sâu, và những câu không chứa từ khoá đặc
> trưng sẽ phải hỏi LLM — mỗi lần tốn thêm 2–4 giây.

Dataset đã có sẵn trong repo (`ml/data/`, 810 câu đã gán nhãn), **không cần** chạy
`build_dataset.py`.

### 5.3. Xem bảng so sánh ba phương pháp

```powershell
python ml/compare.py
```

In ra bảng đối chiếu **luật từ khoá / TF-IDF + Logistic Regression / PhoBERT**, tách
riêng nhóm câu khó. Đây là số liệu chính cho phần học sâu trong báo cáo.

---

## 6. Cấu hình — KHÔNG CẦN LÀM GÌ

Mặc định trong `core/config.py` **đã đúng** cấu hình dùng để đo mọi số liệu trong
báo cáo. Không cần tạo `.env`.

Cấu hình đang chạy:

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| `VMA_SLA_SECONDS` | `45` | mốc thời gian của đề bài |
| `VMA_AGENTS_SUY_NGHI` | *(rỗng)* | tắt chế độ suy nghĩ của Qwen3 |
| `VMA_MAX_RETRY_ROUNDS` | `0` | tắt vòng giải lại |
| `VMA_TIMEOUT_RECOMPUTE` | `20` | hạn cho bộ tính lại |

Chỉ tạo `.env` khi muốn **đổi** thứ gì đó:

```powershell
copy .env.example .env
```

File `.env.example` để mọi biến ở dạng chú thích kèm giá trị mặc định, nên copy ra
mà không sửa gì thì hành vi **giống hệt** khi không có `.env`. Cuối file có sẵn các
khối cấu hình A/B/C dùng để dựng đường đánh đổi độ chính xác – thời gian.

> Đổi `.env` xong phải **khởi động lại backend** mới có hiệu lực.

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

Nếu Ollama đã chạy nền (có biểu tượng khay hệ thống) thì **bỏ qua**:

```powershell
ollama ps
```

Không thấy gì thì chạy:

```powershell
ollama serve
```

> **Mẹo cho buổi demo:** đặt biến môi trường `OLLAMA_KEEP_ALIVE=-1` trước khi chạy
> `ollama serve`. Model sẽ nằm thường trú trong VRAM, mất hẳn 10–15 giây nạp lại ở
> câu hỏi đầu tiên.

### Cửa sổ 2 — Backend

```powershell
cd ViMultiAgent\backend
python -m uvicorn main:app --port 8000
```

Chờ đến khi hiện `Application startup complete`. Lần đầu mất thêm vài giây nạp
PhoBERT vào RAM.

**Đọc kỹ dòng backend in ra lúc khởi động** — nó cho biết phần học sâu có chạy không:

```
[ViMultiAgent] PhoBERT router: đã nạp, tầng 1 hoạt động.
```

Nếu thấy khối `CẢNH BÁO: KHÔNG có PhoBERT router` thì bạn **chưa làm bước 5.2**.
Chương trình vẫn giải được bài nên rất dễ bỏ qua — nhưng tầng học sâu đang không
chạy, và đó là phần đóng góp chính của đề tài.

### Cửa sổ 3 — Frontend

```powershell
cd ViMultiAgent\frontend
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
  "sla_seconds": 45.0,
  "tools": { "sympy": true, "units": true }
}
```

### 9.2. Chạy bộ kiểm thử

```powershell
cd backend
python -m pytest
```

Phải thấy **222 test đạt**. Bộ này không cần Ollama, chạy trong khoảng 14 giây.

### 9.3. Kiểm tra GPU

```powershell
ollama ps
```

Cột **PROCESSOR** phải ghi **100% GPU**. Dưới 100% nghĩa là model đang tràn sang
CPU và mọi số đo thời gian sẽ không khớp báo cáo.

### 9.4. Giải thử một bài

Trên giao diện, bấm nút **Lý** để điền đề mẫu rồi bấm **Giải bài**. Quan sát:

- Năm vai sáng dần: Planner → Router → Subject → Verify → Explain
- **Đáp án hiện ra trước khi lời giảng chảy xong** — hệ thống phát đáp số ngay khi
  chốt, không bắt chờ giảng bài
- Lời giải chảy chữ theo thời gian thực
- Dòng cuối báo tổng thời gian, khoảng **25–35 giây** trên máy có GPU 6 GB
- Cuối cột phải hiện thẻ **Bài tập tương tự** — bấm "Sinh bài" phải ra đề mới
  **tức thì** (không gọi LLM). Bấm lại "Bài khác" phải ra đề khác.

> **Câu hỏi đầu tiên luôn lâu bất thường** (thêm 10–15 giây) vì Ollama phải nạp
> model 2,5 GB lên GPU. Các lượt sau nhanh hơn nhiều. Đừng tưởng hệ thống treo.

### 9.5. Đo hiệu năng đầy đủ

```powershell
python scripts/bench.py --de eval/data/de_chuan.csv --so-luong 20
```

Chạy 20 bài lấy trải đều, mất khoảng **11 phút**. Kết quả mong đợi: mọi lượt dưới
45 giây, trung bình khoảng 30 giây.

Chạy trọn 150 bài thì bỏ `--so-luong 20`, mất khoảng 80 phút.

> Đừng dùng giao diện trong lúc đo — các request tranh cùng một GPU và làm sai số đo.

---

## 10. Khi gặp lỗi

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `python` không phải lệnh hợp lệ | Quên tích "Add Python to PATH" | Cài lại Python, nhớ tích ô đó |
| Cổng 8000 báo đang bận | Còn server cũ chạy nền | Xem mục 10.1 |
| Giao diện trắng ở cổng 5173 | Chưa `npm install` | Làm lại bước 7 |
| Bấm Giải bài không có phản hồi | Backend chưa chạy | Kiểm tra cửa sổ 2 và `/api/health` |
| Backend báo lỗi kết nối Ollama | Ollama chưa chạy | `ollama ps`, nếu trống thì `ollama serve` |
| Trả lời chậm hơn 60 giây | Model chạy trên CPU | `ollama ps`, xem cột PROCESSOR — dưới 100% GPU là đang tràn |
| Router luôn báo "Quyết định bằng luật" | Chưa huấn luyện PhoBERT | Làm bước 5.2 |
| `ModuleNotFoundError: torch` | Chưa cài phần học sâu | Bước 5.1 |
| `ModuleNotFoundError: underthesea` | Thiếu bộ tách từ tiếng Việt | `pip install -r requirements-ml.txt` |

### 10.1. Giải phóng cổng 8000

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id <PID vừa thấy> -Force
```

Nếu vẫn bận, nguyên nhân thường là chế độ `--reload` sinh tiến trình con giữ socket:

```powershell
Get-Process python | Select-Object Id, StartTime
Stop-Process -Id <PID> -Force
```

---

## 11. Cấu trúc thư mục

```
ViMultiAgent/
├── backend/
│   ├── agents/              8 agent + bộ điều phối
│   │   ├── manager.py       điều phối toàn luồng, phát sự kiện SSE
│   │   ├── planner.py       phân tích đề
│   │   ├── router.py        chọn môn: PhoBERT → luật → LLM
│   │   ├── math_agent.py    ─┐
│   │   ├── physics_agent.py  ├ ba Subject Agent, chung khung subject.py
│   │   ├── chemistry_agent.py┘
│   │   ├── verify_agent.py  kiểm chứng, 5 phép kiểm tất định
│   │   ├── recompute_agent.py  trích cấu trúc cho SymPy tự giải, chạy song song
│   │   ├── explain_agent.py giảng bài, streaming
│   │   └── sinh_bai_tuong_tu.py  sinh bài luyện cùng dạng, KHÔNG gọi LLM
│   ├── tools/               SymPy, hoá học, đơn vị, trọng tài số học,
│   │                        kiểm chứng tượng trưng
│   ├── memory/              memory pool: kho định lý + kho lời giải
│   ├── ml/                  dataset + huấn luyện PhoBERT
│   │   ├── data/            810 câu đã gán nhãn, chia sẵn train/val/test
│   │   └── phobert_router/  trọng số — SINH RA sau bước 5.2, KHÔNG có trong repo
│   ├── eval/                bộ đề chuẩn, 175 mẫu sinh đề, công cụ chấm mù
│   │   └── data/            3 bộ đề: chuẩn 150 · giữ riêng 150 · khó 300
│   ├── core/                schema, cấu hình, SQLite, cứu JSON
│   ├── tests/               222 test
│   ├── scripts/             bench, tiến độ, cứu log, chấm lại, soi Verify
│   └── main.py              điểm khởi động FastAPI
├── frontend/                React + TypeScript + Vite + KaTeX
├── .env.example             mẫu cấu hình (mặc định trong code đã đúng)
├── TAILIEU.md               tài liệu kỹ thuật chi tiết
└── yeucaumoi.md             đề bài gốc
```

---

## 12. Danh sách kiểm tra trước khi demo

- [ ] `ollama ps` thấy `qwen3:4b`, cột PROCESSOR ghi **100% GPU**
- [ ] `/api/health` trả `"status": "ok"` và `"sla_seconds": 45.0`
- [ ] `python -m pytest` đạt **222/222**
- [ ] Backend in `PhoBERT router: đã nạp` lúc khởi động (KHÔNG phải khối CẢNH BÁO)
- [ ] Thẻ **Bài tập tương tự** sinh được đề mới, bấm "Bài khác" ra đề khác
- [ ] Giải thử một bài mỗi môn, xem đủ năm vai chạy
- [ ] Đã hỏi trước một câu bất kỳ để Ollama nạp model — tránh lượt demo đầu bị chậm
- [ ] Nếu cần khoe phần học sâu: chạy sẵn `python ml/compare.py` và chụp lại bảng
