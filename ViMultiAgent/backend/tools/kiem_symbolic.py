"""Kiểm chứng TẤT ĐỊNH bằng SymPy — tính lại bài toán, không hỏi mô hình.

Vì sao có module này
--------------------
`sympy_tool` có 8 hàm công khai nhưng agent chỉ dùng 3. Năm hàm còn lại chưa từng
được gọi, trong đó có `check_substitution` mà chính docstring của module gọi là
"hàm quan trọng nhất".

Ghép với số liệu điểm gãy thì rất khớp — ba chủ đề Toán sai NẶNG NHẤT trên bộ đề
khó đều là loại SymPy kiểm được trong vài mili giây:

    tích phân từng phần   sai 3/3
    giới hạn              sai 3/3
    tiếp tuyến            sai 3/3

Khác gì `recompute_agent`
-------------------------
`recompute_agent` bắt MÔ HÌNH vừa suy luận vừa ra số — 42 giây, và chỉ cho kết
quả dùng được ở ~16% số bài.

Ở đây tách đôi: mô hình chỉ **trích cấu trúc** (loại bài, hàm gốc, biến, cận) —
việc dễ, không cần suy nghĩ, vài giây. Còn **SymPy tính**, tất định, không bao giờ
sai, gần như không tốn thời gian.

Đúng triết lý dự án đã tuyên bố từ đầu: *LLM quyết định LÀM GÌ, SymPy quyết định
KẾT QUẢ LÀ BAO NHIÊU* — nhưng đến giờ vẫn chưa thực hiện ở vai tính lại.

Giới hạn
--------
Chỉ kiểm được bài quy về được biểu thức tượng trưng. Bài Hoá theo phương trình
phản ứng, bài Lý nhiều bước đổi đơn vị thì không — những bài đó vẫn dựa vào các
phép kiểm sẵn có. Trả `None` khi không kiểm được, KHÔNG đoán bừa.
"""

from __future__ import annotations

import re
from typing import Any

import sympy as sp

from tools import sympy_tool

# Sai số tương đối khi so hai giá trị bằng số. Nới hơn ngưỡng của trọng tài (1%)
# vì đáp số ở đây có thể đi qua vài bước làm tròn của mô hình.
DUNG_SAI = 0.02

# Các loại bài kiểm được. Giữ danh sách ngắn và rõ — thêm loại nào thì phải có
# test cho loại đó, kẻo phép kiểm tất định lại thành nguồn báo oan.
LOAI_KIEM = (
    "dao_ham",       # đạo hàm của ham_goc tại diem (hoặc biểu thức đạo hàm)
    "tich_phan",     # tích phân ham_goc theo bien, có thể có can_duoi/can_tren
    "gioi_han",      # giới hạn ham_goc khi bien -> diem
    "phuong_trinh",  # thế nghiệm ngược vào phương trình
    "tiep_tuyen",    # phương trình tiếp tuyến của ham_goc tại diem
    # --- Hình học, thêm ở P3 ---
    "the_tich",      # thể tích khối theo `hinh` và `tham_so`
    "kc_hai_diem",   # khoảng cách giữa diem và diem2
    "kc_diem_mp",    # khoảng cách từ diem đến mặt phẳng ham_goc
)

# Công thức thể tích và diện tích, tra theo tên hình. `tham_so` là dãy số cách
# nhau bằng dấu chấm phẩy, thứ tự ghi ngay trong chú thích từng dòng.
#
# Vì sao đáng làm — P3 trong `PHUONGAN_TOCDO.md`:
# Bài hình học trước đây KHÔNG có phép kiểm tất định nào chạy được, nên Verify
# không đủ điều kiện đi đường tắt và buộc phải hỏi LLM (~4-6 giây). Tệ hơn, chính
# lượt hỏi đó là nguồn báo oan: đo được một bài thể tích ra đáp án 20 — ĐÚNG —
# nhưng LLM viết "1/3 * 12 * 5 = 20 nhưng đúng là 20" rồi kết luận FAIL.
CONG_THUC_HINH: dict[str, tuple[int, Any]] = {
    # tên hình:        (số tham số, hàm tính)
    "chop":            (2, lambda p: p[0] * p[1] / 3),        # S_đáy; h
    "lang_tru":        (2, lambda p: p[0] * p[1]),            # S_đáy; h
    # Biến thể mô tả đáy bằng KÍCH THƯỚC thay vì diện tích. Có chúng thì mô hình
    # không phải tự quy đổi — chính bước quy đổi ấy là nguồn lỗi đo được: đề cho
    # "đáy hình vuông cạnh 3", mô hình điền thẳng 3 vào ô diện tích đáy, SymPy
    # tính ra 9 rồi phủ quyết đáp án ĐÚNG là 27.
    "chop_day_vuong":  (2, lambda p: p[0] ** 2 * p[1] / 3),   # cạnh đáy; h
    "lang_tru_day_vuong": (2, lambda p: p[0] ** 2 * p[1]),    # cạnh đáy; h
    "non":             (2, lambda p: sp.pi * p[0] ** 2 * p[1] / 3),   # r; h
    "tru":             (2, lambda p: sp.pi * p[0] ** 2 * p[1]),       # r; h
    "cau":             (1, lambda p: sp.Rational(4, 3) * sp.pi * p[0] ** 3),  # r
    "lap_phuong":      (1, lambda p: p[0] ** 3),              # a
    "hop_chu_nhat":    (3, lambda p: p[0] * p[1] * p[2]),     # a; b; c
}


def _so(x: Any) -> float | None:
    try:
        v = complex(sp.N(x))
        return v.real if abs(v.imag) < 1e-9 else None
    except Exception:  # noqa: BLE001
        return None


# Các điểm dùng để thử hai biểu thức có trùng nhau không. Chọn số lẻ, không nguyên,
# để tránh vô tình rơi đúng nghiệm chung của hiệu hai biểu thức khác nhau.
_DIEM_THU = (0.3719, 1.1327, 2.7183, -1.4142, 4.6692)


def _khop(a: Any, b: Any) -> bool | None:
    """Hai kết quả có bằng nhau không. `None` khi không kết luận được.

    Ba tầng, vì đáp số có thể là số HOẶC biểu thức:

      1. rút gọn tượng trưng — bắt được `1/2` bằng `0.5`, `sqrt(2)/2` bằng `1/sqrt(2)`
      2. hiệu quy về một số — so với dung sai
      3. hiệu còn ẩn — THỬ TẠI VÀI ĐIỂM

    Tầng 3 là chỗ bản đầu tiên thiếu, và nó khiến `7x + 1` với `5x + 5` bị trả về
    "không so sánh được" thay vì "khác nhau". Tức tiếp tuyến sai lọt lưới — đúng
    chủ đề đang sai 3/3 trên bộ đề khó.
    """
    try:
        hieu = sp.simplify(a - b)
    except Exception:  # noqa: BLE001
        return None

    if hieu == 0:
        return True

    v = _so(hieu)
    if v is not None:
        thang = max(1.0, abs(_so(a) or 1.0))
        return abs(v) <= DUNG_SAI * thang

    an = sorted(hieu.free_symbols, key=str)
    if not an:
        return None

    lech = False
    thu_duoc = 0
    for d in _DIEM_THU:
        try:
            gt = complex(sp.N(hieu.subs({s: d for s in an})))
            moc = complex(sp.N(a.subs({s: d for s in an}))) if hasattr(a, "subs") else 1.0
        except Exception:  # noqa: BLE001
            continue
        if not (abs(gt.real) < 1e12 and abs(gt.imag) < 1e12):
            continue                      # điểm rơi vào chỗ không xác định
        thu_duoc += 1
        if abs(gt) > DUNG_SAI * max(1.0, abs(moc)):
            lech = True
            break

    if lech:
        return False
    # Trùng khít ở mọi điểm thử được, dù rút gọn tượng trưng không chứng minh nổi.
    return True if thu_duoc >= 2 else None


class KetQuaKiem:
    """Kết quả một lượt kiểm. `dat is None` nghĩa là KHÔNG kiểm được."""

    __slots__ = ("dat", "mo_ta", "gia_tri_dung")

    def __init__(self, dat: bool | None, mo_ta: str, gia_tri_dung: str = "") -> None:
        self.dat = dat
        self.mo_ta = mo_ta
        self.gia_tri_dung = gia_tri_dung

    def __repr__(self) -> str:  # pragma: no cover
        return f"KetQuaKiem(dat={self.dat}, mo_ta={self.mo_ta!r})"


def _khong_kiem_duoc(ly_do: str) -> KetQuaKiem:
    return KetQuaKiem(None, ly_do)


# ---------------------------------------------------------------------------
# Hình học — đọc tham số
# ---------------------------------------------------------------------------

# Sách giáo khoa Việt Nam ngăn toạ độ bằng dấu CHẤM PHẨY: A(1; 2; 3). Nhưng mô
# hình hay viết theo kiểu quốc tế `A(1, 2, 3)`, nên nhận cả hai.
_NGAN_CACH = re.compile(r"[;,]")


def _doc_bo_so(s: str) -> list[float] | None:
    """`(1; 2; 3)` hoặc `1, 2, 3` -> [1.0, 2.0, 3.0]. Đọc hỏng thì trả None."""
    tho = (s or "").strip()
    for bo in "()[]{}":
        tho = tho.strip(bo)
    tho = tho.strip()
    if not tho:
        return None
    ra: list[float] = []
    for phan in _NGAN_CACH.split(tho):
        if not phan.strip():
            continue
        gt = _so(sympy_tool.parse(phan))
        if gt is None:
            return None
        ra.append(gt)
    return ra or None


def _he_so_mat_phang(pt: str) -> tuple[float, float, float, float] | None:
    """`x + 2y - 2z + 1 = 0` -> (1, 2, -2, 1).

    Chỉ nhận phương trình BẬC NHẤT. Còn bậc hai (mặt cầu) thì trả None thay vì
    lấy bừa hệ số — đó là loại nhầm khiến phép kiểm tất định thành nguồn báo oan.
    """
    tho = (pt or "").strip()
    if not tho:
        return None
    ve_trai = tho.split("=")[0] if "=" in tho else tho
    try:
        bt = sp.expand(sympy_tool.parse(ve_trai))
        x, y, z = sp.symbols("x y z")
        if any(sp.degree(bt, s) > 1 for s in (x, y, z) if bt.has(s)):
            return None
        a, b, c = (_so(bt.coeff(s)) for s in (x, y, z))
        if None in (a, b, c):
            return None
        d = _so(bt - a * x - b * y - c * z)
    except Exception:  # noqa: BLE001
        return None
    if d is None or (a == 0 and b == 0 and c == 0):
        return None
    return a, b, c, d


# Số dẫn đầu, bóc khỏi đuôi đơn vị.
_SO_DAN_DAU = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)")


def _doc_dap_an_co_don_vi(s: str) -> Any | None:
    """Đọc đáp án hình học, chịu được đuôi đơn vị.

    Đáp số hình học gần như luôn kèm đơn vị, và đơn vị thì muôn hình vạn trạng:
    `20 cm³`, `20 đv³`, `20 đvtt`, `20 đơn vị thể tích`. Liệt kê hết là không khả
    thi, nên làm theo thứ tự: thử parse nguyên văn trước; còn ký hiệu tự do thì
    bóc lấy phần SỐ dẫn đầu.

    ĐO ĐƯỢC vì sao cần: bài thể tích trả `20.0 đv³` khiến `sympy_tool.parse` đọc
    `đv` thành ký hiệu tự do, `_khop` trả None, phép kiểm im lặng bỏ qua — rồi
    Verify rơi xuống hỏi LLM và LLM báo oan một đáp án ĐÚNG.
    """
    tho = (s or "").strip()
    if not tho:
        return None
    try:
        gt = sympy_tool.parse(tho)
        if not getattr(gt, "free_symbols", set()):
            return gt
    except Exception:  # noqa: BLE001
        pass

    khop = _SO_DAN_DAU.match(tho.replace(",", "."))
    if not khop:
        return None
    try:
        return sympy_tool.parse(khop.group(1))
    except Exception:  # noqa: BLE001
        return None


def _kiem_hinh_hoc(
    loai: str, dap_an: str, ham_goc: str, diem: str, diem2: str,
    hinh: str, tham_so: str,
) -> KetQuaKiem:
    """Tính lại đại lượng hình học bằng công thức đóng, rồi đối chiếu đáp án."""
    if loai == "the_tich":
        ten = (hinh or "").strip().lower().replace(" ", "_").replace("-", "_")
        muc = CONG_THUC_HINH.get(ten)
        if muc is None:
            return _khong_kiem_duoc(f"chưa có công thức cho hình '{hinh}'")
        can, tinh = muc
        ts = _doc_bo_so(tham_so)
        if ts is None or len(ts) != can:
            return _khong_kiem_duoc(
                f"hình '{ten}' cần {can} tham số, nhận được {len(ts) if ts else 0}"
            )
        dung = tinh(ts)
        cach = f"thể tích khối {ten} từ tham số {ts}"

    elif loai == "kc_hai_diem":
        a, b = _doc_bo_so(diem), _doc_bo_so(diem2)
        if a is None or b is None or len(a) != len(b) or len(a) not in (2, 3):
            return _khong_kiem_duoc("cần hai điểm cùng số chiều (2 hoặc 3)")
        dung = sp.sqrt(sum((u - v) ** 2 for u, v in zip(a, b)))
        cach = f"khoảng cách giữa {a} và {b}"

    else:  # kc_diem_mp
        mp = _he_so_mat_phang(ham_goc)
        p = _doc_bo_so(diem)
        if mp is None:
            return _khong_kiem_duoc("không đọc được phương trình mặt phẳng bậc nhất")
        if p is None or len(p) != 3:
            return _khong_kiem_duoc("cần toạ độ điểm gồm 3 thành phần")
        a, b, c, d = mp
        # Giá trị tuyệt đối ở tử là chỗ mô hình hay quên, và quên thì ra số ÂM —
        # đúng cái mà `verify_agent._check_hinh_hoc` bắt được.
        dung = sp.Abs(a * p[0] + b * p[1] + c * p[2] + d) / sp.sqrt(a**2 + b**2 + c**2)
        cach = f"khoảng cách từ {p} đến mặt phẳng ({a}, {b}, {c}, {d})"

    da = _doc_dap_an_co_don_vi(dap_an)
    if da is None:
        return _khong_kiem_duoc(f"không đọc được đáp án `{dap_an}`")

    dat = _khop(da, sp.simplify(dung))
    if dat is None:
        return _khong_kiem_duoc("không đối chiếu được đáp án với giá trị tính lại")
    gia_tri = f"{_so(dung):.6g}" if _so(dung) is not None else str(dung)
    return KetQuaKiem(
        dat,
        (f"SymPy tính lại {cach} được {gia_tri}, khớp đáp án."
         if dat else
         f"SymPy tính lại {cach} được {gia_tri} nhưng lời giải ghi `{dap_an}`."),
        gia_tri,
    )


def kiem(
    loai: str,
    dap_an: str,
    ham_goc: str = "",
    bien: str = "x",
    diem: str = "",
    can_duoi: str = "",
    can_tren: str = "",
    diem2: str = "",
    hinh: str = "",
    tham_so: str = "",
) -> KetQuaKiem:
    """Tính lại bài toán bằng SymPy rồi đối chiếu với đáp án của lời giải.

    Mọi tham số đều là chuỗi, vì chúng đến từ đầu ra JSON của mô hình.

    Ba tham số cuối chỉ dùng cho nhóm hình học:
      * `diem2`   — điểm thứ hai của `kc_hai_diem`
      * `hinh`    — tên khối cho `the_tich` (chop, lang_tru, non, tru, cau...)
      * `tham_so` — dãy số cách nhau bằng dấu chấm phẩy, xem `CONG_THUC_HINH`
    """
    loai = (loai or "").strip()
    if loai not in LOAI_KIEM:
        return _khong_kiem_duoc(f"không kiểm được loại '{loai}'")
    if not dap_an.strip():
        return _khong_kiem_duoc("không có đáp án để đối chiếu")

    # Rẽ nhánh phương trình TRƯỚC khi parse đáp án: đáp số ở đó có thể là nhiều
    # nghiệm ("2; 3", "x = 2 hoặc x = 3") — không phải một biểu thức SymPy hợp lệ.
    if loai == "phuong_trinh":
        return _kiem_phuong_trinh(ham_goc, bien, dap_an)

    # Nhóm hình học dùng công thức đóng, không đụng tới `ham_goc` như một hàm số.
    if loai in ("the_tich", "kc_hai_diem", "kc_diem_mp"):
        return _kiem_hinh_hoc(loai, dap_an, ham_goc, diem, diem2, hinh, tham_so)

    try:
        x = sp.Symbol(bien or "x")
        da = sympy_tool.parse(dap_an)
    except Exception as e:  # noqa: BLE001
        return _khong_kiem_duoc(f"không đọc được đáp án: {type(e).__name__}")

    try:
        if not ham_goc.strip():
            return _khong_kiem_duoc("thiếu hàm gốc")
        f = sympy_tool.parse(ham_goc)

        if loai == "dao_ham":
            dung = sp.diff(f, x)
            if diem.strip():
                dung = dung.subs(x, sympy_tool.parse(diem))
        elif loai == "tich_phan":
            if can_duoi.strip() and can_tren.strip():
                dung = sp.integrate(
                    f, (x, sympy_tool.parse(can_duoi), sympy_tool.parse(can_tren))
                )
            else:
                dung = sp.integrate(f, x)
        elif loai == "gioi_han":
            if not diem.strip():
                return _khong_kiem_duoc("thiếu điểm lấy giới hạn")
            moc = sp.oo if diem.strip() in ("oo", "+oo", "inf", "∞") else sympy_tool.parse(diem)
            dung = sp.limit(f, x, moc)
        else:  # tiep_tuyen
            if not diem.strip():
                return _khong_kiem_duoc("thiếu hoành độ tiếp điểm")
            x0 = sympy_tool.parse(diem)
            dung = sp.diff(f, x).subs(x, x0) * (x - x0) + f.subs(x, x0)
    except Exception as e:  # noqa: BLE001
        return _khong_kiem_duoc(f"SymPy không tính được: {type(e).__name__}")

    if dung is sp.nan or (hasattr(dung, "has") and dung.has(sp.zoo)):
        return _khong_kiem_duoc("SymPy cho kết quả không xác định")

    # Đáp án chứa ký hiệu LẠ so với kết quả đúng => nhiều khả năng nó là chữ, không
    # phải biểu thức toán. `parse` biến "tăng dần" thành tích hai ký hiệu `tăng·dần`
    # rồi so với `2` và kết luận SAI — báo oan một lời giải mà ta không hiểu nổi.
    # Không hiểu thì phải im lặng, đừng phán.
    la = getattr(da, "free_symbols", set()) - getattr(dung, "free_symbols", set()) - {x}
    if la:
        return _khong_kiem_duoc(
            f"đáp án chứa ký hiệu lạ ({', '.join(sorted(map(str, la)))}), không đối chiếu được"
        )

    kq = _khop(sp.expand(dung), sp.expand(da))
    if kq is None:
        return _khong_kiem_duoc("không so sánh được hai kết quả")

    dung_str = sp.sstr(sp.simplify(dung))
    if kq:
        return KetQuaKiem(True, f"SymPy tính lại được `{dung_str}`, khớp đáp án.", dung_str)
    return KetQuaKiem(
        False,
        f"SymPy tính lại được `{dung_str}` nhưng lời giải ghi `{dap_an}`.",
        dung_str,
    )


def _kiem_phuong_trinh(phuong_trinh: str, bien: str, nghiem: str) -> KetQuaKiem:
    """Thế nghiệm ngược vào phương trình gốc.

    Đây là phép kiểm mà docstring của `sympy_tool` gọi là quan trọng nhất, và cũng
    là phép kiểm chưa từng được nối vào đâu. Nó không cần giải lại phương trình —
    chỉ cần thế vào và xem hai vế có bằng nhau, nên không bao giờ sai.
    """
    if not phuong_trinh.strip():
        return _khong_kiem_duoc("thiếu phương trình gốc")

    # Đáp án có thể là nhiều nghiệm: "x = 2 hoặc x = 3", "2; 3", "{2, 3}".
    import re

    tho = re.sub(r"[{}]", "", nghiem)
    tho = re.sub(r"\b(x|hoặc|hay|và|or|and)\b", ";", tho, flags=re.I)
    tho = tho.replace("=", ";").replace(",", ";")
    cac_nghiem = [t.strip() for t in tho.split(";") if t.strip()]
    if not cac_nghiem:
        return _khong_kiem_duoc("không tách được nghiệm")

    hong: list[str] = []
    for n in cac_nghiem:
        r = sympy_tool.check_substitution(phuong_trinh, {bien or "x": n})
        if not r.get("ok"):
            return _khong_kiem_duoc(f"không thế được nghiệm `{n}`")
        if not r.get("satisfied"):
            hong.append(n)

    if hong:
        return KetQuaKiem(
            False,
            f"Thế ngược vào phương trình thì nghiệm {', '.join(hong)} KHÔNG thoả mãn.",
        )
    return KetQuaKiem(
        True, f"Thế ngược vào phương trình: mọi nghiệm ({', '.join(cac_nghiem)}) đều thoả mãn."
    )
