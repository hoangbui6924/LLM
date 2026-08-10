"""Chấm lại kết quả đã có, bằng bộ đọc số MẠNH HƠN — không cần chạy lại model.

    python scripts/cham_lai.py <csv ket qua> [--de <csv bo de>]

Vì sao cần
----------
Hệ thống càng giải giỏi thì càng hay trả lời ở DẠNG CHÍNH XÁC thay vì số thập
phân: `2/9 e^3 + 1/9`, `3e^4/16`, `\\frac{15}{\\sqrt{3}}`. Đó là cách viết ĐÚNG và
đẹp hơn, nhưng bộ đọc số của bench không tính nổi nên chấm thành SAI.

Đây là lần thứ ba loại lỗi này lộ ra trong dự án (trước đó là `5/36`, `√73`, rồi
đơn vị `0,0018 m` so với `1,8 mm`). Mỗi lần nó dìm accuracy vài điểm phần trăm mà
không để lại dấu vết gì ngoài con số thấp.

Ba thứ bản mạnh xử lý được mà bench chưa
-----------------------------------------
1. `\\frac` LỒNG NHAU — `\\frac{15}{\\sqrt{3}}` có ngoặc bên trong nên biểu thức
   chính quy một lớp của SymPy bó tay.
2. `e` là CƠ SỐ TỰ NHIÊN, không phải một ẩn. SymPy mặc định đọc `e` thành ký hiệu
   tự do, nên `3e^4/16` không quy được về số và bị bóc lấy số 3.
3. Đuôi đơn vị và các lệnh LaTeX rác (`\\left`, `\\cdot`, `\\,`).

Script này KHÔNG sửa bench — nó chấm lại dữ liệu đã có để biết con số thật, và để
quyết định có đáng sửa bench hay không.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sympy as sp  # noqa: E402
from sympy.parsing.sympy_parser import (  # noqa: E402
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_T = standard_transformations + (implicit_multiplication_application, convert_xor)

# `e` và `E` là cơ số tự nhiên. Không khai thì SymPy đọc thành ẩn và `3e^4` hỏng.
_TU_DIEN = {"e": sp.E, "E": sp.E, "pi": sp.pi, "Pi": sp.pi}

_FRAC = re.compile(r"\\frac\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]+)\}")
_RAC = re.compile(r"\\(left|right|,|;|!|:|text|mathrm)")
_DUOI_DON_VI = re.compile(r"\s*[A-Za-zΩ%°][A-Za-zΩ%°/^0-9.]*\s*$")


def doc_so(s: str) -> float | None:
    if not s or not s.strip():
        return None
    t = s.strip()

    # `\frac` lồng nhau: chạy nhiều lượt, mỗi lượt bóc được một lớp.
    for _ in range(5):
        moi = _FRAC.sub(r"((\1)/(\2))", t)
        if moi == t:
            break
        t = moi

    t = _SQRT.sub(r"sqrt(\1)", t)
    t = re.sub(r"\\(cdot|times)", "*", t)
    t = _RAC.sub(" ", t)
    t = t.replace("√", "sqrt").replace("{", "(").replace("}", ")").replace("\\", "")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)

    for thu in (t, _DUOI_DON_VI.sub("", t).strip()):
        if not thu:
            continue
        try:
            v = complex(sp.N(parse_expr(thu, transformations=_T, local_dict=_TU_DIEN)))
            if abs(v.imag) < 1e-9:
                return v.real
        except Exception:  # noqa: BLE001
            continue

    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", t)
    return float(m.group(0)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Chấm lại kết quả bằng bộ đọc số mạnh hơn")
    ap.add_argument("ket_qua")
    ap.add_argument("--de", default=str(GOC / "eval" / "data" / "de_kho.csv"))
    ap.add_argument("--dung-sai", type=float, default=0.02)
    a = ap.parse_args()

    kq = list(csv.DictReader(Path(a.ket_qua).open(encoding="utf-8-sig")))
    de = {r["id"]: r for r in csv.DictReader(Path(a.de).open(encoding="utf-8-sig"))}

    lat: list[tuple] = []
    khong_doc_duoc: list[tuple] = []
    for r in kq:
        if r.get("dung") == "1" or r["id"] not in de:
            continue
        d = de[r["id"]]
        if d["question_type"] != "numeric" or not d["answer_value"]:
            continue
        v = doc_so(r["dap_an_he_thong"])
        c = float(d["answer_value"])
        if v is None:
            khong_doc_duoc.append((r["id"], r["level"], r["dap_an_he_thong"]))
        elif abs(v - c) <= a.dung_sai * max(1.0, abs(c)):
            lat.append((r["id"], r["level"], r["dap_an_he_thong"], c, v))

    print(f">>> {len(lat)} bài bị CHẤM OAN (đúng nhưng tính là sai)\n")
    for i, l, ans, c, v in lat:
        print(f"  {i:<16} [{l:<3}] {ans[:36]!r:<40} = {v:.6g}   (chuẩn {c:.6g})")

    if khong_doc_duoc:
        print(f"\n  ({len(khong_doc_duoc)} bài vẫn không đọc nổi đáp án — sai thật hoặc rỗng)")

    n = len(kq)
    d = sum(int(r["dung"]) for r in kq)
    print(f"\n{'=' * 56}")
    print(f"  Accuracy cũ  : {d}/{n} = {d / n * 100:.1f}%")
    print(f"  Accuracy mới : {d + len(lat)}/{n} = {(d + len(lat)) / n * 100:.1f}%"
          f"   ({len(lat) / n * 100:+.1f} điểm)")

    # Tách theo mức độ: đáp số dạng chính xác hay gặp ở bài khó, nên lỗi chấm
    # dồn vào đúng nhóm VDC và làm bảng phân tầng lệch hẳn.
    print(f"\n  Bài chấm oan theo mức độ:")
    for m in ("NB", "TH", "VD", "VDC"):
        c_m = sum(1 for x in lat if x[1] == m)
        t_m = sum(1 for r in kq if r["level"] == m)
        if t_m:
            cu = sum(int(r["dung"]) for r in kq if r["level"] == m)
            print(f"    {m:<4} +{c_m}  ->  {cu}/{t_m} = {cu / t_m * 100:.1f}%"
                  f"  thành  {cu + c_m}/{t_m} = {(cu + c_m) / t_m * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
