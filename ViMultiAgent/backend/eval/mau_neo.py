"""Mẫu neo — lời giải chuẩn mực soạn tay, trộn vào phiếu chấm để hiệu chỉnh thang điểm.

    python eval/mau_neo.py          nối 3 mẫu neo vào loi_giang.jsonl

Vì sao cần
----------
Điểm giáo viên chấm cho lời giảng của máy chỉ có nghĩa khi biết **thang điểm của
chính họ nằm ở đâu**. Nếu một lời giải viết chuẩn mực cũng chỉ được 3,8/5 thì mốc
4/5 của đề bài là khắt khe với MỌI lời giải, không riêng gì lời giảng do máy sinh
— và ta có bằng chứng để nói vậy, thay vì phải biện minh.

Ba nguyên tắc khi soạn
----------------------
1. **Cùng định dạng với lời giảng của hệ thống** — cùng các mục "Tóm tắt đề",
   "Bước N", "Đáp án", "Dễ sai ở đâu". Khác định dạng thì giáo viên nhận ra ngay
   và mất tính chấm mù.
2. **Chất lượng người viết** — giải thích VÌ SAO làm bước đó, không chỉ nêu công
   thức. Đây là điều mô hình 4B hay thiếu nhất.
3. **Không hoàn hảo giả tạo** — viết như một giáo viên viết cho học sinh, không
   phải như một bài mẫu thi.

Ba bài được chọn nằm NGOÀI 20 bài đã thu, để không trùng lặp.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RA = GOC / "eval" / "phieu_cham" / "loi_giang.jsonl"

MAU_NEO = [
    {
        "id": "neo_math_008",
        "subject": "math",
        "topic": "tich_phan",
        "level": "TH",
        "question": "Tính tích phân I = ∫ từ 2 đến 4 của (2x + 1) dx.",
        "dap_an_he_thong": "14",
        "dap_an_chuan": "14",
        "verdict": "PASS",
        "nguon": "sach_giai",
        "bi_cat": False,
        "giay": 0,
        "loi": "",
        "loi_giang": """**Tóm tắt đề**
Cần tính tích phân xác định của hàm bậc nhất $2x + 1$ trên đoạn từ 2 đến 4.

**Bước 1 — Tìm nguyên hàm**
Với tích phân xác định, việc đầu tiên là tìm một nguyên hàm bất kỳ của hàm dưới dấu tích phân. Ta dùng công thức $\\int x^n dx = \\frac{x^{n+1}}{n+1}$ cho từng hạng tử:

$$F(x) = \\int (2x + 1)\\,dx = x^2 + x$$

Không cần viết hằng số $C$ ở đây, vì khi lấy hiệu hai đầu mút nó tự triệt tiêu.

**Bước 2 — Áp dụng công thức Newton–Leibniz**
Tích phân xác định bằng hiệu giá trị của nguyên hàm tại hai cận:

$$I = F(4) - F(2)$$

**Bước 3 — Thay số**
$$F(4) = 4^2 + 4 = 20 \\qquad F(2) = 2^2 + 2 = 6$$

$$I = 20 - 6 = 14$$

**Đáp án**
**I = 14**

**Dễ sai ở đâu**
- Lấy $F(2) - F(4)$ thay vì $F(4) - F(2)$, ra kết quả âm
- Quên bình phương khi thay số, tính $F(4) = 4 + 4 = 8$
""",
    },
    {
        "id": "neo_phys_008",
        "subject": "physics",
        "topic": "dao_dong_dieu_hoa",
        "level": "TH",
        "question": ("Một vật dao động điều hoà với biên độ A = 6 cm và tần số góc "
                     "ω = 20 rad/s. Tính vận tốc cực đại của vật."),
        "dap_an_he_thong": "1,2 m/s",
        "dap_an_chuan": "1.2 m/s",
        "verdict": "PASS",
        "nguon": "sach_giai",
        "bi_cat": False,
        "giay": 0,
        "loi": "",
        "loi_giang": """**Tóm tắt đề**
Cho biên độ và tần số góc của một dao động điều hoà, cần tìm vận tốc cực đại.

**Bước 1 — Đổi biên độ về hệ SI**
Đây là bước bắt buộc và cũng là chỗ mất điểm nhiều nhất. Công thức vật lý luôn dùng đơn vị SI, mà đề cho biên độ bằng centimét:

$$A = 6\\ \\text{cm} = 0,06\\ \\text{m}$$

**Bước 2 — Nhớ lại ý nghĩa của vận tốc cực đại**
Trong dao động điều hoà, vật chạy nhanh nhất khi đi qua vị trí cân bằng. Tại đó toàn bộ cơ năng đã chuyển thành động năng, và độ lớn vận tốc đạt giá trị:

$$v_{max} = A\\omega$$

**Bước 3 — Thay số**
$$v_{max} = 0,06 \\times 20 = 1,2\\ \\text{m/s}$$

**Đáp án**
**v_max = 1,2 m/s**

**Dễ sai ở đâu**
- Quên đổi cm sang m, ra 120 m/s — một con số vô lý cho vật dao động
- Nhầm $\\omega$ với tần số $f$; nếu đề cho $f$ thì phải nhân thêm $2\\pi$
""",
    },
    {
        "id": "neo_chem_008",
        "subject": "chemistry",
        "topic": "tinh_theo_pthh",
        "level": "TH",
        "question": ("Đốt cháy hoàn toàn 4,8 gam Mg trong khí O2 dư thu được MgO. "
                     "Tính khối lượng MgO thu được. Biết Mg = 24, O = 16."),
        "dap_an_he_thong": "8 gam",
        "dap_an_chuan": "8 gam",
        "verdict": "PASS",
        "nguon": "sach_giai",
        "bi_cat": False,
        "giay": 0,
        "loi": "",
        "loi_giang": """**Tóm tắt đề**
Đốt 4,8 gam magie trong oxi dư, cần tìm khối lượng magie oxit tạo thành.

**Bước 1 — Viết và cân bằng phương trình phản ứng**
Mọi bài tính theo phương trình đều phải bắt đầu từ đây, vì tỉ lệ mol lấy từ hệ số cân bằng:

$$2Mg + O_2 \\rightarrow 2MgO$$

Chữ "O2 dư" cho biết magie phản ứng hết, nên ta tính theo magie.

**Bước 2 — Đổi khối lượng Mg sang số mol**
$$n_{Mg} = \\frac{m}{M} = \\frac{4,8}{24} = 0,2\\ \\text{mol}$$

**Bước 3 — Lập tỉ lệ theo phương trình**
Hệ số của Mg và MgO đều bằng 2, tức tỉ lệ 1 : 1. Cứ 1 mol Mg cháy cho 1 mol MgO:

$$n_{MgO} = n_{Mg} = 0,2\\ \\text{mol}$$

**Bước 4 — Đổi ngược về khối lượng**
Khối lượng mol của MgO bằng $24 + 16 = 40$ g/mol, nên:

$$m_{MgO} = 0,2 \\times 40 = 8\\ \\text{gam}$$

**Đáp án**
**m(MgO) = 8 gam**

**Dễ sai ở đâu**
- Quên cân bằng phương trình rồi lấy tỉ lệ sai
- Nhớ nhầm khối lượng mol MgO thành 24 hoặc 16 thay vì tổng của cả hai
- Tính theo O2 thay vì Mg, trong khi O2 dư nên không quyết định lượng sản phẩm
""",
    },
]


def main() -> int:
    if not RA.exists():
        print(f"Chưa có {RA}. Chạy `python eval/thu_loi_giang.py` trước.")
        return 2

    cu = [json.loads(l) for l in RA.read_text(encoding="utf-8").splitlines() if l.strip()]
    da_co = {x["id"] for x in cu}
    them = [m for m in MAU_NEO if m["id"] not in da_co]
    if not them:
        print("Các mẫu neo đã có sẵn trong file, không thêm lại.")
        return 0

    for m in them:
        m["so_ky_tu"] = len(m["loi_giang"])

    with RA.open("a", encoding="utf-8") as f:
        for m in them:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"Đã thêm {len(them)} mẫu neo vào {RA.name}")
    for m in them:
        print(f"  {m['id']:<16} {m['subject']:<10} {m['so_ky_tu']:5} ký tự")
    print(f"\nTổng cộng: {len(cu) + len(them)} bài trong phiếu chấm")
    print("  (giáo viên KHÔNG được biết bài nào là mẫu neo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
