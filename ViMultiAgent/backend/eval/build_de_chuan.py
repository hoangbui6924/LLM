"""Sinh bộ đề chuẩn để đo hiệu năng — 150 bài, 50 mỗi môn.

Chạy:  python eval/build_de_chuan.py

Vì sao SINH ra chứ không gõ tay
-------------------------------
Bộ đề này là *ground truth*. Sai một đáp án là mọi số liệu tính từ nó thành rác,
và loại lỗi đó gần như không thể phát hiện về sau — bench sẽ báo hệ thống "sai"
ở một bài mà thực ra nó giải đúng.

Gõ tay 150 đáp án thì chắc chắn có vài chỗ nhầm. Ở đây mỗi mẫu đề mã hoá sẵn một
CÔNG THỨC, còn đáp án do Python tính ra từ ĐÚNG những con số đã đưa vào đề. Sai
số học là không thể xảy ra về mặt kiến tạo.

Ba tầng bảo đảm
---------------
1. Đáp án tính bằng code từ tham số của chính đề bài.
2. Cột `bieu_thuc_kiem` ghi lại công thức đã thay số. `eval/kiem_de_chuan.py`
   dùng SymPy tính lại cột này và đối chiếu với `answer_value` — bắt mọi lệch
   giữa "công thức đã ghi" và "đáp án đã lưu".
3. Bài cân bằng phương trình hoá học lấy hệ số từ `tools.chem_tool` (giải bằng
   không gian null của ma trận nguyên tố), không do người soạn đoán.

Tầng thứ 3 mà script không thay được: TÍNH ĐÚNG CỦA CÔNG THỨC. Việc chọn
`Z = sqrt(R^2 + (ZL - ZC)^2)` là đúng vật lý hay không thì chỉ người đọc mới
thẩm định được. Mỗi mẫu vì vậy đều ghi rõ công thức trong `ghi_chu` để rà soát.
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path
from typing import Callable

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools import chem_tool  # noqa: E402

RA = GOC / "eval" / "data" / "de_chuan.csv"
SO_BAI_MOI_MON = 50

# Nguyên tử khối dùng trong đề — lấy tròn theo sách giáo khoa phổ thông, KHÔNG
# lấy theo bảng chính xác của chem_tool. Học sinh THPT được cho H=1, O=16, và đề
# phải nhất quán với con số mà đề tự cung cấp.
NTK = {"H": 1, "C": 12, "N": 14, "O": 16, "Na": 23, "Mg": 24, "Al": 27,
       "S": 32, "Cl": 35.5, "K": 39, "Ca": 40, "Fe": 56, "Cu": 64, "Zn": 65,
       "Ag": 108, "Ba": 137}


def vn(x: float, chu_so: int = 4) -> str:
    """Số theo cách viết Việt Nam: dấu phẩy thập phân, bỏ đuôi 0 thừa."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    s = f"{x:.{chu_so}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def M(ct: dict[str, int]) -> float:
    """Khối lượng mol từ số nguyên tử mỗi nguyên tố."""
    return sum(NTK[e] * n for e, n in ct.items())


def hs(a: int, bien: str) -> str:
    """Viết hệ số theo lối toán học: 1x thành x, 1i thành i.

    Nhỏ nhặt nhưng đáng làm: đề viết `y = 1x^2 + 3x + 5` trông như lỗi máy sinh,
    và mô hình ngôn ngữ cũng phải tiêu thêm token để hiểu.
    """
    return bien if a == 1 else f"{a}{bien}"


# ---------------------------------------------------------------------------
# TOÁN — 25 mẫu
# ---------------------------------------------------------------------------


def m01(r):
    a, b, c, x0 = r.choice([2, 3, 4]), r.choice([5, 7, 11]), r.choice([1, 2]), r.choice([1, 2, 3])
    dap = 3 * a * x0**2 + b
    return dict(
        topic="dao_ham", level="NB",
        question=f"Tính đạo hàm của hàm số y = {a}x^3 + {b}x - {c} tại điểm x = {x0}.",
        answer_value=dap, bieu_thuc_kiem=f"3*{a}*{x0}**2 + {b}",
        ghi_chu="y' = 3ax^2 + b, thay x0",
    )


def m02(r):
    a, b, t = r.choice([3, 6]), r.choice([2, 4]), r.choice([1, 2])
    dap = a * t**3 / 3 + b * t**2 / 2
    return dict(
        topic="tich_phan", level="NB",
        question=f"Tính tích phân I = ∫ từ 0 đến {t} của ({a}x^2 + {b}x) dx.",
        answer_value=dap, bieu_thuc_kiem=f"{a}*{t}**3/3 + {b}*{t}**2/2",
        ghi_chu="Nguyên hàm ax^3/3 + bx^2/2, thay cận",
    )


def m03(r):
    r1, r2 = sorted(r.sample([2, 3, 4, 5, 6, 7], 2))
    s, p = r1 + r2, r1 * r2
    return dict(
        topic="phuong_trinh_bac_hai", level="NB",
        question=f"Tìm nghiệm lớn nhất của phương trình x^2 - {s}x + {p} = 0.",
        answer_value=float(r2), bieu_thuc_kiem=f"({s} + sqrt({s}**2 - 4*{p}))/2",
        ghi_chu="Công thức nghiệm, lấy nghiệm lớn",
    )


def m04(r):
    co_so, k = r.choice([2, 3, 5]), r.choice([3, 4, 5])
    return dict(
        topic="logarit", level="NB",
        question=f"Tính giá trị của biểu thức log cơ số {co_so} của {co_so**k}.",
        answer_value=float(k), bieu_thuc_kiem=f"log({co_so**k})/log({co_so})",
        ghi_chu="log_a(a^k) = k",
    )


def m05(r):
    u1, d, n = r.choice([3, 5, 7]), r.choice([2, 4, 6]), r.choice([10, 12, 15])
    return dict(
        topic="cap_so_cong", level="NB",
        question=f"Cho cấp số cộng có số hạng đầu u1 = {u1} và công sai d = {d}. Tính số hạng thứ {n}.",
        answer_value=float(u1 + (n - 1) * d), bieu_thuc_kiem=f"{u1} + ({n} - 1)*{d}",
        ghi_chu="u_n = u1 + (n-1)d",
    )


def m06(r):
    u1, q, n = r.choice([2, 3]), r.choice([2, 3]), r.choice([5, 6])
    return dict(
        topic="cap_so_nhan", level="NB",
        question=f"Cho cấp số nhân có số hạng đầu u1 = {u1} và công bội q = {q}. Tính số hạng thứ {n}.",
        answer_value=float(u1 * q ** (n - 1)), bieu_thuc_kiem=f"{u1}*{q}**({n} - 1)",
        ghi_chu="u_n = u1*q^(n-1)",
    )


def m07(r):
    a, b, c, x0 = r.choice([2, 3]), r.choice([4, 5]), r.choice([1, 6]), r.choice([2, 3])
    return dict(
        topic="gia_tri_ham_so", level="NB",
        question=f"Cho hàm số f(x) = {a}x^2 + {b}x - {c}. Tính f({x0}).",
        answer_value=float(a * x0**2 + b * x0 - c),
        bieu_thuc_kiem=f"{a}*{x0}**2 + {b}*{x0} - {c}",
        ghi_chu="Thay số vào hàm",
    )


def m08(r):
    a, b, p, q = r.choice([2, 4]), r.choice([1, 3]), r.choice([1, 2]), r.choice([3, 4])
    dap = a * (q**2 - p**2) / 2 + b * (q - p)
    return dict(
        topic="tich_phan", level="TH",
        question=f"Tính tích phân I = ∫ từ {p} đến {q} của ({a}x + {b}) dx.",
        answer_value=dap,
        bieu_thuc_kiem=f"{a}*({q}**2 - {p}**2)/2 + {b}*({q} - {p})",
        ghi_chu="Nguyên hàm ax^2/2 + bx, hiệu hai cận",
    )


def m09(r):
    co_so, m, k = r.choice([2, 3]), r.choice([3, 4, 5]), r.choice([1, 2])
    return dict(
        topic="phuong_trinh_mu", level="TH",
        question=f"Giải phương trình {co_so}^(x + {k}) = {co_so**m}.",
        answer_value=float(m - k), bieu_thuc_kiem=f"{m} - {k}",
        ghi_chu="Đưa về cùng cơ số rồi cân bằng số mũ",
    )


def m10(r):
    import math
    n, k = r.choice([8, 10, 12]), r.choice([2, 3])
    return dict(
        topic="to_hop", level="TH",
        question=f"Một lớp có {n} học sinh. Có bao nhiêu cách chọn ra {k} học sinh để trực nhật?",
        answer_value=float(math.comb(n, k)),
        bieu_thuc_kiem=f"factorial({n})/(factorial({k})*factorial({n - k}))",
        ghi_chu="Tổ hợp chập k của n, không kể thứ tự",
    )


def m11(r):
    import math
    n, k = r.choice([6, 7, 8]), r.choice([2, 3])
    return dict(
        topic="chinh_hop", level="TH",
        question=f"Có bao nhiêu cách xếp {k} học sinh vào {k} vị trí khác nhau từ một nhóm {n} học sinh?",
        answer_value=float(math.perm(n, k)),
        bieu_thuc_kiem=f"factorial({n})/factorial({n - k})",
        ghi_chu="Chỉnh hợp chập k của n, CÓ kể thứ tự",
    )


def m12(r):
    a, b, c, d = r.choice([1, 2]), r.choice([2, 3]), r.choice([3, 4]), r.choice([1, 2])
    return dict(
        topic="so_phuc", level="TH",
        question=f"Cho số phức z = ({a} + {hs(b, 'i')})({c} - {hs(d, 'i')}). Tìm phần thực của z.",
        answer_value=float(a * c + b * d), bieu_thuc_kiem=f"{a}*{c} + {b}*{d}",
        ghi_chu="(a+bi)(c-di) có phần thực ac + bd vì i^2 = -1",
    )


def m13(r):
    a, b = r.choice([3, 6, 8]), r.choice([4, 8, 15])
    import math
    return dict(
        topic="so_phuc", level="TH",
        question=f"Tính môđun của số phức z = {a} + {b}i.",
        answer_value=math.hypot(a, b), bieu_thuc_kiem=f"sqrt({a}**2 + {b}**2)",
        ghi_chu="|z| = sqrt(a^2 + b^2)",
    )


def m14(r):
    a, c = r.choice([2, 3, 4]), r.choice([1, 2])
    b, d = r.choice([1, 5]), r.choice([3, 4])
    return dict(
        topic="tiem_can", level="TH",
        question=f"Tìm tiệm cận ngang của đồ thị hàm số y = ({hs(a, 'x')} + {b})/({hs(c, 'x')} - {d}).",
        answer_value=a / c, bieu_thuc_kiem=f"{a}/{c}",
        ghi_chu="Tiệm cận ngang y = a/c khi bậc tử bằng bậc mẫu",
    )


def m15(r):
    tong = r.choice([5, 6, 7, 8, 9])
    dem = sum(1 for i in range(1, 7) for j in range(1, 7) if i + j == tong)
    return dict(
        topic="xac_suat", level="TH",
        question=f"Gieo đồng thời hai con xúc xắc cân đối. Tính xác suất để tổng số chấm bằng {tong}.",
        answer_value=dem / 36, bieu_thuc_kiem=f"{dem}/36",
        ghi_chu="Xác suất cổ điển, không gian mẫu 36",
    )


def m16(r):
    a, b, c, x0 = r.choice([1, 2]), r.choice([2, 3]), r.choice([1, 5]), r.choice([1, 2])
    k = 2 * a * x0 + b
    y0 = a * x0**2 + b * x0 + c
    return dict(
        topic="tiep_tuyen", level="VD", question_type="symbolic",
        question=(f"Cho hàm số y = {hs(a, 'x^2')} + {hs(b, 'x')} + {c}. Viết phương trình tiếp tuyến "
                  f"của đồ thị hàm số tại điểm có hoành độ x = {x0}."),
        answer_expr=f"{k}*x + {y0 - k * x0}",
        bieu_thuc_kiem=f"{k}*(x - {x0}) + {y0}",
        ghi_chu="y = y'(x0)(x - x0) + y(x0). Đáp số là BIỂU THỨC",
    )


def m17(r):
    a, b = r.choice([1, 2, 3]), r.choice([1, 4, 5])
    return dict(
        topic="cuc_tri", level="VD",
        question=f"Cho hàm số y = x^3 - {3 * a}x^2 + {b}. Tìm giá trị cực đại của hàm số.",
        answer_value=float(b), bieu_thuc_kiem=f"0**3 - {3 * a}*0**2 + {b}",
        ghi_chu="y' = 3x^2 - 6ax = 0 tại x=0 và x=2a; x=0 là điểm cực đại",
    )


def m18(r):
    import sympy as sp
    c, hi = r.choice([1, 2, 5]), r.choice([2, 3])
    x = sp.Symbol("x")
    f = x**3 - 3 * x + c
    moc = [0, hi] + [s for s in sp.solve(sp.diff(f, x), x) if s.is_real and 0 <= s <= hi]
    dap = max(float(f.subs(x, m)) for m in moc)
    return dict(
        topic="gtln_gtnn", level="VD",
        question=f"Tìm giá trị lớn nhất của hàm số y = x^3 - 3x + {c} trên đoạn [0; {hi}].",
        answer_value=dap, bieu_thuc_kiem=f"{hi}**3 - 3*{hi} + {c}",
        ghi_chu="So sánh giá trị tại hai đầu mút và các điểm tới hạn",
    )


def m19(r):
    a, h = r.choice([3, 4, 6]), r.choice([4, 5, 9])
    return dict(
        topic="the_tich_khoi_chop", level="VD",
        question=f"Cho khối chóp có đáy là hình vuông cạnh {a} và chiều cao bằng {h}. Tính thể tích khối chóp.",
        answer_value=a**2 * h / 3, bieu_thuc_kiem=f"1/3*{a}**2*{h}",
        ghi_chu="V = (1/3)*S_đáy*h",
    )


def m20(r):
    a, b, h = r.choice([3, 4]), r.choice([5, 6]), r.choice([4, 10])
    return dict(
        topic="the_tich_lang_tru", level="VD",
        question=(f"Cho khối lăng trụ đứng có đáy là tam giác vuông với hai cạnh góc vuông "
                  f"bằng {a} và {b}, chiều cao lăng trụ bằng {h}. Tính thể tích khối lăng trụ."),
        answer_value=a * b / 2 * h, bieu_thuc_kiem=f"1/2*{a}*{b}*{h}",
        ghi_chu="V = S_đáy*h, đáy là tam giác vuông",
    )


def m21(r):
    import math
    do, xanh = r.choice([5, 6]), r.choice([3, 4])
    dap = math.comb(do, 2) * math.comb(xanh, 1) / math.comb(do + xanh, 3)
    return dict(
        topic="xac_suat", level="VD",
        question=(f"Một hộp có {do} viên bi đỏ và {xanh} viên bi xanh. Lấy ngẫu nhiên 3 viên. "
                  f"Tính xác suất lấy được đúng 2 viên bi đỏ."),
        answer_value=dap,
        bieu_thuc_kiem=f"{math.comb(do, 2)}*{math.comb(xanh, 1)}/{math.comb(do + xanh, 3)}",
        ghi_chu="C(do,2)*C(xanh,1)/C(tổng,3). Bài này Router hay nhầm sang môn Lý",
    )


def m22(r):
    k, m = r.choice([2, 3]), r.choice([3, 4])
    import math
    dap = (k + math.sqrt(k**2 + 4 * 2**m)) / 2
    return dict(
        topic="phuong_trinh_logarit", level="VD",
        question=(f"Giải phương trình log cơ số 2 của x cộng log cơ số 2 của (x - {k}) bằng {m}. "
                  f"Tìm nghiệm của phương trình."),
        answer_value=dap, bieu_thuc_kiem=f"({k} + sqrt({k}**2 + 4*2**{m}))/2",
        ghi_chu=f"x(x-{k}) = 2^{m}; điều kiện x > {k} nên loại nghiệm âm",
    )


def m23(r):
    import math
    t = r.choice([1, 2])
    dap = (t - 1) * math.exp(t) + 1
    return dict(
        topic="tich_phan_tung_phan", level="VDC",
        question=f"Tính tích phân I = ∫ từ 0 đến {t} của x·e^x dx.",
        answer_value=dap, bieu_thuc_kiem=f"({t} - 1)*exp({t}) + 1",
        ghi_chu="Từng phần: u = x, dv = e^x dx, cho (x-1)e^x",
    )


def m24(r):
    import math
    k = r.choice([4, 9, 16, 25])
    return dict(
        topic="bat_dang_thuc", level="VDC",
        question=f"Tìm giá trị nhỏ nhất của biểu thức f(x) = x + {k}/x với x > 0.",
        answer_value=2 * math.sqrt(k), bieu_thuc_kiem=f"2*sqrt({k})",
        ghi_chu="Cauchy: x + k/x >= 2*sqrt(k), dấu bằng khi x = sqrt(k)",
    )


def m25(r):
    import math
    nam, nu, chon = r.choice([6, 7]), r.choice([4, 5]), r.choice([3, 4])
    dap = 1 - math.comb(nam, chon) / math.comb(nam + nu, chon)
    return dict(
        topic="xac_suat", level="VDC",
        question=(f"Một nhóm có {nam} nam và {nu} nữ. Chọn ngẫu nhiên {chon} người. "
                  f"Tính xác suất để trong nhóm được chọn có ít nhất một nữ."),
        answer_value=dap,
        bieu_thuc_kiem=f"1 - {math.comb(nam, chon)}/{math.comb(nam + nu, chon)}",
        ghi_chu="Dùng biến cố đối: 1 - P(toàn nam)",
    )


# ---------------------------------------------------------------------------
# VẬT LÝ — 25 mẫu
# ---------------------------------------------------------------------------


def p01(r):
    v = r.choice([36, 54, 72, 90])
    return dict(
        topic="doi_don_vi", level="NB",
        question=f"Một ô tô chuyển động với vận tốc {v} km/h. Tính vận tốc của ô tô theo đơn vị m/s.",
        answer_value=v * 1000 / 3600, answer_unit="m/s",
        bieu_thuc_kiem=f"{v}*1000/3600", ghi_chu="1 km/h = 1/3,6 m/s",
    )


def p02(r):
    u, res = r.choice([6, 12, 24]), r.choice([2, 3, 4])
    return dict(
        topic="dinh_luat_ohm", level="NB",
        question=f"Đặt hiệu điện thế U = {u} V vào hai đầu điện trở R = {res} Ω. Tính cường độ dòng điện qua điện trở.",
        answer_value=u / res, answer_unit="A",
        bieu_thuc_kiem=f"{u}/{res}", ghi_chu="I = U/R",
    )


def p03(r):
    f = r.choice([2, 4, 5, 10])
    return dict(
        topic="dao_dong_dieu_hoa", level="NB",
        question=f"Một vật dao động điều hoà với tần số f = {f} Hz. Tính chu kỳ dao động của vật.",
        answer_value=1 / f, answer_unit="s",
        bieu_thuc_kiem=f"1/{f}", ghi_chu="T = 1/f",
    )


def p04(r):
    m = r.choice([2, 5, 8, 10])
    return dict(
        topic="trong_luc", level="NB",
        question=f"Một vật có khối lượng m = {m} kg. Tính trọng lượng của vật, lấy g = 10 m/s^2.",
        answer_value=m * 10, answer_unit="N",
        bieu_thuc_kiem=f"{m}*10", ghi_chu="P = mg",
    )


def p05(r):
    lam, f = r.choice([2, 4, 5]), r.choice([20, 50, 100])
    return dict(
        topic="song_co", level="NB",
        question=f"Một sóng cơ có bước sóng {lam} m và tần số {f} Hz. Tính tốc độ truyền sóng.",
        answer_value=lam * f, answer_unit="m/s",
        bieu_thuc_kiem=f"{lam}*{f}", ghi_chu="v = lambda*f",
    )


def p06(r):
    fo, s = r.choice([20, 50, 100]), r.choice([3, 5, 10])
    return dict(
        topic="cong_co_hoc", level="NB",
        question=f"Một lực {fo} N kéo vật đi được quãng đường {s} m theo phương của lực. Tính công của lực.",
        answer_value=fo * s, answer_unit="J",
        bieu_thuc_kiem=f"{fo}*{s}", ghi_chu="A = F*s khi lực cùng phương chuyển động",
    )


def p07(r):
    m, v = r.choice([270, 540, 800]), r.choice([100, 200])
    return dict(
        topic="khoi_luong_rieng", level="NB",
        question=f"Một khối vật chất có khối lượng {m} g và thể tích {v} cm^3. Tính khối lượng riêng của vật.",
        answer_value=m / v, answer_unit="g/cm^3",
        bieu_thuc_kiem=f"{m}/{v}", ghi_chu="D = m/V",
    )


def p08(r):
    a_cm, w = r.choice([4, 5, 6]), r.choice([10, 20])
    return dict(
        topic="dao_dong_dieu_hoa", level="TH",
        question=(f"Một vật dao động điều hoà với biên độ A = {a_cm} cm và tần số góc "
                  f"ω = {w} rad/s. Tính vận tốc cực đại của vật."),
        answer_value=a_cm / 100 * w, answer_unit="m/s",
        bieu_thuc_kiem=f"{a_cm}/100*{w}", ghi_chu="v_max = A*omega, đổi cm sang m",
    )


def p09(r):
    import math
    l = r.choice([1, 0.4, 2.5])
    return dict(
        topic="con_lac_don", level="TH",
        question=(f"Một con lắc đơn có chiều dài l = {vn(l)} m dao động tại nơi có "
                  f"g = 9,8 m/s^2. Tính chu kỳ dao động của con lắc."),
        answer_value=2 * math.pi * math.sqrt(l / 9.8), answer_unit="s",
        bieu_thuc_kiem=f"2*pi*sqrt({l}/9.8)", ghi_chu="T = 2*pi*sqrt(l/g)",
    )


def p10(r):
    m, v = r.choice([2, 4, 5]), r.choice([4, 6, 10])
    return dict(
        topic="dong_nang", level="TH",
        question=f"Một vật khối lượng {m} kg chuyển động với vận tốc {v} m/s. Tính động năng của vật.",
        answer_value=0.5 * m * v**2, answer_unit="J",
        bieu_thuc_kiem=f"0.5*{m}*{v}**2", ghi_chu="W_d = mv^2/2",
    )


def p11(r):
    m, h = r.choice([2, 3, 5]), r.choice([4, 10, 20])
    return dict(
        topic="the_nang", level="TH",
        question=f"Một vật khối lượng {m} kg được đưa lên độ cao {h} m. Lấy g = 10 m/s^2. Tính thế năng trọng trường của vật.",
        answer_value=m * 10 * h, answer_unit="J",
        bieu_thuc_kiem=f"{m}*10*{h}", ghi_chu="W_t = mgh",
    )


def p12(r):
    eps, a = r.choice([3.1, 4.2, 5.0]), r.choice([2.2, 2.5, 3.0])
    return dict(
        topic="quang_dien", level="TH",
        question=(f"Chiếu ánh sáng vào một kim loại có công thoát {vn(a)} eV. Biết năng lượng "
                  f"của photon là {vn(eps)} eV. Tính động năng ban đầu cực đại của electron quang điện."),
        answer_value=eps - a, answer_unit="eV",
        bieu_thuc_kiem=f"{eps} - {a}", ghi_chu="Einstein: W_d_max = epsilon - A",
    )


def p13(r):
    r1, r2, u = r.choice([3, 5]), r.choice([6, 7]), r.choice([18, 24, 36])
    return dict(
        topic="dien_tro", level="TH",
        question=(f"Hai điện trở R1 = {r1} Ω và R2 = {r2} Ω mắc nối tiếp vào hiệu điện thế "
                  f"U = {u} V. Tính cường độ dòng điện trong mạch."),
        answer_value=u / (r1 + r2), answer_unit="A",
        bieu_thuc_kiem=f"{u}/({r1} + {r2})", ghi_chu="Nối tiếp: R = R1 + R2, I = U/R",
    )


def p14(r):
    r1, r2 = r.choice([3, 4, 6]), r.choice([6, 12])
    return dict(
        topic="dien_tro", level="TH",
        question=f"Hai điện trở R1 = {r1} Ω và R2 = {r2} Ω mắc song song. Tính điện trở tương đương của đoạn mạch.",
        answer_value=r1 * r2 / (r1 + r2), answer_unit="Ohm",
        bieu_thuc_kiem=f"{r1}*{r2}/({r1} + {r2})", ghi_chu="Song song: R = R1*R2/(R1+R2)",
    )


def p15(r):
    m, dt = r.choice([2, 3, 5]), r.choice([20, 30, 50])
    return dict(
        topic="nhiet_luong", level="TH",
        question=(f"Tính nhiệt lượng cần cung cấp để đun nóng {m} kg nước tăng thêm {dt} độ C. "
                  f"Biết nhiệt dung riêng của nước là 4200 J/(kg.K)."),
        answer_value=m * 4200 * dt, answer_unit="J",
        bieu_thuc_kiem=f"{m}*4200*{dt}", ghi_chu="Q = mc*delta_t",
    )


def p16(r):
    import math
    k, m = r.choice([100, 400]), r.choice([0.25, 1, 4])
    return dict(
        topic="con_lac_lo_xo", level="VD",
        question=(f"Một con lắc lò xo có độ cứng k = {k} N/m gắn vật nặng khối lượng "
                  f"m = {vn(m)} kg. Tính tần số góc của dao động."),
        answer_value=math.sqrt(k / m), answer_unit="rad/s",
        bieu_thuc_kiem=f"sqrt({k}/{m})", ghi_chu="omega = sqrt(k/m)",
    )


def p17(r):
    import math
    res, zl, zc = r.choice([30, 40, 60]), r.choice([70, 80]), r.choice([30, 40])
    return dict(
        topic="mach_rlc", level="VD",
        question=(f"Một đoạn mạch xoay chiều có R = {res} Ω, cảm kháng ZL = {zl} Ω và "
                  f"dung kháng ZC = {zc} Ω. Tính tổng trở của đoạn mạch."),
        answer_value=math.hypot(res, zl - zc), answer_unit="Ohm",
        bieu_thuc_kiem=f"sqrt({res}**2 + ({zl} - {zc})**2)",
        ghi_chu="Z = sqrt(R^2 + (ZL - ZC)^2)",
    )


def p18(r):
    lam_um, d, a_mm = r.choice([0.5, 0.6]), r.choice([2, 3]), r.choice([1, 1.5])
    dap_mm = lam_um * 1e-6 * d / (a_mm * 1e-3) * 1000
    return dict(
        topic="giao_thoa_anh_sang", level="VD",
        question=(f"Trong thí nghiệm giao thoa Y-âng, khoảng cách giữa hai khe a = {vn(a_mm)} mm, "
                  f"khoảng cách từ hai khe đến màn D = {d} m, ánh sáng đơn sắc có bước sóng "
                  f"{vn(lam_um)} μm. Tính khoảng vân quan sát được trên màn."),
        answer_value=dap_mm, answer_unit="mm",
        bieu_thuc_kiem=f"{lam_um}*1e-6*{d}/({a_mm}*1e-3)*1000",
        ghi_chu="i = lambda*D/a, chú ý đổi đơn vị",
    )


def p19(r):
    t_bra, so_ck = r.choice([8, 15, 20]), r.choice([2, 3, 4])
    t = t_bra * so_ck
    return dict(
        topic="phong_xa", level="VD",
        question=(f"Một chất phóng xạ có chu kỳ bán rã {t_bra} ngày. Sau {t} ngày, phần trăm "
                  f"khối lượng chất phóng xạ còn lại so với ban đầu là bao nhiêu?"),
        answer_value=100 * 0.5**so_ck, answer_unit="%",
        bieu_thuc_kiem=f"100*(1/2)**({t}/{t_bra})",
        ghi_chu="m = m0*(1/2)^(t/T)",
    )


def p20(r):
    import math
    h = r.choice([20, 45, 80])
    return dict(
        topic="nem_ngang", level="VD",
        question=f"Một vật được ném ngang từ độ cao {h} m. Lấy g = 10 m/s^2. Tính thời gian rơi của vật.",
        answer_value=math.sqrt(2 * h / 10), answer_unit="s",
        bieu_thuc_kiem=f"sqrt(2*{h}/10)",
        ghi_chu="Ném ngang: thời gian rơi chỉ phụ thuộc độ cao, t = sqrt(2h/g)",
    )


def p21(r):
    n1, n2, u1 = r.choice([1000, 2000]), r.choice([200, 500]), r.choice([220, 110])
    return dict(
        topic="may_bien_ap", level="VD",
        question=(f"Một máy biến áp lí tưởng có cuộn sơ cấp {n1} vòng và cuộn thứ cấp {n2} vòng. "
                  f"Đặt vào hai đầu cuộn sơ cấp hiệu điện thế {u1} V. Tính hiệu điện thế ở cuộn thứ cấp."),
        answer_value=u1 * n2 / n1, answer_unit="V",
        bieu_thuc_kiem=f"{u1}*{n2}/{n1}", ghi_chu="U2/U1 = N2/N1",
    )


def p22(r):
    u, i = r.choice([220, 110]), r.choice([2, 5])
    return dict(
        topic="cong_suat_dien", level="VD",
        question=f"Một thiết bị điện hoạt động ở hiệu điện thế {u} V với cường độ dòng điện {i} A. Tính công suất tiêu thụ.",
        answer_value=u * i, answer_unit="W",
        bieu_thuc_kiem=f"{u}*{i}", ghi_chu="P = U*I",
    )


def p23(r):
    import math
    a1, a2 = r.choice([3, 6, 8]), r.choice([4, 8, 15])
    return dict(
        topic="tong_hop_dao_dong", level="VDC",
        question=(f"Một vật thực hiện đồng thời hai dao động điều hoà cùng phương, cùng tần số, "
                  f"biên độ lần lượt là {a1} cm và {a2} cm, lệch pha nhau π/2. "
                  f"Tính biên độ dao động tổng hợp."),
        answer_value=math.hypot(a1, a2), answer_unit="cm",
        bieu_thuc_kiem=f"sqrt({a1}**2 + {a2}**2)",
        ghi_chu="Vuông pha: A = sqrt(A1^2 + A2^2)",
    )


def p24(r):
    import math
    l, c_uf = r.choice([0.1, 0.4]), r.choice([10, 25])
    c = c_uf * 1e-6
    return dict(
        topic="mach_dao_dong", level="VDC",
        question=(f"Một mạch dao động LC lí tưởng có độ tự cảm L = {vn(l)} H và điện dung "
                  f"C = {c_uf} μF. Tính tần số dao động riêng của mạch."),
        answer_value=1 / (2 * math.pi * math.sqrt(l * c)), answer_unit="Hz",
        bieu_thuc_kiem=f"1/(2*pi*sqrt({l}*{c_uf}*1e-6))",
        ghi_chu="f = 1/(2*pi*sqrt(LC))",
    )


def p25(r):
    a, x = r.choice([10, 8]), r.choice([6, 4])
    return dict(
        topic="nang_luong_dao_dong", level="VDC",
        question=(f"Một vật dao động điều hoà với biên độ A = {a} cm. Tại vị trí có li độ "
                  f"x = {x} cm, tính tỉ số giữa động năng và thế năng của vật."),
        answer_value=(a**2 - x**2) / x**2,
        bieu_thuc_kiem=f"({a}**2 - {x}**2)/{x}**2",
        ghi_chu="W_d/W_t = (A^2 - x^2)/x^2",
    )


# ---------------------------------------------------------------------------
# HOÁ HỌC — 25 mẫu
# ---------------------------------------------------------------------------

_HOP_CHAT = [
    ("H2SO4", {"H": 2, "S": 1, "O": 4}),
    ("HNO3", {"H": 1, "N": 1, "O": 3}),
    ("CaCO3", {"Ca": 1, "C": 1, "O": 3}),
    ("Na2CO3", {"Na": 2, "C": 1, "O": 3}),
    ("Al2O3", {"Al": 2, "O": 3}),
    ("CuSO4", {"Cu": 1, "S": 1, "O": 4}),
]


def c01(r):
    ten, ct = r.choice(_HOP_CHAT)
    cho = ", ".join(f"{e} = {vn(NTK[e])}" for e in sorted(ct))
    return dict(
        topic="khoi_luong_mol", level="NB",
        question=f"Tính khối lượng mol của hợp chất {ten}. Biết {cho}.",
        answer_value=M(ct), answer_unit="g/mol",
        bieu_thuc_kiem=" + ".join(f"{NTK[e]}*{n}" for e, n in sorted(ct.items())),
        ghi_chu="Cộng khối lượng nguyên tử theo chỉ số",
    )


def c02(r):
    v = r.choice([2.24, 5.6, 11.2, 22.4])
    khi = r.choice(["O2", "CO2", "H2"])
    return dict(
        topic="so_mol", level="NB",
        question=f"Tính số mol của {vn(v)} lít khí {khi} ở điều kiện tiêu chuẩn.",
        answer_value=v / 22.4, answer_unit="mol",
        bieu_thuc_kiem=f"{v}/22.4", ghi_chu="n = V/22,4 ở đktc",
    )


def c03(r):
    ten, ct = r.choice([("NaOH", {"Na": 1, "O": 1, "H": 1}), ("CaCO3", {"Ca": 1, "C": 1, "O": 3})])
    mm = M(ct)
    n = r.choice([0.2, 0.5, 0.1])
    m = n * mm
    return dict(
        topic="so_mol", level="NB",
        question=f"Tính số mol có trong {vn(m)} gam {ten}. Biết M({ten}) = {vn(mm)} g/mol.",
        answer_value=n, answer_unit="mol",
        bieu_thuc_kiem=f"{m}/{mm}", ghi_chu="n = m/M",
    )


def c04(r):
    n, v_ml = r.choice([0.5, 0.2, 1.0]), r.choice([250, 500, 200])
    return dict(
        topic="nong_do_mol", level="NB",
        question=f"Hoà tan {vn(n)} mol NaCl vào nước thu được {v_ml} ml dung dịch. Tính nồng độ mol của dung dịch.",
        answer_value=n / (v_ml / 1000), answer_unit="M",
        bieu_thuc_kiem=f"{n}/({v_ml}/1000)", ghi_chu="C_M = n/V, V tính bằng lít",
    )


def c05(r):
    ten, ct = r.choice(_HOP_CHAT)
    n = r.choice([0.1, 0.25, 2])
    return dict(
        topic="khoi_luong_chat", level="NB",
        question=f"Tính khối lượng của {vn(n)} mol {ten}. Biết M({ten}) = {vn(M(ct))} g/mol.",
        answer_value=n * M(ct), answer_unit="gam",
        bieu_thuc_kiem=f"{n}*{M(ct)}", ghi_chu="m = n*M",
    )


def c06(r):
    """Hệ số cân bằng lấy từ chem_tool — giải bằng ma trận, không đoán."""
    pu = r.choice([
        (["Al", "O2"], ["Al2O3"], 1),
        (["Fe", "O2"], ["Fe3O4"], 1),
        (["H2", "O2"], ["H2O"], 1),
        (["C2H6", "O2"], ["CO2", "H2O"], 1),
    ])
    trai, phai, vi_tri = pu
    kq = chem_tool.balance_equation(trai, phai)
    if not kq.get("balanced"):
        return None
    he_so = kq["reactant_coeffs"][vi_tri]
    return dict(
        topic="can_bang_pthh", level="NB",
        question=(f"Cân bằng phương trình phản ứng {' + '.join(trai)} → {' + '.join(phai)}. "
                  f"Cho biết hệ số của {trai[vi_tri]} sau khi cân bằng."),
        answer_value=float(he_so), bieu_thuc_kiem=str(he_so),
        ghi_chu=f"Phương trình cân bằng: {kq['equation']} (tính bằng chem_tool)",
    )


def c07(r):
    ten, ct = r.choice([("Al2O3", {"Al": 2, "O": 3}), ("CaCO3", {"Ca": 1, "C": 1, "O": 3})])
    ngto = r.choice(sorted(ct))
    n = r.choice([0.1, 0.5])
    return dict(
        topic="so_mol_nguyen_tu", level="NB",
        question=f"Trong {vn(n)} mol {ten} có bao nhiêu mol nguyên tử {ngto}?",
        answer_value=n * ct[ngto], answer_unit="mol",
        bieu_thuc_kiem=f"{n}*{ct[ngto]}", ghi_chu=f"Mỗi phân tử {ten} có {ct[ngto]} nguyên tử {ngto}",
    )


def c08(r):
    kl, mkl, oxit, moxit = r.choice([
        ("Mg", 24, "MgO", 40), ("Ca", 40, "CaO", 56), ("Zn", 65, "ZnO", 81),
    ])
    n = r.choice([0.1, 0.2])
    m = n * mkl
    return dict(
        topic="tinh_theo_pthh", level="TH",
        question=(f"Đốt cháy hoàn toàn {vn(m)} gam {kl} trong khí O2 dư thu được {oxit}. "
                  f"Tính khối lượng {oxit} thu được. Biết {kl} = {mkl}, O = 16."),
        answer_value=m / mkl * moxit, answer_unit="gam",
        bieu_thuc_kiem=f"{m}/{mkl}*{moxit}",
        ghi_chu=f"2{kl} + O2 -> 2{oxit}, tỉ lệ mol 1:1",
    )


def c09(r):
    v_ml, cm = r.choice([100, 200]), r.choice([0.5, 1.0])
    return dict(
        topic="axit_bazo", level="TH",
        question=(f"Trung hoà hoàn toàn {v_ml} ml dung dịch HCl {vn(cm)}M bằng dung dịch NaOH. "
                  f"Tính khối lượng NaOH đã phản ứng. Biết M(NaOH) = 40 g/mol."),
        answer_value=v_ml / 1000 * cm * 40, answer_unit="gam",
        bieu_thuc_kiem=f"{v_ml}/1000*{cm}*40",
        ghi_chu="HCl + NaOH -> NaCl + H2O, tỉ lệ 1:1",
    )


def c10(r):
    import math
    c = r.choice([0.01, 0.001, 0.1])
    return dict(
        topic="ph", level="TH",
        question=f"Tính pH của dung dịch HCl có nồng độ {vn(c, 3)}M.",
        answer_value=-math.log10(c),
        bieu_thuc_kiem=f"-log({c})/log(10)",
        ghi_chu="HCl là axit mạnh, phân li hoàn toàn nên pH = -log[H+]",
    )


def c11(r):
    kl, mkl, hoa_tri = r.choice([("Al", 27, 3), ("Zn", 65, 2), ("Mg", 24, 2)])
    n = r.choice([0.1, 0.2])
    m = n * mkl
    n_h2 = n * hoa_tri / 2
    return dict(
        topic="kim_loai_axit", level="TH",
        question=(f"Hoà tan hoàn toàn {vn(m)} gam {kl} vào dung dịch HCl dư. Tính thể tích khí H2 "
                  f"thu được ở điều kiện tiêu chuẩn. Biết {kl} = {mkl}."),
        answer_value=n_h2 * 22.4, answer_unit="lit",
        bieu_thuc_kiem=f"{m}/{mkl}*{hoa_tri}/2*22.4",
        ghi_chu=f"{kl} hoá trị {hoa_tri}, mỗi mol {kl} cho {hoa_tri}/2 mol H2",
    )


def c12(r):
    m_chat, m_nuoc = r.choice([20, 40]), r.choice([180, 160])
    return dict(
        topic="nong_do_phan_tram", level="TH",
        question=f"Hoà tan {m_chat} gam muối vào {m_nuoc} gam nước. Tính nồng độ phần trăm của dung dịch thu được.",
        answer_value=m_chat / (m_chat + m_nuoc) * 100, answer_unit="%",
        bieu_thuc_kiem=f"{m_chat}/({m_chat} + {m_nuoc})*100",
        ghi_chu="C% = m_chất tan/m_dung dịch*100",
    )


def c13(r):
    hc, so_c = r.choice([("CH4", 1), ("C2H6", 2), ("C3H8", 3)])
    n = r.choice([0.1, 0.2])
    return dict(
        topic="dot_chay_huu_co", level="TH",
        question=(f"Đốt cháy hoàn toàn {vn(n)} mol {hc}. Tính thể tích khí CO2 thu được "
                  f"ở điều kiện tiêu chuẩn."),
        answer_value=n * so_c * 22.4, answer_unit="lit",
        bieu_thuc_kiem=f"{n}*{so_c}*22.4",
        ghi_chu=f"Mỗi mol {hc} cháy cho {so_c} mol CO2 (bảo toàn nguyên tố C)",
    )


def c14(r):
    c1, v1, v2 = r.choice([2.0, 1.0]), r.choice([100, 50]), r.choice([500, 250])
    return dict(
        topic="pha_loang", level="TH",
        question=(f"Pha loãng {v1} ml dung dịch NaOH {vn(c1)}M thành {v2} ml. "
                  f"Tính nồng độ mol của dung dịch sau khi pha loãng."),
        answer_value=c1 * v1 / v2, answer_unit="M",
        bieu_thuc_kiem=f"{c1}*{v1}/{v2}",
        ghi_chu="Số mol chất tan không đổi: C1*V1 = C2*V2",
    )


def c15(r):
    m_fe, h = r.choice([5.6, 11.2]), r.choice([80, 75])
    return dict(
        topic="hieu_suat", level="VD",
        question=(f"Đốt cháy {vn(m_fe)} gam Fe trong O2 dư thu được Fe3O4 với hiệu suất phản ứng "
                  f"{h}%. Tính khối lượng Fe3O4 thực tế thu được. Biết Fe = 56, O = 16."),
        answer_value=m_fe / 56 / 3 * 232 * h / 100, answer_unit="gam",
        bieu_thuc_kiem=f"{m_fe}/56/3*232*{h}/100",
        ghi_chu="3Fe + 2O2 -> Fe3O4 nên n(Fe3O4) = n(Fe)/3; nhân hiệu suất",
    )


def c16(r):
    n_naoh, n_hcl = r.choice([0.1, 0.15]), r.choice([0.2, 0.3])
    het = min(n_naoh, n_hcl)
    return dict(
        topic="chat_du", level="VD",
        question=(f"Cho {vn(n_naoh)} mol NaOH vào dung dịch chứa {vn(n_hcl)} mol HCl. "
                  f"Tính khối lượng muối NaCl thu được sau phản ứng. Biết M(NaCl) = 58,5 g/mol."),
        answer_value=het * 58.5, answer_unit="gam",
        bieu_thuc_kiem=f"{het}*58.5",
        ghi_chu="Tỉ lệ 1:1 nên chất thiếu quyết định lượng muối",
    )


def c17(r):
    n = r.choice([0.1, 0.2])
    m_este = n * 88
    return dict(
        topic="este", level="VD",
        question=(f"Xà phòng hoá hoàn toàn {vn(m_este)} gam etyl axetat CH3COOC2H5 bằng dung dịch "
                  f"NaOH vừa đủ. Tính khối lượng muối CH3COONa thu được. "
                  f"Biết M(CH3COOC2H5) = 88, M(CH3COONa) = 82 g/mol."),
        answer_value=n * 82, answer_unit="gam",
        bieu_thuc_kiem=f"{m_este}/88*82",
        ghi_chu="CH3COOC2H5 + NaOH -> CH3COONa + C2H5OH, tỉ lệ 1:1",
    )


def c18(r):
    i, t = r.choice([5, 2]), r.choice([1930, 9650])
    return dict(
        topic="dien_phan", level="VD",
        question=(f"Điện phân dung dịch CuSO4 với cường độ dòng điện {i} A trong {t} giây. "
                  f"Tính khối lượng Cu bám ở catot. Biết Cu = 64, F = 96500 C/mol."),
        answer_value=64 * i * t / (2 * 96500), answer_unit="gam",
        bieu_thuc_kiem=f"64*{i}*{t}/(2*96500)",
        ghi_chu="Faraday: m = A*I*t/(n*F), Cu2+ nhận 2 electron nên n = 2",
    )


def c19(r):
    m_kl, m_oxit = r.choice([10, 20]), None
    m_oxit = m_kl + r.choice([4, 8])
    return dict(
        topic="bao_toan_khoi_luong", level="VD",
        question=(f"Đốt cháy hoàn toàn {m_kl} gam hỗn hợp kim loại trong khí O2 thu được "
                  f"{m_oxit} gam hỗn hợp oxit. Tính thể tích khí O2 đã phản ứng ở điều kiện tiêu chuẩn."),
        answer_value=(m_oxit - m_kl) / 32 * 22.4, answer_unit="lit",
        bieu_thuc_kiem=f"({m_oxit} - {m_kl})/32*22.4",
        ghi_chu="Bảo toàn khối lượng: m(O2) = m(oxit) - m(kim loại)",
    )


def c20(r):
    n = r.choice([0.1, 0.2])
    m = n * 56
    return dict(
        topic="kim_loai_axit", level="VD",
        question=(f"Hoà tan hoàn toàn {vn(m)} gam Fe vào dung dịch H2SO4 loãng dư. Tính thể tích "
                  f"khí H2 thu được ở điều kiện tiêu chuẩn. Biết Fe = 56."),
        answer_value=n * 22.4, answer_unit="lit",
        bieu_thuc_kiem=f"{m}/56*22.4",
        ghi_chu="Fe + H2SO4 loãng -> FeSO4 + H2, tỉ lệ 1:1 (Fe lên hoá trị II)",
    )


def c21(r):
    m = r.choice([10, 25])
    return dict(
        topic="muoi_cacbonat", level="VD",
        question=(f"Cho {m} gam CaCO3 tác dụng hoàn toàn với dung dịch HCl dư. Tính thể tích khí CO2 "
                  f"thu được ở điều kiện tiêu chuẩn. Biết M(CaCO3) = 100 g/mol."),
        answer_value=m / 100 * 22.4, answer_unit="lit",
        bieu_thuc_kiem=f"{m}/100*22.4",
        ghi_chu="CaCO3 + 2HCl -> CaCl2 + H2O + CO2, tỉ lệ 1:1",
    )


def c22(r):
    m_hh, v_h2 = r.choice([12, 20]), r.choice([2.24, 4.48])
    n_fe = v_h2 / 22.4
    return dict(
        topic="hon_hop_kim_loai", level="VDC",
        question=(f"Cho {m_hh} gam hỗn hợp Fe và Cu tác dụng với dung dịch HCl dư, thu được "
                  f"{vn(v_h2)} lít khí H2 ở điều kiện tiêu chuẩn. Tính phần trăm khối lượng của Fe "
                  f"trong hỗn hợp. Biết Fe = 56."),
        answer_value=n_fe * 56 / m_hh * 100, answer_unit="%",
        bieu_thuc_kiem=f"{v_h2}/22.4*56/{m_hh}*100",
        ghi_chu="Cu KHÔNG tác dụng HCl, chỉ Fe sinh H2 nên n(Fe) = n(H2)",
    )


def c23(r):
    so_c, so_h = r.choice([(2, 6), (3, 8), (1, 4)])
    n_x = 0.1
    n_co2, n_h2o = n_x * so_c, n_x * so_h / 2
    return dict(
        topic="tim_cong_thuc_phan_tu", level="VDC",
        question=(f"Đốt cháy hoàn toàn {vn(n_x)} mol hiđrocacbon X thu được {vn(n_co2)} mol CO2 và "
                  f"{vn(n_h2o)} mol H2O. Tính khối lượng mol của X. Biết C = 12, H = 1."),
        answer_value=so_c * 12 + so_h * 1, answer_unit="g/mol",
        bieu_thuc_kiem=f"{n_co2}/{n_x}*12 + {n_h2o}*2/{n_x}*1",
        ghi_chu="Số C = n(CO2)/n(X); số H = 2*n(H2O)/n(X)",
    )


def c24(r):
    import math
    v_hcl, c_hcl = r.choice([200, 100]), 0.5
    v_naoh, c_naoh = r.choice([300, 400]), 0.5
    n_du = v_naoh / 1000 * c_naoh - v_hcl / 1000 * c_hcl
    v_tong = (v_hcl + v_naoh) / 1000
    oh = n_du / v_tong
    return dict(
        topic="ph", level="VDC",
        question=(f"Trộn {v_hcl} ml dung dịch HCl {vn(c_hcl)}M với {v_naoh} ml dung dịch NaOH "
                  f"{vn(c_naoh)}M. Tính pH của dung dịch thu được."),
        answer_value=14 + math.log10(oh),
        bieu_thuc_kiem=f"14 + log({oh})/log(10)",
        ghi_chu="NaOH dư, tính [OH-] rồi pH = 14 - pOH",
    )


def c25(r):
    n_caco3 = r.choice([0.1, 0.2])
    n_hcl_du = r.choice([0.5, 0.6])
    m_muoi = n_caco3 * 111
    return dict(
        topic="muoi_cacbonat", level="VDC",
        question=(f"Cho {vn(n_caco3 * 100)} gam CaCO3 vào dung dịch chứa {vn(n_hcl_du)} mol HCl. "
                  f"Sau phản ứng hoàn toàn, tính khối lượng muối CaCl2 thu được. "
                  f"Biết M(CaCO3) = 100, M(CaCl2) = 111 g/mol."),
        answer_value=m_muoi, answer_unit="gam",
        bieu_thuc_kiem=f"{n_caco3}*111",
        ghi_chu=f"CaCO3 + 2HCl -> CaCl2 + H2O + CO2. Cần {n_caco3 * 2} mol HCl, có {n_hcl_du} nên HCl dư, CaCO3 hết",
    )


# ---------------------------------------------------------------------------

MAU: dict[str, list[Callable]] = {
    "math": [m01, m02, m03, m04, m05, m06, m07, m08, m09, m10, m11, m12, m13,
             m14, m15, m16, m17, m18, m19, m20, m21, m22, m23, m24, m25],
    "physics": [p01, p02, p03, p04, p05, p06, p07, p08, p09, p10, p11, p12, p13,
                p14, p15, p16, p17, p18, p19, p20, p21, p22, p23, p24, p25],
    "chemistry": [c01, c02, c03, c04, c05, c06, c07, c08, c09, c10, c11, c12, c13,
                  c14, c15, c16, c17, c18, c19, c20, c21, c22, c23, c24, c25],
}

TIEN_TO = {"math": "math", "physics": "phys", "chemistry": "chem"}

COT = ["id", "subject", "topic", "level", "question_type", "question", "choices",
       "answer_value", "answer_unit", "answer_expr", "answer_choice",
       "bieu_thuc_kiem", "nguon", "ghi_chu"]


def sinh_mon(
    mon: str, so_bai: int, r: random.Random, tranh: set[str] | None = None
) -> list[dict]:
    """Sinh đủ số bài cho một môn, đi vòng qua các mẫu để trải đều dạng bài.

    `tranh` là tập câu hỏi KHÔNG được sinh lại — dùng khi dựng bộ giữ riêng, để nó
    rời hẳn bộ đã dùng để sửa code. Pool tham số khá hẹp nên chỉ đổi seed thôi vẫn
    trùng tới 41%; phải loại tường minh mới sạch.
    """
    ra: list[dict] = []
    da_co: set[str] = set(tranh or ())
    mau = MAU[mon]
    vong = 0
    while len(ra) < so_bai and vong < 60:
        for f in mau:
            if len(ra) >= so_bai:
                break
            for _ in range(12):          # thử lại vài lần nếu trùng đề
                d = f(r)
                if d and d["question"] not in da_co:
                    break
            else:
                continue
            if not d or d["question"] in da_co:
                continue
            da_co.add(d["question"])
            stt = len(ra) + 1
            ra.append({
                "id": f"{TIEN_TO[mon]}_{d['level'].lower()}_{stt:03d}",
                "subject": mon,
                "topic": d["topic"],
                "level": d["level"],
                "question_type": d.get("question_type", "numeric"),
                "question": d["question"],
                "choices": "",
                "answer_value": "" if d.get("answer_value") is None else f"{d['answer_value']:.6g}",
                "answer_unit": d.get("answer_unit", ""),
                "answer_expr": d.get("answer_expr", ""),
                "answer_choice": "",
                "bieu_thuc_kiem": d["bieu_thuc_kiem"],
                "nguon": "tu_soan",
                "ghi_chu": d.get("ghi_chu", ""),
            })
        vong += 1
    return ra


def main(seed: int = 20260805, ra: Path | None = None, tranh_file: str | None = None) -> int:
    """Sinh bộ đề. Seed cố định để bộ đề tái lập được.

    Đổi seed là có một bộ đề MỚI HOÀN TOÀN: cùng các dạng bài, khác toàn bộ số
    liệu. Dùng để dựng bộ GIỮ RIÊNG (held-out).

    Vì sao cần: mọi sửa đổi rút ra từ việc phân tích lỗi trên một bộ đề đều có nguy
    cơ may đo vừa khít đúng bộ đó. Chương trình không học được bộ đề — nó không có
    cache, không đọc database, trọng số đóng băng — nhưng NGƯỜI SỬA CODE thì có.
    Đo lại trên bộ giữ riêng mới là phép thử sạch cho bản sửa.
    """
    r = random.Random(seed)
    global RA
    if ra is not None:
        RA = ra

    tranh: set[str] = set()
    if tranh_file:
        with Path(tranh_file).open(encoding="utf-8-sig", newline="") as f:
            tranh = {(d.get("question") or "").strip() for d in csv.DictReader(f)}
        print(f"Tránh trùng với {len(tranh)} câu trong {tranh_file}")

    tat_ca: list[dict] = []
    for mon in ("math", "physics", "chemistry"):
        bai = sinh_mon(mon, SO_BAI_MOI_MON, r, tranh)
        tat_ca += bai
        theo_muc: dict[str, int] = {}
        for b in bai:
            theo_muc[b["level"]] = theo_muc.get(b["level"], 0) + 1
        print(f"{mon:<10} {len(bai):3} bài  " +
              "  ".join(f"{k} {v}" for k, v in sorted(theo_muc.items())))

    RA.parent.mkdir(parents=True, exist_ok=True)
    with RA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COT)
        w.writeheader()
        w.writerows(tat_ca)

    print(f"\nTổng {len(tat_ca)} bài -> {RA}")
    print("Chạy `python eval/kiem_de_chuan.py` để tự kiểm đáp án trước khi dùng.")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Sinh bộ đề chuẩn")
    ap.add_argument("--seed", type=int, default=20260805, help="đổi seed để có bộ đề mới")
    ap.add_argument("--ra", help="đường dẫn file CSV đầu ra")
    ap.add_argument("--tranh", help="CSV chứa các câu KHÔNG được sinh lại (dựng bộ giữ riêng)")
    a = ap.parse_args()
    raise SystemExit(main(a.seed, Path(a.ra) if a.ra else None, a.tranh))
