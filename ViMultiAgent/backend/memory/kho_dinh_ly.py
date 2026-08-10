"""Kho định lý — công thức chương trình THPT, tra cứu tất định.

Vì sao cần
----------
Mô hình 4B chọn hướng giải khá tốt nhưng **nhớ công thức thì không đáng tin**. Đo
được trên bộ đề: môn Hoá yếu nhất ở cả hai cấu hình (76% và 84%), và người dùng
thử tay cũng báo đúng triệu chứng — "không nắm vững bảng tuần hoàn nên cân bằng
sai hoặc khối lượng mol sai".

Chèn sẵn công thức đúng vào prompt rẻ hơn nhiều so với để model tự nhớ rồi sai,
rồi Verify bắt, rồi giải lại. Chi phí: vài trăm token prefill, không thêm lượt
gọi LLM nào.

Cách tra
--------
Chấm điểm theo hai nguồn, cộng lại:
  * `Plan.topic` khớp   -> 3 điểm  (Planner đã chuẩn hoá sẵn thành slug)
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
# Để 2 thì hụt những bài mà Planner KHÔNG trả về `topic` và đề chỉ chứa đúng một
# từ khoá đặc trưng — đo được: "Hoà tan 5,4 gam Al vào HCl dư" và "Tìm giá trị nhỏ
# nhất của biểu thức x + 25/x" đều tra ra rỗng dù có mục khớp.
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
    "math": [
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
        (["the_tich_khoi_chop", "the_tich_lang_tru", "hinh_hoc_khong_gian"],
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
        (["hinh_hoc_toa_do"], ["oxyz", "mặt phẳng", "khoảng cách từ điểm", "vectơ"],
         "Toạ độ: khoảng cách hai điểm = √(Δx² + Δy² + Δz²); "
         "điểm đến mặt phẳng ax+by+cz+d=0: |ax₀+by₀+cz₀+d|/√(a²+b²+c²); "
         "cos góc hai vectơ = (u·v)/(|u||v|)."),
        (["hinh_hoc_toa_do"], ["đường tròn", "oxy"],
         "Đường tròn x² + y² - 2ax - 2by + c = 0 có tâm I(a;b), bán kính R = √(a² + b² - c). "
         "Khoảng cách điểm đến đường thẳng ax+by+c=0: |ax₀+by₀+c|/√(a²+b²)."),
        (["he_phuong_trinh"], ["hệ phương trình"],
         "Hệ hai ẩn: cộng/trừ hai vế để khử một ẩn, hoặc thế. Luôn thử lại nghiệm vào cả hai phương trình."),
    ],
    # =====================================================================
    "physics": [
        (["dao_dong_dieu_hoa", "nang_luong_dao_dong"], ["dao động điều hoà", "biên độ", "li độ"],
         "Dao động điều hoà: ω = 2πf = 2π/T; v_max = Aω; a_max = Aω²; "
         "v = ω√(A² - x²); W = (1/2)kA²; W_đ/W_t = (A² - x²)/x². "
         "ĐỔI cm sang m trước khi tính."),
        (["con_lac_lo_xo"], ["con lắc lò xo", "độ cứng"],
         "Con lắc lò xo: ω = √(k/m); T = 2π√(m/k)."),
        (["con_lac_don"], ["con lắc đơn"],
         "Con lắc đơn: T = 2π√(l/g)."),
        (["tong_hop_dao_dong"], ["tổng hợp", "lệch pha"],
         "Tổng hợp hai dao động cùng phương cùng tần số: "
         "A² = A₁² + A₂² + 2A₁A₂·cos(Δφ). Vuông pha thì A = √(A₁² + A₂²)."),
        (["song_co", "song_dung"], ["sóng", "bước sóng", "sóng dừng"],
         "Sóng: v = λf. Sóng dừng hai đầu cố định: l = n·λ/2 (n là số bụng). "
         "Một đầu tự do: l = (2n+1)λ/4."),
        (["dinh_luat_ohm", "dien_tro", "mach_dien_mot_chieu"], ["điện trở", "ohm", "cường độ dòng"],
         "Ohm: I = U/R. Nối tiếp R = R₁ + R₂. Song song R = R₁R₂/(R₁+R₂). "
         "Toàn mạch: I = E/(R + r)."),
        (["mach_rlc"], ["rlc", "tổng trở", "cảm kháng", "dung kháng", "cộng hưởng"],
         "Mạch RLC nối tiếp: Z = √(R² + (Z_L - Z_C)²); I = U/Z; P = UIcosφ = I²R = U²R/Z². "
         "Cộng hưởng khi Z_L = Z_C: Z = R, P_max = U²/R."),
        (["mach_dao_dong"], ["mạch lc", "dao động riêng"],
         "Mạch dao động LC: f = 1/(2π√(LC)); T = 2π√(LC). Đổi mH, μF, pF về H và F trước khi tính."),
        (["may_bien_ap"], ["máy biến áp", "sơ cấp", "thứ cấp"],
         "Máy biến áp lí tưởng: U₂/U₁ = N₂/N₁ = I₁/I₂."),
        (["giao_thoa_anh_sang"], ["giao thoa", "y-âng", "khoảng vân", "vân sáng"],
         "Giao thoa Y-âng: khoảng vân i = λD/a; vân sáng bậc k cách vân trung tâm x = k·i. "
         "ĐỔI đơn vị: mm→m, μm/nm→m."),
        (["quang_dien", "luong_tu"], ["quang điện", "công thoát", "photon"],
         "Lượng tử: ε = hc/λ. Quang điện Einstein: ε = A + W_đmax, "
         "nên W_đmax = ε - A. 1 eV = 1,6·10⁻¹⁹ J."),
        (["phong_xa", "hat_nhan"], ["phóng xạ", "chu kỳ bán rã", "hạt nhân"],
         "Phóng xạ: m = m₀·(1/2)^(t/T); phần đã phân rã = m₀[1 - (1/2)^(t/T)]. "
         "Hạt nhân ký hiệu A_Z X có Z proton và N = A - Z neutron."),
        (["dong_nang", "the_nang", "co_nang"], ["động năng", "thế năng", "cơ năng"],
         "W_đ = mv²/2; W_t = mgh; bảo toàn cơ năng: mgh = mv²/2 nên v = √(2gh)."),
        (["dong_luong"], ["động lượng", "va chạm"],
         "Động lượng p = mv, bảo toàn trong va chạm. Va chạm mềm: v' = m₁v₁/(m₁ + m₂)."),
        (["nem_ngang", "nem_xien"], ["ném ngang", "ném xiên", "tầm xa"],
         "Ném ngang: t = √(2h/g), tầm xa L = v₀t. "
         "Ném xiên: tầm xa L = v₀²·sin(2α)/g."),
        (["nhiet_luong", "nhiet_dien"], ["nhiệt lượng", "nhiệt dung riêng"],
         "Q = mc·Δt. Toả nhiệt trên điện trở (Joule-Lenz): Q = I²Rt."),
        (["cong_co_hoc", "cong_suat_dien"], ["công", "công suất"],
         "Công cơ học A = F·s·cosα. Công suất điện P = UI; điện năng A = P·t."),
        (["chat_khi"], ["khí lí tưởng", "đẳng nhiệt", "đẳng áp"],
         "Khí lí tưởng: đẳng nhiệt p₁V₁ = p₂V₂; đẳng áp V₁/T₁ = V₂/T₂; "
         "tổng quát p₁V₁/T₁ = p₂V₂/T₂ với T tính bằng Kelvin."),
        (["thau_kinh"], ["thấu kính", "tiêu cự", "ảnh"],
         "Thấu kính: 1/f = 1/d + 1/d', suy ra d' = df/(d - f). Độ phóng đại k = -d'/d."),
        (["dien_tich"], ["điện tích", "coulomb"],
         "Coulomb: F = k·|q₁q₂|/r² với k = 9·10⁹ N·m²/C²."),
        (["tu_truong", "cam_ung_dien_tu"], ["từ trường", "lực từ", "cảm ứng"],
         "Lực từ F = BIl·sinα. Suất điện động cảm ứng e = N·|ΔΦ/Δt|."),
        (["ap_suat"], ["áp suất"],
         "Áp suất chất lỏng p = ρgh."),
        (["khoi_luong_rieng"], ["khối lượng riêng"],
         "Khối lượng riêng D = m/V."),
        (["doi_don_vi"], ["km/h", "đổi đơn vị"],
         "Đổi đơn vị: 1 km/h = 1/3,6 m/s. Luôn đưa mọi dữ kiện về hệ SI TRƯỚC khi thay số."),
    ],
    # =====================================================================
    "chemistry": [
        (["so_mol", "the_tich_khi", "khoi_luong_chat"], ["số mol", "đktc", "mol"],
         "Số mol: n = m/M; n = V/22,4 (khí ở đktc); n = C_M·V (V tính bằng lít). "
         "Ngược lại m = n·M, V = n·22,4."),
        (["khoi_luong_mol"], ["khối lượng mol", "nguyên tử khối"],
         "Nguyên tử khối phổ thông: H=1, C=12, N=14, O=16, Na=23, Mg=24, Al=27, "
         "S=32, Cl=35,5, K=39, Ca=40, Fe=56, Cu=64, Zn=65, Ag=108, Ba=137. "
         "Khối lượng mol hợp chất = tổng nguyên tử khối theo chỉ số."),
        (["nong_do_mol", "pha_loang"], ["nồng độ mol", "pha loãng"],
         "Nồng độ mol C_M = n/V (V tính bằng lít). Pha loãng: C₁V₁ = C₂V₂ vì số mol "
         "chất tan không đổi. Trộn hai dung dịch: C = (n₁ + n₂)/(V₁ + V₂)."),
        (["nong_do_phan_tram"], ["nồng độ phần trăm", "c%"],
         "C% = m_chất tan/m_dung dịch · 100, với m_dung dịch = m_chất tan + m_dung môi."),
        (["can_bang_pthh"], ["cân bằng", "phương trình phản ứng"],
         "Cân bằng phương trình: số nguyên tử MỖI nguyên tố phải bằng nhau ở hai vế. "
         "Viết và cân bằng TRƯỚC mọi tính toán, rồi mới lập tỉ lệ mol theo hệ số."),
        (["tinh_theo_pthh"], ["tính theo phương trình"],
         "Tính theo PTHH: đổi khối lượng sang mol → lập tỉ lệ theo HỆ SỐ phương trình "
         "→ đổi ngược về khối lượng hoặc thể tích."),
        (["chat_du"], ["chất dư", "chất hết", "vừa đủ"],
         "Bài chất dư: chia số mol mỗi chất cho hệ số của nó; tỉ số NHỎ NHẤT là chất hết, "
         "và mọi tính toán phải theo chất hết đó."),
        (["hieu_suat"], ["hiệu suất"],
         "Hiệu suất: m_thực tế = m_lý thuyết · H/100. Tính theo lý thuyết trước rồi mới nhân H."),
        (["kim_loai_axit", "kim_loai_nuoc"],
         ["tác dụng axit", "hcl", "h2so4 loãng", "hoà tan", "hòa tan", "kim loại", "khí h2"],
         "Kim loại + axit loãng → muối + H₂. Kim loại hoá trị n cho n/2 mol H₂ mỗi mol. "
         "Fe lên hoá trị II với HCl và H₂SO₄ loãng. Cu, Ag đứng SAU H nên KHÔNG phản ứng."),
        (["axit_bazo", "ph"], ["trung hoà", "ph", "axit", "bazơ"],
         "Trung hoà: HCl + NaOH → NaCl + H₂O (1:1); H₂SO₄ + 2NaOH (1:2). "
         "pH = -log[H⁺]; pOH = -log[OH⁻]; pH + pOH = 14. Axit mạnh phân li hoàn toàn."),
        (["bao_toan_khoi_luong", "bao_toan_nguyen_to"], ["bảo toàn khối lượng"],
         "Bảo toàn khối lượng: tổng khối lượng chất tham gia = tổng khối lượng sản phẩm. "
         "Kim loại + O₂ → oxit thì m(O₂) = m(oxit) - m(kim loại)."),
        (["bao_toan_electron"], ["bảo toàn electron", "oxi hoá", "khử"],
         "Bảo toàn electron: tổng electron chất khử NHƯỜNG = tổng electron chất oxi hoá NHẬN. "
         "n(e) = n(kim loại) × hoá trị. Mỗi mol H₂ nhận 2 electron; NO₂ nhận 1; NO nhận 3."),
        (["dien_phan"], ["điện phân", "faraday", "catot"],
         "Định luật Faraday: m = A·I·t/(n·F) với F = 96500 C/mol, n là số electron trao đổi "
         "(Cu²⁺ nhận 2, Ag⁺ nhận 1)."),
        (["dot_chay_huu_co"], ["đốt cháy", "hiđrocacbon", "ankan", "anken"],
         "Đốt cháy CxHy: CxHy + (x + y/4)O₂ → xCO₂ + (y/2)H₂O. "
         "Số C = n(CO₂)/n(chất); số H = 2·n(H₂O)/n(chất). "
         "Ankan CnH(2n+2), anken CnH2n."),
        (["tim_cong_thuc_phan_tu", "lap_cong_thuc"], ["công thức phân tử", "xác định công thức"],
         "Lập công thức: tính số mol mỗi nguyên tố → lấy tỉ lệ tối giản → công thức đơn giản nhất → "
         "đối chiếu khối lượng mol để ra công thức phân tử."),
        (["este"], ["este", "xà phòng hoá", "thuỷ phân"],
         "Este đơn chức + NaOH → muối + ancol, tỉ lệ 1:1. "
         "M(CH₃COOC₂H₅) = 88; M(CH₃COONa) = 82."),
        (["muoi_cacbonat", "ket_tua"], ["cacbonat", "caco3", "kết tủa", "co2"],
         "CaCO₃ + 2HCl → CaCl₂ + H₂O + CO₂ (tỉ lệ mol CaCO₃ : CO₂ = 1:1). "
         "CO₂ + Ca(OH)₂ dư → CaCO₃↓ + H₂O. M(CaCO₃) = 100, M(CaCl₂) = 111."),
        (["hon_hop_kim_loai"], ["hỗn hợp", "phần trăm khối lượng"],
         "Hỗn hợp kim loại + HCl: chỉ kim loại ĐỨNG TRƯỚC H trong dãy hoạt động mới sinh H₂. "
         "Cu, Ag không phản ứng. Dùng số mol H₂ để suy ngược ra kim loại phản ứng."),
        (["cacbohidrat", "len_men"], ["glucozơ", "tinh bột", "lên men", "xenlulozơ"],
         "C₆H₁₂O₆ (M=180) lên men → 2C₂H₅OH (M=46) + 2CO₂. "
         "Tinh bột (C₆H₁₀O₅)n mắt xích 162, thuỷ phân cho glucozơ 180."),
        (["amin"], ["amin", "amino axit"],
         "Amin đơn chức chứa 1 N: đốt cháy 2 mol amin cho 1 mol N₂."),
        (["so_mol_nguyen_tu"], ["số mol nguyên tử"],
         "Số mol nguyên tử một nguyên tố = số mol phân tử × chỉ số của nguyên tố đó."),
        (["phan_ung_the"], ["kim loại mạnh đẩy", "cuso4"],
         "Kim loại mạnh hơn đẩy kim loại yếu hơn ra khỏi muối: Zn + CuSO₄ → ZnSO₄ + Cu, tỉ lệ 1:1."),
        (["thanh_phan_khong_khi"], ["không khí"],
         "Không khí: O₂ chiếm khoảng 20% thể tích, N₂ khoảng 80%."),
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
