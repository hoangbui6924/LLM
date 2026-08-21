"""Đo hiệu năng thật của cả luồng — số liệu cho phần đánh giá hệ thống.

Chạy:
    python scripts/bench.py                              3 bài mẫu dựng sẵn
    python scripts/bench.py --de eval/data/de_chuan.csv   bộ đề chuẩn
    python scripts/bench.py --de ... --n 3                lặp 3 lượt lấy trung bình
    python scripts/bench.py --de ... --mon dai_so         lọc một phân môn
    python scripts/bench.py --de ... --muc VD,VDC         lọc theo mức độ

Bốn chỉ số của đề tài lấy ra từ đây:

  * Accuracy      — chấm tự động, đối chiếu đáp số đã giải tay trong bộ đề
  * Verification  — ma trận đúng/sai × verdict, xem checker bắt được bao nhiêu
  * Latency       — phân bố thời gian, đối chiếu CẢ mốc 45 giây của đề gốc lẫn
                    mốc SLA đang cấu hình
  * (Explanation quality do giáo viên chấm, không đo được ở đây)

Mọi lượt chạy đều ghi ra CSV để phân tích sau và dán vào báo cáo. In ra màn hình
rồi để trôi là mất dữ liệu đắt tiền — một chiến dịch đo đầy đủ tốn vài giờ máy.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Console Windows mặc định cp1252, không in nổi tiếng Việt có dấu.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents import manager  # noqa: E402
from agents.recompute_agent import _boc_ve_phai  # noqa: E402
from core import config, db  # noqa: E402
import sympy as sp  # noqa: E402
from sympy.parsing.sympy_parser import parse_expr as _parse_expr  # noqa: E402

from tools import sympy_tool  # noqa: E402

GOC_BACKEND = Path(__file__).resolve().parents[1]

# Mốc của ĐỀ BÀI GỐC. Cố định, không đọc từ config: dù nhóm có nới SLA lên bao
# nhiêu thì báo cáo vẫn phải trả lời được câu "có đạt 45 giây không".
MOC_DE_BAI = 45.0

# Dung sai chấm số: chấp nhận model làm tròn 0,6283 thành 0,63 hay 7,733 thành 7,73.
DUNG_SAI = 0.02

TEN_MON = {"dai_so": "Đại số", "hinh_hoc": "Hình học"}
CAC_MUC = ("NB", "TH", "VD", "VDC")
TEN_MUC = {
    "NB": "Nhận biết",
    "TH": "Thông hiểu",
    "VD": "Vận dụng",
    "VDC": "Vận dụng cao",
}


# ---------------------------------------------------------------------------
# Bộ đề
# ---------------------------------------------------------------------------


@dataclass
class Bai:
    """Một bài trong bộ đề chuẩn, kèm đáp án đã giải tay.

    Ba trường đáp án tách riêng vì đáp số THPT có ba dạng khác nhau, và mỗi dạng
    cần một cách chấm khác nhau — gộp làm một thì hoặc chấm sai, hoặc phải đoán.
    """

    id: str
    subject: str
    question: str
    topic: str = ""
    level: str = "TH"
    question_type: str = "numeric"        # numeric | mcq | symbolic
    choices: dict[str, str] = field(default_factory=dict)
    answer_value: float | None = None     # đáp số bằng số
    answer_unit: str = ""
    answer_expr: str = ""                 # đáp số dạng biểu thức
    answer_choice: str = ""               # A/B/C/D
    bieu_thuc_kiem: str = ""              # công thức đã thay số, để TỰ KIỂM đáp án
    nguon: str = ""
    ghi_chu: str = ""

    @property
    def mon_vi(self) -> str:
        return TEN_MON.get(self.subject, self.subject)

    def dap_an_chuan(self) -> str:
        """Đáp án chuẩn dạng chữ, để in ra và ghi vào CSV kết quả."""
        if self.question_type == "mcq":
            return self.answer_choice
        if self.question_type == "symbolic":
            return self.answer_expr
        if self.answer_value is None:
            return ""
        return f"{self.answer_value:g}" + (f" {self.answer_unit}" if self.answer_unit else "")


# Hai bài dựng sẵn — giữ nguyên từ bản trước để `python scripts/bench.py` trơn vẫn
# chạy được như cũ, tiện kiểm tra nhanh sau mỗi lần sửa code.
BAI_MAC_DINH = [
    Bai(
        id="mau_dai_so",
        subject="dai_so",
        topic="dao_ham",
        level="TH",
        question="Tính đạo hàm của hàm số y = x^3 - 3x^2 + 2x tại điểm x = 1",
        answer_value=-1.0,
        bieu_thuc_kiem="3*1**2 - 6*1 + 2",
    ),
    Bai(
        id="mau_hinh",
        subject="hinh_hoc",
        topic="toa_do_kc_diem_mp",
        level="TH",
        question=(
            "Trong không gian Oxyz, tính khoảng cách từ điểm A(1; 2; 3) "
            "đến mặt phẳng x + 2y - 2z + 1 = 0."
        ),
        answer_value=0.0,
        bieu_thuc_kiem="Abs(1 + 2*2 - 2*3 + 1)/sqrt(1**2 + 2**2 + (-2)**2)",
    ),
]


def _so(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def doc_de(duong_dan: Path) -> list[Bai]:
    """Đọc bộ đề từ CSV.

    Dùng utf-8-sig vì Excel trên Windows lưu kèm BOM, và bộ đề chắc chắn sẽ được
    soạn bằng Excel. Không xử lý BOM thì cột đầu tiên mang tên "﻿id" và mọi
    thứ hỏng theo cách rất khó nhìn ra.
    """
    bai: list[Bai] = []
    with duong_dan.open(encoding="utf-8-sig", newline="") as f:
        for dong in csv.DictReader(f):
            cau = (dong.get("question") or "").strip()
            if not cau or cau.startswith("#"):
                continue
            lua_chon: dict[str, str] = {}
            tho = (dong.get("choices") or "").strip()
            if tho:
                try:
                    lua_chon = json.loads(tho)
                except json.JSONDecodeError:
                    lua_chon = {}
            bai.append(
                Bai(
                    id=(dong.get("id") or f"bai_{len(bai) + 1}").strip(),
                    subject=(dong.get("subject") or "dai_so").strip(),
                    question=cau,
                    topic=(dong.get("topic") or "").strip(),
                    level=(dong.get("level") or "TH").strip().upper(),
                    question_type=(dong.get("question_type") or "numeric").strip(),
                    choices=lua_chon,
                    answer_value=_so(dong.get("answer_value", "")),
                    answer_unit=(dong.get("answer_unit") or "").strip(),
                    answer_expr=(dong.get("answer_expr") or "").strip(),
                    answer_choice=(dong.get("answer_choice") or "").strip().upper(),
                    bieu_thuc_kiem=(dong.get("bieu_thuc_kiem") or "").strip(),
                    nguon=(dong.get("nguon") or "").strip(),
                    ghi_chu=(dong.get("ghi_chu") or "").strip(),
                )
            )
    return bai


# ---------------------------------------------------------------------------
# Chấm — ba dạng đáp số, ba cách chấm
# ---------------------------------------------------------------------------


# Đuôi đơn vị bám sau con số: "6.72 lit", "0.628 m/s", "50 Ω".
_DUOI_DON_VI = re.compile(r"\s*[A-Za-zΩ%°][A-Za-zΩ%°/^0-9.]*\s*$")


# `\frac` LỒNG NHAU: `\frac{15}{\sqrt{308}}` có ngoặc bên trong nên biểu thức
# chính quy một lớp bó tay. Mẫu này cho phép một mức lồng, và gọi lặp để bóc dần.
_FRAC = re.compile(
    r"\\frac\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
)
_LATEX_RAC = re.compile(r"\\(left|right|,|;|!|:|text|mathrm|displaystyle)")


def _chuan_hoa_so(s: str) -> str:
    """Đưa cách viết của học sinh về cú pháp SymPy đọc được.

    ĐO ĐƯỢC trên bộ đề khó: bài càng khó thì hệ thống càng hay trả lời ở DẠNG
    CHÍNH XÁC thay vì số thập phân — `2/9 e^3 + 1/9`, `\\frac{5e^{6}+1}{9}`. Đó là
    cách viết ĐÚNG và đẹp hơn, nhưng không xử lý được thì bị chấm thành sai. Bốn
    bài bị chấm oan, TẤT CẢ đều ở mức vận dụng cao, kéo tụt nhóm đó 5,4 điểm.
    """
    t = (s or "").strip()
    # Bóc \frac từ ngoài vào, mỗi lượt một lớp.
    for _ in range(5):
        moi = _FRAC.sub(r"((\1)/(\2))", t)
        if moi == t:
            break
        t = moi
    t = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", t)
    t = re.sub(r"\\(cdot|times)", "*", t)
    t = _LATEX_RAC.sub(" ", t)
    # Ngoặc nhọn còn sót sau khi bóc \frac — `5e^{6}` phải thành `5e^(6)`, để
    # nguyên thì SymPy bó tay và cả biểu thức bị bóc lấy mỗi số dẫn đầu.
    t = t.replace("{", "(").replace("}", ")").replace("\\", "")
    # `√73` phải thành `sqrt(73)`, KHÔNG phải `sqrt73` — cái sau thành một tên biến.
    t = re.sub(r"√\s*\(([^)]*)\)", r"sqrt(\1)", t)
    t = re.sub(r"√\s*([0-9.]+)", r"sqrt(\1)", t)
    t = re.sub(r"√\s*([A-Za-z]\w*)", r"sqrt(\1)", t)
    t = t.replace("×", "*").replace("·", "*").replace("−", "-")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)      # dấu phẩy thập phân kiểu Việt Nam
    return t


def _tinh_co_hang_so(bieu_thuc: str) -> float | None:
    """Tính biểu thức, hiểu `e` là CƠ SỐ TỰ NHIÊN chứ không phải một ẩn.

    `sympy_tool.parse` không khai `e`, nên SymPy đọc nó thành ký hiệu tự do và
    `3e^4/16` không quy được về số — rồi bị bóc lấy mỗi số 3. Đo được: hai bài
    vận dụng cao bị chấm oan đúng vì lý do này.

    Chỉ dùng cho việc CHẤM đáp số cuối, không đưa vào `sympy_tool` dùng chung:
    trong lời giải, `e` có thể là tên một điểm hình học chứ không phải 2,718 —
    đổi ở tầng dưới là gây hoạ chỗ khác.
    """
    try:
        e = _parse_expr(
            bieu_thuc,
            transformations=sympy_tool._TRANSFORMS,
            local_dict={"e": sp.E, "E": sp.E, "pi": sp.pi},
        )
        v = complex(sp.N(e))
        return v.real if abs(v.imag) < 1e-9 else None
    except Exception:  # noqa: BLE001
        return None


def _doc_so(s: str) -> float | None:
    """Đọc đáp số ra một con số. TÍNH biểu thức, không chỉ bóc số dẫn đầu.

    ĐO ĐƯỢC trên lần chạy đầu: bóc số dẫn đầu chấm OAN 4 bài đúng — model trả
    `5/36` (bóc ra 5), `64/3` (bóc ra 64), `√73` (bóc ra 73), `37/44` (bóc ra 37).
    Trả lời dạng phân số hay căn thức là cách viết HỢP LỆ và chính xác hơn số thập
    phân, phạt nó là sai từ gốc.

    Thứ tự: tính cả chuỗi -> bỏ đuôi đơn vị rồi tính lại -> cùng đường thì mới bóc
    số dẫn đầu. Bước cuối vẫn cần cho `0,628 m/s`, vì SymPy đọc `m` và `s` thành
    ký hiệu tự do nên không ra số.
    """
    if not s or not s.strip():
        return None
    t = _chuan_hoa_so(s)
    for thu in (t, _DUOI_DON_VI.sub("", t).strip()):
        if not thu:
            continue
        v = _tinh_co_hang_so(thu)
        if v is not None:
            return v
        r = sympy_tool.evaluate(thu)
        if r.get("ok") and r.get("numeric") is not None:
            return float(r["numeric"])
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", t)
    return float(m.group(0)) if m else None


def _tach_don_vi(s: str) -> tuple[float | None, str]:
    """Tách '1,8 mm' thành (1.8, 'mm')."""
    v = _doc_so(s)
    if v is None:
        return None, ""
    m = _DUOI_DON_VI.search(_chuan_hoa_so(s))
    return v, (m.group(0).strip() if m else "")

# Đổi đơn vị cho khâu chấm. Đề Toán THPT chỉ dùng đơn vị độ dài, diện tích, thể
# tích — một bảng tra tất định là đủ, không cần thư viện đơn vị bên ngoài.
#
# Vì sao vẫn cần đổi: đề ghi đáp án chuẩn bằng cm³ mà lời giải trả lời bằng dm³
# thì so số trần sẽ lệch 1000 lần và bị chấm sai. Phạt vì dùng đơn vị khác là
# chấm sai, không phải chấm chặt.
_HE_SO_DOI: dict[tuple[str, str], float] = {
    ("m", "cm"): 100.0,      ("cm", "m"): 0.01,
    ("m", "mm"): 1000.0,     ("mm", "m"): 0.001,
    ("cm", "mm"): 10.0,      ("mm", "cm"): 0.1,
    ("dm", "cm"): 10.0,      ("cm", "dm"): 0.1,
    ("km", "m"): 1000.0,     ("m", "km"): 0.001,
    ("m2", "cm2"): 10000.0,  ("cm2", "m2"): 0.0001,
    ("dm2", "cm2"): 100.0,   ("cm2", "dm2"): 0.01,
    ("m3", "cm3"): 1e6,      ("cm3", "m3"): 1e-6,
    ("dm3", "cm3"): 1000.0,  ("cm3", "dm3"): 0.001,
    ("l", "dm3"): 1.0,       ("dm3", "l"): 1.0,
}

def _cham_so(dap_an: str, dung: float, don_vi_chuan: str = "") -> bool:
    """So đáp số bằng số, CÓ quy đổi đơn vị khi hai bên ghi khác đơn vị.

    ĐO ĐƯỢC: model trả `0,0018 m` cho bài đáp án `1,8 mm` — cùng một giá trị, chỉ
    khác đơn vị, mà so số trần thì lệch 1000 lần và bị chấm sai. Phạt học sinh vì
    dùng mét thay milimét là chấm sai, không phải chấm chặt.
    """
    v, dv = _tach_don_vi(dap_an)
    if v is None:
        return False
    if dv and don_vi_chuan and dv.lower() != don_vi_chuan.lower():
        he_so = _HE_SO_DOI.get((dv.lower(), don_vi_chuan.lower()))
        if he_so is not None:
            v *= he_so
    return abs(v - dung) <= DUNG_SAI * max(1.0, abs(dung))


def _cham_bieu_thuc(dap_an: str, dung: str) -> bool:
    """So hai BIỂU THỨC bằng rút gọn tượng trưng, không so chuỗi.

    `-x + 7` và `-(x - 2) + 5` là một. So chuỗi không phân biệt được, còn
    `simplify(a - b) == 0` thì có. Dùng lại đúng công cụ mà Verify đang dùng.
    """
    a, b = _boc_ve_phai(dung), _boc_ve_phai(dap_an)
    if not a or not b:
        return False
    kq = sympy_tool.are_equivalent(a, b)
    return bool(kq.get("ok") and kq.get("equivalent"))


def _cham_mcq(mcq: str, dap_an: str, dung: str) -> bool:
    """Ưu tiên trường mcq_choice; thiếu thì mò chữ cái trong đáp án."""
    import re

    chon = (mcq or "").strip().upper()
    if not chon:
        m = re.search(r"\b([ABCD])\b", (dap_an or "").upper())
        chon = m.group(1) if m else ""
    return bool(chon) and chon == dung.strip().upper()


def cham(bai: Bai, dap_an: str, mcq: str) -> bool:
    if bai.question_type == "mcq" and bai.answer_choice:
        return _cham_mcq(mcq, dap_an, bai.answer_choice)
    if bai.question_type == "symbolic" and bai.answer_expr:
        return _cham_bieu_thuc(dap_an, bai.answer_expr)
    if bai.answer_value is not None:
        return _cham_so(dap_an, bai.answer_value, bai.answer_unit)
    return False


# ---------------------------------------------------------------------------
# Chạy
# ---------------------------------------------------------------------------

# Gom span của Manager về sáu cột cố định cho dễ đọc trong CSV.
_NHOM_SPAN = {
    "planner": "planner",
    "router": "router",
    "recompute": "recompute",
    "verify_agent": "verify",
    "explain_agent": "explain",
    "dai_so_agent": "subject",
    "hinh_hoc_agent": "subject",
}


async def chay_mot_bai(bai: Bai) -> dict:
    """Chạy một bài qua toàn bộ luồng, thu mọi thứ cần cho báo cáo.

    Đọc kết quả từ sự kiện `done` (chứa trọn `SolveResult`) thay vì nhặt nhạnh từ
    các sự kiện agent dọc đường: `done` là dữ liệu đã chốt, còn sự kiện dọc đường
    có thể bị vòng giải lại ghi đè.
    """
    t0 = time.perf_counter()
    tong_ms = 0.0
    so_chunk = 0
    ket: dict = {}
    loi = ""
    # Đáp số Subject Agent đưa ra TRƯỚC khi Manager cứu đáp án. Đây mới là thứ
    # Verify đã phán, nên chỉ số "phát hiện sai" phải chấm trên nó.
    dap_an_subject = ""
    da_cuu = False
    rc_co_gia_tri = False
    rc_ly_do_hong = ""

    try:
        async for ev in manager.solve_stream(bai.question):
            if ev["type"] == "token":
                so_chunk += 1
            elif ev["type"] == "agent":
                ten = ev.get("name", "")
                if (
                    ev.get("status") == "done"
                    and ten.endswith("_agent")
                    and ten not in ("verify_agent", "explain_agent")
                ):
                    dap_an_subject = ev.get("detail", "") or ""
            elif ev["type"] == "cuu_dap_an":
                da_cuu = True
            elif ev["type"] == "recompute_info":
                rc_co_gia_tri = bool(ev.get("co_gia_tri"))
                rc_ly_do_hong = ev.get("ly_do_hong", "")
            elif ev["type"] == "done":
                tong_ms = ev.get("total_ms", 0.0)
                ket = ev.get("result") or {}
            elif ev["type"] == "error":
                loi = ev.get("message", "")
    except Exception as e:  # noqa: BLE001 — một bài hỏng không được dừng cả chiến dịch
        loi = f"{type(e).__name__}: {e}"

    tong_s = (time.perf_counter() - t0) if tong_ms == 0 else tong_ms / 1000.0

    sol = (ket.get("solution") or {}) if ket else {}
    ver = (ket.get("verify") or {}) if ket else {}
    route = (ket.get("route") or {}) if ket else {}
    trace = (ket.get("trace") or {}) if ket else {}

    dap_an = (sol.get("final_answer") or "").strip()
    mcq = (sol.get("mcq_choice") or "") or ""
    verdict = (ver.get("verdict") or "").strip()

    moc: dict[str, float] = {k: 0.0 for k in ("planner", "router", "subject", "recompute", "verify", "explain")}
    for sp in trace.get("spans", []) or []:
        nhom = _NHOM_SPAN.get(sp.get("agent", ""))
        if nhom:
            moc[nhom] += float(sp.get("duration_ms", 0.0)) / 1000.0

    return {
        "bai": bai,
        # `dung`        — đáp án NGƯỜI DÙNG NHẬN ĐƯỢC, sau khi Manager cứu. Đây là
        #                 độ chính xác đầu-cuối, dùng cho chỉ số 1.
        # `dung_subject`— đáp án Subject Agent tự đưa ra, TRƯỚC khi cứu. Verify phán
        #                 trên bản này, nên chỉ số 3 phải chấm trên nó.
        # Trộn hai thứ là sai lệch nghiêm trọng: bài mà Subject sai, Verify bắt đúng,
        # rồi Manager cứu thành công sẽ bị đếm thành "Verify báo oan" — tức phạt hệ
        # thống đúng ba lần cho một lần nó làm đúng.
        "dung": cham(bai, dap_an, mcq) if not loi else False,
        "dung_subject": cham(bai, dap_an_subject, mcq) if not loi else False,
        "dap_an": dap_an,
        "dap_an_subject": dap_an_subject,
        "da_cuu": da_cuu,
        "rc_co_gia_tri": rc_co_gia_tri,
        "rc_ly_do_hong": rc_ly_do_hong,
        "mcq": mcq,
        "verdict": verdict,
        "tong_s": tong_s,
        "dat_45s": tong_s <= MOC_DE_BAI,
        "dat_sla": tong_s <= config.SLA_SECONDS,
        "so_chunk": so_chunk,
        "mon_router": route.get("subject", ""),
        "router_theo": route.get("decided_by", ""),
        "retry": int(trace.get("retry_rounds", 0) or 0),
        "canh_bao": (ket.get("warning_vi") or "") if ket else "",
        "loi": loi,
        "moc": moc,
    }


# ---------------------------------------------------------------------------
# Báo cáo
# ---------------------------------------------------------------------------


def _ti_le(tu: int, mau: int) -> str:
    return f"{tu}/{mau} = {tu / mau * 100:5.1f}%" if mau else f"{tu}/0 =   —  "


def in_accuracy(kq: list[dict]) -> None:
    n = len(kq)
    dung = sum(1 for r in kq if r["dung"])
    dung_sub = sum(1 for r in kq if r["dung_subject"])
    print("\n" + "=" * 68)
    print("CHỈ SỐ 1 — ĐỘ CHÍNH XÁC")
    print("=" * 68)
    print(f"  Toàn bộ      : {_ti_le(dung, n)}    (ngưỡng đề bài ≥ 75%)")
    print(f"  Riêng Subject Agent (trước bước cứu): {_ti_le(dung_sub, n)}")
    if dung != dung_sub:
        print(f"    -> tầng kiểm chứng + cứu đáp án đóng góp {dung - dung_sub:+d} bài")

    print("\n  Theo môn:")
    for m in TEN_MON:
        s = [r for r in kq if r["bai"].subject == m]
        if s:
            print(f"    {TEN_MON[m]:<6} {_ti_le(sum(1 for r in s if r['dung']), len(s))}")

    print("\n  Theo mức độ:")
    for mu in CAC_MUC:
        s = [r for r in kq if r["bai"].level == mu]
        if s:
            print(f"    {TEN_MUC[mu]:<14} {_ti_le(sum(1 for r in s if r['dung']), len(s))}")

    # Sai số 95% — công bố con số trần trụi trên vài chục bài là chỗ dễ bị vặn nhất.
    if n:
        p = dung / n
        bien = 1.96 * (p * (1 - p) / n) ** 0.5
        print(f"\n  Khoảng tin cậy 95%: {p * 100:.1f}% ± {bien * 100:.1f} điểm %  (n = {n})")


def in_ma_tran(kq: list[dict]) -> None:
    """Ma trận đúng/sai × verdict — chỉ số 3 của đề tài.

    Chấm trên `dung_subject` (đáp số TRƯỚC khi cứu), không phải `dung`. Verify soi
    lời giải của Subject Agent, nên phải đối chiếu với chính bản đó.
    """
    print("\n" + "=" * 68)
    print("CHỈ SỐ 3 — KHẢ NĂNG PHÁT HIỆN SAI CỦA VERIFY")
    print("=" * 68)
    print("  (chấm trên lời giải của Subject Agent, TRƯỚC bước cứu đáp án)")

    cot = ("PASS", "FAIL", "UNCERTAIN")

    def dem(dung: bool, v: str) -> int:
        return sum(1 for r in kq if r["dung_subject"] is dung and r["verdict"] == v)

    print(f"\n  {'':<18}{'PASS':>10}{'FAIL':>10}{'UNCERTAIN':>12}")
    print(f"  {'Lời giải ĐÚNG':<18}" + "".join(f"{dem(True, c):>10}" if c != "UNCERTAIN" else f"{dem(True, c):>12}" for c in cot))
    print(f"  {'Lời giải SAI':<18}" + "".join(f"{dem(False, c):>10}" if c != "UNCERTAIN" else f"{dem(False, c):>12}" for c in cot))

    n_sai = sum(1 for r in kq if not r["dung_subject"])
    n_dung = sum(1 for r in kq if r["dung_subject"])

    bat_chat = dem(False, "FAIL")
    bat_noi = dem(False, "FAIL") + dem(False, "UNCERTAIN")
    bao_oan = dem(True, "FAIL")

    print()
    print(f"  Phát hiện sai (chặt, chỉ FAIL)      : {_ti_le(bat_chat, n_sai)}   (ngưỡng ≥ 85%)")
    print(f"  Phát hiện sai (nới, FAIL+UNCERTAIN) : {_ti_le(bat_noi, n_sai)}")
    print(f"  Báo oan lời giải đúng               : {_ti_le(bao_oan, n_dung)}")
    print()
    print("  Đọc kèm nhau: một checker luôn trả FAIL sẽ đạt 100% ở dòng đầu mà vô")
    print("  dụng. Tỉ lệ báo oan là thứ chặn cách lách đó.")

    # Giá trị của bộ tính lại độc lập, đo trực tiếp: bao nhiêu bài Subject Agent
    # làm sai mà Manager cứu thành đúng.
    cuu = [r for r in kq if r["da_cuu"]]
    cuu_dung = [r for r in cuu if r["dung"] and not r["dung_subject"]]
    cuu_hong = [r for r in cuu if not r["dung"] and r["dung_subject"]]
    if cuu:
        print(f"\n  Cơ chế cứu đáp án: kích hoạt {len(cuu)} lần")
        print(f"    sai -> đúng : {len(cuu_dung)}  (bộ tính lại độc lập cứu được)")
        print(f"    đúng -> sai : {len(cuu_hong)}  (cứu hỏng, càng ít càng tốt)")


def in_latency(kq: list[dict]) -> None:
    print("\n" + "=" * 68)
    print("CHỈ SỐ 4 — THỜI GIAN")
    print("=" * 68)
    t = sorted(r["tong_s"] for r in kq)
    n = len(t)
    if not n:
        return
    p50 = t[n // 2]
    p95 = t[min(n - 1, int(n * 0.95))]
    print(f"  Trung bình {sum(t) / n:6.1f}s   |  p50 {p50:6.1f}s  |  p95 {p95:6.1f}s")
    print(f"  Nhanh nhất {t[0]:6.1f}s   |  Chậm nhất {t[-1]:6.1f}s")
    print()
    print(f"  Đạt mốc ĐỀ BÀI  {MOC_DE_BAI:.0f}s : {_ti_le(sum(1 for r in kq if r['dat_45s']), n)}")
    print(f"  Đạt mốc CẤU HÌNH {config.SLA_SECONDS:.0f}s : {_ti_le(sum(1 for r in kq if r['dat_sla']), n)}")

    print("\n  Thời gian trung bình từng vai (giây):")
    tb = {}
    for vai in ("planner", "router", "subject", "recompute", "verify", "explain"):
        tb[vai] = sum(r["moc"].get(vai, 0.0) for r in kq) / n
        print(f"    {vai:<12} {tb[vai]:6.1f}")

    # Recompute chạy SONG SONG với Subject, nên phần đóng góp của cặp này vào thời
    # gian thực là max(), không phải tổng. Ghi rõ ra vì đây là chỗ dễ đọc nhầm nhất:
    # khi recompute dài hơn Subject thì CHÍNH NÓ là đường găng, và mọi nỗ lực tối ưu
    # Subject Agent đều vô ích.
    song_song = max(tb["subject"], tb["recompute"])
    duong_gang = tb["planner"] + tb["router"] + song_song + tb["verify"] + tb["explain"]
    print(f"\n  Đường găng ≈ planner + router + max(subject, recompute) + verify + explain")
    print(f"             = {tb['planner']:.1f} + {tb['router']:.1f} + {song_song:.1f}"
          f" + {tb['verify']:.1f} + {tb['explain']:.1f} = {duong_gang:.1f}s")
    if tb["recompute"] > tb["subject"]:
        print(f"    >> RECOMPUTE đang là đường găng ({tb['recompute']:.1f}s so với Subject "
              f"{tb['subject']:.1f}s).")
        print(f"       Nó KHÔNG còn ẩn dưới Subject. Tắt chế độ suy nghĩ cho vai này sẽ "
              f"cắt khoảng {tb['recompute'] - tb['subject']:.0f}s.")


def in_su_co(kq: list[dict]) -> None:
    rong = [r for r in kq if not r["dap_an"]]
    loi = [r for r in kq if r["loi"]]
    retry = sum(r["retry"] for r in kq)
    print("\n" + "=" * 68)
    print("SỰ CỐ")
    print("=" * 68)
    print(f"  Không ra đáp án : {len(rong)}/{len(kq)}")
    print(f"  Lỗi ngoại lệ    : {len(loi)}/{len(kq)}")
    print(f"  Tổng vòng giải lại: {retry}")
    for r in loi[:5]:
        print(f"    - {r['bai'].id}: {r['loi'][:70]}")


COT_CSV = [
    "id", "subject", "topic", "level", "question_type",
    "dung", "dung_subject", "da_cuu", "verdict", "tong_s", "dat_45s", "dat_sla",
    "dap_an_he_thong", "dap_an_subject", "dap_an_chuan", "mcq_he_thong", "mcq_chuan",
    "planner_s", "router_s", "subject_s", "recompute_s", "verify_s", "explain_s",
    "so_chunk_stream", "retry", "router_theo",
    "rc_co_gia_tri", "rc_ly_do_hong",
    "canh_bao", "loi", "question",
]


def xuat_csv(kq: list[dict], thu_muc: Path) -> Path:
    thu_muc.mkdir(parents=True, exist_ok=True)
    ten = f"ket_qua_sla{config.SLA_SECONDS:.0f}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    duong_dan = thu_muc / ten
    with duong_dan.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COT_CSV)
        for r in kq:
            b: Bai = r["bai"]
            w.writerow([
                b.id, b.subject, b.topic, b.level, b.question_type,
                int(r["dung"]), int(r["dung_subject"]), int(r["da_cuu"]),
                r["verdict"], f"{r['tong_s']:.2f}",
                int(r["dat_45s"]), int(r["dat_sla"]),
                r["dap_an"], r["dap_an_subject"], b.dap_an_chuan(),
                r["mcq"], b.answer_choice,
                f"{r['moc']['planner']:.2f}", f"{r['moc']['router']:.2f}",
                f"{r['moc']['subject']:.2f}", f"{r['moc']['recompute']:.2f}",
                f"{r['moc']['verify']:.2f}", f"{r['moc']['explain']:.2f}",
                r["so_chunk"], r["retry"], r["router_theo"],
                int(r["rc_co_gia_tri"]), r["rc_ly_do_hong"],
                r["canh_bao"], r["loi"], b.question,
            ])
    return duong_dan


# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> int:
    if args.de:
        duong_dan = Path(args.de)
        if not duong_dan.is_absolute():
            duong_dan = GOC_BACKEND / duong_dan
        if not duong_dan.exists():
            print(f"Không thấy bộ đề: {duong_dan}")
            return 2
        de = doc_de(duong_dan)
        print(f"Bộ đề: {duong_dan}  ({len(de)} bài)")
    else:
        de = list(BAI_MAC_DINH)
        print("Bộ đề: 3 bài mẫu dựng sẵn (dùng --de để chạy bộ đề chuẩn)")

    if args.mon:
        loc = {m.strip() for m in args.mon.split(",") if m.strip()}
        de = [b for b in de if b.subject in loc]
    if args.muc:
        loc = {m.strip().upper() for m in args.muc.split(",") if m.strip()}
        de = [b for b in de if b.level in loc]
    if args.so_luong:
        # Lấy trải đều thay vì cắt N bài đầu — cắt đầu thì chỉ toàn môn Toán mức NB,
        # chạy thử kiểu đó không nói lên điều gì.
        buoc = max(1, len(de) // args.so_luong)
        de = de[::buoc][: args.so_luong]
    if not de:
        print("Bộ lọc không chừa lại bài nào.")
        return 2

    print(f"Model : {config.MODEL_HEAVY} (heavy) / {config.MODEL_LIGHT} (light)")
    print(f"Cấu hình: SLA {config.SLA_SECONDS:.0f}s | suy nghĩ {sorted(config.AGENTS_SUY_NGHI) or 'tắt'}"
          f" | giải lại {config.MAX_RETRY_ROUNDS} vòng")
    print(f"Sẽ chạy {len(de) * args.n} lượt. Đừng dùng giao diện lúc này — tranh GPU làm sai số đo.\n")

    # Manager có lưu lịch sử vào SQLite, nhưng `db.init()` chỉ chạy ở main.py. Chạy
    # bench với VMA_DB_PATH riêng (nên làm, để không lẫn vào lịch sử thật) thì bảng
    # chưa tồn tại, và manager nuốt lỗi lưu nên hỏng hoàn toàn im lặng.
    try:
        db.init()
    except Exception as e:  # noqa: BLE001 — không lưu được lịch sử thì vẫn phải đo
        print(f"(Không khởi tạo được DB lịch sử: {e} — kết quả vẫn ghi ra CSV)\n")

    kq: list[dict] = []
    tong_luot = len(de) * args.n
    for lap in range(args.n):
        for i, bai in enumerate(de, start=1):
            stt = lap * len(de) + i
            r = await chay_mot_bai(bai)
            kq.append(r)
            cx = "ĐÚNG" if r["dung"] else "SAI "
            sla = "" if r["dat_sla"] else "  [VƯỢT SLA]"
            print(
                f"[{stt:3}/{tong_luot}] {bai.mon_vi:<5} {bai.level:<3} {bai.id:<14} "
                f"{cx} {r['tong_s']:6.1f}s  {r['verdict'] or '?':<9}"
                f" {r['dap_an'][:34]!r}{sla}"
            )
            if r["loi"]:
                print(f"          lỗi: {r['loi'][:80]}")

    in_accuracy(kq)
    in_ma_tran(kq)
    in_latency(kq)
    in_su_co(kq)

    thu_muc = Path(args.out) if args.out else GOC_BACKEND / "eval" / "reports"
    duong_dan = xuat_csv(kq, thu_muc)
    print(f"\nĐã ghi chi tiết từng lượt: {duong_dan}")

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Đo hiệu năng ViMultiAgent")
    ap.add_argument("--de", help="đường dẫn CSV bộ đề (mặc định: 3 bài dựng sẵn)")
    ap.add_argument("--n", type=int, default=1, help="số lượt lặp")
    ap.add_argument("--mon", help="lọc phân môn: dai_so,hinh_hoc")
    ap.add_argument("--muc", help="lọc mức độ: NB,TH,VD,VDC")
    ap.add_argument("--so-luong", type=int, help="chỉ chạy N bài lấy trải đều — để chạy thử nhanh")
    ap.add_argument("--out", help="thư mục ghi CSV kết quả")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
