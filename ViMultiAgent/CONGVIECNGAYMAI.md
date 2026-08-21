# CÔNG VIỆC NGÀY MAI

Cập nhật 2026-08-21. Bối cảnh: đã hạ dự án từ 3 môn (Toán–Lý–Hoá) xuống
**1 môn Toán THPT**, kiến trúc còn 2 Subject Agent là **Đại số** và **Hình học**.

**F và G đã xong ngày 2026-08-21** — chương trình nay chạy bằng một cú bấm
`chay.bat`, giao diện và API cùng cổng 8000.

Thứ tự còn lại: **H → B → C → D**. Lý do H lên đầu: nó là lỗi làm hỏng điểm
benchmark ở mục C, sửa sau khi đo là phải đo lại.

---

## A. ĐÃ XONG (không cần làm lại)

- Backend: `Subject = Literal["dai_so","hinh_hoc"]`, 2 agent, Router map 15 dạng
  bài → 2 phân môn qua `NHANH_CUA_DANG`.
- Xoá hẳn: `math_agent.py`, `physics_agent.py`, `chemistry_agent.py`,
  `tools/chem_tool.py`, `tools/units_tool.py`, `tests/test_khoi_luong_mol.py`.
- Verify: bỏ soát bảo toàn nguyên tố / khối lượng mol / thứ nguyên; thêm
  `_check_hinh_hoc` bắt đáp số âm cho thể tích, diện tích, độ dài, khoảng cách.
- 3 bộ đề: 600 → **200 bài** (de_chuan 50, de_giu_rieng 50, de_kho 100).
- Bộ sinh đề: `build_de_chuan` 25 mẫu, `build_de_kho` 36 mẫu, đã tách dai_so/hinh_hoc.
- `ml/`: dataset 15 nhãn dạng bài, đã cân bằng theo lớp (lệch 10× → 2×).
- Frontend: 3 nút Đại số / Giải tích / Hình học. `tsc --noEmit` sạch.
- **192/192 test pass.** Mã nguồn 0 tham chiếu Lý/Hoá.
- `npm run build` **chạy được**, exit 0, 1,43 giây, sinh ra `frontend/dist/`.

---

## F. XÂY DỰNG GIAO DIỆN — ✅ XONG 2026-08-21

- [x] **Biểu tượng đổi theo phân môn.** Nhãn agent thì vốn đã đúng (backend gửi
      `label`), nhưng biểu tượng kẹt ở `∑` vì hai Subject Agent dùng chung một ô
      nên `a.name` luôn là `dai_so_agent`. Thêm `AgentState.agent_that` giữ tên
      agent THỰC, biểu tượng và màu đọc theo trường đó.
- [x] **Hiện dạng bài + tầng định tuyến.** `topic`, `decided_by`,
      `phobert_confidence` trước chỉ nằm trong `result.route` của sự kiện `done`
      — tức chỉ thấy được sau khi chạy xong cả lượt. Nay `manager.py` phát kèm
      ngay ở sự kiện `done` của Router, giao diện hiện hai huy hiệu:
      `PhoBERT 0.99` và `toa_do_the_tich`.
- [x] Ba màu huy hiệu cho ba tầng (PhoBERT / luật từ khoá / LLM), có tooltip nêu
      chi phí từng tầng.
- [x] Icon `hinh_hoc_agent` giữ `△` — hợp, đối xứng với `∑` của đại số.

Đã kiểm: `tsc --noEmit` sạch, bundle chứa đủ chuỗi mới, 192/192 test pass.

---

## G. BUILD ĐỂ CHẠY CHƯƠNG TRÌNH CUỐI CÙNG — ✅ XONG 2026-08-21

- [x] **Mount `frontend/dist` vào FastAPI** (`backend/main.py`). Đặt SAU
      `include_router` — mount `/` bắt mọi đường dẫn, để trước thì nuốt luôn
      `/api` và `/docs`. Chưa build thì giữ endpoint JSON cũ, chế độ dev không đổi.
- [x] SPA fallback: dùng `html=True`. Giao diện không có router phía client
      (không có `react-router` trong deps) nên chừng đó là đủ.
- [x] Giữ `CORS_ORIGINS` cho chế độ dev, không xoá.
- [x] **SSE chạy đúng trên cùng origin** — đã kiểm thật, `text/event-stream`,
      436 chunk chữ chảy về bình thường.
- [x] **`chay.bat`** ở thư mục gốc: đặt `OLLAMA_MODELS` → bật Ollama nếu chưa
      chạy (chờ tối đa 30 giây) → build giao diện nếu thiếu `dist` → chạy uvicorn
      → mở trình duyệt.
- [x] `README.md` mục 3 viết lại: một cú bấm, cách thủ công, và chế độ dev.

**Kết quả đo end-to-end** (bản build, cùng cổng 8000):

| Bài | Router | Đáp án | Verify |
|---|---|---|---|
| Thể tích khối chóp (đáy 12, cao 5) | **PhoBERT** `toa_do_the_tich` 0,99 · **0 ms** | 20 ✅ | FAIL ❌ báo oan |
| Đạo hàm y = x³−3x²+2x tại x=1 | **PhoBERT** `dao_ham` · **0 ms** | −1 ✅ | PASS ✅ |

Tổng 33,8 giây, trong SLA 45 giây.

**Đáng chú ý:** Router nay đi qua PhoBERT ở **0 ms** thay vì rơi xuống LLM mất
~2000 ms như trước khi cân bằng dữ liệu.

**Việc phụ còn lại (không chặn):**
- [ ] Bundle JS **598 kB** (gzip 183 kB), Vite cảnh báo vượt 500 kB. Phần lớn là
      KaTeX + react-markdown. Có thể `dynamic import()` phần render Markdown.

---

## H. LỖI MỚI PHÁT HIỆN — Verify báo oan bài Hình học

Đo được khi kiểm thử G. Bài thể tích khối chóp ra đáp án **20 (đúng)** nhưng bị
Verify kết luận FAIL. Nguyên văn lời LLM:

> `Tính toán sai: 1/3 * 12 * 5 = 20 nhưng đúng là 20`

Nó tự mâu thuẫn trong một câu. Prompt `verify_agent.SYSTEM` đã có chốt chặn cho
dạng *"sai số 0"* và *"lệch 0%"* nhưng chưa có cho dạng **"X nhưng đúng là X"**.

**Nguyên nhân gốc sâu hơn:** bài hình học **không có phép kiểm tất định nào chạy
được** — `_check_arithmetic` báo "Không bước nào đủ dữ kiện để tính lại", còn
`tools/kiem_symbolic.py` chỉ nhận 5 dạng Đại số (`dao_ham`, `tich_phan`,
`gioi_han`, `phuong_trinh`, `tiep_tuyen`). Không có trọng tài SymPy thì Verify
buộc phải hỏi LLM, và đó là nguồn báo oan.

Đây đúng là điểm yếu mà `TAILIEU.md` từng ghi cho môn Hoá, nay **Hình học thừa kế**.

- [ ] Vá nhanh: thêm chốt chặn "hai vế bằng nhau thì là PASS" vào
      `verify_agent.SYSTEM`.
- [ ] Vá gốc: mở rộng `kiem_symbolic` sang các dạng hình học tính được —
      `toa_do_the_tich`, `toa_do_khoang_cach`, `toa_do_kc_diem_mp` đều có công
      thức đóng, SymPy tính lại được dễ dàng.
- [ ] Việc này ảnh hưởng trực tiếp tới điểm benchmark ở mục C — nên làm **trước**
      khi chạy đo.

---

## B. CHỈ SỐ PHOBERT

### B1. Chống overfit rồi mới đặt ngưỡng

**Vấn đề đo được:** train loss chạm 0,03 ngay epoch 6 rồi tụt còn 0,0216 ở epoch 12
— model học vẹt. val_acc chỉ 0,513.

So sánh hai lần train trên cùng tập con:

| Tập | Lần 1 (4 epoch, chưa cân bằng) | Lần 2 (12 epoch, đã cân bằng) |
|---|---|---|
| `seed` (câu viết tay) | 0,621 | **0,750** ↑ |
| `hard` (câu khó) | 0,800 | **0,600** ↓ |
| val_acc | 0,472 | 0,513 |

Giỏi hơn ở câu thường nhưng **kém đi ở câu khó** — mà `hard` mới là tập chứng minh
"vì sao cần học sâu", nên đây là bước lùi phải sửa.

**Việc cần làm** trong `ml/train_phobert.py`:
- [ ] Giữ **checkpoint có val_acc tốt nhất**, không lấy epoch cuối.
- [ ] Thêm weight decay (thử 0.01) và/hoặc early stopping.
- [ ] Train lại, mục tiêu: kéo `hard` về ≥ 0,80 mà không mất phần đã được ở `seed`.
- [ ] Thời gian tham khảo: 12 epoch trên 873 câu mất **3275 giây** (~55 phút).

### B2. Đặt lại `NGUONG_PHOBERT` trong `agents/router.py`

Hiện để **0,85**, là con số kế thừa từ bài toán 3 lớp cũ, chưa đo lại cho 15 lớp.

Bảng đo trên model hiện tại (168 câu val+test):

| Ngưỡng | Chốt được | Chính xác khi chốt |
|---|---|---|
| 0,70 | 115/168 | 77,4% |
| **0,85** | 99/168 | **83,8%** |
| 0,90 | 93/168 | 83,9% |
| 0,95 | 65/168 | 78,5% |
| 0,98 | 18/168 | 100% |

Độ tin cậy CÓ phân biệt được: đoán đúng trung vị 0,962, đoán sai trung vị 0,653.
Nhưng câu sai vẫn lên tới 0,977 nên không tin tuyệt đối được.

- [ ] Đo lại bảng này **sau khi** làm xong B1, rồi mới chốt ngưỡng.

---

## C. BENCHMARK — user đã nói "để sau"

- [ ] Chạy `python scripts/bench.py --de eval/data/de_chuan.csv` trên bộ 200 bài mới.
      Mất vài giờ suy luận LLM.
- [ ] Sau khi có số thật, cập nhật bảng số liệu trong: `BAOCAO.md`,
      `KETQUA_SO_SANH.md`, `sosanh.md`, `TAILIEU.md`, `ppt.md`.

**Lưu ý:** các bảng đó hiện vẫn là số đo cũ trên 600 bài 3 môn (kiểu "Lý 78,0% ·
Hoá 84,0%", kiểm định McNemar theo môn). Xoá dòng Lý/Hoá thì tổng và p-value còn
lại sai, nên phải đo lại chứ không sửa tay. **Không bịa số.**

---

## D. VIỆC NHỎ / CẦN QUYẾT ĐỊNH

### D1. `yeucaumoi.md` — cần user quyết
File này là **đề bài gốc của giảng viên** ("Xây 3 Subject Agent (Toán, Lý, Hóa)").
Tôi để nguyên vì sửa nó là sửa yêu cầu được giao. Cần user quyết có đụng vào không.

### D2. Test thiếu phủ 3 nhãn
`gioi_han`, `tiem_can_ngang`, `tiem_can_dung` có **0 câu trong test**.
Nguyên nhân: quy tắc chống rò rỉ giữ mọi biến thể cùng khuôn trong cùng một tập,
lớp chỉ có 2 khuôn thì dễ rơi hết vào train/val.
- [ ] Thêm khuôn thứ **ba** cho 3 lớp này trong `ml/build_dataset.py`.
- Không ảnh hưởng chất lượng model, chỉ làm test_acc kém chi tiết.

### D3. Bộ đề lệch nặng về Đại số
- `de_chuan` và `de_giu_rieng`: chỉ **4/50 bài hình học**.
- Gốc: `eval/build_de_chuan.py` chỉ có **2/25 mẫu** hình học (m19, m20).
- `de_kho` thì cân: 54 đại số / 46 hình học.
- [ ] Cân nhắc viết thêm mẫu hình học cho `build_de_chuan.py` rồi sinh lại bộ đề.

---

## E. LỆNH HAY DÙNG

```powershell
cd E:\DeepLearning\LLM\ViMultiAgent\backend

python ml/build_dataset.py                          # dựng lại dataset
python ml/train_phobert.py --epochs 12 --batch 16 --lr 3e-5
python -m pytest -q                                 # 192 test
python eval/build_de_chuan.py                       # sinh lại bộ đề chuẩn
python eval/build_de_kho.py                         # sinh de_kho + de_giu_rieng
python scripts/bench.py --de eval/data/de_chuan.csv # benchmark (lâu)
python -m uvicorn main:app --port 8000              # chạy backend
```

```powershell
cd E:\DeepLearning\LLM\ViMultiAgent\frontend

npx tsc --noEmit        # kiểm kiểu, không sinh file
npm run dev             # chế độ dev, cổng 5173, có proxy /api
npm run build           # sinh frontend/dist (1,4 giây)
npm run preview         # xem thử bản build — LƯU Ý: không có proxy /api
```
