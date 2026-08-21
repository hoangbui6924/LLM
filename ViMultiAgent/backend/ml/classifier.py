"""Bộ phân loại DẠNG BÀI Toán bằng PhoBERT — dùng lúc chạy thật.

Hệ thống chỉ làm Toán THPT nên mô hình không còn phân loại môn nữa; nó nhận dạng
bài (đạo hàm, tích phân, thể tích toạ độ...) và `agents/router.py` quy dạng đó về
phân môn Đại số hay Hình học.


Thiết kế theo ba nguyên tắc:

1. **Nạp lười.** Mô hình chỉ tải vào RAM ở lần gọi đầu. Backend khởi động vẫn
   nhanh, và ai không huấn luyện PhoBERT thì hệ thống vẫn chạy bình thường.
2. **Không có mô hình thì im lặng nhường chỗ.** `available()` trả False, Router
   tự lùi về luật từ khoá. Không văng lỗi, không chặn cả hệ thống.
3. **Chạy CPU.** ~30 ms mỗi câu, không tranh 6 GB VRAM với Ollama. Router gọi
   một lần mỗi câu hỏi nên 30 ms là không đáng kể trong ngân sách 45 giây —
   trong khi hỏi LLM tốn 2-4 giây.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

MODEL_DIR = Path(__file__).resolve().parent / "phobert_router"

_khoa = threading.Lock()
_da_nap = False
_tok: Any = None
_model: Any = None
# Chỉ là bản dự phòng khi `labels.json` thiếu. Danh sách THẬT luôn đọc từ file đó
# lúc nạp mô hình, để nhãn không bao giờ lệch với trọng số đã huấn luyện.
_nhan: list[str] = [
    "dao_ham", "tich_phan", "gioi_han", "phuong_trinh", "tiep_tuyen",
    "gtln", "gtnn", "so_diem_cuc_tri", "tiem_can_ngang", "tiem_can_dung",
    "khac_dai_so",
    "toa_do_khoang_cach", "toa_do_the_tich", "toa_do_kc_diem_mp", "khac_hinh_hoc",
]


def available() -> bool:
    """Có mô hình đã huấn luyện trên đĩa hay không."""
    return (MODEL_DIR / "config.json").exists()


def _nap() -> bool:
    global _da_nap, _tok, _model, _nhan
    if _da_nap:
        return _model is not None
    with _khoa:
        if _da_nap:
            return _model is not None
        _da_nap = True
        if not available():
            return False
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            _tok = AutoTokenizer.from_pretrained(MODEL_DIR)
            _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
            _model.eval()
            torch.set_num_threads(max(1, (torch.get_num_threads() or 4) // 2))

            nhan_file = MODEL_DIR / "labels.json"
            if nhan_file.exists():
                _nhan = json.loads(nhan_file.read_text(encoding="utf-8"))["labels"]
        except Exception:  # noqa: BLE001 — thiếu thư viện thì lùi về luật, không chết
            _model = None
            return False
    return _model is not None


def du_doan(cau_hoi: str) -> tuple[str, float] | None:
    """Trả (môn, độ tin cậy) hoặc None nếu không dùng được mô hình.

    Độ tin cậy là xác suất softmax của lớp thắng. Router dùng nó để quyết định
    có cần hỏi thêm LLM hay không — dưới ngưỡng thì bài này thuộc vùng mà mô
    hình không chắc, đúng lúc nên tiêu token cho LLM.
    """
    if not cau_hoi.strip() or not _nap():
        return None
    try:
        import torch

        from ml.segment import tach_tu

        lo = _tok(
            tach_tu(cau_hoi),
            truncation=True,
            padding=True,
            max_length=96,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = _model(**lo).logits[0]
            xac_suat = torch.softmax(logits, dim=-1)
            i = int(xac_suat.argmax())
        return _nhan[i], float(xac_suat[i])
    except Exception:  # noqa: BLE001
        return None
