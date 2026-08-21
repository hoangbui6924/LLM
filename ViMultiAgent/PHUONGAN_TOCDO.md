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

Cần bạn duyệt trước khi tôi bắt tay.
