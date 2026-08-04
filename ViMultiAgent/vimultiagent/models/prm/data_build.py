"""Dựng dataset huấn luyện ViSTEM-PRM.

    python -m vimultiagent.models.prm.data_build --n 4000

Bài toán học: cho ĐỀ BÀI và các bước giải tới bước k, dự đoán **bước k có đúng không**.

Quy ước gán nhãn (quan trọng, ảnh hưởng trực tiếp tới chất lượng model):
  - Lời giải đúng, n bước  -> n mẫu DƯƠNG (tiền tố tới từng bước)
  - Lời giải bị tiêm lỗi ở bước e -> các bước 0..e−1 là DƯƠNG, bước e là ÂM.
    **Các bước sau e bị LOẠI BỎ.** Chúng có thể tự nhất quán với lỗi phía trên,
    nên gán nhãn cho chúng sẽ tạo nhiễu. Bài toán ta cần giải là tìm bước sai
    ĐẦU TIÊN, không phải chấm mọi bước.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from . import augment, mutate, synth

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "eval" / "datasets" / "prm"

SEP = " [SEP] "

# Định dạng đầu vào hiện hành. Ghi vào training_meta.json lúc huấn luyện và đọc lại
# lúc suy luận — checkpoint cũ phải tiếp tục chạy đúng định dạng nó đã học.
INPUT_FORMAT = "v2"


def step_text(step: Any) -> str:
    """Ghép các trường của MỘT bước thành câu.

    ĐÂY LÀ NGUỒN SỰ THẬT DUY NHẤT cho việc "một bước giải trông như thế nào dưới
    dạng văn bản". Trước đây có tới ba chỗ tự ghép theo ba cách khác nhau:
    dựng dữ liệu huấn luyện, suy luận (PRM._step_text), và ghi memory pool
    (Orchestrator._remember chỉ nối goal_vi). Ba cách ghép khác nhau nghĩa là model
    được huấn luyện trên một phân phối văn bản và bị hỏi trên một phân phối khác.
    Đây đúng là lỗi đã xảy ra với `answers_match` (xem docs/04-ket-qua.md, Lỗi 1) —
    hai chỗ cùng trả lời một câu hỏi thì phải là cùng một đoạn mã.

    Nhận cả `SolutionStep` (có thuộc tính) lẫn chuỗi có sẵn.
    """
    if isinstance(step, str):
        return step.strip()
    parts: list[str] = []
    for field in (
        getattr(step, "goal_vi", ""),
        getattr(step, "expression_latex", ""),
        getattr(step, "result_latex", ""),
        getattr(step, "justification_vi", ""),
    ):
        f = (field or "").strip()
        # Bỏ trùng: Solver hay diễn đạt goal_vi và justification_vi giống hệt nhau,
        # ghép thẳng sẽ nhân đôi câu và làm lệch phân phối (docs/04, Lỗi 2).
        if f and f not in parts:
            parts.append(f)
    return ". ".join(parts)


def build_input(problem: str, steps: list[str], upto: int, fmt: str = INPUT_FORMAT) -> str:
    """Chuỗi đầu vào cho model.

    v2 đặt bước ĐANG ĐƯỢC CHẤM lên ĐẦU. Lý do là một ràng buộc cứng chứ không phải
    thẩm mỹ: PhoBERT chặn ở 258 vị trí, và `eval/run_prm_diag.py` đo được 32 % đầu
    vào thật vượt 256 token. Với `truncation_side='right'` của v1 (bước đang chấm
    nằm cuối), gần một phần ba số bước bị hỏi "bước này đúng không" trong khi chính
    bước đó đã bị cắt mất. Đưa nó lên đầu thì phần bị cắt là các bước trước xa nhất —
    thứ ít quan trọng nhất.

    v1 giữ lại để checkpoint cũ vẫn chạy đúng định dạng nó đã được huấn luyện.
    """
    prefix = " ".join(f"B{i + 1}: {s}" for i, s in enumerate(steps[:upto]))
    target = steps[upto]
    if fmt == "v1":
        return f"ĐỀ: {problem}{SEP}TRƯỚC: {prefix}{SEP}XÉT: {target}"
    return f"XÉT: {target}{SEP}ĐỀ: {problem}{SEP}TRƯỚC: {prefix}"


def examples_from_correct(item: dict[str, Any]) -> list[dict[str, Any]]:
    steps = item["steps"]
    return [
        {
            "text": build_input(item["problem"], steps, i),
            "label": 1,
            "domain": item["domain"],
            "subtopic": item["subtopic"],
            "source": item["id"],
            "step_idx": i,
            "mutation_type": None,
        }
        for i in range(len(steps))
    ]


def examples_from_mutation(item: dict[str, Any], mut: dict[str, Any]) -> list[dict[str, Any]]:
    steps = mut["steps"]
    e = mut["error_step"]
    out = [
        {
            "text": build_input(item["problem"], steps, i),
            "label": 1,
            "domain": item["domain"],
            "subtopic": item["subtopic"],
            "source": item["id"],
            "step_idx": i,
            "mutation_type": None,
        }
        for i in range(e)
    ]
    out.append(
        {
            "text": build_input(item["problem"], steps, e),
            "label": 0,
            "domain": item["domain"],
            "subtopic": item["subtopic"],
            "source": item["id"],
            "step_idx": e,
            "mutation_type": mut["mutation_type"],
            "description": mut["description"],
        }
    )
    return out


def load_real_examples() -> list[dict[str, Any]]:
    """Lời giải thật đã PASS verifier, lấy từ memory pool.

    Trộn dữ liệu thật vào dữ liệu tổng hợp là điều nên làm ngay khi có: lời giải
    thật có cách diễn đạt đa dạng hơn nhiều so với template, và đó chính là thứ
    quyết định model có tổng quát hoá được hay không.
    """
    sources = [
        ROOT / "vimultiagent" / "memory" / "data" / "solved_examples.jsonl",
        # Lời giải thu từ benchmark (python -m vimultiagent.models.prm.harvest).
        # Đây mới là nguồn chính trên thực tế: benchmark luôn chạy `remember=False`
        # nên memory pool ở trên gần như luôn rỗng.
        ROOT / "eval" / "datasets" / "prm" / "real_solutions.jsonl",
    ]
    out: list[dict[str, Any]] = []
    for f in sources:
        if f.exists():
            out.extend(_read_real_file(f))
    return out


def _read_real_file(f: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            # Ưu tiên `steps` — văn bản đầy đủ, ghép bằng đúng hàm dùng lúc suy luận.
            # Chỉ lùi về tách `solution_sketch` cho các bản ghi CŨ (ghi trước khi có
            # trường này); chúng chỉ chứa goal_vi nên lệch phân phối, dùng tạm thôi.
            steps = [s.strip() for s in e.get("steps") or [] if s and s.strip()]
            if not steps:
                steps = [s.strip() for s in e.get("solution_sketch", "").split("→") if s.strip()]
            if len(steps) >= 2:
                out.append(
                    {
                        "id": e["id"], "problem": e["problem"], "steps": steps,
                        "domain": e.get("domain", "math"), "subtopic": e.get("subtopic", ""),
                    }
                )
        except Exception:  # noqa: BLE001
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4000, help="số lời giải đúng sinh ra")
    ap.add_argument("--mutations-per", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument(
        "--augment", type=int, default=1,
        help="số biến thể GIỮ NGUYÊN NGHĨA sinh thêm cho mỗi lời giải (0 = tắt). "
             "Chống việc PRM chấm theo cách diễn đạt thay vì theo đúng/sai — xem "
             "eval/run_prm_diag.py và vimultiagent/models/prm/augment.py.",
    )
    args = ap.parse_args()

    rng = random.Random(args.seed)
    items = synth.generate(args.n, seed=args.seed)
    real = load_real_examples()
    if real:
        print(f"Trộn thêm {len(real)} lời giải THẬT (memory pool + harvest)")
        items += real

    if args.augment > 0:
        # Tăng cường TRƯỚC khi tiêm lỗi, để nhãn âm cũng có đủ kiểu diễn đạt.
        variants = augment.augment_items(items, rng, n_variants=args.augment)
        print(f"Tăng cường thêm {len(variants)} biến thể giữ nguyên nghĩa "
              f"({args.augment} biến thể/lời giải)")
        items += variants

    rows: list[dict[str, Any]] = []
    n_mut = 0
    for it in items:
        rows.extend(examples_from_correct(it))
        for m in mutate.mutate_many(it["steps"], rng, k=args.mutations_per):
            rows.extend(examples_from_mutation(it, m))
            n_mut += 1

    rng.shuffle(rows)

    # Chia theo NGUỒN chứ không theo dòng: các mẫu sinh từ cùng một lời giải dùng
    # chung tiền tố, để lọt sang cả hai phía sẽ làm rò rỉ và thổi phồng điểm val.
    sources = sorted({r["source"] for r in rows})
    rng.shuffle(sources)
    n_val = int(len(sources) * args.val_frac)
    val_src = set(sources[:n_val])

    train = [r for r in rows if r["source"] not in val_src]
    val = [r for r in rows if r["source"] in val_src]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in (("train", train), ("val", val)):
        p = OUT_DIR / f"{name}.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        pos = sum(1 for r in data if r["label"] == 1)
        print(f"{name:<6} {len(data):>7} mẫu | dương {pos} ({pos / max(len(data), 1):.1%}) -> {p}")

    by_type: dict[str, int] = {}
    for r in rows:
        if r["label"] == 0:
            by_type[r["mutation_type"]] = by_type.get(r["mutation_type"], 0) + 1
    print(f"\n{len(items)} lời giải gốc, {n_mut} biến thể hỏng")
    print("Phân bố loại lỗi:", by_type)


if __name__ == "__main__":
    main()
