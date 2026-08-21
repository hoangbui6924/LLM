"""Vẽ biểu đồ đối chứng MỘT TÁC TỬ vs ĐA TÁC TỬ — hình cho báo cáo.

Đọc hai tệp CSV đã có sẵn, không chạy lại mô hình:

    * CSV mốc nền   — do `scripts/bench_don_le.py` sinh ra (`moc_nen_*.csv`)
    * CSV đa tác tử — do `scripts/bench.py` sinh ra (`ket_qua_sla45_*.csv`)

Chạy:
    python scripts/ve_so_sanh.py \
        --don eval/reports/moc_nen_tho_....csv \
        --da  eval/reports/ket_qua_sla45_20260809_205118.csv

Sinh ra 5 tệp PNG cùng một tệp Markdown gộp mọi bảng số — Markdown là thứ tìm
lại được sau vài tuần, PNG là thứ dán vào báo cáo.

Hàm nào sinh tệp nào
--------------------
Phần `<hậu tố>` lấy từ cờ `--hau-to`, không có thì tự lấy dấu thời gian. Chạy lại
với CÙNG hậu tố là ghi đè bộ cũ; đó là chủ ý, để báo cáo đã nhúng ảnh không phải
sửa đường dẫn mỗi lần vẽ lại.

    hinh_chi_so()     -> 01_chi_so_cot_loi_<hậu tố>.png
    hinh_thoi_gian()  -> 02_thoi_gian_<hậu tố>.png
    hinh_radar()      -> 03_radar_<hậu tố>.png
    hinh_phan_ra()    -> 04_phan_ra_<hậu tố>.png
    hinh_rong()       -> 05_hieu_qua_rong_<hậu tố>.png
    xuat_md()         -> BAOCAO_SO_SANH_<hậu tố>.md

Chỗ nối tên hàm với tên tệp nằm trong `main()` ở cuối file, danh sách `hinh`.

Quy ước trình bày (giữ nguyên qua cả 5 hình)
--------------------------------------------
* **Màu theo thực thể, không theo thứ hạng.** Một tác tử LUÔN là cam, đa tác tử
  LUÔN là xanh, ở mọi hình. Đổi màu giữa các hình là cách chắc chắn làm người đọc
  hiểu nhầm.
* **Không dùng đồ thị hai trục tung.** Ghép thời gian và số lượt gọi LLM lên cùng
  một khung với hai thang khác nhau sẽ *bịa ra* một tương quan không có trong dữ
  liệu, vì cách canh hai thang là tuỳ tiện. Hai đại lượng khác đơn vị thì tách
  thành hai khung.
* **Nhãn số ngay trên cột.** Hình PNG không có tooltip, nên nhãn trực tiếp là
  đường duy nhất đọc được giá trị. Bảng số trong tệp Markdown là bản đối chiếu.
* Lưới kẻ mảnh, liền nét, chìm hẳn xuống dưới; không viền quanh cột.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

GOC_BACKEND = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Bảng màu — hai ô đầu của bộ màu phân loại, đã soát bằng bộ kiểm tra mù màu.
# Cặp này đạt cả 5 phép kiểm trên nền trắng: ΔE mù màu 24,7 (ngưỡng 8) và ΔE thị
# lực thường 33,6 (ngưỡng 15). Đừng đổi sang cặp khác mà không soát lại.
# ---------------------------------------------------------------------------
MAU_DON = "#eb6834"   # cam  — một tác tử
MAU_DA = "#2a78d6"    # xanh — đa tác tử
MUC = "#898781"       # chữ phụ, vạch trục
LUOI = "#e1e0d9"      # lưới kẻ mảnh
INK = "#0b0b0b"       # chữ chính
INK2 = "#52514e"      # chữ phụ đậm hơn
NEN = "#ffffff"       # nền trắng để dán vào Word

TEN_DON = "Một tác tử"
TEN_DA = "Đa tác tử"

TEN_MON = {"dai_so": "Đại số", "hinh_hoc": "Hình học"}
TEN_MUC = {"NB": "Nhận biết", "TH": "Thông hiểu", "VD": "Vận dụng", "VDC": "Vận dụng cao"}
MOC_DE_BAI = 45.0

plt.rcParams.update({
    "font.family": "DejaVu Sans",   # phông duy nhất trong matplotlib phủ đủ dấu tiếng Việt
    "font.size": 11,
    "axes.edgecolor": MUC,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "figure.facecolor": NEN,
    "axes.facecolor": NEN,
    "savefig.facecolor": NEN,
})


def _khung(ax, tren: float | None = None) -> None:
    """Bỏ khung thừa, để lại lưới ngang mảnh và liền nét.

    Lưới đứt nét đọc thành "ngưỡng" hoặc "dự báo" trong khi nó chỉ là lưới, nên
    dùng nét liền một tông chìm hơn nền.
    """
    for canh in ("top", "right"):
        ax.spines[canh].set_visible(False)
    for canh in ("left", "bottom"):
        ax.spines[canh].set_color(MUC)
        ax.spines[canh].set_linewidth(0.8)
    ax.grid(axis="y", color=LUOI, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    if tren is not None:
        ax.set_ylim(0, tren)


def _nhan_cot(ax, thanh, dinh_dang: str = "{:.1f}") -> None:
    for t in thanh:
        h = t.get_height()
        ax.annotate(
            dinh_dang.format(h),
            (t.get_x() + t.get_width() / 2, h),
            textcoords="offset points", xytext=(0, 4),
            ha="center", va="bottom", fontsize=9.5, color=INK2,
        )


# ---------------------------------------------------------------------------
# Đọc dữ liệu
# ---------------------------------------------------------------------------


def doc(duong_dan: Path) -> list[dict]:
    with duong_dan.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ghep(don: list[dict], da: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Ghép cặp theo `id`, giữ đúng thứ tự và chỉ giữ bài có ở CẢ HAI bên.

    Trả thêm số bài trùng id nhưng khác đề — ba bộ đề dùng chung hệ thống đánh id
    nên đây là lỗi thật sự có thể xảy ra, và nó làm mọi hình vẽ ra thành vô nghĩa.
    """
    bang = {(r.get("id") or "").strip(): r for r in da}
    a, b, lech = [], [], 0
    for r in don:
        k = (r.get("id") or "").strip()
        if k not in bang:
            continue
        m = bang[k]
        if (m.get("question") or "").strip() and (r.get("question") or "").strip():
            if m["question"].strip() != r["question"].strip():
                lech += 1
        a.append(r)
        b.append(m)
    return a, b, lech


def _ti_le(rows: list[dict], dieu_kien) -> float:
    return sum(1 for r in rows if dieu_kien(r)) / len(rows) * 100 if rows else 0.0


def _tb(rows: list[dict], cot: str) -> float:
    v = [float(r[cot]) for r in rows if (r.get(cot) or "").strip()]
    return sum(v) / len(v) if v else 0.0


def _phan_vi(rows: list[dict], cot: str, q: float) -> float:
    v = sorted(float(r[cot]) for r in rows if (r.get(cot) or "").strip())
    return v[min(len(v) - 1, int(len(v) * q))] if v else 0.0


def phat_hien_sai(da: list[dict]) -> float:
    """Tỉ lệ Verify bắt được lời giải sai của Subject Agent (verdict FAIL).

    Chấm trên `dung_subject` — đáp số TRƯỚC bước cứu — vì Verify soi đúng bản đó.
    """
    sai = [r for r in da if r.get("dung_subject") != "1"]
    if not sai:
        return 0.0
    return sum(1 for r in sai if r.get("verdict") == "FAIL") / len(sai) * 100


def chi_so(don: list[dict], da: list[dict]) -> dict:
    return {
        "n": len(don),
        "acc_don": _ti_le(don, lambda r: r.get("dung") == "1"),
        "acc_da": _ti_le(da, lambda r: r.get("dung") == "1"),
        # Mốc nền không có tầng kiểm chứng nào -> 0 THEO KIẾN TẠO, không phải đo kém.
        "ph_don": 0.0,
        "ph_da": phat_hien_sai(da),
        "sla_don": _ti_le(don, lambda r: r.get("dat_45s") == "1"),
        "sla_da": _ti_le(da, lambda r: r.get("dat_45s") == "1"),
        "co_dap_don": _ti_le(don, lambda r: bool((r.get("dap_an_he_thong") or "").strip())),
        "co_dap_da": _ti_le(da, lambda r: bool((r.get("dap_an_he_thong") or "").strip())),
        "t_don": _tb(don, "tong_s"),
        "t_da": _tb(da, "tong_s"),
        "p50_don": _phan_vi(don, "tong_s", 0.50),
        "p50_da": _phan_vi(da, "tong_s", 0.50),
        "p95_don": _phan_vi(don, "tong_s", 0.95),
        "p95_da": _phan_vi(da, "tong_s", 0.95),
    }


def mcnemar(don: list[dict], da: list[dict]) -> dict:
    b = sum(1 for x, y in zip(don, da) if x.get("dung") != "1" and y.get("dung") == "1")
    c = sum(1 for x, y in zip(don, da) if x.get("dung") == "1" and y.get("dung") != "1")
    cd = sum(1 for x, y in zip(don, da) if x.get("dung") == "1" and y.get("dung") == "1")
    cs = len(don) - b - c - cd
    n = b + c
    # Bản CHÍNH XÁC (nhị thức) chứ không phải xấp xỉ khi-bình-phương: số bài lệch ở
    # quy mô 150 thường chỉ vài chục, dưới ngưỡng b+c >= 25 mà xấp xỉ đòi hỏi.
    p = 1.0 if n == 0 else min(
        1.0, sum(math.comb(n, i) for i in range(min(b, c) + 1)) * (0.5 ** n) * 2
    )
    return {"b": b, "c": c, "cung_dung": cd, "cung_sai": cs, "p": p}


# ---------------------------------------------------------------------------
# Hình 1 — bốn chỉ số cốt lõi  ->  01_chi_so_cot_loi_<hậu tố>.png
# ---------------------------------------------------------------------------


def hinh_chi_so(cs: dict, ra: Path) -> Path:
    nhan = ["Độ chính xác", "Phát hiện\nlời giải sai", "Đạt mốc 45 s", "Ra được\nđáp án"]
    v_don = [cs["acc_don"], cs["ph_don"], cs["sla_don"], cs["co_dap_don"]]
    v_da = [cs["acc_da"], cs["ph_da"], cs["sla_da"], cs["co_dap_da"]]

    x = np.arange(len(nhan))
    w = 0.36
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    t1 = ax.bar(x - w / 2 - 0.01, v_don, w, label=TEN_DON, color=MAU_DON)
    t2 = ax.bar(x + w / 2 + 0.01, v_da, w, label=TEN_DA, color=MAU_DA)
    _nhan_cot(ax, t1)
    _nhan_cot(ax, t2)

    ax.set_xticks(x, nhan)
    ax.set_ylabel("Tỉ lệ (%)")
    ax.set_title("Bốn chỉ số cốt lõi — cùng bộ đề, cùng mô hình, cùng thước chấm",
                 fontsize=13, fontweight="bold", pad=14)
    _khung(ax, 112)
    ax.legend(frameon=False, ncols=2, loc="upper right")

    # Ghi chú vào đúng cột đáng chú ý nhất. Cột "phát hiện lời giải sai" của mốc
    # nền bằng 0 vì không có gì để đo, chứ không phải vì đo ra 0 — hai chuyện khác
    # hẳn nhau, và không chú thích thì người đọc hiểu thành cái thứ hai.
    # Đẩy lên trên hẳn nhãn `0.0` — hai chú thích cùng neo vào y = 0 thì chồng
    # lên nhau và đọc thành một khối chữ vô nghĩa.
    ax.annotate(
        "không có tầng\nkiểm chứng",
        (1 - w / 2 - 0.01, 0), textcoords="offset points", xytext=(0, 20),
        ha="center", va="bottom", fontsize=8.5, color=MUC, style="italic",
    )
    fig.tight_layout()
    fig.savefig(ra, dpi=200)
    plt.close(fig)
    return ra


# ---------------------------------------------------------------------------
# Hình 2 — thời gian (một trục duy nhất)  ->  02_thoi_gian_<hậu tố>.png
# ---------------------------------------------------------------------------


def hinh_thoi_gian(cs: dict, ra: Path) -> Path:
    nhan = ["Trung bình", "Trung vị (p50)", "Bách phân vị 95"]
    v_don = [cs["t_don"], cs["p50_don"], cs["p95_don"]]
    v_da = [cs["t_da"], cs["p50_da"], cs["p95_da"]]

    x = np.arange(len(nhan))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    t1 = ax.bar(x - w / 2 - 0.01, v_don, w, label=TEN_DON, color=MAU_DON)
    t2 = ax.bar(x + w / 2 + 0.01, v_da, w, label=TEN_DA, color=MAU_DA)
    _nhan_cot(ax, t1)
    _nhan_cot(ax, t2)

    ax.axhline(MOC_DE_BAI, color=MUC, linewidth=1.0)
    ax.annotate("Mốc đề bài 45 s", (len(nhan) - 0.5, MOC_DE_BAI),
                textcoords="offset points", xytext=(0, 4),
                ha="right", va="bottom", fontsize=9, color=MUC)

    ax.set_xticks(x, nhan)
    ax.set_ylabel("Thời gian (giây)")
    ax.set_title("Giá phải trả: độ trễ end-to-end", fontsize=13, fontweight="bold", pad=14)
    _khung(ax, max(max(v_da), MOC_DE_BAI) * 1.25)
    ax.legend(frameon=False, ncols=2, loc="upper left")
    fig.tight_layout()
    fig.savefig(ra, dpi=200)
    plt.close(fig)
    return ra


# ---------------------------------------------------------------------------
# Hình 3 — radar tổng hợp  ->  03_radar_<hậu tố>.png
# ---------------------------------------------------------------------------


def diem_toc_do(t: float) -> float:
    """Quy thời gian thành điểm 0–100 để đưa lên radar.

    Công thức: 100 × (45 − t) / 45, chặn trong [0, 100]. Chọn mốc 45 giây vì đó
    là ngân sách đã đăng ký của đề tài, nên "hết sạch ngân sách" = 0 điểm là một
    quy ước có căn cứ, không phải một hằng số tự đặt. Ghi rõ công thức ở đây và
    trong tệp Markdown: trục radar không nêu cách quy đổi là trục không kiểm chứng
    được, và đó là chỗ hội đồng hỏi đầu tiên.
    """
    return max(0.0, min(100.0, (MOC_DE_BAI - t) / MOC_DE_BAI * 100))


def hinh_radar(cs: dict, ra: Path) -> Path:
    truc = ["Độ chính xác", "Phát hiện lỗi", "Tốc độ", "Đạt mốc 45 s", "Ra được đáp án"]
    v_don = [cs["acc_don"], cs["ph_don"], diem_toc_do(cs["t_don"]),
             cs["sla_don"], cs["co_dap_don"]]
    v_da = [cs["acc_da"], cs["ph_da"], diem_toc_do(cs["t_da"]),
            cs["sla_da"], cs["co_dap_da"]]

    goc = np.linspace(0, 2 * np.pi, len(truc), endpoint=False).tolist()
    goc += goc[:1]
    fig, ax = plt.subplots(figsize=(7.4, 7.4), subplot_kw={"projection": "polar"})

    for gia_tri, mau, ten in ((v_don, MAU_DON, TEN_DON), (v_da, MAU_DA, TEN_DA)):
        g = gia_tri + gia_tri[:1]
        ax.plot(goc, g, color=mau, linewidth=2.0, label=ten)
        ax.fill(goc, g, color=mau, alpha=0.13)

    ax.set_xticks(goc[:-1], truc, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8.5, color=MUC)
    ax.tick_params(pad=12)
    ax.grid(color=LUOI, linewidth=0.8)
    ax.spines["polar"].set_color(LUOI)
    ax.set_title("Ma trận radar tổng hợp (thang 0–100)",
                 fontsize=13, fontweight="bold", pad=26)
    ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.18, 1.10))
    fig.text(0.5, 0.025,
             "Trục “Tốc độ” quy đổi từ thời gian: 100 × (45 − t) / 45.  "
             "Bốn trục còn lại là tỉ lệ phần trăm đo trực tiếp.",
             ha="center", fontsize=8.5, color=MUC)
    fig.tight_layout()
    fig.savefig(ra, dpi=200)
    plt.close(fig)
    return ra


# ---------------------------------------------------------------------------
# Hình 4 — phân rã theo môn và theo mức độ  ->  04_phan_ra_<hậu tố>.png
# ---------------------------------------------------------------------------


def _theo_nhom(don: list[dict], da: list[dict], cot: str, khoa: list[str]) -> tuple:
    v_don, v_da, dem = [], [], []
    for k in khoa:
        a = [r for r in don if (r.get(cot) or "").strip().upper() == k.upper()]
        b = [r for r in da if (r.get(cot) or "").strip().upper() == k.upper()]
        v_don.append(_ti_le(a, lambda r: r.get("dung") == "1"))
        v_da.append(_ti_le(b, lambda r: r.get("dung") == "1"))
        dem.append(len(a))
    return v_don, v_da, dem


def hinh_phan_ra(don: list[dict], da: list[dict], ra: Path) -> Path:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4))

    for ax, cot, khoa, ten, tieu_de in (
        (ax1, "subject", ["dai_so", "hinh_hoc"], TEN_MON, "Theo phân môn"),
        (ax2, "level", ["NB", "TH", "VD", "VDC"], TEN_MUC, "Theo mức độ nhận thức"),
    ):
        v_don, v_da, dem = _theo_nhom(don, da, cot, khoa)
        x = np.arange(len(khoa))
        w = 0.36
        t1 = ax.bar(x - w / 2 - 0.01, v_don, w, label=TEN_DON, color=MAU_DON)
        t2 = ax.bar(x + w / 2 + 0.01, v_da, w, label=TEN_DA, color=MAU_DA)
        _nhan_cot(ax, t1)
        _nhan_cot(ax, t2)
        ax.set_xticks(x, [f"{ten[k]}\n(n={d})" for k, d in zip(khoa, dem)])
        ax.set_ylabel("Độ chính xác (%)")
        ax.set_title(tieu_de, fontsize=12, fontweight="bold", pad=12)
        _khung(ax, 112)
        ax.legend(frameon=False, ncols=2, loc="upper right")

    fig.suptitle("Khoảng cách hai kiến trúc nở ra ở đâu",
                 fontsize=13, fontweight="bold", y=0.99)
    fig.tight_layout()
    fig.savefig(ra, dpi=200)
    plt.close(fig)
    return ra


# ---------------------------------------------------------------------------
# Hình 5 — hiệu quả ròng của kiến trúc đa tác tử  ->  05_hieu_qua_rong_<hậu tố>.png
# ---------------------------------------------------------------------------


def hinh_rong(mn: dict, n: int, ra: Path) -> Path:
    """Chỉ hai ô lệch nhau mới mang thông tin, nên chỉ vẽ hai ô đó.

    Bài cả hai cùng đúng hoặc cùng sai không nói gì về việc kiến trúc nào hơn —
    đó chính là lý do kiểm định McNemar bỏ qua chúng. Vẽ cả bốn ô sẽ để hai cột
    lớn vô nghĩa lấn át hai cột thật sự mang kết luận.
    """
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    nhan = ["Đa tác tử CỨU được\n(một tác tử sai → đa tác tử đúng)",
            "Đa tác tử LÀM HỎNG\n(một tác tử đúng → đa tác tử sai)"]
    gia_tri = [mn["b"], mn["c"]]
    thanh = ax.barh(nhan, gia_tri, height=0.5, color=[MAU_DA, MAU_DON])
    for t, v in zip(thanh, gia_tri):
        ax.annotate(f"{v} bài", (v, t.get_y() + t.get_height() / 2),
                    textcoords="offset points", xytext=(6, 0),
                    va="center", fontsize=11, color=INK2, fontweight="bold")

    ax.invert_yaxis()
    for canh in ("top", "right", "left"):
        ax.spines[canh].set_visible(False)
    ax.spines["bottom"].set_color(MUC)
    ax.grid(axis="x", color=LUOI, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(gia_tri + [1]) * 1.28)
    # Đếm số bài thì trục phải là số nguyên — vạch 2,5 bài là vạch vô nghĩa.
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.set_xlabel("Số bài")
    ax.set_title(f"Hiệu quả ròng trên {n} bài ghép cặp  ·  McNemar p = {mn['p']:.4g}",
                 fontsize=11.5, fontweight="bold", pad=14)
    # Chừa sẵn dải dưới rồi mới đặt chú thích, nếu không `tight_layout` kéo nhãn
    # trục xuống đúng chỗ dòng chữ này và hai thứ chồng lên nhau.
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.text(0.5, 0.02,
             f"Ròng: {mn['b'] - mn['c']:+d} bài.  "
             f"{'Có' if mn['p'] < 0.05 else 'Chưa có'} ý nghĩa thống kê ở mức 0,05.",
             ha="center", fontsize=9.5, color=MUC)
    fig.savefig(ra, dpi=200)
    plt.close(fig)
    return ra


# ---------------------------------------------------------------------------
# Markdown gộp  ->  BAOCAO_SO_SANH_<hậu tố>.md
# ---------------------------------------------------------------------------


def xuat_md(cs, mn, don, da, lech, ten_don, ten_da, hinh, ra: Path) -> Path:
    L: list[str] = []
    L.append("# Đối chứng kiến trúc: MỘT TÁC TỬ vs ĐA TÁC TỬ\n")
    L.append(f"*Dựng lúc {datetime.now():%d/%m/%Y %H:%M} · {cs['n']} bài ghép cặp*\n")

    if lech:
        L.append(f"> **CẢNH BÁO:** {lech} bài trùng `id` nhưng khác đề bài. "
                 f"Hai lượt chạy không cùng bộ đề — số liệu dưới đây không dùng được.\n")

    L.append("## Nguồn dữ liệu\n")
    L.append("| Nhánh | Tệp CSV |")
    L.append("|---|---|")
    L.append(f"| Một tác tử | `{ten_don}` |")
    L.append(f"| Đa tác tử | `{ten_da}` |")
    L.append("")
    L.append("Chỉ đổi **một biến duy nhất là kiến trúc**: cùng mô hình `qwen3:4b`, cùng "
             "`temperature`, cùng `num_ctx`, cùng tắt chế độ suy nghĩ, cùng bộ đề, và cùng "
             "hàm chấm — `cham()` của `bench.py` được dùng lại trực tiếp cho cả hai nhánh "
             "thay vì viết hai bản.\n")

    L.append("## Bốn chỉ số cốt lõi\n")
    L.append(f"![Bốn chỉ số cốt lõi]({hinh[0].name})\n")
    L.append("| Chỉ số | Một tác tử | Đa tác tử | Chênh |")
    L.append("|---|---:|---:|---:|")
    for ten, a, b in (
        ("Độ chính xác (%)", cs["acc_don"], cs["acc_da"]),
        ("Phát hiện lời giải sai (%)", cs["ph_don"], cs["ph_da"]),
        ("Đạt mốc 45 s (%)", cs["sla_don"], cs["sla_da"]),
        ("Ra được đáp án (%)", cs["co_dap_don"], cs["co_dap_da"]),
    ):
        L.append(f"| {ten} | {a:.1f} | {b:.1f} | {b - a:+.1f} |")
    L.append("")
    L.append("Dòng *phát hiện lời giải sai* bằng **0 theo kiến tạo** ở mốc nền, không phải "
             "do đo kém: một lời gọi LLM đơn lẻ không có đường tính toán độc lập nào để "
             "đối chiếu, nên đúng và sai được trả về với cùng một giọng tự tin. Đây là "
             "khác biệt về **bản chất**, không phải về mức độ — và là lập luận mạnh nhất "
             "của kiến trúc đa tác tử, mạnh hơn vài điểm phần trăm độ chính xác.\n")

    L.append("## Giá phải trả: độ trễ\n")
    L.append(f"![Thời gian]({hinh[1].name})\n")
    L.append("| Thống kê thời gian | Một tác tử | Đa tác tử |")
    L.append("|---|---:|---:|")
    L.append(f"| Trung bình (s) | {cs['t_don']:.1f} | {cs['t_da']:.1f} |")
    L.append(f"| Trung vị p50 (s) | {cs['p50_don']:.1f} | {cs['p50_da']:.1f} |")
    L.append(f"| Bách phân vị 95 (s) | {cs['p95_don']:.1f} | {cs['p95_da']:.1f} |")
    L.append(f"| Số lượt gọi LLM mỗi bài | 1 | 4–6 |")
    L.append("")
    L.append(f"Đa tác tử chậm hơn **{cs['t_da'] - cs['t_don']:.1f} giây** mỗi lượt, tức "
             f"**{cs['t_da'] / max(cs['t_don'], 1e-9):.1f} lần**. Đây là cái giá của việc "
             "chạy thêm Planner, Router, bộ tính lại, Verify và Explain.\n")

    L.append("## Ma trận radar tổng hợp\n")
    L.append(f"![Radar]({hinh[2].name})\n")
    L.append("Bốn trục là tỉ lệ phần trăm đo trực tiếp. Trục **Tốc độ** quy đổi từ thời "
             "gian theo công thức `100 × (45 − t) / 45`, chặn trong [0, 100]; mốc 45 giây "
             "là ngân sách đã đăng ký của đề tài chứ không phải hằng số tự đặt.\n")
    L.append("> Lưu ý khi đọc: diện tích hình radar **không** có ý nghĩa toán học, và đổi "
             "thứ tự trục là đổi hẳn hình dạng. Dùng nó để nhìn nhanh hình thái mạnh–yếu, "
             "đừng dùng để so hơn kém — việc đó thuộc về các hình cột.\n")

    L.append("## Khoảng cách nở ra ở đâu\n")
    L.append(f"![Phân rã]({hinh[3].name})\n")
    for cot, khoa, ten, tieu in (
        ("subject", ["dai_so", "hinh_hoc"], TEN_MON, "Phân môn"),
        ("level", ["NB", "TH", "VD", "VDC"], TEN_MUC, "Mức độ"),
    ):
        v_don, v_da, dem = _theo_nhom(don, da, cot, khoa)
        L.append(f"| {tieu} | Một tác tử | Đa tác tử | Chênh | Số bài |")
        L.append("|---|---:|---:|---:|---:|")
        for k, a, b, d in zip(khoa, v_don, v_da, dem):
            L.append(f"| {ten[k]} | {a:.1f}% | {b:.1f}% | {b - a:+.1f} | {d} |")
        L.append("")

    L.append("## Hiệu quả ròng và kiểm định thống kê\n")
    L.append(f"![Hiệu quả ròng]({hinh[4].name})\n")
    L.append("| | Đa tác tử ĐÚNG | Đa tác tử SAI |")
    L.append("|---|---:|---:|")
    L.append(f"| **Một tác tử ĐÚNG** | {mn['cung_dung']} | {mn['c']} |")
    L.append(f"| **Một tác tử SAI** | {mn['b']} | {mn['cung_sai']} |")
    L.append("")
    L.append(f"- Đa tác tử **cứu được {mn['b']} bài** mà một tác tử làm sai.")
    L.append(f"- Đa tác tử **làm hỏng {mn['c']} bài** mà một tác tử làm đúng.")
    L.append(f"- Ròng: **{mn['b'] - mn['c']:+d} bài**.")
    L.append(f"- **McNemar** (dạng chính xác, hai phía): **p = {mn['p']:.4g}** — "
             f"{'có' if mn['p'] < 0.05 else '**chưa** có'} ý nghĩa thống kê ở mức 0,05.")
    L.append("")
    L.append("Dùng kiểm định ghép cặp chứ không so hai tỉ lệ rời nhau: cùng một bộ đề chạy "
             "hai kiến trúc là thiết kế **đo lặp trên cùng đối tượng**. Chỉ hai ô lệch nhau "
             "mang thông tin — bài cả hai cùng đúng hay cùng sai không nói gì về việc kiến "
             "trúc nào hơn. Dùng bản chính xác thay vì xấp xỉ khi-bình-phương vì số bài "
             f"lệch chỉ có {mn['b'] + mn['c']}, dưới ngưỡng ≥ 25 mà xấp xỉ đòi hỏi.\n")
    if mn["p"] >= 0.05:
        L.append("> **Đọc trung thực:** chênh lệch quan sát được chưa loại trừ được ngẫu "
                 "nhiên ở cỡ mẫu này. Cần thêm bài hoặc thêm lượt lặp mới kết luận chắc "
                 "về độ chính xác. Lưu ý kết luận này **chỉ áp cho độ chính xác** — khác "
                 "biệt về năng lực tự kiểm chứng không cần kiểm định vì nó đúng theo kiến "
                 "tạo.\n")

    L.append("## Cách dựng lại\n")
    L.append("```bash")
    L.append("cd ViMultiAgent/backend")
    L.append("set VMA_LUU_LOI_GIAI_MAU=0")
    L.append("python scripts/bench_don_le.py --de eval/data/de_giu_rieng.csv \\")
    L.append(f"    --che-do <tho|json> --so-sanh eval/reports/{ten_da}")
    L.append(f"python scripts/ve_so_sanh.py --don eval/reports/{ten_don} \\")
    L.append(f"    --da eval/reports/{ten_da}")
    L.append("```")

    ra.write_text("\n".join(L), encoding="utf-8")
    return ra


# ---------------------------------------------------------------------------


def main(args: argparse.Namespace) -> int:
    def _duong(s: str) -> Path:
        p = Path(s)
        return p if p.is_absolute() else GOC_BACKEND / p

    p_don, p_da = _duong(args.don), _duong(args.da)
    for p in (p_don, p_da):
        if not p.exists():
            print(f"Không thấy tệp: {p}")
            return 2

    don_tho, da_tho = doc(p_don), doc(p_da)
    don, da, lech = ghep(don_tho, da_tho)
    if not don:
        print("Không ghép được cặp nào — hai tệp khác bộ đề?")
        return 2
    print(f"Ghép được {len(don)} bài "
          f"(mốc nền {len(don_tho)} · đa tác tử {len(da_tho)})")
    if lech:
        print(f"!! CẢNH BÁO: {lech} bài trùng id nhưng KHÁC ĐỀ.")

    cs = chi_so(don, da)
    mn = mcnemar(don, da)

    thu_muc = _duong(args.out) if args.out else GOC_BACKEND / "eval" / "reports" / "hinh"
    thu_muc.mkdir(parents=True, exist_ok=True)
    dau = args.hau_to or f"{datetime.now():%Y%m%d_%H%M%S}"

    hinh = [
        hinh_chi_so(cs, thu_muc / f"01_chi_so_cot_loi_{dau}.png"),
        hinh_thoi_gian(cs, thu_muc / f"02_thoi_gian_{dau}.png"),
        hinh_radar(cs, thu_muc / f"03_radar_{dau}.png"),
        hinh_phan_ra(don, da, thu_muc / f"04_phan_ra_{dau}.png"),
        hinh_rong(mn, len(don), thu_muc / f"05_hieu_qua_rong_{dau}.png"),
    ]
    md = xuat_md(cs, mn, don, da, lech, p_don.name, p_da.name, hinh,
                 thu_muc / f"BAOCAO_SO_SANH_{dau}.md")

    for h in hinh:
        print(f"  hình: {h}")
    print(f"\nBáo cáo Markdown: {md}")
    print(f"\nTóm tắt: một tác tử {cs['acc_don']:.1f}% / {cs['t_don']:.1f}s  ·  "
          f"đa tác tử {cs['acc_da']:.1f}% / {cs['t_da']:.1f}s  ·  "
          f"McNemar p = {mn['p']:.4g}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Vẽ biểu đồ đối chứng hai kiến trúc")
    ap.add_argument("--don", required=True, help="CSV mốc nền một tác tử")
    ap.add_argument("--da", required=True, help="CSV kết quả đa tác tử")
    ap.add_argument("--out", help="thư mục ghi hình (mặc định eval/reports/hinh)")
    ap.add_argument("--hau-to", dest="hau_to", help="hậu tố tên tệp thay cho dấu thời gian")
    raise SystemExit(main(ap.parse_args()))
