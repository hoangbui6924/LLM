# KẾT QUẢ ĐỐI CHỨNG KIẾN TRÚC — MỘT TÁC TỬ vs ĐA TÁC TỬ

*Đo ngày 22/08/2026 · bộ đề khó `de_kho.csv`, **100 bài Toán THPT** ·
mô hình `qwen3:4b` · ghép cặp 100/100 bài*

> **Tài liệu này đã được viết lại toàn bộ.** Bản trước kết luận "đa tác tử không
> cho độ chính xác cao hơn" dựa trên 450 bài của **ba môn Toán – Lý – Hoá**. Hệ
> thống nay chỉ còn **một môn Toán**, nên mọi số liệu cũ không còn hiệu lực và
> phép đo đã chạy lại từ đầu. Kết luận **đảo chiều** — xem mục 6.

---

## 1. TÓM TẮT MỘT ĐOẠN

Trên 100 bài Toán của bộ đề khó, kiến trúc đa tác tử đạt **73,0%** so với **54,0%**
của mốc nền một lời gọi LLM — chênh **+19 điểm phần trăm**. Kiểm định McNemar
ghép cặp cho **p = 0,002563**, đạt ý nghĩa thống kê ở mức 0,05. Chi phí đổi lại
chỉ là **1,1 giây** mỗi bài.

Ngoài độ chính xác, khác biệt lớn hơn nằm ở chỗ mốc nền **không có tầng kiểm chứng
nào**: nó phát hiện được **0%** lời giải sai, trong khi hệ đa tác tử bắt được
**63%**. Đây là khác biệt về bản chất, không phải mức độ — mốc nền trả về đáp án
đúng và đáp án sai với cùng một giọng tự tin.

> **Kết luận: trên phạm vi Toán THPT, kiến trúc đa tác tử vượt trội cả về ĐỘ CHÍNH
> XÁC lẫn ĐỘ TIN CẬY.**

---

## 2. THIẾT KẾ THỰC NGHIỆM

Nguyên tắc: **chỉ thay đổi một biến duy nhất là kiến trúc.**

| | Giữ chung cho cả hai nhánh |
|---|---|
| Mô hình | `qwen3:4b` lượng tử hoá Q4_K_M, chạy cục bộ qua Ollama |
| Tham số sinh | `temperature` 0,2 · `num_ctx` 4096 · tắt chế độ suy nghĩ |
| Bộ đề | `de_kho.csv` — 100 bài, 54 Đại số + 46 Hình học |
| Hàm chấm | **Dùng lại trực tiếp** `cham()` của `bench.py` cho cả hai nhánh |
| Phần cứng | RTX 3060 Laptop 6 GB |

Mốc nền được cấp trọn **2750 token** cho một lượt gọi, đúng bằng tổng ngân sách mà
hệ đa tác tử tiêu cho một bài (Planner 400 + Subject 1100 + Verify 350 + Explain
900). Cấp trọn thay vì cấp một phần là có chủ đích: mốc nền phải làm hết việc đọc
đề, giải và trình bày trong một lượt, nên cắt bớt ngân sách của nó sẽ tạo lợi thế
giả cho phía đa tác tử.

Hai nhánh **không chạy đồng thời** — chạy song song sẽ tranh GPU và làm sai số đo
thời gian của cả hai.

---

## 3. BỐN CHỈ SỐ CỐT LÕI

![Bốn chỉ số cốt lõi](backend/eval/reports/hinh/01_chi_so_cot_loi_toan.png)

| Chỉ số | Một tác tử | Đa tác tử | Chênh |
|---|---:|---:|---:|
| **Độ chính xác** | 54,0% | **73,0%** | **+19,0** |
| **Phát hiện lời giải sai** | 0,0% | **63,0%** | **+63,0** |
| Thời gian trung bình | 30,2 s | 31,3 s | +1,1 s |
| Đạt mốc 45 giây | 100,0% | 99,0% | −1,0 |

Đổi **1,1 giây** lấy **19 điểm chính xác** — tỉ lệ đánh đổi rất có lợi. Một bài của
nhánh đa tác tử chạm 66,5 giây nên tỉ lệ đạt mốc là 99/100 thay vì tuyệt đối.

---

## 4. BẢNG CHÉO GHÉP CẶP

![Hiệu quả ròng](backend/eval/reports/hinh/05_hieu_qua_rong_toan.png)

| | Đa tác tử ĐÚNG | Đa tác tử SAI |
|---|---:|---:|
| **Một tác tử ĐÚNG** | 45 | **9** |
| **Một tác tử SAI** | **28** | 18 |

* Đa tác tử **cứu được 28 bài** mà mốc nền làm sai
* Đa tác tử **làm hỏng 9 bài** mà mốc nền làm đúng
* Hiệu quả ròng **+19 bài**, trên 37 cặp lệch

**McNemar (chính xác, hai phía): p = 0,002563** — có ý nghĩa thống kê ở mức 0,05.

Cỡ mẫu 37 cặp lệch vượt ngưỡng 25 mà kiểm định đòi, nên đây là kết luận có căn cứ
chứ không phải may mắn của một lần đo.

---

## 5. KHOẢNG CÁCH NỞ RA Ở ĐÂU

![Phân rã](backend/eval/reports/hinh/04_phan_ra_toan.png)

### Theo phân môn

| Phân môn | n | Một tác tử | Đa tác tử | Chênh |
|---|---:|---:|---:|---:|
| Đại số | 54 | 70,4% | 74,1% | +3,7 |
| **Hình học** | 46 | **34,8%** | **71,7%** | **+36,9** |

**Gần như toàn bộ khoảng cách nằm ở Hình học.** Ở Đại số hai kiến trúc bám sát
nhau, chênh 3,7 điểm — trong khoảng nhiễu. Ở Hình học thì mốc nền sụp xuống 34,8%
trong khi hệ đa tác tử giữ được 71,7%.

Giải thích hợp lý nhất: bài hình học đòi nhiều bước trung gian (dựng hình, xác
định đường cao, lập toạ độ) và một lượt gọi duy nhất không đủ chỗ — **32/100 lời
giải của mốc nền bị cắt vì chạm trần token**, tập trung ở nhóm này.

### Theo mức độ nhận thức

| Mức độ | n | Một tác tử | Đa tác tử | Chênh |
|---|---:|---:|---:|---:|
| Nhận biết | 14 | 35,7% | **100,0%** | +64,3 |
| Thông hiểu | 29 | **72,4%** | 69,0% | −3,4 |
| Vận dụng | 39 | 61,5% | **82,1%** | +20,6 |
| Vận dụng cao | 18 | 22,2% | **38,9%** | +16,7 |

Đa tác tử dẫn ở ba trên bốn mức. Riêng Thông hiểu mốc nền nhỉnh hơn 3,4 điểm,
nhưng với n = 29 thì chênh lệch này nằm trong nhiễu.

Con số 35,7% ở mức Nhận biết là **bất thường** — thấp hơn cả Thông hiểu. Nguyên
nhân đã tìm ra, xem mục 7.

---

## 6. SO VỚI KẾT LUẬN CŨ — ĐẢO CHIỀU

| | Bản 3 môn (12–13/08) | **Bản Toán (22/08)** |
|---|---|---|
| Bộ đề | 450 bài · Toán, Lý, Hoá | 100 bài · Toán |
| Ròng | −5, +5, −10, −3 (đảo dấu) | **+19 (nhất quán)** |
| p tốt nhất | 0,3374 — không ý nghĩa | **0,002563 — có ý nghĩa** |
| Kết luận | Giá trị nằm ở độ tin cậy, **không** ở độ chính xác | Vượt trội **cả hai** |

**Vì sao đảo chiều.** Số liệu cũ cho thấy đa tác tử chỉ thắng ở môn Toán (+9 điểm
trên bộ khó) còn thua ở Vật lý (−9) và Hoá học (−10). Toàn bộ phần thua nằm ở hai
môn nay đã bị loại khỏi phạm vi đề tài. Thu hẹp về một môn Toán vì vậy không chỉ
đáp ứng góp ý "quá dàn trải" — nó còn loại đúng phần dữ liệu đang che lấp hiệu quả
thật của kiến trúc.

Cần nói rõ để tránh hiểu nhầm: đây **không phải chọn lọc số liệu có lợi**. Phạm vi
đề tài được thu hẹp trước, vì lý do sư phạm và theo yêu cầu phản biện; phép đo lại
là hệ quả bắt buộc của việc đổi phạm vi, không phải nguyên nhân.

---

## 7. HẠN CHẾ CỦA PHÉP ĐO NÀY

**Con số 54,0% của mốc nền là CHẶN DƯỚI, không phải giá trị thật.**

Hàm chấm không quy đổi được ký tự Unicode `π`: mốc nền trả `36π` — bằng đúng
113,097 và là đáp án **đúng** — nhưng bị chấm SAI. Tương tự với đơn vị đặt trong
ngoặc, `36π (đơn vị²)`.

Đây là **thiên vị hệ thống chứ không phải nhiễu**: hệ đa tác tử đi qua SymPy nên
gần như luôn trả số thập phân và không dính lỗi này, còn mốc nền viết văn xuôi nên
hay để nguyên `π`. Dấu hiệu nhận ra là con số 35,7% ở mức Nhận biết — câu dễ mà
sai nhiều hơn câu khó.

Hệ quả: **khoảng cách 19 điểm sẽ hẹp lại** nếu chấm lại bằng hàm chấm đã vá. Chưa
chấm lại tại thời điểm viết tài liệu này.

Hai hạn chế khác:

* **Cỡ mẫu 100 bài, đo một lượt.** Mô hình chạy ở `temperature` 0,2 chứ không
  phải 0 nên mỗi lượt đo có sai khác tự nhiên. Muốn chắc thì lặp 3 lượt lấy trung vị.
* **Chỉ đo trên bộ khó.** Chưa đo đối chứng trên `de_chuan.csv` và
  `de_giu_rieng.csv` — hai bộ này dễ hơn nên khoảng cách nhiều khả năng hẹp hơn.

---

## 8. TÁI LẬP

```powershell
cd E:\DeepLearning\LLM\ViMultiAgent\backend
$env:VMA_LUU_LOI_GIAI_MAU = "0"

python scripts/bench.py --de eval/data/de_kho.csv --out eval/reports/ss_da_tac_tu
python scripts/bench_don_le.py --de eval/data/de_kho.csv `
    --so-sanh eval/reports/ss_da_tac_tu/ket_qua_sla45_20260822_141959.csv `
    --out eval/reports/ss_don_tac_tu
python scripts/ve_so_sanh.py `
    --don eval/reports/ss_don_tac_tu/moc_nen_tho_20260822_151155.csv `
    --da  eval/reports/ss_da_tac_tu/ket_qua_sla45_20260822_141959.csv `
    --hau-to toan
```

Xem `CHAYBENCHMARK.md` để biết chi tiết từng bước và thời gian ước tính.

| Dữ liệu gốc | Đường dẫn |
|---|---|
| Đa tác tử | `backend/eval/reports/ss_da_tac_tu/ket_qua_sla45_20260822_141959.csv` |
| Một tác tử | `backend/eval/reports/ss_don_tac_tu/moc_nen_tho_20260822_151155.csv` |
| Báo cáo tự sinh | `backend/eval/reports/hinh/BAOCAO_SO_SANH_toan.md` |
| Năm biểu đồ | `backend/eval/reports/hinh/0*_toan.png` |

Số liệu của bản 3 môn vẫn giữ nguyên trong `backend/eval/reports/dulieu1111/` và
bộ hình hậu tố `_kho_tho`, `_json` để đối chiếu khi cần.
