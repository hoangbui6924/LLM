"""Phiếu chấm cho giáo viên — bước 2 và 4 của chỉ số 2.

    python eval/phieu_cham.py xuat            dựng file HTML gửi giáo viên
    python eval/phieu_cham.py gop <thư mục>   gộp các CSV giáo viên gửi lại

Vì sao là HTML tự chứa chứ không phải Google Form
--------------------------------------------------
1. Lời giảng đầy công thức LaTeX. Google Form hiện ra `$$\\frac{a}{b}$$` thô, giáo
   viên không đọc nổi thì chấm cũng vô nghĩa. File này nhúng sẵn KaTeX nên công
   thức hiện đúng như học sinh sẽ thấy.
2. Không cần mạng, không cần tài khoản — đúng tinh thần offline của dự án.
3. Giáo viên mở bằng trình duyệt, chấm xong bấm nút tải CSV rồi gửi lại.

Ba thiết kế chống thiên vị
--------------------------
* **Chấm mù** — không đánh dấu bài nào do hệ thống sinh, bài nào chép từ sách giải.
* **Mẫu neo** — trộn vài lời giải sách giải vào. Nếu chính sách giải cũng chỉ được
  4,1 điểm thì mốc 4/5 cho máy là khắt khe, và ta có BẰNG CHỨNG để nói vậy.
* **Có cả bài sai** — lấy mẫu theo đúng tỉ lệ đúng/sai thật. Chỉ đưa bài đúng là
  chọn mẫu thiên vị, người chấm khó tính sẽ vặn ngay.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import random
import re
import statistics
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THU_MUC = GOC / "eval" / "phieu_cham"
NGUON_JSONL = THU_MUC / "loi_giang.jsonl"
KATEX = GOC.parent / "frontend" / "node_modules" / "katex" / "dist"

# Năm mục Likert. Hỏi tách bạch để biết hỏng ở đâu, không chỉ biết "điểm thấp".
MUC_CHAM = [
    ("chinh_xac", "Chính xác về mặt chuyên môn"),
    ("de_hieu", "Học sinh THPT đọc là hiểu được"),
    ("cac_buoc", "Các bước hợp lý, không nhảy cóc"),
    ("ngon_ngu", "Tiếng Việt tự nhiên, thuật ngữ đúng sách giáo khoa"),
    ("tong_the", "ĐÁNH GIÁ TỔNG THỂ"),
]
MUC_CHOT = "tong_the"      # mục đối chiếu với ngưỡng >= 4/5


# ---------------------------------------------------------------------------
# Dựng HTML
# ---------------------------------------------------------------------------


def _katex_css() -> str:
    """CSS của KaTeX với font nhúng thẳng dạng base64.

    Không nhúng font thì file phải nằm cạnh thư mục fonts/ mới chạy — gửi qua email
    là hỏng. Nhúng vào thì một file duy nhất, mở ở đâu cũng đúng.
    """
    css = (KATEX / "katex.min.css").read_text(encoding="utf-8")

    def _thay(m: re.Match) -> str:
        f = KATEX / "fonts" / m.group(1)
        if not f.exists():
            return m.group(0)
        b64 = base64.b64encode(f.read_bytes()).decode()
        return f"url(data:font/woff2;base64,{b64})"

    css = re.sub(r"url\(fonts/([^)]+\.woff2)\)", _thay, css)
    # Bỏ các định dạng dự phòng, trình duyệt hiện đại chỉ cần woff2.
    css = re.sub(r",url\(fonts/[^)]+\.(woff|ttf)\)\s*format\(\"[^\"]+\"\)", "", css)
    return css


def _md_sang_html(md: str) -> str:
    """Đổi Markdown của Explain Agent sang HTML, GIỮ NGUYÊN phần LaTeX.

    Explain sinh ra định dạng cố định: **tiêu đề**, đoạn văn, $$công thức$$, gạch
    đầu dòng. Chỉ cần xử lý đúng ngần đó — kéo cả thư viện Markdown vào là thừa.
    """
    md = md or ""
    # Che phần toán trước khi escape HTML, kẻo `<` `>` trong công thức bị hỏng.
    kho: list[str] = []

    def _giu(m: re.Match) -> str:
        kho.append(m.group(0))
        return f"\x00{len(kho) - 1}\x00"

    md = re.sub(r"\$\$.+?\$\$|\$[^$\n]+?\$", _giu, md, flags=re.S)
    md = html.escape(md)
    md = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", md)
    md = re.sub(r"_(.+?)_", r"<em>\1</em>", md)

    dong_ra: list[str] = []
    trong_ul = False
    for dong in md.split("\n"):
        d = dong.strip()
        if d.startswith("- ") or d.startswith("* "):
            if not trong_ul:
                dong_ra.append("<ul>")
                trong_ul = True
            dong_ra.append(f"<li>{d[2:]}</li>")
            continue
        if trong_ul:
            dong_ra.append("</ul>")
            trong_ul = False
        dong_ra.append(f"<p>{d}</p>" if d else "")
    if trong_ul:
        dong_ra.append("</ul>")

    ra = "\n".join(dong_ra)
    for i, goc in enumerate(kho):
        ra = ra.replace(f"\x00{i}\x00", goc)
    return ra


_CSS_TRANG = """
:root{--vien:#d8dee9;--nhat:#f7f9fc;--dam:#1f2937;--nhan:#2563eb}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px 80px;font:16px/1.65 "Segoe UI",system-ui,sans-serif;
     color:var(--dam);background:#fff;max-width:900px;margin-inline:auto}
h1{font-size:22px;margin:0 0 4px} h2{font-size:17px;margin:0}
.mo-dau{background:var(--nhat);border:1px solid var(--vien);border-radius:10px;
        padding:16px 20px;margin-bottom:28px}
.mo-dau ol{margin:8px 0 0;padding-left:20px} .mo-dau li{margin:4px 0}
.bai{border:1px solid var(--vien);border-radius:10px;padding:18px 20px;margin-bottom:22px}
.de{background:var(--nhat);border-left:3px solid var(--nhan);padding:10px 14px;
    margin:10px 0 16px;border-radius:0 6px 6px 0}
.giang{margin-bottom:18px} .giang p{margin:6px 0} .giang ul{margin:6px 0 6px 18px}
.bang{width:100%;border-collapse:collapse;margin-top:10px;font-size:14.5px}
.bang th,.bang td{border:1px solid var(--vien);padding:7px 6px;text-align:center}
.bang th:first-child,.bang td:first-child{text-align:left;width:46%}
.bang thead th{background:var(--nhat);font-weight:600;font-size:13px}
.chot{background:#fff8e6}
textarea{width:100%;margin-top:10px;padding:8px;border:1px solid var(--vien);
         border-radius:6px;font:inherit;font-size:14px;resize:vertical}
.thanh{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--vien);
       padding:11px 16px;display:flex;gap:14px;align-items:center;justify-content:center}
button{background:var(--nhan);color:#fff;border:0;border-radius:7px;padding:10px 22px;
       font:inherit;font-weight:600;cursor:pointer}
button:disabled{background:#9aa5b1;cursor:not-allowed}
.dem{font-size:14px;color:#4b5563}
@media(prefers-color-scheme:dark){
  :root{--vien:#374151;--nhat:#1a2230;--dam:#e5e7eb}
  body{background:#0f151f;color:var(--dam)} .thanh{background:#0f151f}
  .chot{background:#2a2410}
}
"""


def dung_html(cac_bai: list[dict], ten_tep: Path, seed: int) -> None:
    r = random.Random(seed)
    bai = list(cac_bai)
    r.shuffle(bai)                      # xáo để thứ tự không gợi ý nguồn gốc

    khoi: list[str] = []
    for i, b in enumerate(bai, start=1):
        hang = "".join(
            f"<tr class='{'chot' if ma == MUC_CHOT else ''}'><th>{ten}</th>"
            + "".join(
                f"<td><input type=radio name='{b['id']}__{ma}' value='{d}' required></td>"
                for d in range(1, 6)
            )
            + "</tr>"
            for ma, ten in MUC_CHAM
        )
        khoi.append(f"""
<section class="bai" data-id="{html.escape(b['id'])}">
  <h2>Bài {i}/{len(bai)}</h2>
  <div class="de"><strong>Đề:</strong> {html.escape(b['question'])}</div>
  <div class="giang">{_md_sang_html(b['loi_giang'])}</div>
  <table class="bang">
    <thead><tr><th>Tiêu chí</th><th>1<br>Rất kém</th><th>2</th><th>3</th><th>4</th>
    <th>5<br>Rất tốt</th></tr></thead>
    <tbody>{hang}</tbody>
  </table>
  <textarea rows="2" name="{b['id']}__ghi_chu"
            placeholder="Nhận xét thêm (không bắt buộc)"></textarea>
</section>""")

    ten_tep.parent.mkdir(parents=True, exist_ok=True)
    ten_tep.write_text(f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu chấm chất lượng lời giảng</title>
<style>{_katex_css()}</style>
<style>{_CSS_TRANG}</style>
</head><body>
<h1>Phiếu chấm chất lượng lời giảng</h1>
<div class="mo-dau">
  <p>Cảm ơn thầy/cô đã dành thời gian. Dưới đây là <strong>{len(bai)} lời giảng</strong>
     cho các bài Toán, Lý, Hoá bậc THPT.</p>
  <ol>
    <li>Đọc đề và lời giảng, cho điểm từ <strong>1 (rất kém)</strong> đến
        <strong>5 (rất tốt)</strong> cho từng tiêu chí.</li>
    <li>Dòng <strong>ĐÁNH GIÁ TỔNG THỂ</strong> (nền vàng) là điểm quan trọng nhất.</li>
    <li>Trong bộ này <strong>có cả lời giảng đúng lẫn sai</strong> — mong thầy/cô
        chấm đúng như đang chấm bài học sinh.</li>
    <li>Chấm xong, bấm <strong>Tải kết quả</strong> ở cuối trang rồi gửi lại file CSV.</li>
  </ol>
</div>
{"".join(khoi)}
<div class="thanh">
  <span class="dem" id="dem">Chưa chấm bài nào</span>
  <button id="tai" disabled>Tải kết quả</button>
</div>
<script>{(KATEX / 'katex.min.js').read_text(encoding='utf-8')}</script>
<script>{(KATEX / 'contrib' / 'auto-render.min.js').read_text(encoding='utf-8')}</script>
<script>
renderMathInElement(document.body,{{delimiters:[
  {{left:"$$",right:"$$",display:true}},{{left:"$",right:"$",display:false}}],
  throwOnError:false}});

const CHOT = {json.dumps([m for m, _ in MUC_CHAM], ensure_ascii=False)};
const BAI = Array.from(document.querySelectorAll(".bai")).map(e => e.dataset.id);

function daCham(){{
  return BAI.filter(id => CHOT.every(m =>
    document.querySelector(`input[name="${{id}}__${{m}}"]:checked`))).length;
}}
function capNhat(){{
  const n = daCham();
  document.getElementById("dem").textContent =
    n === BAI.length ? `Đã chấm đủ ${{n}}/${{BAI.length}} bài` : `Đã chấm ${{n}}/${{BAI.length}} bài`;
  document.getElementById("tai").disabled = n === 0;
}}
document.addEventListener("change", capNhat);
capNhat();

document.getElementById("tai").addEventListener("click", () => {{
  const ten = (prompt("Tên thầy/cô (dùng để phân biệt các phiếu):") || "").trim() || "khong_ten";
  const dong = [["giao_vien","bai_id",...CHOT,"ghi_chu"].join(",")];
  for (const id of BAI) {{
    const diem = CHOT.map(m => {{
      const o = document.querySelector(`input[name="${{id}}__${{m}}"]:checked`);
      return o ? o.value : "";
    }});
    if (diem.every(d => !d)) continue;
    const gc = (document.querySelector(`textarea[name="${{id}}__ghi_chu"]`).value || "")
      .replace(/"/g, "'").replace(/[\\r\\n]+/g, " ");
    dong.push([ten, id, ...diem, `"${{gc}}"`].join(","));
  }}
  const blob = new Blob(["\\ufeff" + dong.join("\\n")], {{type:"text/csv;charset=utf-8"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `phieu_cham_${{ten.replace(/[^a-zA-Z0-9]/g,"_")}}.csv`;
  a.click();
}});
</script>
</body></html>""", encoding="utf-8")


# ---------------------------------------------------------------------------
# Gộp điểm
# ---------------------------------------------------------------------------


def gop(thu_muc: Path, nguon: Path) -> int:
    tep = sorted(thu_muc.glob("*.csv"))
    if not tep:
        print(f"Không thấy file CSV nào trong {thu_muc}")
        return 2

    goc: dict[str, dict] = {}
    if nguon.exists():
        with nguon.open(encoding="utf-8") as f:
            for d in f:
                if d.strip():
                    b = json.loads(d)
                    goc[b["id"]] = b

    dong: list[dict] = []
    for t in tep:
        with t.open(encoding="utf-8-sig", newline="") as f:
            dong += list(csv.DictReader(f))

    gv = sorted({d["giao_vien"] for d in dong})
    print(f"Số phiếu   : {len(tep)} file, {len(gv)} người chấm")
    print(f"Số lượt chấm: {len(dong)}")
    print(f"Người chấm : {', '.join(gv)}\n")

    print("=" * 62)
    print("ĐIỂM TRUNG BÌNH TỪNG TIÊU CHÍ")
    print("=" * 62)
    for ma, ten in MUC_CHAM:
        v = [float(d[ma]) for d in dong if d.get(ma)]
        if not v:
            continue
        sd = statistics.stdev(v) if len(v) > 1 else 0.0
        dat = "ĐẠT" if statistics.mean(v) >= 4.0 else "CHƯA ĐẠT"
        sao = "  <-- đối chiếu ngưỡng >= 4/5" if ma == MUC_CHOT else ""
        print(f"  {ten:<48} {statistics.mean(v):.2f} ± {sd:.2f}"
              + (f"   {dat}{sao}" if ma == MUC_CHOT else ""))

    chot = [float(d[MUC_CHOT]) for d in dong if d.get(MUC_CHOT)]
    if chot:
        print(f"\n  Phân bố điểm tổng thể:")
        for d in range(1, 6):
            n = chot.count(float(d))
            print(f"    {d} điểm: {n:3} lượt  {'#' * (n * 40 // max(1, len(chot)))}")

    # Mẫu neo: nếu chính lời giải sách giải cũng không đạt 4/5 thì ngưỡng là khắt khe.
    if goc:
        print("\n" + "=" * 62)
        print("TÁCH THEO NGUỒN")
        print("=" * 62)
        theo_nguon: dict[str, list[float]] = {}
        for d in dong:
            b = goc.get(d["bai_id"])
            if b and d.get(MUC_CHOT):
                theo_nguon.setdefault(b.get("nguon", "he_thong"), []).append(float(d[MUC_CHOT]))
        for ng, v in sorted(theo_nguon.items()):
            ten = "Hệ thống sinh" if ng == "he_thong" else "Mẫu neo (sách giải)"
            print(f"  {ten:<24} {statistics.mean(v):.2f}  (n = {len(v)})")
        if len(theo_nguon) > 1:
            print("\n  Nếu mẫu neo cũng dưới 4,0 thì ngưỡng đề bài là khắt khe với MỌI lời giải,")
            print("  không riêng gì lời giảng do máy sinh — đây là lập luận có số liệu đỡ lưng.")

    # Độ đồng thuận: cùng một bài mà điểm lệch nhau nhiều thì con số trung bình yếu.
    theo_bai: dict[str, list[float]] = {}
    for d in dong:
        if d.get(MUC_CHOT):
            theo_bai.setdefault(d["bai_id"], []).append(float(d[MUC_CHOT]))
    nhieu = [statistics.stdev(v) for v in theo_bai.values() if len(v) > 1]
    if nhieu:
        print(f"\n  Độ lệch chuẩn trung bình GIỮA các người chấm trên cùng một bài:"
              f" {statistics.mean(nhieu):.2f}")
        print("  (dưới 0,8 là đồng thuận tốt; trên 1,2 là mỗi người một ý)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phiếu chấm chất lượng lời giảng")
    ap.add_argument("lenh", choices=["xuat", "gop"])
    ap.add_argument("thu_muc", nargs="?", help="thư mục chứa CSV giáo viên gửi lại (lệnh gop)")
    ap.add_argument("--nguon", default=str(NGUON_JSONL))
    ap.add_argument("--ra", default=str(THU_MUC / "phieu_cham.html"))
    ap.add_argument("--seed", type=int, default=20260806)
    a = ap.parse_args()

    nguon = Path(a.nguon)
    if a.lenh == "gop":
        return gop(Path(a.thu_muc or THU_MUC / "da_cham"), nguon)

    if not nguon.exists():
        print(f"Không thấy {nguon}")
        print("Chạy `python eval/thu_loi_giang.py` trước.")
        return 2

    bai = [json.loads(d) for d in nguon.read_text(encoding="utf-8").splitlines() if d.strip()]
    bai = [b for b in bai if b.get("loi_giang", "").strip()]
    if not bai:
        print("Không có lời giảng nào dùng được.")
        return 2

    cat = sum(1 for b in bai if b.get("bi_cat"))
    if cat:
        print(f"CẢNH BÁO: {cat}/{len(bai)} lời giảng bị cắt giữa chừng.")
        print("Chấm bài giảng cụt thì điểm thấp là do phép đo hỏng, không phải hệ thống.\n")

    ra = Path(a.ra)
    dung_html(bai, ra, a.seed)
    print(f"Đã dựng phiếu chấm: {ra}")
    print(f"  {len(bai)} bài, {len(MUC_CHAM)} tiêu chí mỗi bài")
    print(f"  Kích thước: {ra.stat().st_size / 1024:.0f} KB (đã nhúng KaTeX, mở offline được)")
    print("\nGửi file này cho giáo viên. Nhận CSV về thì bỏ vào eval/phieu_cham/da_cham/")
    print("rồi chạy: python eval/phieu_cham.py gop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
