"""Tăng cường phải GIỮ NGUYÊN NGHĨA — nếu không thì nó tạo mẫu dương sai.

Đây là ràng buộc sống còn của augment.py: nhãn được giữ nguyên sau khi biến đổi, nên
một phép làm lệch giá trị số sẽ lặng lẽ dạy PRM rằng một bước sai là đúng. Tệ hơn là
không tăng cường gì cả, và không có gì báo lỗi.
"""

from __future__ import annotations

import random
import re

from vimultiagent.models.prm.augment import augment_items, augment_step, augment_steps

# Bắt cả `0,1` `0.1` `56` và cả trong `\frac{5,6}{56}`
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _values(s: str) -> list[float]:
    """Tập giá trị số, chuẩn hoá dấu thập phân và số 0 đuôi."""
    out = []
    for m in _NUM.finditer(s):
        try:
            out.append(float(m.group(0).replace(",", ".")))
        except ValueError:
            pass
    return sorted(out)


SAMPLES = [
    "Tính số mol Fe: n = 5,6/56 = 0,1 mol. Ta có khối lượng mol Fe = 56 g/mol.",
    "Áp dụng công thức T = 2*pi*căn bậc hai của m/k. Suy ra T = 0,397 s.",
    "Theo đề bài m = 400 g = 0,4 kg. Vậy k = 100 N/m.",
    "Tính thể tích khí: V = 0,1 x 22,4 = 2,24 lít. Ta có điều kiện tiêu chuẩn.",
    "Ta có nghiệm x = 3 và x = -1. Loại x = -1 vì điều kiện x > 0.",
]


def test_giá_trị_số_không_bao_giờ_đổi() -> None:
    """Ràng buộc số một. Nếu test này hỏng thì dữ liệu huấn luyện bị nhiễm."""
    r = random.Random(0)
    for src in SAMPLES:
        want = _values(src)
        for _ in range(40):
            got = _values(augment_step(src, r))
            assert got == want, f"lệch giá trị:\n  gốc: {src}\n  biến thể: {got} != {want}"


def test_không_làm_bước_thành_rỗng_hoặc_cụt() -> None:
    r = random.Random(1)
    for src in SAMPLES:
        for _ in range(40):
            out = augment_step(src, r)
            assert len(out.strip()) >= 20, f"bước bị cắt quá ngắn: {out!r}"


def test_có_sinh_ra_khác_biệt_thật() -> None:
    """Tăng cường mà luôn trả về y nguyên thì vô dụng — nó phải thực sự đa dạng hoá."""
    r = random.Random(2)
    src = SAMPLES[0]
    variants = {augment_step(src, r) for _ in range(30)}
    assert len(variants) >= 5, f"chỉ sinh được {len(variants)} biến thể khác nhau"


def test_có_sinh_được_dạng_latex() -> None:
    """Khoảng cách lớn nhất giữa template và lời giải thật chính là LaTeX."""
    r = random.Random(3)
    outs = [augment_step("Tính n = 5,6/56 = 0,1 mol theo công thức n = m/M.", r)
            for _ in range(40)]
    assert any("\\frac" in o for o in outs), "không sinh được dạng \\frac lần nào"


def test_biến_thể_giữ_nguyên_id_để_không_rò_rỉ() -> None:
    """train.py chia tập theo NGUỒN. Biến thể mang id khác sẽ khiến bản gốc rơi vào
    train còn biến thể rơi vào val — rò rỉ, và điểm val đẹp giả."""
    r = random.Random(4)
    items = [{"id": "s001", "problem": "Đề", "steps": SAMPLES[:2],
              "domain": "chemistry", "subtopic": "x"}]
    out = augment_items(items, r, n_variants=3)
    assert len(out) == 3
    assert {v["id"] for v in out} == {"s001"}
    assert all(v["augmented"] for v in out)


def test_không_làm_hỏng_bản_gốc() -> None:
    r = random.Random(5)
    items = [{"id": "s1", "problem": "Đề", "steps": ["Tính n = 0,1 mol từ m = 5,6 g."],
              "domain": "math", "subtopic": "y"}]
    before = list(items[0]["steps"])
    augment_items(items, r, n_variants=2)
    assert items[0]["steps"] == before


def test_augment_steps_giữ_số_bước() -> None:
    r = random.Random(6)
    assert len(augment_steps(SAMPLES, r)) == len(SAMPLES)


def test_tắt_được() -> None:
    assert augment_items([{"id": "a", "steps": ["x"]}], random.Random(0), 0) == []
