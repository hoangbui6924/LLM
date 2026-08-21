"""Fine-tune PhoBERT làm bộ phân loại DẠNG BÀI Toán THPT.

Chạy:  python ml/train_phobert.py
       python ml/train_phobert.py --epochs 5 --batch 16

Đây là phần học sâu do nhóm tự huấn luyện: dữ liệu tự dựng, mô hình tự fine-tune,
kết quả tự đo. Mô hình nền `vinai/phobert-base` (135M tham số) chỉ đóng vai trò
biểu diễn ngôn ngữ, còn tầng phân loại và toàn bộ trọng số được cập nhật ở đây.

Vòng lặp huấn luyện viết tay thay vì dùng `Trainer` của transformers — ít dòng
hơn ở quy mô này, và quan trọng hơn là nhìn thấy rõ từng bước để viết vào báo cáo.

Chạy trên CPU: torch bản CPU đủ nhanh cho ~600 câu (vài phút), và tránh hẳn việc
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

from ml.seed_questions import NHAN  # noqa: E402
from ml.segment import tach_nhieu  # noqa: E402

MODEL_NEN = "vinai/phobert-base"
DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR = Path(__file__).resolve().parent / "phobert_router"

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
    ap.add_argument("--wd", type=float, default=0.01, help="weight decay, chống học vẹt")
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

    # Weight decay chống học vẹt. ĐO ĐƯỢC khi chưa có: train loss chạm 0,03 ngay
    # epoch 6 rồi tụt còn 0,0216 ở epoch 12, trong khi val_acc đứng ở 0,51 — mô
    # hình thuộc lòng 35 khuôn mẫu chứ không học đặc trưng của dạng bài.
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    tong_buoc = args.epochs * len(dl_train)
    sched = torch.optim.lr_scheduler.LinearLR(
        opt, start_factor=1.0, end_factor=0.1, total_iters=tong_buoc
    )

    print(f"\nHuấn luyện {args.epochs} epoch, {len(dl_train)} bước mỗi epoch")
    t0 = time.perf_counter()
    lich_su = []

    # Giữ bản có val_acc CAO NHẤT, không phải bản của epoch cuối.
    #
    # Vì sao: dữ liệu chỉ có 66 câu viết tay trên 15 nhãn, phần còn lại sinh từ
    # 35 khuôn. Mô hình chạm đáy loss rất sớm rồi từ đó chỉ thuộc kỹ thêm khuôn.
    # Lấy epoch cuối là lấy đúng bản học vẹt nhất. Đo được ở lần train 12 epoch:
    # val_acc lên xuống 0,4602 -> 0,4779 -> 0,4956 -> 0,5133, còn `hard` thì TỤT
    # từ 0,80 xuống 0,60 so với bản 4 epoch.
    tot_nhat = {"acc": -1.0, "epoch": 0, "trang_thai": None}

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

        dau = ""
        if acc_val > tot_nhat["acc"]:
            tot_nhat = {
                "acc": acc_val,
                "epoch": ep,
                # Chép sang CPU, nếu không thì bản giữ lại vẫn trỏ vào tensor bị
                # ghi đè ở epoch sau.
                "trang_thai": {
                    k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                },
            }
            dau = "  <- tốt nhất"
        print(f"  epoch {ep}  loss {loss_tb:.4f}  val_acc {acc_val:.4f}{dau}")

    thoi_gian = time.perf_counter() - t0

    if tot_nhat["trang_thai"] is not None and tot_nhat["epoch"] != args.epochs:
        print(
            f"\nLấy lại epoch {tot_nhat['epoch']} (val_acc {tot_nhat['acc']:.4f}) "
            f"thay vì epoch cuối {args.epochs}."
        )
        model.load_state_dict(tot_nhat["trang_thai"])

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
        json.dumps(
            {
                "labels": NHAN,
                "history": lich_su,
                "test_acc": acc_test,
                "epoch_da_chon": tot_nhat["epoch"],
                "val_acc_tot_nhat": tot_nhat["acc"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nĐã lưu vào {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
