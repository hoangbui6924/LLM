"""Thu thập lời giảng để giáo viên chấm — bước 1 của chỉ số 2.

Chạy:
    python eval/thu_loi_giang.py                          20 bài, bộ đề chuẩn
    python eval/thu_loi_giang.py --so-bai 30 --de <csv>

Vì sao cần script riêng thay vì lấy từ kết quả bench
----------------------------------------------------
Bench chỉ ghi `explain_s` (thời gian), KHÔNG ghi nội dung lời giảng. Mà chỉ số 2
chấm đúng cái nội dung đó.

Quan trọng hơn: bench chạy dưới ngân sách thời gian nên Explain bị cắt khi hết giờ.
ĐO ĐƯỢC trên 150 bài: 81 bài (54%) chạm đúng trần token, tức lời giảng đứt giữa
chừng. Đem bài giảng cụt cho giáo viên chấm thì điểm thấp là do PHÉP ĐO hỏng, không
phải do hệ thống giảng dở.

Script này vì vậy đặt SLA rất rộng để Explain chạy trọn vẹn. Đây là lựa chọn có chủ
đích: chỉ số 2 đo CHẤT LƯỢNG lời giảng, chỉ số 4 mới đo tốc độ. Trộn hai thứ vào
một phép đo thì hỏng cả hai.
"""

from __future__ import annotations

import os

# Phải đặt TRƯỚC khi import core.config, vì config đọc env lúc nạp module.
# 600 giây để Explain không bao giờ bị cắt giữa chừng.
os.environ.setdefault("VMA_SLA_SECONDS", "600")

import argparse  # noqa: E402
import asyncio  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents import manager  # noqa: E402
from core import config, db  # noqa: E402

DE_MAC_DINH = GOC / "eval" / "data" / "de_chuan.csv"
RA_MAC_DINH = GOC / "eval" / "phieu_cham" / "loi_giang.jsonl"


def lay_mau(duong_dan: Path, so_bai: int, seed: int) -> list[dict]:
    """Lấy mẫu PHÂN TẦNG theo môn và mức độ.

    Chọn bừa thì dễ ra toàn bài dễ hoặc lệch môn, và điểm giáo viên chấm sẽ không
    đại diện cho gì cả.
    """
    with duong_dan.open(encoding="utf-8-sig", newline="") as f:
        tat_ca = [r for r in csv.DictReader(f) if (r.get("question") or "").strip()]

    r = random.Random(seed)
    nhom: dict[tuple[str, str], list[dict]] = {}
    for bai in tat_ca:
        nhom.setdefault((bai["subject"], bai["level"]), []).append(bai)
    for v in nhom.values():
        r.shuffle(v)

    # Rải đều: đi vòng qua từng nhóm, mỗi vòng lấy một bài.
    ra: list[dict] = []
    khoa = sorted(nhom)
    while len(ra) < so_bai and any(nhom[k] for k in khoa):
        for k in khoa:
            if len(ra) >= so_bai:
                break
            if nhom[k]:
                ra.append(nhom[k].pop())
    return ra


async def chay_mot(bai: dict) -> dict:
    t0 = time.perf_counter()
    chunks: list[str] = []
    ket: dict = {}
    loi = ""
    try:
        async for ev in manager.solve_stream(bai["question"]):
            if ev["type"] == "token":
                chunks.append(ev["text"])
            elif ev["type"] == "done":
                ket = ev.get("result") or {}
            elif ev["type"] == "error":
                loi = ev.get("message", "")
    except Exception as e:  # noqa: BLE001
        loi = f"{type(e).__name__}: {e}"

    sol = (ket.get("solution") or {}) if ket else {}
    ver = (ket.get("verify") or {}) if ket else {}
    loi_giang = "".join(chunks)

    return {
        "id": bai["id"],
        "subject": bai["subject"],
        "topic": bai.get("topic", ""),
        "level": bai.get("level", ""),
        "question": bai["question"],
        "dap_an_he_thong": (sol.get("final_answer") or "").strip(),
        "dap_an_chuan": (bai.get("answer_value") or bai.get("answer_expr") or "")
        + ((" " + bai["answer_unit"]) if bai.get("answer_unit") else ""),
        "verdict": ver.get("verdict", ""),
        "loi_giang": loi_giang,
        "so_ky_tu": len(loi_giang),
        "bi_cat": "Hết ngân sách thời gian" in loi_giang,
        "giay": round(time.perf_counter() - t0, 1),
        "nguon": "he_thong",
        "loi": loi,
    }


async def main(args: argparse.Namespace) -> int:
    de = Path(args.de) if args.de else DE_MAC_DINH
    if not de.is_absolute():
        de = GOC / de
    if not de.exists():
        print(f"Không thấy bộ đề: {de}")
        return 2

    mau = lay_mau(de, args.so_bai, args.seed)
    print(f"Bộ đề : {de.name}")
    print(f"Lấy mẫu: {len(mau)} bài (phân tầng theo môn và mức độ)")
    print(f"SLA    : {config.SLA_SECONDS:.0f}s — nới rộng để lời giảng KHÔNG bị cắt")
    print(f"Model  : {config.MODEL_HEAVY}\n")

    try:
        db.init()
    except Exception:  # noqa: BLE001
        pass

    ra = Path(args.ra) if args.ra else RA_MAC_DINH
    ra.parent.mkdir(parents=True, exist_ok=True)

    ket_qua: list[dict] = []
    with ra.open("w", encoding="utf-8") as f:
        for i, bai in enumerate(mau, start=1):
            r = await chay_mot(bai)
            ket_qua.append(r)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            cat = "  [BỊ CẮT]" if r["bi_cat"] else ""
            print(
                f"[{i:3}/{len(mau)}] {r['subject']:<10} {r['level']:<4} {r['id']:<16}"
                f" {r['giay']:6.1f}s  {r['so_ky_tu']:5} ký tự{cat}"
            )
            if r["loi"]:
                print(f"          lỗi: {r['loi'][:70]}")

    bi_cat = sum(1 for r in ket_qua if r["bi_cat"])
    rong = sum(1 for r in ket_qua if not r["loi_giang"].strip())
    print(f"\nĐã ghi {len(ket_qua)} lời giảng -> {ra}")
    print(f"  Bị cắt giữa chừng : {bi_cat}/{len(ket_qua)}")
    print(f"  Rỗng              : {rong}/{len(ket_qua)}")
    if bi_cat:
        print("  CẢNH BÁO: lời giảng bị cắt không nên đem chấm — nới VMA_MAX_TOKENS_EXPLAIN.")
    print("\nBước tiếp: python eval/phieu_cham.py xuat")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Thu thập lời giảng cho giáo viên chấm")
    ap.add_argument("--de", help="CSV bộ đề")
    ap.add_argument("--so-bai", type=int, default=20)
    ap.add_argument("--ra", help="file JSONL đầu ra")
    ap.add_argument("--seed", type=int, default=20260806)
    raise SystemExit(asyncio.run(main(ap.parse_args())))
