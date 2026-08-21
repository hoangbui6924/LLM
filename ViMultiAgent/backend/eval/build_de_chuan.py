"""Sinh bộ đề chuẩn để đo hiệu năng — 150 bài, 50 mỗi môn.

Chạy:  python eval/build_de_chuan.py

Vì sao SINH ra chứ không gõ tay
-------------------------------
Bộ đề này là *ground truth*. Sai một đáp án là mọi số liệu tính từ nó thành rác,
và loại lỗi đó gần như không thể phát hiện về sau — bench sẽ báo hệ thống "sai"
ở một bài mà thực ra nó giải đúng.

Gõ tay 100 đáp án thì chắc chắn có vài chỗ nhầm. Ở đây mỗi mẫu đề mã hoá sẵn một
CÔNG THỨC, còn đáp án do Python tính ra từ ĐÚNG những con số đã đưa vào đề. Sai
số học là không thể xảy ra về mặt kiến tạo.

Hai tầng bảo đảm
----------------
1. Đáp án tính bằng code từ tham số của chính đề bài.
2. Cột `bieu_thuc_kiem` ghi lại công thức đã thay số. `eval/kiem_de_chuan.py`
   dùng SymPy tính lại cột này và đối chiếu với `answer_value` — bắt mọi lệch
   giữa "công thức đã ghi" và "đáp án đã lưu".

Tầng thứ 3 mà script không thay được: TÍNH ĐÚNG CỦA CÔNG THỨC. Việc chọn
`V = (1/3)*S_đáy*h` có đúng với hình đề cho hay không thì chỉ người đọc mới thẩm
định được. Mỗi mẫu vì vậy đều ghi rõ công thức trong `ghi_chu` để rà soát.
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


RA = GOC / "eval" / "data" / "de_chuan.csv"
SO_BAI_MOI_MON = 50   # mỗi phân môn



def vn(x: float, chu_so: int = 4) -> str:
    """Số theo cách viết Việt Nam: dấu phẩy thập phân, bỏ đuôi 0 thừa."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    s = f"{x:.{chu_so}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


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

MAU: dict[str, list[Callable]] = {
    # Đại số & Giải tích — 23 mẫu
    "dai_so": [m01, m02, m03, m04, m05, m06, m07, m08, m09, m10, m11, m12, m13,
               m14, m15, m16, m17, m18, m21, m22, m23, m24, m25],
    # Hình học — 2 mẫu (thể tích khối chóp, thể tích lăng trụ)
    "hinh_hoc": [m19, m20],
}

TIEN_TO = {"dai_so": "ds", "hinh_hoc": "hh"}

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
    for mon in MAU:
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
