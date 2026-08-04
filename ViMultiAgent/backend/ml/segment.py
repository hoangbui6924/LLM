"""Tách từ tiếng Việt cho PhoBERT.

PhoBERT được huấn luyện trên văn bản ĐÃ tách từ theo kiểu `vận_tốc`, `phương_trình`.
Đưa văn bản thô vào là dùng sai mô hình: những từ ghép hai âm tiết bị cắt thành
hai token rời, khác hẳn phân bố lúc pre-train, và độ chính xác tụt.

Đây là chi tiết dễ bỏ sót nhất khi dùng PhoBERT. Bắt buộc dùng CÙNG một hàm tách
cho cả lúc huấn luyện lẫn lúc suy luận — lệch nhau là hỏng âm thầm, không báo lỗi.

`underthesea.word_tokenize(..., format="text")` trả về chuỗi đã nối bằng gạch dưới.
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _tokenizer():
    from underthesea import word_tokenize

    return word_tokenize


@lru_cache(maxsize=4096)
def tach_tu(cau: str) -> str:
    """Tách từ một câu. Có cache vì Router gọi lại nhiều lần cho cùng câu hỏi."""
    if not cau or not cau.strip():
        return ""
    try:
        return _tokenizer()(cau.strip(), format="text")
    except Exception:  # noqa: BLE001 — tách từ hỏng thì dùng văn bản thô còn hơn chết
        return cau.strip()


def tach_nhieu(cac_cau: list[str]) -> list[str]:
    return [tach_tu(c) for c in cac_cau]
