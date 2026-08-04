# Kế hoạch 5 ngày — bản đã cắt phạm vi

> Thay thế lộ trình 8 tuần ở [01](./01-problem-and-architecture.md) và [02](./02-training-plan.md).
> Hạn: báo cáo + trình chiếu sản phẩm sau 5 ngày.

---

## 1. Những gì đã bị CẮT, và vì sao

Mọi thứ cần `docker`, cần build step, hoặc cần học một framework mới đều bị loại.
Không phải vì chúng dở, mà vì mỗi thứ trong đó là một buổi tối debug mà lịch này không có.

| Bỏ | Thay bằng | Lý do |
|---|---|---|
| Qdrant (docker) | numpy + BM25 tự viết trong RAM | Kho chỉ 30 chunk. Một lượt gọi mạng tới docker còn chậm hơn. Bớt một dịch vụ có thể chết. |
| Langfuse (docker) | `Trace` tự viết, ghi JSON | Ta đã thiết kế trace là đầu ra hạng nhất từ đầu — Langfuse chỉ lặp lại việc đó. |
| LangGraph / AutoGen | Orchestrator tự viết, ~200 dòng | Đồ thị là chuỗi tuyến tính + 1 vòng lặp. Không đáng đánh cược vào breaking change của thư viện. |
| Next.js | Một file `index.html` | Không `node_modules`, không webpack hỏng lúc 2 giờ sáng. Vẫn có KaTeX và timeline tác tử. |
| ChemPy | Parser công thức + nullspace SymPy tự viết | ChemPy chưa ổn định trên Python 3.13. Tự viết mất 80 dòng và chạy chắc chắn. |
| Fine-tune embedding (A) | Giữ BM25 + dense có sẵn | Không đủ thời gian, và chưa có bằng chứng truy hồi đang là nút thắt. |
| Chưng cất Explainer (D) | — | Tham vọng nhất, rủi ro nhất. Đưa vào "hướng phát triển". |

**Giữ lại nguyên vẹn:** kiến trúc 6 tác tử, kiểm chứng 4 tầng, vòng repair, RAG,
memory pool, ablation, và **ViSTEM-PRM** (phần Học sâu).

---

## 2. Lịch

### Ngày 1 — Bộ khung chạy được ✅ *(đã xong)*

- [x] `schemas.py` — hợp đồng có kiểu giữa các tác tử
- [x] `llm.py` — một client cho Groq/OpenRouter/Together/Ollama, cache ra đĩa, chặn ngân sách
- [x] Tool layer — SymPy, Pint, Hoá học *(đã test: cân bằng `2KMnO₄ + 16HCl → …` đúng; bắt được lỗi "quên căn" bằng thứ nguyên)*
- [x] 6 tác tử + orchestrator SOP có vòng repair
- [x] FastAPI + SSE + frontend một file
- [x] Kho tri thức 30 chunk + RAG lai *(top-1 đúng 4/4 truy vấn thử, kể cả đầu vào không dấu)*

### Ngày 2 — Có số đối chứng

- [x] Bộ chấm tự động *(15/15 ca thử, xử lý được `0,4 s` ↔ `0.397`, `e − 1` ↔ `1.71828`, `1/6`)*
- [x] Baseline A0 (CoT) + A1 (self-consistency)
- [x] `run_bench.py` với 9 cấu hình ablation
- [ ] **⚠ CẦN BẠN LÀM: lấy `GROQ_API_KEY` và điền vào `.env`** — đây là thứ duy nhất đang chặn
- [ ] Chạy `--config cot` rồi `--config full` → có hai con số đầu tiên

### Ngày 3 — Phần Học sâu

- [x] Bộ sinh lời giải đúng từ template *(13 template, ~3000 bài không trùng)*
- [x] Bộ tiêm lỗi 5 loại → 38k mẫu step-level, không tốn một đồng API nào
- [ ] Huấn luyện ViSTEM-PRM *(đang chạy)*
- [ ] Cắm làm tầng T0, đo độ trễ tiết kiệm được
- [ ] *(nếu kịp)* Router classifier

### Ngày 4 — Số liệu cho báo cáo

- [ ] Chạy `--config all` → bảng ablation A0–A8
- [ ] Mở rộng dataset lên ~60–80 bài (thêm đề THPT QG thật)
- [ ] LLM-judge chấm chất lượng sư phạm
- [ ] Người chấm 20 mẫu → đối chiếu với LLM-judge
- [ ] Phân tích lỗi: PRM bắt tốt loại lỗi nào, dở loại nào

### Ngày 5 — Đóng gói

- [ ] Báo cáo
- [ ] Slide
- [ ] Video demo *(quay sẵn — đừng demo trực tiếp phụ thuộc mạng)*
- [ ] Chuẩn bị `VMA_PROFILE=local_offline` làm phương án dự phòng khi mất mạng

---

## 3. Việc bạn phải làm ngay (chặn tiến độ)

```bash
# 1. Lấy key miễn phí ở https://console.groq.com/keys
# 2. cp .env.example .env  rồi điền GROQ_API_KEY=gsk_...
# 3. Kiểm tra:
python -c "from vimultiagent.core.config import get_settings; print(get_settings().available_providers())"
# mong đợi: {'groq': True, ...}
```

Không có key thì các tác tử LLM không chạy được. Phần Học sâu (PRM) và toàn bộ
tool layer thì **không cần key** — vẫn làm được song song.

---

## 4. Rủi ro còn lại

| Rủi ro | Đối sách |
|---|---|
| Free tier Groq bị rate-limit khi chạy ablation | Cache ra đĩa đã bật sẵn; chạy `--concurrency 2`; chạy qua đêm |
| Dataset 30 bài quá nhỏ để kết luận | Nói rõ trong báo cáo là tập hạt giống; mở rộng ngày 4; báo cáo khoảng tin cậy |
| Mất mạng lúc bảo vệ | Video demo quay sẵn + profile `local_offline` |
| PRM học vẹt trên dữ liệu template | Đã chia tập theo NGUỒN; ngày 4 trộn thêm lời giải thật từ memory pool |
| Kết quả ablation không như kỳ vọng | Kết quả âm vẫn là kết quả — báo cáo trung thực còn hơn số liệu đẹp không giải thích được |
