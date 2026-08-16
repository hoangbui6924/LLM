# Đối chứng kiến trúc: MỘT TÁC TỬ vs ĐA TÁC TỬ

*Dựng lúc 13/08/2026 00:50 · 300 bài ghép cặp*

## Nguồn dữ liệu

| Nhánh | Tệp CSV |
|---|---|
| Một tác tử | `moc_nen_tho_20260813_001657.csv` |
| Đa tác tử | `ket_qua_sla45_20260809_232605.csv` |

Chỉ đổi **một biến duy nhất là kiến trúc**: cùng mô hình `qwen3:4b`, cùng `temperature`, cùng `num_ctx`, cùng tắt chế độ suy nghĩ, cùng bộ đề, và cùng hàm chấm — `cham()` của `bench.py` được dùng lại trực tiếp cho cả hai nhánh thay vì viết hai bản.

## Bốn chỉ số cốt lõi

![Bốn chỉ số cốt lõi](01_chi_so_cot_loi_kho_tho.png)

| Chỉ số | Một tác tử | Đa tác tử | Chênh |
|---     |---:        |---:       |---:   |
| Độ chính xác (%) | 75.3 | 72.0 | -3.3 |
| Phát hiện lời giải sai (%) | 0.0 | 45.2 | +45.2 |
| Đạt mốc 45 s (%) | 92.0 | 100.0 | +8.0 |
| Ra được đáp án (%) | 92.0 | 98.7 | +6.7 |

Dòng *phát hiện lời giải sai* bằng **0 theo kiến tạo** ở mốc nền, không phải do đo kém: một lời gọi LLM đơn lẻ không có đường tính toán độc lập nào để đối chiếu, nên đúng và sai được trả về với cùng một giọng tự tin. Đây là khác biệt về **bản chất**, không phải về mức độ — và là lập luận mạnh nhất của kiến trúc đa tác tử, mạnh hơn vài điểm phần trăm độ chính xác.

## Giá phải trả: độ trễ

![Thời gian](02_thoi_gian_kho_tho.png)

| Thống kê thời gian | Một tác tử | Đa tác tử |
|---|---:|---:|
| Trung bình (s) | 28.1 | 30.9 |
| Trung vị p50 (s) | 27.0 | 31.3 |
| Bách phân vị 95 (s) | 45.0 | 39.6 |
| Số lượt gọi LLM mỗi bài | 1 | 4–6 |

Đa tác tử chậm hơn **2.8 giây** mỗi lượt, tức **1.1 lần**. Đây là cái giá của việc chạy thêm Planner, Router, bộ tính lại, Verify và Explain.

## Ma trận radar tổng hợp

![Radar](03_radar_kho_tho.png)

Bốn trục là tỉ lệ phần trăm đo trực tiếp. Trục **Tốc độ** quy đổi từ thời gian theo công thức `100 × (45 − t) / 45`, chặn trong [0, 100]; mốc 45 giây là ngân sách đã đăng ký của đề tài chứ không phải hằng số tự đặt.

> Lưu ý khi đọc: diện tích hình radar **không** có ý nghĩa toán học, và đổi thứ tự trục là đổi hẳn hình dạng. Dùng nó để nhìn nhanh hình thái mạnh–yếu, đừng dùng để so hơn kém — việc đó thuộc về các hình cột.

## Khoảng cách nở ra ở đâu

![Phân rã](04_phan_ra_kho_tho.png)

| Môn | Một tác tử | Đa tác tử | Chênh | Số bài |
|---|---:|---:|---:|---:|
| Toán | 61.0% | 70.0% | +9.0 | 100 |
| Vật lý | 75.0% | 66.0% | -9.0 | 100 |
| Hoá học | 90.0% | 80.0% | -10.0 | 100 |

| Mức độ | Một tác tử | Đa tác tử | Chênh | Số bài |
|---|---:|---:|---:|---:|
| Nhận biết | 73.0% | 75.7% | +2.7 | 37 |
| Thông hiểu | 81.2% | 82.6% | +1.4 | 69 |
| Vận dụng | 81.7% | 78.8% | -2.9 | 104 |
| Vận dụng cao | 64.4% | 54.4% | -10.0 | 90 |

## Hiệu quả ròng và kiểm định thống kê

![Hiệu quả ròng](05_hieu_qua_rong_kho_tho.png)

| | Đa tác tử ĐÚNG | Đa tác tử SAI |
|---|---:|---:|
| **Một tác tử ĐÚNG** | 177 | 49 |
| **Một tác tử SAI** | 39 | 35 |

- Đa tác tử **cứu được 39 bài** mà một tác tử làm sai.
- Đa tác tử **làm hỏng 49 bài** mà một tác tử làm đúng.
- Ròng: **-10 bài**.
- **McNemar** (dạng chính xác, hai phía): **p = 0.3374** — **chưa** có ý nghĩa thống kê ở mức 0,05.

Dùng kiểm định ghép cặp chứ không so hai tỉ lệ rời nhau: cùng một bộ đề chạy hai kiến trúc là thiết kế **đo lặp trên cùng đối tượng**. Chỉ hai ô lệch nhau mang thông tin — bài cả hai cùng đúng hay cùng sai không nói gì về việc kiến trúc nào hơn. Dùng bản chính xác thay vì xấp xỉ khi-bình-phương vì số bài lệch chỉ có 88, dưới ngưỡng ≥ 25 mà xấp xỉ đòi hỏi.

> **Đọc trung thực:** chênh lệch quan sát được chưa loại trừ được ngẫu nhiên ở cỡ mẫu này. Cần thêm bài hoặc thêm lượt lặp mới kết luận chắc về độ chính xác. Lưu ý kết luận này **chỉ áp cho độ chính xác** — khác biệt về năng lực tự kiểm chứng không cần kiểm định vì nó đúng theo kiến tạo.

## Cách dựng lại

```bash
cd ViMultiAgent/backend
set VMA_LUU_LOI_GIAI_MAU=0
python scripts/bench_don_le.py --de eval/data/de_giu_rieng.csv \
    --che-do <tho|json> --so-sanh eval/reports/ket_qua_sla45_20260809_232605.csv
python scripts/ve_so_sanh.py --don eval/reports/moc_nen_tho_20260813_001657.csv \
    --da eval/reports/ket_qua_sla45_20260809_232605.csv
```