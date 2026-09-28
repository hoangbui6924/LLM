# Chạy benchmark so sánh một tác tử vs đa tác tử

Ba bước, chạy tuần tự trong PowerShell. Tổng khoảng **1,7 giờ** cho bộ 100 bài khó.

## Chuẩn bị

Ollama phải đang chạy và có model `qwen3:4b`.

```powershell
$env:OLLAMA_MODELS = "E:\DeepLearning\Ollama\models"
ollama list
```

> Biến `OLLAMA_MODELS` là bắt buộc — model nằm ở ổ E, không phải thư mục mặc định
> `C:\Users\...\.ollama`. Thiếu nó Ollama báo không có model và đòi tải lại 2,5 GB.

Đóng giao diện web trong lúc đo — tranh GPU làm sai số đo thời gian.

```powershell
cd E:\DeepLearning\LLM\ViMultiAgent\backend
$env:VMA_LUU_LOI_GIAI_MAU = "0"
```

Biến trên bắt buộc phải có, nếu không kho lời giải lớn dần giữa chừng và lần chạy
sau sẽ ra số khác.

## Bước 1 — đo đa tác tử (~48 phút / 100 bài)

```powershell
python scripts/bench.py --de eval/data/de_kho.csv --out eval/reports/ss_da_tac_tu
```

Ghi ra `eval/reports/ss_da_tac_tu/ket_qua_sla45_<ngày_giờ>.csv`.

## Bước 2 — đo một tác tử (~50 phút / 100 bài)

```powershell
$DA = (Get-ChildItem eval\reports\ss_da_tac_tu\ket_qua_sla45_*.csv |
       Sort-Object LastWriteTime | Select-Object -Last 1).FullName

python scripts/bench_don_le.py --de eval/data/de_kho.csv --che-do tho `
    --so-sanh $DA --out eval/reports/ss_don_tac_tu
```

`tho` là một lời gọi LLM văn xuôi tự do, `json` là một lời gọi có ép schema. Cờ
`--so-sanh` tự ghép cặp với kết quả bước 1, in bảng chéo kèm kiểm định McNemar,
đồng thời ghi ra `so_sanh_<chế độ>_*.md`.

## Bước 3 — vẽ hình (vài giây)

```powershell
$DON = (Get-ChildItem eval\reports\ss_don_tac_tu\moc_nen_tho_*.csv |
        Sort-Object LastWriteTime | Select-Object -Last 1).FullName

python scripts/ve_so_sanh.py --don $DON --da $DA --hau-to toan
```

Ra 5 hình PNG và 1 báo cáo Markdown trong `eval/reports/hinh/`.

> **Luôn đặt `--hau-to`.** Không đặt thì tên tệp lấy theo dấu thời gian, và dễ đè
> lên bộ hình cũ. Bộ hậu tố `_kho_tho` và `_json` là số liệu bản 3 môn, cần giữ
> để đối chiếu.

---

## Chạy thử nhanh trước

Thêm `--so-luong 15` vào bước 1 và 2 để chạy 15 bài lấy trải đều, mất khoảng 15
phút cho cả quy trình. Dùng để xác nhận mọi thứ thông trước khi đo thật.

## Ba bộ đề có sẵn

| Tệp | Số bài | Ghi chú |
|---|---:|---|
| `eval/data/de_chuan.csv` | 50 | Bộ chuẩn — 46 Đại số, 4 Hình học |
| `eval/data/de_giu_rieng.csv` | 50 | **Bộ giữ riêng**, trùng 0% với bộ chuẩn |
| `eval/data/de_kho.csv` | 100 | Bộ khó — 54 Đại số, 46 Hình học, 65% mức VD/VDC |

Cả ba đều là **Toán THPT**, đã giải tay sẵn đáp án.

## Lưu ý

- Bước 2 phải dùng **đúng bộ đề** của bước 1. Ghép nhầm bộ đề vẫn ra bảng đẹp mà
  vô nghĩa; script sẽ in cảnh báo `trùng id nhưng KHÁC ĐỀ` nếu gặp.
- McNemar ra `p >= 0,05` không phải lỗi — nghĩa là cỡ mẫu chưa đủ để kết luận chắc.
  Thêm `--n 3` để lặp 3 lượt.
- `de_chuan.csv` chỉ có 4/50 bài hình học nên **không dùng để đánh giá phần Hình
  học**. Dùng `de_kho.csv` cho việc đó.

---

## Lần đo gần nhất — 22/08/2026

Bộ khó 100 bài Toán. Kết quả đầy đủ trong `KETQUA_SO_SANH.md`.

| | Một tác tử | Đa tác tử |
|---|---:|---:|
| Độ chính xác | 54,0% | **73,0%** |
| Phát hiện lời giải sai | 0% | **63%** |
| Thời gian TB | 30,2 s | 31,3 s |

McNemar **p = 0,002563** — có ý nghĩa thống kê. Đa tác tử cứu 28 bài, làm hỏng 9.

```
ss_da_tac_tu/ket_qua_sla45_20260822_141959.csv    (đa tác tử)
   └── ss_don_tac_tu/moc_nen_tho_20260822_151155.csv   (một tác tử, văn xuôi)
```

> **Cảnh báo khi trích dẫn:** 54,0% của mốc nền là **chặn dưới**. Hàm chấm chưa
> quy đổi được ký tự `π`, mà mốc nền hay trả `36π` thay vì `113.097`. Khoảng cách
> 19 điểm sẽ hẹp lại nếu chấm lại. Xem mục 7 của `KETQUA_SO_SANH.md`.

## Dữ liệu bản 3 môn (cũ, giữ để đối chiếu)

Số liệu 12–13/08/2026 trên 450 bài Toán – Lý – Hoá nằm ở
`eval/reports/dulieu1111/` và bộ hình hậu tố `_kho_tho`, `_json`.
**Không dùng cho báo cáo hiện tại** — hệ thống đã đổi phạm vi còn một môn Toán.
