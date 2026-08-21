"""Báo cáo tiến độ một chiến dịch bench đang chạy.

Chạy:  python scripts/tien_do.py <đường dẫn file log của bench>

Đọc dòng kết quả từng lượt mà bench in ra, tính accuracy tạm thời, phân bố thời
gian, chia theo môn và mức độ, rồi ước tính thời gian còn lại.

Gom thành script riêng thay vì gõ `python -c` mỗi lần vì hai lý do: lệnh cố định
thì cấp quyền một lần là xong (vòng lặp báo cáo hằng giờ chạy được lúc không có
ai ngồi máy), và logic phân tích không bị chép lại mỗi lần một khác.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Dòng bench in ra:  [ 23/100] Đại số VD  ds_vd_016    ĐÚNG   66.7s  PASS  '...'
DONG = re.compile(
    r"\[\s*(\d+)/(\d+)\]\s+\S+\s+(\S+)\s+(\w+?)_\w+?_\w*?(\d+)\s+(ĐÚNG|SAI)\s+([\d.]+)s\s+(\S*)"
)

TEN_MON = {"ds": "Đại số", "hh": "Hình học"}
MUC = ("NB", "TH", "VD", "VDC")


def doc(duong_dan: Path) -> tuple[list[dict], int]:
    rows: list[dict] = []
    tong = 0
    for dong in duong_dan.read_text(encoding="utf-8", errors="replace").splitlines():
        m = DONG.match(dong)
        if not m:
            continue
        tong = int(m.group(2))
        rows.append(
            {
                "muc": m.group(3),
                "mon": m.group(4),
                "dung": m.group(6) == "ĐÚNG",
                "giay": float(m.group(7)),
                "verdict": m.group(8),
            }
        )
    return rows, tong


def ti_le(tu: int, mau: int) -> str:
    return f"{tu:3}/{mau:<3} = {tu / mau * 100:5.1f}%" if mau else "  —  "


def main(duong_dan: Path) -> int:
    if not duong_dan.exists():
        print(f"Không thấy file: {duong_dan}")
        return 2

    rows, tong = doc(duong_dan)
    xong = "Đã ghi chi tiết" in duong_dan.read_text(encoding="utf-8", errors="replace")

    if not rows:
        print("Chưa có lượt nào hoàn thành.")
        return 0

    n = len(rows)
    tong = tong or n
    tb = sum(r["giay"] for r in rows) / n
    dung = sum(r["dung"] for r in rows)

    print(f"TIẾN ĐỘ  : {n}/{tong}  ({n / tong * 100:.0f}%)", end="")
    print("   >>> ĐÃ XONG <<<" if xong else f"   còn ~{(tong - n) * tb / 60:.0f} phút")
    print(f"Accuracy : {ti_le(dung, n)}")
    print(
        f"Thời gian: tb {tb:5.1f}s | max {max(r['giay'] for r in rows):5.1f}s"
        f" | đạt 45s {sum(1 for r in rows if r['giay'] <= 45)}/{n}"
    )

    print("\nTheo môn:")
    for k, ten in TEN_MON.items():
        g = [r for r in rows if r["mon"] == k]
        if g:
            tbm = sum(r["giay"] for r in g) / len(g)
            print(f"  {ten:<5} {ti_le(sum(r['dung'] for r in g), len(g))}   tb {tbm:5.1f}s")

    print("\nTheo mức độ:")
    for k in MUC:
        g = [r for r in rows if r["muc"] == k]
        if g:
            print(f"  {k:<4} {ti_le(sum(r['dung'] for r in g), len(g))}")

    # Ma trận rút gọn: Verify có bắt được lời giải sai không.
    sai = [r for r in rows if not r["dung"]]
    dung_r = [r for r in rows if r["dung"]]
    if sai:
        bat = sum(1 for r in sai if r["verdict"] == "FAIL")
        oan = sum(1 for r in dung_r if r["verdict"] == "FAIL")
        print("\nVerify (tạm thời, chấm trên đáp án cuối):")
        print(f"  Bắt được lời giải sai: {ti_le(bat, len(sai))}")
        print(f"  Báo oan lời giải đúng: {ti_le(oan, len(dung_r))}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng: python scripts/tien_do.py <file log của bench>")
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))
