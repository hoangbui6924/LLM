# Kết quả thực nghiệm

> Cập nhật liên tục. Số liệu lấy từ `eval/reports/`.
> Cấu hình: Groq · Solver = `openai/gpt-oss-120b` · Verifier = `llama-3.3-70b-versatile`
> (khác họ) · chế độ `balanced` · RTX 3060 Laptop 6 GB cho phần huấn luyện.

---

## 1. ViSTEM-PRM — phần Học sâu

### 1.1 Huấn luyện

| Hạng mục | Giá trị |
|---|---|
| Model nền | `vinai/phobert-base-v2` (135 M tham số) |
| Dữ liệu | 38 526 mẫu step-level (32 785 train / 5 741 val) |
| Nguồn dữ liệu | 3 000 lời giải đúng sinh từ 13 template + 8 041 biến thể bị tiêm lỗi |
| Chi phí gán nhãn | **0 đồng** — nhãn âm sinh ra từ mutation testing |
| Chia tập | theo **NGUỒN** (không theo dòng) để tránh rò rỉ tiền tố |
| Cân bằng lớp | trọng số nghịch tần suất (79,2 % dương / 20,8 % âm) |
| Huấn luyện | 3 epoch · batch 16 · seq 256 · AMP fp16 · ~470 s/epoch |
| VRAM đỉnh | ~5,7 GB / 6 GB |

Đường loss: 0,2068 → 0,1695 → 0,1322.

| Epoch | Accuracy | Precision (bắt lỗi) | Recall | F1 |
|---|---|---|---|---|
| 2 | 0,9749 | 0,9872 | 0,8927 | 0,9376 |
| **3** | **0,9807** | **0,9928** | **0,9149** | **0,9523** |

### 1.2 Chọn ngưỡng vận hành — bằng số, không đoán

Quét ngưỡng trên tập validation (`prm_threshold_sweep.json`). Đường cong rất phẳng
trong dải 0,05–0,75 (precision ≈ 0,99), tức model rất "chắc chắn" — xác suất dồn về
hai đầu.

Ngưỡng chọn: **0,55** → precision 0,993 · recall 0,916.

Lý do ưu tiên precision, và đây là con số đo được chứ không phải cảm tính: **một lần
báo oan kích hoạt một vòng repair, và mỗi vòng repair cộng thêm ~60 s** vào độ trễ.
Bỏ sót rẻ hơn nhiều vì T2/T3 phía sau vẫn còn cơ hội bắt.

### 1.3 Đánh giá mức LỜI GIẢI (mutation testing, 150 bài, 300 trường hợp)

| Chỉ số | Giá trị | KPI đề tài |
|---|---|---|
| **Tỉ lệ phát hiện lỗi (recall)** | **91,3 %** | ≥ 85 % ✅ |
| Precision | 97,2 % | — |
| F1 | 0,942 | — |
| Độ trễ trung vị | **24 ms** | so với ~3 000 ms của một lượt gọi LLM |

TP = 137 · FN = 13 · FP = 4 · TN = 146

**Recall theo loại lỗi — kết quả quan trọng nhất của mục này:**

| Loại lỗi | Recall | Nhận xét |
|---|---|---|
| formula (nhầm công thức) | **100 %** | lỗi cấu trúc, nhìn ra được từ văn bản |
| condition (bỏ điều kiện xác định) | **100 %** | lỗi thiếu bước, nhận diện theo mẫu |
| unit (quên quy đổi) | **100 %** | |
| sign (sai dấu) | 98,1 % | |
| **arithmetic (sai số học)** | **77,4 %** | **điểm yếu — cần tính lại mới biết** |

**Luận điểm rút ra:** PRM bắt gần như hoàn hảo lỗi *ngữ nghĩa và cấu trúc*, nhưng
đuối rõ rệt với *sai số học* — vì phát hiện loại này đòi hỏi thực sự thực hiện phép
tính, thứ một bộ phân loại văn bản không làm được. Đó chính xác là việc của SymPy ở
tầng T1. **Hai tầng bù nhau chứ không chồng chéo**, và đây là lập luận bảo vệ cho
thiết kế nhiều tầng.

Recall theo môn: Toán 93,8 % · Vật lý 90,5 % · Hoá 89,3 %.

> **Giới hạn cần nêu trong báo cáo:** dữ liệu đánh giá sinh từ cùng bộ template với
> dữ liệu huấn luyện (khác tham số, khác seed). Đây là đánh giá *trong phân phối*.

### 1.4 Đo ngoài phân phối — mọi số ở trên KHÔNG giữ được

`python -m eval.run_prm_diag` chấm PRM trên **lời giải thật của Solver**, bóc từ
cache LLM trên đĩa và gán nhãn qua cột `correct` của benchmark.

| | Template (mục 1.3) | Lời giải thật |
|---|---|---|
| Báo oan lời giải đúng | 2,8 % | **57 % (4/7)** |
| Bắt được lời giải sai | 91,3 % | 0/1 |

```
2,24 lít   ĐÚNG   P=0.0003      0,4 s   ĐÚNG   P=0.6292
2,24 lít   ĐÚNG   P=0.0003      0,4 s   ĐÚNG   P=0.8782
0,397 s    ĐÚNG   P=0.0046      18      ĐÚNG   P=0.9637
0,4 s      ĐÚNG   P=0.0649      4 cm³   SAI    P=0.9940  ← cao nhất lại là bài SAI
```

n = 8 (7 đúng / 1 sai) — quá nhỏ để tính precision/recall có ý nghĩa. Nhưng **thứ tự
xếp hạng đã đảo**, nên đây không phải bài toán chỉnh ngưỡng. Bằng chứng rõ nhất:
ba lời giải đúng của **cùng một bài** cho 0,065 / 0,629 / 0,878 — điểm số đang phản
ánh cách diễn đạt chứ không phản ánh đúng/sai.

**Nguyên nhân 1 — lỗi cắt chuỗi.** PhoBERT chặn cứng ở 258 vị trí. 32 % đầu vào thật
vượt 256 token (trung vị 192, max 487). `build_input` v1 đặt bước đang chấm ở **cuối**
chuỗi, `truncation_side='right'` cắt từ cuối ⇒ gần một phần ba số bước bị hỏi "bước
này đúng không" trong khi chính bước đó đã bị xoá khỏi đầu vào. Đổi sang cắt trái
**không cứu được** (báo oan tăng 4/7 → 5/7) vì model đã học dưới chế độ cắt phải.
Đã sửa ở định dạng **v2**: đưa `XÉT:` lên đầu, phần bị cắt là các bước trước xa nhất.
Cần huấn luyện lại mới có hiệu lực.

**Nguyên nhân 2 — ba đường ghép văn bản khác nhau.** Dựng dữ liệu huấn luyện, suy luận,
và ghi memory pool trước đây mỗi chỗ ghép một kiểu; riêng memory pool chỉ nối `goal_vi`.
Nghĩa là kế hoạch "trộn lời giải thật vào huấn luyện" **sẽ hỏng âm thầm**: model học
trên văn bản trơ, bị hỏi trên văn bản có LaTeX. Đã gộp về một hàm `data_build.step_text`.
Cùng họ với Lỗi 1 ở mục 2 — hai chỗ trả lời cùng một câu hỏi thì phải là cùng một đoạn mã.

**Hệ quả:** T0 chưa được tính là một tầng kiểm chứng hoạt động được, và khoản tiết kiệm
độ trễ từ "cascade thoát sớm" chưa tồn tại. Giữ `advisory` cho tới khi huấn luyện lại
bằng v2 + dữ liệu thật và đo lại bằng chính `run_prm_diag.py`.

---

## 2. Ba lỗi tìm được nhờ đo, không nhờ đọc code

Mục này nên vào báo cáo: nó cho thấy quy trình kỹ thuật, và cả ba lỗi đều **im lặng** —
không crash, chỉ làm số liệu sai.

### Lỗi 1 — Verifier và bộ chấm dùng hai cài đặt so khớp khác nhau

Solver trả `final_answer` dạng câu văn ("Khối lượng muối thu được là 8,2 gam"), còn
`verify_t2` so khớp bằng `.split()[0]` → luôn coi là bất đồng.

Hậu quả đo được trên 30 bài: **20/30 FAIL giả → 22 vòng repair thừa → độ trễ trung vị
99,6 s** (KPI là 45 s), và accuracy tụt xuống dưới cả baseline.

Sửa: tách `vimultiagent/core/answer_match.py`, dùng chung cho **cả** Verifier lúc chạy
**và** bộ chấm lúc đánh giá. Hai chỗ cùng trả lời câu hỏi "hai đáp án này có bằng nhau
không" thì phải là cùng một đoạn mã.

### Lỗi 2 — PRM nhận văn bản bị nhân đôi

`score_solution` ghép `goal_vi + expression + result + justification`. Khi Solver diễn
đạt gọn, `goal_vi` và `justification_vi` trùng nhau → câu bị lặp → phân phối lệch khỏi
lúc huấn luyện.

Hậu quả: recall mức lời giải chỉ **59,3 %** dù F1 mức bước là 0,952.
Sau khi khử trùng lặp: **91,3 %**.

### Lỗi 3 — Ngưỡng T0 đặt theo cảm tính

Ban đầu đặt `reject_threshold = 0,15` với lý do "chỉ bác bỏ khi rất chắc". Quét thực tế
cho thấy đường cong phẳng tới 0,75, nên 0,15 không mua thêm precision mà chỉ mất recall.

---

## 3. Baseline và hệ đầy đủ

### 3.1 Vấn đề đã phát hiện: tập hạt giống quá dễ

| Cấu hình | Accuracy (tập seed, 30 bài) |
|---|---|
| A0 · Single-agent CoT | **93,3 %** |

Ở mức 93,3 % gần như không còn chỗ để hệ đa tác tử thể hiện. Một báo cáo kết luận
"hệ của chúng tôi 95 %, baseline 93 %" sẽ không thuyết phục được hội đồng.

**Đối sách:** đã dựng thêm `eval/datasets/hard_thpt.jsonl` — 30 bài nhiều bước, **cả
30 bài đều có bẫy tường minh**, chọn theo tiêu chí đối kháng với điểm yếu của một lượt
CoT:

- nghiệm ngoại lai (`log₂x + log₂(x−2) = 3` cho 2 nghiệm, phải loại 1)
- rút gọn tử–mẫu trước khi đếm tiệm cận
- chất giới hạn (`0,2 mol Fe + 0,3 mol HCl` — phải tính theo HCl)
- khối lượng dung dịch phải trừ khí bay ra
- chỉnh hợp vs tổ hợp
- quy đổi đơn vị nhiều tầng

Mọi đáp án đã tính tay và đối chiếu.

### 3.2 Bảng kết quả

*(đang chạy lại sau khi sửa 3 lỗi trên — sẽ cập nhật)*

| Cấu hình | Acc (seed) | Acc (hard) | p50 | p95 | ≤45 s |
|---|---|---|---|---|---|
| A0 · Single-agent CoT | 93,3 % | — | 4,0 s | 63,2 s | 90 % |
| A7 · Hệ đầy đủ *(trước khi sửa)* | 76,7 % | — | 99,6 s | 133,9 s | 20 % |
| A7 · Hệ đầy đủ *(sau khi sửa)* | *đang chạy* | | | | |

---

## 4. Việc còn lại

- [ ] Chạy ablation A0–A8 trên **cả hai** tập (seed + hard)
- [ ] LLM-judge chất lượng sư phạm + đối chiếu 20 mẫu chấm người
- [ ] Trộn lời giải thật vào dữ liệu PRM, huấn luyện lại, đo tổng quát hoá
- [ ] Phân tích lỗi còn lại theo môn và theo chủ đề
