"""Kho định lý — công thức Toán chương trình THPT, tra cứu tất định.

Kho chia theo đúng hai phân môn của hệ thống: `dai_so` và `hinh_hoc`.

Vì sao cần
----------
Mô hình 4B chọn hướng giải khá tốt nhưng **nhớ công thức thì không đáng tin**. Đo
được trên bộ đề: bài hình học không gian và bài toạ độ yếu nhất, vì chúng cần
nhiều công thức phải nhớ chính xác (thể tích khối tròn xoay, khoảng cách từ điểm
đến mặt phẳng) mà model hay nhớ nhầm hệ số.

Chèn sẵn công thức đúng vào prompt rẻ hơn nhiều so với để model tự nhớ rồi sai,
rồi Verify bắt, rồi giải lại. Chi phí: vài trăm token prefill, không thêm lượt
gọi LLM nào.

Cách tra
--------
Chấm điểm theo hai nguồn, cộng lại:
  * `Plan.topic` khớp   -> 3 điểm  (Router điền bằng nhãn PhoBERT, tất định)
  * từ khoá xuất hiện   -> 1 điểm mỗi từ

Lấy tối đa `SO_MUC_TOI_DA` mục điểm cao nhất. Không có mục nào đạt ngưỡng thì trả
chuỗi rỗng — thà không chèn gì còn hơn chèn công thức lạc đề, vì công thức sai
chỗ còn dẫn model đi sai hướng.

Giới hạn cần biết: kho này chỉ phủ chương trình phổ thông. Bài ngoài chương trình
sẽ không tra được gì, và đó là hành vi đúng.
"""

from __future__ import annotations

import re
import unicodedata

# Số mục tối đa chèn vào prompt. Ba là đủ: nhiều hơn thì loãng, và mỗi mục thừa
# là thêm token prefill cho mọi lượt gọi.
SO_MUC_TOI_DA = 3

# Dưới ngưỡng này coi như không liên quan.
#
# Để 2 thì hụt những bài KHÔNG có `topic` và đề chỉ chứa đúng một từ khoá đặc
# trưng — đo được: "Tìm giá trị nhỏ nhất của biểu thức x + 25/x" tra ra rỗng dù
# có mục khớp.
#
# Để 1 thì lọt thêm ít nhiễu, nhưng nhiễu bị chặn bởi hai lớp: kết quả sắp theo
# điểm giảm dần nên mục đúng luôn đứng đầu, và `SO_MUC_TOI_DA` cắt còn 3 mục.
NGUONG_DIEM = 1


def _bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt để so khớp chịu được lỗi gõ thiếu dấu."""
    return "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    ).replace("đ", "d")


# ---------------------------------------------------------------------------
# Nội dung. Mỗi mục: (danh sách topic, danh sách từ khoá, công thức)
# Công thức viết NGẮN, đúng ký hiệu sách giáo khoa Việt Nam.
# ---------------------------------------------------------------------------

KHO: dict[str, list[tuple[list[str], list[str], str]]] = {
    # =====================================================================
    "dai_so": [
        (["dao_ham"], ["đạo hàm", "y'", "f'"],
         "Đạo hàm: (x^n)' = n·x^(n-1); (u·v)' = u'v + uv'; (u/v)' = (u'v - uv')/v²; "
         "(sin x)' = cos x; (cos x)' = -sin x; (e^x)' = e^x; (ln x)' = 1/x."),
        (["tich_phan", "dien_tich_hinh_phang"], ["tích phân", "nguyên hàm", "∫"],
         "Nguyên hàm: ∫x^n dx = x^(n+1)/(n+1) + C (n ≠ -1); ∫(1/x)dx = ln|x| + C; "
         "∫e^x dx = e^x + C. Tích phân xác định: ∫[a→b] f = F(b) - F(a)."),
        (["tich_phan_tung_phan"], ["từng phần"],
         "Tích phân từng phần: ∫u dv = uv - ∫v du. Với ∫x·e^x dx đặt u = x, dv = e^x dx, "
         "được (x-1)e^x + C."),
        (["dien_tich_hinh_phang"], ["diện tích hình phẳng", "giới hạn bởi"],
         "Diện tích hình phẳng giữa hai đồ thị: S = ∫[a→b] |f(x) - g(x)| dx, với a, b "
         "là hoành độ giao điểm."),
        (["phuong_trinh_bac_hai"], ["bậc hai", "delta", "biệt thức"],
         "Phương trình ax² + bx + c = 0: Δ = b² - 4ac; x = (-b ± √Δ)/(2a). "
         "Vi-ét: x₁ + x₂ = -b/a, x₁·x₂ = c/a."),
        (["logarit", "phuong_trinh_logarit"], ["logarit", "log", "ln"],
         "Logarit: log_a(a^k) = k; log_a(xy) = log_a x + log_a y; log_a(x/y) = log_a x - log_a y; "
         "log_a(x^n) = n·log_a x. ĐIỀU KIỆN: đối số phải DƯƠNG — luôn kiểm rồi loại nghiệm ngoại lai."),
        (["phuong_trinh_mu"], ["phương trình mũ", "^x"],
         "Phương trình mũ: a^x = a^y ⟺ x = y (a > 0, a ≠ 1). Dạng a^(2x) - m·a^x + n = 0 "
         "thì đặt t = a^x > 0 rồi giải bậc hai."),
        (["cap_so_cong"], ["cấp số cộng", "công sai"],
         "Cấp số cộng: u_n = u₁ + (n-1)d; S_n = n(u₁ + u_n)/2 = n[2u₁ + (n-1)d]/2."),
        (["cap_so_nhan"], ["cấp số nhân", "công bội"],
         "Cấp số nhân: u_n = u₁·q^(n-1); S_n = u₁(q^n - 1)/(q - 1) với q ≠ 1."),
        (["to_hop", "chinh_hop", "hoan_vi_vong"], ["tổ hợp", "chỉnh hợp", "hoán vị", "bao nhiêu cách"],
         "Tổ hợp C(n,k) = n!/(k!(n-k)!) — KHÔNG kể thứ tự. "
         "Chỉnh hợp A(n,k) = n!/(n-k)! — CÓ kể thứ tự. "
         "Hoán vị n! ; hoán vị vòng quanh (n-1)!."),
        (["xac_suat", "xac_suat_nhi_thuc"], ["xác suất"],
         "Xác suất cổ điển: P = (số kết quả thuận lợi)/(số kết quả có thể). "
         "Biến cố đối: P(A) = 1 - P(Ā). Nhị thức: P = C(n,k)·p^k·(1-p)^(n-k)."),
        (["so_phuc"], ["số phức", "môđun", "phần thực", "phần ảo"],
         "Số phức z = a + bi: |z| = √(a² + b²); (a+bi)(c+di) = (ac - bd) + (ad + bc)i "
         "vì i² = -1; |z^n| = |z|^n."),
        (["tiem_can"], ["tiệm cận"],
         "Hàm y = (ax + b)/(cx + d): tiệm cận ngang y = a/c, tiệm cận đứng x = -d/c."),
        (["tiep_tuyen"], ["tiếp tuyến"],
         "Tiếp tuyến tại điểm hoành độ x₀: y = f'(x₀)·(x - x₀) + f(x₀)."),
        (["cuc_tri", "diem_uon"], ["cực trị", "cực đại", "cực tiểu", "điểm uốn"],
         "Cực trị: giải y' = 0 rồi xét dấu y' hoặc dấu y''. y'' < 0 là cực ĐẠI, y'' > 0 là cực TIỂU. "
         "Điểm uốn: y'' = 0 và đổi dấu."),
        (["gtln_gtnn"], ["giá trị lớn nhất", "giá trị nhỏ nhất", "gtln", "gtnn"],
         "GTLN/GTNN trên đoạn [a;b]: so sánh giá trị tại HAI ĐẦU MÚT và tại các điểm "
         "tới hạn (y' = 0) nằm trong đoạn."),
        (["bat_dang_thuc"], ["bất đẳng thức", "cauchy", "nhỏ nhất của biểu thức"],
         "Cauchy (AM-GM): với x, y > 0 thì x + y ≥ 2√(xy), dấu bằng khi x = y. "
         "Do đó x + k/x ≥ 2√k với x > 0."),
        (["gioi_han"], ["giới hạn", "lim"],
         "Giới hạn dạng √(ax²+bx) - √a·x khi x→+∞: nhân liên hợp, kết quả b/(2√a)."),
        (["he_phuong_trinh"], ["hệ phương trình"],
         "Hệ hai ẩn: cộng/trừ hai vế để khử một ẩn, hoặc thế. Luôn thử lại nghiệm vào cả hai phương trình."),
    ],
    # =====================================================================
    "hinh_hoc": [
        (["toa_do_the_tich", "the_tich_khoi_chop", "the_tich_lang_tru",
          "hinh_hoc_khong_gian"],
         ["thể tích", "khối chóp", "lăng trụ", "hình nón", "hình trụ", "khối cầu"],
         "Thể tích: chóp V = (1/3)·S_đáy·h; lăng trụ V = S_đáy·h; "
         "nón V = (1/3)πr²h, S_xq = πrl; trụ V = πr²h; cầu V = (4/3)πr³, S = 4πr²."),
        (["hinh_hoc_khong_gian"], ["chóp tứ giác đều", "cạnh bên"],
         "Chóp tứ giác đều cạnh đáy a, cạnh bên b: nửa đường chéo đáy = a√2/2, "
         "chiều cao h = √(b² - a²/2)."),
        (["hinh_hoc_phang"], ["tam giác", "heron", "diện tích tam giác", "định lý cosin"],
         "Tam giác: Heron S = √(p(p-a)(p-b)(p-c)) với p = (a+b+c)/2; "
         "S = (1/2)ab·sinC; định lý cosin a² = b² + c² - 2bc·cosA; "
         "R = abc/(4S); r = S/p."),
        (["toa_do_khoang_cach", "toa_do_kc_diem_mp", "hinh_hoc_toa_do"],
         ["oxyz", "mặt phẳng", "khoảng cách từ điểm", "vectơ"],
         "Toạ độ: khoảng cách hai điểm = √(Δx² + Δy² + Δz²); "
         "điểm đến mặt phẳng ax+by+cz+d=0: |ax₀+by₀+cz₀+d|/√(a²+b²+c²); "
         "cos góc hai vectơ = (u·v)/(|u||v|). Tử số LUÔN có giá trị tuyệt đối — "
         "khoảng cách không bao giờ âm."),
        (["hinh_hoc_toa_do"], ["đường tròn", "oxy"],
         "Đường tròn x² + y² - 2ax - 2by + c = 0 có tâm I(a;b), bán kính R = √(a² + b² - c). "
         "Khoảng cách điểm đến đường thẳng ax+by+c=0: |ax₀+by₀+c|/√(a²+b²)."),
        (["hinh_hoc_khong_gian"], ["góc giữa", "hình chiếu", "vuông góc"],
         "Góc giữa đường thẳng và mặt phẳng = góc giữa đường thẳng và HÌNH CHIẾU của "
         "nó trên mặt phẳng đó. Góc giữa hai mặt phẳng lấy theo hai đường vuông góc "
         "với giao tuyến. Mọi giá trị cosin phải nằm trong [-1; 1]."),
        (["khac_hinh_hoc"], ["mặt cầu ngoại tiếp", "bán kính mặt cầu"],
         "Mặt cầu ngoại tiếp: tâm cách đều mọi đỉnh. Với khối hộp chữ nhật kích thước "
         "a, b, c thì R = √(a² + b² + c²)/2."),
    ],
}


def _diem(muc: tuple[list[str], list[str], str], topic: str, van_ban: str) -> int:
    cac_topic, tu_khoa, _ = muc
    # So topic sau khi BỎ DẤU. Prompt dặn Planner sinh slug không dấu, nhưng model
    # 4B không nghe: đo được nó trả về `khối_lượng_mol` thay vì `khoi_luong_mol`.
    # So thẳng thì điểm khớp topic (+3) KHÔNG BAO GIỜ kích hoạt và kho định lý chạy
    # ở nửa công suất — một lỗi câm, không có dấu hiệu gì ngoài kết quả tra kém.
    diem = 3 if topic and any(topic == _bo_dau(t) for t in cac_topic) else 0
    for tk in tu_khoa:
        if _bo_dau(tk) in van_ban:
            diem += 1
    return diem


def tra_cuu(subject: str, topic: str = "", cau_hoi: str = "") -> list[str]:
    """Trả các công thức liên quan nhất, nhiều nhất `SO_MUC_TOI_DA` mục."""
    muc_list = KHO.get(subject, [])
    if not muc_list:
        return []

    van_ban = _bo_dau(cau_hoi)
    topic = _bo_dau((topic or "").strip())

    cham = [(_diem(m, topic, van_ban), m[2]) for m in muc_list]
    cham = [(d, n) for d, n in cham if d >= NGUONG_DIEM]
    cham.sort(key=lambda x: -x[0])
    return [n for _, n in cham[:SO_MUC_TOI_DA]]


def doan_van(subject: str, topic: str = "", cau_hoi: str = "") -> str:
    """Khối văn bản chèn thẳng vào prompt. Rỗng nếu không tra được gì."""
    muc = tra_cuu(subject, topic, cau_hoi)
    if not muc:
        return ""
    return "Công thức liên quan (đã kiểm chứng, dùng đúng như ghi ở đây):\n" + "\n".join(
        f"- {m}" for m in muc
    )
