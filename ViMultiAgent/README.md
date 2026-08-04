# ViMultiAgent

**Hệ thống đa tác tử giải bài toán học thuật STEM tiếng Việt** — Toán, Vật lý, Hoá học cấp THPT,
lời giải từng bước có tính sư phạm, kèm **tự kiểm chứng bằng tác tử độc lập**.

> Đề tài 19 · Môn Học sâu Nâng cao và Ứng dụng · CLO4

---

## Điểm khác biệt

Hệ thống **không tin lời giải của chính nó**. Một tác tử Kiểm tra dùng **model khác họ**,
không nhìn thấy lời giải cũ, phải xác nhận trước khi lời giải được diễn giải cho học sinh.
Nếu không xác nhận được, hệ thống **nói rõ điều đó** thay vì trình bày một lời giải sai
một cách tự tin.

Kiểm chứng có 4 tầng, xếp theo giá tăng dần:

| Tầng | Cơ chế | Chi phí | Sai được không? |
|---|---|---|---|
| **T0** | `ViSTEM-PRM` — model đã huấn luyện chấm từng bước | ~30 ms | có |
| **T1** | SymPy thế ngược · Pint kiểm thứ nguyên · bảo toàn nguyên tố | ~5 ms | **không bao giờ** |
| **T2** | Model khác họ giải lại độc lập | ~3 s | có |
| **T3** | Model khác họ soát tìm bước sai đầu tiên | ~3 s | có |

T1 bác bỏ thì dừng ngay — không gọi LLM để nghe lại điều đã biết chắc.

---

## Cài đặt

```bash
pip install -r requirements.txt

python scripts/build_kb.py           # kho tri thức THPT  (30 chunk)
python scripts/build_dataset.py      # tập đánh giá        (30 bài có đáp án)
```

### Cấu hình model — **bắt buộc làm bước này**

```bash
cp .env.example .env
```

Rồi điền **ít nhất một** trong các key sau vào `.env`:

| Provider | Lấy ở đâu | Ghi chú |
|---|---|---|
| **Groq** *(khuyến nghị)* | https://console.groq.com/keys | Có free tier, thông lượng cao → gánh KPI 45 s |
| OpenRouter | https://openrouter.ai/keys | Có model `:free`, dùng để đa dạng hoá Verifier |
| Together AI | https://api.together.ai | Nhiều model open-weights lớn |

**Không có key nào?** Chạy hoàn toàn cục bộ bằng Ollama:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull llama3.1:8b-instruct-q4_K_M
# rồi đặt trong .env:
#   VMA_PROFILE=local_offline
#   VMA_STRATEGY=fast
```

> Đánh đổi khi chạy Ollama trên 6 GB VRAM: ~110 s mỗi bài, **trượt KPI 45 s**.
> Dùng để demo offline và khi mất mạng, không dùng để chạy benchmark.

Kiểm tra cấu hình:

```bash
python -c "from vimultiagent.core.config import get_settings; print(get_settings().available_providers())"
```

---

## Chạy

### Giao diện web

```bash
python -m uvicorn vimultiagent.api.main:app --reload --port 8000
```

Mở http://localhost:8000 — có sẵn nút đề mẫu, timeline tác tử chạy trực tiếp,
công thức render bằng KaTeX.

### Dòng lệnh

```bash
python -c "
import asyncio
from vimultiagent.graph.orchestrator import solve_problem
r = asyncio.run(solve_problem('Một con lắc lò xo có m = 400 g, k = 100 N/m. Tính chu kỳ.'))
print(r.solution.final_answer, '|', r.verification.verdict, '| tin cậy', r.confidence)
"
```

### Benchmark & ablation

```bash
python eval/run_bench.py --list                     # xem các cấu hình
python eval/run_bench.py --config full              # hệ đầy đủ
python eval/run_bench.py --config cot               # baseline A0
python eval/run_bench.py --config all               # toàn bộ ablation -> bảng cho báo cáo
```

Kết quả ghi ra `eval/reports/`. **Mọi lượt gọi LLM đều được cache ra đĩa**, nên chạy
lại cùng một cấu hình gần như miễn phí — hãy tận dụng khi dựng bảng kết quả.

---

## Phần Học sâu — ViSTEM-PRM

Model phân loại **bước giải đúng/sai**, đóng vai trò tầng T0 của Verifier.

```bash
# 1. Sinh dữ liệu (KHÔNG cần API key — lời giải đúng sinh từ template, nhãn âm từ mutation)
python -m vimultiagent.models.prm.data_build --n 3000 --mutations-per 3

# 2. Huấn luyện  (~3 GB VRAM, vừa RTX 3060 6 GB)
python -m vimultiagent.models.prm.train --epochs 3 --batch-size 16

# 3. Bật trong configs/app.yaml -> prm.enabled: true  (mặc định đã bật)
```

Dữ liệu huấn luyện **miễn phí về mặt gán nhãn**: mutation testing vốn đã cần cho KPI
"tỉ lệ phát hiện sai ≥ 85%", và nó sinh ra nhãn âm chính xác như một sản phẩm phụ.

Năm loại lỗi được tiêm, chọn theo phân tích lỗi thực tế của học sinh THPT:
`unit` (quên quy đổi) · `sign` (sai dấu) · `formula` (nhầm công thức) ·
`arithmetic` (sai số học) · `condition` (bỏ điều kiện xác định).

---

## Cấu trúc

```
configs/          models.yaml (sổ đăng ký model) · app.yaml (chế độ chạy)
vimultiagent/
  core/           schemas.py (hợp đồng giữa tác tử) · llm.py · prompts.py · config.py
  agents/         analyzer · retriever · solver · verifier · explainer
  graph/          orchestrator.py — SOP engine, MetaGPT-inspired
  tools/          sympy · pint · hoá học · registry
  memory/         RAG lai BM25 + dense, không cần vector DB ngoài
  models/prm/     synth · mutate · data_build · train · infer   ← PHẦN HỌC SÂU
  api/            FastAPI + SSE
eval/             metrics · baselines · run_bench (8 cấu hình ablation)
frontend/         index.html — một file, không build step
docs/             thiết kế, kế hoạch huấn luyện, kế hoạch 5 ngày
```

---

## Quyết định kỹ thuật đáng chú ý

| Quyết định | Lý do |
|---|---|
| **Tự viết orchestrator**, không LangGraph/AutoGen | Đồ thị là chuỗi tuyến tính + đúng 1 vòng lặp có điều kiện. ~200 dòng, không thêm phụ thuộc, đo được từng mili-giây. |
| **Không dùng vector DB ngoài** | Kho chỉ vài trăm chunk — numpy trong RAM nhanh hơn một lượt gọi mạng tới docker, và bớt một nguồn hỏng hóc trước hạn nộp. |
| **Không `exec()` mã LLM sinh** | Tool có chữ ký cố định, tham số validate được. Mất linh hoạt, đổi lại không có lỗ hổng thực thi mã. |
| **Frontend một file, không build step** | Không `node_modules`, không webpack lỗi lúc 2 giờ sáng trước buổi bảo vệ. |
| **Cache LLM ra đĩa** | Chạy lại benchmark miễn phí. Đây là thứ quyết định có kịp dựng bảng ablation hay không. |
| **Solver ≠ Verifier về họ model** | Cùng model thì chỉ đang đo mức độ một model đồng ý với chính nó. Ràng buộc này là giả thuyết trung tâm của đề tài (ablation A3). |

---

## Ghi chú cho báo cáo

- Dùng API để phục vụ model **trọng số mở** (Qwen, Llama) vẫn thoả yêu cầu "LLM open-source" —
  trọng số tải được, tự host được. Nên nêu rõ một câu để không bị vặn.
- Tuyên bố "đầu tiên tại Việt Nam" nên hạ thành *"theo hiểu biết của chúng tôi..."* kèm
  một mục related-work có khảo sát thật. Tuyên bố tuyệt đối sẽ bị hỏi; tuyên bố có giới hạn thì không.
- Nên giữ một tập đề **held-out** (đề 2025) để phát hiện rò rỉ dữ liệu — accuracy cao
  trên đề cũ có thể là ghi nhớ từ lúc pretrain chứ không phải suy luận.
