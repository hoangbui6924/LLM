"""So sánh ba cách phân loại môn học — bảng số liệu chính của phần học sâu.

Chạy:  python ml/compare.py

Ba phương pháp, xếp theo độ phức tạp tăng dần:

1. **Luật từ khoá** — đúng bộ luật đang chạy trong `agents/router.py`. Không huấn
   luyện, 0 ms, 0 token.
2. **TF-IDF + Logistic Regression** — học máy cổ điển. Đây là mốc so sánh QUAN
   TRỌNG NHẤT: nếu PhoBERT không vượt được nó thì việc dùng transformer ở đây là
   thừa, và phải trung thực nói ra điều đó.
3. **PhoBERT fine-tuned** — mô hình học sâu do nhóm huấn luyện.

Báo cáo tách riêng theo nguồn dữ liệu. Con số trên `template` gần như luôn đẹp vì
các câu sinh từ khuôn rất đều; chỉ nhóm `hard` — câu không chứa từ khoá đặc trưng
hoặc lai môn — mới phân định được ba phương pháp.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent / "data"
PHOBERT_DIR = Path(__file__).resolve().parent / "phobert_router"
from ml.seed_questions import NHAN  # noqa: E402

# Tên hiển thị tiếng Việt của từng dạng bài.
TEN_VI = {
    "dao_ham": "Đạo hàm", "tich_phan": "Tích phân", "gioi_han": "Giới hạn",
    "phuong_trinh": "Phương trình", "tiep_tuyen": "Tiếp tuyến",
    "gtln": "GTLN", "gtnn": "GTNN", "so_diem_cuc_tri": "Cực trị",
    "tiem_can_ngang": "Tiệm cận ngang", "tiem_can_dung": "Tiệm cận đứng",
    "khac_dai_so": "Đại số khác",
    "toa_do_khoang_cach": "Toạ độ - khoảng cách",
    "toa_do_the_tich": "Thể tích", "toa_do_kc_diem_mp": "Điểm đến mặt phẳng",
    "khac_hinh_hoc": "Hình học khác",
}


def doc(ten: str) -> tuple[list[str], list[str], list[str]]:
    cau, nhan, nguon = [], [], []
    with (DATA_DIR / f"{ten}.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cau.append(row["question"])
            nhan.append(row["label"])
            nguon.append(row["source"])
    return cau, nhan, nguon


# ---------------------------------------------------------------------------
# Chỉ số
# ---------------------------------------------------------------------------


def macro_f1(that: list[str], doan: list[str]) -> float:
    """Macro-F1 — trung bình F1 của ba lớp, không thiên vị lớp đông.

    Dùng macro thay vì accuracy vì test không cân tuyệt đối giữa ba môn.
    """
    tong = 0.0
    for lop in NHAN:
        tp = sum(1 for t, d in zip(that, doan) if t == lop and d == lop)
        fp = sum(1 for t, d in zip(that, doan) if t != lop and d == lop)
        fn = sum(1 for t, d in zip(that, doan) if t == lop and d != lop)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        tong += 2 * p * r / (p + r) if p + r else 0.0
    return tong / len(NHAN)


def do_chinh_xac(that: list[str], doan: list[str]) -> float:
    if not that:
        return 0.0
    return sum(1 for t, d in zip(that, doan) if t == d) / len(that)


def nham_lan(that: list[str], doan: list[str]) -> str:
    """Ma trận nhầm lẫn dạng chữ, gọn để dán vào báo cáo."""
    dong = ["        " + "".join(f"{TEN_VI[c]:>8}" for c in NHAN) + "   (dự đoán)"]
    for tl in NHAN:
        o = [sum(1 for t, d in zip(that, doan) if t == tl and d == dl) for dl in NHAN]
        dong.append(f"  {TEN_VI[tl]:<5} " + "".join(f"{v:>8}" for v in o))
    return "\n".join(dong)


# ---------------------------------------------------------------------------
# Ba phương pháp
# ---------------------------------------------------------------------------


def pp_luat(cau_test: list[str]) -> tuple[list[str], float]:
    from agents.router import _by_rule

    t0 = time.perf_counter()
    doan = [_by_rule(c)[0] for c in cau_test]
    return doan, (time.perf_counter() - t0) * 1000.0 / max(len(cau_test), 1)


def pp_tfidf(
    cau_train: list[str], nhan_train: list[str], cau_test: list[str]
) -> tuple[list[str], float]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    # ngram ký tự 2-5: chịu được lỗi chính tả và thiếu dấu, vốn phổ biến khi học
    # sinh gõ nhanh. Đây là mốc so sánh mạnh, không phải mốc bù nhìn.
    mo_hinh = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced"),
    )
    mo_hinh.fit(cau_train, nhan_train)
    t0 = time.perf_counter()
    doan = list(mo_hinh.predict(cau_test))
    return doan, (time.perf_counter() - t0) * 1000.0 / max(len(cau_test), 1)


def pp_phobert(cau_test: list[str]) -> tuple[list[str], float] | None:
    if not (PHOBERT_DIR / "config.json").exists():
        return None
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    from ml.segment import tach_nhieu

    tok = AutoTokenizer.from_pretrained(PHOBERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(PHOBERT_DIR)
    model.eval()

    da_tach = tach_nhieu(cau_test)
    t0 = time.perf_counter()
    doan: list[str] = []
    with torch.no_grad():
        for i in range(0, len(da_tach), 32):
            lo = tok(
                da_tach[i : i + 32],
                truncation=True,
                padding=True,
                max_length=96,
                return_tensors="pt",
            )
            pred = model(**lo).logits.argmax(dim=-1).tolist()
            doan.extend(NHAN[p] for p in pred)
    return doan, (time.perf_counter() - t0) * 1000.0 / max(len(cau_test), 1)


# ---------------------------------------------------------------------------


def bao_cao(ten: str, that: list[str], doan: list[str], nguon: list[str], ms: float) -> None:
    print(f"\n### {ten}")
    print(f"  Toàn bộ test : acc {do_chinh_xac(that, doan):.4f}   macro-F1 {macro_f1(that, doan):.4f}")
    for ng in ("seed", "template", "hard"):
        idx = [i for i, s in enumerate(nguon) if s == ng]
        if not idx:
            continue
        t = [that[i] for i in idx]
        d = [doan[i] for i in idx]
        sao = "  <-- nhóm phân định" if ng == "hard" else ""
        print(f"  {ng:<12} : acc {do_chinh_xac(t, d):.4f}   macro-F1 {macro_f1(t, d):.4f}   (n={len(idx)}){sao}")
    print(f"  Thời gian    : {ms:.2f} ms mỗi câu")


def main() -> int:
    cau_tr, nhan_tr, _ = doc("train")
    cau_va, nhan_va, _ = doc("val")
    cau_te, nhan_te, nguon_te = doc("test")

    # TF-IDF được dùng cả train lẫn val để công bằng với PhoBERT (PhoBERT dùng val
    # để theo dõi, còn TF-IDF không cần) — cùng lượng dữ liệu nhìn thấy.
    cau_fit = cau_tr + cau_va
    nhan_fit = nhan_tr + nhan_va

    print("=" * 66)
    print("SO SÁNH BA PHƯƠNG PHÁP PHÂN LOẠI MÔN HỌC")
    print("=" * 66)
    print(f"Train {len(cau_tr)} | Val {len(cau_va)} | Test {len(cau_te)} câu")

    ket = {}

    doan, ms = pp_luat(cau_te)
    bao_cao("1. Luật từ khoá (không huấn luyện)", nhan_te, doan, nguon_te, ms)
    ket["luat"] = doan

    doan, ms = pp_tfidf(cau_fit, nhan_fit, cau_te)
    bao_cao("2. TF-IDF + Logistic Regression", nhan_te, doan, nguon_te, ms)
    ket["tfidf"] = doan

    kq = pp_phobert(cau_te)
    if kq is None:
        print("\n### 3. PhoBERT — CHƯA CÓ MÔ HÌNH")
        print("  Chạy `python ml/train_phobert.py` trước.")
    else:
        doan, ms = kq
        bao_cao("3. PhoBERT fine-tuned", nhan_te, doan, nguon_te, ms)
        ket["phobert"] = doan

    # Ma trận nhầm lẫn trên nhóm khó — chỗ đáng soi nhất.
    idx_kho = [i for i, s in enumerate(nguon_te) if s == "hard"]
    if idx_kho:
        print("\n" + "=" * 66)
        print("MA TRẬN NHẦM LẪN TRÊN NHÓM CÂU KHÓ")
        print("=" * 66)
        for ten, doan in ket.items():
            print(f"\n{ten}:")
            print(nham_lan([nhan_te[i] for i in idx_kho], [doan[i] for i in idx_kho]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
