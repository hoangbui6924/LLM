"""Suy luận ViSTEM-PRM — tầng T0 của Verifier.

Một forward pass ~20-40 ms thay cho một lượt gọi LLM ~2-4 giây. Nhưng lợi ích thật
không nằm ở tốc độ mà ở CHỖ ĐẶT NGƯỠNG: PRM chỉ được phép bác bỏ khi nó rất chắc.

Lý do bất đối xứng: chi phí của hai loại sai KHÔNG bằng nhau.
  - Báo oan một lời giải đúng -> tốn thêm một vòng repair (mất vài giây, ít tiền)
  - Bỏ sót một lời giải sai   -> học sinh học sai kiến thức

Nghe thì nên hạ ngưỡng để bắt nhiều hơn. Nhưng T2/T3 phía sau vẫn còn cơ hội bắt,
nên vai trò đúng của T0 là LỌC NHANH những trường hợp rõ ràng, không phải phán quyết
cuối. Ngưỡng thực tế nằm ở `configs/app.yaml -> prm.reject_threshold` (hiện 0.55,
chọn bằng quét trên tập validation — xem eval/reports/prm_threshold_sweep.json).

CẢNH BÁO — ĐỌC TRƯỚC KHI CHUYỂN SANG `blocking`:
Toàn bộ số đo đẹp của PRM (F1 bước 0,952 · recall lời giải 91,3 %) đều đo TRONG
phân phối template. Trên lời giải THẬT của Solver, `eval/run_prm_diag.py` cho thấy
thứ tự điểm số không còn giữ được — xem eval/reports/prm_diag_real.json. Hai nguyên
nhân đã xác định:

  1. 32 % đầu vào thật vượt 256 token. PhoBERT chặn cứng ở 258 vị trí, mà bước ĐANG
     ĐƯỢC CHẤM nằm ở CUỐI chuỗi (`build_input`) và `truncation_side='right'` —
     nên với gần một phần ba số bước, model bị hỏi "bước này đúng không" trong khi
     chính bước đó đã bị cắt khỏi đầu vào. Đổi sang cắt trái KHÔNG cứu được (đo rồi:
     báo oan tăng từ 4/7 lên 5/7) vì model được huấn luyện dưới chế độ cắt phải.
     Phải sửa ở `build_input` rồi huấn luyện lại.
  2. Điểm số bị chi phối bởi CÁCH DIỄN ĐẠT: ba lời giải đúng của cùng một bài cho
     0,065 / 0,629 / 0,878 — biên độ trải gần hết thang đo.

Vì thế mặc định là `advisory`, và tầng này chưa được tính là một tầng kiểm chứng
hoạt động được.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...core.config import get_settings
from ...core.schemas import Solution, VerdictItem
from .data_build import build_input, step_text

ROOT = Path(__file__).resolve().parents[3]


class PRM:
    def __init__(self, checkpoint: str | Path, device: str = "cuda", max_length: int = 256) -> None:
        import torch  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        self.torch = torch
        self.device = device if torch.cuda.is_available() and device == "cuda" else "cpu"
        self.max_length = max_length
        self.tok = AutoTokenizer.from_pretrained(str(checkpoint))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint))
        self.model.to(self.device).eval()

        # Định dạng đầu vào phải khớp CHÍNH XÁC cái mà checkpoint này đã học. Suy ra
        # từ metadata chứ không mặc định theo hằng số hiện hành: đổi INPUT_FORMAT rồi
        # dùng lại checkpoint cũ sẽ cho ra điểm số vô nghĩa mà không báo lỗi gì.
        meta_f = Path(checkpoint) / "training_meta.json"
        self.input_format = "v1"
        if meta_f.exists():
            try:
                import json  # noqa: PLC0415

                self.input_format = json.loads(meta_f.read_text(encoding="utf-8")).get(
                    "input_format", "v1"
                )
            except Exception:  # noqa: BLE001
                pass

    def score_steps(self, problem: str, steps: list[str]) -> list[float]:
        """Trả xác suất ĐÚNG cho từng bước.

        Chấm cả lời giải trong MỘT batch — nếu chấm từng bước một thì lợi thế tốc độ
        so với LLM mất sạch.
        """
        if not steps:
            return []
        texts = [
            build_input(problem, steps, i, fmt=self.input_format) for i in range(len(steps))
        ]
        enc = self.tok(
            texts, truncation=True, max_length=self.max_length,
            padding=True, return_tensors="pt",
        ).to(self.device)
        with self.torch.no_grad():
            logits = self.model(**enc).logits
        return self.torch.softmax(logits.float(), dim=-1)[:, 1].cpu().tolist()

    # Giữ tên cũ làm bí danh: `step_text` trong data_build là nguồn sự thật duy nhất,
    # dùng chung cho cả dựng dữ liệu huấn luyện, ghi memory pool và suy luận.
    _step_text = staticmethod(step_text)

    def score_solution(self, problem: str, sol: Solution) -> list[VerdictItem]:
        """Chấm một Solution, trả về các VerdictItem cho Verifier."""
        steps = [step_text(s) for s in sol.steps]
        if not steps:
            return []

        probs = self.score_steps(problem, steps)
        cfg = get_settings().prm
        thr = float(cfg.get("reject_threshold", 0.15))

        items: list[VerdictItem] = []
        for s, p in zip(sol.steps, probs):
            if p < thr:
                items.append(
                    VerdictItem(
                        step_id=s.id, check_type="prm", passed=False,
                        detail_vi=f"ViSTEM-PRM đánh giá bước này nhiều khả năng sai "
                                  f"(P(đúng) = {p:.2f} < {thr}).",
                        score=p,
                    )
                )
                break  # chỉ báo bước sai ĐẦU TIÊN — các bước sau sai theo là đương nhiên

        if not items:
            items.append(
                VerdictItem(
                    check_type="prm", passed=True,
                    detail_vi=f"ViSTEM-PRM không thấy bước nào đáng ngờ "
                              f"(P(đúng) thấp nhất = {min(probs):.2f}).",
                    score=float(min(probs)),
                )
            )
        return items


_PRM: PRM | None = None
_TRIED = False


def get_prm() -> PRM | None:
    """Nạp lười, chỉ một lần. Chưa huấn luyện thì trả None và Verifier bỏ qua T0 —
    hệ thống phải chạy được trước khi có model, nếu không thì không bao giờ thu thập
    được dữ liệu để huấn luyện nó."""
    global _PRM, _TRIED
    if _TRIED:
        return _PRM
    _TRIED = True

    cfg = get_settings().prm
    if not cfg.get("enabled", True):
        return None
    ckpt = ROOT / cfg.get("checkpoint", "checkpoints/prm")
    if not (ckpt / "config.json").exists():
        print(f"[PRM] Chưa có checkpoint tại {ckpt} — bỏ qua tầng T0. "
              f"Huấn luyện: python -m vimultiagent.models.prm.train")
        return None
    try:
        _PRM = PRM(ckpt, device=cfg.get("device", "cuda"),
                   max_length=int(cfg.get("max_length", 256)))
        print(f"[PRM] Đã nạp {ckpt} trên {_PRM.device}")
    except Exception as e:  # noqa: BLE001
        print(f"[PRM] Nạp lỗi ({type(e).__name__}: {e}) — bỏ qua tầng T0.")
        _PRM = None
    return _PRM
