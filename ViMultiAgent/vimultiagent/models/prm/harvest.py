"""Thu hoạch lời giải THẬT từ báo cáo benchmark sang dữ liệu huấn luyện PRM.

    python -m vimultiagent.models.prm.harvest
    python -m vimultiagent.models.prm.harvest --reports 20260804_*_full.json

Đây là mắt xích còn thiếu giữa "chạy benchmark" và "huấn luyện lại PRM".
`data_build.load_real_examples` trước nay chỉ đọc memory pool, mà benchmark luôn chạy
với `remember=False` (tập đánh giá tuyệt đối không được lọt vào pool), nên pool vẫn
rỗng và đường nạp dữ liệu thật thực tế chưa bao giờ chảy.

---------------------------------------------------------------------------
GÁN NHÃN — phần cần cẩn thận nhất, và là lý do script này không chỉ là vài dòng
---------------------------------------------------------------------------

Benchmark chỉ cho ta nhãn ở mức LỜI GIẢI (`correct`: đáp số cuối có khớp đáp án không).
PRM lại cần nhãn ở mức BƯỚC. Hai mức đó không quy được về nhau:

  * Đáp số đúng KHÔNG kéo theo mọi bước đúng. Đã quan sát trực tiếp: bài Fe + HCl cho
    `final_answer = 2,24 lít` (đúng) trong khi bước 3 viết n(H₂) = ½·n(Fe) = 0,05 mol
    (sai — 0,05 × 22,4 = 1,12). Lấy lời giải đó làm mẫu dương ở mọi bước là dạy PRM
    rằng một bước sai là đúng.
  * Đáp số sai chỉ cho biết CÓ một bước sai, không cho biết bước NÀO. Gán nhãn âm cho
    toàn bộ các bước sẽ tạo nhiễu lớn hơn tín hiệu.

Nên chiến lược ở đây là: **chỉ lấy lời giải đúng làm NGUỒN, rồi sinh nhãn âm bằng
mutation y như với dữ liệu template.** Ta không cố đoán nhãn âm từ lời giải sai.
Cái mà dữ liệu thật đóng góp không phải là nhãn — nhãn thì mutation vốn đã cho miễn
phí — mà là **CÁCH DIỄN ĐẠT**: LaTeX, độ dài bước không đều, từ ngữ tự do. Đó đúng là
thứ mà `eval/run_prm_diag.py` chỉ ra là PRM đang thiếu.

---------------------------------------------------------------------------
RÒ RỈ — đọc trước khi dùng kết quả để báo cáo
---------------------------------------------------------------------------
Lời giải thu ở đây là lời giải CỦA CHÍNH tập đánh giá. Huấn luyện PRM trên chúng rồi
đo hệ thống trên cùng tập đó là rò rỉ. Vì thế mỗi bản ghi mang theo `source_problem_id`
và `dataset`, để:
  * `train.py` chia tập theo NGUỒN (đã làm sẵn) không cho cùng một bài lọt cả hai phía;
  * bạn giữ được một phần đề làm tập kín — dùng `--exclude-ids` hoặc `--holdout-frac`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ...core.schemas import SolutionStep
from .data_build import step_text

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "eval" / "reports"
DATASETS = ROOT / "eval" / "datasets"
OUT = ROOT / "eval" / "datasets" / "prm" / "real_solutions.jsonl"


def load_problem_texts() -> dict[str, str]:
    """id đề -> nội dung đề.

    Báo cáo benchmark chỉ lưu `id`, không lưu nội dung đề, nên phải tra ngược từ tập
    dữ liệu. Làm ở đây thay vì bắt run_bench lưu thêm: cách này chạy được với cả các
    báo cáo đã có sẵn.
    """
    out: dict[str, str] = {}
    for f in DATASETS.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                out[d["id"]] = d.get("problem", "")
    return out


def _steps_of(sol: dict[str, Any]) -> list[str]:
    """Ghép văn bản từng bước bằng ĐÚNG hàm PRM dùng lúc suy luận.

    Đi qua `SolutionStep` để được validate luôn — bản ghi hỏng thì bỏ qua, không để
    nó lặng lẽ thành chuỗi rỗng rồi trôi vào dữ liệu huấn luyện.
    """
    out: list[str] = []
    for st in sol.get("steps") or []:
        try:
            out.append(step_text(SolutionStep.model_validate(st)))
        except Exception:  # noqa: BLE001
            continue
    return [s for s in out if s.strip()]


def _tools_all_ok(sol: dict[str, Any]) -> bool:
    """Có bước nào gọi công cụ mà công cụ báo lỗi không.

    Đây là bộ lọc RẺ chứ không phải bảo đảm: tool lỗi thường là do LLM gọi sai tham số
    chứ không hẳn lời giải sai (xem verifier.verify_t1). Nhưng khi đang chọn mẫu DƯƠNG
    thì thà bỏ sót còn hơn nhận nhầm.
    """
    for st in sol.get("steps") or []:
        for tc in st.get("tool_calls") or []:
            if tc.get("ok") is False:
                return False
    return True


def harvest(
    patterns: list[str], min_steps: int = 2, exclude_ids: set[str] | None = None
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    exclude_ids = exclude_ids or set()
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    texts = load_problem_texts()
    stat = {
        "files": 0, "rows": 0, "no_solution": 0, "incorrect": 0, "no_problem": 0,
        "too_short": 0, "tool_failed": 0, "excluded": 0, "duplicate": 0, "kept": 0,
    }

    files: list[Path] = []
    for p in patterns:
        files.extend(sorted(REPORTS.glob(p)))
    for f in dict.fromkeys(files):
        stat["files"] += 1
        try:
            rows = json.loads(f.read_text(encoding="utf-8")).get("rows", [])
        except Exception:  # noqa: BLE001
            continue
        for row in rows:
            stat["rows"] += 1
            sol = row.get("solution")
            if not sol:
                # Báo cáo chạy TRƯỚC khi run_bench.py bắt đầu lưu `solution`.
                stat["no_solution"] += 1
                continue
            pid = str(row.get("id", ""))
            if pid in exclude_ids:
                stat["excluded"] += 1
                continue
            if not row.get("correct"):
                # Xem phần GÁN NHÃN ở đầu file: lời giải sai không cho ta nhãn âm
                # dùng được, nên bỏ qua thay vì đoán.
                stat["incorrect"] += 1
                continue
            if not _tools_all_ok(sol):
                stat["tool_failed"] += 1
                continue
            problem = texts.get(pid, "")
            if not problem:
                # Không có nội dung đề thì mẫu vô dụng: PRM chấm bước TRONG NGỮ CẢNH đề.
                stat["no_problem"] += 1
                continue
            steps = _steps_of(sol)
            if len(steps) < min_steps:
                stat["too_short"] += 1
                continue
            key = (pid, " | ".join(steps))
            if key in seen:
                stat["duplicate"] += 1
                continue
            seen.add(key)
            out.append(
                {
                    "id": f"real_{pid}_{len(out)}",
                    "source_problem_id": pid,       # để chia tập theo nguồn / giữ kín
                    "dataset": f.name,
                    "problem": problem,
                    "steps": steps,
                    "domain": row.get("domain", "math"),
                    "subtopic": row.get("subtopic", ""),
                    "final_answer": sol.get("final_answer", ""),
                }
            )
            stat["kept"] += 1
    return out, stat


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", nargs="*", default=["*_full.json"],
                    help="mẫu tên file trong eval/reports/")
    ap.add_argument("--min-steps", type=int, default=2)
    ap.add_argument("--exclude-ids", default="",
                    help="danh sách id đề giữ kín, phân tách bằng dấu phẩy")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    excl = {s.strip() for s in args.exclude_ids.split(",") if s.strip()}
    rows, stat = harvest(args.reports, args.min_steps, excl)

    print("=" * 66)
    print("THU HOẠCH LỜI GIẢI THẬT CHO PRM")
    print("=" * 66)
    for k, label in (
        ("files", "file báo cáo đọc được"),
        ("rows", "dòng kết quả"),
        ("no_solution", "  bỏ — chưa lưu `solution` (báo cáo cũ)"),
        ("incorrect", "  bỏ — đáp số sai (không suy ra được nhãn bước)"),
        ("tool_failed", "  bỏ — có công cụ báo lỗi"),
        ("no_problem", "  bỏ — không tra được nội dung đề"),
        ("too_short", "  bỏ — quá ít bước"),
        ("excluded", "  bỏ — nằm trong danh sách giữ kín"),
        ("duplicate", "  bỏ — trùng"),
        ("kept", "GIỮ LẠI"),
    ):
        print(f"{label:<45} {stat[k]:>6}")

    if not rows:
        print(
            "\nKhông thu được mẫu nào.\n"
            "Nguyên nhân thường gặp: báo cáo hiện có được tạo TRƯỚC khi run_bench.py\n"
            "bắt đầu lưu `solution`. Chạy lại benchmark rồi thu hoạch:\n"
            "    python eval/run_bench.py --config full"
        )
        return

    out_f = Path(args.out)
    out_f.parent.mkdir(parents=True, exist_ok=True)
    out_f.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    n_prob = len({r["source_problem_id"] for r in rows})
    print(f"\nĐã ghi {len(rows)} lời giải từ {n_prob} đề -> {out_f.relative_to(ROOT)}")
    print("Bước tiếp: python -m vimultiagent.models.prm.data_build --n 3000 --mutations-per 3")


if __name__ == "__main__":
    main()
