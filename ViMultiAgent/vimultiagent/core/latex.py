"""Dọn LaTeX do LLM sinh ra trước khi đưa xuống frontend.

Hai hỏng hóc quan sát được trên màn hình thật, cả hai đều làm công thức hiện ra
nguyên văn màu đỏ thay vì được render:

1. **Escape JSON ăn mất dấu gạch chéo.** `\\t`, `\\f`, `\\b`, `\\r` đều là escape HỢP LỆ
   của JSON. Model viết `"\\times"` (một gạch) thì `json.loads` trả về ký tự TAB rồi
   `"imes"` — trên màn hình thành `n imes V`. Tương tự `\\frac` -> form feed + `rac`.
   Sửa được một cách tất định: một ký tự điều khiển nằm giữa chuỗi LaTeX thì gần như
   chắc chắn là dấu gạch chéo bị nuốt, trả nó về.

2. **Bọc dấu phân cách hai lần.** Frontend đã bọc `\\[ ... \\]` quanh trường `latex`,
   nên model bọc thêm `$...$` sẽ tạo ra `\\[$...$\\]`. KaTeX gặp `$` trong chế độ toán
   thì báo lỗi, và `throwOnError:false` khiến nó in mã nguồn ra màu đỏ.

Dọn ở tầng máy chủ chứ không chỉ nhắc trong prompt: nhắc trong prompt là mong đợi,
dọn sau khi sinh mới là bảo đảm — cùng lập luận với ràng buộc "Explainer không được
đổi đáp số" trong agents/explainer.py.
"""

from __future__ import annotations

import re

# Ký tự điều khiển -> chữ cái mà JSON đã nuốt mất dấu gạch chéo đứng trước.
_CTRL_TO_LETTER = {
    "\t": "t",   # \times, \theta, \to, \tan, \text, \frac{...}{...} qua \t...
    "\x0c": "f",  # \frac, \forall
    "\x08": "b",  # \beta, \bar, \binom
    "\r": "r",   # \rightarrow, \rho
    "\x0b": "v",  # \vec, \varphi
    "\x07": "a",  # \alpha, \approx
}

_DELIMS = (
    (r"\[", r"\]"),
    (r"\(", r"\)"),
    ("$$", "$$"),
    ("$", "$"),
)


def repair_json_escapes(s: str) -> str:
    """Trả lại dấu gạch chéo mà `json.loads` đã nuốt.

    Chỉ đụng tới ký tự điều khiển — chúng không bao giờ hợp lệ trong một biểu thức
    LaTeX, nên nếu có mặt thì chắc chắn là tai nạn escape.
    """
    for ctrl, letter in _CTRL_TO_LETTER.items():
        s = s.replace(ctrl, "\\" + letter)
    # Xuống dòng thì mơ hồ hơn: có thể model cố ý ngắt dòng. Trong một trường LaTeX
    # một dòng thì nó gần như luôn là `\n...` bị nuốt (\neq, \nu, \ne).
    s = re.sub(r"\n(?=[a-zA-Z])", r"\\n", s)
    return s


def strip_delimiters(s: str) -> str:
    """Bóc các cặp dấu phân cách mà model tự thêm. Lặp vì có bài bọc hai lớp."""
    s = s.strip()
    for _ in range(3):
        before = s
        for left, right in _DELIMS:
            if len(s) > len(left) + len(right) and s.startswith(left) and s.endswith(right):
                s = s[len(left) : -len(right)].strip()
                break
        if s == before:
            break
    return s


def clean_latex(s: str | None) -> str:
    """Dọn một trường LaTeX: sửa escape rồi bóc dấu phân cách thừa."""
    if not s:
        return ""
    return strip_delimiters(repair_json_escapes(s)).strip()


def clean_prose(s: str | None) -> str:
    """Dọn văn xuôi có thể lẫn LaTeX inline.

    KHÔNG bóc dấu phân cách ở đây — trong văn xuôi thì `$...$` là hợp lệ và frontend
    có cấu hình để render nó. Chỉ sửa phần escape bị nuốt.
    """
    if not s:
        return ""
    return repair_json_escapes(s)
