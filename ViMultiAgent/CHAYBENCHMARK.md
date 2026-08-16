# Chạy benchmark so sánh một tác tử vs đa tác tử

Ba bước, chạy tuần tự trong PowerShell. Tổng cộng khoảng 2,5–3 giờ.

## Chuẩn bị

Ollama phải đang chạy và có model `qwen3:4b` (kiểm tra bằng `ollama list`).
Đóng giao diện web trong lúc đo — tranh GPU làm sai số đo thời gian.

```powershell (chạy lệnh dưới)
cd e:\DeepLearning\ViMultiAgent\backend
$env:VMA_LUU_LOI_GIAI_MAU = "0"
```

Biến môi trường trên bắt buộc phải có, nếu không kho lời giải lớn dần giữa chừng
và lần chạy sau sẽ ra số khác.

## Bước 1 — đo đa tác tử (~1,5 giờ)

```powershell(chạy lệnh dưới)
python scripts/bench.py --de eval/data/de_chuan.csv
```

Ghi ra `eval/reports/ket_qua_sla45_<ngày_giờ>.csv`.

## Bước 2 — đo một tác tử (~30 phút mỗi chế độ)

```powershell(chạy lệnh dưới)
$DA = (Get-ChildItem eval\reports\ket_qua_sla45_*.csv | Sort-Object LastWriteTime | Select-Object -Last 1).Name

python scripts/bench_don_le.py --de eval/data/de_chuan.csv --che-do tho  --so-sanh eval/reports/$DA
python scripts/bench_don_le.py --de eval/data/de_chuan.csv --che-do json --so-sanh eval/reports/$DA
```

`tho` là một lời gọi LLM văn xuôi tự do, `json` là một lời gọi có ép schema.
Cờ `--so-sanh` tự ghép cặp với kết quả bước 1 và in bảng đối chứng kèm kiểm định
McNemar, đồng thời ghi ra `so_sanh_<chế độ>_*.md`.

## Bước 3 — vẽ hình (vài giây)

```powershell(chạy lệnh dưới)
$DON = (Get-ChildItem eval\reports\moc_nen_tho_*.csv | Sort-Object LastWriteTime | Select-Object -Last 1).Name

python scripts/ve_so_sanh.py --don eval/reports/$DON --da eval/reports/$DA
```

Ra 5 hình PNG và 1 báo cáo Markdown trong `eval/reports/hinh/`.

---

## Chạy thử nhanh trước

Thêm `--so-luong 15` vào bước 1 và 2 để chạy 15 bài lấy trải đều, mất khoảng
15 phút cho cả quy trình. Dùng để xác nhận mọi thứ thông trước khi đo thật.

## Lưu ý

- Bước 2 phải dùng **đúng bộ đề** của bước 1. Ghép nhầm bộ đề vẫn ra bảng đẹp mà
  vô nghĩa; script sẽ in cảnh báo `trùng id nhưng KHÁC ĐỀ` nếu gặp.
- Bộ đề khác có sẵn: `eval/data/de_giu_rieng.csv` (150 bài),
  `eval/data/de_kho.csv` (300 bài khó).
- McNemar ra `p >= 0.05` không phải lỗi — nghĩa là cỡ mẫu chưa đủ để kết luận chắc
  về chênh lệch độ chính xác. Thêm `--n 3` để lặp 3 lượt.

Bộ giữ riêng (150 bài)


ket_qua_sla45_20260809_205118.csv  (đa tác tử)
   ├── moc_nen_tho_20260812_205223.csv    (một tác tử, văn xuôi)
   └── moc_nen_json_20260812_210740.csv   (một tác tử, ép schema)
Bộ khó (300 bài)


ket_qua_sla45_20260809_232605.csv  (đa tác tử)
   ├── moc_nen_tho_20260813_001657.csv
   └── moc_nen_json_20260813_004953.csv