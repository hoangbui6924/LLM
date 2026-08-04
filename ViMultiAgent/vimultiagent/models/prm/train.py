"""Huấn luyện ViSTEM-PRM — bộ phân loại bước giải đúng/sai.

    python -m vimultiagent.models.prm.train --epochs 3 --batch-size 16

Kiến trúc: encoder Transformer + đầu phân loại nhị phân. Đầu vào là
`ĐỀ [SEP] các bước trước [SEP] bước đang xét`, đầu ra là xác suất bước đó ĐÚNG.

Hai quyết định huấn luyện đáng nói trong báo cáo:

1. **Trọng số lớp.** Dữ liệu lệch ~79/21 nghiêng về bước đúng. Không cân lại thì
   model học được 79% accuracy chỉ bằng cách nói "đúng" với mọi thứ — vô dụng,
   vì việc duy nhất ta cần nó làm là bắt lỗi.

2. **Chia tập theo NGUỒN, không theo dòng.** Các mẫu sinh từ cùng một lời giải
   dùng chung tiền tố. Chia ngẫu nhiên theo dòng sẽ làm rò rỉ và cho ra điểm val
   đẹp nhưng giả.

Ngân sách VRAM (RTX 3060 Laptop 6 GB):
   phobert-base (135M) · batch 16 · seq 256 · AMP  ->  ~3 GB   ✅
   xlm-roberta-base (278M) · batch 8 · grad-accum 2 ->  ~5 GB   ⚠ sát
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from .data_build import INPUT_FORMAT

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "eval" / "datasets" / "prm"
CKPT = ROOT / "checkpoints" / "prm"
REPORTS = ROOT / "eval" / "reports"


class StepDataset(Dataset):
    def __init__(self, path: Path, tokenizer: Any, max_length: int = 256) -> None:
        self.rows = [
            json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()
        ]
        self.tok = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int) -> dict[str, Any]:
        r = self.rows[i]
        enc = self.tok(
            r["text"], truncation=True, max_length=self.max_length,
            padding="max_length", return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"][0],
            "attention_mask": enc["attention_mask"][0],
            "labels": torch.tensor(r["label"], dtype=torch.long),
        }


@torch.no_grad()
def evaluate(model: Any, loader: DataLoader, device: str, rows: list[dict]) -> dict[str, Any]:
    model.eval()
    probs_all: list[float] = []
    labels_all: list[int] = []
    for batch in loader:
        ids = batch["input_ids"].to(device)
        mask = batch["attention_mask"].to(device)
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(device == "cuda")):
            logits = model(input_ids=ids, attention_mask=mask).logits
        p = torch.softmax(logits.float(), dim=-1)[:, 1]
        probs_all.extend(p.cpu().tolist())
        labels_all.extend(batch["labels"].tolist())

    probs = np.array(probs_all)
    labels = np.array(labels_all)
    preds = (probs >= 0.5).astype(int)

    # "Positive" của chỉ số dưới đây = BƯỚC SAI (label 0). Đó mới là thứ ta quan tâm:
    # bắt được bao nhiêu phần trăm bước sai, và có báo oan nhiều không.
    tp = int(((preds == 0) & (labels == 0)).sum())
    fp = int(((preds == 0) & (labels == 1)).sum())
    fn = int(((preds == 1) & (labels == 0)).sum())
    tn = int(((preds == 1) & (labels == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    # Phân rã theo loại lỗi — bảng giá trị nhất cho báo cáo: PRM giỏi bắt lỗi gì,
    # dở bắt lỗi gì. Kết quả này định hướng cả phần phân tích lỗi.
    by_type: dict[str, dict[str, Any]] = {}
    for i, r in enumerate(rows):
        if r["label"] != 0:
            continue
        mt = r.get("mutation_type") or "unknown"
        by_type.setdefault(mt, {"n": 0, "caught": 0})
        by_type[mt]["n"] += 1
        by_type[mt]["caught"] += int(preds[i] == 0)
    for mt, v in by_type.items():
        v["recall"] = round(v["caught"] / v["n"], 4) if v["n"] else 0.0

    return {
        "accuracy": round(float((preds == labels).mean()), 4),
        "error_precision": round(prec, 4),
        "error_recall": round(rec, 4),
        "error_f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "recall_by_mutation": by_type,
        "probs": probs, "labels": labels,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="vinai/phobert-base-v2")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(CKPT))
    args = ap.parse_args()

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Thiết bị: {device}"
          + (f" | {torch.cuda.get_device_name(0)}" if device == "cuda" else ""))
    print(f"Model nền: {args.base}")

    try:
        tok = AutoTokenizer.from_pretrained(args.base)
    except Exception:  # noqa: BLE001
        tok = AutoTokenizer.from_pretrained(args.base, use_fast=False)

    train_ds = StepDataset(DATA / "train.jsonl", tok, args.max_length)
    val_ds = StepDataset(DATA / "val.jsonl", tok, args.max_length)
    print(f"Train {len(train_ds)} | Val {len(val_ds)}")

    counts = Counter(r["label"] for r in train_ds.rows)
    total = sum(counts.values())
    # weight[c] tỉ lệ nghịch với tần suất lớp c -> lớp "bước sai" (hiếm) được đền bù
    weights = torch.tensor(
        [total / (2 * counts.get(0, 1)), total / (2 * counts.get(1, 1))],
        dtype=torch.float, device=device,
    )
    print(f"Phân bố nhãn: {dict(counts)} | trọng số lớp: {weights.tolist()}")

    model = AutoModelForSequenceClassification.from_pretrained(args.base, num_labels=2).to(device)

    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size * 2, shuffle=False, num_workers=0)

    optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = (len(train_dl) // args.grad_accum) * args.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(
        optim, max_lr=args.lr, total_steps=max(steps, 1), pct_start=0.1
    )
    scaler = torch.amp.GradScaler("cuda", enabled=(device == "cuda"))
    loss_fn = nn.CrossEntropyLoss(weight=weights)

    history: list[dict[str, Any]] = []
    best_f1 = -1.0
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for ep in range(1, args.epochs + 1):
        model.train()
        t0, running = time.time(), 0.0
        optim.zero_grad(set_to_none=True)
        for i, batch in enumerate(train_dl):
            ids = batch["input_ids"].to(device, non_blocking=True)
            mask = batch["attention_mask"].to(device, non_blocking=True)
            y = batch["labels"].to(device, non_blocking=True)

            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(device == "cuda")):
                logits = model(input_ids=ids, attention_mask=mask).logits
                loss = loss_fn(logits.float(), y) / args.grad_accum

            scaler.scale(loss).backward()
            running += loss.item() * args.grad_accum

            if (i + 1) % args.grad_accum == 0:
                scaler.unscale_(optim)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optim)
                scaler.update()
                optim.zero_grad(set_to_none=True)
                if sched.last_epoch < steps - 1:
                    sched.step()

            if (i + 1) % 100 == 0:
                print(f"  ep{ep} [{i + 1}/{len(train_dl)}] loss {running / (i + 1):.4f}")

        m = evaluate(model, val_dl, device, val_ds.rows)
        m["epoch"] = ep
        m["train_loss"] = round(running / max(len(train_dl), 1), 4)
        m["seconds"] = round(time.time() - t0, 1)
        probs, labels = m.pop("probs"), m.pop("labels")
        history.append(m)

        print(f"\nEpoch {ep} ({m['seconds']}s) loss={m['train_loss']:.4f} "
              f"acc={m['accuracy']:.4f} | BẮT LỖI: P={m['error_precision']:.4f} "
              f"R={m['error_recall']:.4f} F1={m['error_f1']:.4f}")
        for mt, v in sorted(m["recall_by_mutation"].items(), key=lambda x: -x[1]["n"]):
            print(f"    {mt:<12} recall {v['recall']:.3f}  ({v['caught']}/{v['n']})")

        if m["error_f1"] > best_f1:
            best_f1 = m["error_f1"]
            model.save_pretrained(out_dir)
            tok.save_pretrained(out_dir)
            np.savez(out_dir / "val_scores.npz", probs=probs, labels=labels)
            print(f"  ✓ Lưu checkpoint tốt nhất (F1={best_f1:.4f}) -> {out_dir}")

    (out_dir / "training_meta.json").write_text(
        json.dumps(
            {"base_model": args.base, "epochs": args.epochs, "batch_size": args.batch_size,
             "lr": args.lr, "max_length": args.max_length, "best_error_f1": best_f1,
             # Suy luận đọc lại trường này để dựng đầu vào ĐÚNG định dạng checkpoint
             # đã học. Thiếu nó, infer.py mặc định "v1" — đúng cho các checkpoint cũ.
             "input_format": INPUT_FORMAT,
             "history": history, "train_size": len(train_ds), "val_size": len(val_ds)},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "prm_training.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nXong. F1 bắt lỗi tốt nhất: {best_f1:.4f}\nCheckpoint: {out_dir}")


if __name__ == "__main__":
    main()
