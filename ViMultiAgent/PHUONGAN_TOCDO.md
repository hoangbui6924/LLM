# Phương án xử lý vấn đề tốc độ

> Góp ý cần giải quyết: **"Chương trình chậm (RAM 6GB)"**
>
> Tài liệu này chỉ MÔ TẢ để duyệt. Chưa sửa dòng code nào.
> Lập ngày 2026-08-21.

---

## 1. Hiện trạng đo được

Một lượt giải bài hình học, đo thật trên bản build:

| Vai | Thời gian | Ghi chú |
|---|---:|---|
| Planner | 12,6 s | khâu tốn nhất |
| **Router** | **0,0 s** | PhoBERT, đã tối ưu xong |
| Hình học Agent | 5,8 s | |
| Verify | 4,2 s | |
| Explain | 8,1 s | chảy chữ theo thời gian thực |
| **Tổng** | **33,8 s** | mốc SLA là 45 s |

Cấu hình: `qwen3:4b` cho MỌI vai, `num_ctx` 4096, RTX 3060 Laptop 6 GB, đo ~74 token/giây.

### Đường găng

```
Planner ──> Subject ──> Verify ──> Explain
 12,6s       5,8s        4,2s       8,1s      = 30,7s
                │
          Recompute (chạy SONG SONG, không tính vào đường găng)
```

Router đã bị đưa ra khỏi đường găng nhờ PhoBERT (trước là ~2,0 s qua LLM).

### Ba điều quan trọng cần biết trước khi bàn phương án

1. **Số liệu trên chỉ là MỘT lượt đo, và có lẫn chi phí khởi động.** Ollama nạp
   model lần đầu mất 8–15 giây (ghi trong README). Con số 12,6 s của Planner rất
   có thể phần lớn là chi phí đó chứ không phải Planner thật chậm. **Chưa xác
   minh được điều này thì mọi ước tính bên dưới đều là phỏng đoán.**

2. **Đáp án đã được phát TRƯỚC khi Explain chạy.** `manager.py` phát sự kiện
   `dap_an` ngay sau Verify. Người dùng nhìn thấy đáp số ở giây thứ ~25,7, còn
   8,1 giây của Explain là phần giảng bài chảy chữ sau đó.

3. **Máy chấm có 6 GB VRAM.** `qwen3:4b` chiếm 3,2 GB nên nằm trọn trong GPU.
   Đây là lý do dự án chọn 4b thay vì 8b (8b chiếm 6,0 GB, chỉ nhét được 73% vào
   GPU, tụt còn 16,3 token/giây). Mọi phương án đổi model phải tôn trọng trần này.

---

## 2. Phương án

Xếp theo thứ tự nên làm. Ký hiệu rủi ro: 🟢 thấp · 🟡 vừa · 🔴 cao.

---

### P0 — Đo lại cho đúng trước khi tối ưu 🟢 **BẮT BUỘC LÀM ĐẦU TIÊN**

**Mô tả.** Chạy `scripts/bench.py` trên 20–30 bài, bỏ lượt đầu tiên (cold start),
lấy **trung vị** thời gian từng vai thay vì một lượt đơn lẻ. Tách riêng lượt đầu
để biết chi phí nạp model là bao nhiêu.

**Ưu điểm**
- Không sửa gì, không rủi ro.
- Trả lời câu hỏi quyết định: 12,6 s của Planner là thật hay là cold start? Nếu
  là cold start thì P1 giải quyết xong, khỏi cần đụng tới các phương án rủi ro.
- Có số liệu nhiều lượt mới báo cáo được cho hội đồng.

**Nhược điểm**
- Tốn 20–30 phút chạy.
- Không tự nó làm chương trình nhanh hơn.

**Độ cải thiện:** 0 giây. Nhưng **không có nó thì mọi phương án dưới đây là đoán mò.**

---

### P1 — Hâm nóng model lúc khởi động 🟢

**Mô tả.** Backend đã hâm nóng PhoBERT lúc khởi động (`main._ham_nong`). Làm
tương tự với Ollama: gửi một lượt gọi mồi rất ngắn tới `qwen3:4b` trong
`lifespan`, để model nằm sẵn trong VRAM trước khi người dùng hỏi câu đầu tiên.

**Ưu điểm**
- Rẻ, khoảng 10 dòng, không đụng vào logic giải bài.
- Cắt trọn chi phí nạp model khỏi lượt hỏi đầu tiên — đúng lượt mà người chấm sẽ
  bấm khi demo.
- Không đánh đổi độ chính xác.

**Nhược điểm**
- Backend khởi động chậm thêm ~10 giây.
- Chỉ giúp lượt ĐẦU. Các lượt sau vốn đã có model nóng.
- Nếu Ollama tự đẩy model ra khỏi VRAM sau một thời gian rảnh thì tác dụng mất.

**Độ cải thiện ước tính:** lượt đầu **−8 đến −15 giây**. Lượt sau: 0.

---

### P2 — Báo cáo "thời gian tới đáp án" bên cạnh tổng thời gian 🟢

**Mô tả.** Không đổi code xử lý, chỉ bổ sung một chỉ số vào phần đo và báo cáo:
thời điểm phát sự kiện `dap_an`. Hiện chỉ đo tổng thời gian, tức tính cả 8,1 giây
Explain — trong khi người dùng đã có đáp án từ trước đó.

**Ưu điểm**
- Không rủi ro, không đánh đổi gì.
- Phản ánh đúng trải nghiệm thật: đáp số hiện ở ~25,7 s.
- Đây là số liệu trung thực, không phải mẹo — cơ chế phát đáp án sớm đã có sẵn
  trong `manager.py` và có ghi chú giải thích lý do.

**Nhược điểm**
- Chương trình **không nhanh lên thật một giây nào**.
- Nếu trình bày vụng, hội dồng sẽ coi là nguỵ biện. Phải nêu cả hai con số, không
  được thay thế con số tổng.

**Độ cải thiện:** 33,8 s → **25,7 s** trên chỉ số "thời gian tới đáp án".
Tổng thời gian giữ nguyên.

---

### P3 — Mở rộng `kiem_symbolic` sang các dạng hình học 🟡

**Mô tả.** `tools/kiem_symbolic.py` hiện chỉ kiểm được 5 dạng Đại số (`dao_ham`,
`tich_phan`, `gioi_han`, `phuong_trinh`, `tiep_tuyen`). Bài hình học không có
phép kiểm tất định nào chạy được, nên Verify không đủ điều kiện đi đường tắt
(`BO_QUA_LLM_REVIEW` đòi "bộ tính lại đã xác nhận độc lập") và buộc phải gọi LLM.

Bổ sung ba dạng có công thức đóng, SymPy tính lại dễ:
`toa_do_the_tich`, `toa_do_khoang_cach`, `toa_do_kc_diem_mp`.

**Ưu điểm**
- **Một mũi tên hai đích**: vừa cắt lượt LLM của Verify, vừa sửa lỗi báo oan đã
  ghi ở mục H trong `CONGVIECNGAYMAI.md` (bài thể tích ra 20 — đúng — nhưng bị
  kết luận FAIL).
- Không đánh đổi độ chính xác, mà còn **tăng** — thêm phép kiểm tất định.
- Đúng tinh thần dự án: công cụ quyết định kết quả, không phải LLM.

**Nhược điểm**
- Phải viết và kiểm chứng công thức cho từng dạng, tốn công hơn P1/P2.
- Chỉ giúp bài hình học. Trong `de_kho` là 46/100 bài, nhưng trong `de_chuan` chỉ
  4/50 — nên mức hưởng lợi phụ thuộc bộ đề (xem mục D3 `CONGVIECNGAYMAI.md`).

**Độ cải thiện ước tính:** **−4 đến −6 giây** trên bài hình học đi được đường tắt.
Trung bình toàn bộ đề thì thấp hơn, tuỳ tỉ lệ bài hình.

---

### P4 — Dùng `qwen3:1.7b` cho các vai nhẹ 🔴

**Mô tả.** Hiện `MODEL_HEAVY` và `MODEL_LIGHT` **đều là `qwen3:4b`**. Máy đã tải
sẵn `qwen3:1.7b` (1,4 GB). Chuyển Planner và Explain sang 1.7b, giữ 4b cho Subject
Agent và Verify.

Về VRAM: 1,4 + 2,5 = **3,9 GB < 6 GB**, nên hai model nằm đồng thời trong GPU
được, không phải hoán đổi. Ghi chú trong `config.py` cảnh báo chuyện hoán đổi
tốn 10 giây mỗi lần, nhưng đó là tính cho cặp **8b + 4b = 9,2 GB** — cặp
1.7b + 4b thì không vướng.

**Ưu điểm**
- Nhắm đúng hai khâu tốn nhất: Planner + Explain = 20,7 s trên tổng 30,7 s đường găng.
- Model 1.7b nhanh hơn khoảng gấp đôi.
- Không cần tải gì thêm.

**Nhược điểm — đây là phương án rủi ro nhất**
- **Chất lượng đọc đề quyết định mọi thứ phía sau.** Đã có số đo cảnh báo: chỉ
  cắt `MAX_TOKENS_PLANNER` từ 400 xuống 250 đã làm độ chính xác tụt từ 90% xuống
  65% trên cùng 20 bài. Đổi hẳn model còn tác động mạnh hơn cắt token.
- Explain dùng model yếu hơn sẽ hạ điểm giảng bài — mà đó là chỉ số 2 của đề tài,
  do giáo viên chấm tay.
- Giả định "hai model cùng nằm trong VRAM" **chưa được kiểm chứng trên máy này**,
  cần xác nhận bằng `ollama ps` cột PROCESSOR.

**Độ cải thiện ước tính:** **−8 đến −10 giây**, nhưng **chỉ chấp nhận được nếu
A/B trên bộ đề cho thấy độ chính xác không tụt.** Không đo A/B thì không được dùng.

---

### P5 — Bỏ Planner, để Subject Agent tự đọc đề 🔴

**Mô tả.** Gộp việc đọc hiểu đề vào Subject Agent, cắt hẳn một lượt gọi LLM khỏi
đường găng.

**Ưu điểm**
- Cắt trọn khâu đắt nhất: **−12,6 giây**, nhiều hơn mọi phương án khác.
- Đúng ý góp ý số 3 của người phản biện: *"ít Agent hơn nhưng được thiết kế hợp
  lý → tốc độ tốt hơn và độ chính xác vẫn đảm bảo"*, và có thể trở thành một
  phần đóng góp thực nghiệm của đề tài.

**Nhược điểm**
- Mất `givens` / `unknowns` có cấu trúc — Verify và memory pool đang dùng chúng.
- Mất `steps_outline` định hướng cho Subject Agent.
- Mất bước chuẩn hoá đề và cơ chế `_giu_nguyen_so_lieu` (đã bắt được lỗi thật:
  model chép `R = 110` thành `R = 1:110`).
- **Mâu thuẫn với yêu cầu số 2 "nhiều Agents"** — giảm còn 4 vai chính.

**Độ cải thiện ước tính:** **−12 giây**, nhưng rủi ro hỏng độ chính xác là cao
nhất trong tất cả phương án.

---

### P6 — Hạ trần token của Explain 🔴 **KHÔNG NÊN**

**Mô tả.** Giảm `MAX_TOKENS_EXPLAIN` từ 900 xuống 600–700.

**Ưu điểm:** cắt được 2–3 giây, sửa một dòng cấu hình.

**Nhược điểm:** Trần này vốn đã được **nới từ 700 lên 900** vì đo được 81/150 lời
giảng (54%) bị cắt cụt giữa chừng ở mức 700. Hạ lại là quay về đúng lỗi đã sửa,
và làm hỏng chỉ số điểm giảng bài.

**Độ cải thiện:** −2 đến −3 giây, đổi lấy việc hỏng một chỉ số của đề tài.
**Ghi ở đây để loại trừ, không đề xuất làm.**

---

## 3. Tổng hợp

| | Phương án | Rủi ro | Cải thiện ước tính | Đánh đổi độ chính xác |
|---|---|:---:|---:|---|
| P0 | Đo lại cho đúng | 🟢 | 0 s | Không |
| P1 | Hâm nóng model | 🟢 | −8…−15 s (lượt đầu) | Không |
| P2 | Đo thêm "thời gian tới đáp án" | 🟢 | 33,8 → 25,7 s (chỉ số mới) | Không |
| P3 | Mở rộng kiểm chứng hình học | 🟡 | −4…−6 s (bài hình) | **Tăng** |
| P4 | qwen3:1.7b cho vai nhẹ | 🔴 | −8…−10 s | Có, phải A/B |
| P5 | Bỏ Planner | 🔴 | −12 s | Cao |
| P6 | Hạ token Explain | 🔴 | −2…−3 s | Có — **loại** |

## 4. Đề xuất

**Làm P0 → P1 → P2 → P3.** Bốn phương án này cộng lại không đánh đổi độ chính xác
một chút nào, mà P3 còn làm tăng.

Sau khi có số liệu từ P0 mới quyết định P4 và P5. Rất có thể P1 đã giải quyết phần
lớn con số 12,6 giây, và khi đó không cần đụng tới hai phương án rủi ro cao.

**Không làm P6.**

---

# 5. KẾT QUẢ SAU KHI THỰC HIỆN — 2026-08-21

Đã làm xong P0, P1, P2, P3. Đo hai lần trên **cùng 24 bài** của `de_chuan.csv`.

## 5.1. P0 đã bác bỏ chẩn đoán ban đầu

Số liệu 24 bài khác hẳn suy đoán rút từ MỘT lượt đo:

| Vai | Suy đoán (1 lượt) | **Đo thật (24 bài)** |
|---|---:|---:|
| Planner | 12,6 s | **6,0 s** |
| Router | 0,0 s | 0,3 s |
| Subject | 5,8 s | 8,4 s |
| Recompute | — | 7,0 s |
| Verify | 4,2 s | 3,6 s |
| **Explain** | 8,1 s | **11,1 s** |

**Explain mới là khâu tốn nhất, không phải Planner.** Con số 12,6 giây trước đây
phần lớn là chi phí nạp model, đúng như giả thuyết ở mục 1.

Hệ quả trực tiếp: **P5 (bỏ Planner) mất phần lớn giá trị** — nó chỉ cắt được 6
giây chứ không phải 12, trong khi rủi ro hỏng độ chính xác vẫn nguyên. Không nên
làm nữa.

## 5.2. Bảng đối chiếu trước / sau

| | Trước (P0) | Sau (P1+P2+P3) |
|---|---:|---:|
| Tổng thời gian trung bình | 30,7 s | 30,8 s |
| p50 | 29,8 s | 30,8 s |
| **Thời gian tới đáp án** | *(chưa đo được)* | **19,8 s** |
| Đạt mốc 45 s | 24/24 | 24/24 |
| **Độ chính xác** | **21/24** | **21/24** |
| Planner | 6,0 s | 5,7 s |
| Subject | 8,4 s | 8,2 s |
| Recompute | 7,0 s | **8,4 s** |
| Verify | 3,6 s | 3,7 s |
| Explain | 11,1 s | 11,0 s |

## 5.3. Từng phương án — thực tế ra sao

**P1 — có tác dụng, nhưng KHÔNG xuất hiện trong bảng trên.**
Lý do: `scripts/bench.py` gọi thẳng `agents.manager`, **không đi qua FastAPI**,
nên `lifespan` và phần hâm nóng không hề chạy. Kiểm riêng qua đường ứng dụng thật
thì thấy rõ:
```
[ViMultiAgent] Ollama: qwen3:4b đã nạp vào VRAM (6.2s).
Khởi động backend: 13.7s
```
Tức 6,2 giây được dời khỏi lượt hỏi đầu tiên sang lúc khởi động. Đây là **lượt mà
người chấm sẽ bấm khi demo**, nên vẫn đáng giá — chỉ là bench không đo được.

**P2 — giao đúng thứ đã hứa.** Người dùng có đáp án ở giây **19,8** trong khi tổng
là 30,8 giây. Phần giảng bài chiếm 11,0 giây chảy sau đó. Cả hai con số đều được
in trong báo cáo bench, không thay thế cho nhau.

**P3 — đúng về chức năng, nhưng không đo được ở đây, VÀ có cái giá phải trả.**

Không đo được vì trong 24 bài chỉ có **2 bài hình học** (`the_tich_khoi_chop`,
`the_tich_lang_tru`). Đây đúng là hạn chế đã ghi trước ở mục D3 của
`CONGVIECNGAYMAI.md`: `de_chuan` chỉ có 4/50 bài hình.

Cái giá: **Recompute tăng từ 7,0 lên 8,4 giây.** Nguyên nhân nhiều khả năng là
prompt của vai này dài thêm ~25 dòng hướng dẫn hình học. Chưa tách được khỏi
nhiễu đo vì mỗi cấu hình mới chạy một lượt.

Về chức năng thì P3 chạy đúng, có 18 test phủ cả hai chiều: đáp án đúng thì ĐẠT,
sai thì bắt được, đáp số âm do quên giá trị tuyệt đối thì bắt được, gặp hình lạ
hoặc mặt bậc hai thì im lặng chứ không đoán bừa.

## 5.4. Phát hiện mới: Recompute đã thành đường găng

Chính bench cảnh báo:

```
>> RECOMPUTE đang là đường găng (8.4s so với Subject 8.2s).
   Nó KHÔNG còn ẩn dưới Subject.
```

Đây là thay đổi về chất. Recompute chạy SONG SONG với Subject Agent, nên bao lâu
nay nó "miễn phí" về thời gian. Nay nó dài hơn Subject, tức **mọi nỗ lực tối ưu
Subject Agent đều vô ích** — thời gian bị quyết định bởi Recompute.

---

# 6. ĐỀ XUẤT TIẾP THEO

### P7 — Hạ trần token của Recompute 🟢 **nên làm ngay**

`MAX_TOKENS_RECOMPUTE` đang là **2200**, kèm chú thích trong `config.py`:
*"Có suy nghĩ nên cần rộng: ~1800 token cho `<think>` + ~200 cho biểu thức"*.

Nhưng `VMA_AGENTS_SUY_NGHI` **mặc định rỗng** — chế độ suy nghĩ đang TẮT. Vai này
giờ chỉ trích xuất cấu trúc bài toán, không suy luận, nên 2200 token là thừa rất
nhiều so với nhu cầu thật.

- **Ưu:** sửa một dòng cấu hình; nhắm đúng đường găng mới; không đụng độ chính xác
  vì vai này chỉ điền JSON ngắn.
- **Nhược:** cắt quá tay thì JSON bị cụt và bộ tính lại mất tác dụng — phải đo lại
  tỉ lệ `ly_do_hong` sau khi đổi.
- **Cải thiện ước tính:** −2 đến −4 giây, vì nó cắt thẳng vào đường găng.

### P8 — Rút gọn phần hình học trong prompt Recompute 🟢

Bù lại cái giá của P3. Gộp bảng thứ tự tham số cho 7 loại khối thành vài dòng
ngắn hơn.

- **Cải thiện ước tính:** trả lại phần lớn 1,4 giây mà P3 đã lấy đi.

### Cần đo lại P3 cho tử tế

Chạy bench trên `de_kho.csv` (46/100 bài hình học) thay vì `de_chuan.csv`
(4/50). Chỉ ở đó mới thấy được P3 có cắt được lượt LLM của Verify hay không.

### P5 — nên gạch bỏ

P0 cho thấy Planner chỉ tốn 6 giây, không phải 12,6. Lợi ích giảm một nửa trong
khi rủi ro không đổi. Không đáng.

---

# 7. KẾT QUẢ CUỐI — bốn loạt đo, cùng 24 bài `de_chuan.csv`

| | P0 mốc nền | P1–P3 | P8 | **P8b (cuối)** |
|---|---:|---:|---:|---:|
| Tổng thời gian TB | 30,7 s | 30,8 s | 30,3 s | **29,1 s** |
| p50 | 29,8 s | 30,8 s | 28,6 s | **27,6 s** |
| p95 | 40,5 s | 40,6 s | 43,0 s | **39,9 s** |
| Nhanh nhất | 22,9 s | 22,8 s | 22,7 s | **20,0 s** |
| **Thời gian tới đáp án** | — | 19,8 s | 20,2 s | **18,6 s** |
| **Độ chính xác** | 21/24 | 21/24 | 21/24 | **22/24** |
| Đạt mốc 45 s | 24/24 | 24/24 | 24/24 | 24/24 |
| Planner | 6,0 | 5,7 | 5,5 | 5,5 |
| Router | 0,3 | 0,3 | 0,3 | 0,3 |
| Subject | 8,4 | 8,2 | 9,1 | 8,0 |
| Recompute | 7,0 | **8,4** | **5,3** | 6,6 |
| Verify | 3,6 | 3,7 | 4,0 | **3,4** |
| Explain | 11,1 | 11,0 | 10,2 | 10,5 |
| Đường găng | 29,4 | 29,2 | 29,2 | **27,7** |

## 7.1. Kết luận

**Đạt được:** tổng thời gian 30,7 → 29,1 giây (−5%), đường găng 29,4 → 27,7 giây,
và có thêm chỉ số **18,6 giây tới đáp án** — đây mới là độ trễ người dùng cảm
nhận. Độ chính xác không giảm, thậm chí nhích lên 22/24.

**Phải nói rõ:** mức giảm 1,6 giây trên 24 mẫu là **bằng chứng yếu**. Mô hình chạy
ở `temperature 0.2` chứ không phải 0, nên mỗi loạt đo có sai khác tự nhiên. Muốn
kết luận chắc thì phải lặp mỗi cấu hình vài lượt, hoặc chạy trên cả 50 bài.

**Verdict lật qua lật lại giữa các loạt** cũng là biểu hiện của nhiễu đó, không
phải hồi quy:

| Bài | P0 | P8 | P8b |
|---|---|---|---|
| `math_th_037` (số phức) | FAIL | PASS | FAIL |
| `math_th_009` (phương trình mũ) | PASS | FAIL | FAIL |

Cả hai đều là bài ĐẠI SỐ, không dính tới phần hình học đã thêm.

## 7.2. Tổng kết từng phương án

| | Kết quả thực tế |
|---|---|
| **P0** | Bác bỏ chẩn đoán ban đầu. Explain (11,1s) mới là khâu tốn nhất, không phải Planner (6,0s). |
| **P1** | Chạy đúng, dời 6,2 s khỏi lượt hỏi đầu. **Không đo được bằng bench** vì bench không đi qua FastAPI lifespan. |
| **P2** | Giao đúng: 18,6 s tới đáp án so với 29,1 s tổng. |
| **P3** | Chức năng đúng nhưng **hai lần suýt hỏng** — xem 7.3. |
| **P7** | **Bác bỏ.** Recompute chỉ sinh 32–46 token, không hề chạm trần 2200. `num_predict` là mức chặn, không phải mục tiêu. |
| **P8** | Prompt Recompute 101 → 41 dòng (−45%). Recompute 8,4 → 6,6 s, hết là đường găng. |
| **P5** | Gạch bỏ. Chỉ cắt được 6 s chứ không phải 12,6 s như tưởng. |
| **P6** | Không làm, đúng như đã loại từ đầu. |

## 7.3. Hai lỗi P3 tự gây ra — bài học đắt nhất của đợt này

**Lỗi 1 — tính năng chưa từng chạy.** `compute()` kiểm tay `loai_kiem and ham_goc`
trong khi hình học không dùng `ham_goc`. Mọi bài thể tích rơi vào `bieu_thuc_rong`.
18 test của `kiem_symbolic` đều XANH vì chúng gọi thẳng tầng dưới, không đi qua
chỗ nối.

**Lỗi 2 — phép kiểm tất định tự báo oan.** Đề "khối chóp đáy hình vuông CẠNH 3,
cao 9", mô hình điền `hinh="chop", tham_so="3; 9"` — nhét cạnh vào ô diện tích.
SymPy tính 9 rồi **phủ quyết** đáp án đúng 27.

Lỗi 2 nguy hiểm hơn nhiều: phép kiểm tất định có quyền phủ quyết, nên nó sai một
lần là mất luôn một đáp án đúng. Đã vá ba lớp: thêm biến thể `chop_day_vuong`
nhận cạnh đáy, prompt nêu thẳng ca sai làm phản ví dụ, và `_the_tich_mo_ho()` từ
chối kiểm khi đề mô tả đáy bằng hình dạng mà mô hình vẫn chọn ô diện tích.

**Bài học:** test đơn vị cho tầng dưới KHÔNG thay được test cho chỗ nối. Đã bổ
sung 26 test phủ đúng hai chỗ này (tổng 236), và kiểm ngược bằng cách khôi phục
logic cũ để chắc chúng thật sự bắt được lỗi.

## 7.4. Còn lại

- [ ] **Đo P3 cho tử tế**: `de_chuan` chỉ có 2/24 bài hình học nên phần hình gần
      như không được kiểm. Phải chạy trên `de_kho.csv` (46/100 bài hình).
- [ ] **Lặp phép đo**: mỗi cấu hình chạy 3 lượt rồi lấy trung vị, mới tách được
      tín hiệu khỏi nhiễu.
- [ ] Explain 10,5 s vẫn là khâu tốn nhất và **chưa có phương án nào chạm tới nó**.
      Nhưng nó nằm SAU mốc có đáp án, nên ưu tiên thấp.
