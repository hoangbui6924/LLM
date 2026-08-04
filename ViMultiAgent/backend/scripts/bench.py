"""Đo hiệu năng thật của cả luồng — số liệu cho phần đánh giá hệ thống.

Chạy:  python scripts/bench.py            (3 bài mẫu, mỗi môn một bài)
       python scripts/bench.py --n 2      (lặp 2 lượt để lấy trung bình)

In ra thời gian từng agent, tổng thời gian, và có đạt mốc 45 giây không —
đúng ba tiêu chí đánh giá nêu ở cuối yeucaumoi.md.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Console Windows mặc định cp1252, không in nổi tiếng Việt có dấu.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents import manager  # noqa: E402
from core import config  # noqa: E402

# Mỗi bài kèm ĐÁP SỐ ĐÚNG đã tự giải tay, để chấm tự động thay vì nhìn bằng mắt.
#   Toán: y' = 3x^2 - 6x + 2, tại x = 1 -> 3 - 6 + 2 = -1
#   Lý  : v_max = A*omega = 0,05 * 2*pi*2 = 0,6283 m/s
#   Hoá : n(Fe) = 5,6/56 = 0,1 mol; 3Fe + 2O2 -> Fe3O4 nên n(Fe3O4) = 0,1/3;
#         m = 0,1/3 * 232 = 7,733 gam
BAI_MAU = [
    ("Toán", "Tính đạo hàm của hàm số y = x^3 - 3x^2 + 2x tại điểm x = 1", -1.0),
    ("Lý", "Một vật dao động điều hoà với biên độ A = 5 cm và tần số f = 2 Hz. "
           "Tính vận tốc cực đại của vật.", 0.6283185307),
    ("Hoá", "Đốt cháy hoàn toàn 5,6 gam Fe trong khí O2 dư thu được Fe3O4. "
            "Tính khối lượng Fe3O4 thu được.", 7.7333333),
]

# Dung sai 2%: chấp nhận model làm tròn 0,6283 thành 0,63 hay 7,733 thành 7,73.
DUNG_SAI = 0.02


def _doc_so(s: str) -> float | None:
    """Bóc số ra khỏi chuỗi đáp số có thể kèm đơn vị: '7,73 gam' -> 7.73."""
    import re
    if not s:
        return None
    s = re.sub(r"(?<=\d),(?=\d)", ".", s.strip())
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
    return float(m.group(0)) if m else None


def cham(dap_an: str, dung: float) -> bool:
    v = _doc_so(dap_an)
    if v is None:
        return False
    return abs(v - dung) <= DUNG_SAI * max(1.0, abs(dung))


async def chay_mot_bai(mon: str, cau_hoi: str, dap_an_dung: float) -> dict:
    t0 = time.perf_counter()
    moc: list[tuple[str, float]] = []
    dap_an = ""
    verdict = ""
    tokens = 0

    async for ev in manager.solve_stream(cau_hoi):
        if ev["type"] == "agent" and ev["status"] == "done":
            moc.append((ev["label"], ev.get("ms", 0) / 1000.0))
            if ev["name"].endswith("_agent") and ev["name"] not in (
                "verify_agent",
                "explain_agent",
            ):
                dap_an = ev.get("detail", "")
            if ev["name"] == "verify_agent":
                verdict = ev.get("verdict", "")
        elif ev["type"] == "token":
            tokens += 1

    tong = time.perf_counter() - t0
    return {
        "mon": mon,
        "dung": cham(dap_an, dap_an_dung),
        "dap_an_dung": dap_an_dung,
        "tong_s": tong,
        "dat_sla": tong <= config.SLA_SECONDS,
        "dap_an": dap_an,
        "verdict": verdict,
        "moc": moc,
        "so_chunk_stream": tokens,
    }


async def main(n: int) -> int:
    print(f"Model: {config.MODEL_HEAVY} (heavy) / {config.MODEL_LIGHT} (light)")
    print(f"Mốc KPI: {config.SLA_SECONDS:.0f} giây\n")

    ket_qua = []
    for lap in range(n):
        for mon, cau, dung in BAI_MAU:
            r = await chay_mot_bai(mon, cau, dung)
            ket_qua.append(r)
            dat = "ĐẠT" if r["dat_sla"] else "TRƯỢT"
            cx = "ĐÚNG" if r["dung"] else "SAI "
            print(f"[{mon}] {cx} — {r['tong_s']:.1f}s {dat} — Verify: {r['verdict'] or '?'}")
            print(f"      Đáp án: {r['dap_an'][:60]}   (đúng: {dung:g})")
            for ten, giay in r["moc"]:
                print(f"        {ten:<18} {giay:5.1f}s")
            print()

    tong = [r["tong_s"] for r in ket_qua]
    dat = sum(1 for r in ket_qua if r["dat_sla"])
    pas = sum(1 for r in ket_qua if r["verdict"] == "PASS")
    dung_n = sum(1 for r in ket_qua if r["dung"])
    print("-" * 56)
    print(f"Số lượt      : {len(ket_qua)}")
    print(f"Trung bình   : {sum(tong) / len(tong):.1f}s")
    print(f"Nhanh nhất   : {min(tong):.1f}s")
    print(f"Chậm nhất    : {max(tong):.1f}s")
    print(f"Đạt mốc 45s  : {dat}/{len(ket_qua)}")
    print(f"Verify PASS  : {pas}/{len(ket_qua)}")
    print(f"ĐÁP SỐ ĐÚNG  : {dung_n}/{len(ket_qua)}")
    print()
    for mon in ("Toán", "Lý", "Hoá"):
        m = [r for r in ket_qua if r["mon"] == mon]
        if m:
            print(f"  {mon:<5} {sum(1 for r in m if r['dung'])}/{len(m)} đúng")
    return 0 if dat == len(ket_qua) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="số lượt lặp")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.n)))
