# ViMultiAgent — Nội dung slide báo cáo

14 slide. Mỗi slide ghi rõ **nói gì**, **chiếu gì**, và chỗ nào cần nhấn.

Mọi con số dưới đây đều lấy từ `TAILIEU.md`, là số đo thật kèm cỡ mẫu. Đừng làm
tròn lên khi trình bày — người chấm hỏi lại nguồn là có ngay.

---

## Slide 1 — Trang bìa

**ViMultiAgent**
Hệ đa tác tử giải bài tập STEM tiếng Việt, chạy hoàn toàn ngoại tuyến

- Toán · Vật lý · Hoá học bậc THPT
- Tên nhóm, thành viên, lớp, giảng viên hướng dẫn

> Một dòng chốt hạ đặt dưới tiêu đề, đọc là nhớ:
> **"LLM quyết định LÀM GÌ, công cụ quyết định KẾT QUẢ LÀ BAO NHIÊU."**

---

## Slide 2 — Bài toán đặt ra

**Vì sao không gọi thẳng ChatGPT là xong?**

Ba vấn đề của cách làm một mô hình duy nhất:

| Vấn đề | Hệ quả |
|---|---|
| Mô hình ngôn ngữ **tính sai số học** | đáp số sai nhưng lời văn vẫn trôi chảy, học sinh không phát hiện được |
| **Không có gì kiểm chứng** | sai hay đúng đều trình bày tự tin như nhau |
| Phụ thuộc API trả phí, cần mạng | không dùng được trong phòng máy trường học |

Ví dụ thật lấy từ chính hệ thống này (dùng để dẫn sang slide sau):
lời giải viết `0,1 × 62 = 3,8` — sai, đúng phải là **6,2**.

**Mục tiêu:** hệ thống chạy offline, tự phát hiện được lỗi của chính nó.

---

## Slide 3 — Yêu cầu đề tài

**Kiến trúc lấy cảm hứng MetaGPT — 5 tác tử**

Phân tích đề → Giải chuyên ngành → Kiểm tra → Giải thích → Sinh bài tương tự

Cộng thêm: memory pool (kho định lý + lời giải mẫu), tool use (SymPy), frontend
streaming + LaTeX.

**Bốn chỉ số đánh giá**

| Chỉ số | Ngưỡng |
|---|---|
| Độ chính xác | ≥ 75% |
| Độ trễ end-to-end | ≤ 45 giây |
| Tỉ lệ phát hiện lời giải sai | ≥ 85% |
| Chất lượng lời giảng | ≥ 4/5 |

> Nói rõ ngay từ đầu: chỉ số 4 **đã bỏ** theo thống nhất, chỉ số 3 **chưa đạt**.
> Nêu trước thì phần sau nghe như báo cáo trung thực; giấu để người chấm tự phát
> hiện thì thành che giấu.

---

## Slide 4 — Kiến trúc tổng thể

**Chiếu sơ đồ luồng** (vẽ lại từ mục 2 của `TAILIEU.md`):

```
Người dùng
    ▼
 Planner ──────► tách dữ kiện, xác định ẩn cần tìm
    ▼
 Router ───────► chọn môn: PhoBERT → luật từ khoá → LLM
    ├────────────────────────┐
    ▼                        ▼
 Subject Agent        Bộ tính lại độc lập
 (Toán/Lý/Hoá)        (chạy SONG SONG)
    ▼                        │
 Trọng tài SymPy             │
    ▼◄───────────────────────┘
 Verify ───────► 5 phép kiểm tất định + LLM soi lại
    ▼
 Chốt đáp án ──► phát ngay cho giao diện
    ▼
 Explain ──────► giảng bài, streaming từng chữ
```

**Ba điểm cần nhấn khi chiếu:**

1. Nhánh đôi ở giữa — **hai lời giải độc lập** chạy song song, không phải một
2. Trọng tài SymPy **ghi đè** số sai của mô hình, không xin phép
3. "Chốt đáp án" nằm **trước** Explain — đáp số hiện ra sớm hơn ~11,6 giây

| Thành phần | Công nghệ |
|---|---|
| Khung đa tác tử | AutoGen |
| Mô hình ngôn ngữ | Qwen3:4b qua Ollama, cục bộ |
| Phân loại môn | PhoBERT fine-tune — **nhóm tự huấn luyện** |
| Tính toán tất định | SymPy, Pint, bộ công cụ hoá tự viết |
| Backend / Frontend | FastAPI + SSE / React + TypeScript + KaTeX |

---

## Slide 5 — Định tuyến ba tầng (phần học sâu của nhóm)

**Đây là đóng góp deep learning, nên dành hẳn một slide.**

PhoBERT (`vinai/phobert-base`) fine-tune 3 lớp trên 810 câu tự gán nhãn.

| Tầng | Thời gian | Vai trò |
|---|---|---|
| **PhoBERT** | ~50 ms | quyết định **94,7%** số bài |
| Luật từ khoá | 0 ms | khi PhoBERT không chắc |
| LLM | 2–4 giây | chỉ khi hai tầng trên bó tay |

**Bảng so sánh ba phương pháp** — chạy `python ml/compare.py` để lấy số, chiếu
riêng nhóm "câu khó" (câu không chứa từ khoá đặc trưng). Đây là chỗ PhoBERT hơn
hẳn luật từ khoá, và là bằng chứng học sâu có tác dụng thật.

> Nói thêm nếu còn thời gian: PhoBERT vẫn sai ở câu xác suất bi (xếp nhầm sang Vật
> lý với độ tin cậy 0,90). **Độ tin cậy cao mà vẫn sai**, nên nâng ngưỡng vô ích —
> đó là lý do phải có tầng hai và ba chứ không phó mặc cho một mô hình.

---

## Slide 6 — Tầng kiểm chứng tất định (điểm khác biệt lớn nhất)

**Thông điệp: hệ thống không tin mô hình ngôn ngữ, kể cả mô hình của chính nó.**

Năm phép kiểm chạy **trước** khi LLM được đọc bất cứ thứ gì:

| Phép kiểm | Áp cho | Cơ chế |
|---|---|---|
| Có bước giải và đáp số | mọi bài | |
| Tính lại số học từng bước | mọi bài | SymPy, thế ký hiệu, ngưỡng 1% |
| Thứ nguyên đáp số | Vật lý | Pint |
| Bảo toàn nguyên tố | Hoá | giải hệ bằng không gian null của ma trận |
| Khối lượng mol | Hoá | bảng nguyên tử khối |

Cộng thêm **bộ tính lại độc lập**: SymPy tự giải lại bài (đạo hàm, tích phân, giới
hạn, phương trình, tiếp tuyến) rồi đối chiếu.

**Hai nguyên tắc đáng nhấn:**

- **Một phép kiểm tất định thất bại là FAIL, bất kể LLM nói gì.**
- Thứ tự có chủ đích: chạy máy trước, đưa kết quả cho LLM sau. Làm ngược lại thì
  mô hình 4B bị lập luận trôi chảy cuốn theo và "đồng ý" với lời giải sai.

---

## Slide 7 — Memory pool và tác tử sinh bài tập

**Memory pool** — hai kho, bơm vào prompt của Subject Agent:

- **Kho định lý**: ~70 công thức THPT, chọn theo chủ đề bài đang giải
- **Kho lời giải mẫu**: SQLite, **chỉ lưu bài đã qua kiểm chứng sạch**

**Tác tử Sinh bài tập tương tự** — vai thứ năm của bản yêu cầu:

| | |
|---|---|
| Nguồn | 175 mẫu đề tham số hoá |
| Thời gian | **43 ms** |
| Lượt gọi LLM | **0** |
| Bảo đảm đáp án | Python tính từ tham số của chính đề bài |

> Chỗ này nên nhấn mạnh, vì nó **mạnh hơn MetaGPT gốc**: bên đó để LLM nghĩ đề.
> Mô hình vừa tính 0,1 × 62 = 3,8 thì không thể tin nó bịa đề cho học sinh. Đề sai
> đưa cho người học còn tệ hơn không đưa gì — họ không có cách nào biết mình sai
> hay đề sai.
>
> Đáp án ở đây **đúng theo kiến tạo**, không phải theo may rủi: có test tính lại
> toàn bộ 175 mẫu bằng SymPy và nó đạt.

---

## Slide 8 — Phương pháp đánh giá

**Slide này quyết định độ tin cậy của mọi con số phía sau. Đừng lướt nhanh.**

Ba bộ đề, **rời hẳn nhau, trùng lặp 0%**:

| Bộ | Số bài | Dùng để |
|---|---|---|
| `de_chuan` | 150 | phát triển — mọi bản sửa đều rút ra từ đây |
| **`de_giu_rieng`** | **150** | **chưa từng dùng để sửa gì — con số nộp báo cáo** |
| `de_kho` | 300 | dò trần năng lực, 30% bài vận dụng cao |

**Ba tầng bảo đảm đáp án đúng:**

1. Đề sinh từ mẫu có tham số, đáp án do Python tính từ chính tham số đó
2. Cột `bieu_thuc_kiem` được SymPy tính lại và đối chiếu — bắt mọi lệch
3. Hệ số phản ứng hoá lấy từ giải ma trận, không do người soạn đoán

> **Vì sao phải có bộ giữ riêng.** Sửa hệ thống dựa trên bộ nào thì con số trên bộ
> đó không còn là phép thử độc lập nữa — nó đo cả công sức chỉnh riêng cho bộ ấy.
> Bộ giữ riêng là cách duy nhất biết cải tiến có **tổng quát thật** hay không.

---

## Slide 9 — Kết quả đối chiếu bốn chỉ số

**Số lấy từ bộ giữ riêng 150 bài.**

| Chỉ số | Ngưỡng | Đạt được | |
|---|---|---|---|
| Độ chính xác | ≥ 75% | **78,7% ± 6,6** | ✅ |
| Độ trễ | ≤ 45 giây | **150/150**, trung bình 30,4s | ✅ |
| Phát hiện lời giải sai | ≥ 85% | 53,1% | ❌ |
| Chất lượng lời giảng | ≥ 4/5 | đã bỏ theo thống nhất | — |

**Bằng chứng cải tiến tổng quát thật:**

Bộ phát triển 80,0% — bộ giữ riêng 78,7%. **Chênh 1,3 điểm**, nằm gọn trong sai số
±6,6. Nếu các bản sửa chỉ là may đo cho bộ phát triển thì khoảng cách phải lớn hơn
nhiều.

Toàn bộ 600 bài của cả ba bộ đều **dưới 45 giây**, không có ngoại lệ.

---

## Slide 10 — Phân tích sâu: điểm gãy nằm ở đâu

**Theo mức độ** (bộ giữ riêng):

| Mức | Đúng |
|---|---|
| Nhận biết | 90,4% |
| Thông hiểu | 80,4% |
| Vận dụng | 71,4% |
| **Vận dụng cao** | **52,9%** |

**Theo môn:** Toán 82,0% · Hoá 84,0% · Lý 70,0%

**Hai kết luận rút ra:**

- Vận dụng cao là điểm gãy **duy nhất và nhất quán** trên cả ba bộ đề (70,0% ·
  52,9% · 54,4%) → đây là **giới hạn năng lực thật của mô hình 4 tỉ tham số**,
  không phải lỗi kỹ thuật có thể vá.
- Hoá ổn định nhất, nhiều khả năng nhờ **hai phép kiểm tất định riêng** cho môn
  này. Đây là bằng chứng gián tiếp rằng tầng kiểm chứng có tác dụng thật.

> Phát biểu an toàn cho phần hỏi đáp: *hệ thống dùng được tới hết mức Vận dụng;
> Vận dụng cao thì chưa tin được.*

---

## Slide 11 — Tối ưu độ trễ: đổi kiến trúc, không cắt xén

**Slide kỹ thuật hay nhất của báo cáo. Nên dành thời gian.**

Vấn đề: bộ tính lại bật chế độ suy nghĩ cho độ chính xác 90,0% nhưng tốn 41,6 giây
và **trở thành đường găng** — 149/150 bài có nó chậm hơn Subject Agent, tức cơ chế
chạy song song mất sạch tác dụng.

| | Cấu hình C | **Cấu hình D** |
|---|---|---|
| Độ chính xác | 90,0% | 80,0% |
| **Đạt mốc 45 giây** | **3,3%** | **100%** |
| Thời gian trung bình | 65,1s | 30,0s |

**Cách giải quyết — đổi vai trò, không cắt token:**

> Bộ tính lại chuyển từ *"tự suy luận ra đáp số"* sang *"trích đề về dạng máy đọc
> được rồi để SymPy tự giải"*.

Mô hình chỉ còn phải **chép lại đề cho đúng cấu trúc**, việc nó làm tốt. Phần tính
toán giao hẳn cho SymPy, việc SymPy không bao giờ sai. **41,6 giây → 5,1 giây.**

Đường găng hiện tại: `5,5 + max(8,6 ; 5,1) + 4,7 + 11,6 = 30,3 giây`

---

## Slide 12 — Một phép kiểm báo đạt suốt nhiều ngày mà chưa từng chạy

**Slide gây ấn tượng nhất. Kể như một câu chuyện.**

Chạy thử giao diện, đề *"đốt cháy hoàn toàn 4,6 gam Na trong O₂ dư"*:

| Bước | Lời giải ghi | |
|---|---|---|
| 2 | `nNa = mNa/MNa` → 0,2 mol | đúng |
| 3 | `nNa2O = nNa/2` → 0,1 mol | đúng |
| 4 | `mNa2O = nNa2O × MNa2O` → **3,8 g** | **sai, phải 6,2** |

Verify vẫn kết luận **"số học các bước khớp"**.

**Nguyên nhân:** mô hình luôn viết vế phải bằng **công thức chữ**, chỉ để con số ở
trường kết quả. SymPy gặp toàn ký hiệu tự do nên trả `None` và bỏ qua bước — **im
lặng**. Cả 4 bước đều bị bỏ qua, rồi hàm vẫn báo đạt.

**Hệ quả kép, vế thứ hai mới nặng:** Verify Agent đọc dòng "số học khớp" đó rồi yên
tâm kết luận PASS. Một phép kiểm chết không chỉ vô dụng — nó **phát tín hiệu giả
làm hỏng phán đoán của tầng phía trên**.

**Cách sửa:** thế giá trị từ các bước trước và từ bảng nguyên tử khối vào trước khi
tính. Kèm ba chốt chặn báo oan, trong đó có: lệch đúng một luỹ thừa của 10 thì hiểu
là đổi đơn vị (`A = 6 cm` dùng bằng mét ở bước sau), không phải sai số học.

> **Bài học phương pháp — đây mới là điều đáng nói với hội đồng.**
> Bộ kiểm thử 181 bài lúc đó **đều đạt**, vì không test nào dựng lời giải viết bằng
> công thức chữ — đúng dạng mô hình luôn sinh ra. Lỗi chỉ lộ khi có người ngồi đọc
> một đáp án cụ thể trên màn hình.
>
> **Test bảo vệ được điều ta nghĩ tới. Chỉ dùng thật mới lộ ra điều ta không nghĩ tới.**

---

## Slide 13 — Hạn chế đã biết

**Nêu thẳng. Hội đồng sẽ hỏi, trả lời trước thì chủ động.**

**Chỉ số 3 chưa đạt — 53,1% so với ngưỡng 85%.** Nguyên nhân gốc: tầng kiểm chứng
bị giới hạn bởi **chất lượng trích xuất của mô hình 4B**. Nó không phân biệt nổi
"tính f(3)" với "tính f'(3)", nên mọi phép kiểm phía sau đều phải dè dặt. Hai lần
can thiệp gần đây chỉ **dịch chuyển cân bằng** giữa bắt đúng và báo oan
(70,4%/27,6% → 60,0%/18,3%) chứ không nâng được cả hai.

**Bài Hoá không có trọng tài SymPy.** Bộ kiểm tất định chỉ nhận 5 dạng Toán, nên
mọi bài Hoá phải qua vòng LLM soi lại — nguồn báo oan lớn nhất còn lại.

**Vận dụng cao là trần năng lực của mô hình**, không vá được bằng kỹ thuật.

**Bộ đề tự soạn.** Đáp án đúng theo kiến tạo, nhưng văn phong đều tay hơn đề thi thật.

**Memory pool chưa chứng minh được giá trị** — đo trên 50 bài Hoá cho kết quả y hệt
khi tắt (42/50 cả hai).

**Hướng phát triển:** mở rộng trọng tài SymPy sang mảng Hoá; thử mô hình 8B trên máy
đủ VRAM; nhận đề bằng ảnh.

---

## Slide 14 — Demo và tổng kết

**Kịch bản demo — 3 phút, làm theo đúng thứ tự này:**

1. Hỏi trước một câu bất kỳ để Ollama nạp model (**làm trước khi lên bục**, lượt đầu
   luôn chậm thêm 10–15 giây)
2. Giải một bài Vật lý — chỉ vào **năm vai sáng dần** và **đáp án hiện ra trước khi
   lời giảng chảy xong**
3. Bấm **"Sinh bài"** ở thẻ Bài tập tương tự — ra đề mới **tức thì**, nhấn là không
   gọi LLM lần nào
4. Mở `ollama ps` cho thấy **100% GPU**, và chạy `python -m pytest` → **222 test đạt**

**Ba câu chốt:**

- Hệ thống **chạy hoàn toàn ngoại tuyến**, không một khoá API nào
- Đạt **2/3 chỉ số còn hiệu lực**, và biết rõ chỉ số còn lại hỏng ở đâu, vì sao
- Giá trị lớn nhất không nằm ở con số 78,7%, mà ở chỗ hệ thống **tự phát hiện được
  lỗi của chính nó** — đó là thứ một lời gọi API đơn lẻ không làm được

---

## Phụ lục — bỏ vào slide dự phòng, chỉ chiếu khi bị hỏi

| Câu hỏi có thể gặp | Trả lời sẵn |
|---|---|
| Vì sao chọn model 4B mà không lớn hơn? | 8B nặng 6,0 GB, tràn 27% xuống CPU, tốc độ còn 16 token/giây — chậm gấp 4,5 lần, trượt mốc 45 giây |
| Máy cấu hình tối thiểu? | GPU 4 GB (model chiếm 2,9 GB), RAM 8 GB, ổ trống 12 GB |
| Có bao nhiêu kiểm thử? | 222, chạy 14 giây, không cần Ollama |
| Sao không dùng WolframAlpha như đề bài? | Cần khoá API và mạng, trái với yêu cầu chạy ngoại tuyến; SymPy thay được toàn bộ phần tính toán |
| Sai số ±6,6 tính thế nào? | Khoảng tin cậy 95% cho tỉ lệ trên mẫu n = 150 |
| Vì sao tắt vòng giải lại? | Đo được là lỗ ròng: sửa được 8 bài nhưng làm hỏng 10 bài khác |
