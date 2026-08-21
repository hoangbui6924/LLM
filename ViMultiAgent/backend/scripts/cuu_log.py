"""Cứu kết quả từ log của một lượt bench bị dừng giữa chừng.

    python scripts/cuu_log.py <file log> [--ra <csv>]

Vì sao cần: `bench.py` chỉ ghi CSV KHI CHẠY XONG. Dừng ngang — vì mất điện, vì
phải tắt máy, vì bấm nhầm — là mất trắng mọi bài đã chạy, dù chúng đã in ra màn
hình. Script này đọc lại phần đã in và dựng thành CSV.

Cứu được: mã bài, môn, mức độ, đúng/sai, verdict, tổng thời gian, đáp án.
KHÔNG cứu được: thời gian từng vai, đáp án trước bước cứu, cờ đã cứu — những thứ
đó chỉ có trong bộ nhớ tiến trình.

Nói cách khác đây là bản vớt vát, không thay được lượt chạy trọn vẹn. Nhưng nó đủ
cho ba chỉ số chính, và hơn hẳn con số không.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# [ 42/200] Hình học VDC hh_vdc_k041  SAI   178.5s  PASS      '4.1'  [VƯỢT SLA]
DONG = re.compile(
    r"\[\s*(\d+)/(\d+)\]\s+(\S+)\s+(\S+)\s+(\S+)\s+(ĐÚNG|SAI)\s+([\d.]+)s\s+(\S*)\s*(?:'(.*?)')?"
)

MON = {"Đại số": "dai_so", "Hình học": "hinh_hoc"}
COT = ["stt", "id", "subject", "level", "dung", "verdict", "tong_s",
       "dat_45s", "dap_an_he_thong"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Cứu kết quả bench từ log")
    ap.add_argument("log")
    ap.add_argument("--ra")
    a = ap.parse_args()

    log = Path(a.log)
    if not log.exists():
        print(f"Không thấy: {log}")
        return 2

    dong: list[dict] = []
    tong = 0
    for l in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = DONG.match(l)
        if not m:
            continue
        tong = int(m.group(2))
        giay = float(m.group(7))
        dong.append({
            "stt": int(m.group(1)),
            "id": m.group(5),
            "subject": MON.get(m.group(3), m.group(3)),
            "level": m.group(4),
            "dung": int(m.group(6) == "ĐÚNG"),
            "verdict": m.group(8),
            "tong_s": f"{giay:.2f}",
            "dat_45s": int(giay <= 45.0),
            "dap_an_he_thong": m.group(9) or "",
        })

    if not dong:
        print("Không đọc được dòng kết quả nào.")
        return 2

    ra = Path(a.ra) if a.ra else (
        Path(__file__).resolve().parents[1] / "eval" / "reports"
        / f"cuu_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    )
    ra.parent.mkdir(parents=True, exist_ok=True)
    with ra.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COT)
        w.writeheader()
        w.writerows(dong)

    d = sum(r["dung"] for r in dong)
    print(f"Cứu được {len(dong)}/{tong} bài -> {ra}")
    print(f"  Accuracy    : {d}/{len(dong)} = {d / len(dong) * 100:.1f}%")
    print(f"  Thời gian TB: {sum(float(r['tong_s']) for r in dong) / len(dong):.1f}s")
    print()
    for mon, ten in (("dai_so", "Đại số"), ("hinh_hoc", "Hình học")):
        g = [r for r in dong if r["subject"] == mon]
        if g:
            print(f"  {ten:<5} {sum(r['dung'] for r in g):3}/{len(g):<4}"
                  f" tb {sum(float(r['tong_s']) for r in g) / len(g):6.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
