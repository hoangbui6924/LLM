"""Dựng dataset phân loại môn học từ câu hỏi STEM tiếng Việt.

Chạy:  python ml/build_dataset.py

Sinh ra `ml/data/{train,val,test}.csv` với ba cột: question, label, source.

Vì sao có cột `source`
----------------------
Ba nguồn dữ liệu có giá trị khoa học rất khác nhau, trộn lẫn rồi báo một con số
accuracy chung là tự lừa mình:

* `seed`     — câu viết tay, sát đề thi thật. Đây là dữ liệu gốc.
* `template` — sinh từ khuôn mẫu, đổi số liệu và cách diễn đạt. Làm dày dữ liệu
               huấn luyện, nhưng dễ với mọi mô hình nên KHÔNG dùng để khoe accuracy.
* `hard`     — câu viết tay không chứa từ khoá đặc trưng, hoặc lai môn. Đây mới
               là tập phân định được luật từ khoá với mô hình học sâu.

Khi báo cáo, tách riêng accuracy trên `hard`. Con số trên `template` gần như luôn
đẹp và không nói lên điều gì.

Tách tập
--------
Chia theo tầng (stratified) để ba môn cân bằng ở cả ba tập. Quan trọng hơn: các
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

from ml.seed_questions import HARDS, SEEDS  # noqa: E402

RNG = random.Random(20260804)
DATA_DIR = Path(__file__).resolve().parent / "data"

NHAN = ["math", "physics", "chemistry"]

# ---------------------------------------------------------------------------
# Khuôn mẫu — mỗi khuôn là (chuỗi định dạng, dict các giá trị thay thế)
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, list[tuple[str, dict[str, list[str]]]]] = {
    "math": [
        ("Tính đạo hàm của hàm số y = {f} tại điểm x = {a}",
         {"f": ["x^2 + 3x", "x^3 - 2x", "2x^3 + x", "x^4 - x^2", "3x^2 - 5x + 1"],
          "a": ["0", "1", "2", "-1", "3"]}),
        ("Tính tích phân của {f} từ {a} đến {b}",
         {"f": ["x", "x^2", "2x + 1", "sin(x)", "e^x"],
          "a": ["0", "1"], "b": ["2", "3", "pi"]}),
        ("Giải phương trình {pt}",
         {"pt": ["x^2 - 5x + 6 = 0", "2x^2 - 3x - 5 = 0", "x^2 - 9 = 0",
                 "3x - 7 = 2", "x^2 + 4x + 4 = 0"]}),
        ("Tìm giá trị {loai} của hàm số y = {f} trên đoạn [{a}; {b}]",
         {"loai": ["lớn nhất", "nhỏ nhất"],
          "f": ["-x^2 + 4x", "x^2 - 2x", "x^3 - 3x"],
          "a": ["0", "-1"], "b": ["2", "3", "4"]}),
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
        ("Tính thể tích khối {hinh} có {dl1} bằng {a} và {dl2} bằng {b}",
         {"hinh": ["chóp", "lăng trụ", "hộp chữ nhật"],
          "dl1": ["diện tích đáy"], "a": ["12", "20", "36"],
          "dl2": ["chiều cao"], "b": ["4", "5", "6"]}),
        ("Tìm tiệm cận {loai} của đồ thị hàm số y = ({a}x + {b})/(x - {c})",
         {"loai": ["ngang", "đứng"], "a": ["2", "3"], "b": ["1", "5"], "c": ["1", "3"]}),
        ("Cho số phức z = {a} + {b}i. Tính {yeu_cau}",
         {"a": ["3", "1", "2"], "b": ["4", "2", "5"],
          "yeu_cau": ["môđun của z", "phần thực của z", "số phức liên hợp của z"]}),
    ],
    "physics": [
        ("Một vật dao động điều hoà với biên độ {A} cm và tần số {f} Hz. Tính {yeu_cau}",
         {"A": ["3", "4", "5", "8", "10"], "f": ["1", "2", "2,5", "5"],
          "yeu_cau": ["vận tốc cực đại", "gia tốc cực đại", "chu kỳ dao động"]}),
        ("Con lắc lò xo có độ cứng {k} N/m và vật nặng {m} g. Tính chu kỳ dao động",
         {"k": ["50", "100", "200", "400"], "m": ["100", "250", "400", "500"]}),
        ("Một vật khối lượng {m} kg chịu tác dụng lực {F} N. Tính gia tốc",
         {"m": ["2", "4", "5", "10"], "F": ["10", "20", "30", "50"]}),
        ("Vật khối lượng {m} kg chuyển động với vận tốc {v} m/s. Tính {yeu_cau}",
         {"m": ["2", "3", "5"], "v": ["4", "6", "10"],
          "yeu_cau": ["động năng", "động lượng"]}),
        ("Đoạn mạch có điện trở {R} ôm và hiệu điện thế {U} V. Tính {yeu_cau}",
         {"R": ["10", "20", "25", "50"], "U": ["12", "24", "110", "220"],
          "yeu_cau": ["cường độ dòng điện", "công suất tiêu thụ"]}),
        ("Hai điện trở {r1} ôm và {r2} ôm mắc {cach}. Tính điện trở tương đương",
         {"r1": ["3", "4", "6"], "r2": ["6", "8", "12"], "cach": ["nối tiếp", "song song"]}),
        ("Sóng có tần số {f} Hz và bước sóng {lam} m. Tính tốc độ truyền sóng",
         {"f": ["50", "100", "200", "440"], "lam": ["2", "3", "4", "6"]}),
        ("Một vật rơi tự do từ độ cao {h} m. Tính {yeu_cau}, lấy g = 10 m/s2",
         {"h": ["20", "45", "80", "125"],
          "yeu_cau": ["thời gian rơi", "vận tốc khi chạm đất"]}),
        ("Thấu kính {loai} có tiêu cự {f} cm, vật đặt cách thấu kính {d} cm. Xác định vị trí ảnh",
         {"loai": ["hội tụ", "phân kỳ"], "f": ["10", "20", "25"], "d": ["15", "30", "40"]}),
        ("Chất phóng xạ có chu kỳ bán rã {T} ngày. Sau {t} ngày còn lại bao nhiêu phần trăm",
         {"T": ["4", "8", "12"], "t": ["8", "16", "24", "36"]}),
    ],
    "chemistry": [
        ("Đốt cháy hoàn toàn {m} gam {kl} trong khí O2. Tính khối lượng oxit thu được",
         {"m": ["2,4", "5,6", "8,1", "11,2"], "kl": ["Fe", "Mg", "Al", "Cu"]}),
        ("Cân bằng phương trình phản ứng {pt}",
         {"pt": ["Al + HCl tạo AlCl3 và H2", "Fe + O2 tạo Fe3O4",
                 "Na + H2O tạo NaOH và H2", "CH4 + O2 tạo CO2 và H2O"]}),
        ("Tính số mol của {m} gam {chat}",
         {"m": ["4", "9,8", "16", "23"], "chat": ["NaOH", "H2SO4", "CaCO3", "KMnO4"]}),
        ("Hoà tan {m} gam {chat} vào nước thành {V} ml dung dịch. Tính nồng độ mol",
         {"m": ["4", "8", "10"], "chat": ["NaOH", "KOH", "NaCl"],
          "V": ["200", "250", "500"]}),
        ("Tính pH của dung dịch {chat} nồng độ {C} M",
         {"chat": ["HCl", "HNO3", "NaOH"], "C": ["0,001", "0,01", "0,1"]}),
        ("Cho {m} gam {kl} tác dụng hết với dung dịch HCl. Tính thể tích khí H2 ở điều kiện tiêu chuẩn",
         {"m": ["2,4", "5,4", "6,5", "13"], "kl": ["Mg", "Al", "Zn", "Fe"]}),
        ("Tính thành phần phần trăm khối lượng của {nt} trong hợp chất {hc}",
         {"nt": ["oxi", "hiđro", "cacbon"], "hc": ["H2O", "CO2", "H2SO4", "CaCO3"]}),
        ("Xác định số oxi hoá của {nt} trong {hc}",
         {"nt": ["lưu huỳnh", "nitơ", "mangan"],
          "hc": ["H2SO4", "HNO3", "KMnO4", "K2Cr2O7"]}),
        ("Cho {V} ml dung dịch {muoi} {C} M tác dụng với dung dịch {tt} dư. Tính khối lượng kết tủa",
         {"V": ["100", "200", "250"], "muoi": ["AgNO3", "BaCl2", "Na2SO4"],
          "C": ["0,1", "0,2", "1"], "tt": ["NaCl", "Na2SO4", "BaCl2"]}),
        ("Tính khối lượng {chat} cần để pha {V} ml dung dịch {C} M",
         {"chat": ["NaCl", "NaOH", "KNO3"], "V": ["100", "250", "500"],
          "C": ["0,2", "0,4", "1"]}),
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


def dung_dataset(moi_khuon: int = 45) -> list[tuple[str, str, str, int]]:
    """Trả về danh sách (question, label, source, khuon_id).

    `khuon_id` dùng để chia tập theo nhóm — mọi biến thể của cùng một khuôn phải
    nằm chung một tập, nếu không thì test bị rò rỉ.
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
        for mau, gia_tri in khuons:
            khuon_id += 1
            for cau in _sinh_tu_khuon(mau, gia_tri, moi_khuon):
                hang.append((cau, nhan, "template", khuon_id))

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

    # Chia theo tầng: xáo trong từng nhãn để ba môn cân bằng ở mọi tập.
    theo_nhan: dict[str, list[int]] = {}
    for kid, muc in theo_khuon.items():
        theo_nhan.setdefault(muc[0][1], []).append(kid)

    # Xếp tham lam theo SỐ CÂU, không theo số khuôn: mỗi khuôn sinh ra số câu rất
    # khác nhau, chia đều số khuôn thì test lệch hẳn (đo thử: Toán 92 câu, Lý 24).
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
