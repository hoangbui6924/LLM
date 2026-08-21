"""Tự kiểm bộ đề chuẩn — chạy TRƯỚC khi dùng bộ đề để đo bất cứ thứ gì.

Chạy:  python eval/kiem_de_chuan.py

Kiểm ba thứ:

1. **Đáp án khớp công thức.** SymPy tính lại cột `bieu_thuc_kiem` rồi đối chiếu
   với `answer_value` (bài số) hoặc `answer_expr` (bài biểu thức). Lệch là bộ đề
   sai, không phải hệ thống sai.

2. **Đủ trường bắt buộc.** Bài `numeric` phải có `answer_value`, bài `symbolic`
   phải có `answer_expr`, bài `mcq` phải có `answer_choice`.

3. **Không trùng đề.**

Vì sao cần: bộ đề là ground truth. Một đáp án sai ở đây làm bench báo hệ thống
"giải sai" ở bài mà nó giải đúng — và loại lỗi đó gần như không thể lần ra khi
nhìn vào bảng số liệu cuối cùng.

Lưu ý về giới hạn: script này kiểm ĐÁP ÁN CÓ KHỚP CÔNG THỨC ĐÃ GHI hay không.
Nó KHÔNG kiểm được công thức có đúng về mặt Toán học hay không — chuyện đó phải
đọc cột `ghi_chu` mà thẩm định bằng mắt. Hai việc khác nhau, đừng nhầm.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sympy as sp  # noqa: E402

from tools import sympy_tool  # noqa: E402

DE = GOC / "eval" / "data" / "de_chuan.csv"

# Ngưỡng lệch cho phép giữa đáp án lưu và giá trị SymPy tính lại. Đáp án lưu ở
# dạng 6 chữ số có nghĩa nên sai số làm tròn cỡ 1e-6; để 1e-4 là rộng rãi mà vẫn
# bắt được mọi lỗi thật (lỗi thật thường lệch hàng chục phần trăm).
NGUONG = 1e-4


def kiem_mot(dong: dict) -> list[str]:
    loi: list[str] = []
    loai = (dong.get("question_type") or "numeric").strip()
    bt = (dong.get("bieu_thuc_kiem") or "").strip()
    gt = (dong.get("answer_value") or "").strip()
    be = (dong.get("answer_expr") or "").strip()
    ac = (dong.get("answer_choice") or "").strip()

    if not (dong.get("question") or "").strip():
        loi.append("thiếu đề bài")

    if loai == "numeric" and not gt:
        loi.append("bài numeric nhưng thiếu answer_value")
    if loai == "symbolic" and not be:
        loi.append("bài symbolic nhưng thiếu answer_expr")
    if loai == "mcq" and not ac:
        loi.append("bài mcq nhưng thiếu answer_choice")

    if not bt:
        loi.append("thiếu bieu_thuc_kiem, không tự kiểm được")
        return loi

    kq = sympy_tool.evaluate(bt)
    if not kq.get("ok"):
        loi.append(f"SymPy không đọc được bieu_thuc_kiem: {kq.get('error', '')[:60]}")
        return loi

    if loai == "symbolic":
        # So bằng rút gọn tượng trưng: `-x + 7` và `-(x-2) + 5` phải tính là một.
        so = sympy_tool.are_equivalent(bt, be)
        if not so.get("ok"):
            loi.append(f"không so được biểu thức: {so.get('error', '')[:60]}")
        elif not so.get("equivalent"):
            loi.append(f"answer_expr `{be}` KHÔNG tương đương bieu_thuc_kiem `{bt}`")
        return loi

    tinh = kq.get("numeric")
    if tinh is None:
        loi.append(f"bieu_thuc_kiem `{bt}` không quy được về một số")
        return loi

    try:
        luu = float(gt)
    except ValueError:
        loi.append(f"answer_value `{gt}` không phải số")
        return loi

    thang = max(1e-9, abs(tinh))
    lech = abs(tinh - luu) / thang
    if lech > NGUONG:
        loi.append(
            f"LỆCH ĐÁP ÁN: lưu {luu:.10g} nhưng công thức `{bt}` cho {tinh:.10g} "
            f"(lệch {lech * 100:.4f}%)"
        )
    return loi


def main() -> int:
    if not DE.exists():
        print(f"Không thấy bộ đề: {DE}")
        print("Chạy `python eval/build_de_chuan.py` trước.")
        return 2

    with DE.open(encoding="utf-8-sig", newline="") as f:
        cac_dong = list(csv.DictReader(f))

    print(f"Bộ đề: {DE}")
    print(f"Số bài: {len(cac_dong)}\n")

    hong: list[tuple[str, list[str]]] = []
    for d in cac_dong:
        loi = kiem_mot(d)
        if loi:
            hong.append((d.get("id", "?"), loi))

    # Trùng đề
    thay: dict[str, str] = {}
    trung: list[tuple[str, str]] = []
    for d in cac_dong:
        cau = (d.get("question") or "").strip()
        if cau in thay:
            trung.append((thay[cau], d.get("id", "?")))
        else:
            thay[cau] = d.get("id", "?")

    # Thống kê phân bố
    print("Phân bố theo môn và mức độ:")
    mon_muc: dict[tuple[str, str], int] = {}
    chu_de: dict[str, set[str]] = {}
    for d in cac_dong:
        k = (d.get("subject", "?"), d.get("level", "?"))
        mon_muc[k] = mon_muc.get(k, 0) + 1
        chu_de.setdefault(d.get("subject", "?"), set()).add(d.get("topic", ""))
    for mon in ("dai_so", "hinh_hoc"):
        phan = "  ".join(
            f"{mu} {mon_muc.get((mon, mu), 0):2}" for mu in ("NB", "TH", "VD", "VDC")
        )
        tong = sum(v for (m, _), v in mon_muc.items() if m == mon)
        print(f"  {mon:<10} tổng {tong:3}   {phan}   ({len(chu_de.get(mon, set()))} chủ đề)")

    print()
    if trung:
        print(f"CẢNH BÁO — {len(trung)} cặp đề trùng nhau:")
        for a, b in trung[:10]:
            print(f"  {a} == {b}")
        print()

    if hong:
        print("=" * 66)
        print(f"CÓ LỖI — {len(hong)}/{len(cac_dong)} bài không đạt")
        print("=" * 66)
        for ma, loi in hong:
            print(f"\n  [{ma}]")
            for l in loi:
                print(f"    - {l}")
        print("\nSỬA XONG RỒI HÃY DÙNG BỘ ĐỀ NÀY ĐỂ ĐO.")
        return 1

    print("=" * 66)
    print(f"ĐẠT — {len(cac_dong)}/{len(cac_dong)} bài có đáp án khớp công thức")
    print("=" * 66)
    print("\nNhắc lại giới hạn: script chỉ xác nhận đáp án khớp CÔNG THỨC ĐÃ GHI.")
    print("Việc công thức có đúng Lý/Hoá hay không thì phải đọc cột ghi_chu mà thẩm định.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
