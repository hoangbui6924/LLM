# Giải trình các câu hỏi về đề tài ViMultiAgent

Trả lời năm câu hỏi trong phần **Các bước thực hiện**, kèm đối chiếu với bộ chỉ số
đánh giá đã đăng ký.

Mọi số liệu trong tài liệu này đo thật trên máy phát triển (RTX 3060 Laptop 6 GB),
chi tiết phương pháp đo ở [TAILIEU.md](TAILIEU.md) mục 9 và 10.

---

## 1. Tải LLM open source (Qwen) — có phải cài lên không? Bỏ thư mục vào đâu?

**Không đặt vào thư mục dự án, và nhóm cũng không tự quản lý file trọng số.**

Việc này do Ollama đảm nhiệm. Toàn bộ thao tác gói trong một lệnh:

```powershell
ollama pull qwen3:4b
```

| Hạng mục | Chi tiết |
|---|---|
| Vị trí lưu | `C:\Users\<tên người dùng>\.ollama\models` — **nằm ngoài** thư mục dự án |
| Dung lượng | 2,5 GB, đã lượng tử hoá ở mức Q4_K_M |
| Cách chương trình truy cập | **Không đọc file trọng số.** Gọi qua HTTP tới `http://localhost:11434` |
| Điểm cấu hình | Biến `OLLAMA_HOST` trong `backend/core/config.py` |

### Vì sao thiết kế theo hướng này

1. **Giới hạn của GitHub.** File trọng số 2,5 GB vượt xa hạn mức 100 MB mỗi file.
   Đưa model vào repo là không khả thi về mặt kỹ thuật.
2. **Đổi model không cần sửa mã.** Model là một biến môi trường, không phải một
   đường dẫn cứng trong mã nguồn.
3. **Cho phép tách máy.** Vì giao tiếp qua HTTP, Ollama có thể chạy trên một máy
   khác trong mạng nội bộ; máy chạy giao diện không cần GPU.

---

## 2. Có cần cài thư viện không? Trang web có phải kết nối tới thư mục Qwen để train dữ liệu?

### 2.1. Thư viện — có, chia ba nhóm

| Nhóm | File khai báo | Thành phần chính |
|---|---|---|
| Lõi, bắt buộc | `backend/requirements.txt` | autogen-agentchat, autogen-ext[ollama], fastapi, uvicorn, pydantic, sse-starlette, httpx, **sympy**, **pint**, python-dotenv, pytest |
| Học sâu, tuỳ chọn | `backend/requirements-ml.txt` | torch (bản CPU), transformers, underthesea, scikit-learn |
| Giao diện | `frontend/package.json` | React, TypeScript, Vite, KaTeX |

Nhóm học sâu để ở chế độ **tuỳ chọn** có chủ đích: thiếu nó hệ thống vẫn chạy đủ,
Router tự lùi về luật từ khoá. Điều này giúp người chỉ muốn xem sản phẩm không phải
cài hơn 1 GB thư viện.

Riêng `torch` phải cài bản CPU bằng lệnh chỉ định nguồn:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Cài bản mặc định sẽ kéo về bản CUDA nặng ~2,5 GB và tranh VRAM với Ollama, trong khi
PhoBERT chạy CPU chỉ mất ~50 ms mỗi câu — thừa nhanh so với ngân sách 45 giây.

### 2.2. Đính chính về việc "train dữ liệu trên Qwen"

> **Trang web không huấn luyện Qwen, và không cần kết nối tới thư mục chứa Qwen.**

Đây là điểm dễ hiểu nhầm nhất của đề tài. Cần tách bạch hai mô hình có vai trò khác
hẳn nhau:

| | **Qwen3:4b** | **PhoBERT** |
|---|---|---|
| Nhóm có huấn luyện không | **Không** — chỉ dùng suy luận | **Có** — nhóm tự fine-tune |
| Quy mô | 4 tỉ tham số | 135 triệu tham số |
| Cách kết nối | HTTP API tới Ollama | Nạp trọng số vào RAM tiến trình backend |
| Nhiệm vụ | Sinh lời giải, sinh lời giảng | Phân loại môn học ở Router |
| Thời gian huấn luyện | Không có | ~12 phút trên CPU |

Nhóm **không fine-tune Qwen**, và đây là quyết định có cân nhắc chứ không phải bỏ
sót. Fine-tune một mô hình 4 tỉ tham số cần GPU từ 24 GB VRAM trở lên cùng nhiều giờ
chạy — vượt xa điều kiện phần cứng của đề tài. Quan trọng hơn: **nó không cần thiết**
để đạt mục tiêu.

Thay cho fine-tune, chất lượng lời giải được nâng bằng bốn cơ chế khác, tất cả đều
đo được hiệu quả riêng:

1. **Chuyên biệt hoá vai** (role specialization) — 8 tác tử, mỗi tác tử nhận một
   prompt hẹp và một nhiệm vụ duy nhất.
2. **Memory pool** — chèn công thức chuẩn sách giáo khoa vào prompt, thay vì để mô
   hình 4B tự nhớ.
3. **Tầng kiểm chứng tất định** — SymPy, cân bằng nguyên tố, khối lượng mol, kiểm
   thứ nguyên. Không tốn token, kết quả không phụ thuộc mô hình.
4. **Tác tử tính lại độc lập** — giải song song bằng đường khác rồi đối chiếu; lệch
   nhau thì trọng tài số học phân xử.

### 2.3. Về kiến trúc phần mềm

Đề tài không phải "Python thuần chạy trên VS Code". Sản phẩm gồm hai phần chạy trên
hai cổng khác nhau:

| Phần | Công nghệ | Cổng |
|---|---|---|
| Backend | Python + FastAPI | 8000 |
| Frontend | React + TypeScript + Vite | 5173 |

Backend phát dữ liệu về giao diện bằng **SSE** (Server-Sent Events) để lời giảng
chảy chữ theo thời gian thực, thay vì bắt người dùng chờ trắng màn hình 30 giây.

---

## 3. Dataset thu thập từ nguồn nào, lưu ở đâu, kết nối với trang web thế nào?

Dự án có **ba loại dữ liệu khác hẳn nhau về bản chất và vai trò**. Trộn lẫn chúng
rồi báo một con số chung là tự lừa mình, nên phần này tách bạch rõ.

### 3.1. Dataset huấn luyện PhoBERT — `backend/ml/data/`

**810 câu do nhóm tự xây dựng**, chia theo tầng: 535 train · 116 val · 159 test.

Mỗi câu gắn nhãn `source` để lúc báo cáo tách bạch được ba nguồn:

| Nguồn | Số câu ở tập test | Cách tạo | Giá trị khoa học |
|---|---|---|---|
| `seed` | 47 | Soạn tay theo chương trình THPT, bám các dạng bài phổ biến trong đề thi tốt nghiệp và sách bài tập | Dữ liệu gốc |
| `template` | 67 | Sinh từ khuôn mẫu, đổi số liệu và cách diễn đạt | Làm dày dữ liệu huấn luyện. **Không dùng để công bố accuracy** — dễ với mọi mô hình |
| `hard` | 45 | Soạn tay, **cố tình không chứa từ khoá đặc trưng** của môn, hoặc lai hai môn | Tập quan trọng nhất — chỉ nhóm này mới phân định được luật từ khoá với học sâu |

Hai biện pháp chống rò rỉ dữ liệu:

- Chia theo tầng (stratified) để ba môn cân bằng ở cả ba tập.
- Các câu sinh từ **cùng một khuôn mẫu được giữ trong cùng một tập**. Nếu khuôn
  "Tính đạo hàm của y = {f} tại x = {a}" xuất hiện ở cả train lẫn test thì phép đo
  chỉ đang kiểm tra khả năng nhớ khuôn, không phải khả năng phân loại.

### 3.2. Ba bộ đề đánh giá — `backend/eval/data/`

| File | Số bài | Vai trò |
|---|---|---|
| `de_chuan.csv` | 150 | Bộ phát triển — mọi cải tiến của dự án rút ra từ đây |
| `de_giu_rieng.csv` | 150 | **Bộ giữ riêng**, trùng 0% với bộ chuẩn, chưa từng dùng để sửa bất cứ thứ gì |
| `de_kho.csv` | 300 | Dò trần năng lực hệ thống |

Ba bộ **rời hẳn nhau**. Bộ giữ riêng sinh ra với tham số `--tranh` để loại bỏ mọi câu
đã có trong bộ chuẩn.

Đặc điểm quan trọng: đề **sinh tự động với seed cố định** nên tái lập được, và **đáp
án tính bằng SymPy / chem_tool** nên tính đúng có bảo đảm — không phải chép từ sách
giải rồi tin. Trước khi dùng để đo, bộ đề còn phải qua bước tự kiểm
(`eval/kiem_de_chuan.py`).

Ba bộ này **không dùng để huấn luyện bất cứ mô hình nào**, chỉ dùng để đo.

### 3.3. Memory pool — `vimultiagent.db` (SQLite)

| Kho | Nội dung | Cách hình thành |
|---|---|---|
| Kho định lý | Công thức chuẩn sách giáo khoa | Soạn sẵn, cố định |
| Kho lời giải | Ví dụ mẫu cho prompt | Tự tích luỹ từ những lượt đã qua kiểm chứng PASS |

Kho lời giải là thứ khiến hệ thống khá dần lên khi được dùng nhiều. Khi đo đạc phải
tắt việc ghi (`VMA_LUU_LOI_GIAI_MAU=0`) để phép đo đứng yên — nếu vừa ghi vừa đọc thì
bài thứ 150 chạy trên một hệ thống khác với bài thứ nhất.

### 3.4. Cách từng loại nối với trang web

| Dữ liệu | Cơ chế kết nối |
|---|---|
| PhoBERT | **Nạp lười** vào RAM ở lần Router gọi đầu tiên (`ml/classifier.py`). Backend khởi động vẫn nhanh; không có mô hình thì `available()` trả False và Router lùi về luật từ khoá, không văng lỗi |
| Memory pool | Backend đọc/ghi SQLite ở mỗi lượt giải |
| Ba bộ đề | **Không nối với trang web.** Chỉ `scripts/bench.py` đọc để đo hiệu năng |

---

## 4. Mất bao lâu để train xong?

| Công việc | Thời gian | Phần cứng | Số lần phải làm |
|---|---|---|---|
| **Fine-tune PhoBERT** | **~12 phút** | CPU, không cần GPU | 1 lần |
| Huấn luyện Qwen | **Không có** | — | — |
| Cài đặt từ máy trắng | 30–45 phút | — | 1 lần |
| Chạy đo đầy đủ 600 bài | ~4 giờ | GPU | Mỗi lần đổi cấu hình |

Mười hai phút là con số thật vì bài toán rất nhẹ: phân loại 3 lớp trên 535 câu huấn
luyện, mô hình nền 135 triệu tham số. Việc huấn luyện chạy trên CPU nên **không cần
tắt Ollama** — hai thứ không tranh tài nguyên của nhau.

Trọng số PhoBERT sau huấn luyện nặng 517 MB, **không nằm trong repo** vì vượt hạn mức
100 MB của GitHub. Người lấy dự án về phải tự chạy `python ml/train_phobert.py` một
lần. Kết quả mong đợi:

```
Độ chính xác trên test: 0.94
  seed       47/47 = 1.0000
  template   67/67 = 1.0000
  hard       36/45 = 0.8000
```

---

## 5. Đã đạt tính đột phá và các chỉ số đánh giá chưa? Có dùng tài nguyên gợi ý?

### 5.1. Đối chiếu bộ chỉ số đã đăng ký

Số liệu lấy từ **bộ đề giữ riêng 150 bài**.

| Chỉ số đăng ký | Ngưỡng | Đo được | Kết luận |
|---|---|---|---|
| Accuracy bài toán Toán cấp THPT tiếng Việt | ≥ 75% | **78,7% ± 6,6** | ✅ **Đạt** |
| Latency end-to-end | ≤ 45s | **150/150 = 100%**, trung bình 30,4s | ✅ **Đạt** |
| Solution verification rate | ≥ 85% | 53,1% (chặt) · 71,9% (nới) | ❌ **Chưa đạt** |
| Explanation quality (10 giáo viên, Likert 5) | ≥ 4/5 | Chưa tổ chức chấm | ⏳ **Chưa có số** |

Trên toàn bộ **600 bài** thuộc ba bộ đề rời nhau: **600/600 lượt dưới 45 giây**,
không một ngoại lệ nào.

### 5.2. Vì sao báo cáo lấy số của bộ giữ riêng, không lấy 80,0% của bộ chuẩn

Mọi bản sửa trong dự án — bộ đọc số, chốt chặn `loai_kiem`, kiến trúc recompute, cơ
chế cứu đáp án — đều rút ra từ quan sát trên `de_chuan.csv`. Con số trên bộ đó **không
còn là một phép thử độc lập**.

Bộ giữ riêng trùng 0% và chưa từng được dùng để sửa gì. Chênh lệch giữa hai bộ chỉ
**1,3 điểm** (80,0% so với 78,7%), nằm gọn trong sai số ±6,6 — đây chính là bằng chứng
các cải tiến **tổng quát thật**, không phải may đo riêng cho bộ phát triển.

### 5.3. Kết quả chi tiết trên cả ba bộ đề

| Bộ đề | n | Accuracy | Đạt mốc 45s | Phát hiện sai | Báo oan |
|---|---|---|---|---|---|
| Chuẩn | 150 | 80,0% ± 6,4 | **150/150** | 60,0% | 18,3% |
| **Giữ riêng** | 150 | **78,7% ± 6,6** | **150/150** | 53,1% | 11,0% |
| Khó | 300 | 72,0% ± 5,1 | **300/300** | 45,2% | 15,7% |

Phân rã theo mức độ cho thấy một điểm gãy **duy nhất và nhất quán** trên cả ba bộ:

| Mức | Bộ chuẩn | Bộ giữ riêng | Bộ khó |
|---|---|---|---|
| Nhận biết | 97,6% | 90,4% | 75,7% |
| Thông hiểu | 73,9% | 80,4% | 82,6% |
| Vận dụng | 73,8% | 71,4% | 78,8% |
| **Vận dụng cao** | 70,0% | **52,9%** | **54,4%** |

### 5.4. Về chỉ số chưa đạt — nói thẳng

**Solution verification rate mới đạt 53,1%, còn cách ngưỡng 85% khá xa.**

Nguyên nhân đã xác định: các can thiệp gần đây chỉ **dịch chuyển cân bằng** giữa
"bắt đúng lời giải sai" và "báo oan lời giải đúng" (tỉ lệ báo oan 11–18%), chứ không
nâng được đồng thời cả hai. Siết chặt tiêu chí thì bắt được nhiều hơn nhưng báo oan
tăng, và mỗi lần báo oan là một lần hệ thống đi sửa một lời giải vốn đã đúng.

Có một tình tiết giảm nhẹ: con số này đo khi phép kiểm `_check_arithmetic` còn hỏng
(chi tiết ở [TAILIEU.md](TAILIEU.md) mục 4.6), nên nó là **cận dưới** của bản hiện
tại. Chạy lại `bench.py` sẽ cho số cao hơn — nhưng nhóm không cho rằng đủ để chạm 85%.

Đây là hạn chế được ghi nhận công khai ở [TAILIEU.md](TAILIEU.md) mục 11, không né
tránh.

### 5.5. Chỉ số chất lượng lời giảng — hạ tầng đã sẵn sàng

Chỉ số này chưa có số vì chưa tổ chức được buổi chấm, nhưng **toàn bộ công cụ đã dựng
xong**:

```powershell
python eval/thu_loi_giang.py --so-bai 30    # thu lời giảng, KHÔNG bị cắt do hết giờ
python eval/phieu_cham.py xuat              # dựng phiếu HTML tự chứa, nhúng KaTeX
python eval/phieu_cham.py gop <thư mục>     # gộp CSV giáo viên gửi lại
```

Ba thiết kế chống thiên vị đã cài sẵn trong quy trình chấm:

- **Chấm mù** — không đánh dấu bài nào do hệ thống sinh, bài nào chép từ sách giải.
- **Mẫu neo** — trộn lời giải sách giải vào. Nếu chính sách giải cũng chỉ được 4,1
  điểm thì mốc 4/5 cho máy là khắt khe, và nhóm có **bằng chứng** để nói vậy.
- **Có cả bài sai** — lấy mẫu theo đúng tỉ lệ đúng/sai thật, không chọn mẫu thiên vị.

Phiếu chấm là file HTML tự chứa có nhúng KaTeX, giáo viên mở bằng trình duyệt, không
cần mạng và không cần tài khoản.

### 5.6. Tài nguyên gợi ý — tình trạng sử dụng

| Tài nguyên | Tình trạng | Cụ thể |
|---|---|---|
| **microsoft/autogen** | ✅ **Dùng thật** | `autogen-agentchat>=0.7`, `autogen-ext[ollama]>=0.7`; lớp vỏ chung của các tác tử ở `agents/base.py` |
| **MetaGPT** | ⚠️ Tham khảo ý tưởng | Kế thừa tư tưởng **role specialization**, **không dùng mã nguồn** |
| Hong et al. (2024), MetaGPT, ICLR 2024 | ✅ Trích dẫn | |
| Wu et al. (2023), AutoGen | ✅ Trích dẫn | |

### 5.7. Về tuyên bố tính đột phá

Bản đăng ký ghi *"đầu tiên tại Việt Nam có cơ chế self-verification bằng tác tử độc
lập"*. Cụm **"đầu tiên tại Việt Nam"** là một tuyên bố **không kiểm chứng được** — nếu
hội đồng yêu cầu chứng minh, nhóm không có căn cứ nào để chống đỡ, và một điểm yếu như
vậy có thể kéo đổ cả phần trình bày.

Đề nghị diễn đạt lại theo đúng những gì **chứng minh được bằng số đo**:

> Hệ thống đa tác tử giải bài tập Toán THPT tiếng Việt chạy **hoàn toàn ngoại tuyến trên
> máy phổ thông** (GPU 4–6 GB, không cần API key của bất kỳ dịch vụ nào), kết hợp tác
> tử LLM với **tầng kiểm chứng tất định** (SymPy, cân bằng nguyên tố, khối lượng mol,
> kiểm thứ nguyên) và **tác tử tính lại độc lập chạy song song** — đạt **78,7%** độ
> chính xác trên bộ đề giữ riêng với **100% lượt dưới 45 giây**.

Những điểm mạnh nhất để bảo vệ trước hội đồng, xếp theo sức thuyết phục:

1. **Chạy offline hoàn toàn, chi phí vận hành bằng không.** Không API key, không phụ
   thuộc dịch vụ nước ngoài — quan trọng với bối cảnh trường học Việt Nam.
2. **Cơ chế tự kiểm chứng bằng đường tính toán độc lập.** Một mô hình đơn lẻ không có
   khả năng này; nó cũng không thể tự phát hiện mình nhớ sai khối lượng mol.
3. **Số liệu tái lập được, có bộ giữ riêng.** Bộ đề sinh với seed cố định, đáp án tính
   bằng SymPy, có bộ held-out chưa từng dùng để sửa gì.
4. **Trung thực về hạn chế.** Chỉ số 3 chưa đạt và điều đó được ghi rõ, kèm phân tích
   nguyên nhân.

---

## Phụ lục — tra cứu nhanh

| Cần tìm | Xem ở |
|---|---|
| Cài đặt trên máy mới | [INSTALL.md](INSTALL.md) |
| Cách dùng, API, script, cấu hình | [HUONGDAN.md](HUONGDAN.md) |
| Kiến trúc, thuật toán, số liệu đầy đủ | [TAILIEU.md](TAILIEU.md) |
| Phương pháp đo | [TAILIEU.md](TAILIEU.md) mục 9 |
| Bảng kết quả đầy đủ | [TAILIEU.md](TAILIEU.md) mục 10 |
| Hạn chế đã biết | [TAILIEU.md](TAILIEU.md) mục 11 |
