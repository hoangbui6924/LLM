"""Chọn ngưỡng vận hành cho ViSTEM-PRM từ điểm số trên tập validation.

    python -m vimultiagent.models.prm.tune_threshold

Vì sao cần script riêng: F1 báo trong lúc huấn luyện dùng ngưỡng mặc định 0,5 (argmax).
Nhưng ngưỡng vận hành đúng KHÔNG phải 0,5, vì hai loại sai có giá đắt khác nhau, và
vì T0 nằm trước T2/T3 chứ không phải phán quyết cuối.

Script quét toàn dải ngưỡng và in ra bảng đánh đổi để CHỌN CÓ CƠ SỞ, thay vì đoán.
Đường cong này nên đưa vào báo cáo — nó cho thấy quyết định kỹ thuật được ra bằng số.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CKPT = ROOT / "checkpoints" / "prm"
REPORTS = ROOT / "eval" / "reports"


def prf(probs: np.ndarray, labels: np.ndarray, thr: float) -> dict[str, float]:
    """'Positive' = BƯỚC SAI. Bác bỏ khi P(đúng) < thr."""
    flagged = probs < thr
    wrong = labels == 0
    tp = int((flagged & wrong).sum())
    fp = int((flagged & ~wrong).sum())
    fn = int((~flagged & wrong).sum())
    tn = int((~flagged & ~wrong).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": round(thr, 3), "precision": round(prec, 4),
            "recall": round(rec, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main() -> None:
    f = CKPT / "val_scores.npz"
    if not f.exists():
        raise SystemExit(f"Chưa có {f}. Chạy: python -m vimultiagent.models.prm.train")
    d = np.load(f)
    probs, labels = d["probs"], d["labels"]
    print(f"Tập validation: {len(labels)} bước "
          f"({int((labels == 0).sum())} sai, {int((labels == 1).sum())} đúng)\n")

    grid = [round(x, 3) for x in np.arange(0.05, 0.96, 0.05)]
    rows = [prf(probs, labels, t) for t in grid]

    print(f"{'ngưỡng':>8}{'precision':>11}{'recall':>9}{'F1':>8}{'báo oan':>10}{'bỏ sót':>9}")
    print("-" * 55)
    for r in rows:
        print(f"{r['threshold']:>8.2f}{r['precision']:>11.3f}{r['recall']:>9.3f}"
              f"{r['f1']:>8.3f}{r['fp']:>10}{r['fn']:>9}")

    best_f1 = max(rows, key=lambda r: r["f1"])

    # Ngưỡng vận hành: F1 cao nhất, với SÀN PRECISION 0,97.
    #
    # Vì sao ưu tiên precision mạnh đến vậy — con số đo được, không phải cảm tính:
    # một lần T0 báo oan sẽ kích hoạt một vòng repair, và vòng repair khiến Solver
    # chạy lại. Đo trên tập 30 bài: mỗi vòng repair thừa cộng thêm ~60 giây vào độ
    # trễ. Bỏ sót thì rẻ hơn nhiều, vì T2/T3 phía sau vẫn còn cơ hội bắt.
    ok = [r for r in rows if r["precision"] >= 0.97]
    recommended = max(ok, key=lambda r: r["f1"]) if ok else best_f1

    print(f"\nF1 cao nhất       : ngưỡng {best_f1['threshold']:.2f} "
          f"(P={best_f1['precision']:.3f} R={best_f1['recall']:.3f} F1={best_f1['f1']:.3f})")
    print(f"KHUYẾN NGHỊ dùng  : ngưỡng {recommended['threshold']:.2f} "
          f"(P={recommended['precision']:.3f} R={recommended['recall']:.3f})")
    print(f"\n→ Đặt vào configs/app.yaml:  prm.reject_threshold: {recommended['threshold']}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "prm_threshold_sweep.json"
    out.write_text(
        json.dumps({"sweep": rows, "best_f1": best_f1, "recommended": recommended},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Đã ghi: {out}")


if __name__ == "__main__":
    main()
