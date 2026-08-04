"""Sinh lời giải ĐÚNG một cách tất định, từ template có tham số.

Vì sao cần: PRM cần hàng nghìn lời giải đúng để làm mẫu dương. Lấy từ hệ thống thật
thì phải chờ có API key, chờ chạy xong, và mỗi mẫu tốn tiền. Ở đây ta sinh chúng bằng
công thức — đúng theo định nghĩa, miễn phí, và có ngay.

Đây KHÔNG phải mẹo lách: các bước sinh ra có cùng cấu trúc và cùng loại lỗi tiềm ẩn
với lời giải thật. Dữ liệu thật (lời giải đã PASS verifier) được trộn thêm vào sau,
và tỉ lệ trộn là một tham số của thí nghiệm.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable

Rng = random.Random


def _f(x: float, nd: int = 4) -> str:
    """Định dạng số theo kiểu Việt Nam (dấu phẩy thập phân), bỏ số 0 thừa."""
    s = f"{x:.{nd}g}"
    if "e" in s or "E" in s:
        return s
    return s.rstrip("0").rstrip(".") if "." in s else s


# ---------------------------------------------------------------------------
# VẬT LÝ
# ---------------------------------------------------------------------------


def t_con_lac_lo_xo(r: Rng) -> dict[str, Any]:
    m_g = r.randrange(50, 1010, 10)
    k = r.randrange(10, 305, 5)
    m = m_g / 1000
    T = 2 * math.pi * math.sqrt(m / k)
    return dict(
        domain="physics", subtopic="con_lac_lo_xo",
        problem=f"Một con lắc lò xo gồm vật nhỏ khối lượng {m_g} g và lò xo có độ cứng "
                f"{k} N/m dao động điều hòa. Tính chu kỳ dao động.",
        steps=[
            f"Đổi đơn vị về hệ SI: m = {m_g} g = {_f(m)} kg.",
            f"Áp dụng công thức chu kỳ con lắc lò xo: T = 2π√(m/k).",
            f"Thay số: T = 2π√({_f(m)}/{k}) = 2π×{_f(math.sqrt(m/k))} s.",
            f"Kiểm tra thứ nguyên: √(kg/(N/m)) = √(kg·m/N) = s, đúng đơn vị của chu kỳ.",
            f"Vậy chu kỳ dao động là T = {_f(T)} s.",
        ],
        answer=f"{_f(T)} s", answer_value=T, unit="s",
    )


def t_song_co(r: Rng) -> dict[str, Any]:
    v = r.randrange(300, 361, 1)
    f = r.randrange(100, 1501, 10)
    lam = v / f
    return dict(
        domain="physics", subtopic="song_co",
        problem=f"Một sóng âm truyền trong không khí với tốc độ {v} m/s và tần số {f} Hz. "
                f"Tính bước sóng.",
        steps=[
            f"Công thức liên hệ: v = λf, suy ra λ = v/f.",
            f"Thay số: λ = {v}/{f} = {_f(lam)} m.",
            f"Kiểm tra điều kiện: bước sóng dương và nhỏ hơn quãng đường sóng đi trong 1 s, hợp lý.",
            f"Vậy bước sóng là λ = {_f(lam)} m.",
        ],
        answer=f"{_f(lam)} m", answer_value=lam, unit="m",
    )


def t_khe_young(r: Rng) -> dict[str, Any]:
    a_mm = round(r.uniform(0.3, 2.5), 1)
    D = round(r.uniform(0.8, 3.5), 1)
    lam_nm = r.randrange(400, 761, 10)
    a, lam = a_mm * 1e-3, lam_nm * 1e-9
    i = lam * D / a
    return dict(
        domain="physics", subtopic="song_anh_sang",
        problem=f"Trong thí nghiệm Young, hai khe cách nhau {_f(a_mm)} mm, màn cách hai khe "
                f"{_f(D)} m, ánh sáng có bước sóng {lam_nm} nm. Tính khoảng vân.",
        steps=[
            f"Đổi đơn vị: a = {_f(a_mm)} mm = {a:.1e} m; λ = {lam_nm} nm = {lam:.1e} m.",
            f"Công thức khoảng vân: i = λD/a.",
            f"Thay số: i = {lam:.1e}×{_f(D)}/{a:.1e} = {_f(i)} m.",
            f"Vậy khoảng vân là i = {_f(i * 1000)} mm.",
        ],
        answer=f"{_f(i * 1000)} mm", answer_value=i * 1000, unit="mm",
    )


def t_van_toc_cuc_dai(r: Rng) -> dict[str, Any]:
    A_cm = r.randrange(1, 21)
    w = r.choice([r.randrange(2, 31), round(r.randrange(2, 11) * math.pi, 4)])
    A = A_cm / 100
    v = A * w
    return dict(
        domain="physics", subtopic="dao_dong_dieu_hoa",
        problem=f"Một vật dao động điều hòa với biên độ {A_cm} cm và tần số góc "
                f"{_f(w)} rad/s. Tính tốc độ cực đại.",
        steps=[
            f"Đổi đơn vị: A = {A_cm} cm = {_f(A)} m.",
            f"Tốc độ cực đại trong dao động điều hòa: v_max = Aω.",
            f"Thay số: v_max = {_f(A)}×{_f(w)} = {_f(v)} m/s.",
            f"Vậy tốc độ cực đại là {_f(v)} m/s.",
        ],
        answer=f"{_f(v)} m/s", answer_value=v, unit="m/s",
    )


def t_tong_tro(r: Rng) -> dict[str, Any]:
    R = r.randrange(10, 151, 5)
    ZL = r.randrange(10, 201, 5)
    ZC = r.randrange(10, 201, 5)
    Z = math.sqrt(R ** 2 + (ZL - ZC) ** 2)
    return dict(
        domain="physics", subtopic="dien_xoay_chieu",
        problem=f"Mạch RLC nối tiếp có R = {R} Ω, cảm kháng Z_L = {ZL} Ω, "
                f"dung kháng Z_C = {ZC} Ω. Tính tổng trở của mạch.",
        steps=[
            f"Công thức tổng trở mạch RLC nối tiếp: Z = √(R² + (Z_L − Z_C)²).",
            f"Tính hiệu kháng: Z_L − Z_C = {ZL} − {ZC} = {ZL - ZC} Ω.",
            f"Thay số: Z = √({R}² + ({ZL - ZC})²) = √{R ** 2 + (ZL - ZC) ** 2} = {_f(Z)} Ω.",
            f"Kiểm tra điều kiện: Z ≥ R = {R} Ω, thoả mãn vì tổng trở luôn không nhỏ hơn điện trở thuần.",
            f"Vậy tổng trở là Z = {_f(Z)} Ω.",
        ],
        answer=f"{_f(Z)} Ω", answer_value=Z, unit="ohm",
    )


def t_phong_xa(r: Rng) -> dict[str, Any]:
    T = r.randrange(2, 41)
    n = r.randrange(1, 7)
    t = T * n
    frac = 100 / (2 ** n)
    return dict(
        domain="physics", subtopic="hat_nhan",
        problem=f"Một chất phóng xạ có chu kỳ bán rã {T} ngày. Sau {t} ngày, phần trăm "
                f"số hạt nhân còn lại so với ban đầu là bao nhiêu?",
        steps=[
            f"Định luật phóng xạ: N = N₀·2^(−t/T).",
            f"Tính số chu kỳ bán rã đã trôi qua: t/T = {t}/{T} = {n}.",
            f"Tỉ lệ còn lại: N/N₀ = 2^(−{n}) = 1/{2 ** n} = {_f(frac)}%.",
            f"Vậy còn lại {_f(frac)}% số hạt nhân ban đầu.",
        ],
        answer=f"{_f(frac)}%", answer_value=frac, unit="%",
    )


# ---------------------------------------------------------------------------
# TOÁN
# ---------------------------------------------------------------------------


def t_tich_phan(r: Rng) -> dict[str, Any]:
    n = r.choice([1, 2, 3, 4])
    b = r.randrange(1, 11)
    c = r.randrange(0, 8)
    val = b ** (n + 1) / (n + 1) + c * b ** 2 / 2
    return dict(
        domain="math", subtopic="tich_phan",
        problem=f"Tính tích phân I = ∫ từ 0 đến {b} của (x^{n} + {c}x) dx.",
        steps=[
            f"Tìm nguyên hàm: F(x) = x^{n + 1}/{n + 1} + {c}x²/2.",
            f"Áp dụng công thức Newton–Leibniz: I = F({b}) − F(0).",
            f"Tính F({b}) = {b}^{n + 1}/{n + 1} + {c}×{b}²/2 = {_f(val)}.",
            f"Vì F(0) = 0 nên I = {_f(val)}.",
        ],
        answer=f"{_f(val)}", answer_value=val, unit=None,
    )


def t_dao_ham(r: Rng) -> dict[str, Any]:
    a = r.randrange(1, 8)
    b = r.randrange(1, 10)
    x0 = r.randrange(1, 7)
    val = 3 * a * x0 ** 2 + 2 * b * x0
    return dict(
        domain="math", subtopic="dao_ham",
        problem=f"Cho hàm số y = {a}x³ + {b}x². Tính đạo hàm của hàm số tại điểm x = {x0}.",
        steps=[
            f"Áp dụng công thức (x^n)' = n·x^(n−1): y' = {3 * a}x² + {2 * b}x.",
            f"Thay x = {x0}: y'({x0}) = {3 * a}×{x0}² + {2 * b}×{x0}.",
            f"Tính: y'({x0}) = {3 * a * x0 ** 2} + {2 * b * x0} = {val}.",
            f"Vậy đạo hàm tại x = {x0} bằng {val}.",
        ],
        answer=f"{val}", answer_value=float(val), unit=None,
    )


def t_cap_so_cong(r: Rng) -> dict[str, Any]:
    u1 = r.randrange(-10, 16)
    d = r.choice([x for x in range(-6, 9) if x != 0])
    n = r.randrange(5, 31)
    un = u1 + (n - 1) * d
    return dict(
        domain="math", subtopic="cap_so",
        problem=f"Cho cấp số cộng có số hạng đầu u₁ = {u1} và công sai d = {d}. "
                f"Tính số hạng thứ {n}.",
        steps=[
            f"Công thức số hạng tổng quát của cấp số cộng: uₙ = u₁ + (n−1)d.",
            f"Thay số với n = {n}: u_{n} = {u1} + ({n}−1)×{d}.",
            f"Tính: u_{n} = {u1} + {(n - 1) * d} = {un}.",
            f"Vậy số hạng thứ {n} là {un}.",
        ],
        answer=f"{un}", answer_value=float(un), unit=None,
    )


def t_mo_dun_so_phuc(r: Rng) -> dict[str, Any]:
    a = r.choice([x for x in range(-12, 13) if x != 0])
    b = r.choice([x for x in range(-15, 16) if x != 0])
    mod = math.hypot(a, b)
    return dict(
        domain="math", subtopic="so_phuc",
        problem=f"Cho số phức z = {a} {'+' if b >= 0 else '−'} {abs(b)}i. Tính mô đun của z.",
        steps=[
            f"Công thức mô đun số phức z = a + bi: |z| = √(a² + b²).",
            f"Với a = {a}, b = {b}: |z| = √({a}² + ({b})²) = √{a ** 2 + b ** 2}.",
            f"Tính: |z| = {_f(mod)}.",
            f"Vậy mô đun của z bằng {_f(mod)}.",
        ],
        answer=f"{_f(mod)}", answer_value=mod, unit=None,
    )


# ---------------------------------------------------------------------------
# HOÁ HỌC
# ---------------------------------------------------------------------------

_METALS = {"Fe": (56, 2), "Zn": (65, 2), "Mg": (24, 2), "Al": (27, 3), "Ca": (40, 2)}


def t_kim_loai_axit(r: Rng) -> dict[str, Any]:
    sym = r.choice(list(_METALS))
    M, val = _METALS[sym]
    n_metal = round(r.randrange(5, 81) / 100, 2)
    mass = round(n_metal * M, 3)
    n_h2 = n_metal * val / 2
    V = n_h2 * 22.4
    return dict(
        domain="chemistry", subtopic="kim_loai",
        problem=f"Cho {_f(mass)} gam {sym} tác dụng hoàn toàn với dung dịch HCl dư. "
                f"Tính thể tích khí H₂ thu được ở điều kiện tiêu chuẩn. Cho {sym} = {M}.",
        steps=[
            f"Tính số mol kim loại: n({sym}) = m/M = {_f(mass)}/{M} = {_f(n_metal)} mol.",
            f"Phương trình: 2{sym} + {2 * val}HCl → 2{sym}Cl_{val} + {val}H₂ "
            f"(tỉ lệ mol {sym} : H₂ = 2 : {val}).",
            f"Suy ra n(H₂) = {_f(n_metal)}×{val}/2 = {_f(n_h2)} mol.",
            f"Thể tích ở đktc: V = n×22,4 = {_f(n_h2)}×22,4 = {_f(V)} lít.",
            f"Kiểm tra điều kiện: HCl dư nên {sym} phản ứng hết, tính theo {sym} là hợp lệ.",
        ],
        answer=f"{_f(V)} lít", answer_value=V, unit="L",
    )


def t_ph_axit_manh(r: Rng) -> dict[str, Any]:
    p = r.choice([1, 2, 3, 4])
    C = 10 ** (-p)
    return dict(
        domain="chemistry", subtopic="axit_bazo_ph",
        problem=f"Tính pH của dung dịch HCl có nồng độ {C:g} M.",
        steps=[
            f"HCl là axit mạnh, điện li hoàn toàn: HCl → H⁺ + Cl⁻.",
            f"Do đó [H⁺] = C_M = {C:g} M.",
            f"Áp dụng pH = −log[H⁺] = −log({C:g}) = {p}.",
            f"Vậy pH của dung dịch bằng {p}.",
        ],
        answer=f"{p}", answer_value=float(p), unit=None,
    )


def t_the_tich_khi(r: Rng) -> dict[str, Any]:
    n = round(r.randrange(5, 151) / 100, 2)
    V = n * 22.4
    return dict(
        domain="chemistry", subtopic="tinh_toan_mol",
        problem=f"Đốt cháy hoàn toàn {_f(n)} mol CH₄. Tính thể tích khí CO₂ thu được "
                f"ở điều kiện tiêu chuẩn.",
        steps=[
            f"Phương trình cháy: CH₄ + 2O₂ → CO₂ + 2H₂O.",
            f"Tỉ lệ mol CH₄ : CO₂ = 1 : 1 nên n(CO₂) = n(CH₄) = {_f(n)} mol.",
            f"Thể tích khí ở đktc: V = n×22,4 = {_f(n)}×22,4 = {_f(V)} lít.",
            f"Vậy thu được {_f(V)} lít khí CO₂.",
        ],
        answer=f"{_f(V)} lít", answer_value=V, unit="L",
    )


TEMPLATES: list[Callable[[Rng], dict[str, Any]]] = [
    t_con_lac_lo_xo, t_song_co, t_khe_young, t_van_toc_cuc_dai, t_tong_tro, t_phong_xa,
    t_tich_phan, t_dao_ham, t_cap_so_cong, t_mo_dun_so_phuc,
    t_kim_loai_axit, t_ph_axit_manh, t_the_tich_khi,
]


def generate(n: int, seed: int = 42) -> list[dict[str, Any]]:
    """Sinh n lời giải đúng, phân bố đều trên các template."""
    r = Rng(seed)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    attempts = 0
    # Xoay vòng theo SỐ LẦN THỬ, không theo số bài đã nhận. Nếu xoay theo len(out),
    # một template hết tổ hợp mới sẽ giữ nguyên chỉ số và khoá vòng lặp ở chính nó.
    while len(out) < n and attempts < n * 40:
        item = TEMPLATES[attempts % len(TEMPLATES)](r)
        attempts += 1
        if item["problem"] in seen:
            continue  # trùng lặp làm model nhớ vẹt thay vì học
        seen.add(item["problem"])
        item["id"] = f"syn_{len(out):05d}"
        out.append(item)
    return out
