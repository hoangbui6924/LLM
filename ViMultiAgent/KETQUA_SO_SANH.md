# KẾT QUẢ ĐỐI CHỨNG KIẾN TRÚC — MỘT TÁC TỬ vs ĐA TÁC TỬ

*Đo ngày 12–13/08/2026 · **bốn phép đo** trên **hai bộ đề rời nhau, 450 bài** ·
mô hình `qwen3:4b`*

---

## TÓM TẮT MỘT ĐOẠN

Qua **bốn phép đo độc lập trên 450 bài thuộc hai bộ đề rời nhau**, kiến trúc đa tác
tử **không cho độ chính xác cao hơn** một lời gọi LLM đơn lẻ: cả bốn lần đều
p > 0,33, và dấu của hiệu quả ròng **đảo chiều giữa các lần đo** (−5, +5, −10, −3) —
chữ ký của nhiễu, không phải của một hiệu ứng thật. Phép đo mạnh nhất (bộ khó,
300 bài, 88 cặp lệch — vượt xa ngưỡng 25 mà kiểm định đòi) cho p = 0,3374.

Ngược lại, **ba chỉ số độ tin cậy lặp lại nhất quán trên cả hai bộ đề**: phát hiện
lời giải sai 53,1% / 45,2% so với **0% theo kiến tạo**; tuân thủ ngân sách 45 giây
100% so với 88,7% / 92,0%; tỉ lệ trả về được đáp án 99,3% / 98,7% so với
88,7% / 92,0%.

> **Kết luận: giá trị của kiến trúc đa tác tử nằm ở ĐỘ TIN CẬY, không nằm ở ĐỘ
> CHÍNH XÁC.**

Đây đúng là điều báo cáo tuyên bố ở phần Tóm tắt, và nay đã có mốc nền để chứng minh
thay vì chỉ khẳng định. Một phát hiện lặp lại được trên hai bộ đề độc lập vững hơn
nhiều so với một giá trị p may mắn ở một lần đo.

---

## BẢNG TỔNG HỢP BỐN PHÉP ĐO

| Phép đo | n | Mốc nền | Đa tác tử | Ròng | Cặp lệch | p (McNemar) |
|---|---:|---:|---:|---:|---:|---:|
| Giữ riêng · thô | 150 | 82,0% | 78,7% | −5 | 29 | 0,4583 |
| Giữ riêng · JSON | 150 | 75,3% | 78,7% | +5 | 37 | 0,5114 |
| **Khó · thô** | **300** | **75,3%** | **72,0%** | **−10** | **88** | **0,3374** |
| Khó · JSON | 300 | 73,0% | 72,0% | −3 | 89 | 0,8323 |

Không phép đo nào đạt ý nghĩa thống kê ở mức 0,05. Hai phép đo trên bộ khó có cỡ
mẫu lệch 88 và 89, tức **đã đủ lực thống kê** — kết quả "không chênh lệch" ở đây là
một kết luận có căn cứ, không phải hệ quả của việc thiếu mẫu.

### Giả thuyết "phân rã vai trả công ở bài khó" — đã bác bỏ

| Vận dụng cao | Mốc nền | Đa tác tử | |
|---|---:|---:|---|
| Bộ giữ riêng (n = 17) | 47,1% | **52,9%** | đa tác tử dẫn |
| **Bộ khó (n = 90)** | **64,4%** | 54,4% | **đảo chiều** |

Tín hiệu quan sát được ở n = 17 **không lặp lại** khi tăng lên n = 90 mà còn lật
ngược dấu (ròng −9, p = 0,211). Đây là ví dụ điển hình của một tín hiệu cỡ mẫu nhỏ
không có thật. Bộ đề khó có 65% số bài ở mức Vận dụng và Vận dụng cao (194/300) so
với 35% ở bộ giữ riêng, nên nếu giả thuyết đúng thì đây là nơi nó phải lộ ra rõ nhất.

Phân rã theo môn trên bộ khó cũng không nhóm nào đạt ý nghĩa: Toán ròng +9
(p = 0,122), Vật lý ròng −9 (p = 0,188), Hoá học ròng −10 (p = 0,064 — nhóm gần
ngưỡng nhất, và nghiêng về **phía mốc nền**).

---

## 1. Thiết kế phép so sánh

Chỉ đổi **một biến duy nhất là kiến trúc**:

| Giữ y nguyên | Cho khác |
|---|---|
| Mô hình `qwen3:4b` qua Ollama, cục bộ | có/không Planner, Router, Recompute, Verify, Explain |
| `temperature` 0,2 · `num_ctx` 4096 | có/không tầng kiểm chứng tất định |
| Chế độ suy nghĩ: tắt | số lượt gọi LLM: 1 so với 4–6 |
| Bộ đề `de_giu_rieng.csv` (150 bài) | |
| **Hàm chấm** — dùng lại trực tiếp `cham()` của `bench.py` | |

Hàm chấm là chỗ dễ hỏng nhất nên cố ý không viết bản riêng: `cham()` biết đọc đáp
án dạng phân số (`5/36`), căn thức (`√73`), và biết quy đổi đơn vị (`0,0018 m` ↔
`1,8 mm`). Hai thước chấm lệch nhau một chi tiết là đủ làm cả phép so sánh vô nghĩa.

**Ngân sách token cấp trọn cho mốc nền: 2750 token** — đúng bằng tổng ngân sách hệ
đa tác tử tiêu cho một bài (Planner 400 + Subject 1100 + Verify 350 + Explain 900).
Mốc nền phải làm mọi việc trong một lượt nên cắt bớt là tạo lợi thế giả cho phía
đa tác tử. Cấp dư còn hơn cấp thiếu: mốc nền càng mạnh thì kết luận càng chắc.

Thang **ba nấc** để tách được đóng góp của từng cơ chế:

| Nấc | Kiến trúc | Đóng góp đo được khi lên nấc sau |
|---|---|---|
| 1 | Một lời gọi, văn xuôi tự do | — |
| 2 | Một lời gọi, ép schema `Solution` | ràng buộc đầu ra theo lược đồ |
| 3 | Hệ đa tác tử đầy đủ | phân rã vai + tầng kiểm chứng |

---

## 2. Kết quả ba nấc

| | 1. Một tác tử (thô) | 2. Một tác tử (JSON) | 3. Đa tác tử |
|---|---:|---:|---:|
| **Độ chính xác** | **82,0%** | 75,3% | 78,7% |
| **Phát hiện lời giải sai** | 0% | 0% | **53,1%** |
| **Đạt mốc 45 s** | 88,7% | **100%** | **100%** |
| **Ra được đáp án** | 88,7% | **100%** | 99,3% |
| **Thời gian trung bình** | 22,0 s | **6,1 s** | 30,4 s |
| Số lượt gọi LLM / bài | 1 | 1 | 4–6 |

![Bốn chỉ số cốt lõi](backend/eval/reports/hinh/01_chi_so_cot_loi_tho.png)

![Thời gian](backend/eval/reports/hinh/02_thoi_gian_tho.png)

![Radar](backend/eval/reports/hinh/03_radar_tho.png)

---

## 3. Đối chứng ghép cặp và kiểm định thống kê

Cùng một bộ đề chạy hai kiến trúc là thiết kế **đo lặp trên cùng đối tượng**, nên
dùng kiểm định ghép cặp chứ không so hai tỉ lệ rời nhau. Chỉ hai ô lệch nhau mang
thông tin — bài cả hai cùng đúng hay cùng sai không nói gì về việc kiến trúc nào hơn.

### Nấc 1 (thô) so với đa tác tử

| | Đa tác tử ĐÚNG | Đa tác tử SAI |
|---|---:|---:|
| **Một tác tử ĐÚNG** | 106 | 17 |
| **Một tác tử SAI** | 12 | 15 |

- Đa tác tử **cứu được 12 bài**, **làm hỏng 17 bài** → ròng **−5 bài**.
- **McNemar (chính xác, hai phía): p = 0,4583** → **chưa** có ý nghĩa thống kê.

### Nấc 2 (JSON) so với đa tác tử

| | Đa tác tử ĐÚNG | Đa tác tử SAI |
|---|---:|---:|
| **Một tác tử ĐÚNG** | 97 | 16 |
| **Một tác tử SAI** | 21 | 16 |

- Đa tác tử **cứu được 21 bài**, **làm hỏng 16 bài** → ròng **+5 bài**.
- **McNemar (chính xác, hai phía): p = 0,5114** → **chưa** có ý nghĩa thống kê.

![Hiệu quả ròng](backend/eval/reports/hinh/05_hieu_qua_rong_tho.png)

Dùng bản **chính xác (nhị thức)** chứ không phải xấp xỉ khi-bình-phương: số bài lệch
chỉ 29 và 37, quanh ngưỡng ≥ 25 mà xấp xỉ đòi hỏi.

> **Kết luận đúng về độ chính xác:** trên bộ đề này, **hai kiến trúc không phân biệt
> được**. Không được viết "đa tác tử chính xác hơn", cũng không được viết "mốc nền
> chính xác hơn" — cả hai đều vượt quá dữ liệu. Hai nấc mốc nền còn cho ra dấu chênh
> **ngược nhau** (−5 và +5 bài), càng củng cố rằng khác biệt này là nhiễu.

---

## 4. Ba năng lực đa tác tử thắng dứt khoát — lặp lại trên cả hai bộ đề

| Chỉ số | Bộ giữ riêng (150 bài) | Bộ khó (300 bài) |
|---|---|---|
| Phát hiện lời giải sai | **53,1%** so với 0% | **45,2%** so với 0% |
| Đạt mốc 45 s | **100%** so với 88,7% | **100%** so với 92,0% |
| Ra được đáp án | **99,3%** so với 88,7% | **98,7%** so với 92,0% |

Ba chỉ số này **không phụ thuộc vào lần đo nào may mắn**: chúng giữ nguyên chiều và
gần nguyên độ lớn qua hai bộ đề rời hẳn nhau. Đó là điều khiến chúng dùng làm luận
cứ được, còn chênh lệch độ chính xác thì không.

**Một hạn chế phải ghi trung thực:** năng lực phát hiện lời giải sai **tụt từ 53,1%
xuống 45,2%** khi độ khó của đề tăng — tầng kiểm chứng yếu đi đúng lúc cần nhất. Cả
hai con số đều còn cách xa ngưỡng 85% đã đăng ký.

### 4.1. Phát hiện lời giải sai — 53,1% / 45,2% so với 0%

Đây **không phải** kết quả đo kém của mốc nền mà là **0 theo kiến tạo**: một lời gọi
LLM đơn lẻ không có đường tính toán độc lập nào để đối chiếu, nên đúng và sai được
trả về với cùng một giọng tự tin. Khác biệt về **bản chất**, không phải về mức độ —
và vì thế không cần kiểm định thống kê.

Trong bối cảnh giáo dục đây là chỉ số quan trọng nhất: người học ở đúng trình độ cần
dùng công cụ này lại chính là người không đủ năng lực phát hiện lỗi của nó.

### 4.2. Giữ ngân sách thời gian — 100% so với 88,7%

**17/150 lượt của mốc nền quá hạn 45 giây và trả về rỗng.** Toàn bộ là quá hạn,
không có ngoại lệ chương trình nào. Phân bố tập trung đúng vào bài khó:

| | VDC | VD | TH | NB |
|---|---:|---:|---:|---:|
| Số ca quá hạn | 7 | 6 | 4 | 0 |

| | Lý | Hoá | Toán |
|---|---:|---:|---:|
| Số ca quá hạn | 10 | 6 | 1 |

Đây là **lỗi kiến trúc, không phải rủi ro đo**. Hệ đa tác tử có Manager quản ngân
sách: trước mỗi bước tốn kém nó kiểm thời gian còn lại, hết giờ thì bỏ bước tinh
chỉnh, và chặn cứng Explain bằng `asyncio.timeout`. Mốc nền không có cơ chế nào nên
cứ thế trôi qua mốc rồi trả về rỗng. **Mốc nền hỏng đúng ở những bài người dùng cần
nó nhất.**

### 4.3. Luôn trả về đáp án — 99,3% so với 88,7%

Hệ quả trực tiếp của mục trên, cộng thêm cơ chế cứu đáp án và đường cứu JSON bị cắt.

---

## 5. Khoảng cách nở ra ở đâu

![Phân rã](backend/eval/reports/hinh/04_phan_ra_tho.png)

| Môn | Một tác tử | Đa tác tử | Chênh |
|---|---:|---:|---:|
| Toán | 82,0% | 82,0% | 0,0 |
| Vật lý | 76,0% | 70,0% | −6,0 |
| Hoá học | 88,0% | 84,0% | −4,0 |

| Mức độ | Một tác tử | Đa tác tử | Chênh | n |
|---|---:|---:|---:|---:|
| Nhận biết | 96,2% | 90,4% | −5,8 | 52 |
| Thông hiểu | 84,8% | 80,4% | −4,4 | 46 |
| Vận dụng | 74,3% | 71,4% | −2,9 | 35 |
| **Vận dụng cao** | 47,1% | **52,9%** | **+5,8** | 17 |

**Vận dụng cao là mức duy nhất đa tác tử dẫn**, và khoảng cách thu hẹp đều theo độ
khó tăng dần — đúng giả thuyết rằng phân rã vai chỉ trả công ở bài cần nhiều bước.
Nhưng n = 17, **không đủ để kết luận mạnh**; đây là hướng cần đo thêm trên
`de_kho.csv` (300 bài), không phải một phát hiện đã chốt.

---

## 6. Việc nên làm với báo cáo

Số liệu này **không mâu thuẫn** với luận điểm trung tâm của BAOCAO.md:

> *"Điểm khác biệt của hệ thống không nằm ở việc gọi một mô hình ngôn ngữ để sinh
> lời giải — điều bất kỳ ứng dụng nào cũng làm được — mà nằm ở kiến trúc kiểm chứng"*

Ba thứ đa tác tử thắng đều đúng là ba thứ câu trên tuyên bố nó thắng. Thứ bị bác bỏ
chỉ là **giả định ngầm** rằng phân rã vai còn kéo độ chính xác lên — giả định báo cáo
chưa từng viết ra, và nay có bằng chứng để chủ động nói nó không đúng thay vì để
phản biện phát hiện.

Ba việc nên làm:

1. **Thêm mốc nền vào Chương 4.** Con số 78,7% hiện đứng một mình, không có gì để so;
   người đọc không biết một lời gọi trần đạt bao nhiêu.
2. **Phát biểu lại đóng góp** theo hướng độ tin cậy: *"kiến trúc đa tác tử đổi 1,4
   lần thời gian lấy 53,1% năng lực tự phát hiện lỗi và 100% tuân thủ ngân sách, ở
   mức độ chính xác không đổi"*. Đây là phát biểu **mạnh hơn và đứng vững hơn** một
   khẳng định về độ chính xác mà p = 0,46 không đỡ nổi.
3. **Đã đo thêm trên `de_kho.csv`** (300 bài, ngày 13/08/2026) — kết quả bác bỏ giả
   thuyết Vận dụng cao, xem Bảng tổng hợp bốn phép đo ở đầu tài liệu. **Không nên đo
   thêm lần thứ năm để tìm một kết quả thuận lợi hơn**: bốn phép đo đã cho bốn giá
   trị p trong khoảng 0,33–0,83 với dấu đảo chiều, và hai phép đo trên bộ khó đã đủ
   lực thống kê. Đo thêm chỉ sinh ra một dấu ngẫu nhiên nữa, và việc chọn bộ số nào
   để công bố sẽ do kết quả quyết định — đó chính là thứ làm hỏng giá trị của cả
   chiến dịch đo.

### Cách trình bày hình trong báo cáo

**Dùng trọn bộ `_tho`** (mốc nền văn xuôi tự do) làm hình chính: đó là mốc nền mạnh
nhất nên kết luận rút ra từ nó bảo thủ nhất, khó bị vặn nhất. Bộ `_json` đưa vào phụ
lục làm đối chứng phụ.

**Tuyệt đối không trộn hai bộ hình.** Số sẽ không khớp và phản biện dò ra trong một
phút: bảng chéo bộ `_tho` cộng lại ra 123/150 = 82,0%, còn bộ `_json` ra 113/150 =
75,3%. Đặt hình bốn chỉ số của bộ này cạnh hình hiệu quả ròng của bộ kia là mâu
thuẫn nội tại.

**Thứ tự:** hình bốn chỉ số trước (dựng bối cảnh), hình hiệu quả ròng sau (trả lời
câu "chênh lệch đó có thật không"). Đảo lại thì người đọc gặp giá trị p khi chưa biết
nó đang kiểm định điều gì.

---

## 7. Tệp dữ liệu và cách dựng lại

| Loại | Đường dẫn |
|---|---|
| **Bộ giữ riêng** — đa tác tử | `backend/eval/reports/ket_qua_sla45_20260809_205118.csv` |
| **Bộ giữ riêng** — mốc nền | `backend/eval/reports/moc_nen_{tho,json}_20260812_*.csv` |
| **Bộ khó** — đa tác tử | `backend/eval/reports/ket_qua_sla45_20260809_232605.csv` |
| **Bộ khó** — mốc nền | `backend/eval/reports/moc_nen_{tho,json}_20260813_*.csv` |
| Hình (hậu tố `_tho`, `_json`, `_kho_tho`) | `backend/eval/reports/hinh/` |
| MD chi tiết từng phép đo | `backend/eval/reports/so_sanh_*.md` |
| Script mốc nền | `backend/scripts/bench_don_le.py` |
| Script vẽ hình | `backend/scripts/ve_so_sanh.py` |

Tổng thời gian máy: khoảng 5 giờ cho bốn phép đo mốc nền. Hai nhánh đa tác tử không
phải chạy lại vì đã có sẵn kết quả trên đúng hai bộ đề này.

```bash
cd ViMultiAgent/backend
set VMA_LUU_LOI_GIAI_MAU=0          # không bơm lời giải vào memory pool khi đo

python scripts/bench_don_le.py --de eval/data/de_giu_rieng.csv --che-do tho \
    --so-sanh eval/reports/ket_qua_sla45_20260809_205118.csv
python scripts/bench_don_le.py --de eval/data/de_giu_rieng.csv --che-do json \
    --so-sanh eval/reports/ket_qua_sla45_20260809_205118.csv

python scripts/ve_so_sanh.py --don eval/reports/moc_nen_tho_....csv \
    --da eval/reports/ket_qua_sla45_20260809_205118.csv --hau-to tho
```

Prompt của mốc nền nằm trong `scripts/bench_don_le.py`, biến `SYSTEM_THO` và
`SYSTEM_JSON` — nên đưa vào phụ lục báo cáo, vì câu hỏi đầu tiên của phản biện sẽ là
*"các anh có dìm mốc nền không"*.

Thời gian máy đã tốn: nấc 1 khoảng 55 phút, nấc 2 khoảng 15 phút. Nhánh đa tác tử
không phải chạy lại vì đã có sẵn kết quả trên đúng bộ đề này.
