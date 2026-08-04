"""Fine-tune PhoBERT làm bộ phân loại môn học.

Chạy:  python ml/train_phobert.py
       python ml/train_phobert.py --epochs 5 --batch 16

Đây là phần học sâu do nhóm tự huấn luyện: dữ liệu tự dựng, mô hình tự fine-tune,
kết quả tự đo. Mô hình nền `vinai/phobert-base` (135M tham số) chỉ đóng vai trò
biểu diễn ngôn ngữ, còn tầng phân loại và toàn bộ trọng số được cập nhật ở đây.

Vòng lặp huấn luyện viết tay thay vì dùng `Trainer` của transformers — ít dòng
hơn ở quy mô này, và quan trọng hơn là nhìn thấy rõ từng bước để viết vào báo cáo.

Chạy trên CPU: torch bản CPU đủ nhanh cho 535 câu (vài phút), và tránh hẳn việc
tranh 6 GB VRAM với Ollama đang giữ model qwen3.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

from ml.segment import tach_nhieu  # noqa: E402

MODEL_NEN = "vinai/phobert-base"
DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR = Path(__file__).resolve().parent / "phobert_router"

NHAN = ["math", "physics", "chemistry"]
NHAN2ID = {n: i for i, n in enumerate(NHAN)}


def doc_csv(ten: str) -> tuple[list[str], list[int], list[str]]:
    cau, nhan, nguon = [], [], []
    with (DATA_DIR / f"{ten}.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cau.append(row["question"])
            nhan.append(NHAN2ID[row["label"]])
            nguon.append(row["source"])
    return cau, nhan, nguon


class BoDuLieu(Dataset):
    def __init__(self, ma_hoa, nhan: list[int]):
        self.ma_hoa = ma_hoa
        self.nhan = nhan

    def __len__(self) -> int:
        return len(self.nhan)

    def __getitem__(self, i: int) -> dict:
        muc = {k: v[i] for k, v in self.ma_hoa.items()}
        muc["labels"] = torch.tensor(self.nhan[i])
        return muc


def danh_gia(model, loader, thiet_bi) -> tuple[float, list[int]]:
    model.eval()
    dung = tong = 0
    du_doan: list[int] = []
    with torch.no_grad():
        for lo in loader:
            nhan = lo.pop("labels").to(thiet_bi)
            lo = {k: v.to(thiet_bi) for k, v in lo.items()}
            logits = model(**lo).logits
            pred = logits.argmax(dim=-1)
            du_doan.extend(pred.cpu().tolist())
            dung += (pred == nhan).sum().item()
            tong += nhan.numel()
    return dung / max(tong, 1), du_doan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=96)
    args = ap.parse_args()

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    thiet_bi = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {thiet_bi}")
    print(f"Mô hình nền: {MODEL_NEN}\n")

    print("Đang tải tokenizer và mô hình (lần đầu sẽ tải ~540 MB)…")
    tok = AutoTokenizer.from_pretrained(MODEL_NEN)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NEN, num_labels=len(NHAN)
    ).to(thiet_bi)

    tap = {}
    for ten in ("train", "val", "test"):
        cau, nhan, nguon = doc_csv(ten)
        print(f"  {ten:<6} {len(cau):>4} câu")
        # Tách từ TRƯỚC khi tokenize — bắt buộc với PhoBERT.
        da_tach = tach_nhieu(cau)
        ma_hoa = tok(
            da_tach,
            truncation=True,
            padding="max_length",
            max_length=args.max_len,
            return_tensors="pt",
        )
        tap[ten] = (BoDuLieu(ma_hoa, nhan), nhan, nguon)

    dl_train = DataLoader(tap["train"][0], batch_size=args.batch, shuffle=True)
    dl_val = DataLoader(tap["val"][0], batch_size=args.batch)
    dl_test = DataLoader(tap["test"][0], batch_size=args.batch)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    tong_buoc = args.epochs * len(dl_train)
    sched = torch.optim.lr_scheduler.LinearLR(
        opt, start_factor=1.0, end_factor=0.1, total_iters=tong_buoc
    )

    print(f"\nHuấn luyện {args.epochs} epoch, {len(dl_train)} bước mỗi epoch")
    t0 = time.perf_counter()
    lich_su = []
    for ep in range(1, args.epochs + 1):
        model.train()
        tong_loss = 0.0
        for lo in dl_train:
            lo = {k: v.to(thiet_bi) for k, v in lo.items()}
            out = model(**lo)
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            tong_loss += out.loss.item()
        loss_tb = tong_loss / len(dl_train)
        acc_val, _ = danh_gia(model, dl_val, thiet_bi)
        lich_su.append({"epoch": ep, "loss": loss_tb, "val_acc": acc_val})
        print(f"  epoch {ep}  loss {loss_tb:.4f}  val_acc {acc_val:.4f}")

    thoi_gian = time.perf_counter() - t0
    acc_test, du_doan = danh_gia(model, dl_test, thiet_bi)
    print(f"\nHuấn luyện xong trong {thoi_gian:.0f} giây")
    print(f"Độ chính xác trên test: {acc_test:.4f}")

    # Tách riêng nhóm câu khó — đây mới là con số đáng báo cáo.
    _, nhan_test, nguon_test = tap["test"][1], tap["test"][1], tap["test"][2]
    for nguon in ("seed", "template", "hard"):
        idx = [i for i, s in enumerate(nguon_test) if s == nguon]
        if not idx:
            continue
        dung = sum(1 for i in idx if du_doan[i] == nhan_test[i])
        print(f"  {nguon:<10} {dung}/{len(idx)} = {dung / len(idx):.4f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    (OUT_DIR / "labels.json").write_text(
        json.dumps({"labels": NHAN, "history": lich_su, "test_acc": acc_test},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nĐã lưu vào {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
