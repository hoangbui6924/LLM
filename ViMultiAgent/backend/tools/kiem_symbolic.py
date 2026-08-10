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
)


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


def kiem(
    loai: str,
    dap_an: str,
    ham_goc: str = "",
    bien: str = "x",
    diem: str = "",
    can_duoi: str = "",
    can_tren: str = "",
) -> KetQuaKiem:
    """Tính lại bài toán bằng SymPy rồi đối chiếu với đáp án của lời giải.

    Mọi tham số đều là chuỗi, vì chúng đến từ đầu ra JSON của mô hình.
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
