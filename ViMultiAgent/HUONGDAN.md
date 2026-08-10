# Hướng dẫn sử dụng chi tiết ViMultiAgent

Tài liệu này nói về **cách dùng** hệ thống sau khi đã cài xong: nhập đề thế nào cho
đúng, đọc kết quả ra sao, gọi API, chạy từng công cụ dòng lệnh, chỉnh cấu hình, và
dựng lại toàn bộ số liệu trong báo cáo.

Chưa cài được thì đọc **[INSTALL.md](INSTALL.md)** trước — file này giả định hệ
thống đã chạy được.

---

## 0. Bốn tài liệu, dùng cái nào khi nào

| File | Trả lời câu hỏi | Đọc khi |
|---|---|---|
| [README.md](README.md) | Chạy nhanh thế nào? | Đã quen dự án, chỉ cần lệnh |
| [INSTALL.md](INSTALL.md) | Cài trên máy mới thế nào? | Lần đầu, hoặc máy chấm bài |
| **HUONGDAN.md** (file này) | Dùng và vận hành thế nào? | Hằng ngày, lúc demo, lúc đo đạc |
| [TAILIEU.md](TAILIEU.md) | Bên trong hoạt động ra sao? | Viết báo cáo, sửa mã nguồn, trả lời phản biện |

---

## 1. Mở máy — trình tự ba bước

Ba tiến trình phải sống cùng lúc. Thứ tự **có quan trọng**: backend cần Ollama sẵn
sàng lúc nhận câu hỏi đầu tiên.

```powershell
# 1. Ollama — bỏ qua nếu đã có biểu tượng ở khay hệ thống
ollama serve

# 2. Backend
cd E:\DeepLearning\ViMultiAgent\backend
python -m uvicorn main:app --port 8000

# 3. Frontend
cd E:\DeepLearning\ViMultiAgent\frontend
npm run dev
```

Mở <http://localhost:5173>.

### Ba dòng phải đọc lúc backend khởi động

```
[ViMultiAgent] PhoBERT router: đã nạp, tầng 1 hoạt động.
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Thấy khối `CẢNH BÁO: KHÔNG có PhoBERT router` nghĩa là **tầng học sâu không chạy**.
Hệ thống vẫn giải bài bình thường nên rất dễ bỏ qua — nhưng đó là phần đóng góp
chính của đề tài. Xử lý: chạy `python ml/train_phobert.py` (mục 5.2 của INSTALL).

### Làm nóng trước khi dùng thật

Câu hỏi đầu tiên sau khi khởi động luôn chậm hơn 10–15 giây vì Ollama phải nạp 2,5 GB
lên GPU. Trước buổi demo, hỏi trước một câu bất kỳ để "đốt" khoản này:

```powershell
curl.exe -X POST http://localhost:8000/api/solve_sync -H "Content-Type: application/json" -d "{\"question\":\"2+2 bang bao nhieu\"}"
```

Hoặc giữ model thường trú luôn:

```powershell
$env:OLLAMA_KEEP_ALIVE = "-1"
ollama serve
```

---

## 2. Dùng giao diện web

### 2.1. Bố cục màn hình

| Vùng | Nội dung |
|---|---|
| Ô nhập trên cùng | Đề bài. `Ctrl + Enter` để gửi nhanh |
| Ba nút Toán / Lý / Hoá | Điền sẵn đề mẫu — dùng khi demo |
| Cột trái | Năm vai của quy trình, sáng dần theo tiến trình |
| Đáp án | Hiện **trước khi** lời giảng chảy xong |
| Các bước giải | Từng bước có công thức KaTeX |
| Lời giảng | Chảy chữ theo thời gian thực |
| Thẻ *Bài tập tương tự* | Sinh đề luyện cùng dạng, không gọi LLM |
| Dòng cuối | Tổng thời gian và có đạt mốc KPI không |

### 2.2. Năm vai chạy theo thứ tự nào

```
Planner ──→ Router ──→ Subject Agent ──→ Verify ──→ Explain
                          │                 ▲
                          └── Recompute ────┘   (chạy SONG SONG, không hiện riêng)
```

Bộ tính lại độc lập không có ô riêng trên giao diện vì nó chạy **cùng lúc** với
Subject Agent. Khi nó và Subject Agent ra hai đáp số khác nhau, trọng tài số học
vào cuộc — lúc đó giao diện hiện thêm dòng ghi chú ở phần đáp án.

### 2.3. Viết đề bài thế nào cho hệ thống hiểu đúng

Bộ đọc đề chấp nhận văn xuôi tiếng Việt bình thường. Vài điểm **đo được là có ảnh
hưởng thật**:

| Nên | Không nên | Vì sao |
|---|---|---|
| Ghi rõ đơn vị: `v = 20 m/s` | `v = 20` | Bộ kiểm đơn vị không có gì để đối chiếu |
| Nêu rõ hỏi gì: `Tính vận tốc lúc t = 3 s` | `Vận tốc?` | Planner trích `unknowns` yếu → Subject Agent giải lệch |
| Một bài một lượt hỏi | Ba câu a, b, c trong một ô | Trần token của Subject Agent là 1100, ba câu sẽ bị cắt cụt |
| Trắc nghiệm: ghi đủ A. B. C. D. | Chỉ ghi đề, bỏ phương án | Hệ thống có trường `mcq_choice` riêng, thiếu phương án thì bỏ trống |
| Công thức hoá viết chuẩn: `Fe3O4`, `H2SO4` | `fe3o4` | `chem_tool` đọc công thức để soát khối lượng mol |

Độ dài tối đa mỗi câu hỏi: **4000 ký tự** (chặn ở tầng API).

### 2.4. Đọc phần đáp án

Ba thông tin đi kèm mỗi đáp số:

**Verdict của Verify** — `PASS` / `FAIL`:
- `PASS` không có nghĩa là chắc chắn đúng. Đo trên 150 bài, Verify **báo oan
  18–28%**, và tỉ lệ phát hiện sai của lượt hỏi LLM chỉ 31,2%.
- `FAIL` kèm cảnh báo *"Lời giải chưa qua được bước kiểm chứng"* — nên tự đối chiếu.

**Confidence** — độ tự tin, lấy từ Verify nếu có, không thì từ Subject Agent.

**Cảnh báo** — xuất hiện khi cơ chế cứu đáp án đã can thiệp, tức đáp số hiển thị
không phải thứ Subject Agent đưa ra ban đầu. Xem cơ chế ở [TAILIEU.md](TAILIEU.md)
mục 5.

> **Quy tắc thực dụng:** `PASS` + không cảnh báo + trọng tài không phải phân xử là
> tổ hợp đáng tin nhất. Có bất kỳ dấu hiệu nào trong ba thứ đó thì đọc kỹ các bước
> giải trước khi tin đáp số.

### 2.5. Thẻ *Bài tập tương tự*

Bấm **Sinh bài** → ra đề mới **tức thì** (mili giây, không gọi LLM). Bấm **Bài khác**
→ đề khác cùng dạng.

Đề sinh ra có đáp án **bảo đảm đúng** vì nó dựng từ mẫu tham số hoá rồi tính bằng
SymPy / `chem_tool`, không nhờ model. Đổi lại, nó chỉ phủ những dạng đã có mẫu — gặp
dạng lạ thì thẻ báo *"Chưa có mẫu đề nào cho dạng bài này."*

Endpoint này cố ý **tách khỏi** `/api/solve`: gộp vào sẽ cộng thời gian sinh đề vào
chỉ số độ trễ đang đo.

---

## 3. Gọi API trực tiếp

Gốc: `http://localhost:8000/api`

### 3.1. Bảng endpoint

| Method | Đường dẫn | Trả về | Dùng để |
|---|---|---|---|
| GET | `/health` | JSON | Kiểm tra backend + cấu hình đang chạy |
| POST | `/solve` | **SSE** | Giải bài, có tiến trình và streaming |
| POST | `/solve_sync` | JSON | Giải bài, chờ trọn gói — tiện cho script |
| POST | `/bai_tuong_tu` | JSON | Sinh bài luyện cùng dạng |
| GET | `/history?limit=20` | JSON | Lượt hỏi gần đây (tối đa 100) |
| GET | `/stats` | JSON | Tổng hợp: số lượt, thời gian TB, tỉ lệ PASS theo môn |

### 3.2. `/api/health` — kiểm tra nhanh nhất

```powershell
curl.exe http://localhost:8000/api/health
```

```json
{
  "status": "ok",
  "model_heavy": "qwen3:4b",
  "model_light": "qwen3:4b",
  "ollama": "http://localhost:11434",
  "sla_seconds": 45.0,
  "tools": { "sympy": true, "units": true }
}
```

Endpoint này còn là cách **xác nhận `.env` đã có hiệu lực chưa** — sửa `.env` xong,
khởi động lại backend rồi xem `sla_seconds` và `model_heavy` có đổi không.

### 3.3. `/api/solve` — luồng SSE

Mỗi sự kiện là một dòng JSON. Các loại:

| `type` | Ý nghĩa | Trường đáng chú ý |
|---|---|---|
| `agent` | Một vai bắt đầu / kết thúc | `name`, `label`, `status` |
| `recompute_info` | Bộ tính lại độc lập đã cho kết quả | |
| `arbiter` | Trọng tài số học phải phân xử hai đáp số lệch nhau | |
| `dap_an` | **Chốt đáp số**, phát trước khi giảng | `gia_tri`, `latex`, `mcq`, `verdict`, `confidence`, `warning` |
| `token` | Một mẩu chữ của lời giảng | `text` |
| `retry` | Verify bắt giải lại (mặc định tắt) | `round`, `reason` |
| `cuu_dap_an` | Cơ chế cứu đáp án đã can thiệp | |
| `done` | Kết thúc | `total_ms`, `within_sla`, `warning`, `result` |
| `error` | Có lỗi | `message` |

Sự kiện `dap_an` tách riêng khỏi `done` là một quyết định **đo được**: trước đây
frontend chỉ nhận đáp án ở `done`, tức bắt người dùng chờ thêm **10,6 giây** để đọc
một con số đã chốt xong từ trước.

### 3.4. `/api/solve_sync` — bản chờ trọn gói

```powershell
curl.exe -X POST http://localhost:8000/api/solve_sync `
  -H "Content-Type: application/json" `
  -d '{\"question\":\"Tính đạo hàm của f(x) = x^3 - 3x + 2 tại x = 2\"}'
```

Không có streaming, chờ 20–45 giây rồi trả một cục JSON. Dùng cho script và kiểm thử.

### 3.5. `/api/bai_tuong_tu`

```powershell
curl.exe -X POST http://localhost:8000/api/bai_tuong_tu `
  -H "Content-Type: application/json" `
  -d '{\"mon\":\"math\",\"topic\":\"dao_ham\",\"muc\":\"TH\"}'
```

`mon` nhận `math` / `physics` / `chemistry`. Endpoint **không chạy lại Planner** —
nó nhận sẵn `mon`/`topic` mà giao diện đang giữ từ lượt giải trước, nhờ vậy trả về
gần như tức thì.

---

## 4. Công cụ dòng lệnh

Mọi lệnh chạy từ thư mục `backend`.

### 4.1. `scripts/bench.py` — đo hiệu năng, có chấm đúng/sai tự động

```powershell
python scripts/bench.py --de eval/data/de_chuan.csv --so-luong 20
```

| Tham số | Ý nghĩa |
|---|---|
| `--de <csv>` | Bộ đề. Bỏ trống thì dùng 3 bài dựng sẵn |
| `--so-luong N` | Chỉ chạy N bài **lấy trải đều** — chạy thử nhanh |
| `--n N` | Số lượt lặp (mặc định 1) |
| `--mon math\|physics\|chemistry` | Lọc theo môn |
| `--muc NB\|TH\|VD\|VDC` | Lọc theo mức độ |
| `--out <thư mục>` | Nơi ghi CSV kết quả |

Bộ chấm không so chuỗi: nó **tính** biểu thức bằng SymPy, quy đổi đơn vị khi hai bên
ghi khác đơn vị, và rút gọn tượng trưng khi đáp án là biểu thức. `1/2`, `0,5` và
`50%` được coi là cùng một đáp số.

Thời gian tham khảo trên RTX 3060 Laptop 6 GB: **20 bài ≈ 11 phút**, trọn 150 bài
≈ 80 phút.

> **Đừng dùng giao diện trong lúc đo.** Các request tranh cùng một GPU và làm hỏng
> mọi số đo thời gian.

### 4.2. `scripts/tien_do.py` — theo dõi chiến dịch đang chạy

```powershell
python scripts/tien_do.py <đường dẫn log>
```

Đọc log của một lượt bench đang chạy và báo đã xong bao nhiêu bài, đúng bao nhiêu,
còn bao lâu. Dùng khi chạy trọn 150 bài mà không muốn ngồi nhìn.

### 4.3. `scripts/cuu_log.py` — cứu kết quả từ lượt bench bị dừng

```powershell
python scripts/cuu_log.py <log> --ra ket_qua.csv
```

Máy sập giữa chừng, hoặc lỡ bấm `Ctrl+C` ở bài thứ 130 — script này dựng lại CSV kết
quả từ log thay vì chạy lại 80 phút.

### 4.4. `scripts/cham_lai.py` — chấm lại, không chạy lại model

```powershell
python scripts/cham_lai.py ket_qua.csv --de eval/data/de_kho.csv --dung-sai 0.02
```

Cải tiến bộ đọc đáp số rồi muốn áp dụng lên kết quả cũ thì dùng cái này — không cần
tốn 80 phút chạy lại. `--dung-sai` là sai số tương đối cho phép khi so số.

### 4.5. `scripts/soi_verify.py` — chẩn đoán Verify Agent

Chạy Verify trên những bài cụ thể và in ra từng phép kiểm đạt/hỏng. Đây là **công cụ
chẩn đoán, không phải đo đạc** — dùng khi nghi Verify báo oan.

### 4.6. `ml/compare.py` — bảng so sánh ba phương pháp phân loại môn

```powershell
python ml/compare.py
```

In bảng đối chiếu **luật từ khoá / TF-IDF + Logistic Regression / PhoBERT**, tách
riêng nhóm câu khó. Đây là số liệu chính cho phần học sâu trong báo cáo — nên chạy
sẵn và chụp lại màn hình trước buổi bảo vệ.

### 4.7. `ml/train_phobert.py` — huấn luyện lại bộ phân loại

```powershell
python ml/train_phobert.py
```

~12 phút trên CPU. Chỉ cần chạy lại khi đổi dataset trong `ml/data/`.

### 4.8. Bộ công cụ đánh giá lời giảng (chỉ số 2)

```powershell
python eval/thu_loi_giang.py --so-bai 30        # bước 1: thu lời giảng
python eval/phieu_cham.py xuat                  # bước 2: dựng phiếu HTML cho giáo viên
python eval/phieu_cham.py gop <thư mục CSV>     # bước 4: gộp phiếu giáo viên gửi lại
```

Vì sao phải thu riêng chứ không lấy từ bench: bench chỉ ghi **thời gian** của Explain,
không ghi nội dung; và bench chạy dưới ngân sách thời gian nên **81/150 lời giảng
(54%) bị cắt giữa chừng**. Đem bài giảng cụt cho giáo viên chấm thì điểm thấp là lỗi
của phép đo, không phải của hệ thống.

Phiếu chấm là **HTML tự chứa, nhúng sẵn KaTeX** — công thức hiện đúng, không cần mạng,
không cần tài khoản. Ba thiết kế chống thiên vị: chấm mù, có mẫu neo lấy từ sách giải,
và trộn cả bài sai theo đúng tỉ lệ thật.

### 4.9. Sinh lại bộ đề

```powershell
python eval/build_de_chuan.py --seed 20260805       # 150 bài, 50 mỗi môn
python eval/build_de_kho.py --seed 20260806         # 300 bài khó
python eval/kiem_de_chuan.py                        # TỰ KIỂM — chạy trước khi dùng
```

Seed cố định để bộ đề **tái lập được**. Tham số `--tranh <csv>` loại bỏ những câu đã
có trong bộ khác — đây là cách dựng bộ giữ riêng (held-out) không giẫm lên bộ chuẩn.

> Luôn chạy `kiem_de_chuan.py` trước khi dùng một bộ đề để đo bất cứ thứ gì. Bộ đề
> sai đáp án thì mọi con số phía sau đều vô nghĩa.

### 4.10. Kiểm thử

```powershell
python -m pytest
```

**222 test**, khoảng 14 giây, **không cần Ollama**. Đây là bộ kiểm các công cụ tất
định: SymPy, hoá học, đơn vị, trọng tài số học, kiểm chứng tượng trưng.

---

## 5. Cấu hình

Sửa file `.env` ở thư mục gốc dự án. **Không có `.env` thì hệ thống vẫn chạy đúng
cấu hình đã dùng để đo mọi số liệu báo cáo** — chỉ tạo `.env` khi muốn đổi thứ gì.

```powershell
copy .env.example .env
```

Đổi xong phải **khởi động lại backend**.

### 5.1. Mô hình và kết nối

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `VMA_MODEL_HEAVY` | `qwen3:4b` | Subject Agent + Verify |
| `VMA_MODEL_LIGHT` | `qwen3:4b` | Planner, Router, Explain |
| `VMA_TEMPERATURE` | `0.2` | |
| `VMA_NUM_CTX` | `4096` | Ăn VRAM thật: 8192 → 3,3 GB, 4096 → 2,9 GB |

> **Đừng trộn hai model khác nhau** khi VRAM dưới 10 GB. `qwen3:8b` + `qwen3:4b`
> cộng lại 9,2 GB; Ollama sẽ đẩy model này ra để nạp model kia, mỗi lần đổi tốn
> ~10 giây, và luồng có 4 lần đổi vai — mất trắng 40 giây chỉ để nạp.

### 5.2. Ngân sách thời gian

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `VMA_SLA_SECONDS` | `45` | Mốc KPI của đề bài |
| `VMA_AGENT_TIMEOUT` | `60` | Hạn chung mỗi vai |
| `VMA_TIMEOUT_RECOMPUTE` | `20` | Bộ tính lại chỉ trích cấu trúc, chạy ~5 giây |
| `VMA_NGUONG_GIAI_LAI` | `40` | Còn ít hơn ngần này giây thì không giải lại nữa |

### 5.3. Trần token đầu ra — công cụ giữ SLA hiệu quả nhất

| Biến | Mặc định |
|---|---|
| `VMA_MAX_TOKENS_PLANNER` | `400` |
| `VMA_MAX_TOKENS_ROUTER` | `150` |
| `VMA_MAX_TOKENS_SUBJECT` | `1100` |
| `VMA_MAX_TOKENS_VERIFY` | `350` |
| `VMA_MAX_TOKENS_EXPLAIN` | `900` |
| `VMA_MAX_TOKENS_RECOMPUTE` | `2200` |

> **ĐỪNG hạ `MAX_TOKENS_PLANNER` xuống 250.** Đã đo trên cùng 20 bài: 400 token cho
> 18/20 đúng, 250 token chỉ còn 13/20. Mất 5 bài để đổi lấy 2,6 giây. Chất lượng đọc
> đề quyết định mọi thứ phía sau — đây là chỗ tiết kiệm token đắt nhất trong cả luồng.

### 5.4. Các cờ bật/tắt cơ chế — đều để đối chứng A/B

| Biến | Mặc định | Tắt đi thì sao |
|---|---|---|
| `VMA_MAX_RETRY_ROUNDS` | `0` (tắt) | Bật `1`: cứu 1 bài nhưng hỏng 2, tốn thêm 5 giây/lượt |
| `VMA_AGENTS_SUY_NGHI` | *(rỗng)* | Bật cho `recompute`: vai này tốn 41,6 giây thay vì 5,1 |
| `VMA_LOC_TINH_LAI_DO_DANG` | `1` | Tắt: bộ tính lại đè kết quả dở dang lên đáp số đúng |
| `VMA_KIEM_KHOI_LUONG_MOL` | `1` | Tắt: model tự nhớ M(Fe₃O₄), nhớ sai không tầng nào bắt |
| `VMA_DUNG_SAI_KHOI_LUONG_MOL` | `0.015` | Chừa chỗ cho cách làm tròn của SGK (Cu = 64) |
| `VMA_BO_QUA_LLM_REVIEW` | `1` | Tắt: cộng thêm 4,6 giây mỗi lượt |
| `VMA_DUNG_KHO_DINH_LY` | `1` | Tắt: model tự nhớ công thức SGK |
| `VMA_DUNG_KHO_LOI_GIAI` | `1` | Tắt: mất phần học từ lượt đã qua kiểm chứng |
| `VMA_LUU_LOI_GIAI_MAU` | `1` | **Đặt `0` khi đo** — kho lớn dần làm phép đo mất tính dừng |

> **Quan trọng khi đo đạc:** đặt `VMA_LUU_LOI_GIAI_MAU=0`. Vừa ghi vừa đọc kho lời
> giải trong cùng một lần đo thì độ chính xác trôi dần theo thời gian — bài thứ 150
> chạy trên một hệ thống khác với bài thứ 1, và con số thu được không so sánh được
> với bất cứ thứ gì.

### 5.5. Máy yếu VRAM

```ini
VMA_NUM_CTX=1900
```

Mức này đã **đo thật**: còn 2,7 GB, độ dài lời giảng không đổi (644 chunk so với 647).
Không hạ thấp hơn — nhu cầu thật ~1720 token, xuống dưới là bắt đầu cắt lời giảng ở
những bài nhiều bước.

### 5.6. Ba khối cấu hình A/B/C

Cuối `.env.example` có sẵn ba khối dùng để dựng **đường đánh đổi độ chính xác – thời
gian** trong báo cáo. Chép nguyên khối vào `.env`, chạy bench, ghi lại, rồi đổi khối
khác. Chi tiết ở [TAILIEU.md](TAILIEU.md) mục 10.7.

---

## 6. Tình huống thường gặp lúc dùng

Khác với bảng lỗi cài đặt trong [INSTALL.md](INSTALL.md) mục 10 — đây là những thứ
xảy ra khi hệ thống **đã chạy đúng**.

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| Lời giảng đứt giữa câu | Chạm trần `MAX_TOKENS_EXPLAIN`, hoặc hết ngân sách thời gian | Nới `VMA_MAX_TOKENS_EXPLAIN`, hoặc nới `VMA_SLA_SECONDS` |
| Đáp án đúng nhưng Verify báo `FAIL` | Verify báo oan 18–28% — đã đo | Bình thường. Dùng `scripts/soi_verify.py` để xem phép kiểm nào hỏng |
| Router chọn sai môn | Đề dùng từ khoá lẫn giữa hai môn | Viết rõ hơn, hoặc bổ sung câu vào `ml/data/` rồi huấn luyện lại |
| Thẻ *Bài tập tương tự* báo chưa có mẫu | Dạng bài chưa được tham số hoá | Đúng thiết kế — chỉ phủ những dạng bảo đảm được đáp án |
| Bài dài bị giải nửa chừng | Nhiều câu a, b, c trong một lượt hỏi | Tách ra hỏi từng câu |
| Đáp số đổi giữa chừng trên màn hình | Trọng tài số học hoặc cơ chế cứu đã can thiệp | Đúng thiết kế. Đọc dòng cảnh báo kèm theo |
| Lượt sau chậm hơn hẳn lượt trước | Ollama đã nhả model khỏi VRAM | Đặt `OLLAMA_KEEP_ALIVE=-1` |
| Thời gian đo không khớp báo cáo | Có thứ khác đang tranh GPU | `ollama ps` — cột PROCESSOR phải là **100% GPU** |
| `/api/stats` trả số lạ | DB tích luỹ cả những lượt thử nghiệm | Xoá `vimultiagent.db`, backend tự tạo lại |

---

## 7. Kịch bản demo 10 phút

Trình tự này cho thấy đủ cả bốn điểm của đề tài mà không có khoảng chết.

**Trước khi bắt đầu** (làm xong hết, đừng làm trước mặt hội đồng):

- [ ] `ollama ps` → `qwen3:4b`, PROCESSOR **100% GPU**
- [ ] `/api/health` → `"status": "ok"`, `"sla_seconds": 45.0`
- [ ] Backend in `PhoBERT router: đã nạp`
- [ ] Đã hỏi trước một câu để nạp model
- [ ] `python ml/compare.py` chạy sẵn, chụp màn hình để dành
- [ ] `python -m pytest` → 222/222, để sẵn cửa sổ

**Trình bày:**

| Phút | Làm gì | Chỉ vào đâu |
|---|---|---|
| 0–1 | Bấm nút **Lý**, bấm Giải bài | Năm vai sáng dần — kiến trúc đa tác tử |
| 1–2 | Chờ đáp án hiện | **Đáp án ra trước khi giảng xong** — cắt 10,6 giây chờ |
| 2–3 | Cuộn xuống lời giảng đang chảy | Streaming thật, không phải chờ trắng màn hình |
| 3–4 | Chỉ vào dòng thời gian cuối | Dưới mốc 45 giây, 600/600 lượt đã đo đạt |
| 4–5 | Bấm **Sinh bài** ở thẻ Bài tập tương tự, bấm **Bài khác** | Tức thì — vì không gọi LLM, đáp án bảo đảm đúng |
| 5–7 | Mở cửa sổ `pytest` | 222 test cho tầng kiểm chứng tất định |
| 7–9 | Mở ảnh chụp `ml/compare.py` | Phần học sâu: PhoBERT tự huấn luyện, 94,7% quyết định định tuyến |
| 9–10 | Giải một bài Hoá | Soát khối lượng mol bằng `chem_tool`, không tin trí nhớ model |

**Câu hỏi phản biện hay gặp và chỗ tra câu trả lời:**

| Câu hỏi | Trả lời ở |
|---|---|
| "Học sâu ở đâu trong đề tài?" | [TAILIEU.md](TAILIEU.md) mục 7 — PhoBERT nhóm tự fine-tune, phân biệt rõ với Qwen3 |
| "Sao không dùng model to hơn?" | INSTALL mục 0 — 8b tràn 27% xuống CPU, chậm gấp 4,5 lần |
| "Làm sao biết đáp án đúng?" | TAILIEU mục 4 — 5 phép kiểm tất định + bộ tính lại độc lập |
| "Bộ đề có bị học thuộc không?" | TAILIEU mục 9.1 — ba bộ đề rời hẳn nhau, có bộ giữ riêng |
| "Lời giảng hay dở đánh giá thế nào?" | Mục 4.8 file này — giáo viên chấm mù, có mẫu neo từ sách giải |

---

## 8. Dựng lại toàn bộ số liệu báo cáo

Trình tự đầy đủ, khoảng **3 giờ máy chạy**.

```powershell
cd E:\DeepLearning\ViMultiAgent\backend

# 1. Tắt ghi kho lời giải để phép đo đứng yên
#    (đặt VMA_LUU_LOI_GIAI_MAU=0 trong .env, khởi động lại backend)

# 2. Tự kiểm bộ đề trước — bộ đề sai thì mọi số sau đều vô nghĩa
python eval/kiem_de_chuan.py

# 3. Chỉ số 1 + 3: độ chính xác và ma trận Verify, 150 bài (~80 phút)
python scripts/bench.py --de eval/data/de_chuan.csv --out reports/chuan

# 4. Trần năng lực: bộ đề khó 300 bài (~160 phút, chạy qua đêm)
python scripts/bench.py --de eval/data/de_kho.csv --out reports/kho

# 5. Chỉ số 2: lời giảng cho giáo viên chấm
python eval/thu_loi_giang.py --so-bai 30
python eval/phieu_cham.py xuat

# 6. Phần học sâu
python ml/compare.py

# 7. Đường đánh đổi accuracy–latency: lặp bước 3 với ba khối A/B/C trong .env.example
```

Kết quả CSV nằm ở `eval/reports/`. Bảng số liệu đã tổng hợp sẵn ở
[TAILIEU.md](TAILIEU.md) mục 10 — đối chiếu với kết quả mới chạy để biết máy của bạn
có cho ra cùng con số không.

> Máy khác GPU thì **thời gian sẽ khác, độ chính xác thì không** — độ chính xác chỉ
> phụ thuộc model và cấu hình, không phụ thuộc phần cứng. Lệch độ chính xác nghĩa là
> có gì đó khác cấu hình, kiểm tra `/api/health` và `.env` trước tiên.
