"""Tăng cường dữ liệu GIỮ NGUYÊN NGHĨA — chống phụ thuộc bề mặt câu chữ.

Không gọi LLM nào, không tốn tiền, chạy trong vài giây.

VÌ SAO CẦN: `eval/run_prm_diag.py` đo được ba lời giải ĐÚNG của **cùng một bài** cho
P(đúng) = 0,065 / 0,629 / 0,878 — trải gần hết thang đo. Điểm số của PRM đang phản ánh
CÁCH DIỄN ĐẠT chứ không phản ánh đúng/sai. Nguyên nhân: model chỉ từng thấy văn bản
sinh từ 13 template, đều tăm tắp; lời giải thật thì có LaTeX, độ dài bước không đều,
từ ngữ tự do.

Cách chữa đúng bài toán này là dạy model rằng **cùng một nội dung viết theo nhiều kiểu
vẫn là cùng một nhãn**. Đó chính là định nghĩa của tăng cường giữ nguyên nghĩa.

RÀNG BUỘC BẤT BIẾN của mọi phép biến đổi ở đây: **không được đổi tính đúng/sai của
bước**. Nhãn được giữ nguyên sau khi biến đổi, nên một phép làm hỏng con số sẽ lặng lẽ
tạo ra mẫu dương sai — tệ hơn là không tăng cường gì. Vì thế mọi phép ở đây chỉ đụng
tới trình bày: cách viết công thức, từ đồng nghĩa, định dạng số. Việc làm hỏng nội dung
là của `mutate.py`, và nó nằm ở đường hoàn toàn tách biệt.

Thứ tự trong đường ống: synth/harvest -> **augment** -> mutate -> data_build.
Tăng cường TRƯỚC khi tiêm lỗi, để nhãn âm cũng có đủ kiểu diễn đạt.
"""

from __future__ import annotations

import random
import re
from typing import Any, Callable

Rng = random.Random

# --- Từ đồng nghĩa mở đầu bước, theo lối viết của SGK và của học sinh --------
_SYNONYMS: list[tuple[str, list[str]]] = [
    (r"\bTính\b", ["Ta tính", "Xác định", "Tìm", "Cần tính"]),
    (r"\bTa có\b", ["Suy ra", "Từ đó có", "Ta được"]),
    (r"\bÁp dụng công thức\b", ["Dùng công thức", "Theo công thức", "Sử dụng công thức"]),
    (r"\bSuy ra\b", ["Do đó", "Vì vậy", "Từ đó"]),
    (r"\bVậy\b", ["Kết luận", "Do đó", "Như vậy"]),
    (r"\bTheo đề bài\b", ["Đề cho", "Từ giả thiết", "Theo giả thiết"]),
    (r"\bthu được\b", ["nhận được", "ta được", "cho ra"]),
    (r"\bsố mol\b", ["số mol", "lượng chất (mol)"]),
]

# --- Số: cùng một giá trị, nhiều cách viết ----------------------------------
_NUM = re.compile(r"(?<![\w^{])(\d+)[.,](\d+)(?![\w}])")
_INT = re.compile(r"(?<![\w^{.,])(\d+)(?![\w}.,])")


def _swap_decimal_mark(s: str, r: Rng) -> str:
    """Dấu thập phân: `0,1` <-> `0.1`. Lời giải thật lẫn lộn cả hai kiểu."""
    if r.random() < 0.5:
        return _NUM.sub(lambda m: f"{m.group(1)}.{m.group(2)}", s)
    return _NUM.sub(lambda m: f"{m.group(1)},{m.group(2)}", s)


def _pad_decimal(s: str, r: Rng) -> str:
    """`0,1` -> `0,10`. Giá trị không đổi, bề mặt đổi."""
    def rep(m: re.Match[str]) -> str:
        frac = m.group(2)
        if len(frac) < 3 and r.random() < 0.4:
            return f"{m.group(1)},{frac}0"
        return m.group(0)
    return _NUM.sub(rep, s)


# --- LaTeX: cùng một biểu thức, viết trơn hoặc viết công thức ---------------
_FRAC = re.compile(r"(?<![\w}])(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)(?![\w{])")

# Một lệnh LaTeX kèm TRỌN các nhóm ngoặc của nó: `\frac{5,6}{56}`, `\sqrt{2}`, `\times`.
# Ranh giới là dấu ngoặc, không phải dấu câu — nên nó không bao giờ cắt ngang một số.
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+(?:\{[^{}]*\})*")


def _latexify(s: str, r: Rng) -> str:
    """Đưa biểu thức về dạng LaTeX như Solver thật hay viết.

    Đây là phép quan trọng nhất trong file: lời giải template gần như không có LaTeX,
    lời giải thật thì đầy. Khoảng cách đó là một phần lớn của lệch phân phối.
    """
    out = s
    if r.random() < 0.7:
        out = _FRAC.sub(lambda m: rf"\frac{{{m.group(1)}}}{{{m.group(2)}}}", out)
    if r.random() < 0.6:
        out = re.sub(r"\s*[x×*]\s*(?=\d|\\)", r" \\times ", out)
    if r.random() < 0.4:
        out = re.sub(r"\^(\d)(?![\d}])", r"^{\1}", out)
    if r.random() < 0.3:
        out = re.sub(r"\bcan bac hai\b|\bcăn bậc hai của\b", r"\\sqrt", out)
    # Bọc `$...$` như Solver thật hay làm — nhưng chỉ khi đã có lệnh LaTeX,
    # bọc một chuỗi trơn thì không giống lời giải thật.
    #
    # Chỉ bọc TRỌN một lệnh LaTeX kèm các nhóm ngoặc của nó. Bản trước dùng regex
    # "ăn tới ký tự phân cách gần nhất", và nó khớp `\frac{5` rồi bọc thành `$\frac{5$` —
    # cắt đôi số 5.6 thành 5 và 6. Đúng kiểu hỏng mà tăng cường tuyệt đối không được
    # phạm: giá trị số đổi trong khi nhãn giữ nguyên. Test bắt được, không phải review.
    if "\\" in out and r.random() < 0.5 and "$" not in out:
        m = _LATEX_CMD.search(out)
        if m:
            out = out[: m.start()] + f"${m.group(0)}$" + out[m.end() :]
    return out


def _rephrase(s: str, r: Rng) -> str:
    out = s
    for pat, opts in _SYNONYMS:
        if r.random() < 0.45:
            out = re.sub(pat, r.choice(opts), out, count=1)
    return out


def _vary_spacing(s: str, r: Rng) -> str:
    """Khoảng trắng quanh dấu bằng — lời giải thật không nhất quán."""
    if r.random() < 0.3:
        return re.sub(r"\s*=\s*", "=", s)
    if r.random() < 0.3:
        return re.sub(r"\s*=\s*", " = ", s)
    return s


# ĐÃ BỎ: phép cắt mệnh đề cuối câu.
# Nó không làm bước SAI, nhưng nó xoá mất kết quả tính ("Suy ra T = 0,397 s") — đúng
# thứ mà PRM phải chấm. Dạy model chấp nhận một bước không có kết quả là làm nó yếu đi
# ở chính việc nó tồn tại để làm. Bỏ hẳn cho phép giữ một BẤT BIẾN chặt và kiểm được:
# tập giá trị số phải giống hệt trước và sau khi tăng cường. Một bất biến kiểm được
# đáng giá hơn một trục biến thiên nữa.

_OPS: list[Callable[[str, Rng], str]] = [
    _latexify, _rephrase, _swap_decimal_mark, _pad_decimal, _vary_spacing,
]


def augment_step(step: str, r: Rng) -> str:
    """Một biến thể giữ nguyên nghĩa của một bước."""
    out = step
    ops = _OPS[:]
    r.shuffle(ops)
    for op in ops:
        out = op(out, r)
    return out.strip()


def augment_steps(steps: list[str], r: Rng) -> list[str]:
    return [augment_step(s, r) for s in steps]


def augment_items(
    items: list[dict[str, Any]], r: Rng, n_variants: int = 1
) -> list[dict[str, Any]]:
    """Nhân mỗi lời giải thành `n_variants` biến thể.

    Biến thể GIỮ NGUYÊN `id` của bản gốc. Điều này bắt buộc: `train.py` chia tập theo
    NGUỒN, nên biến thể của cùng một lời giải phải nằm cùng một phía. Đặt id khác nhau
    sẽ khiến bản gốc rơi vào train còn biến thể rơi vào val — rò rỉ, và điểm val đẹp giả.
    """
    if n_variants <= 0:
        return []
    out: list[dict[str, Any]] = []
    for it in items:
        for _ in range(n_variants):
            v = dict(it)
            v["steps"] = augment_steps(it["steps"], r)
            v["augmented"] = True
            out.append(v)
    return out
