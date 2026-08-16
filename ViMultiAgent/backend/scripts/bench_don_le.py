"""Mốc nền MỘT TÁC TỬ — để so sánh có đối chứng với kiến trúc đa tác tử.

Vì sao cần file này
-------------------
Báo cáo khẳng định kiến trúc đa tác tử hơn hẳn một lời gọi LLM đơn lẻ. Đó là
khẳng định ĐỊNH LƯỢNG, và nó chỉ có giá trị khi đo được trên **cùng bộ đề, cùng
mô hình, cùng tham số sinh, cùng thước chấm**. Thiếu mốc nền thì con số 78,7%
không nói lên điều gì: người đọc không biết một lời gọi trần đạt bao nhiêu.

Nguyên tắc công bằng — mọi thứ giữ nguyên, chỉ đổi KIẾN TRÚC:

    Giống nhau : model (qwen3:4b), temperature, num_ctx, tắt chế độ suy nghĩ,
                 bộ đề, hàm chấm (dùng lại `cham()` của bench.py)
    Khác nhau  : đa tác tử có Planner/Router/Recompute/Verify/Explain và tầng
                 kiểm chứng tất định; mốc nền chỉ có MỘT lượt gọi LLM

Hai chế độ mốc nền, cố ý làm thành một cái thang:

    --che-do tho   Một lời gọi, văn xuôi tự do. Đây là "hỏi thẳng chatbot" —
                   mốc nền thật sự của người dùng phổ thông.
    --che-do json  Một lời gọi, ép đúng schema `Solution`. Vẫn một tác tử,
                   nhưng ĐÃ ĐƯỢC TẶNG cơ chế ràng buộc đầu ra của hệ thống.

Chênh lệch giữa hai chế độ đo riêng đóng góp của structured output; chênh lệch
giữa `json` và đa tác tử đo riêng đóng góp của việc phân rã vai + kiểm chứng.

Chạy:
    python scripts/bench_don_le.py --de eval/data/de_giu_rieng.csv
    python scripts/bench_don_le.py --de eval/data/de_giu_rieng.csv --che-do json
    python scripts/bench_don_le.py --de ... --so-sanh eval/reports/ket_qua_sla45_....csv

Cờ `--so-sanh` ghép cặp theo `id` với một tệp kết quả đa tác tử có sẵn và in bảng
đối chứng kèm kiểm định McNemar. Ghép cặp chứ không so hai tỉ lệ rời nhau: cùng
một bộ đề chạy hai kiến trúc là thiết kế **đo lặp trên cùng đối tượng**, và kiểm
định ghép cặp mạnh hơn hẳn so sánh hai tỉ lệ độc lập.

File này KHÔNG gọi Manager, nên không ghi gì vào SQLite — chạy bao nhiêu lần cũng
không đụng tới memory pool của hệ thống thật.

File này KHÔNG vẽ hình
----------------------
Đầu ra chỉ có hai tệp, đều do `main()` ở cuối file này ghi ra:

    moc_nen_<che_do>_<dấu thời gian>.csv   `xuat_csv()`  — dữ liệu thô từng bài
    so_sanh_<che_do>_<dấu thời gian>.md    `xuat_md()`   — kết luận dạng chữ

Hình PNG là việc của `scripts/ve_so_sanh.py`. Nó đọc CSV ở trên ghép với CSV đa
tác tử của `bench.py` rồi sinh 5 hình cùng một tệp Markdown gộp:

    01_chi_so_cot_loi_*.png    4 chỉ số cốt lõi   <- hinh_chi_so()
    02_thoi_gian_*.png         độ trễ             <- hinh_thoi_gian()
    03_radar_*.png             radar tổng hợp     <- hinh_radar()
    04_phan_ra_*.png           theo môn/mức độ    <- hinh_phan_ra()
    05_hieu_qua_rong_*.png     McNemar            <- hinh_rong()
    BAOCAO_SO_SANH_*.md        gộp mọi bảng số    <- xuat_md()

Tách làm hai script là cố ý: vẽ lại hình tốn vài giây, còn đo lại tốn vài giờ. Gộp
vào một chỗ thì mỗi lần chỉnh màu hay đổi nhãn đều phải chạy lại cả chiến dịch đo.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ollama  # noqa: E402

# Dùng lại nguyên bộ máy của bench.py: bộ đọc đề, hàm chấm, cách in tỉ lệ. Viết
# một bản riêng là tự chuốc hoạ — hai thước chấm lệch nhau một chi tiết nhỏ (quy
# đổi đơn vị, hay đọc `5/36` thành 5) là đủ để cả phép so sánh mất giá trị.
import bench  # noqa: E402
from bench import (  # noqa: E402
    CAC_MUC,
    MOC_DE_BAI,
    TEN_MON,
    TEN_MUC,
    Bai,
    _ti_le,
    cham,
    doc_de,
)

from agents.base import _options, run_structured  # noqa: E402
from core import config  # noqa: E402
from core.schemas import Solution  # noqa: E402

GOC_BACKEND = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Mốc nền 1 — một lời gọi, văn xuôi tự do
# ---------------------------------------------------------------------------

# Prompt cố ý viết TỐT, không phải viết cho có. Mốc nền bị dìm thì kết luận "đa
# tác tử hơn" là kết luận rỗng, và người phản biện nhìn ra ngay khi đọc phụ lục.
# Đây là prompt mà một người dùng cẩn thận sẽ viết: nêu vai, nêu kỷ luật từng
# môn, và bắt kết bằng một dòng đáp số để chấm được tự động.
SYSTEM_THO = """Bạn là giáo viên THPT giỏi cả ba môn Toán, Vật lý và Hoá học.

Hãy giải bài toán được giao, trình bày từng bước rõ ràng bằng tiếng Việt.

Kỷ luật bắt buộc:
- Với Vật lý: đổi mọi dữ kiện về hệ SI trước khi tính.
- Với Hoá học: viết và cân bằng phương trình phản ứng trước khi tính.
- Với Toán: nêu điều kiện xác định trước khi biến đổi, loại nghiệm ngoại lai.
- Không làm tròn giữa chừng, chỉ làm tròn ở đáp số cuối.
- Nếu là câu trắc nghiệm, phải chọn một phương án A/B/C/D.

DÒNG CUỐI CÙNG của câu trả lời BẮT BUỘC có dạng:
ĐÁP SỐ: <chỉ đáp số kèm đơn vị, không diễn giải>
"""

# Bắt dòng đáp số. Lấy lần khớp CUỐI CÙNG: model hay nhắc cụm này giữa bài rồi
# mới chốt ở cuối, lấy lần đầu là lấy nhầm một kết quả trung gian.
_DONG_DAP_SO = re.compile(r"ĐÁP\s*SỐ\s*[:：]\s*(.+)", re.IGNORECASE)

# Model CHÉP LẠI chỗ giữ chỗ trong prompt thay vì điền giá trị vào: nó viết đúng
# chuỗi `ĐÁP SỐ: <chỉ đáp số kèm đơn vị, không diễn giải>`. ĐO ĐƯỢC 2/15 bài đầu
# tiên rơi vào đúng khuôn này, và cả hai đều bị chạm trần token — model lan man
# hết ngân sách rồi vội chép nốt khuôn kết.
#
# Lấy nguyên chuỗi giữ chỗ làm đáp số là phạt oan mốc nền vì một lỗi bám prompt,
# trong khi con số nó tính ra có thể vẫn nằm ngay phía trên. Nhận diện rồi tụt
# xuống nấc sau.
_GIU_CHO = re.compile(r"^<.*>$|chỉ đáp số|kèm đơn vị.*không diễn giải", re.IGNORECASE)


def _boc_dap_so(van_ban: str) -> str:
    """Lấy đáp số ra khỏi bài văn xuôi.

    Hai nấc, tụt dần. Nấc hai cố tình có mặt: model đôi khi quên dòng ĐÁP SỐ dù
    đã giải đúng, và chấm nó thành "không ra đáp án" là phạt oan mốc nền — đúng
    thứ làm hỏng tính công bằng của phép so sánh.
    """
    for k in reversed(_DONG_DAP_SO.findall(van_ban or "")):
        ung_vien = k.strip().strip("*` ")
        if ung_vien and not _GIU_CHO.search(ung_vien):
            return ung_vien
    for dong in reversed((van_ban or "").splitlines()):
        d = dong.strip().strip("*`# ")
        if d and re.search(r"\d", d):
            # Cắt phần dẫn: "Vậy khối lượng Fe3O4 là 7,73 gam" -> "7,73 gam".
            m = re.search(r"(?:=|\blà\b)\s*([^=]+)$", d)
            return (m.group(1) if m else d).strip()
    return ""


def _de_bai(bai: Bai) -> str:
    de = bai.question
    if bai.choices:
        de += "\n\n" + "\n".join(f"{k}. {v}" for k, v in sorted(bai.choices.items()))
    return de


async def chay_tho(bai: Bai, max_tokens: int, timeout: float) -> dict:
    """Một lời gọi ollama trần. Không Planner, không Verify, không công cụ."""
    client = ollama.AsyncClient(host=config.OLLAMA_HOST)

    t0 = time.perf_counter()
    van_ban, loi, bi_cat = "", "", False
    try:
        kq = await asyncio.wait_for(
            client.chat(
                model=config.MODEL_HEAVY,
                messages=[
                    {"role": "system", "content": SYSTEM_THO},
                    {"role": "user", "content": _de_bai(bai)},
                ],
                # `think=False` giống hệt mọi agent của hệ thống. Bật ở đây mà tắt
                # bên kia là so hai thứ khác nhau ở hai biến cùng lúc.
                think=False,
                options=_options(max_tokens),
            ),
            timeout=timeout,
        )
        van_ban = getattr(getattr(kq, "message", None), "content", "") or ""
        bi_cat = str(getattr(kq, "done_reason", "")) == "length"
    except asyncio.TimeoutError:
        loi = f"qua han {timeout:.0f}s"
    except Exception as e:  # noqa: BLE001 — một bài hỏng không được dừng cả chiến dịch
        loi = f"{type(e).__name__}: {e}"

    return {
        "tong_s": time.perf_counter() - t0,
        "dap_an": _boc_dap_so(van_ban),
        "mcq": "",  # `cham()` tự mò chữ cái A/B/C/D trong đáp án
        "so_buoc": len([d for d in van_ban.splitlines() if d.strip()]),
        "bi_cat": bi_cat,
        "loi": loi,
    }


# ---------------------------------------------------------------------------
# Mốc nền 2 — một lời gọi, ép schema `Solution`
# ---------------------------------------------------------------------------

SYSTEM_JSON = SYSTEM_THO.rsplit("DÒNG CUỐI CÙNG", 1)[0] + """
Trả về JSON đúng schema:
- steps: danh sách bước, mỗi bước gồm id, goal_vi, expression (LaTeX trần),
  result (kết quả bước kèm đơn vị), reason_vi
- final_answer: CHỈ đáp số kèm đơn vị, không diễn giải
- final_answer_latex: đáp số dạng LaTeX
- mcq_choice: "A"/"B"/"C"/"D" nếu là trắc nghiệm, không thì null
- unit: đơn vị của đáp số, không có thì null
- confidence: 0..1
"""


async def chay_json(bai: Bai, max_tokens: int, timeout: float) -> dict:
    """Một lời gọi có ràng buộc schema — dùng lại đúng lớp vỏ của hệ thống.

    Tên agent là `single_agent`, không nằm trong `config.AGENTS_SUY_NGHI`, nên chế
    độ suy nghĩ tắt y hệt các agent thật.
    """
    t0 = time.perf_counter()
    sol, span = await run_structured(
        name="single_agent",
        system=SYSTEM_JSON,
        task=_de_bai(bai),
        out_type=Solution,
        model=config.MODEL_HEAVY,
        timeout=timeout,
        max_tokens=max_tokens,
    )
    return {
        "tong_s": time.perf_counter() - t0,
        "dap_an": (sol.final_answer or "").strip() if sol else "",
        "mcq": (sol.mcq_choice or "") if sol else "",
        "so_buoc": len(sol.steps) if sol else 0,
        "bi_cat": "truncated" in (span.retry_reasons or []),
        "loi": "" if span.ok else (span.error or ""),
    }


# ---------------------------------------------------------------------------
# Báo cáo ra màn hình
# ---------------------------------------------------------------------------


def _thong_ke(kq: list[dict]) -> dict:
    """Gom mọi con số cần cho cả bản in màn hình lẫn bản Markdown."""
    n = len(kq)
    t = sorted(r["tong_s"] for r in kq)
    dung = sum(1 for r in kq if r["dung"])
    p = dung / n if n else 0.0
    return {
        "n": n,
        "dung": dung,
        "acc": p * 100,
        "bien": 1.96 * (p * (1 - p) / n) ** 0.5 * 100 if n else 0.0,
        "tb": sum(t) / n if n else 0.0,
        "p50": t[n // 2] if n else 0.0,
        "p95": t[min(n - 1, int(n * 0.95))] if n else 0.0,
        "nhanh": t[0] if n else 0.0,
        "cham": t[-1] if n else 0.0,
        "dat_45": sum(1 for r in kq if r["tong_s"] <= MOC_DE_BAI),
        "rong": sum(1 for r in kq if not r["dap_an"]),
        "cat": sum(1 for r in kq if r["bi_cat"]),
        "loi": sum(1 for r in kq if r["loi"]),
        "theo_mon": {
            m: (sum(1 for r in kq if r["bai"].subject == m and r["dung"]),
                sum(1 for r in kq if r["bai"].subject == m))
            for m in ("math", "physics", "chemistry")
        },
        "theo_muc": {
            mu: (sum(1 for r in kq if r["bai"].level == mu and r["dung"]),
                 sum(1 for r in kq if r["bai"].level == mu))
            for mu in CAC_MUC
        },
    }


def in_ket_qua(tk: dict, che_do: str) -> None:
    print("\n" + "=" * 68)
    print(f"MỐC NỀN MỘT TÁC TỬ — chế độ `{che_do}`")
    print("=" * 68)
    print(f"  Độ chính xác : {_ti_le(tk['dung'], tk['n'])}")
    print(f"  Khoảng tin cậy 95%: {tk['acc']:.1f}% ± {tk['bien']:.1f} điểm %  (n = {tk['n']})")

    print("\n  Theo môn:")
    for m, (d, s) in tk["theo_mon"].items():
        if s:
            print(f"    {TEN_MON[m]:<6} {_ti_le(d, s)}")
    print("\n  Theo mức độ:")
    for mu, (d, s) in tk["theo_muc"].items():
        if s:
            print(f"    {TEN_MUC[mu]:<14} {_ti_le(d, s)}")

    print("\n  Thời gian:")
    print(f"    Trung bình {tk['tb']:6.1f}s  |  p50 {tk['p50']:6.1f}s  |  p95 {tk['p95']:6.1f}s")
    print(f"    Đạt mốc đề bài {MOC_DE_BAI:.0f}s : {_ti_le(tk['dat_45'], tk['n'])}")

    print("\n  Sự cố:")
    print(f"    Không ra đáp án      : {tk['rong']}/{tk['n']}")
    print(f"    Bị cắt vì trần token : {tk['cat']}/{tk['n']}")
    print(f"    Lỗi ngoại lệ         : {tk['loi']}/{tk['n']}")

    print("\n  Khả năng phát hiện lời giải sai: KHÔNG CÓ.")
    print("    Mốc nền không có tầng kiểm chứng nào — đúng và sai được trả về với")
    print("    cùng một giọng tự tin. Khác biệt về BẢN CHẤT, không phải mức độ.")


# ---------------------------------------------------------------------------
# Đối chứng ghép cặp
# ---------------------------------------------------------------------------


def _mcnemar(b: int, c: int) -> float:
    """Kiểm định McNemar dạng chính xác (nhị thức), hai phía.

    Chỉ hai ô lệch nhau mới mang thông tin: bài cả hai cùng đúng hay cùng sai
    không nói gì về việc kiến trúc nào hơn. Dưới giả thuyết không, mỗi bài lệch
    có xác suất 1/2 rơi về mỗi phía.

    Dùng bản chính xác chứ không phải xấp xỉ khi-bình-phương: ở quy mô 150 bài số
    bài lệch thường chỉ vài chục, mà xấp xỉ khi-bình-phương chỉ đáng tin khi
    b + c đủ lớn (thường đòi ≥ 25).
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n) * 2)


def doi_chung(kq: list[dict], duong_dan_multi: Path) -> dict | None:
    """Ghép cặp theo `id` với một tệp kết quả đa tác tử đã chạy trước đó."""
    multi: dict[str, dict] = {}
    with duong_dan_multi.open(encoding="utf-8-sig", newline="") as f:
        for dong in csv.DictReader(f):
            multi[(dong.get("id") or "").strip()] = dong

    cap = [(r, multi[r["bai"].id]) for r in kq if r["bai"].id in multi]
    if not cap:
        return None

    # Cùng `id` nhưng khác đề bài là chuyện có thật: ba bộ đề dùng chung hệ thống
    # đánh id, chỉ khác tham số. Ghép nhầm thì bảng vẫn đẹp mà vô nghĩa hoàn toàn.
    lech = sum(
        1 for r, m in cap
        if (m.get("question") or "").strip()
        and m["question"].strip() != r["bai"].question.strip()
    )

    n = len(cap)
    return {
        "file": duong_dan_multi.name,
        "n": n,
        "lech_de": lech,
        "acc_don": sum(1 for r, _ in cap if r["dung"]) / n * 100,
        "acc_da": sum(1 for _, m in cap if m.get("dung") == "1") / n * 100,
        "t_don": sum(r["tong_s"] for r, _ in cap) / n,
        "t_da": sum(float(m.get("tong_s") or 0) for _, m in cap) / n,
        "cung_dung": sum(1 for r, m in cap if r["dung"] and m.get("dung") == "1"),
        "b": sum(1 for r, m in cap if not r["dung"] and m.get("dung") == "1"),
        "c": sum(1 for r, m in cap if r["dung"] and m.get("dung") != "1"),
        "cung_sai": sum(1 for r, m in cap if not r["dung"] and m.get("dung") != "1"),
        "sla_don": sum(1 for r, _ in cap if r["tong_s"] <= MOC_DE_BAI) / n * 100,
        "sla_da": sum(1 for _, m in cap if m.get("dat_45s") == "1") / n * 100,
        "rong_don": sum(1 for r, _ in cap if not r["dap_an"]) / n * 100,
        "rong_da": sum(1 for _, m in cap if not (m.get("dap_an_he_thong") or "").strip()) / n * 100,
        # Tỉ lệ phát hiện lời giải sai của đa tác tử, lấy từ chính cột của bench.py:
        # verdict FAIL trên những bài Subject Agent làm sai.
        "phat_hien_da": _phat_hien(cap),
        "theo_mon": {
            m: (
                sum(1 for r, _ in cap if r["bai"].subject == m and r["dung"]),
                sum(1 for _, mm in cap if mm.get("subject") == m and mm.get("dung") == "1"),
                sum(1 for r, _ in cap if r["bai"].subject == m),
            )
            for m in ("math", "physics", "chemistry")
        },
        "theo_muc": {
            mu: (
                sum(1 for r, _ in cap if r["bai"].level == mu and r["dung"]),
                sum(1 for _, mm in cap if mm.get("level") == mu and mm.get("dung") == "1"),
                sum(1 for r, _ in cap if r["bai"].level == mu),
            )
            for mu in CAC_MUC
        },
    }


def _phat_hien(cap: list) -> float:
    sai = [m for _, m in cap if m.get("dung_subject") != "1"]
    if not sai:
        return 0.0
    return sum(1 for m in sai if m.get("verdict") == "FAIL") / len(sai) * 100


def in_doi_chung(dc: dict) -> None:
    print("\n" + "=" * 68)
    print("ĐỐI CHỨNG GHÉP CẶP — MỘT TÁC TỬ so với ĐA TÁC TỬ")
    print("=" * 68)
    print(f"  Tệp đa tác tử : {dc['file']}")
    print(f"  Ghép được     : {dc['n']} bài")
    if dc["lech_de"]:
        print(f"  !! CẢNH BÁO: {dc['lech_de']} bài trùng id nhưng KHÁC ĐỀ. Hai lượt chạy")
        print("     không cùng bộ đề — bảng dưới đây không dùng được.")

    print(f"\n  {'':<24}{'Một tác tử':>13}{'Đa tác tử':>13}{'Chênh':>10}")
    print(f"  {'Độ chính xác (%)':<24}{dc['acc_don']:>13.1f}{dc['acc_da']:>13.1f}"
          f"{dc['acc_da'] - dc['acc_don']:>+10.1f}")
    print(f"  {'Thời gian TB (s)':<24}{dc['t_don']:>13.1f}{dc['t_da']:>13.1f}"
          f"{dc['t_da'] - dc['t_don']:>+10.1f}")
    print(f"  {'Đạt mốc 45s (%)':<24}{dc['sla_don']:>13.1f}{dc['sla_da']:>13.1f}"
          f"{dc['sla_da'] - dc['sla_don']:>+10.1f}")
    print(f"  {'Phát hiện lời giải sai':<24}{0.0:>13.1f}{dc['phat_hien_da']:>13.1f}"
          f"{dc['phat_hien_da']:>+10.1f}")

    print("\n  Bảng chéo (ghép cặp trên từng bài):")
    print(f"    {'':<24}{'Đa tác tử ĐÚNG':>16}{'Đa tác tử SAI':>16}")
    print(f"    {'Một tác tử ĐÚNG':<24}{dc['cung_dung']:>16}{dc['c']:>16}")
    print(f"    {'Một tác tử SAI':<24}{dc['b']:>16}{dc['cung_sai']:>16}")

    p = _mcnemar(dc["b"], dc["c"])
    print(f"\n  Đa tác tử cứu được {dc['b']} bài mà một tác tử làm sai.")
    print(f"  Đa tác tử làm hỏng {dc['c']} bài mà một tác tử làm đúng.")
    print(f"  McNemar (chính xác, hai phía): p = {p:.4g}"
          f"  -> {'CÓ' if p < 0.05 else 'CHƯA'} ý nghĩa thống kê ở mức 0,05")
    if p >= 0.05:
        print("     Đọc trung thực: chênh lệch chưa loại trừ được ngẫu nhiên ở cỡ mẫu")
        print("     này. Cần thêm bài hoặc thêm lượt lặp mới kết luận chắc.")


# ---------------------------------------------------------------------------
# Xuất tệp
# ---------------------------------------------------------------------------

COT_CSV = [
    "id", "subject", "topic", "level", "question_type", "che_do",
    "dung", "tong_s", "dat_45s", "dap_an_he_thong", "dap_an_chuan",
    "mcq_he_thong", "mcq_chuan", "so_buoc", "bi_cat", "loi", "question",
]


def xuat_csv(kq: list[dict], che_do: str, thu_muc: Path, dau_thoi_gian: str) -> Path:
    thu_muc.mkdir(parents=True, exist_ok=True)
    duong_dan = thu_muc / f"moc_nen_{che_do}_{dau_thoi_gian}.csv"
    with duong_dan.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COT_CSV)
        for r in kq:
            b: Bai = r["bai"]
            w.writerow([
                b.id, b.subject, b.topic, b.level, b.question_type, che_do,
                int(r["dung"]), f"{r['tong_s']:.2f}", int(r["tong_s"] <= MOC_DE_BAI),
                r["dap_an"], b.dap_an_chuan(), r["mcq"], b.answer_choice,
                r["so_buoc"], int(r["bi_cat"]), r["loi"], b.question,
            ])
    return duong_dan


def xuat_md(
    tk: dict, dc: dict | None, che_do: str, bo_de: str, csv_ra: Path,
    thu_muc: Path, dau_thoi_gian: str,
) -> Path:
    """Ghi bản Markdown — đây mới là thứ tìm lại được sau vài tuần.

    CSV là dữ liệu thô cho máy đọc; Markdown là kết luận cho người đọc, kèm đủ
    siêu dữ liệu để biết con số sinh ra trong điều kiện nào. Thiếu phần siêu dữ
    liệu thì ba tháng sau không ai dựng lại được lượt đo này.
    """
    thu_muc.mkdir(parents=True, exist_ok=True)
    duong_dan = thu_muc / f"so_sanh_{che_do}_{dau_thoi_gian}.md"
    L: list[str] = []

    L.append(f"# Đối chứng một tác tử vs đa tác tử — chế độ `{che_do}`\n")
    L.append(f"*Chạy lúc {datetime.now():%d/%m/%Y %H:%M}*\n")

    L.append("## Điều kiện đo\n")
    L.append("| Hạng mục | Giá trị |")
    L.append("|---|---|")
    L.append(f"| Bộ đề | `{bo_de}` ({tk['n']} bài) |")
    L.append(f"| Mô hình | `{config.MODEL_HEAVY}` qua Ollama, chạy cục bộ |")
    L.append(f"| Chế độ mốc nền | `{che_do}` "
             f"({'văn xuôi tự do' if che_do == 'tho' else 'ép schema Solution'}) |")
    L.append(f"| Temperature | {config.TEMPERATURE} |")
    L.append(f"| num_ctx | {config.NUM_CTX} |")
    L.append(f"| Chế độ suy nghĩ | tắt (giống mọi agent của hệ thống) |")
    L.append(f"| CSV thô | `{csv_ra.name}` |")
    L.append("")
    L.append("Chỉ đổi **một biến duy nhất là kiến trúc**. Model, tham số sinh, bộ đề và "
             "hàm chấm giữ y nguyên — hàm chấm dùng lại trực tiếp `cham()` của "
             "`bench.py`, không viết bản riêng.\n")

    if dc:
        L.append("## Kết quả tổng hợp\n")
        if dc["lech_de"]:
            L.append(f"> **CẢNH BÁO:** {dc['lech_de']} bài trùng id nhưng khác đề bài. "
                     f"Hai lượt chạy không cùng bộ đề, số liệu dưới đây không dùng được.\n")
        L.append("| Chỉ số | Một tác tử | Đa tác tử | Chênh |")
        L.append("|---|---:|---:|---:|")
        L.append(f"| Độ chính xác (%) | {dc['acc_don']:.1f} | {dc['acc_da']:.1f} "
                 f"| {dc['acc_da'] - dc['acc_don']:+.1f} |")
        L.append(f"| Thời gian TB (s) | {dc['t_don']:.1f} | {dc['t_da']:.1f} "
                 f"| {dc['t_da'] - dc['t_don']:+.1f} |")
        L.append(f"| Đạt mốc 45 s (%) | {dc['sla_don']:.1f} | {dc['sla_da']:.1f} "
                 f"| {dc['sla_da'] - dc['sla_don']:+.1f} |")
        L.append(f"| Phát hiện lời giải sai (%) | 0,0 | {dc['phat_hien_da']:.1f} "
                 f"| {dc['phat_hien_da']:+.1f} |")
        L.append(f"| Không ra đáp án (%) | {dc['rong_don']:.1f} | {dc['rong_da']:.1f} "
                 f"| {dc['rong_da'] - dc['rong_don']:+.1f} |")
        L.append(f"| Số lượt gọi LLM mỗi bài | 1 | 4–6 | — |")
        L.append("")
        L.append("Dòng *phát hiện lời giải sai* là **0 theo kiến tạo** ở mốc nền, không "
                 "phải do đo kém: một lời gọi đơn lẻ không có đường tính toán độc lập nào "
                 "để đối chiếu. Đây là khác biệt về bản chất, không phải về mức độ.\n")

        L.append("## Đối chứng ghép cặp\n")
        L.append(f"Ghép cặp theo `id` với `{dc['file']}` — {dc['n']} bài.\n")
        L.append("| | Đa tác tử ĐÚNG | Đa tác tử SAI |")
        L.append("|---|---:|---:|")
        L.append(f"| **Một tác tử ĐÚNG** | {dc['cung_dung']} | {dc['c']} |")
        L.append(f"| **Một tác tử SAI** | {dc['b']} | {dc['cung_sai']} |")
        L.append("")
        p = _mcnemar(dc["b"], dc["c"])
        L.append(f"- Đa tác tử **cứu được {dc['b']} bài** mà một tác tử làm sai.")
        L.append(f"- Đa tác tử **làm hỏng {dc['c']} bài** mà một tác tử làm đúng.")
        L.append(f"- **McNemar** (chính xác, hai phía): **p = {p:.4g}** — "
                 f"{'có' if p < 0.05 else 'CHƯA có'} ý nghĩa thống kê ở mức 0,05.")
        if p >= 0.05:
            L.append("")
            L.append("> Đọc trung thực: chênh lệch quan sát được chưa loại trừ được ngẫu "
                     "nhiên ở cỡ mẫu này. Cần thêm bài hoặc thêm lượt lặp mới kết luận chắc.")
        L.append("")
        L.append(f"Giá phải trả: đa tác tử tốn thêm **{dc['t_da'] - dc['t_don']:.1f} giây** "
                 f"mỗi lượt, tức **{dc['t_da'] / max(dc['t_don'], 1e-9):.1f} lần** chậm hơn.\n")

        L.append("## Phân rã theo môn\n")
        L.append("| Môn | Một tác tử | Đa tác tử | Số bài |")
        L.append("|---|---:|---:|---:|")
        for m, (d1, d2, s) in dc["theo_mon"].items():
            if s:
                L.append(f"| {TEN_MON[m]} | {d1 / s * 100:.1f}% | {d2 / s * 100:.1f}% | {s} |")
        L.append("")
        L.append("## Phân rã theo mức độ nhận thức\n")
        L.append("| Mức độ | Một tác tử | Đa tác tử | Số bài |")
        L.append("|---|---:|---:|---:|")
        for mu, (d1, d2, s) in dc["theo_muc"].items():
            if s:
                L.append(f"| {TEN_MUC[mu]} | {d1 / s * 100:.1f}% | {d2 / s * 100:.1f}% | {s} |")
        L.append("")
    else:
        L.append("## Kết quả mốc nền\n")
        L.append(f"- Độ chính xác: **{tk['acc']:.1f}%** ± {tk['bien']:.1f} điểm % (n = {tk['n']})")
        L.append(f"- Thời gian TB: {tk['tb']:.1f} s (p50 {tk['p50']:.1f} · p95 {tk['p95']:.1f})")
        L.append("")
        L.append("*(Không ghép cặp được với lượt chạy đa tác tử nào — dùng `--so-sanh`.)*\n")

    L.append("## Chi tiết mốc nền\n")
    L.append(f"- Độ chính xác: **{tk['acc']:.1f}%** ± {tk['bien']:.1f} điểm % (n = {tk['n']})")
    L.append(f"- Thời gian: TB {tk['tb']:.1f} s · p50 {tk['p50']:.1f} · p95 {tk['p95']:.1f} "
             f"· nhanh nhất {tk['nhanh']:.1f} · chậm nhất {tk['cham']:.1f}")
    L.append(f"- Đạt mốc 45 s: {tk['dat_45']}/{tk['n']}")
    L.append(f"- Không ra đáp án: {tk['rong']}/{tk['n']} · bị cắt vì trần token: "
             f"{tk['cat']}/{tk['n']} · lỗi ngoại lệ: {tk['loi']}/{tk['n']}")
    L.append("")
    L.append("| Môn | Đúng / Tổng | Tỉ lệ |")
    L.append("|---|---:|---:|")
    for m, (d, s) in tk["theo_mon"].items():
        if s:
            L.append(f"| {TEN_MON[m]} | {d}/{s} | {d / s * 100:.1f}% |")
    L.append("")
    L.append("| Mức độ | Đúng / Tổng | Tỉ lệ |")
    L.append("|---|---:|---:|")
    for mu, (d, s) in tk["theo_muc"].items():
        if s:
            L.append(f"| {TEN_MUC[mu]} | {d}/{s} | {d / s * 100:.1f}% |")
    L.append("")

    L.append("## Cách dựng lại\n")
    L.append("```bash")
    L.append(f"cd ViMultiAgent/backend")
    L.append(f"python scripts/bench_don_le.py --de {bo_de} --che-do {che_do} \\")
    L.append(f"    --so-sanh eval/reports/{dc['file'] if dc else '<ket_qua_da_tac_tu>.csv'}")
    L.append("```")
    L.append("")
    L.append("Prompt của mốc nền nằm trong `scripts/bench_don_le.py`, biến `SYSTEM_THO` "
             "và `SYSTEM_JSON`.")

    duong_dan.write_text("\n".join(L), encoding="utf-8")
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
        ten_bo_de = args.de
        print(f"Bộ đề: {duong_dan}  ({len(de)} bài)")
    else:
        de = list(bench.BAI_MAC_DINH)
        ten_bo_de = "(3 bài mẫu dựng sẵn)"
        print("Bộ đề: 3 bài mẫu dựng sẵn (dùng --de để chạy bộ đề chuẩn)")

    if args.mon:
        loc = {m.strip() for m in args.mon.split(",") if m.strip()}
        de = [b for b in de if b.subject in loc]
    if args.muc:
        loc = {m.strip().upper() for m in args.muc.split(",") if m.strip()}
        de = [b for b in de if b.level in loc]
    if args.so_luong:
        # Lấy trải đều thay vì cắt N bài đầu — cắt đầu thì chỉ toàn Toán mức NB.
        buoc = max(1, len(de) // args.so_luong)
        de = de[::buoc][: args.so_luong]
    if not de:
        print("Bộ lọc không chừa lại bài nào.")
        return 2

    print(f"Chế độ: {args.che_do}  |  Model: {config.MODEL_HEAVY}  |  "
          f"trần token {args.tokens}  |  hạn {args.timeout:.0f}s")
    print(f"Sẽ chạy {len(de) * args.n} lượt. Đừng dùng giao diện lúc này — tranh GPU "
          f"làm sai số đo.\n")

    chay = chay_json if args.che_do == "json" else chay_tho
    kq: list[dict] = []
    tong_luot = len(de) * args.n
    for lap in range(args.n):
        for i, bai in enumerate(de, start=1):
            r = await chay(bai, args.tokens, args.timeout)
            r["bai"] = bai
            r["dung"] = cham(bai, r["dap_an"], r["mcq"]) if not r["loi"] else False
            kq.append(r)
            print(
                f"[{lap * len(de) + i:3}/{tong_luot}] {bai.mon_vi:<5} {bai.level:<3} "
                f"{bai.id:<14} {'ĐÚNG' if r['dung'] else 'SAI '} {r['tong_s']:6.1f}s"
                f"  {r['dap_an'][:34]!r}" + ("  [CẮT]" if r["bi_cat"] else ""),
                flush=True,
            )
            if r["loi"]:
                print(f"          lỗi: {r['loi'][:80]}", flush=True)

    tk = _thong_ke(kq)
    in_ket_qua(tk, args.che_do)

    dc = None
    if args.so_sanh:
        p = Path(args.so_sanh)
        if not p.is_absolute():
            p = GOC_BACKEND / p
        if not p.exists():
            print(f"\n(Không thấy tệp đa tác tử để so sánh: {p})")
        else:
            dc = doi_chung(kq, p)
            if dc:
                in_doi_chung(dc)
            else:
                print(f"\n(Không ghép được cặp nào với {p.name} — khác bộ đề?)")

    dau = f"{datetime.now():%Y%m%d_%H%M%S}"
    thu_muc = Path(args.out) if args.out else GOC_BACKEND / "eval" / "reports"
    csv_ra = xuat_csv(kq, args.che_do, thu_muc, dau)
    md_ra = xuat_md(tk, dc, args.che_do, ten_bo_de, csv_ra, thu_muc, dau)
    print(f"\nCSV chi tiết từng lượt : {csv_ra}")
    print(f"Báo cáo Markdown       : {md_ra}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Mốc nền một tác tử cho ViMultiAgent")
    ap.add_argument("--de", help="đường dẫn CSV bộ đề")
    ap.add_argument("--che-do", choices=("tho", "json"), default="tho",
                    dest="che_do", help="tho = văn xuôi tự do; json = ép schema")
    ap.add_argument("--n", type=int, default=1, help="số lượt lặp")
    ap.add_argument("--mon", help="lọc môn: math,physics,chemistry")
    ap.add_argument("--muc", help="lọc mức độ: NB,TH,VD,VDC")
    ap.add_argument("--so-luong", type=int, dest="so_luong",
                    help="chỉ chạy N bài lấy trải đều — để chạy thử nhanh")
    # Mặc định = TOÀN BỘ ngân sách token mà hệ đa tác tử tiêu cho một bài
    # (Planner + Subject + Verify + Explain). Cấp trọn chứ không cấp một phần.
    #
    # Lý do: mốc nền phải làm trọn mọi việc trong MỘT lượt — đọc đề, giải, trình
    # bày — nên cắt bớt ngân sách của nó là tạo ra lợi thế giả cho phía đa tác tử,
    # và người phản biện sẽ vặn ngay "vậy là các anh bóp cổ mốc nền". Cấp dư còn
    # hơn cấp thiếu: mốc nền càng mạnh thì kết luận càng chắc.
    #
    # ĐO ĐƯỢC ở trần 1500: 2/15 bài đầu chạm trần rồi bị cắt giữa chừng.
    ap.add_argument("--tokens", type=int,
                    default=(config.MAX_TOKENS_PLANNER + config.MAX_TOKENS_SUBJECT
                             + config.MAX_TOKENS_VERIFY + config.MAX_TOKENS_EXPLAIN),
                    help="trần token đầu ra cho lượt gọi duy nhất")
    ap.add_argument("--timeout", type=float, default=config.SLA_SECONDS,
                    help="hạn cho một lượt (mặc định = SLA của hệ thống)")
    ap.add_argument("--so-sanh", dest="so_sanh",
                    help="CSV kết quả đa tác tử để ghép cặp đối chứng")
    ap.add_argument("--out", help="thư mục ghi CSV + Markdown kết quả")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
