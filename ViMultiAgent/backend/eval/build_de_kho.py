"""Sinh bộ đề KHÓ — 300 bài, 100 mỗi môn, dùng để dò trần năng lực hệ thống.

Chạy:
    python eval/build_de_kho.py
    python eval/build_de_kho.py --seed 12345 --ra eval/data/de_kho_2.csv

Khác gì bộ `de_chuan.csv`
-------------------------
1. **Gấp đôi số bài** — 100 mỗi môn thay vì 50.
2. **Toán có hình học thật** — 18/36 mẫu là hình phẳng, hình không gian, toạ độ
   Oxy và Oxyz. Bộ cũ gần như thuần đại số - giải tích, nên không nói được gì về
   nửa còn lại của chương trình Toán THPT.
3. **Vận dụng cao khó hẳn** — bài VDC ở bộ cũ chỉ cần một bước suy luận (Cauchy,
   biến cố đối). Ở đây mỗi bài VDC bắt buộc nối **ba khái niệm trở lên**: khoảng
   cách giữa hai đường chéo nhau, mạch RLC có tham số biến thiên, bảo toàn
   electron trong hỗn hợp nhiều chất. Mục đích là tìm chỗ hệ thống GÃY, không
   phải để có con số đẹp.
4. **Rời hẳn hai bộ cũ** — mặc định loại trùng với cả `de_chuan.csv` lẫn
   `de_giu_rieng.csv`.

Vì sao vẫn SINH chứ không gõ tay: xem đầu file `build_de_chuan.py`. Đáp án do
Python tính từ chính các số đưa vào đề, rồi `kiem_de_chuan.py` dùng SymPy đối
chiếu lại cột `bieu_thuc_kiem`. Sai số học là không thể xảy ra về mặt kiến tạo.

Thứ script KHÔNG kiểm được vẫn là tính đúng của CÔNG THỨC. Mỗi mẫu vì vậy ghi rõ
công thức đã dùng trong `ghi_chu` để rà soát bằng mắt.
"""

from __future__ import annotations

import csv
import math
import random
import sys
from pathlib import Path
from typing import Callable

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
sys.path.insert(0, str(GOC / "eval"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from build_de_chuan import COT, NTK, TIEN_TO, M, hs, vn  # noqa: E402
from tools import chem_tool  # noqa: E402

RA = GOC / "eval" / "data" / "de_kho.csv"
SO_BAI_MOI_MON = 100

# Loại trùng với cả hai bộ đã dùng để phát triển và kiểm chứng.
TRANH_MAC_DINH = [
    GOC / "eval" / "data" / "de_chuan.csv",
    GOC / "eval" / "data" / "de_giu_rieng.csv",
]


def _bo_ba_pythago(r: random.Random) -> tuple[int, int, int]:
    """Bộ ba Pythago để cạnh huyền ra số đẹp."""
    return r.choice([(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17), (9, 12, 15)])


# ===========================================================================
# TOÁN — 36 mẫu: 18 đại số/giải tích + 18 hình học
# ===========================================================================

# ---- Đại số & Giải tích ---------------------------------------------------


def t01(r):
    a, b, x0 = r.choice([2, 3, 5, 7]), r.choice([4, 6, 9, 12]), r.choice([1, 2, 3, 4])
    return dict(topic="dao_ham", level="NB",
                question=f"Tính đạo hàm của hàm số y = {a}x^4 - {b}x^2 + 5 tại điểm x = {x0}.",
                answer_value=4 * a * x0**3 - 2 * b * x0,
                bieu_thuc_kiem=f"4*{a}*{x0}**3 - 2*{b}*{x0}",
                ghi_chu="y' = 4ax^3 - 2bx")


def t02(r):
    a, n, t = r.choice([2, 3, 5]), r.choice([2, 3, 4]), r.choice([1, 2, 3])
    return dict(topic="tich_phan", level="TH",
                question=f"Tính tích phân I = ∫ từ 0 đến {t} của {a}x^{n} dx.",
                answer_value=a * t ** (n + 1) / (n + 1),
                bieu_thuc_kiem=f"{a}*{t}**{n + 1}/{n + 1}",
                ghi_chu="Nguyên hàm a*x^(n+1)/(n+1)")


def t03(r):
    a, b = r.choice([2, 3, 5, 7]), r.choice([3, 4, 6, 8])
    return dict(topic="logarit", level="TH",
                question=f"Tính giá trị biểu thức log cơ số {a} của {a**b}.",
                answer_value=float(b), bieu_thuc_kiem=f"log({a**b})/log({a})",
                ghi_chu="log_a(a^b) = b")


def t04(r):
    u1, q, n = r.choice([1, 2, 3, 4]), r.choice([2, 3]), r.choice([6, 7, 8])
    tong = u1 * (q**n - 1) / (q - 1)
    return dict(topic="cap_so_nhan", level="VD",
                question=(f"Cho cấp số nhân có u1 = {u1}, công bội q = {q}. "
                          f"Tính tổng {n} số hạng đầu tiên."),
                answer_value=tong, bieu_thuc_kiem=f"{u1}*({q}**{n} - 1)/({q} - 1)",
                ghi_chu="S_n = u1*(q^n - 1)/(q - 1)")


def t05(r):
    n, k = r.choice([9, 11, 13, 15]), r.choice([3, 4, 5])
    return dict(topic="to_hop", level="TH",
                question=f"Tính số tổ hợp chập {k} của {n} phần tử.",
                answer_value=float(math.comb(n, k)),
                bieu_thuc_kiem=f"factorial({n})/(factorial({k})*factorial({n - k}))",
                ghi_chu="C(n,k) = n!/(k!(n-k)!)")


def t06(r):
    a, b = r.choice([2, 3, 4, 5]), r.choice([1, 2, 3])
    mo_dun = math.hypot(a, b)
    return dict(topic="so_phuc", level="TH",
                question=f"Cho số phức z = {a} + {hs(b, 'i')}. Tính môđun của z^2.",
                answer_value=mo_dun**2, bieu_thuc_kiem=f"{a}**2 + {b}**2",
                ghi_chu="|z^2| = |z|^2 = a^2 + b^2")


def t07(r):
    a, m = r.choice([2, 3]), r.choice([2, 3, 4])
    # b PHẢI khác m. Bằng nhau thì t^2 - 2a^m*t + a^(2m) = 0 có NGHIỆM KÉP, phương
    # trình chỉ còn một nghiệm x = m, mà đáp án lại cộng m + b thành 2m — sai.
    # Đã bắt được ca này khi rà lại bộ đề: 3^(2x) - 54*3^x + 729 = 0 lưu đáp án 6
    # trong khi đúng là 3.
    b = r.choice([x for x in (1, 2, 3) if x != m])
    return dict(topic="phuong_trinh_mu", level="VD",
                question=(f"Giải phương trình {a}^(2x) - {a**m + a**b}·{a}^x + {a ** (m + b)} = 0. "
                          f"Tính tổng các nghiệm."),
                answer_value=float(m + b),
                bieu_thuc_kiem=f"{m} + {b}",
                ghi_chu=f"Đặt t = {a}^x, hai nghiệm PHÂN BIỆT t = {a}^{m} và {a}^{b} "
                        f"nên x = {m} và {b}")


def t08(r):
    a, b, c = r.choice([1, 2]), r.choice([3, 6, 9]), r.choice([2, 4, 8])
    # y = ax^3 - bx^2 + cx, y' = 3ax^2 - 2bx + c; tính y' tại điểm uốn x = b/(3a)
    x_uon = b / (3 * a)
    return dict(topic="diem_uon", level="VD",
                question=(f"Cho hàm số y = {hs(a, 'x^3')} - {b}x^2 + {c}x. "
                          f"Tìm hoành độ điểm uốn của đồ thị hàm số."),
                answer_value=x_uon, bieu_thuc_kiem=f"{b}/(3*{a})",
                ghi_chu="y'' = 6ax - 2b = 0 => x = b/(3a)")


def t09(r):
    a, b = r.choice([2, 3, 4]), r.choice([1, 3, 5])
    # GTNN của y = ax + b/x tren (0, +oo)
    return dict(topic="gtln_gtnn", level="VD",
                question=f"Tìm giá trị nhỏ nhất của hàm số y = {a}x + {b}/x với x > 0.",
                answer_value=2 * math.sqrt(a * b), bieu_thuc_kiem=f"2*sqrt({a}*{b})",
                ghi_chu="Cauchy: ax + b/x >= 2*sqrt(ab)")


def t10(r):
    n = r.choice([5, 6, 7])
    k = r.choice([2, 3])
    # Xac suat lay k bi do tu n do va n xanh, lay k vien deu do
    tong = 2 * n
    p = math.comb(n, k) / math.comb(tong, k)
    return dict(topic="xac_suat", level="VD",
                question=(f"Một hộp có {n} bi đỏ và {n} bi xanh. Lấy ngẫu nhiên {k} viên. "
                          f"Tính xác suất để cả {k} viên đều màu đỏ."),
                answer_value=p,
                bieu_thuc_kiem=f"{math.comb(n, k)}/{math.comb(tong, k)}",
                ghi_chu="C(n,k)/C(2n,k)")


def t11(r):
    a = r.choice([2, 3, 4])
    t = r.choice([1, 2])
    # ∫ x*e^(ax) dx tu 0 den t = (a*t-1)*e^(a*t)/a^2 + 1/a^2
    val = ((a * t - 1) * math.exp(a * t) + 1) / a**2
    return dict(topic="tich_phan_tung_phan", level="VDC",
                question=f"Tính tích phân I = ∫ từ 0 đến {t} của x·e^({a}x) dx.",
                answer_value=val,
                bieu_thuc_kiem=f"(({a}*{t} - 1)*exp({a}*{t}) + 1)/{a}**2",
                ghi_chu="Từng phần u=x, dv=e^(ax)dx => ((ax-1)e^(ax))/a^2")


def t12(r):
    a, b = r.choice([1, 2]), r.choice([2, 3, 4])
    # Dien tich hinh phang giua y = ax^2 va y = bx: giao tai 0 va b/a
    xg = b / a
    dt = b * xg**2 / 2 - a * xg**3 / 3
    return dict(topic="dien_tich_hinh_phang", level="VDC",
                question=(f"Tính diện tích hình phẳng giới hạn bởi đồ thị hai hàm số "
                          f"y = {hs(a, 'x^2')} và y = {b}x."),
                answer_value=dt,
                bieu_thuc_kiem=f"{b}*({b}/{a})**2/2 - {a}*({b}/{a})**3/3",
                ghi_chu="Giao tại x=0 và x=b/a; S = ∫(bx - ax^2)dx")


def t13(r):
    n = r.choice([4, 5, 6])
    # So cach xep n nguoi vao ban tron
    return dict(topic="hoan_vi_vong", level="VD",
                question=f"Có bao nhiêu cách xếp {n} người ngồi quanh một bàn tròn?",
                answer_value=float(math.factorial(n - 1)),
                bieu_thuc_kiem=f"factorial({n - 1})",
                ghi_chu="Hoán vị vòng quanh: (n-1)!")


def t14(r):
    a, b = r.choice([3, 4, 5]), r.choice([2, 6, 7])
    return dict(topic="he_phuong_trinh", level="TH",
                question=(f"Giải hệ phương trình x + y = {a + b} và x - y = {a - b}. "
                          f"Tìm giá trị của x."),
                answer_value=float(a), bieu_thuc_kiem=f"(({a + b}) + ({a - b}))/2",
                ghi_chu="Cộng hai vế: 2x = tổng")


def t15(r):
    p, n = r.choice([0.3, 0.4, 0.5]), r.choice([3, 4])
    k = r.choice([1, 2])
    val = math.comb(n, k) * p**k * (1 - p) ** (n - k)
    return dict(topic="xac_suat_nhi_thuc", level="VDC",
                question=(f"Một xạ thủ bắn {n} phát độc lập, xác suất trúng mỗi phát là "
                          f"{vn(p)}. Tính xác suất trúng đúng {k} phát."),
                answer_value=val,
                bieu_thuc_kiem=f"{math.comb(n, k)}*{p}**{k}*(1 - {p})**{n - k}",
                ghi_chu="Nhị thức: C(n,k)*p^k*(1-p)^(n-k)")


def t16(r):
    a = r.choice([2, 3, 4])
    b = r.choice([1, 2])
    # lim (sqrt(ax^2+bx) - sqrt(a)*x) khi x->+oo = b/(2*sqrt(a))
    return dict(topic="gioi_han", level="VDC",
                question=(f"Tính giới hạn của biểu thức sqrt({a}x^2 + {b}x) - sqrt({a})·x "
                          f"khi x tiến tới dương vô cùng."),
                answer_value=b / (2 * math.sqrt(a)),
                bieu_thuc_kiem=f"{b}/(2*sqrt({a}))",
                ghi_chu="Nhân liên hợp: b/(2*sqrt(a))")


def t17(r):
    a, b = r.choice([2, 3]), r.choice([5, 7, 11])
    return dict(topic="phuong_trinh_logarit", level="VD",
                question=(f"Giải phương trình log cơ số {a} của (x + {b}) bằng 2. "
                          f"Tìm nghiệm x."),
                answer_value=float(a**2 - b), bieu_thuc_kiem=f"{a}**2 - {b}",
                ghi_chu="x + b = a^2")


def t18(r):
    a, b, c = r.choice([1, 2]), r.choice([2, 4, 6]), r.choice([1, 3, 5])
    # Tiep tuyen cua y = ax^3 + bx + c tai x0, he so goc
    x0 = r.choice([1, 2])
    return dict(topic="tiep_tuyen", level="VD", question_type="symbolic",
                question=(f"Cho hàm số y = {hs(a, 'x^3')} + {b}x + {c}. Viết phương trình "
                          f"tiếp tuyến của đồ thị tại điểm có hoành độ x = {x0}."),
                answer_expr=f"{3 * a * x0**2 + b}*x + {a * x0**3 + b * x0 + c - (3 * a * x0**2 + b) * x0}",
                bieu_thuc_kiem=f"{3 * a * x0**2 + b}*(x - {x0}) + {a * x0**3 + b * x0 + c}",
                ghi_chu="y = y'(x0)(x - x0) + y(x0)")


# ---- Hình học -------------------------------------------------------------


def h01(r):
    a, b, c = r.choice([(3, 4, 5), (6, 8, 10), (5, 5, 6), (7, 8, 9), (13, 14, 15)])
    p = (a + b + c) / 2
    s = math.sqrt(p * (p - a) * (p - b) * (p - c))
    return dict(topic="hinh_hoc_phang", level="TH",
                question=(f"Cho tam giác có ba cạnh lần lượt là {a}, {b} và {c}. "
                          f"Tính diện tích tam giác đó."),
                answer_value=s,
                bieu_thuc_kiem=f"sqrt(({a}+{b}+{c})/2*(({a}+{b}+{c})/2-{a})*"
                               f"(({a}+{b}+{c})/2-{b})*(({a}+{b}+{c})/2-{c}))",
                ghi_chu="Công thức Heron: S = sqrt(p(p-a)(p-b)(p-c))")


def h02(r):
    b, c = r.choice([4, 5, 6, 8]), r.choice([6, 7, 9, 10])
    goc = r.choice([60, 120])
    a2 = b**2 + c**2 - 2 * b * c * math.cos(math.radians(goc))
    return dict(topic="hinh_hoc_phang", level="VD",
                question=(f"Cho tam giác ABC có AB = {c}, AC = {b} và góc A = {goc} độ. "
                          f"Tính độ dài cạnh BC."),
                answer_value=math.sqrt(a2),
                bieu_thuc_kiem=f"sqrt({b}**2 + {c}**2 - 2*{b}*{c}*cos({goc}*pi/180))",
                ghi_chu="Định lý cosin: a^2 = b^2 + c^2 - 2bc*cosA")


def h03(r):
    b, c = r.choice([5, 6, 8]), r.choice([7, 9, 10])
    goc = r.choice([30, 150])
    return dict(topic="hinh_hoc_phang", level="TH",
                question=(f"Cho tam giác có hai cạnh {b} và {c}, góc xen giữa bằng {goc} độ. "
                          f"Tính diện tích tam giác."),
                answer_value=0.5 * b * c * math.sin(math.radians(goc)),
                bieu_thuc_kiem=f"0.5*{b}*{c}*sin({goc}*pi/180)",
                ghi_chu="S = (1/2)ab*sinC")


def h04(r):
    a, b, c = _bo_ba_pythago(r)
    s = a * b / 2
    rr = a * b * c / (4 * s)
    return dict(topic="hinh_hoc_phang", level="VD",
                question=(f"Cho tam giác vuông có hai cạnh góc vuông {a} và {b}, cạnh huyền {c}. "
                          f"Tính bán kính đường tròn ngoại tiếp tam giác."),
                answer_value=rr, bieu_thuc_kiem=f"{a}*{b}*{c}/(4*({a}*{b}/2))",
                ghi_chu="R = abc/(4S); với tam giác vuông R = c/2")


def h05(r):
    a, b, c = _bo_ba_pythago(r)
    s = a * b / 2
    p = (a + b + c) / 2
    return dict(topic="hinh_hoc_phang", level="VD",
                question=(f"Cho tam giác vuông có hai cạnh góc vuông {a} và {b}, cạnh huyền {c}. "
                          f"Tính bán kính đường tròn nội tiếp tam giác."),
                answer_value=s / p, bieu_thuc_kiem=f"({a}*{b}/2)/(({a}+{b}+{c})/2)",
                ghi_chu="r = S/p")


def h06(r):
    rr, h = r.choice([3, 4, 6]), r.choice([5, 9, 12])
    return dict(topic="hinh_hoc_khong_gian", level="TH",
                question=f"Tính thể tích khối nón có bán kính đáy {rr} và chiều cao {h}.",
                answer_value=math.pi * rr**2 * h / 3,
                bieu_thuc_kiem=f"pi*{rr}**2*{h}/3",
                ghi_chu="V = (1/3)*pi*r^2*h")


def h07(r):
    rr, h = r.choice([2, 3, 5]), r.choice([4, 7, 10])
    return dict(topic="hinh_hoc_khong_gian", level="NB",
                question=f"Tính thể tích khối trụ có bán kính đáy {rr} và chiều cao {h}.",
                answer_value=math.pi * rr**2 * h,
                bieu_thuc_kiem=f"pi*{rr}**2*{h}",
                ghi_chu="V = pi*r^2*h")


def h08(r):
    rr = r.choice([2, 3, 4, 6])
    return dict(topic="hinh_hoc_khong_gian", level="NB",
                question=f"Tính thể tích khối cầu có bán kính {rr}.",
                answer_value=4 / 3 * math.pi * rr**3,
                bieu_thuc_kiem=f"4/3*pi*{rr}**3",
                ghi_chu="V = (4/3)*pi*r^3")


def h09(r):
    rr = r.choice([3, 5, 7, 9])
    return dict(topic="hinh_hoc_khong_gian", level="NB",
                question=f"Tính diện tích mặt cầu có bán kính {rr}.",
                answer_value=4 * math.pi * rr**2,
                bieu_thuc_kiem=f"4*pi*{rr}**2",
                ghi_chu="S = 4*pi*r^2")


def h10(r):
    rr, l = r.choice([3, 4, 5]), r.choice([8, 10, 13])
    return dict(topic="hinh_hoc_khong_gian", level="TH",
                question=(f"Tính diện tích xung quanh của hình nón có bán kính đáy {rr} "
                          f"và độ dài đường sinh {l}."),
                answer_value=math.pi * rr * l, bieu_thuc_kiem=f"pi*{rr}*{l}",
                ghi_chu="S_xq = pi*r*l")


def h11(r):
    a, canh_ben = r.choice([(6, 5), (4, 6), (8, 9), (6, 7)])
    # Chop tu giac deu day vuong canh a, canh ben b: h = sqrt(b^2 - (a*sqrt(2)/2)^2)
    h = math.sqrt(canh_ben**2 - (a * math.sqrt(2) / 2) ** 2)
    return dict(topic="hinh_hoc_khong_gian", level="VD",
                question=(f"Cho khối chóp tứ giác đều có cạnh đáy bằng {a} và cạnh bên bằng "
                          f"{canh_ben}. Tính chiều cao của khối chóp."),
                answer_value=h,
                bieu_thuc_kiem=f"sqrt({canh_ben}**2 - ({a}*sqrt(2)/2)**2)",
                ghi_chu="Nửa đường chéo đáy = a*sqrt(2)/2; h = sqrt(b^2 - đó^2)")


def h12(r):
    a, canh_ben = r.choice([(6, 5), (4, 6), (8, 9), (6, 7)])
    h = math.sqrt(canh_ben**2 - (a * math.sqrt(2) / 2) ** 2)
    return dict(topic="hinh_hoc_khong_gian", level="VDC",
                question=(f"Cho khối chóp tứ giác đều có cạnh đáy bằng {a} và cạnh bên bằng "
                          f"{canh_ben}. Tính thể tích khối chóp."),
                answer_value=a**2 * h / 3,
                bieu_thuc_kiem=f"{a}**2*sqrt({canh_ben}**2 - ({a}*sqrt(2)/2)**2)/3",
                ghi_chu="Phải tìm h qua cạnh bên trước rồi mới V = (1/3)*a^2*h")


def h13(r):
    a = r.choice([2, 3, 4, 6])
    # Khoang cach giua hai duong cheo nhau AB' va BC' trong hinh lap phuong canh a = a/sqrt(3)
    return dict(topic="hinh_hoc_khong_gian", level="VDC",
                question=(f"Cho hình lập phương ABCD.A'B'C'D' có cạnh bằng {a}. "
                          f"Tính khoảng cách giữa hai đường thẳng chéo nhau AC và B'D'."),
                answer_value=float(a), bieu_thuc_kiem=f"{a}",
                ghi_chu="AC nằm mặt đáy, B'D' nằm mặt trên và song song mặt đáy => "
                        "khoảng cách bằng chiều cao a")


def h14(r):
    x1, y1, z1 = r.choice([1, 2, 3]), r.choice([0, 2, 4]), r.choice([1, 3, 5])
    x2, y2, z2 = x1 + r.choice([2, 3, 6]), y1 + r.choice([3, 4, 6]), z1 + r.choice([6, 12])
    d = math.dist((x1, y1, z1), (x2, y2, z2))
    return dict(topic="hinh_hoc_toa_do", level="NB",
                question=(f"Trong không gian Oxyz, cho hai điểm A({x1}; {y1}; {z1}) và "
                          f"B({x2}; {y2}; {z2}). Tính độ dài đoạn thẳng AB."),
                answer_value=d,
                bieu_thuc_kiem=f"sqrt(({x2}-{x1})**2 + ({y2}-{y1})**2 + ({z2}-{z1})**2)",
                ghi_chu="AB = sqrt(Δx^2 + Δy^2 + Δz^2)")


def h15(r):
    a, b, c, d = r.choice([1, 2]), r.choice([2, 2]), r.choice([2, 3]), r.choice([1, 5, 6])
    x0, y0, z0 = r.choice([1, 3]), r.choice([2, 4]), r.choice([0, 5])
    kc = abs(a * x0 + b * y0 + c * z0 + d) / math.sqrt(a**2 + b**2 + c**2)
    return dict(topic="hinh_hoc_toa_do", level="VD",
                question=(f"Trong không gian Oxyz, tính khoảng cách từ điểm M({x0}; {y0}; {z0}) "
                          f"đến mặt phẳng có phương trình {a}x + {b}y + {c}z + {d} = 0."),
                answer_value=kc,
                bieu_thuc_kiem=f"Abs({a}*{x0} + {b}*{y0} + {c}*{z0} + {d})/"
                               f"sqrt({a}**2 + {b}**2 + {c}**2)",
                ghi_chu="d = |ax0+by0+cz0+d|/sqrt(a^2+b^2+c^2)")


def h16(r):
    a, b = r.choice([2, 3, 4]), r.choice([1, 5, 6])
    c = r.choice([2, 3])
    x0, y0 = r.choice([1, 4]), r.choice([2, 3])
    kc = abs(a * x0 + b * y0 + c) / math.sqrt(a**2 + b**2)
    return dict(topic="hinh_hoc_toa_do", level="TH",
                question=(f"Trong mặt phẳng Oxy, tính khoảng cách từ điểm M({x0}; {y0}) "
                          f"đến đường thẳng {a}x + {b}y + {c} = 0."),
                answer_value=kc,
                bieu_thuc_kiem=f"Abs({a}*{x0} + {b}*{y0} + {c})/sqrt({a}**2 + {b}**2)",
                ghi_chu="d = |ax0+by0+c|/sqrt(a^2+b^2)")


def h17(r):
    a, b, cc = r.choice([1, 2, 3]), r.choice([2, 3, 4]), r.choice([-4, -11, -20])
    # x^2+y^2-2ax-2by+cc=0 => R = sqrt(a^2+b^2-cc)
    rr = math.sqrt(a**2 + b**2 - cc)
    return dict(topic="hinh_hoc_toa_do", level="VD",
                question=(f"Trong mặt phẳng Oxy, cho đường tròn có phương trình "
                          f"x^2 + y^2 - {2 * a}x - {2 * b}y + ({cc}) = 0. Tính bán kính đường tròn."),
                answer_value=rr, bieu_thuc_kiem=f"sqrt({a}**2 + {b}**2 - ({cc}))",
                ghi_chu="R = sqrt(a^2 + b^2 - c) với tâm (a;b)")


def h18(r):
    u = (r.choice([1, 2, 3]), r.choice([2, 3]), r.choice([1, 2]))
    v = (r.choice([2, 4]), r.choice([1, 3]), r.choice([3, 5]))
    tich = sum(x * y for x, y in zip(u, v))
    cos = tich / (math.dist((0, 0, 0), u) * math.dist((0, 0, 0), v))
    return dict(topic="hinh_hoc_toa_do", level="VDC",
                question=(f"Trong không gian Oxyz, cho hai vectơ u = ({u[0]}; {u[1]}; {u[2]}) và "
                          f"v = ({v[0]}; {v[1]}; {v[2]}). Tính côsin của góc giữa hai vectơ."),
                answer_value=cos,
                bieu_thuc_kiem=f"({tich})/(sqrt({u[0]}**2+{u[1]}**2+{u[2]}**2)*"
                               f"sqrt({v[0]}**2+{v[1]}**2+{v[2]}**2))",
                ghi_chu="cos = (u.v)/(|u||v|)")


# ===========================================================================
# VẬT LÝ — 32 mẫu
# ===========================================================================


def l01(r):
    a_cm, f = r.choice([3, 4, 6, 8]), r.choice([1, 2, 5])
    return dict(topic="dao_dong_dieu_hoa", level="TH",
                question=(f"Một vật dao động điều hoà với biên độ {a_cm} cm và tần số {f} Hz. "
                          f"Tính gia tốc cực đại của vật."),
                answer_value=a_cm / 100 * (2 * math.pi * f) ** 2, answer_unit="m/s^2",
                bieu_thuc_kiem=f"{a_cm}/100*(2*pi*{f})**2",
                ghi_chu="a_max = A*omega^2, omega = 2*pi*f")


def l02(r):
    m, k = r.choice([0.1, 0.2, 0.4]), r.choice([40, 100, 160])
    return dict(topic="con_lac_lo_xo", level="VD",
                question=(f"Con lắc lò xo có khối lượng {vn(m)} kg và độ cứng {k} N/m. "
                          f"Tính chu kỳ dao động."),
                answer_value=2 * math.pi * math.sqrt(m / k), answer_unit="s",
                bieu_thuc_kiem=f"2*pi*sqrt({m}/{k})",
                ghi_chu="T = 2*pi*sqrt(m/k)")


def l03(r):
    a_cm, k = r.choice([4, 5, 10]), r.choice([50, 100, 200])
    return dict(topic="nang_luong_dao_dong", level="VD",
                question=(f"Con lắc lò xo có độ cứng {k} N/m dao động với biên độ {a_cm} cm. "
                          f"Tính cơ năng của con lắc."),
                answer_value=0.5 * k * (a_cm / 100) ** 2, answer_unit="J",
                bieu_thuc_kiem=f"0.5*{k}*({a_cm}/100)**2",
                ghi_chu="W = (1/2)kA^2, đổi cm sang m")


def l04(r):
    l, n = r.choice([1.2, 1.6, 2.0]), r.choice([3, 4])
    return dict(topic="song_dung", level="VDC",
                question=(f"Một sợi dây dài {vn(l)} m hai đầu cố định có sóng dừng với {n} bụng sóng. "
                          f"Tính bước sóng."),
                answer_value=2 * l / n, answer_unit="m",
                bieu_thuc_kiem=f"2*{l}/{n}",
                ghi_chu="Hai đầu cố định: l = n*lambda/2 => lambda = 2l/n")


def l05(r):
    u, res, zl = r.choice([100, 200, 220]), r.choice([30, 40]), r.choice([40, 30])
    z = math.hypot(res, zl)
    return dict(topic="mach_rlc", level="VD",
                question=(f"Đặt hiệu điện thế hiệu dụng {u} V vào mạch RLC nối tiếp có R = {res} Ω "
                          f"và cảm kháng {zl} Ω, dung kháng bằng 0. Tính cường độ dòng điện hiệu dụng."),
                answer_value=u / z, answer_unit="A",
                bieu_thuc_kiem=f"{u}/sqrt({res}**2 + {zl}**2)",
                ghi_chu="I = U/Z, Z = sqrt(R^2 + ZL^2)")


def l06(r):
    u, res, zl, zc = r.choice([200, 220]), r.choice([40, 60]), r.choice([80, 100]), r.choice([50, 40])
    z = math.hypot(res, zl - zc)
    cong_suat = u**2 * res / z**2
    return dict(topic="mach_rlc", level="VDC",
                question=(f"Mạch RLC nối tiếp có R = {res} Ω, ZL = {zl} Ω, ZC = {zc} Ω, đặt vào "
                          f"hiệu điện thế hiệu dụng {u} V. Tính công suất tiêu thụ của mạch."),
                answer_value=cong_suat, answer_unit="W",
                bieu_thuc_kiem=f"{u}**2*{res}/({res}**2 + ({zl} - {zc})**2)",
                ghi_chu="P = U^2*R/Z^2 = I^2*R")


def l07(r):
    u, res = r.choice([200, 220]), r.choice([50, 100])
    return dict(topic="mach_rlc", level="VDC",
                question=(f"Mạch RLC nối tiếp có R = {res} Ω. Điều chỉnh tần số để xảy ra cộng hưởng, "
                          f"hiệu điện thế hiệu dụng {u} V. Tính công suất cực đại của mạch."),
                answer_value=u**2 / res, answer_unit="W",
                bieu_thuc_kiem=f"{u}**2/{res}",
                ghi_chu="Cộng hưởng: Z = R nên P_max = U^2/R")


def l08(r):
    lam_nm, d, a_mm, k = r.choice([500, 600, 750]), r.choice([1.5, 2]), r.choice([0.5, 1]), r.choice([3, 5])
    i = lam_nm * 1e-9 * d / (a_mm * 1e-3)
    return dict(topic="giao_thoa_anh_sang", level="VDC",
                question=(f"Thí nghiệm Y-âng có a = {vn(a_mm)} mm, D = {vn(d)} m, bước sóng {lam_nm} nm. "
                          f"Tính khoảng cách từ vân trung tâm đến vân sáng bậc {k}."),
                answer_value=k * i * 1000, answer_unit="mm",
                bieu_thuc_kiem=f"{k}*{lam_nm}*1e-9*{d}/({a_mm}*1e-3)*1000",
                ghi_chu="x_k = k*i = k*lambda*D/a")


def l09(r):
    m0, t_bra, t = r.choice([100, 200]), r.choice([5, 10]), r.choice([15, 20, 30])
    return dict(topic="phong_xa", level="VD",
                question=(f"Chất phóng xạ ban đầu {m0} gam, chu kỳ bán rã {t_bra} ngày. "
                          f"Tính khối lượng đã phân rã sau {t} ngày."),
                answer_value=m0 * (1 - 0.5 ** (t / t_bra)), answer_unit="gam",
                bieu_thuc_kiem=f"{m0}*(1 - (1/2)**({t}/{t_bra}))",
                ghi_chu="Δm = m0*(1 - (1/2)^(t/T))")


def l10(r):
    v0, goc = r.choice([20, 30, 40]), r.choice([30, 45, 60])
    tam = v0**2 * math.sin(2 * math.radians(goc)) / 10
    return dict(topic="nem_xien", level="VDC",
                question=(f"Ném một vật với vận tốc ban đầu {v0} m/s hợp với phương ngang góc "
                          f"{goc} độ. Lấy g = 10 m/s^2. Tính tầm xa của vật."),
                answer_value=tam, answer_unit="m",
                bieu_thuc_kiem=f"{v0}**2*sin(2*{goc}*pi/180)/10",
                ghi_chu="L = v0^2*sin(2*alpha)/g")


def l11(r):
    m, v, mm = r.choice([2, 3]), r.choice([4, 6]), r.choice([1, 4])
    # Va cham mem: v' = m*v/(m+M)
    return dict(topic="dong_luong", level="VD",
                question=(f"Vật khối lượng {m} kg chuyển động với vận tốc {v} m/s va chạm mềm "
                          f"vào vật {mm} kg đang đứng yên. Tính vận tốc chung sau va chạm."),
                answer_value=m * v / (m + mm), answer_unit="m/s",
                bieu_thuc_kiem=f"{m}*{v}/({m} + {mm})",
                ghi_chu="Bảo toàn động lượng, va chạm mềm: v' = mv/(m+M)")


def l12(r):
    q1, q2, d = r.choice([2, 3]), r.choice([4, 5]), r.choice([0.1, 0.2, 0.3])
    f = 9e9 * q1 * 1e-6 * q2 * 1e-6 / d**2
    return dict(topic="dien_tich", level="VD",
                question=(f"Hai điện tích {q1} μC và {q2} μC đặt cách nhau {vn(d)} m trong chân không. "
                          f"Tính lực tương tác giữa chúng. Lấy k = 9·10^9."),
                answer_value=f, answer_unit="N",
                bieu_thuc_kiem=f"9e9*{q1}*1e-6*{q2}*1e-6/{d}**2",
                ghi_chu="Coulomb: F = k*q1*q2/r^2")


def l13(r):
    e, rr, res = r.choice([12, 24]), r.choice([1, 2]), r.choice([5, 10, 11])
    return dict(topic="mach_dien_mot_chieu", level="VD",
                question=(f"Nguồn điện có suất điện động {e} V, điện trở trong {rr} Ω, mắc với "
                          f"điện trở ngoài {res} Ω. Tính cường độ dòng điện trong mạch."),
                answer_value=e / (res + rr), answer_unit="A",
                bieu_thuc_kiem=f"{e}/({res} + {rr})",
                ghi_chu="Định luật Ohm toàn mạch: I = E/(R + r)")


def l14(r):
    e, rr, res = r.choice([12, 24]), r.choice([1, 2]), r.choice([5, 10])
    i = e / (res + rr)
    return dict(topic="mach_dien_mot_chieu", level="VDC",
                question=(f"Nguồn có suất điện động {e} V, điện trở trong {rr} Ω nối với điện trở "
                          f"ngoài {res} Ω. Tính công suất tiêu thụ ở mạch ngoài."),
                answer_value=i**2 * res, answer_unit="W",
                bieu_thuc_kiem=f"({e}/({res} + {rr}))**2*{res}",
                ghi_chu="P_ngoài = I^2*R với I = E/(R+r)")


def l15(r):
    d1, f_tk = r.choice([30, 40, 60]), r.choice([10, 15, 20])
    if d1 == f_tk:
        d1 += 10
    d2 = d1 * f_tk / (d1 - f_tk)
    return dict(topic="thau_kinh", level="VDC",
                question=(f"Vật sáng đặt cách thấu kính hội tụ {d1} cm, tiêu cự thấu kính {f_tk} cm. "
                          f"Tính khoảng cách từ ảnh đến thấu kính."),
                answer_value=d2, answer_unit="cm",
                bieu_thuc_kiem=f"{d1}*{f_tk}/({d1} - {f_tk})",
                ghi_chu="1/f = 1/d + 1/d' => d' = d*f/(d-f)")


def l16(r):
    p1, v1, v2 = r.choice([2, 3]), r.choice([4, 6]), r.choice([2, 8])
    return dict(topic="chat_khi", level="TH",
                question=(f"Khí lí tưởng ở áp suất {p1} atm có thể tích {v1} lít. Nén đẳng nhiệt "
                          f"đến thể tích {v2} lít. Tính áp suất khí sau khi nén."),
                answer_value=p1 * v1 / v2, answer_unit="atm",
                bieu_thuc_kiem=f"{p1}*{v1}/{v2}",
                ghi_chu="Đẳng nhiệt Boyle-Mariotte: p1V1 = p2V2")


def l17(r):
    m, c, dt = r.choice([0.5, 2]), r.choice([880, 460]), r.choice([25, 40])
    return dict(topic="nhiet_luong", level="TH",
                question=(f"Tính nhiệt lượng cần cung cấp cho {vn(m)} kg vật liệu có nhiệt dung "
                          f"riêng {c} J/(kg.K) để tăng {dt} độ C."),
                answer_value=m * c * dt, answer_unit="J",
                bieu_thuc_kiem=f"{m}*{c}*{dt}",
                ghi_chu="Q = mc*delta_t")


def l18(r):
    lam_nm = r.choice([400, 500, 600])
    e = 6.625e-34 * 3e8 / (lam_nm * 1e-9) / 1.6e-19
    return dict(topic="luong_tu", level="VDC",
                question=(f"Tính năng lượng của photon ánh sáng có bước sóng {lam_nm} nm, "
                          f"kết quả theo đơn vị eV. Lấy h = 6,625·10^-34, c = 3·10^8, "
                          f"1 eV = 1,6·10^-19 J."),
                answer_value=e, answer_unit="eV",
                bieu_thuc_kiem=f"6.625e-34*3e8/({lam_nm}*1e-9)/1.6e-19",
                ghi_chu="epsilon = hc/lambda, đổi J sang eV")


def l19(r):
    n1, n2, u1 = r.choice([500, 800]), r.choice([2000, 4000]), r.choice([100, 200])
    return dict(topic="may_bien_ap", level="TH",
                question=(f"Máy biến áp có cuộn sơ cấp {n1} vòng, thứ cấp {n2} vòng. Điện áp sơ cấp "
                          f"{u1} V. Tính điện áp thứ cấp."),
                answer_value=u1 * n2 / n1, answer_unit="V",
                bieu_thuc_kiem=f"{u1}*{n2}/{n1}",
                ghi_chu="U2/U1 = N2/N1 (máy tăng áp)")


def l20(r):
    v, f = r.choice([320, 340]), r.choice([400, 500, 800])
    return dict(topic="song_co", level="NB",
                question=f"Sóng âm truyền với tốc độ {v} m/s, tần số {f} Hz. Tính bước sóng.",
                answer_value=v / f, answer_unit="m",
                bieu_thuc_kiem=f"{v}/{f}", ghi_chu="lambda = v/f")


def l21(r):
    m, h = r.choice([0.5, 2, 5]), r.choice([3, 8, 12])
    return dict(topic="co_nang", level="TH",
                question=(f"Vật {vn(m)} kg rơi tự do từ độ cao {h} m. Lấy g = 10 m/s^2. "
                          f"Tính vận tốc khi chạm đất."),
                answer_value=math.sqrt(2 * 10 * h), answer_unit="m/s",
                bieu_thuc_kiem=f"sqrt(2*10*{h})",
                ghi_chu="Bảo toàn cơ năng: mgh = mv^2/2 => v = sqrt(2gh)")


def l22(r):
    i, res, t = r.choice([2, 3]), r.choice([10, 20]), r.choice([60, 300])
    return dict(topic="nhiet_dien", level="VD",
                question=(f"Dòng điện {i} A qua điện trở {res} Ω trong {t} giây. "
                          f"Tính nhiệt lượng toả ra."),
                answer_value=i**2 * res * t, answer_unit="J",
                bieu_thuc_kiem=f"{i}**2*{res}*{t}",
                ghi_chu="Joule-Lenz: Q = I^2*R*t")


def l23(r):
    b, i, l = r.choice([0.2, 0.5]), r.choice([2, 4]), r.choice([0.3, 0.5])
    return dict(topic="tu_truong", level="VD",
                question=(f"Đoạn dây dài {vn(l)} m mang dòng {i} A đặt vuông góc từ trường "
                          f"{vn(b)} T. Tính lực từ tác dụng lên dây."),
                answer_value=b * i * l, answer_unit="N",
                bieu_thuc_kiem=f"{b}*{i}*{l}",
                ghi_chu="F = BIl*sin(alpha), vuông góc nên sin = 1")


def l24(r):
    n, dphi, dt = r.choice([100, 200]), r.choice([0.02, 0.05]), r.choice([0.1, 0.2])
    return dict(topic="cam_ung_dien_tu", level="VDC",
                question=(f"Cuộn dây {n} vòng, từ thông qua mỗi vòng biến thiên {vn(dphi)} Wb "
                          f"trong {vn(dt)} s. Tính suất điện động cảm ứng."),
                answer_value=n * dphi / dt, answer_unit="V",
                bieu_thuc_kiem=f"{n}*{dphi}/{dt}",
                ghi_chu="Faraday: e = N*|dPhi/dt|")


def l25(r):
    a_cm, x_cm = r.choice([10, 8, 12]), r.choice([4, 5, 6])
    w = r.choice([10, 20])
    v = w * math.sqrt((a_cm / 100) ** 2 - (x_cm / 100) ** 2)
    return dict(topic="dao_dong_dieu_hoa", level="VDC",
                question=(f"Vật dao động điều hoà biên độ {a_cm} cm, tần số góc {w} rad/s. "
                          f"Tính tốc độ của vật khi li độ bằng {x_cm} cm."),
                answer_value=v, answer_unit="m/s",
                bieu_thuc_kiem=f"{w}*sqrt(({a_cm}/100)**2 - ({x_cm}/100)**2)",
                ghi_chu="v = omega*sqrt(A^2 - x^2)")


def l26(r):
    p, t = r.choice([500, 1000, 1500]), r.choice([120, 600])
    return dict(topic="cong_suat_dien", level="NB",
                question=f"Thiết bị công suất {p} W hoạt động trong {t} giây. Tính điện năng tiêu thụ.",
                answer_value=p * t, answer_unit="J",
                bieu_thuc_kiem=f"{p}*{t}", ghi_chu="A = P*t")


def l27(r):
    l, c_pf = r.choice([2e-3, 5e-3]), r.choice([200, 500])
    f = 1 / (2 * math.pi * math.sqrt(l * c_pf * 1e-12))
    return dict(topic="mach_dao_dong", level="VDC",
                question=(f"Mạch dao động LC có L = {vn(l * 1000)} mH và C = {c_pf} pF. "
                          f"Tính tần số dao động riêng."),
                answer_value=f, answer_unit="Hz",
                bieu_thuc_kiem=f"1/(2*pi*sqrt({l}*{c_pf}*1e-12))",
                ghi_chu="f = 1/(2*pi*sqrt(LC)), chú ý đổi mH và pF")


def l28(r):
    m, v = r.choice([1000, 1500]), r.choice([10, 20])
    return dict(topic="dong_nang", level="NB",
                question=f"Ô tô khối lượng {m} kg chạy với vận tốc {v} m/s. Tính động năng.",
                answer_value=0.5 * m * v**2, answer_unit="J",
                bieu_thuc_kiem=f"0.5*{m}*{v}**2", ghi_chu="W_d = mv^2/2")


def l29(r):
    d, h = r.choice([1000, 800]), r.choice([5, 10])
    return dict(topic="ap_suat", level="TH",
                question=(f"Tính áp suất tại độ sâu {h} m trong chất lỏng có khối lượng riêng "
                          f"{d} kg/m^3. Lấy g = 10 m/s^2."),
                answer_value=d * 10 * h, answer_unit="Pa",
                bieu_thuc_kiem=f"{d}*10*{h}", ghi_chu="p = rho*g*h")


def l30(r):
    a_cm, t_s = r.choice([5, 10]), r.choice([0.4, 0.8])
    # Quang duong trong 1 chu ky = 4A
    return dict(topic="dao_dong_dieu_hoa", level="VD",
                question=(f"Vật dao động điều hoà biên độ {a_cm} cm, chu kỳ {vn(t_s)} s. "
                          f"Tính quãng đường vật đi được trong một chu kỳ."),
                answer_value=4 * a_cm, answer_unit="cm",
                bieu_thuc_kiem=f"4*{a_cm}",
                ghi_chu="Mỗi chu kỳ vật đi được 4A")


def l31(r):
    f_hz, v = r.choice([50, 60]), r.choice([300, 340])
    return dict(topic="song_co", level="TH",
                question=(f"Hai điểm trên phương truyền sóng cách nhau nửa bước sóng. Sóng có tần số "
                          f"{f_hz} Hz, tốc độ {v} m/s. Tính khoảng cách hai điểm đó."),
                answer_value=v / f_hz / 2, answer_unit="m",
                bieu_thuc_kiem=f"{v}/{f_hz}/2",
                ghi_chu="lambda = v/f, khoảng cách = lambda/2")


def l32(r):
    a_bx, z = r.choice([(235, 92), (238, 92), (14, 6)])
    return dict(topic="hat_nhan", level="NB",
                question=(f"Hạt nhân có số khối {a_bx} và số proton {z}. Tính số neutron "
                          f"trong hạt nhân."),
                answer_value=float(a_bx - z),
                bieu_thuc_kiem=f"{a_bx} - {z}", ghi_chu="N = A - Z")


# ===========================================================================
# HOÁ HỌC — 32 mẫu
# ===========================================================================

_HC_MO_RONG = [
    ("KMnO4", {"K": 1, "Mn": 1, "O": 4}) if "Mn" in NTK else ("K2SO4", {"K": 2, "S": 1, "O": 4}),
    ("Fe2O3", {"Fe": 2, "O": 3}),
    ("Ba(OH)2", {"Ba": 1, "O": 2, "H": 2}),
    ("Al(NO3)3", {"Al": 1, "N": 3, "O": 9}),
    ("Ca3(PO4)2", {"Ca": 3, "P": 2, "O": 8}) if "P" in NTK else ("CaCl2", {"Ca": 1, "Cl": 2}),
    ("C6H12O6", {"C": 6, "H": 12, "O": 6}),
    ("CH3COOH", {"C": 2, "H": 4, "O": 2}),
    ("NH4NO3", {"N": 2, "H": 4, "O": 3}),
]


def q01(r):
    ten, ct = r.choice(_HC_MO_RONG)
    return dict(topic="khoi_luong_mol", level="TH",
                question=f"Tính khối lượng mol của hợp chất {ten}.",
                answer_value=M(ct), answer_unit="g/mol",
                bieu_thuc_kiem=" + ".join(f"{NTK[e]}*{n}" for e, n in sorted(ct.items())),
                ghi_chu="Cộng khối lượng nguyên tử theo chỉ số")


def q02(r):
    ten, ct = r.choice(_HC_MO_RONG)
    m = r.choice([10, 20, 50])
    mm = M(ct)
    return dict(topic="so_mol", level="TH",
                question=(f"Tính số mol có trong {m} gam {ten}. "
                          f"Biết M({ten}) = {vn(mm)} g/mol."),
                answer_value=m / mm, answer_unit="mol",
                bieu_thuc_kiem=f"{m}/{mm}", ghi_chu="n = m/M")


def q03(r):
    pu = r.choice([
        (["Fe", "Cl2"], ["FeCl3"], 1),
        (["KClO3"], ["KCl", "O2"], 0),
        (["C3H8", "O2"], ["CO2", "H2O"], 1),
        (["Na", "H2O"], ["NaOH", "H2"], 0),
        (["FeS2", "O2"], ["Fe2O3", "SO2"], 1),
    ])
    trai, phai, vt = pu
    kq = chem_tool.balance_equation(trai, phai)
    if not kq.get("balanced"):
        return None
    return dict(topic="can_bang_pthh", level="VD",
                question=(f"Cân bằng phương trình {' + '.join(trai)} → {' + '.join(phai)}. "
                          f"Cho biết hệ số của {trai[vt]}."),
                answer_value=float(kq["reactant_coeffs"][vt]),
                bieu_thuc_kiem=str(kq["reactant_coeffs"][vt]),
                ghi_chu=f"Phương trình cân bằng: {kq['equation']} (tính bằng chem_tool)")


def q04(r):
    c1, v1_ml, c2, v2_ml = r.choice([0.5, 1.0]), r.choice([100, 200]), r.choice([0.2, 0.4]), r.choice([300, 500])
    n = c1 * v1_ml / 1000 + c2 * v2_ml / 1000
    v = (v1_ml + v2_ml) / 1000
    return dict(topic="nong_do_mol", level="VD",
                question=(f"Trộn {v1_ml} ml dung dịch NaCl {vn(c1)}M với {v2_ml} ml dung dịch "
                          f"NaCl {vn(c2)}M. Tính nồng độ mol của dung dịch thu được."),
                answer_value=n / v, answer_unit="M",
                bieu_thuc_kiem=f"({c1}*{v1_ml}/1000 + {c2}*{v2_ml}/1000)/(({v1_ml}+{v2_ml})/1000)",
                ghi_chu="Tổng mol chia tổng thể tích")


def q05(r):
    m_hh, pt_zn = r.choice([20, 30]), r.choice([0.4, 0.6])
    m_zn = m_hh * pt_zn
    n_h2 = m_zn / 65
    return dict(topic="hon_hop_kim_loai", level="VDC",
                question=(f"Hỗn hợp {m_hh} gam gồm Zn và Cu, trong đó Zn chiếm {vn(pt_zn * 100)}% "
                          f"khối lượng. Cho hỗn hợp tác dụng HCl dư. Tính thể tích khí H2 "
                          f"thu được ở đktc. Biết Zn = 65."),
                answer_value=n_h2 * 22.4, answer_unit="lit",
                bieu_thuc_kiem=f"{m_hh}*{pt_zn}/65*22.4",
                ghi_chu="Chỉ Zn phản ứng HCl, Cu đứng sau H nên không phản ứng")


def q06(r):
    n_al = r.choice([0.2, 0.4])
    # 2Al + 3H2SO4 -> Al2(SO4)3 + 3H2; n(H2) = 1.5*n(Al)
    return dict(topic="kim_loai_axit", level="VD",
                question=(f"Cho {vn(n_al * 27)} gam Al tác dụng hết với dung dịch H2SO4 loãng. "
                          f"Tính thể tích H2 thu được ở đktc. Biết Al = 27."),
                answer_value=n_al * 1.5 * 22.4, answer_unit="lit",
                bieu_thuc_kiem=f"{n_al * 27}/27*1.5*22.4",
                ghi_chu="2Al + 3H2SO4 -> Al2(SO4)3 + 3H2, tỉ lệ n(H2) = 1,5*n(Al)")


def q07(r):
    n_khi = r.choice([0.1, 0.2, 0.3])
    return dict(topic="ket_tua", level="VD",
                question=(f"Sục {vn(n_khi * 22.4)} lít CO2 (đktc) vào dung dịch Ca(OH)2 dư. "
                          f"Tính khối lượng kết tủa CaCO3 thu được. Biết M(CaCO3) = 100."),
                answer_value=n_khi * 100, answer_unit="gam",
                bieu_thuc_kiem=f"{n_khi * 22.4}/22.4*100",
                ghi_chu="CO2 + Ca(OH)2 -> CaCO3 + H2O, bazơ dư nên CO2 hết")


def q08(r):
    m_glu = r.choice([18, 36, 90])
    # C6H12O6 -> 2C2H5OH + 2CO2; M(glucozo) = 180, M(ancol) = 46
    return dict(topic="len_men", level="VDC",
                question=(f"Lên men hoàn toàn {m_glu} gam glucozơ C6H12O6 thành ancol etylic. "
                          f"Tính khối lượng ancol thu được. Biết M(C6H12O6) = 180, "
                          f"M(C2H5OH) = 46."),
                answer_value=m_glu / 180 * 2 * 46, answer_unit="gam",
                bieu_thuc_kiem=f"{m_glu}/180*2*46",
                ghi_chu="C6H12O6 -> 2C2H5OH + 2CO2, mỗi mol glucozơ cho 2 mol ancol")


def q09(r):
    m_este, mm_este, mm_muoi = r.choice([(7.4, 74, 68), (8.6, 86, 82), (10.2, 102, 82)])
    return dict(topic="este", level="VDC",
                question=(f"Thuỷ phân hoàn toàn {vn(m_este)} gam este trong NaOH vừa đủ, thu được "
                          f"muối. Biết M(este) = {mm_este} và M(muối) = {mm_muoi} g/mol. "
                          f"Tính khối lượng muối."),
                answer_value=m_este / mm_este * mm_muoi, answer_unit="gam",
                bieu_thuc_kiem=f"{m_este}/{mm_este}*{mm_muoi}",
                ghi_chu="Este đơn chức + NaOH -> muối + ancol, tỉ lệ 1:1")


def q10(r):
    v_naoh, c_naoh = r.choice([100, 250]), r.choice([0.1, 0.2])
    return dict(topic="ph", level="VD",
                question=(f"Tính pH của dung dịch NaOH nồng độ {vn(c_naoh)}M."),
                answer_value=14 + math.log10(c_naoh),
                bieu_thuc_kiem=f"14 + log({c_naoh})/log(10)",
                ghi_chu="NaOH bazơ mạnh: pOH = -log[OH-], pH = 14 - pOH")


def q11(r):
    n_fe, n_cu = r.choice([0.1, 0.2]), r.choice([0.1, 0.15])
    return dict(topic="bao_toan_electron", level="VDC",
                question=(f"Hỗn hợp {vn(n_fe)} mol Fe và {vn(n_cu)} mol Cu tan hết trong HNO3 đặc "
                          f"nóng dư, chỉ tạo khí NO2. Tính số mol NO2 thu được. "
                          f"Biết Fe lên số oxi hoá +3 và Cu lên +2."),
                answer_value=n_fe * 3 + n_cu * 2, answer_unit="mol",
                bieu_thuc_kiem=f"{n_fe}*3 + {n_cu}*2",
                ghi_chu="Bảo toàn electron: n(NO2) = 3n(Fe) + 2n(Cu) vì NO2 nhận 1 e")


def q12(r):
    m_caco3, h = r.choice([100, 200]), r.choice([80, 90])
    return dict(topic="hieu_suat", level="VD",
                question=(f"Nung {m_caco3} gam CaCO3 với hiệu suất {h}%. Tính khối lượng CaO "
                          f"thu được. Biết M(CaCO3) = 100, M(CaO) = 56."),
                answer_value=m_caco3 / 100 * 56 * h / 100, answer_unit="gam",
                bieu_thuc_kiem=f"{m_caco3}/100*56*{h}/100",
                ghi_chu="CaCO3 -> CaO + CO2, nhân hiệu suất")


def q13(r):
    v_kk = r.choice([100, 200])
    return dict(topic="thanh_phan_khong_khi", level="NB",
                question=(f"Trong {v_kk} lít không khí có bao nhiêu lít O2? "
                          f"Biết O2 chiếm 20% thể tích không khí."),
                answer_value=v_kk * 0.2, answer_unit="lit",
                bieu_thuc_kiem=f"{v_kk}*0.2", ghi_chu="V(O2) = 20% V(không khí)")


def q14(r):
    m, mm = r.choice([(4.6, 46), (9.2, 46), (6.0, 60)])
    return dict(topic="so_mol", level="NB",
                question=f"Tính số mol có trong {vn(m)} gam chất có khối lượng mol {mm} g/mol.",
                answer_value=m / mm, answer_unit="mol",
                bieu_thuc_kiem=f"{m}/{mm}", ghi_chu="n = m/M")


def q15(r):
    n = r.choice([0.1, 0.25, 0.5])
    return dict(topic="the_tich_khi", level="NB",
                question=f"Tính thể tích của {vn(n)} mol khí ở điều kiện tiêu chuẩn.",
                answer_value=n * 22.4, answer_unit="lit",
                bieu_thuc_kiem=f"{n}*22.4", ghi_chu="V = n*22,4 ở đktc")


def q16(r):
    m_dd, c_pt = r.choice([200, 500]), r.choice([10, 20])
    return dict(topic="nong_do_phan_tram", level="TH",
                question=(f"Tính khối lượng chất tan trong {m_dd} gam dung dịch nồng độ {c_pt}%."),
                answer_value=m_dd * c_pt / 100, answer_unit="gam",
                bieu_thuc_kiem=f"{m_dd}*{c_pt}/100", ghi_chu="m_ct = m_dd*C%/100")


def q17(r):
    n_x = 0.1
    so_c, so_h = r.choice([(2, 4), (3, 6), (4, 8)])
    return dict(topic="tim_cong_thuc_phan_tu", level="VDC",
                question=(f"Đốt cháy hoàn toàn {vn(n_x)} mol anken X thu được {vn(n_x * so_c)} mol CO2. "
                          f"Xác định khối lượng mol của X. Biết anken có công thức chung CnH2n."),
                answer_value=so_c * 12 + so_h, answer_unit="g/mol",
                bieu_thuc_kiem=f"{so_c}*12 + {so_c}*2*1",
                ghi_chu="Anken CnH2n; n = n(CO2)/n(X); M = 12n + 2n = 14n")


def q18(r):
    i, t, n_e = r.choice([1.93, 5]), r.choice([1000, 2000]), r.choice([1, 2])
    kl, mm = r.choice([("Ag", 108), ("Cu", 64)])
    n_e_real = 1 if kl == "Ag" else 2
    return dict(topic="dien_phan", level="VDC",
                question=(f"Điện phân dung dịch muối {kl} với cường độ {vn(i)} A trong {t} giây. "
                          f"Tính khối lượng {kl} thu được ở catot. "
                          f"Biết {kl} = {mm}, F = 96500."),
                answer_value=mm * i * t / (n_e_real * 96500), answer_unit="gam",
                bieu_thuc_kiem=f"{mm}*{i}*{t}/({n_e_real}*96500)",
                ghi_chu=f"Faraday m = AIt/(nF); ion {kl} nhận {n_e_real} electron")


def q19(r):
    n_hcl, n_naoh = r.choice([0.3, 0.4]), r.choice([0.1, 0.2])
    du = n_hcl - n_naoh
    v = r.choice([0.5, 1.0])
    return dict(topic="ph", level="VDC",
                question=(f"Trộn dung dịch chứa {vn(n_hcl)} mol HCl với dung dịch chứa {vn(n_naoh)} "
                          f"mol NaOH, thu được {vn(v)} lít dung dịch. Tính pH dung dịch sau phản ứng."),
                answer_value=-math.log10(du / v),
                bieu_thuc_kiem=f"-log({du}/{v})/log(10)",
                ghi_chu="HCl dư, [H+] = n dư/V, pH = -log[H+]")


def q20(r):
    m_kl, mm, hoa_tri = r.choice([("Mg", 24, 2), ("Ca", 40, 2), ("Na", 23, 1)])
    n = r.choice([0.1, 0.2])
    return dict(topic="kim_loai_nuoc", level="VD",
                question=(f"Cho {vn(n * mm)} gam {m_kl} tác dụng hết với nước dư. Tính thể tích H2 "
                          f"thu được ở đktc. Biết {m_kl} = {mm}, hoá trị {hoa_tri}."),
                answer_value=n * hoa_tri / 2 * 22.4, answer_unit="lit",
                bieu_thuc_kiem=f"{n * mm}/{mm}*{hoa_tri}/2*22.4",
                ghi_chu="Mỗi mol kim loại hoá trị n cho n/2 mol H2")


def q21(r):
    m1, m2 = r.choice([10, 20]), r.choice([30, 40])
    return dict(topic="bao_toan_khoi_luong", level="TH",
                question=(f"Cho {m1} gam chất A phản ứng hết với {m2} gam chất B tạo thành chất C "
                          f"và {vn(m1 * 0.2)} gam khí thoát ra. Tính khối lượng chất C."),
                answer_value=m1 + m2 - m1 * 0.2, answer_unit="gam",
                bieu_thuc_kiem=f"{m1} + {m2} - {m1 * 0.2}",
                ghi_chu="Bảo toàn khối lượng: m(C) = m(A) + m(B) - m(khí)")


def q22(r):
    n_amin, so_n = r.choice([0.1, 0.2]), 1
    return dict(topic="amin", level="VD",
                question=(f"Đốt cháy hoàn toàn {vn(n_amin)} mol metylamin CH3NH2. "
                          f"Tính thể tích khí N2 thu được ở đktc."),
                answer_value=n_amin / 2 * 22.4, answer_unit="lit",
                bieu_thuc_kiem=f"{n_amin}/2*22.4",
                ghi_chu="Mỗi 2 mol amin đơn chức 1 N cho 1 mol N2")


def q23(r):
    m_tinh_bot, h = r.choice([162, 324]), r.choice([80, 75])
    # (C6H10O5)n + nH2O -> nC6H12O6; 162 -> 180
    return dict(topic="cacbohidrat", level="VDC",
                question=(f"Thuỷ phân {m_tinh_bot} gam tinh bột (C6H10O5)n với hiệu suất {h}%. "
                          f"Tính khối lượng glucozơ thu được. Biết mắt xích 162, glucozơ 180."),
                answer_value=m_tinh_bot / 162 * 180 * h / 100, answer_unit="gam",
                bieu_thuc_kiem=f"{m_tinh_bot}/162*180*{h}/100",
                ghi_chu="Mỗi mắt xích 162 cho 1 glucozơ 180, nhân hiệu suất")


def q24(r):
    n_h2so4, n_naoh = r.choice([0.1, 0.2]), r.choice([0.3, 0.4])
    # H2SO4 + 2NaOH -> Na2SO4 + 2H2O
    can = n_h2so4 * 2
    het = min(n_naoh, can) / 2
    return dict(topic="chat_du", level="VDC",
                question=(f"Cho {vn(n_h2so4)} mol H2SO4 phản ứng với {vn(n_naoh)} mol NaOH. "
                          f"Tính khối lượng muối Na2SO4 thu được. Biết M(Na2SO4) = 142."),
                answer_value=het * 142, answer_unit="gam",
                bieu_thuc_kiem=f"{het}*142",
                ghi_chu="H2SO4 + 2NaOH -> Na2SO4 + 2H2O; xác định chất hết trước")


def q25(r):
    m, mm_kl, hoa_tri = r.choice([(5.4, 27, 3), (6.5, 65, 2), (2.4, 24, 2)])
    n_e = m / mm_kl * hoa_tri
    return dict(topic="bao_toan_electron", level="VD",
                question=(f"Hoà tan {vn(m)} gam kim loại hoá trị {hoa_tri} có M = {mm_kl} vào axit dư. "
                          f"Tính số mol electron kim loại đã nhường."),
                answer_value=n_e, answer_unit="mol",
                bieu_thuc_kiem=f"{m}/{mm_kl}*{hoa_tri}",
                ghi_chu="n(e) = n(kim loại) * hoá trị")


def q26(r):
    v_dd, c = r.choice([250, 400]), r.choice([0.5, 2.0])
    return dict(topic="nong_do_mol", level="NB",
                question=f"Tính số mol chất tan trong {v_dd} ml dung dịch nồng độ {vn(c)}M.",
                answer_value=v_dd / 1000 * c, answer_unit="mol",
                bieu_thuc_kiem=f"{v_dd}/1000*{c}", ghi_chu="n = C*V")


def q27(r):
    n_c, n_h = r.choice([(3, 8), (4, 10), (2, 6)])
    n_x = 0.1
    return dict(topic="dot_chay_huu_co", level="VD",
                question=(f"Đốt cháy hoàn toàn {vn(n_x)} mol ankan C{n_c}H{n_h}. "
                          f"Tính thể tích O2 cần dùng ở đktc."),
                answer_value=n_x * (n_c + n_h / 4) * 22.4, answer_unit="lit",
                bieu_thuc_kiem=f"{n_x}*({n_c} + {n_h}/4)*22.4",
                ghi_chu="CxHy + (x + y/4)O2 -> xCO2 + (y/2)H2O")


def q28(r):
    m_fe, m_o = r.choice([(11.2, 4.8), (5.6, 2.4), (16.8, 7.2)])
    return dict(topic="lap_cong_thuc", level="VDC",
                question=(f"Một oxit sắt chứa {vn(m_fe)} gam Fe và {vn(m_o)} gam O. "
                          f"Tính tỉ lệ số mol Fe : O trong oxit. Đáp số là tỉ số n(Fe)/n(O). "
                          f"Biết Fe = 56, O = 16."),
                answer_value=(m_fe / 56) / (m_o / 16),
                bieu_thuc_kiem=f"({m_fe}/56)/({m_o}/16)",
                ghi_chu="Tỉ lệ mol = (m/M) của mỗi nguyên tố")


def q29(r):
    n_zn = r.choice([0.1, 0.2])
    return dict(topic="phan_ung_the", level="VD",
                question=(f"Cho {vn(n_zn * 65)} gam Zn vào dung dịch CuSO4 dư. "
                          f"Tính khối lượng Cu sinh ra. Biết Zn = 65, Cu = 64."),
                answer_value=n_zn * 64, answer_unit="gam",
                bieu_thuc_kiem=f"{n_zn * 65}/65*64",
                ghi_chu="Zn + CuSO4 -> ZnSO4 + Cu, tỉ lệ 1:1")


def q30(r):
    m_hh, m_gam_co2 = r.choice([(20, 8.8), (30, 13.2)])
    return dict(topic="bao_toan_nguyen_to", level="VDC",
                question=(f"Nung {m_hh} gam hỗn hợp muối cacbonat, thu được {vn(m_gam_co2)} gam CO2. "
                          f"Tính khối lượng chất rắn còn lại. Bảo toàn khối lượng."),
                answer_value=m_hh - m_gam_co2, answer_unit="gam",
                bieu_thuc_kiem=f"{m_hh} - {m_gam_co2}",
                ghi_chu="m(rắn) = m(ban đầu) - m(CO2)")


def q31(r):
    c_dau, v_dau, v_them = r.choice([2.0, 4.0]), r.choice([50, 100]), r.choice([150, 200])
    return dict(topic="pha_loang", level="TH",
                question=(f"Thêm {v_them} ml nước vào {v_dau} ml dung dịch {vn(c_dau)}M. "
                          f"Tính nồng độ mol dung dịch sau khi pha."),
                answer_value=c_dau * v_dau / (v_dau + v_them), answer_unit="M",
                bieu_thuc_kiem=f"{c_dau}*{v_dau}/({v_dau} + {v_them})",
                ghi_chu="C1V1 = C2V2, V2 = V_đầu + V_nước")


def q32(r):
    n_h2 = r.choice([0.15, 0.3])
    return dict(topic="hon_hop_kim_loai", level="VDC",
                question=(f"Hỗn hợp Al và Mg tác dụng HCl dư thu được {vn(n_h2 * 22.4)} lít H2 (đktc). "
                          f"Tính tổng số mol electron mà kim loại đã nhường."),
                answer_value=n_h2 * 2, answer_unit="mol",
                bieu_thuc_kiem=f"{n_h2 * 22.4}/22.4*2",
                ghi_chu="Mỗi mol H2 nhận 2 electron nên n(e) = 2*n(H2)")


# ===========================================================================

MAU: dict[str, list[Callable]] = {
    "math": [t01, t02, t03, t04, t05, t06, t07, t08, t09, t10, t11, t12, t13,
             t14, t15, t16, t17, t18,
             h01, h02, h03, h04, h05, h06, h07, h08, h09, h10, h11, h12, h13,
             h14, h15, h16, h17, h18],
    "physics": [l01, l02, l03, l04, l05, l06, l07, l08, l09, l10, l11, l12, l13,
                l14, l15, l16, l17, l18, l19, l20, l21, l22, l23, l24, l25, l26,
                l27, l28, l29, l30, l31, l32],
    "chemistry": [q01, q02, q03, q04, q05, q06, q07, q08, q09, q10, q11, q12,
                  q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23, q24,
                  q25, q26, q27, q28, q29, q30, q31, q32],
}


def sinh_mon(mon: str, so_bai: int, r: random.Random, tranh: set[str]) -> list[dict]:
    ra: list[dict] = []
    da_co: set[str] = set(tranh)
    mau = MAU[mon]
    vong = 0
    while len(ra) < so_bai and vong < 200:
        for f in mau:
            if len(ra) >= so_bai:
                break
            d = None
            for _ in range(25):
                d = f(r)
                if d and d["question"] not in da_co:
                    break
                d = None
            if d is None:
                continue
            da_co.add(d["question"])
            ra.append({
                "id": f"{TIEN_TO[mon]}_{d['level'].lower()}_k{len(ra) + 1:03d}",
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


def main(seed: int, ra_file: Path, tranh_files: list[Path]) -> int:
    r = random.Random(seed)

    tranh: set[str] = set()
    for tf in tranh_files:
        if tf.exists():
            with tf.open(encoding="utf-8-sig", newline="") as f:
                tranh |= {(d.get("question") or "").strip() for d in csv.DictReader(f)}
            print(f"Tránh trùng với {tf.name}")
    print(f"Tổng cộng loại {len(tranh)} câu đã dùng\n")

    tat_ca: list[dict] = []
    for mon in ("math", "physics", "chemistry"):
        bai = sinh_mon(mon, SO_BAI_MOI_MON, r, tranh)
        tat_ca += bai
        muc: dict[str, int] = {}
        for b in bai:
            muc[b["level"]] = muc.get(b["level"], 0) + 1
        chu_de = len({b["topic"] for b in bai})
        print(f"{mon:<10} {len(bai):3} bài  " +
              "  ".join(f"{k} {muc.get(k, 0):2}" for k in ("NB", "TH", "VD", "VDC")) +
              f"   ({chu_de} chủ đề)")

    ra_file.parent.mkdir(parents=True, exist_ok=True)
    with ra_file.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COT)
        w.writeheader()
        w.writerows(tat_ca)

    print(f"\nTổng {len(tat_ca)} bài -> {ra_file}")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Sinh bộ đề KHÓ 300 bài")
    ap.add_argument("--seed", type=int, default=20260806)
    ap.add_argument("--ra", default=str(RA))
    ap.add_argument("--tranh", nargs="*", default=[str(p) for p in TRANH_MAC_DINH])
    a = ap.parse_args()
    raise SystemExit(main(a.seed, Path(a.ra), [Path(p) for p in a.tranh]))
