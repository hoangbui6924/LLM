"""Câu hỏi hạt giống — viết tay, đây là phần dữ liệu gốc của dự án.

Nguồn gốc dữ liệu (cần nêu rõ trong báo cáo, đừng nhập nhèng chỗ này):

* `SEED_*`  — soạn tay theo chương trình THPT, bám các dạng bài phổ biến trong
  đề thi tốt nghiệp và sách bài tập. Đây là phần "dataset do nhóm tự xây dựng".
* `HARD_*`  — cũng soạn tay, nhưng CỐ TÌNH chọn câu **không chứa từ khoá đặc
  trưng** của môn, hoặc **lai hai môn**. Đây là tập quan trọng nhất: bộ phân loại
  bằng luật từ khoá sẽ gãy ở đây, và chỉ nhóm câu này mới trả lời được câu hỏi
  "vì sao cần học sâu?".
* Phần sinh thêm bằng khuôn mẫu nằm ở `build_dataset.py`, gắn nhãn source khác
  để lúc báo cáo tách bạch được.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# TOÁN
# ---------------------------------------------------------------------------

SEED_MATH = [
    "Tính đạo hàm của hàm số y = x^3 - 3x^2 + 2x tại điểm x = 1",
    "Tìm nguyên hàm của hàm số f(x) = 2x + cos(x)",
    "Tính tích phân của x^2 từ 0 đến 3",
    "Giải phương trình bậc hai x^2 - 5x + 6 = 0",
    "Giải bất phương trình 2x - 7 > 3",
    "Tìm tập xác định của hàm số y = căn bậc hai của (x - 4)",
    "Khảo sát sự biến thiên và vẽ đồ thị hàm số y = x^3 - 3x",
    "Tìm giá trị lớn nhất của hàm số y = -x^2 + 4x - 1 trên đoạn [0; 3]",
    "Tính giới hạn của (x^2 - 1)/(x - 1) khi x tiến tới 1",
    "Cho cấp số cộng có u1 = 3 và công sai d = 4. Tính u10",
    "Cho cấp số nhân có số hạng đầu bằng 2, công bội bằng 3. Tính tổng 5 số hạng đầu",
    "Giải phương trình logarit cơ số 2 của x bằng 5",
    "Rút gọn biểu thức logarit cơ số 3 của 27 cộng logarit cơ số 3 của 9",
    "Tính số cách chọn 3 học sinh từ một nhóm 10 học sinh",
    "Một hộp có 5 bi đỏ và 3 bi xanh. Tính xác suất lấy được bi đỏ khi bốc ngẫu nhiên một viên",
    "Tìm hệ số của x^3 trong khai triển nhị thức (1 + 2x)^5",
    "Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Tính độ dài cạnh BC",
    "Tính thể tích khối chóp có diện tích đáy 12 và chiều cao 5",
    "Tính diện tích mặt cầu bán kính 3",
    "Cho hai vectơ a = (1; 2) và b = (3; -1). Tính tích vô hướng của chúng",
    "Tìm phương trình đường thẳng đi qua hai điểm A(1; 2) và B(3; 6)",
    "Tìm tiệm cận ngang của đồ thị hàm số y = (2x + 1)/(x - 3)",
    "Tìm điểm cực trị của hàm số y = x^3 - 3x^2 + 1",
    "Giải hệ phương trình x + y = 5 và x - y = 1",
    "Cho số phức z = 3 + 4i. Tính môđun của z",
    "Tìm phần thực và phần ảo của số phức z = (1 + i)^2",
    "Tính đạo hàm cấp hai của hàm số y = sin(x)",
    "Giải phương trình lượng giác sin(x) = 1/2 trên khoảng từ 0 đến 2pi",
    "Tính diện tích hình phẳng giới hạn bởi đồ thị y = x^2 và trục hoành từ x = 0 đến x = 2",
    "Cho hàm số y = e^x. Tính đạo hàm tại x = 0",
    "Tìm m để phương trình x^2 - 2mx + m + 2 = 0 có hai nghiệm phân biệt",
    "Tính tổng các nghiệm của phương trình x^2 - 7x + 12 = 0",
    "Xét tính đơn điệu của hàm số y = x^3 + 3x trên tập số thực",
    "Cho hình lập phương cạnh 4. Tính thể tích khối lập phương đó",
    "Tính khoảng cách từ điểm M(1; 2) đến đường thẳng 3x + 4y - 5 = 0",
    "Tìm nghiệm của phương trình 2^x = 16",
    "Cho dãy số un = 3n + 1. Tính u5",
    "Tính đạo hàm của hàm hợp y = (2x + 1)^4",
    "Giải phương trình chứa căn: căn bậc hai của (x + 3) bằng 2",
    "Tính tích phân của sin(x) từ 0 đến pi",
    "Tìm giá trị nhỏ nhất của biểu thức x^2 + 4x + 7",
    "Cho tam giác có ba cạnh 5, 12, 13. Chứng minh tam giác đó vuông",
    "Tính số hoán vị của 5 phần tử phân biệt",
    "Xác định toạ độ đỉnh của parabol y = x^2 - 4x + 3",
    "Tính đạo hàm của y = ln(x) tại x = 2",
]

# ---------------------------------------------------------------------------
# VẬT LÝ
# ---------------------------------------------------------------------------

SEED_PHYSICS = [
    "Một vật dao động điều hoà với biên độ 5 cm, tần số 2 Hz. Tính vận tốc cực đại",
    "Con lắc lò xo có độ cứng 100 N/m, vật nặng 250 g. Tính chu kỳ dao động",
    "Con lắc đơn dài 1 m dao động tại nơi có g = 9,8 m/s2. Tính chu kỳ",
    "Một vật rơi tự do từ độ cao 45 m. Tính thời gian rơi, lấy g = 10 m/s2",
    "Xe chuyển động thẳng đều đi được 120 km trong 2 giờ. Tính vận tốc",
    "Một vật khối lượng 2 kg chịu lực 10 N. Tính gia tốc của vật",
    "Tính lực ma sát trượt khi hệ số ma sát 0,2 và áp lực 50 N",
    "Vật khối lượng 5 kg chuyển động với vận tốc 4 m/s. Tính động năng",
    "Tính thế năng trọng trường của vật 2 kg ở độ cao 10 m, lấy g = 10 m/s2",
    "Một lò xo bị nén 4 cm, độ cứng 200 N/m. Tính thế năng đàn hồi",
    "Tính công của lực 20 N khi vật dịch chuyển 5 m theo phương của lực",
    "Một máy có công suất 500 W hoạt động trong 2 phút. Tính công thực hiện",
    "Đoạn mạch có điện trở 20 ôm, hiệu điện thế 12 V. Tính cường độ dòng điện",
    "Hai điện trở 4 ôm và 6 ôm mắc nối tiếp. Tính điện trở tương đương",
    "Hai điện trở 6 ôm và 3 ôm mắc song song. Tính điện trở tương đương",
    "Tính nhiệt lượng toả ra trên điện trở 10 ôm khi dòng 2 A chạy qua trong 30 giây",
    "Sóng có tần số 50 Hz và bước sóng 4 m. Tính tốc độ truyền sóng",
    "Tính chu kỳ của sóng có tần số 200 Hz",
    "Ánh sáng đi từ không khí vào nước có chiết suất 1,33. Tính góc khúc xạ khi góc tới 30 độ",
    "Thấu kính hội tụ có tiêu cự 20 cm, vật đặt cách thấu kính 30 cm. Xác định vị trí ảnh",
    "Tính năng lượng của photon có bước sóng 500 nm",
    "Chất phóng xạ có chu kỳ bán rã 8 ngày. Sau 24 ngày còn lại bao nhiêu phần trăm",
    "Tính độ hụt khối của hạt nhân khi biết khối lượng các nuclôn",
    "Một vật chuyển động biến đổi đều từ nghỉ, sau 5 s đạt 20 m/s. Tính gia tốc",
    "Tính quãng đường vật đi được trong 4 s nếu gia tốc 2 m/s2 và vận tốc đầu bằng 0",
    "Tính động lượng của vật 3 kg chuyển động với tốc độ 6 m/s",
    "Hai vật va chạm mềm, tính vận tốc sau va chạm theo định luật bảo toàn động lượng",
    "Tính áp suất chất lỏng ở độ sâu 5 m trong nước, khối lượng riêng 1000 kg/m3",
    "Tính lực đẩy Ác-si-mét tác dụng lên vật có thể tích 0,002 m3 chìm trong nước",
    "Nhiệt lượng cần cung cấp để đun 2 kg nước từ 20 độ C lên 100 độ C là bao nhiêu",
    "Tính hiệu suất của động cơ nhiệt khi nhận 1000 J và sinh công 300 J",
    "Một dây dẫn dài 0,5 m mang dòng 4 A đặt trong từ trường 0,2 T. Tính lực từ",
    "Tính suất điện động cảm ứng khi từ thông biến thiên 0,04 Wb trong 0,2 s",
    "Mạch dao động LC có L = 2 mH và C = 5 microF. Tính tần số dao động riêng",
    "Tính tần số góc của vật dao động điều hoà có chu kỳ 0,5 s",
    "Một vật dao động điều hoà có phương trình x = 4cos(10t). Tính gia tốc cực đại",
    "Tính bước sóng của sóng âm trong không khí tần số 440 Hz, tốc độ âm 340 m/s",
    "Cường độ điện trường tại điểm cách điện tích điểm 2 cm là bao nhiêu",
    "Tính điện dung tương đương của hai tụ 4 microF và 6 microF mắc song song",
    "Một ô tô hãm phanh từ 20 m/s và dừng sau 40 m. Tính gia tốc hãm",
    "Tính trọng lượng của vật 60 kg trên mặt đất, lấy g = 9,8 m/s2",
    "Vật ném ngang từ độ cao 20 m với vận tốc 10 m/s. Tính tầm ném xa",
    "Tính momen lực khi lực 30 N tác dụng cách trục quay 0,4 m",
    "Xác định vị trí ảnh qua gương phẳng khi vật cách gương 15 cm",
    "Tính điện năng tiêu thụ của bóng đèn 60 W dùng trong 5 giờ",
]

# ---------------------------------------------------------------------------
# HOÁ HỌC
# ---------------------------------------------------------------------------

SEED_CHEMISTRY = [
    "Đốt cháy hoàn toàn 5,6 gam Fe trong khí O2 thu được Fe3O4. Tính khối lượng sản phẩm",
    "Cân bằng phương trình phản ứng Al + HCl tạo AlCl3 và H2",
    "Tính số mol của 9,8 gam H2SO4",
    "Tính khối lượng mol của hợp chất Ca(OH)2",
    "Hoà tan 4 gam NaOH vào nước thành 500 ml dung dịch. Tính nồng độ mol",
    "Tính pH của dung dịch HCl nồng độ 0,01 M",
    "Trung hoà 100 ml dung dịch HCl 0,5 M cần bao nhiêu ml dung dịch NaOH 1 M",
    "Cho 5,4 gam Al tác dụng hết với dung dịch HCl. Tính thể tích khí H2 ở điều kiện tiêu chuẩn",
    "Tính thành phần phần trăm khối lượng của oxi trong hợp chất H2O",
    "Đốt cháy hoàn toàn 2,24 lít khí metan ở điều kiện tiêu chuẩn. Tính khối lượng CO2 sinh ra",
    "Viết phương trình phản ứng giữa Na và H2O",
    "Xác định số oxi hoá của lưu huỳnh trong H2SO4",
    "Cân bằng phản ứng oxi hoá khử KMnO4 + HCl tạo KCl, MnCl2, Cl2 và H2O",
    "Cho 200 ml dung dịch AgNO3 1 M tác dụng với NaCl dư. Tính khối lượng kết tủa",
    "Tính nồng độ phần trăm của dung dịch chứa 20 gam muối trong 180 gam nước",
    "Điện phân dung dịch CuSO4 với dòng điện 2 A trong 30 phút. Tính khối lượng Cu bám vào catot",
    "Cho hỗn hợp Fe và Cu vào dung dịch HCl dư. Kim loại nào tan",
    "Tính khối lượng kết tủa khi cho BaCl2 dư vào 100 ml dung dịch Na2SO4 0,2 M",
    "Xác định công thức phân tử của hợp chất hữu cơ chứa 40% C, 6,67% H và còn lại là O",
    "Đốt cháy hoàn toàn ancol etylic. Viết phương trình phản ứng",
    "Cho glucozơ tác dụng với dung dịch AgNO3 trong NH3. Nêu hiện tượng",
    "Tính khối lượng este thu được khi cho 6 gam axit axetic phản ứng hết với ancol etylic",
    "Phân biệt hai dung dịch NaCl và Na2CO3 bằng phương pháp hoá học",
    "Tính thể tích khí CO2 sinh ra khi cho 10 gam CaCO3 tác dụng hết với HCl dư",
    "Sắp xếp các kim loại Na, Fe, Cu theo chiều tăng dần tính khử",
    "Cho m gam Zn tác dụng hết với dung dịch H2SO4 loãng thu 2,24 lít H2. Tính m",
    "Tính khối lượng muối thu được khi cho 4,6 gam Na tác dụng hết với khí Cl2",
    "Nêu hiện tượng khi nhỏ dung dịch NaOH vào dung dịch CuSO4",
    "Tính độ tan của muối khi 36 gam tan tối đa trong 100 gam nước ở 20 độ C",
    "Xác định chất oxi hoá và chất khử trong phản ứng Fe + CuSO4",
    "Tính khối lượng NaCl cần để pha 250 ml dung dịch 0,4 M",
    "Cho 0,1 mol axit HCl phản ứng với 0,15 mol NaOH. Chất nào còn dư",
    "Viết công thức cấu tạo của các đồng phân ứng với công thức C4H10",
    "Tính số nguyên tử oxi có trong 0,5 mol khí O2",
    "Cho hỗn hợp Mg và MgO tác dụng với HCl dư. Tính phần trăm khối lượng mỗi chất",
    "Xác định chất kết tủa khi trộn dung dịch Na2CO3 với dung dịch CaCl2",
    "Tính thể tích khí O2 cần để đốt cháy hoàn toàn 3,2 gam khí metan",
    "Cho biết loại liên kết hoá học trong phân tử NaCl",
    "Tính nồng độ mol của ion H+ trong dung dịch có pH bằng 3",
    "Nêu ứng dụng của phản ứng lên men rượu từ glucozơ",
    "Cho 11,2 gam Fe vào dung dịch CuSO4 dư. Tính khối lượng Cu sinh ra",
    "Xác định nguyên tố có cấu hình electron 1s2 2s2 2p6 3s1",
    "Tính khối lượng phân tử trung bình của hỗn hợp khí gồm N2 và O2 tỉ lệ mol 1:1",
    "Viết phương trình nhiệt phân KClO3 có xúc tác MnO2",
    "Tính hiệu suất phản ứng khi thu được 8 gam sản phẩm so với lý thuyết 10 gam",
]

# ---------------------------------------------------------------------------
# TẬP KHÓ — không có từ khoá đặc trưng, hoặc lai môn
# ---------------------------------------------------------------------------
#
# Đây là tập quyết định giá trị khoa học của phần học sâu. Router bằng luật từ
# khoá sẽ sai nhiều ở đây, vì:
#   * câu không chứa từ khoá nào của môn đúng ("Tính giá trị của biểu thức...")
#   * câu chứa từ khoá của môn KHÁC ("nồng độ" là từ Hoá nhưng bài lại hỏi pH
#     theo phương pháp điện hoá thuộc Lý, hoặc ngược lại)
#   * câu dùng chung thuật ngữ liên môn: "năng lượng", "khối lượng", "tỉ lệ"

HARD_MATH = [
    "Tính giá trị của biểu thức khi thay x bằng 2",
    "Cho biết mối liên hệ giữa hai đại lượng tỉ lệ nghịch với nhau",
    "Một người gửi 100 triệu với lãi suất 6% một năm. Sau 3 năm nhận bao nhiêu",
    "Tìm quy luật của dãy số 2, 6, 12, 20, 30",
    "Một bể chứa đầy sau 6 giờ nếu mở vòi thứ nhất, 4 giờ nếu mở vòi thứ hai. Mở cả hai thì bao lâu",
    "Chia 120 cái bánh cho ba nhóm theo tỉ lệ 2 : 3 : 5",
    "Tính chu vi của hình tròn có đường kính 10",
    "Một mảnh vườn hình chữ nhật có chu vi 40 m, chiều dài hơn chiều rộng 4 m. Tính diện tích",
    "Trung bình cộng của năm số là 12. Tổng của chúng bằng bao nhiêu",
    "Xác suất để gieo con xúc xắc được mặt chẵn là bao nhiêu",
    "Có bao nhiêu cách xếp 4 người vào một hàng ghế",
    "Tìm hai số biết tổng bằng 20 và tích bằng 96",
    "Một hình hộp chữ nhật có ba kích thước 2, 3, 4. Tính thể tích",
    "Nếu tăng cạnh hình vuông lên gấp đôi thì diện tích tăng bao nhiêu lần",
    "Tính tổng các số tự nhiên từ 1 đến 100",
]

HARD_PHYSICS = [
    "Một vật nặng 2 kg được kéo lên đều theo phương thẳng đứng 3 m. Tính công tối thiểu",
    "Giải thích vì sao khi đi thang máy đi lên nhanh dần ta cảm thấy nặng hơn",
    "Tính thời gian âm truyền hết 1 km trong không khí",
    "Vì sao mùa hè mặc áo màu sáng mát hơn áo màu tối",
    "Một bóng đèn ghi 220V - 100W. Tính điện trở của đèn khi sáng bình thường",
    "Tại sao khi thả một vật vào nước thì vật nhẹ hơn khi cân trong không khí",
    "Tính năng lượng cần để nâng một thùng hàng 50 kg lên độ cao 2 m",
    "Hai xe khởi hành cùng lúc ngược chiều, sau bao lâu thì gặp nhau",
    "Vì sao tàu thuỷ bằng thép lại nổi được trên mặt nước",
    "Tính khối lượng riêng của vật có khối lượng 270 g và thể tích 100 cm3",
    "Một người đẩy tủ nhưng tủ không dịch chuyển. Công của người đó bằng bao nhiêu",
    "Giải thích hiện tượng cầu vồng xuất hiện sau cơn mưa",
    "Tính tỉ số giữa động năng và thế năng của con lắc tại vị trí li độ bằng nửa biên độ",
    "Vì sao dây dẫn điện thường làm bằng đồng chứ không phải sắt",
    "Một tấm pin mặt trời nhận 1000 W trên mỗi mét vuông. Tính công suất thu được trên 2 mét vuông",
]

HARD_CHEMISTRY = [
    "Vì sao không nên đổ nước vào axit đặc mà phải làm ngược lại",
    "Giải thích tại sao đồ vật bằng sắt để ngoài trời lâu ngày bị gỉ",
    "Tính lượng chất cần dùng để thu được 10 gam sản phẩm với hiệu suất 80%",
    "Vì sao khi mở nắp chai nước ngọt lại thấy có bọt khí thoát ra",
    "Tại sao khi nấu ăn người ta thường cho giấm vào để khử mùi tanh của cá",
    "Một mẫu vật chứa hai thành phần, xác định tỉ lệ khối lượng của chúng",
    "Vì sao vôi sống để lâu trong không khí bị giảm chất lượng",
    "Giải thích hiện tượng nước cứng làm giảm tác dụng của xà phòng",
    "Tính lượng nguyên liệu cần để sản xuất 1 tấn sản phẩm với hao hụt 5%",
    "Vì sao người ta bảo quản kim loại kiềm trong dầu hoả",
    "Tại sao khi đốt than trong phòng kín lại nguy hiểm",
    "Xác định thành phần của một hỗn hợp dựa vào khối lượng trước và sau phản ứng",
    "Vì sao dùng bình chữa cháy CO2 dập được đám cháy thông thường",
    "Giải thích vì sao thức ăn để lâu trong không khí bị ôi thiu",
    "Tính lượng khí thải sinh ra khi đốt cháy hoàn toàn 1 kg nhiên liệu",
]

SEEDS = {
    "math": SEED_MATH,
    "physics": SEED_PHYSICS,
    "chemistry": SEED_CHEMISTRY,
}

HARDS = {
    "math": HARD_MATH,
    "physics": HARD_PHYSICS,
    "chemistry": HARD_CHEMISTRY,
}
