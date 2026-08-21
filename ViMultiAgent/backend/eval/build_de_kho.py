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

from build_de_chuan import COT, TIEN_TO, hs, vn  # noqa: E402

RA = GOC / "eval" / "data" / "de_kho.csv"
SO_BAI_MOI_MON = 100   # mỗi phân môn

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

MAU: dict[str, list[Callable]] = {
    # Đại số & Giải tích — 18 mẫu
    "dai_so": [t01, t02, t03, t04, t05, t06, t07, t08, t09, t10, t11, t12, t13,
               t14, t15, t16, t17, t18],
    # Hình học — 18 mẫu
    "hinh_hoc": [h01, h02, h03, h04, h05, h06, h07, h08, h09, h10, h11, h12, h13,
                 h14, h15, h16, h17, h18],
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
    for mon in MAU:
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
