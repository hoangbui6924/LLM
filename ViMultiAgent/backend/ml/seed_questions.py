"""Câu hỏi hạt giống — viết tay, đây là phần dữ liệu gốc của dự án.

Nguồn gốc dữ liệu (cần nêu rõ trong báo cáo, đừng nhập nhèng chỗ này):

* `SEEDS` — soạn tay theo chương trình Toán THPT, bám các dạng bài phổ biến trong
  đề thi tốt nghiệp và sách bài tập. Đây là phần "dataset do nhóm tự xây dựng".
* `HARDS` — cũng soạn tay, nhưng CỐ TÌNH chọn câu **không chứa từ khoá đặc trưng**
  của dạng. Đây là tập quan trọng nhất: bộ phân loại bằng luật từ khoá sẽ gãy ở
  đây, và chỉ nhóm câu này mới trả lời được câu hỏi "vì sao cần học sâu?".
* Phần sinh thêm bằng khuôn mẫu nằm ở `build_dataset.py`, gắn nhãn source khác để
  lúc báo cáo tách bạch được.

Nhãn là DẠNG BÀI, không phải môn
--------------------------------
Hệ thống chỉ làm Toán THPT nên phân loại môn không còn ý nghĩa. Bộ nhãn ở đây là
15 dạng bài, trùng khớp với `agents/router.py::NHANH_CUA_DANG` — Router lấy dạng
bài rồi quy về phân môn Đại số hay Hình học để chọn agent.

Hai nhãn `khac_dai_so` và `khac_hinh_hoc` là nhãn gom: dạng bài nằm trong phân môn
đó nhưng chưa đủ nhiều để tách riêng. Có chúng thì mô hình không bị ép gán bừa một
dạng hẹp cho câu không thuộc dạng nào, và Router vẫn chọn đúng agent.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# ĐẠI SỐ & GIẢI TÍCH
# ---------------------------------------------------------------------------

SEEDS: dict[str, list[str]] = {
    "dao_ham": [
        "Tính đạo hàm của hàm số y = x^3 - 3x^2 + 2x tại điểm x = 1",
        "Tính đạo hàm cấp hai của hàm số y = sin(x)",
        "Cho hàm số y = e^x. Tính đạo hàm tại x = 0",
        "Tính đạo hàm của hàm hợp y = (2x + 1)^4",
        "Tính đạo hàm của y = ln(x) tại x = 2",
    ],
    "tich_phan": [
        "Tìm nguyên hàm của hàm số f(x) = 2x + cos(x)",
        "Tính tích phân của x^2 từ 0 đến 3",
        "Tính diện tích hình phẳng giới hạn bởi đồ thị y = x^2 và trục hoành từ x = 0 đến x = 2",
        "Tính tích phân của sin(x) từ 0 đến pi",
    ],
    "gioi_han": [
        "Tính giới hạn của (x^2 - 1)/(x - 1) khi x tiến tới 1",
    ],
    "phuong_trinh": [
        "Giải phương trình bậc hai x^2 - 5x + 6 = 0",
        "Giải bất phương trình 2x - 7 > 3",
        "Giải phương trình logarit cơ số 2 của x bằng 5",
        "Giải hệ phương trình x + y = 5 và x - y = 1",
        "Giải phương trình lượng giác sin(x) = 1/2 trên khoảng từ 0 đến 2pi",
        "Tìm m để phương trình x^2 - 2mx + m + 2 = 0 có hai nghiệm phân biệt",
        "Tính tổng các nghiệm của phương trình x^2 - 7x + 12 = 0",
        "Tìm nghiệm của phương trình 2^x = 16",
        "Giải phương trình chứa căn: căn bậc hai của (x + 3) bằng 2",
    ],
    "tiep_tuyen": [
        "Viết phương trình tiếp tuyến của đồ thị hàm số y = x^2 + 3x tại điểm có hoành độ x = 1",
        "Cho hàm số y = x^3 - 2x. Viết phương trình tiếp tuyến tại điểm có hoành độ bằng 2",
    ],
    "gtln": [
        "Tìm giá trị lớn nhất của hàm số y = -x^2 + 4x - 1 trên đoạn [0; 3]",
    ],
    "gtnn": [
        "Tìm giá trị nhỏ nhất của biểu thức x^2 + 4x + 7",
    ],
    "so_diem_cuc_tri": [
        "Tìm điểm cực trị của hàm số y = x^3 - 3x^2 + 1",
    ],
    "tiem_can_ngang": [
        "Tìm tiệm cận ngang của đồ thị hàm số y = (2x + 1)/(x - 3)",
    ],
    "tiem_can_dung": [
        "Tìm tiệm cận đứng của đồ thị hàm số y = (x + 2)/(x - 5)",
    ],
    "khac_dai_so": [
        "Tìm tập xác định của hàm số y = căn bậc hai của (x - 4)",
        "Khảo sát sự biến thiên và vẽ đồ thị hàm số y = x^3 - 3x",
        "Cho cấp số cộng có u1 = 3 và công sai d = 4. Tính u10",
        "Cho cấp số nhân có số hạng đầu bằng 2, công bội bằng 3. Tính tổng 5 số hạng đầu",
        "Rút gọn biểu thức logarit cơ số 3 của 27 cộng logarit cơ số 3 của 9",
        "Tính số cách chọn 3 học sinh từ một nhóm 10 học sinh",
        "Một hộp có 5 bi đỏ và 3 bi xanh. Tính xác suất lấy được bi đỏ khi bốc ngẫu nhiên một viên",
        "Tìm hệ số của x^3 trong khai triển nhị thức (1 + 2x)^5",
        "Cho số phức z = 3 + 4i. Tính môđun của z",
        "Tìm phần thực và phần ảo của số phức z = (1 + i)^2",
        "Xét tính đơn điệu của hàm số y = x^3 + 3x trên tập số thực",
        "Cho dãy số un = 3n + 1. Tính u5",
        "Tính số hoán vị của 5 phần tử phân biệt",
        "Xác định toạ độ đỉnh của parabol y = x^2 - 4x + 3",
    ],
    # -----------------------------------------------------------------------
    # HÌNH HỌC
    # -----------------------------------------------------------------------
    "toa_do_khoang_cach": [
        "Tính khoảng cách từ điểm M(1; 2) đến đường thẳng 3x + 4y - 5 = 0",
        "Trong không gian Oxyz, tính khoảng cách giữa hai điểm A(1; 2; 3) và B(4; 6; 3)",
    ],
    "toa_do_the_tich": [
        "Tính thể tích khối chóp có diện tích đáy 12 và chiều cao 5",
        "Cho hình lập phương cạnh 4. Tính thể tích khối lập phương đó",
    ],
    "toa_do_kc_diem_mp": [
        "Trong không gian Oxyz, tính khoảng cách từ điểm A(1; 2; 3) đến mặt phẳng x + 2y - 2z + 1 = 0",
        "Tính khoảng cách từ gốc toạ độ đến mặt phẳng 2x - y + 2z - 6 = 0",
    ],
    "khac_hinh_hoc": [
        "Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Tính độ dài cạnh BC",
        "Tính diện tích mặt cầu bán kính 3",
        "Cho hai vectơ a = (1; 2) và b = (3; -1). Tính tích vô hướng của chúng",
        "Tìm phương trình đường thẳng đi qua hai điểm A(1; 2) và B(3; 6)",
        "Cho tam giác có ba cạnh 5, 12, 13. Chứng minh tam giác đó vuông",
    ],
}


# ---------------------------------------------------------------------------
# Câu KHÓ — không chứa từ khoá đặc trưng của dạng.
#
# Đây là tập phân định luật từ khoá với mô hình học sâu. `build_dataset.py` dồn
# toàn bộ nhóm này vào tập test và báo accuracy riêng cho nó.
# ---------------------------------------------------------------------------

HARDS: dict[str, list[str]] = {
    "khac_dai_so": [
        "Tính giá trị của biểu thức khi thay x bằng 2",
        "Cho biết mối liên hệ giữa hai đại lượng tỉ lệ nghịch với nhau",
        "Một người gửi 100 triệu với lãi suất 6% một năm. Sau 3 năm nhận bao nhiêu",
        "Tìm quy luật của dãy số 2, 6, 12, 20, 30",
        "Một bể chứa đầy sau 6 giờ nếu mở vòi thứ nhất, 4 giờ nếu mở vòi thứ hai. Mở cả hai thì bao lâu",
        "Chia 120 cái bánh cho ba nhóm theo tỉ lệ 2 : 3 : 5",
        "Trung bình cộng của năm số là 12. Tổng của chúng bằng bao nhiêu",
        "Xác suất để gieo con xúc xắc được mặt chẵn là bao nhiêu",
        "Có bao nhiêu cách xếp 4 người vào một hàng ghế",
        "Tìm hai số biết tổng bằng 20 và tích bằng 96",
        "Tính tổng các số tự nhiên từ 1 đến 100",
    ],
    "khac_hinh_hoc": [
        "Tính chu vi của hình tròn có đường kính 10",
        "Một mảnh vườn hình chữ nhật có chu vi 40 m, chiều dài hơn chiều rộng 4 m. Tính diện tích",
        "Một hình hộp chữ nhật có ba kích thước 2, 3, 4. Tính thể tích",
        "Nếu tăng cạnh hình vuông lên gấp đôi thì diện tích tăng bao nhiêu lần",
    ],
}

# Bộ nhãn chuẩn của dự án. Phải khớp `agents/router.py::NHANH_CUA_DANG`.
NHAN = [
    "dao_ham", "tich_phan", "gioi_han", "phuong_trinh", "tiep_tuyen",
    "gtln", "gtnn", "so_diem_cuc_tri", "tiem_can_ngang", "tiem_can_dung",
    "khac_dai_so",
    "toa_do_khoang_cach", "toa_do_the_tich", "toa_do_kc_diem_mp", "khac_hinh_hoc",
]
