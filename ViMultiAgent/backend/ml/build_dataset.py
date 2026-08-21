"""Dựng dataset phân loại DẠNG BÀI từ câu hỏi Toán THPT tiếng Việt.

Chạy:  python ml/build_dataset.py

Sinh ra `ml/data/{train,val,test}.csv` với ba cột: question, label, source.

Vì sao có cột `source`
----------------------
Ba nguồn dữ liệu có giá trị khoa học rất khác nhau, trộn lẫn rồi báo một con số
accuracy chung là tự lừa mình:

* `seed`     — câu viết tay, sát đề thi thật. Đây là dữ liệu gốc.
* `template` — sinh từ khuôn mẫu, đổi số liệu và cách diễn đạt. Làm dày dữ liệu
               huấn luyện, nhưng dễ với mọi mô hình nên KHÔNG dùng để khoe accuracy.
* `hard`     — câu viết tay không chứa từ khoá đặc trưng của dạng. Đây mới là
               tập phân định được luật từ khoá với mô hình học sâu.

Khi báo cáo, tách riêng accuracy trên `hard`. Con số trên `template` gần như luôn
đẹp và không nói lên điều gì.

Tách tập
--------
Chia theo tầng (stratified) để các dạng bài cân bằng ở cả ba tập. Quan trọng hơn: các
câu `template` sinh ra từ CÙNG một khuôn được giữ trong CÙNG một tập, tránh rò rỉ
— nếu khuôn "Tính đạo hàm của y = {f} tại x = {a}" xuất hiện ở cả train lẫn test
thì test chỉ đang đo khả năng nhớ khuôn.
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ml.seed_questions import HARDS, NHAN, SEEDS  # noqa: E402

RNG = random.Random(20260804)
DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# Khuôn mẫu — mỗi khuôn là (chuỗi định dạng, dict các giá trị thay thế)
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, list[tuple[str, dict[str, list[str]]]]] = {
    "dao_ham": [
        ("Tính đạo hàm của hàm số y = {f} tại điểm x = {a}",
         {"f": ["x^2 + 3x", "x^3 - 2x", "2x^3 + x", "x^4 - x^2", "3x^2 - 5x + 1",
                "x^3 - 6x^2 + 9x", "2x^2 - 8x + 3", "x^4 - 4x^2", "5x^3 - x",
                "x^3 + 3x^2 - 1", "4x^2 - 12x", "x^3 - 3x + 2"],
          "a": ["0", "1", "2", "-1", "3", "-2", "4"]}),
        ("Tính đạo hàm của hàm số y = {f}",
         {"f": ["sin(2x)", "ln(3x)", "e^(2x)", "(x + 1)^5", "x*cos(x)", "tan(x)",
                "ln(x^2 + 1)", "e^x*sin(x)", "(3x - 2)^4", "sqrt(x + 1)",
                "x^2*ln(x)", "cos(3x)"]}),
    ],
    "tich_phan": [
        ("Tính tích phân của {f} từ {a} đến {b}",
         {"f": ["x", "x^2", "2x + 1", "sin(x)", "e^x", "x^3", "1/x", "cos(x)",
                "3x^2 - 2x", "x*e^x", "sqrt(x)", "1/(x + 1)"],
          "a": ["0", "1", "2"], "b": ["2", "3", "pi", "4"]}),
        ("Tìm nguyên hàm của hàm số f(x) = {f}",
         {"f": ["3x^2", "cos(x)", "1/x", "e^x + 1", "4x^3 - 2x", "sin(2x)",
                "x^2 + 2x", "2e^(2x)", "1/(x^2)", "5x^4"]}),
    ],
    "gioi_han": [
        ("Tìm giới hạn lim {f} khi x dần tới {a}",
         {"f": ["(3x - 6)/(x^2 - 4)", "(x - 1)/(x^2 - 1)", "(2x^2 - 8)/(x - 2)",
                "(x^2 + 3x)/(2x^2 - x)", "(sqrt(x) - 2)/(x - 4)",
                "(x^3 + 1)/(x + 1)", "(4x - 12)/(x^2 - 9)", "tan(x)/x"],
          "a": ["0", "1", "2", "3", "4", "vô cùng"]}),
        ("Tính giới hạn của {f} khi x tiến tới {a}",
         {"f": ["(x^2 - 4)/(x - 2)", "(x^2 - 9)/(x - 3)", "sin(x)/x",
                "(2x + 1)/(x - 1)", "(x^2 - 1)/(x - 1)", "(3x^2 + x)/(x^2 - 5)",
                "(sqrt(x + 1) - 1)/x", "(x^3 - 8)/(x - 2)", "(1 - cos(x))/x^2",
                "(x^2 - 16)/(x - 4)"],
          "a": ["0", "1", "2", "3", "4", "vô cùng", "âm vô cùng", "5"]}),
    ],
    "phuong_trinh": [
        ("Giải phương trình {pt}",
         {"pt": ["x^2 - 5x + 6 = 0", "2x^2 - 3x - 5 = 0", "x^2 - 9 = 0",
                 "3x - 7 = 2", "x^2 + 4x + 4 = 0", "x^2 - 7x + 12 = 0",
                 "4x^2 - 1 = 0", "x^2 + x - 6 = 0", "5x + 3 = 18",
                 "x^2 - 2x - 8 = 0", "3x^2 - 12 = 0", "2x - 9 = 5",
                 "x^2 - 4x + 3 = 0", "6x + 5 = 23", "x^2 - 25 = 0"]}),
        ("Giải bất phương trình {bpt}",
         {"bpt": ["2x - 7 > 3", "x^2 - 4 < 0", "3x + 1 <= 10", "x^2 - 5x + 6 > 0",
                  "4x - 3 >= 9", "x^2 - 9 <= 0", "5 - 2x < 1", "x^2 + x - 2 > 0",
                  "7x - 2 > 12", "x^2 - 16 < 0"]}),
        ("Giải phương trình {loai} {pt}",
         {"loai": ["mũ", "logarit"],
          "pt": ["2^x = 8", "3^x = 81", "log_2(x) = 4", "log_3(x - 1) = 2",
                 "5^x = 125", "log_2(x + 3) = 3", "2^(x+1) = 16", "log_5(x) = 2",
                 "4^x = 64", "log_2(2x) = 5"]}),
    ],
    "tiep_tuyen": [
        ("Cho hàm số y = {f}. Lập phương trình tiếp tuyến tại điểm M có hoành độ bằng {a}",
         {"f": ["x^2 - 4x + 5", "x^3 + x", "2x^2 + 3", "x^3 - 9x",
                "x^2 - 6x", "3x^3 - x^2", "x^4 - 2x", "5x^2 - 4x + 1"],
          "a": ["1", "2", "-1", "0", "3", "-2"]}),
        ("Viết phương trình tiếp tuyến của đồ thị hàm số y = {f} tại điểm có hoành độ x = {a}",
         {"f": ["x^2 + 3x", "x^3 - 2x", "2x^3 + x", "x^4 - x^2", "3x^2 - 5x + 1",
                "x^3 - 6x^2 + 9x", "2x^2 - 8x + 3", "(x + 1)/(x - 1)",
                "x^3 + 3x^2 - 1", "4x^2 - 12x", "x^3 - 3x + 2", "(2x - 1)/(x + 2)"],
          "a": ["0", "1", "2", "-1", "3", "-2", "4"]}),
    ],
    "gtln": [
        ("Tìm giá trị lớn nhất của hàm số y = {f} trên đoạn [{a}; {b}]",
         {"f": ["-x^2 + 4x", "x^2 - 2x", "x^3 - 3x", "-x^2 + 6x - 5",
                "x^3 - 6x^2 + 9x", "-2x^2 + 8x - 3", "x^4 - 2x^2", "-x^3 + 3x"],
          "a": ["0", "-1", "1", "-2"], "b": ["2", "3", "4", "5"]}),
        ("Tìm giá trị lớn nhất của biểu thức {f}",
         {"f": ["-x^2 + 4x + 1", "-x^2 - 6x + 2", "6 - (x - 2)^2",
                "-2x^2 + 8x", "10 - x^2 + 4x", "-x^2 + 2x + 8"]}),
    ],
    "gtnn": [
        ("Tìm giá trị nhỏ nhất của hàm số y = {f} trên đoạn [{a}; {b}]",
         {"f": ["x^2 - 4x", "x^2 + 2x", "x^3 - 3x", "x^2 - 6x + 5",
                "x^3 - 6x^2 + 9x", "2x^2 - 8x + 3", "x^4 - 2x^2", "x^3 + 3x"],
          "a": ["0", "-1", "1", "-2"], "b": ["2", "3", "4", "5"]}),
        ("Tìm giá trị nhỏ nhất của biểu thức {f}",
         {"f": ["x^2 + 4x + 7", "x^2 - 6x + 11", "x + 25/x với x > 0",
                "x^2 + 2x + 5", "x + 9/x với x > 0", "x^2 - 8x + 20",
                "2x + 8/x với x > 0", "x^2 + 10x + 30"]}),
    ],
    "so_diem_cuc_tri": [
        ("Hàm số y = {f} có bao nhiêu {yeu_cau}",
         {"f": ["x^3 - 3x^2 + 2", "x^4 - 5x^2 + 4", "2x^3 - 6x", "x^4 + 2x^2",
                "x^3 - 12x", "3x^4 - 4x^3", "x^3 + x^2 - x", "x^4 - 18x^2"],
          "yeu_cau": ["điểm cực trị", "điểm cực đại", "điểm cực tiểu"]}),
        ("Tìm {yeu_cau} của hàm số y = {f}",
         {"yeu_cau": ["điểm cực trị", "số điểm cực trị", "điểm cực đại",
                      "điểm cực tiểu", "giá trị cực đại", "giá trị cực tiểu"],
          "f": ["x^3 - 3x^2 + 1", "x^4 - 2x^2", "x^3 - 3x", "x^4 - 4x^2 + 3",
                "x^3 - 6x^2 + 9x", "2x^3 - 3x^2", "x^4 - 8x^2", "x^3 + 3x^2 - 9x",
                "x^4 - 6x^2 + 5", "2x^3 - 9x^2 + 12x"]}),
    ],
    "tiem_can_ngang": [
        ("Đồ thị hàm số y = ({a}x^2 + {b})/({d}x^2 - {c}) có tiệm cận ngang là đường nào",
         {"a": ["2", "3", "5", "1"], "b": ["1", "4", "-3", "6"],
          "c": ["1", "9", "4"], "d": ["1", "2", "4"]}),
        ("Tìm tiệm cận ngang của đồ thị hàm số y = ({a}x + {b})/({d}x - {c})",
         {"a": ["2", "3", "5", "1", "4"], "b": ["1", "5", "-2", "7"],
          "c": ["1", "3", "4", "2"], "d": ["1", "2", "3"]}),
    ],
    "tiem_can_dung": [
        ("Đồ thị hàm số y = ({a}x + {b})/(x^2 - {c}) có bao nhiêu tiệm cận đứng",
         {"a": ["2", "3", "5", "1"], "b": ["1", "4", "-3", "6"],
          "c": ["1", "9", "4", "16"], "x": [""]}),
        ("Tìm tiệm cận đứng của đồ thị hàm số y = ({a}x + {b})/({d}x - {c})",
         {"a": ["2", "3", "5", "1", "4"], "b": ["1", "5", "-2", "7"],
          "c": ["1", "3", "4", "2"], "d": ["1", "2", "3"]}),
    ],
    "khac_dai_so": [
        ("Cho cấp số {loai} có số hạng đầu {u} và {tham} bằng {d}. Tính số hạng thứ {n}",
         {"loai": ["cộng", "nhân"], "u": ["2", "3", "5"],
          "tham": ["công sai", "công bội"], "d": ["2", "3", "4"], "n": ["6", "8", "10"]}),
        ("Tính số cách chọn {k} {doi_tuong} từ {n} {doi_tuong}",
         {"k": ["2", "3", "4"], "n": ["7", "10", "12"],
          "doi_tuong": ["học sinh", "quyển sách", "bông hoa"]}),
        ("Tính xác suất {bien_co} khi {phep_thu}",
         {"bien_co": ["được mặt chẵn", "được số nguyên tố", "được bi đỏ"],
          "phep_thu": ["gieo một con xúc xắc", "bốc ngẫu nhiên một viên bi",
                       "rút ngẫu nhiên một lá bài"]}),
        ("Cho số phức z = {a} + {b}i. Tính {yeu_cau}",
         {"a": ["3", "1", "2"], "b": ["4", "2", "5"],
          "yeu_cau": ["môđun của z", "phần thực của z", "số phức liên hợp của z"]}),
    ],
    "toa_do_khoang_cach": [
        ("Trong mặt phẳng Oxy, tính khoảng cách từ điểm M({a}; {b}) đến đường thẳng {d}",
         {"a": ["1", "2", "-1", "0"], "b": ["2", "3", "0", "-2"],
          "d": ["3x + 4y - 5 = 0", "x - y + 2 = 0", "5x - 12y + 1 = 0",
                "4x + 3y - 7 = 0"]}),
        ("Trong không gian Oxyz, tính khoảng cách giữa hai điểm A({a}; {b}; {c}) và B({d}; {e}; {g})",
         {"a": ["1", "0", "2"], "b": ["2", "1"], "c": ["3", "2"],
          "d": ["4", "3"], "e": ["6", "5"], "g": ["3", "2"]}),
    ],
    "toa_do_the_tich": [
        ("Tính thể tích khối {hinh} có {dl1} bằng {a} và {dl2} bằng {b}",
         {"hinh": ["chóp", "lăng trụ", "hộp chữ nhật"],
          "dl1": ["diện tích đáy"], "a": ["12", "20", "36", "24", "48"],
          "dl2": ["chiều cao"], "b": ["4", "5", "6", "3", "8"]}),
        ("Cho hình {hinh} cạnh {a}. Tính thể tích khối {hinh} đó",
         {"hinh": ["lập phương"], "a": ["2", "3", "4", "5", "6", "7"]}),
        ("Tính thể tích khối {hinh} có bán kính đáy {r} và chiều cao {h}",
         {"hinh": ["nón", "trụ"], "r": ["2", "3", "4", "5"],
          "h": ["6", "9", "12", "10"]}),
    ],
    "toa_do_kc_diem_mp": [
        ("Cho mặt phẳng (P): {mp} và điểm M({a}; {b}; {c}). Tính d(M, (P))",
         {"a": ["1", "3", "-2", "0"], "b": ["0", "2", "-1", "4"],
          "c": ["1", "-3", "2", "5"],
          "mp": ["2x + 2y - z + 3 = 0", "x - 2y + 2z - 4 = 0",
                 "6x - 3y + 2z + 7 = 0", "x + y - z + 2 = 0"]}),
        ("Trong không gian Oxyz, tính khoảng cách từ điểm A({a}; {b}; {c}) đến mặt phẳng {mp}",
         {"a": ["1", "2", "0", "-1"], "b": ["2", "1", "-1", "3"],
          "c": ["3", "0", "2", "-2"],
          "mp": ["x + 2y - 2z + 1 = 0", "2x - y + 2z - 6 = 0", "x + y + z - 3 = 0",
                 "3x - 4y + 12 = 0"]}),
    ],
    "khac_hinh_hoc": [
        ("Cho tam giác ABC vuông tại A, AB = {a}, AC = {b}. Tính độ dài cạnh BC",
         {"a": ["3", "6", "5", "9", "8"], "b": ["4", "8", "12", "15"]}),
        ("Tính {yeu_cau} của {hinh} bán kính {r}",
         {"yeu_cau": ["diện tích", "chu vi", "thể tích"],
          "hinh": ["mặt cầu", "hình tròn", "khối cầu"], "r": ["2", "3", "5", "4"]}),
        ("Cho hai vectơ a = ({a}; {b}) và b = ({c}; {d}). Tính tích vô hướng của chúng",
         {"a": ["1", "2", "3"], "b": ["2", "-1"], "c": ["3", "4"], "d": ["-1", "2"]}),
    ],
}


def _sinh_tu_khuon(mau: str, gia_tri: dict[str, list[str]], so_luong: int) -> list[str]:
    """Sinh các biến thể khác nhau từ một khuôn, không trùng lặp."""
    ra: set[str] = set()
    gioi_han = so_luong * 20  # chặn vòng lặp vô hạn khi khuôn ít biến thể
    for _ in range(gioi_han):
        if len(ra) >= so_luong:
            break
        cau = mau
        for khoa, ds in gia_tri.items():
            cau = cau.replace("{" + khoa + "}", RNG.choice(ds))
        ra.add(cau)
    return sorted(ra)


def dung_dataset(moi_lop: int = 60) -> list[tuple[str, str, str, int]]:
    """Trả về danh sách (question, label, source, khuon_id).

    `khuon_id` dùng để chia tập theo nhóm — mọi biến thể của cùng một khuôn phải
    nằm chung một tập, nếu không thì test bị rò rỉ.

    Cân bằng theo LỚP, không theo khuôn
    -----------------------------------
    Bản trước sinh `moi_khuon` câu cho MỖI KHUÔN, nên lớp nào nhiều khuôn thì
    nhiều dữ liệu. Hậu quả đo được: `khac_dai_so` có 4 khuôn nên được 81 câu
    train, còn `gtnn` có 1 khuôn nghèo biến thể nên chỉ được 8 — lệch hơn 10 lần.

    Mô hình học đúng cái tỉ lệ lệch đó: câu "Tìm giá trị NHỎ nhất" bị gán `gtln`
    với xác suất 0,48 trong khi `gtnn` chỉ 0,05, vì đoán theo lớp đông là chiến
    lược thắng về mặt xác suất tiên nghiệm. Đây là lỗi do dữ liệu, không phải do
    mô hình yếu.

    Nay mỗi LỚP có cùng một hạn mức `moi_lop`, chia đều cho các khuôn của nó.
    Khuôn nghèo biến thể sinh được bao nhiêu thì phần thiếu dồn sang khuôn còn dư.
    """
    hang: list[tuple[str, str, str, int]] = []
    khuon_id = 0

    for nhan, ds in SEEDS.items():
        for cau in ds:
            khuon_id += 1
            hang.append((cau, nhan, "seed", khuon_id))

    for nhan, ds in HARDS.items():
        for cau in ds:
            khuon_id += 1
            hang.append((cau, nhan, "hard", khuon_id))

    for nhan, khuons in TEMPLATES.items():
        con_lai = moi_lop
        # Duyệt hai lượt: lượt đầu chia đều, lượt sau dồn phần khuôn nghèo không
        # sinh nổi sang các khuôn còn dư biến thể.
        sinh_duoc: dict[int, list[str]] = {}
        for vong in range(2):
            for i, (mau, gia_tri) in enumerate(khuons):
                if con_lai <= 0:
                    break
                kid = khuon_id + i + 1
                da_co = len(sinh_duoc.get(kid, []))
                muon = con_lai if vong else max(1, con_lai // (len(khuons) - i))
                moi = _sinh_tu_khuon(mau, gia_tri, da_co + muon)
                them = [c for c in moi if c not in sinh_duoc.get(kid, [])]
                if not them:
                    continue
                sinh_duoc.setdefault(kid, []).extend(them)
                con_lai -= len(them)

        for i in range(len(khuons)):
            kid = khuon_id + i + 1
            for cau in sinh_duoc.get(kid, []):
                hang.append((cau, nhan, "template", kid))
        khuon_id += len(khuons)

    return hang


def chia_tap(
    hang: list[tuple[str, str, str, int]],
) -> dict[str, list[tuple[str, str, str]]]:
    """Chia train/val/test.

    Quy tắc:
    * `hard` dồn hết vào test — đó là thước đo, không phải dữ liệu luyện.
    * `seed` và `template` chia theo khuôn, 70/15/15.
    """
    tap: dict[str, list[tuple[str, str, str]]] = {"train": [], "val": [], "test": []}

    theo_khuon: dict[int, list[tuple[str, str, str]]] = {}
    for cau, nhan, nguon, kid in hang:
        if nguon == "hard":
            tap["test"].append((cau, nhan, nguon))
        else:
            theo_khuon.setdefault(kid, []).append((cau, nhan, nguon))

    # Chia theo tầng: xáo trong từng nhãn để các dạng cân bằng ở mọi tập.
    theo_nhan: dict[str, list[int]] = {}
    for kid, muc in theo_khuon.items():
        theo_nhan.setdefault(muc[0][1], []).append(kid)

    # Xếp tham lam theo SỐ CÂU, không theo số khuôn: mỗi khuôn sinh ra số câu rất
    # khác nhau, chia đều số khuôn thì test lệch hẳn.
    # Duyệt khuôn từ lớn xuống nhỏ, mỗi lần bỏ vào tập đang thiếu nhiều nhất so
    # với hạn mức của nó.
    ty_le = {"train": 0.70, "val": 0.15, "test": 0.15}
    for nhan, ds_kid in theo_nhan.items():
        ds = sorted(ds_kid, key=lambda k: -len(theo_khuon[k]))
        tong = sum(len(theo_khuon[k]) for k in ds)
        han_muc = {t: tong * r for t, r in ty_le.items()}
        da_co = {t: 0 for t in ty_le}
        for kid in ds:
            phan = max(ty_le, key=lambda t: han_muc[t] - da_co[t])
            tap[phan].extend(theo_khuon[kid])
            da_co[phan] += len(theo_khuon[kid])

    for muc in tap.values():
        RNG.shuffle(muc)
    return tap


def ghi_csv(tap: dict[str, list[tuple[str, str, str]]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for ten, muc in tap.items():
        duong_dan = DATA_DIR / f"{ten}.csv"
        with duong_dan.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["question", "label", "source"])
            w.writerows(muc)
        print(f"  {duong_dan.name:<10} {len(muc):>5} câu")


def main() -> int:
    hang = dung_dataset()
    tap = chia_tap(hang)

    print(f"Tổng: {len(hang)} câu\n")
    print("Theo nguồn:")
    for nguon in ("seed", "template", "hard"):
        n = sum(1 for _, _, s, _ in hang if s == nguon)
        print(f"  {nguon:<10} {n:>5}")
    print("\nTheo môn:")
    for nhan in NHAN:
        n = sum(1 for _, l, _, _ in hang if l == nhan)
        print(f"  {nhan:<10} {n:>5}")
    print("\nTách tập:")
    ghi_csv(tap)

    print("\nPhân bố nhãn trong test:")
    for nhan in NHAN:
        n = sum(1 for _, l, _ in tap["test"] if l == nhan)
        nh = sum(1 for _, l, s in tap["test"] if l == nhan and s == "hard")
        print(f"  {nhan:<10} {n:>4} câu (trong đó {nh} câu khó)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
