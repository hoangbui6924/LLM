"""Bộ sinh lỗi có kiểm soát (mutation testing).

Dùng cho HAI việc, và đó chính là lý do nó đáng làm sớm:
  1. Đo KPI "tỉ lệ tác tử checker phát hiện sai ≥ 85%" — tiêm lỗi đã biết rồi
     xem Verifier có bắt được không. Đây là recall đo được, không phải ước lượng.
  2. Sinh nhãn ÂM để huấn luyện ViSTEM-PRM. Nhãn hoàn toàn miễn phí vì ta biết
     chính xác mình đã làm hỏng bước nào.

Năm loại lỗi được chọn theo phân tích lỗi thực tế của học sinh THPT, không phải
chọn ngẫu nhiên:
  unit       — quên quy đổi đơn vị (lỗi số 1 của Vật lý)
  sign       — sai dấu
  formula    — dùng nhầm công thức của dạng bài khác
  arithmetic — sai số học tuy công thức đúng
  condition  — bỏ điều kiện xác định / bỏ bước loại nghiệm
"""

from __future__ import annotations

import random
import re
from typing import Any, Callable

Rng = random.Random

MUTATION_TYPES = ("unit", "sign", "formula", "arithmetic", "condition")

_NUM = re.compile(r"(?<![\w^])(\d+(?:[.,]\d+)?)(?![\w])")


def _numbers_in(s: str) -> list[re.Match[str]]:
    return list(_NUM.finditer(s))


# ---------------------------------------------------------------------------
# Các toán tử đột biến — mỗi hàm trả (bước đã hỏng, mô tả lỗi) hoặc None
# ---------------------------------------------------------------------------


def mut_arithmetic(step: str, r: Rng) -> tuple[str, str] | None:
    """Giữ nguyên công thức, làm sai kết quả tính. Loại lỗi khó phát hiện nhất
    nếu không thực sự tính lại — đúng thứ ta muốn PRM học."""
    ms = _numbers_in(step)
    if not ms:
        return None
    m = r.choice(ms)
    raw = m.group(1)
    try:
        val = float(raw.replace(",", "."))
    except ValueError:
        return None
    if val == 0:
        return None
    factor = r.choice([2, 0.5, 1.1, 0.9, 3])
    new = val * factor
    txt = f"{new:.4g}".rstrip("0").rstrip(".") if "." in f"{new:.4g}" else f"{new:.4g}"
    if "," in raw:
        txt = txt.replace(".", ",")
    return step[: m.start(1)] + txt + step[m.end(1) :], f"sai số học: {raw} → {txt}"


def mut_unit(step: str, r: Rng) -> tuple[str, str] | None:
    """Quên quy đổi: đổi hệ số 10^k hoặc xoá hẳn câu quy đổi."""
    pairs = [
        (r"(\d+(?:[.,]\d+)?)\s*g\b", "kg", 1),
        (r"(\d+(?:[.,]\d+)?)\s*cm\b", "m", 1),
        (r"(\d+(?:[.,]\d+)?)\s*mm\b", "m", 1),
        (r"(\d+(?:[.,]\d+)?)\s*nm\b", "m", 1),
    ]
    if re.search(r"[Đđ]ổi đơn vị|hệ SI", step) and r.random() < 0.6:
        return "(bỏ qua bước đổi đơn vị)", "bỏ bước quy đổi đơn vị"
    for pat, target, _ in pairs:
        m = re.search(pat, step)
        if m:
            # dùng thẳng con số của đơn vị nhỏ như thể nó đã ở đơn vị lớn
            return (
                step[: m.start()] + f"{m.group(1)} {target}" + step[m.end() :],
                f"lỗi đơn vị: dùng {m.group(0)} như {m.group(1)} {target}",
            )
    return None


def mut_sign(step: str, r: Rng) -> tuple[str, str] | None:
    if "−" in step or "-" in step:
        s = step.replace("−", "@@").replace("-", "−", 1).replace("@@", "+", 1)
        if s != step:
            return s, "sai dấu trong biến đổi"
    ms = _numbers_in(step)
    if ms:
        m = r.choice(ms)
        return step[: m.start(1)] + "−" + m.group(1) + step[m.end(1) :], "đổi dấu một đại lượng"
    return None


_FORMULA_SWAPS = [
    ("T = 2π√(m/k)", "T = 2π√(k/m)", "đảo ngược tỉ số trong công thức chu kỳ"),
    ("λ = v/f", "λ = v·f", "nhân thay vì chia khi tính bước sóng"),
    ("i = λD/a", "i = λa/D", "hoán vị D và a trong công thức khoảng vân"),
    ("v_max = Aω", "v_max = Aω²", "nhầm tốc độ cực đại với gia tốc cực đại"),
    ("Z = √(R² + (Z_L − Z_C)²)", "Z = R + Z_L − Z_C", "cộng đại số thay vì cộng vectơ"),
    ("V = n×22,4", "V = n/22,4", "chia thay vì nhân với 22,4"),
    ("n = m/M", "n = M/m", "đảo ngược công thức số mol"),
    ("pH = −log[H⁺]", "pH = log[H⁺]", "quên dấu trừ trong công thức pH"),
    ("uₙ = u₁ + (n−1)d", "uₙ = u₁ + n·d", "sai chỉ số trong cấp số cộng"),
    ("|z| = √(a² + b²)", "|z| = a + b", "cộng phần thực và phần ảo thay vì lấy căn"),
    ("(x^n)' = n·x^(n−1)", "(x^n)' = n·x^(n+1)", "sai số mũ khi lấy đạo hàm"),
]


def mut_formula(step: str, r: Rng) -> tuple[str, str] | None:
    r.shuffle(_FORMULA_SWAPS)
    for good, bad, desc in _FORMULA_SWAPS:
        if good in step:
            return step.replace(good, bad), desc
    key = re.search(r"[Cc]ông thức[^:]*:\s*(.+)", step)
    if key:
        return step[: key.start(1)] + "(công thức không phù hợp với dạng bài này)", "áp dụng sai công thức"
    return None


def mut_condition(step: str, r: Rng) -> tuple[str, str] | None:
    """Bỏ điều kiện xác định / bỏ bước kiểm tra. Lỗi này không làm sai phép tính
    nào cả — nó làm sai LỜI GIẢI. Verifier tất định không bắt được, nên đây là
    chỗ PRM và tầng T3 phải gánh."""
    for pat in (r"[Đđ]iều kiện[^.]*\.", r"[Kk]iểm tra[^.]*\.", r"[Tt]hử lại[^.]*\.",
                r"[Ll]oại nghiệm[^.]*\."):
        if re.search(pat, step):
            return re.sub(pat, "", step).strip() or "(bỏ bước kiểm tra điều kiện)", \
                   "bỏ điều kiện xác định / bước kiểm tra"
    if re.search(r"hoàn toàn|dư\b|đktc", step) and r.random() < 0.5:
        return (
            re.sub(r"ở điều kiện tiêu chuẩn|đktc", "", step).strip(),
            "bỏ qua điều kiện tiêu chuẩn của bài toán",
        )
    return None


MUTATORS: dict[str, Callable[[str, Rng], tuple[str, str] | None]] = {
    "arithmetic": mut_arithmetic,
    "unit": mut_unit,
    "sign": mut_sign,
    "formula": mut_formula,
    "condition": mut_condition,
}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def mutate_solution(
    steps: list[str], rng: Rng, mutation_type: str | None = None
) -> dict[str, Any] | None:
    """Tiêm MỘT lỗi vào MỘT bước.

    Chỉ một lỗi, có chủ đích: bài toán của PRM là tìm bước sai ĐẦU TIÊN. Tiêm nhiều
    lỗi làm nhãn mơ hồ và bài toán học được biến thành bài toán khác.
    """
    if not steps:
        return None
    order = [mutation_type] if mutation_type else list(MUTATION_TYPES)
    rng.shuffle(order)

    # Không tiêm vào bước 1 (thường chỉ là phát biểu công thức) trừ khi lời giải quá ngắn
    candidates = list(range(1, len(steps))) if len(steps) > 2 else list(range(len(steps)))
    rng.shuffle(candidates)

    for mt in order:
        fn = MUTATORS[mt]
        for idx in candidates:
            out = fn(steps[idx], rng)
            if out is None:
                continue
            corrupted, desc = out
            if corrupted.strip() == steps[idx].strip():
                continue
            new_steps = list(steps)
            new_steps[idx] = corrupted
            return {
                "steps": new_steps,
                "error_step": idx,          # 0-indexed
                "mutation_type": mt,
                "description": desc,
                "original_step": steps[idx],
            }
    return None


def mutate_many(
    steps: list[str], rng: Rng, k: int = 2
) -> list[dict[str, Any]]:
    """Sinh tối đa k biến thể hỏng KHÁC LOẠI từ cùng một lời giải."""
    out: list[dict[str, Any]] = []
    types = list(MUTATION_TYPES)
    rng.shuffle(types)
    for mt in types:
        if len(out) >= k:
            break
        m = mutate_solution(steps, rng, mutation_type=mt)
        if m:
            out.append(m)
    return out
