# BÁO CÁO ĐỀ TÀI

# ViMultiAgent — Hệ đa tác tử giải bài tập STEM tiếng Việt chạy hoàn toàn ngoại tuyến

**Lĩnh vực:** Trí tuệ nhân tạo — Hệ đa tác tử (Multi-Agent System) · Mô hình ngôn ngữ lớn · Suy luận thần kinh–ký hiệu (neural-symbolic)

**Phạm vi chuyên môn:** Toán · Vật lý · Hoá học bậc Trung học phổ thông

---

## TÓM TẮT

Báo cáo trình bày ViMultiAgent — hệ thống đa tác tử giải bài tập STEM bằng tiếng Việt,
xây dựng trên khung AutoGen với mô hình ngôn ngữ mã nguồn mở Qwen3:4b chạy cục bộ qua
Ollama, **không sử dụng bất kỳ khoá API của dịch vụ bên ngoài nào**.

Điểm khác biệt của hệ thống không nằm ở việc gọi một mô hình ngôn ngữ để sinh lời giải —
điều bất kỳ ứng dụng nào cũng làm được — mà nằm ở **kiến trúc kiểm chứng**: tám tác tử
chuyên biệt hoá vai trò, một tầng kiểm chứng tất định (SymPy, cân bằng nguyên tố, khối
lượng mol, kiểm thứ nguyên) không tiêu tốn token và không phụ thuộc mô hình, cùng một
tác tử tính lại độc lập chạy song song để đối chiếu chéo. Nguyên tắc xuyên suốt được
phát biểu ngắn gọn:

> **LLM quyết định LÀM GÌ, công cụ quyết định KẾT QUẢ LÀ BAO NHIÊU.**

Hệ thống được đánh giá trên **600 bài toán** thuộc ba bộ đề rời hẳn nhau, trong đó có
một **bộ giữ riêng (held-out) 150 bài chưa từng được dùng để sửa bất cứ thành phần nào**
của hệ thống. Kết quả trên bộ giữ riêng: độ chính xác **78,7% ± 6,6** (ngưỡng đăng ký
≥ 75%), **150/150 lượt dưới 45 giây** với thời gian trung bình 30,4 giây (ngưỡng ≤ 45 s).
Trên toàn bộ 600 bài của cả ba bộ đề: **600/600 lượt dưới 45 giây**, không một ngoại lệ.
Chỉ số tỉ lệ phát hiện lời giải sai đạt 53,1%, **chưa đạt** ngưỡng 85% — nguyên nhân đã
được truy vết và trình bày công khai ở Chương 4.

**Từ khoá:** hệ đa tác tử, chuyên biệt hoá vai trò, mô hình ngôn ngữ cục bộ, suy luận
thần kinh–ký hiệu, tự kiểm chứng, PhoBERT, SymPy, giáo dục STEM.

---

## MỤC LỤC

- **Chương 1.** Giới thiệu và đặt vấn đề
- **Chương 2.** Cơ sở lý thuyết và kiến trúc hệ thống
- **Chương 3.** Thiết kế thực nghiệm và bộ dữ liệu đối chứng
- **Chương 4.** Các áp dụng thực tế, quá trình cài đặt và kết quả thực nghiệm
- Tài liệu tham khảo
- Phụ lục

---
---

# CHƯƠNG 1. GIỚI THIỆU VÀ ĐẶT VẤN ĐỀ

## I. Đặt vấn đề

Giải bài tập là hoạt động chiếm phần lớn thời gian tự học của học sinh phổ thông, đặc biệt
ở nhóm môn STEM (Toán – Vật lý – Hoá học), nơi người học thường bế tắc ở một bước cụ thể
chứ không phải ở toàn bộ bài toán. Sự bùng nổ của các mô hình ngôn ngữ lớn (Large Language
Models – LLM) trong vài năm gần đây đã mở ra triển vọng về một "gia sư ảo" sẵn sàng
24/7: đọc hiểu đề bài viết bằng ngôn ngữ tự nhiên, trình bày lời giải từng bước và giảng
lại theo cách người học tiếp nhận được — điều mà các phần mềm giải toán theo luật (rule-based)
thế hệ trước không làm được.

Tuy nhiên, khi đặt một LLM đơn lẻ vào đúng vai trò gia sư, một rào cản mang tính bản chất
bộc lộ ngay: mô hình được huấn luyện để **dự đoán từ tiếp theo** (next-token prediction)
chứ không phải để **tính toán**. Nó chọn hướng giải khá tốt và viết lập luận mạch lạc,
nhưng con số cụ thể thì không đáng tin — hiện tượng thường được gọi là ảo giác số học
(arithmetic hallucination). Ví dụ ghi nhận được từ chính hệ thống của đề tài này: trên bài
toán đốt cháy 4,6 gam Na trong O₂ dư, mô hình lập luận đúng qua ba bước rồi viết
`0,1 × 62 = 3,8` — trong khi kết quả đúng là 6,2. Một phép nhân sai làm hỏng toàn bộ đáp
số, nhưng **lời văn bao quanh con số sai đó vẫn hoàn toàn trôi chảy và tự tin**.

Nghiêm trọng hơn là sự vắng mặt của cơ chế tự kiểm chứng (self-verification). Một lời gọi
API đơn lẻ chỉ trả về một chuỗi văn bản; không có tín hiệu nào cho biết mô hình đã đối
chiếu lại chưa, hay bước nào là chỗ yếu. Đúng và sai được trình bày với cùng một giọng
tự tin như nhau. Trong bối cảnh giáo dục, hệ quả là nguy cơ sư phạm ngược: **người học ở
đúng trình độ cần dùng công cụ này lại chính là người không đủ năng lực phát hiện ra lỗi
của nó**.

Ở bình diện triển khai, các dịch vụ LLM thương mại còn đặt ra ràng buộc về khoá API, chi
phí theo lượt gọi, kết nối Internet ổn định và việc dữ liệu bài làm của học sinh phải rời
khỏi máy. Với phòng máy trường phổ thông Việt Nam — dùng chung, ngân sách hạn chế, mạng
không phải lúc nào cũng sẵn — đây là nút thắt cổ chai khiến giải pháp khó đi vào sử dụng
thật.

Gần đây, hướng tiếp cận hệ đa tác tử (Multi-Agent Systems) dựa trên LLM, tiêu biểu là
AutoGen (Wu và cộng sự, 2023) và MetaGPT (Hong và cộng sự, ICLR 2024), đã mang lại một
bước chuyển đáng chú ý: thay vì một tác tử vạn năng, hệ thống gồm nhiều tác tử **chuyên
biệt hoá vai trò** (role specialization), mỗi tác tử nhận một prompt hẹp và một nhiệm vụ
duy nhất. Kết hợp với hướng suy luận thần kinh – ký hiệu (neural-symbolic) — giao phần
nhận hiểu ngôn ngữ cho mạng nơ-ron và giao phần tính toán cho hệ đại số hình thức — kiến
trúc này mở ra khả năng để hệ thống **tự phát hiện lỗi của chính nó** bằng những đường
tính toán độc lập, thứ mà một mô hình đơn lẻ về nguyên tắc không thể có.

Mặc dù vậy, cái giá phải trả cho kiến trúc nhiều tác tử là **độ trễ tích luỹ** (cumulative
latency): mỗi vai là một lượt suy luận riêng, chuỗi năm đến sáu vai nối tiếp dễ dàng đẩy
thời gian phản hồi vượt ngưỡng chịu đựng của người dùng tương tác. Ràng buộc này càng gắt
khi hệ thống buộc phải chạy hoàn toàn cục bộ trên phần cứng phổ thông: mô hình đủ nhỏ để
nằm trọn trong bộ nhớ GPU 4–6 GB lại là mô hình có năng lực suy luận hạn chế, tạo nên một
sự đánh đổi trực tiếp giữa độ chính xác và độ trễ (accuracy–latency trade-off). Siết thời
gian thì mất độ chính xác; thêm tầng kiểm chứng thì vỡ ngân sách thời gian.

Thực trạng này đặt ra một bài toán cấp thiết: **làm thế nào để một hệ thống chạy hoàn toàn
ngoại tuyến trên máy phổ thông vẫn có khả năng tự kiểm chứng lời giải của chính nó, mà
không phá vỡ yêu cầu phản hồi thời gian thực?** Từ bối cảnh trên, đề tài *"ViMultiAgent —
Hệ đa tác tử giải bài tập STEM tiếng Việt chạy hoàn toàn ngoại tuyến"* được thực hiện.
Nghiên cứu không dừng lại ở việc ghép nối các tác tử theo một luồng tuần tự, mà đề xuất
một **kiến trúc kiểm chứng hai đường độc lập chạy song song**: bài toán được giải đồng
thời bởi tác tử chuyên môn (LLM suy luận) và bộ tính lại độc lập (LLM trích cấu trúc,
SymPy tự giải), rồi đối chiếu chéo qua một tầng kiểm chứng tất định không tiêu tốn token
và không phụ thuộc mô hình.

## II. Mục tiêu nghiên cứu

Mục tiêu tổng quát của đề tài là xây dựng và **lượng hoá** năng lực, giới hạn cùng sự đánh
đổi của một hệ đa tác tử giải bài tập STEM tiếng Việt vận hành hoàn toàn cục bộ, từ đó xác
định kiến trúc phối hợp tối ưu giữa mô hình ngôn ngữ và công cụ tính toán tất định.

Mục tiêu cụ thể bao gồm:

- **Nghiên cứu cơ sở lý thuyết:** phân tích kiến trúc chuyên biệt hoá vai trò của các khung
  đa tác tử tiêu biểu (AutoGen, MetaGPT), cơ chế ràng buộc đầu ra theo lược đồ (structured
  output) và nguyên lý suy luận thần kinh – ký hiệu.
- **Xây dựng hệ thống hoàn chỉnh:** hiện thực hoá tám tác tử chuyên biệt trên nền LLM mã
  nguồn mở chạy cục bộ, kèm tầng kiểm chứng tất định (SymPy, cân bằng nguyên tố, khối lượng
  mol, kiểm thứ nguyên) và một bộ phân loại môn học bằng học sâu do nhóm tự huấn luyện.
- **Khảo sát sự đánh đổi hệ thống (trade-off analysis):** đo độ chính xác, độ trễ end-to-end,
  tỉ lệ phát hiện lời giải sai và tỉ lệ báo oan trên nhiều khối cấu hình khác nhau, nhằm xác
  định điểm vận hành cân bằng giữa chất lượng và thời gian phản hồi.
- **Đánh giá trên bộ dữ liệu đối chứng độc lập:** thiết kế ba bộ đề rời hẳn nhau, trong đó
  có một bộ giữ riêng (held-out) chưa từng dùng để hiệu chỉnh hệ thống, nhằm kiểm chứng
  rằng các cải tiến **tổng quát thật** chứ không phải may đo cho bộ phát triển.

Bốn chỉ số định lượng được đăng ký làm tiêu chí nghiệm thu:

| # | Chỉ số | Ngưỡng đăng ký |
|---|---|---|
| 1 | Độ chính xác trên bài toán STEM cấp THPT tiếng Việt | ≥ 75% |
| 2 | Độ trễ end-to-end của toàn bộ quy trình | ≤ 45 giây |
| 3 | Tỉ lệ phát hiện lời giải sai (solution verification rate) | ≥ 85% |
| 4 | Chất lượng lời giảng do giáo viên chấm (thang Likert 5) | ≥ 4/5 |

## III. Đối tượng và phạm vi nghiên cứu

**Đối tượng nghiên cứu:**

- Kiến trúc hệ đa tác tử theo hướng chuyên biệt hoá vai trò, xây dựng trên khung AutoGen.
- Mô hình ngôn ngữ mã nguồn mở chạy cục bộ (Qwen3:4b, lượng tử hoá Q4_K_M, phục vụ qua Ollama).
- Mô hình học sâu phân loại văn bản tiếng Việt (PhoBERT fine-tune) trong vai trò định tuyến.
- Tầng kiểm chứng tất định dựa trên hệ đại số hình thức (SymPy, Pint) và bộ công cụ hoá học
  tự phát triển.

**Phạm vi nghiên cứu:**

- *Về mặt nội dung:* giới hạn ở ba môn Toán, Vật lý, Hoá học bậc THPT, phủ bốn mức độ nhận
  thức Nhận biết – Thông hiểu – Vận dụng – Vận dụng cao, với hai dạng câu hỏi là tự luận có
  đáp số và trắc nghiệm bốn phương án. Đầu vào là văn bản tiếng Việt, tối đa 4000 ký tự mỗi
  lượt hỏi. Đề tài **không** xử lý đề bài dạng ảnh chụp (OCR), bài cần dựng hình, và bài có
  nhiều ý a, b, c trong cùng một lượt.
- *Về mặt thực nghiệm:* toàn bộ phép đo thực hiện trên 600 bài toán thuộc ba bộ đề rời nhau
  (150 bài phát triển, 150 bài giữ riêng, 300 bài khó), chạy trên một máy trạm phổ thông
  trang bị GPU 6 GB VRAM. Hệ thống bị ràng buộc chạy **hoàn toàn ngoại tuyến**: không sử
  dụng khoá API của bất kỳ dịch vụ bên ngoài nào, kể cả các dịch vụ tính toán như
  WolframAlpha. Ngân sách thời gian cho một lượt hỏi được cố định ở mức 45 giây.

## IV. Phương pháp nghiên cứu

Để giải quyết các mục tiêu đã đề ra, đề tài kết hợp ba nhóm phương pháp:

- **Phương pháp nghiên cứu lý thuyết:** tổng hợp và phân tích các công trình về hệ đa tác
  tử dựa trên LLM, chuyên biệt hoá vai trò và suy luận thần kinh – ký hiệu; đối chiếu các
  lựa chọn kiến trúc khả dĩ trong ràng buộc phần cứng của đề tài.

- **Phương pháp thực nghiệm và đo đạc tự động (empirical analysis):** xây dựng một luồng
  đánh giá hệ thống hoá (`scripts/bench.py`) tự động nạp bộ đề, chạy suy luận qua toàn bộ
  quy trình, ghi lại đáp số, verdict của tầng kiểm chứng, thời gian của từng vai và tổng
  thời gian end-to-end vào tệp CSV. Đáp án chuẩn của bộ đề được sinh từ mẫu tham số hoá và
  **kiểm chứng lại độc lập bằng SymPy**, bảo đảm tính đúng theo kiến tạo thay vì theo niềm
  tin của người soạn đề.

- **Phương pháp phân tích định lượng và đối chứng (quantitative & ablation):** tính độ chính
  xác kèm khoảng tin cậy 95%, tỉ lệ đạt mốc thời gian, tỉ lệ phát hiện sai và tỉ lệ báo oan,
  phân rã theo môn học và theo mức độ nhận thức. Mọi cơ chế cải tiến đều được đặt sau một cờ
  cấu hình bật/tắt được, cho phép thực hiện đối chứng A/B trên cùng bộ đề để xác định đóng
  góp riêng của từng thành phần thay vì suy đoán định tính.

## V. Đóng góp chính và bố cục báo cáo

Đề tài có bốn đóng góp chính: (1) kiến trúc kiểm chứng hai đường độc lập chạy song song,
trong đó bộ tính lại gần như miễn phí về thời gian vì ẩn dưới đường găng của tác tử chính;
(2) tầng kiểm chứng tất định không tiêu tốn token, với nguyên tắc *một phép kiểm tất định
thất bại là FAIL bất kể mô hình nói gì*; (3) cơ chế định tuyến ba tầng dùng mô hình học sâu
tự huấn luyện, thay thế một lượt gọi LLM tốn 2–4 giây bằng một phép suy luận 50 mili giây;
và (4) một phương pháp đánh giá có bộ giữ riêng, cho phép tái lập toàn bộ số liệu trong báo
cáo.

Phần còn lại của báo cáo được tổ chức như sau. **Chương 2** trình bày cơ sở lý thuyết và
kiến trúc hệ thống ở mức chi tiết đủ để dựng lại. **Chương 3** trình bày thiết kế thực
nghiệm: ba loại dữ liệu, ba bộ đề đối chứng, giao thức đo và các mối đe doạ tới tính hợp lệ
của phép đo. **Chương 4** trình bày các áp dụng thực tế, quá trình cài đặt và toàn bộ kết
quả thực nghiệm, kèm bàn luận và hạn chế.

---
---

# CHƯƠNG 2. CƠ SỞ LÝ THUYẾT VÀ KIẾN TRÚC HỆ THỐNG

## 2.1. Cơ sở lý thuyết

### 2.1.1. Hệ đa tác tử dựa trên mô hình ngôn ngữ

Một *tác tử* (agent) dựa trên LLM là một thực thể phần mềm gồm ba thành phần: một mô hình
ngôn ngữ nền, một chỉ dẫn vai trò (system prompt) xác định nó là ai và làm gì, và một tập
công cụ nó được phép gọi. *Hệ đa tác tử* (multi-agent system) là tập hợp nhiều tác tử như
vậy phối hợp để hoàn thành một nhiệm vụ mà một tác tử đơn lẻ làm không tốt.

Hai công trình nền tảng định hình hướng tiếp cận của đề tài:

- **AutoGen** (Wu và cộng sự, 2023) cung cấp khung lập trình cho hội thoại giữa nhiều tác
  tử, với cơ chế ràng buộc đầu ra theo lược đồ dữ liệu. Đề tài **sử dụng trực tiếp** thư
  viện này (`autogen-agentchat`, `autogen-ext[ollama]`) làm lớp vỏ chung cho các tác tử.

- **MetaGPT** (Hong và cộng sự, ICLR 2024) đề xuất tư tưởng **chuyên biệt hoá vai trò**
  (*role specialization*): thay vì một tác tử vạn năng, hệ thống gồm nhiều tác tử mỗi tác
  tử đảm nhiệm đúng một vai với quy trình làm việc chuẩn hoá. Đề tài **kế thừa tư tưởng
  này, không sử dụng mã nguồn của MetaGPT**.

Cơ sở của chuyên biệt hoá vai trò: một prompt hẹp và một nhiệm vụ duy nhất cho chất lượng
đầu ra cao hơn một prompt rộng bao trùm nhiều nhiệm vụ, đặc biệt với các mô hình quy mô
nhỏ. Với mô hình 4 tỉ tham số như trong đề tài, khác biệt này là quyết định: cùng một mô
hình nền, đặt vào vai "giáo viên Hoá THPT chỉ giải Hoá" cho kết quả khác hẳn khi đặt vào
vai "trợ lý vạn năng".

### 2.1.2. Mô hình ngôn ngữ mã nguồn mở chạy cục bộ

Đề tài dùng **Qwen3:4b** — mô hình 4 tỉ tham số, đã lượng tử hoá ở mức Q4_K_M, dung lượng
2,5 GB — phục vụ qua **Ollama**, một máy chủ suy luận cục bộ cung cấp giao diện HTTP tại
`http://localhost:11434`.

Kiến trúc này có ba hệ quả quan trọng:

1. Chương trình **không đọc trực tiếp file trọng số**. Nó gọi HTTP. Trọng số nằm ở
   `C:\Users\<user>\.ollama\models`, ngoài thư mục dự án.
2. Đổi mô hình chỉ là đổi một biến môi trường, không phải sửa mã nguồn.
3. Vì giao tiếp qua HTTP, máy chạy Ollama có thể tách khỏi máy chạy giao diện.

**Vì sao chọn 4b chứ không lớn hơn.** Đo trên máy phát triển (RTX 3060 Laptop 6 GB VRAM):

| Mô hình | Dung lượng | Tỉ lệ nằm trong GPU | Tốc độ sinh | Toàn luồng |
|---|---|---|---|---|
| qwen3:8b | 6,0 GB | 73% (27% tràn xuống CPU) | 16,3 token/s | ~80 giây |
| **qwen3:4b** | **3,2 GB** | **100%** | **74,1 token/s** | **~22 giây** |

Với mốc 45 giây của đề tài, 4b là lựa chọn duy nhất khả thi trên phần cứng này. Phương án
trộn hai mô hình (8b cho tác tử giải, 4b cho các tác tử còn lại) cũng đã loại: tổng 9,2 GB
vượt 6 GB VRAM, Ollama phải hoán đổi mô hình mỗi lần đổi vai, mỗi lần tốn ~10 giây; luồng
có 4 lần đổi vai nên mất trắng ~40 giây chỉ để nạp mô hình.

### 2.1.3. Suy luận thần kinh–ký hiệu (neural-symbolic)

Đây là nền tảng lý thuyết của toàn bộ tầng kiểm chứng. Ý tưởng: kết hợp **thành phần thần
kinh** (mạng nơ-ron / LLM — mạnh ở nhận dạng mẫu, hiểu ngôn ngữ tự nhiên, chọn hướng giải)
với **thành phần ký hiệu** (hệ tính toán hình thức — bảo đảm tính đúng đắn, kết quả tất
định, lặp lại được).

Đề tài cụ thể hoá nguyên tắc này thành một câu quy tắc áp dụng ở mọi tầng:

> **LLM quyết định LÀM GÌ, công cụ quyết định KẾT QUẢ LÀ BAO NHIÊU.**

Các thành phần ký hiệu được sử dụng:

| Thư viện | Vai trò trong hệ thống |
|---|---|
| **SymPy** | Tính đạo hàm, tích phân, giới hạn, giải phương trình, rút gọn tượng trưng, thế nghiệm ngược |
| **Pint** | Kiểm tính nhất quán thứ nguyên của đáp số vật lý |
| `chem_tool` (tự viết) | Tính khối lượng mol từ công thức hoá học; cân bằng phương trình phản ứng |

`chem_tool` không phụ thuộc thư viện ngoài. Bộ cân bằng phương trình giải bằng cách tìm
**không gian null của ma trận nguyên tố**: mỗi nguyên tố là một phương trình bảo toàn, mỗi
chất là một ẩn hệ số; nghiệm nguyên nhỏ nhất của hệ thuần nhất chính là bộ hệ số cân bằng.
Bộ tính khối lượng mol đọc được công thức có ngoặc lồng nhau và muối ngậm nước
(`CuSO4.5H2O`).

### 2.1.4. Phân loại văn bản tiếng Việt bằng PhoBERT

**PhoBERT** (`vinai/phobert-base`, 135 triệu tham số) là mô hình ngôn ngữ dạng
Transformer encoder được tiền huấn luyện trên khối văn bản tiếng Việt lớn. Đây là **phần
học sâu do nhóm tự huấn luyện** trong đề tài: fine-tune cho bài toán phân loại ba lớp
(Toán / Vật lý / Hoá học) để định tuyến câu hỏi.

Một ràng buộc kỹ thuật bắt buộc: PhoBERT được tiền huấn luyện trên văn bản đã **tách từ**
(word segmentation), nên đầu vào lúc suy luận cũng phải qua bước tách từ tương ứng. Đề tài
dùng `underthesea` cho bước này (`ml/segment.py`). Bỏ bước này thì phân bố token đầu vào
lệch hẳn khỏi phân bố lúc tiền huấn luyện và độ chính xác sụt.

Cần phân biệt rạch ròi hai mô hình học sâu trong hệ thống, vì đây là điểm dễ hiểu nhầm
nhất của đề tài:

| | **Qwen3:4b** | **PhoBERT** |
|---|---|---|
| Nhóm có huấn luyện không | **Không** — chỉ dùng suy luận | **Có** — nhóm tự fine-tune |
| Quy mô | 4 tỉ tham số | 135 triệu tham số |
| Cách kết nối | HTTP API tới Ollama | Nạp trọng số vào RAM tiến trình backend |
| Nhiệm vụ | Sinh lời giải, sinh lời giảng, trích cấu trúc | Phân loại môn học ở Router |
| Thời gian huấn luyện | Không có | ~12 phút trên CPU |

**Vì sao không fine-tune Qwen3.** Đây là quyết định có cân nhắc, không phải bỏ sót.
Fine-tune một mô hình 4 tỉ tham số cần GPU từ 24 GB VRAM trở lên cùng nhiều giờ chạy, vượt
xa điều kiện phần cứng của đề tài. Quan trọng hơn, nó **không cần thiết** để đạt mục tiêu:
chất lượng lời giải được nâng bằng bốn cơ chế khác, mỗi cơ chế đều đo được hiệu quả riêng
— chuyên biệt hoá vai, memory pool, tầng kiểm chứng tất định, và tác tử tính lại độc lập.

### 2.1.5. Ràng buộc đầu ra theo lược đồ (structured output)

Mọi tác tử trong hệ thống (trừ tác tử giảng bài) đều khai báo một lớp Pydantic làm kiểu
đầu ra. AutoGen chuyển lược đồ này xuống Ollama dưới dạng **grammar JSON**, khiến mô hình
về mặt kỹ thuật **không thể** sinh ra đầu ra sai cấu trúc.

Đây là cơ chế mạnh hơn mọi lời dặn trong prompt. Ví dụ cụ thể: ràng buộc `min_length=1`
trên trường `Solution.steps` khiến mô hình không thể trả về mảng bước giải rỗng. Trước khi
có ràng buộc này, mô hình từng buột ra một đáp số với `steps` rỗng và `confidence` = 1.0 —
khi đó toàn bộ tầng kiểm chứng phía sau mất tác dụng vì không có bước nào để kiểm.

## 2.2. Kiến trúc tổng thể

### 2.2.1. Sơ đồ luồng xử lý

```
Người dùng
    │
    ▼
 Planner ──────► phân tích đề, tách dữ kiện và ẩn cần tìm
    │
    ▼
 Router ───────► chọn môn: PhoBERT → luật từ khoá → LLM
    │
    ├──────────────────────────────┐
    ▼                              ▼
 Subject Agent              Bộ tính lại độc lập
 (Toán/Lý/Hoá)              (chạy SONG SONG)
    │                              │
    ▼                              │
 Trọng tài SymPy                   │
 (ghi đè số sai)                   │
    │                              │
    ▼◄─────────────────────────────┘
 Verify ───────► 5 phép kiểm tất định + LLM soi lại
    │
    ▼
 Chốt đáp án ──► phát sự kiện `dap_an` cho giao diện
    │
    ▼
 Explain ──────► giảng bài, streaming từng chữ
    │
    ▼
 (xong — đồng hồ đo độ trễ dừng ở đây)

    ┈┈┈┈┈ NGOÀI luồng đo, do người dùng bấm nút ┈┈┈┈┈
    ▼
 Sinh bài tương tự ──► POST /api/bai_tuong_tu, không gọi LLM, ~43 ms
```

Ba đặc điểm kiến trúc cần nhấn mạnh:

1. **Nhánh đôi ở giữa.** Subject Agent và bộ tính lại độc lập giải cùng một bài bằng hai
   đường khác nhau, chạy song song. Đây là nguồn gốc của năng lực tự kiểm chứng.
2. **Trọng tài SymPy đứng trước Verify.** Mọi con số quy được về số thuần được sửa trước
   khi bước kiểm chứng bắt đầu, nên Verify chỉ còn phải lo phần lập luận.
3. **"Chốt đáp án" nằm trước Explain.** Đáp số hiện ra trên giao diện sớm hơn khoảng
   11,6 giây so với thời điểm lời giảng chảy xong.

### 2.2.2. Manager — bộ điều phối

`agents/manager.py` là một **async generator**: nó phát sự kiện ra ngoài ngay khi từng tác
tử xong việc, thay vì chờ trọn gói rồi mới trả. Nhờ vậy giao diện vẽ được tiến trình theo
thời gian thực.

Manager chịu hai trách nhiệm mà không tác tử nào lo:

- **Ngân sách thời gian.** Trước mỗi bước tốn kém, Manager kiểm tra thời gian còn lại;
  hết ngân sách thì bỏ bước tinh chỉnh và đi thẳng tới Explain. Riêng bước giảng bài bị
  chặn cứng bằng `asyncio.timeout` — kiểm tra hạn giữa các mẩu văn bản là chưa đủ, vì nếu
  mô hình chậm ra token đầu tiên thì vòng lặp nằm chờ và trôi qua mốc.
- **Vòng sửa sai.** Verify báo FAIL thì Subject Agent giải lại kèm phản hồi, tối đa
  `MAX_RETRY_ROUNDS` lần (mặc định tắt — xem Mục 4.4.9).

### 2.2.3. Ngăn xếp công nghệ

| Thành phần | Công nghệ |
|---|---|
| Khung đa tác tử | AutoGen (`autogen-agentchat`, `autogen-ext[ollama]`) |
| Mô hình ngôn ngữ | Qwen3:4b qua Ollama, chạy cục bộ |
| Phân loại môn học | PhoBERT fine-tune (nhóm tự huấn luyện) |
| Tính toán tất định | SymPy, Pint, `chem_tool` tự viết |
| Backend | FastAPI + Server-Sent Events (SSE) |
| Frontend | React + TypeScript + Vite + KaTeX |
| Lưu trữ | SQLite |

Backend chạy ở cổng 8000, frontend ở cổng 5173. Giao tiếp giữa hai phần dùng **SSE** chứ
không phải một lời gọi JSON trọn gói: một lượt chạy mất 20–45 giây, và bắt người dùng chờ
trắng màn hình suốt thời gian đó thì sản phẩm coi như hỏng, dù đáp án có đúng.

## 2.3. Tám tác tử

Bản yêu cầu đề tài đòi năm vai: phân tích đề · giải chuyên ngành · kiểm tra · giải thích ·
sinh bài tương tự. Hệ thống có đủ cả năm, cộng thêm hai vai nhóm tự thêm — **Router** và
**bộ tính lại độc lập** — là nơi phần lớn độ tin cậy đến từ đó. Ba Subject Agent tính là
một vai.

| # | Tác tử | Tệp nguồn | Có gọi LLM | Vai trò |
|---|---|---|---|---|
| 1 | Planner | `agents/planner.py` | có | Đọc hiểu đề, tách dữ kiện và ẩn |
| 2 | Router | `agents/router.py` | hiếm khi | Chọn môn học |
| 3–5 | Math / Physics / Chemistry Agent | `agents/subject.py` | có | Giải bài theo môn |
| 6 | Recompute | `agents/recompute_agent.py` | có (chỉ trích cấu trúc) | Giải lại độc lập bằng SymPy |
| 7 | Verify | `agents/verify_agent.py` | có điều kiện | Kiểm chứng lời giải |
| 8 | Explain | `agents/explain_agent.py` | có (streaming) | Giảng lại lời giải |
| + | Sinh bài tương tự | `agents/sinh_bai_tuong_tu.py` | **không** | Sinh đề luyện cùng dạng |

### 2.3.1. Planner Agent

Đọc hiểu đề bài và **không giải**. Trả về một đối tượng `Plan` gồm: `subject`, `topic`,
`question_type`, `givens` (dữ kiện), `unknowns` (ẩn cần tìm), `choices` (phương án trắc
nghiệm), `normalized_question` (đề đã chuẩn hoá), `steps_outline` (dàn ý các bước) và
`confidence`.

**Chốt chặn `_giu_nguyen_so_lieu()`.** Bản chuẩn hoá chỉ được chấp nhận khi dãy chữ số
trong đó khớp tuyệt đối với đề gốc. Lý do rút từ lỗi đo được: qwen3:4b chép
`x = 5cos(10πt)` thành `x = 5cos(1:0πt)` và `R = 110 Ω` thành `R = 1:110 Ω`. JSON trả về
hoàn chỉnh, `done_reason` là `"stop"` — mô hình thật sự viết sai chứ không phải bị cắt.
Hậu quả rất nặng: mọi tác tử phía sau giải **rất đúng trên một đề đã hỏng**, và không tầng
kiểm chứng nào phát hiện được vì tất cả đều đối chiếu với đề đã sai.

**Trần token 400, không được hạ xuống 250.** Đo trên cùng 20 bài: 400 token cho 18/20
đúng, 250 token chỉ 13/20 — mất 5 bài để đổi lấy 2,6 giây. Subject Agent nhanh lên không
phải vì nó giỏi hơn mà vì nó nhận được ít thông tin hơn. Ở mức vận dụng cao, tỉ lệ đúng
tụt từ 2/2 xuống 0/2. **Chất lượng đọc đề quyết định mọi thứ phía sau**; đây là chỗ tiết
kiệm token đắt nhất trong cả luồng.

### 2.3.2. Router Agent — định tuyến ba tầng

Router chọn Subject Agent theo ba tầng, rẻ trước đắt sau, dừng ở tầng đầu tiên đủ chắc:

```
PhoBERT (~50 ms)  →  luật từ khoá (0 ms)  →  LLM (2–4 giây)
```

Đo trên 150 bài: **PhoBERT quyết định 94,7% số bài**, luật từ khoá 2,7%, LLM 2,7%. Thời
gian trung bình của cả vai: **0,05 giây**.

**PhoBERT chỉ được chốt khi luật từ khoá không phản đối**, và ngưỡng tin cậy đặt ở 0,85.
Lý do rút từ lỗi thật: câu xác suất bốc bi bị PhoBERT xếp vào Vật lý với độ tin cậy 0,90;
câu dao động điều hoà bị xếp vào Toán với 0,86. **Độ tin cậy cao mà vẫn sai**, nên nâng
ngưỡng là vô ích. Nguyên nhân là lệch phân bố: dữ liệu huấn luyện gồm câu ngắn, còn đề
vận dụng thì dài, nhiều mệnh đề. Luật từ khoá thì ngược lại — câu càng dài càng nhiều từ
khoá nên càng chắc. Hai nguồn bù khuyết cho nhau; khi bất đồng thì đẩy xuống tầng LLM.

Thiết kế này còn có một tính chất vận hành quan trọng: **chưa huấn luyện PhoBERT thì hệ
thống vẫn chạy đầy đủ**, chỉ lùi về luật từ khoá. Hàm `classifier.available()` trả về
`False` và Router bỏ qua tầng một, không văng lỗi.

### 2.3.3. Ba Subject Agent

Toán, Lý, Hoá dùng chung khung `agents/subject.py`, khác nhau ở system prompt. Đây chính
là hiện thực của **role specialization**: cùng mô hình nền, khác vai trò và khác kỷ luật
chuyên môn. Thêm một môn mới chỉ tốn một file prompt, không phải sửa luồng.

Đầu ra là đối tượng `Solution` gồm danh sách các bước (`steps`, mỗi bước có `expression`
và `result`), đáp số cuối (`final_answer`), bản LaTeX của đáp số, phương án trắc nghiệm
nếu có, và `confidence`.

### 2.3.4. Bộ tính lại độc lập (Recompute Agent)

Chạy **song song** với Subject Agent bằng `asyncio.gather`. Đây là vai được cải tổ lớn
nhất trong quá trình phát triển, và là ví dụ điển hình cho nguyên tắc thiết kế của đề tài.

| | **Kiến trúc cũ** | **Kiến trúc hiện tại** |
|---|---|---|
| Cách làm | Bắt mô hình vừa suy luận vừa cho ra biểu thức đã thay số | Tách đôi: LLM trích cấu trúc → SymPy tự giải |
| Thời gian | **42,4 giây** | **5,1 giây** |
| Tỉ lệ dùng được | ~16% số bài | ẩn hoàn toàn dưới Subject Agent (8,6 s) |
| Bản chất kết luận | phỏng đoán của mô hình | tất định |

Ở kiến trúc hiện tại, mô hình chỉ phải **chép lại đề dưới dạng máy đọc được** — loại bài,
hàm gốc, biến, cận — việc nó làm tốt. Toàn bộ phần tính toán (lấy đạo hàm, tính tích phân,
thế nghiệm) giao cho SymPy, việc SymPy không bao giờ sai.

**Hai chốt chặn bắt buộc:**

1. **`_loai_kiem_hop_le()`** — loại bài mà mô hình khai báo phải khớp với từ khoá trong đề
   gốc. Đo được: 33/34 ca báo oan là do mô hình gán nhầm loại bài. Điển hình là đề *"Cho
   f(x) = 3x² + 5x − 1, tính f(3)"* bị gán nhãn `dao_ham`; SymPy tính đạo hàm tại 3 ra 23
   trong khi đáp án đúng là giá trị hàm số 41, rồi kết luận lời giải sai.

2. **`_con_ky_hieu_tu_do()`** — nếu đề hỏi một con số mà kết quả tính lại còn chứa ký hiệu
   tự do thì coi như chưa tính xong. Trước khi có chốt này, cơ chế cứu đáp án đã lấy
   nguyên hàm chưa thay cận (`x*(3x+4)`) đè lên đáp số **đúng**, làm hỏng 6 bài trên 150.

### 2.3.5. Verify Agent

Nguyên tắc: **không tin LLM**. Verify chạy toàn bộ các phép kiểm tất định trước, rồi mới
đưa kết quả cho LLM đọc. Làm ngược lại thì mô hình 4B bị lập luận trôi chảy cuốn theo và
"đồng ý" với lời giải sai.

> **Một phép kiểm tất định thất bại là FAIL, bất kể LLM nói gì.**

Năm phép kiểm tất định:

| Phép kiểm | Áp dụng cho | Cơ chế |
|---|---|---|
| `_check_answer_present` | mọi bài | có bước giải và có đáp số hay không |
| `_check_arithmetic` | mọi bài | SymPy tính lại từng bước **sau khi thế ký hiệu**, ngưỡng lệch 1% |
| `_check_units` | Vật lý | soát thứ nguyên bằng Pint |
| `_check_chemistry` | Hoá | bảo toàn nguyên tố, kèm phương trình cân bằng đúng |
| `_check_khoi_luong_mol` | Hoá | đối chiếu M(chất) với bảng nguyên tử khối |

Cộng thêm một phép kiểm nữa từ bộ tính lại độc lập.

**Đường tắt bỏ qua LLM.** Khi không phép kiểm nào hỏng **và** bộ tính lại đã xác nhận đáp
số, Verify bỏ luôn lượt gọi LLM. Điều kiện thứ hai là mấu chốt: thiếu nó thì "mọi phép
kiểm đều đạt" có thể chỉ có nghĩa là **chẳng phép kiểm nào chạy được**. Đo trên 150 bài:
có 106/150 bài mọi phép kiểm tất định đều sạch; bỏ qua LLM ở đúng những bài đó cắt trung
bình 4,6 giây mỗi lượt.

### 2.3.6. Explain Agent

Ràng buộc cứng: **không được sinh đáp án mới**, chỉ diễn đạt lại lời giải đã chốt.

Đây là tác tử duy nhất chạy streaming, và cũng là tác tử duy nhất **gọi thẳng thư viện
`ollama`** thay vì qua AutoGen — vì cần một thứ AutoGen không cho: **mồi sẵn câu mở đầu**.

Lý do phải mồi, đo được trên cùng một đề với ba cách ép qwen3:4b viết tiếng Việt:

| Cách | Kết quả |
|---|---|
| A. System prompt tiếng Việt, cấm đích danh từ tiếng Anh | **vẫn tiếng Anh** |
| B. Thêm "BẮT BUỘC trả lời bằng TIẾNG VIỆT" ở cuối tin nhắn người dùng | **vẫn tiếng Anh** |
| C. Mồi sẵn `**Tóm tắt đề**\n` vào lượt trả lời của trợ lý | **tiếng Việt** |

Mô hình 4B phớt lờ chỉ dẫn nhưng **không thể phớt lờ văn bản nó đang phải viết tiếp**.
Template của Qwen3 hỗ trợ sẵn: khi tin nhắn cuối cùng đã thuộc vai trợ lý, nó không chèn
thẻ mở lượt mới mà để mô hình viết nối vào.

Trần token đặt **900** chứ không phải 700: đo trên 150 bài, 81/150 lời giảng (54%) chạm
đúng trần 700 token, tức bị cắt giữa chừng. Ở mức 900, tỉ lệ này còn 32%.

### 2.3.7. Tác tử sinh bài tập tương tự

Đây là vai thứ năm theo bản yêu cầu: giải xong một bài thì sinh **một** bài cùng dạng để
người học tự luyện.

**Tác tử này không dùng LLM.** Lý do trực tiếp: mô hình 4B trong dự án này từng tính
`0,1 × 62 = 3,8`; một đề bài do nó bịa ra sẽ mang đúng chất lượng đó. **Đề sai đưa cho học
sinh còn tệ hơn không đưa gì** — người học không có cách nào biết mình sai hay đề sai.

Thay vào đó, tác tử dùng lại **175 mẫu đề tham số hoá** trong thư mục `eval/` — chính bộ
mẫu đã dựng nên 600 bài ground truth. Mỗi mẫu mã hoá sẵn công thức, còn đáp án do Python
tính từ đúng những con số vừa bốc vào đề. **Sai số học là không thể xảy ra về mặt kiến
tạo.**

Đây vẫn là *sinh* chứ không phải *tra cứu*: mỗi lần gọi bốc một bộ tham số mới, nên cùng
một mẫu cho ra vô số đề khác nhau (có kiểm thử chứng minh điều này).

Cách tìm mẫu — tụt dần bốn nấc, dừng ở nấc đầu tiên có kết quả:

1. cùng môn **và** trùng khít `topic`;
2. cùng môn và `topic` chứa nhau;
3. cùng môn và cùng mức độ;
4. cùng môn.

Không có mẫu nào thì **trả `None`**, không bịa — giống mọi tầng tất định khác trong hệ
thống.

Một chi tiết kỹ thuật đáng ghi: so `topic` phải **bỏ dấu trước**, vì Planner sinh
`khối_lượng_mol` trong khi mẫu ghi `khoi_luong_mol`. Đã có lần việc chấm điểm chủ đề không
bao giờ khớp chỉ vì thiếu bước này, nên có kiểm thử riêng chốt lại.

| Đặc trưng | Giá trị |
|---|---|
| Số mẫu | 175 (61 Toán · 57 Lý · 57 Hoá) |
| Thời gian đáp ứng | **43 ms** (gồm cả lần nạp kho đầu tiên) |
| Số lượt gọi LLM | **0** |
| Bảo đảm đáp án | tính bằng công thức; có kiểm thử soát toàn bộ 175 mẫu bằng SymPy |

Giao diện giấu đáp án sau một nút bấm, kèm nút "Gợi ý" chỉ đưa công thức cần dùng — hiện
sẵn đáp số thì bài luyện mất hết tác dụng sư phạm.

## 2.4. Tầng kiểm chứng tất định

Bốn module trong `tools/`, tổng 32 hàm, khoảng 1100 dòng mã. Điểm chung: **không tốn token
nào**, và kết luận không phụ thuộc mô hình.

### 2.4.1. `sympy_tool.py`

Bộ phân tích biểu thức chịu được LaTeX "bẩn" mà mô hình hay sinh ra. Hàm quan trọng nhất
là `check_substitution` — thế nghiệm ngược vào phương trình gốc để kiểm tra.

### 2.4.2. `arbiter.py` — trọng tài số học

Với mỗi bước giải, nếu vế phải của trường `expression` quy được về **một số thuần** thì
giá trị đó **ghi đè** lên trường `result` của mô hình. Không xin phép.

Trọng tài chỉ can thiệp khi thoả toàn bộ ba điều kiện: (1) vế phải ra một số, không còn ký
hiệu tự do; (2) `result` cũng đọc ra được một số; (3) hai số lệch **quá 1%**.

Ngưỡng 1% có chủ đích: mô hình làm tròn 0,39738 thành 0,397 là hợp lệ, không nên can
thiệp. Sai số học thật thì lệch hàng chục phần trăm hoặc sai dấu.

### 2.4.3. `chem_tool.py`

Không phụ thuộc thư viện ngoài, tự cài đặt hai năng lực:

- **Khối lượng mol** — bộ phân tích công thức có ngoặc lồng và muối ngậm nước.
- **Cân bằng phương trình** — giải bằng không gian null của ma trận nguyên tố.

Khi mô hình ghi sai hệ số, phản hồi trả về **kèm luôn phương trình đúng** để vòng sau có
căn cứ mà sửa thay vì đoán lần nữa.

Một chi tiết dung sai: sách giáo khoa làm tròn nguyên tử khối (Cu = 64, Zn = 65) còn
`chem_tool` dùng bảng chính xác (63,546 và 65,38). Đo được lệch tối đa 0,71% ở Cu, các hợp
chất thường dưới 0,3%. Ngưỡng dung sai đặt 1,5% — đủ chỗ cho cách làm tròn hợp lệ mà vẫn
bắt được lỗi thật, vì nhớ nhầm sang chất khác thường lệch hàng chục phần trăm.

### 2.4.4. `kiem_symbolic.py`

Cho SymPy **tự giải lại** bài toán. Năm loại bài kiểm được: `dao_ham`, `tich_phan`,
`gioi_han`, `phuong_trinh`, `tiep_tuyen`.

Ba trạng thái trả về, và trạng thái thứ ba là khó nhất về mặt thiết kế:

| Trả về | Nghĩa |
|---|---|
| `True` | SymPy tính lại và khớp đáp án |
| `False` | SymPy tính lại và **khác** đáp án |
| `None` | **không đủ căn cứ — tuyệt đối không đoán** |

Hàm `_khop()` so sánh ba tầng: rút gọn tượng trưng → hiệu quy về số → **thử tại nhiều
điểm**. Tầng thứ ba là chỗ bản đầu tiên còn thiếu, khiến `7x + 1` so với `5x + 5` trả về
"không so sánh được" thay vì "khác nhau" — tức một phương trình tiếp tuyến sai lọt lưới.

### 2.4.5. `units_tool.py`

Kiểm thứ nguyên bằng Pint, có bảng ánh xạ ký hiệu tiếng Việt (`lít`, `gam`, `Ω`) sang đơn
vị chuẩn của thư viện.

### 2.4.6. Thế ký hiệu trong `_check_arithmetic`

Đây là cơ chế đáng ghi lại nhất của dự án về mặt phương pháp, được trình bày đầy đủ như
một ca nghiên cứu ở Mục 4.5. Về mặt kỹ thuật:

Mô hình gần như **luôn** viết vế phải của bước giải bằng công thức chữ (`mNa2O = nNa2O *
MNa2O`) và chỉ để con số ở trường `result`. Nếu đưa thẳng vế phải cho SymPy thì nó gặp
toàn ký hiệu tự do và trả `None`, tức không kiểm được gì.

Bản hiện tại **thế giá trị vào ký hiệu trước khi tính**, lấy từ hai nguồn:

| Nguồn | Ví dụ |
|---|---|
| Vế trái của các bước **trước** | `nNa2O` = 0,1 lấy từ kết quả bước 3 |
| Bảng nguyên tử khối | `MNa2O` → `chem_tool.molar_mass` = 61,98 |

Việc thế thực hiện ở **mức văn bản** chứ không qua SymPy, vì tuỳ chọn
`implicit_multiplication_application` sẽ xé `nNa2O` thành `n*N*a**2*O` và ký hiệu ghép sẽ
không bao giờ khớp bảng tra.

Ba chốt chặn chống báo oan:

- **Thiếu dù một ký hiệu là bỏ qua bước đó.** Thà không kiểm còn hơn kiểm bừa.
- **Lệch đúng một luỹ thừa của 10 thì bỏ qua.** Ca thật phải chặn: bước 1 ghi `A = 6 cm`,
  bước 3 dùng `v = A·ω` với A tính bằng mét — thế thẳng ra 120 trong khi bước ghi 1,2. Lời
  giải đúng, chỉ là ký hiệu đổi đơn vị giữa chừng. Cái giá phải trả là bỏ sót lỗi lệch
  đúng 10 lần; chấp nhận được vì báo oan phá hỏng cả một lời giải đúng, còn bỏ sót chỉ là
  không cải thiện được gì.
- **Báo cáo trung thực.** Dòng kết luận ghi rõ *"Số học khớp ở 2/4 bước thế được số"* hoặc
  *"chưa kiểm được số học"*, không còn khẳng định suông là "số học khớp".

## 2.5. Memory pool

Hai kho, tra cứu bằng từ khoá và trường `Plan.topic`. **Không dùng embedding** — thêm một
mô hình nhúng là thêm vài trăm MB RAM tranh chỗ với Ollama trên máy 6 GB VRAM, trong khi
lợi ích chưa chứng minh được.

### 2.5.1. `kho_dinh_ly.py` — kho định lý

Khoảng 70 mục công thức chương trình THPT, soạn sẵn và cố định. Chấm điểm theo hai nguồn:
`topic` khớp được 3 điểm, mỗi từ khoá trúng được 1 điểm. Lấy tối đa 3 mục; dưới ngưỡng thì
**trả rỗng** — chèn công thức lạc đề vào prompt còn tệ hơn không chèn gì.

So sánh `topic` phải thực hiện **sau khi bỏ dấu**: prompt dặn Planner sinh slug không dấu
nhưng mô hình vẫn trả về `khối_lượng_mol`; so thẳng thì điểm khớp topic không bao giờ kích
hoạt.

### 2.5.2. `kho_loi_giai.py` — kho lời giải mẫu

Một bảng SQLite riêng, **chỉ cất lời giải có verdict PASS và không kèm cảnh báo**. Cất lời
giải sai là tự đầu độc: lần sau nó được lấy ra làm ví dụ mẫu và nhân bản cái sai.

Hai chi tiết phòng thủ: kho **không bao giờ trả về chính câu đang giải** (nếu không, hệ
thống chỉ chép lại đáp án cũ), và mọi lỗi truy cập kho đều bị nuốt để không làm hỏng câu
trả lời.

Đây là thành phần khiến hệ thống về lý thuyết khá dần lên khi được dùng nhiều. Kết quả đo
thực tế được báo cáo trung thực ở Mục 4.4.9: **chưa chứng minh được giá trị**.

## 2.6. Cơ chế cứu đáp án

Nằm ở `manager.py`. Hai tình huống, cùng một nguyên tắc:

1. Subject Agent không ra được đáp số nào (bị cắt token, quá hạn, JSON hỏng);
2. Ra đáp số nhưng **không qua được kiểm chứng**, và công cụ tính ra một số khác.

Cả hai trường hợp đều lấy giá trị của bộ tính lại độc lập, kèm cảnh báo rõ ràng trên giao
diện và hạ `confidence` xuống 0,35–0,4.

> **Lời giải ĐÃ qua kiểm chứng thì tuyệt đối không đụng vào.**

Tình huống 2 là bài học đo được trên môn Hoá: Subject Agent kiên định trả 2,4 gam qua cả
hai vòng, trong khi bộ tính lại ra 7,73 gam — và 7,73 mới đúng. Trước khi có cơ chế này,
hệ thống giữ 2,4 chỉ vì nó đến từ tác tử "chính", tức vứt đi câu trả lời đúng đang cầm
trong tay.

Đo trên 150 bài ở cấu hình hiện tại: cơ chế này **không kích hoạt lần nào**, vì Subject
Agent và bộ tính lại hiếm khi bất đồng sau khi đã có các chốt chặn ở Mục 2.3.4.

## 2.7. Các quyết định kỹ thuật then chốt

Bảng dưới đây tổng hợp những quyết định có ảnh hưởng đo được tới chỉ số, kèm căn cứ.

| Quyết định | Căn cứ đo được |
|---|---|
| **Tắt chế độ suy nghĩ của Qwen3** cho mọi tác tử | Cùng câu hỏi, cùng lược đồ JSON: bật `think` → 24,2 giây (khối suy nghĩ 3273 ký tự); tắt → 5,1 giây. Chuỗi 5 tác tử nối tiếp mà để mặc định thì riêng phần `<think>` đã ăn hết ngân sách 45 giây |
| **Không bật suy nghĩ cho Subject Agent** | Đo được nó làm mọi thứ tệ đi: 1/6 đúng thay vì 3/9, và 5/6 lượt trả lời giải rỗng — khối `<think>` tính chung vào hạn mức `num_predict` nên phần JSON bị cắt cụt |
| **Vá ở tầng thư viện `ollama`, không chọc vào nội bộ AutoGen** | `OllamaChatCompletionClient` không có đường truyền tham số `think` xuống. Bám vào lớp công khai của `ollama` ổn định hơn |
| **Dùng `ContextVar` chứ không phải biến toàn cục** | Các tác tử chạy song song trong cùng một event loop; biến toàn cục sẽ bị lượt này ghi đè lượt kia |
| **Bắt cờ `done_reason` của Ollama** | Không đọc cờ này thì "mô hình bó tay" và "ta cắt ngang mô hình" rơi vào cùng một nhánh xử lý, cùng trả lời giải rỗng, cùng im lặng |
| **Đường cứu JSON bị cắt** (`core/json_cuu.py`) | JSON bị cắt vẫn còn phần đầu hoàn chỉnh; vá lại rồi dựng model, miễn phí về thời gian vì không gọi LLM lần nữa |
| **Hạ `num_ctx` từ 8192 xuống 4096** | Tiết kiệm 400 MB VRAM (3,3 GB → 2,9 GB) mà tốc độ không đổi (30,0 s → 30,5 s). Nhu cầu ngữ cảnh thật chỉ ~1720 token |
| **Phát sự kiện `dap_an` riêng, trước Explain** | Trước đây frontend chỉ nhận đáp án ở sự kiện `done`, tức bắt người dùng chờ thêm **10,6 giây** để đọc một con số đã chốt xong từ trước |
| **Tách endpoint sinh bài tương tự khỏi `/api/solve`** | Gộp vào sẽ cộng thẳng thời gian sinh đề vào chỉ số độ trễ end-to-end đang đo |
| **Chặn cứng Explain bằng `asyncio.timeout`** | Kiểm hạn giữa các mẩu văn bản là chưa đủ: đo được 3/9 lượt vượt trần vì mô hình chậm ra token đầu tiên |

---
---

# CHƯƠNG 3. THIẾT KẾ THỰC NGHIỆM VÀ BỘ DỮ LIỆU ĐỐI CHỨNG

## 3.1. Nguyên tắc thiết kế thực nghiệm

Dự án có **ba loại dữ liệu khác hẳn nhau về bản chất và vai trò**. Trộn lẫn chúng rồi báo
một con số chung là tự lừa mình, nên phần này tách bạch rõ ngay từ đầu:

| Loại | Vị trí | Vai trò | Có dùng để huấn luyện không |
|---|---|---|---|
| Dữ liệu huấn luyện bộ phân loại | `backend/ml/data/` | Fine-tune PhoBERT | **Có** |
| Ba bộ đề đánh giá | `backend/eval/data/` | Đo hiệu năng hệ thống | **Không** |
| Memory pool | `vimultiagent.db` (SQLite) | Dữ liệu vận hành, bơm vào prompt | Không (không phải huấn luyện) |

Ba nguyên tắc xuyên suốt thiết kế thực nghiệm:

1. **Bộ dùng để sửa hệ thống không được dùng để báo cáo kết quả.** Đây là lý do tồn tại
   của bộ giữ riêng.
2. **Đáp án chuẩn phải bảo đảm đúng theo kiến tạo, không phải theo niềm tin.** Đề sinh từ
   mẫu tham số hoá, đáp án do Python tính từ chính tham số đó, rồi còn được SymPy kiểm lại
   một lần nữa.
3. **Phép đo phải đứng yên.** Khi đo, phải tắt việc ghi kho lời giải; nếu vừa ghi vừa đọc
   thì bài thứ 150 chạy trên một hệ thống khác với bài thứ nhất.

## 3.2. Bộ dữ liệu huấn luyện bộ phân loại môn học

### 3.2.1. Quy mô và cách chia

**810 câu do nhóm tự xây dựng**, chia theo tầng (stratified): **535 train · 116 val ·
159 test**.

Mỗi câu gắn thêm nhãn `source` để lúc báo cáo tách bạch được ba nguồn dữ liệu:

| Nguồn | Số câu ở tập test | Cách tạo | Giá trị khoa học |
|---|---|---|---|
| `seed` | 47 | Soạn tay theo chương trình THPT, bám các dạng bài phổ biến trong đề thi tốt nghiệp và sách bài tập | Dữ liệu gốc |
| `template` | 67 | Sinh từ khuôn mẫu, đổi số liệu và cách diễn đạt | Làm dày dữ liệu huấn luyện. **Không dùng để công bố accuracy** — dễ với mọi phương pháp |
| `hard` | 45 | Soạn tay, **cố tình không chứa từ khoá đặc trưng** của môn, hoặc lai hai môn | Tập quan trọng nhất — chỉ nhóm này mới phân định được luật từ khoá với học sâu |

Cấu trúc tệp CSV: `question, label, source`.

### 3.2.2. Hai biện pháp chống rò rỉ dữ liệu

- **Chia theo tầng (stratified)** để ba môn cân bằng ở cả ba tập.
- **Các câu sinh từ cùng một khuôn mẫu được giữ trong cùng một tập.** Nếu khuôn *"Tính đạo
  hàm của y = {f} tại x = {a}"* xuất hiện ở cả train lẫn test thì phép đo chỉ đang kiểm tra
  khả năng nhớ khuôn, không phải khả năng phân loại.

### 3.2.3. Thiết kế đối chứng cho phần học sâu

Script `ml/compare.py` đối chiếu **ba phương pháp** trên cùng tập test:

1. **Luật từ khoá** — đúng bộ luật đang chạy trong `agents/router.py`. Không huấn luyện,
   0 ms, 0 token.
2. **TF-IDF + Logistic Regression** — học máy cổ điển. Đây là **mốc so sánh quan trọng
   nhất**: nếu PhoBERT không vượt được nó thì việc dùng transformer ở đây là thừa, và phải
   trung thực nói ra điều đó.
3. **PhoBERT fine-tuned** — mô hình học sâu do nhóm huấn luyện.

Chỉ số dùng **macro-F1** (trung bình F1 của ba lớp) thay vì accuracy, vì tập test không
cân bằng tuyệt đối giữa ba môn. Kết quả báo cáo tách riêng theo `source`, và nhóm `hard`
là nhóm quyết định.

## 3.3. Ba bộ đề đánh giá hệ thống

### 3.3.1. Cấu tạo

| Tệp | Số bài | Vai trò |
|---|---|---|
| `eval/data/de_chuan.csv` | 150 | **Bộ phát triển** — mọi cải tiến của dự án rút ra từ đây |
| `eval/data/de_giu_rieng.csv` | 150 | **Bộ giữ riêng**, trùng 0% với bộ chuẩn, chưa từng dùng để sửa bất cứ thứ gì |
| `eval/data/de_kho.csv` | 300 | Dò trần năng lực hệ thống; 90 bài (30%) ở mức vận dụng cao |

Mỗi dòng gồm 14 trường: `id, subject, topic, level, question_type, question, choices,
answer_value, answer_unit, answer_expr, answer_choice, bieu_thuc_kiem, nguon, ghi_chu`.

Ví dụ một dòng thật:

```
math_nb_001, math, dao_ham, NB, numeric,
"Tính đạo hàm của hàm số y = 4x^3 + 11x - 1 tại điểm x = 3.",
, 119, , , , "3*4*3**2 + 11", tu_soan, "y' = 3ax^2 + b, thay x0"
```

Trường `bieu_thuc_kiem` là chìa khoá của toàn bộ thiết kế: nó cho phép SymPy tính lại đáp
án một cách độc lập với người soạn đề.

### 3.3.2. Ba tầng bảo đảm đáp án đúng

1. **Đề sinh từ mẫu có tham số**, đáp án do Python tính từ chính các số vừa đưa vào đề.
   Sai số học là **không thể xảy ra về mặt kiến tạo**.
2. **Cột `bieu_thuc_kiem` được SymPy tính lại và đối chiếu** bằng `eval/kiem_de_chuan.py`.
   Cả ba bộ đều đạt **100%** ở bước tự kiểm này.
3. **Hệ số phản ứng hoá học lấy từ giải ma trận**, không do người soạn đoán.

Đề sinh với **seed cố định** nên tái lập được: chạy lại `build_de_chuan.py` trên máy khác
cho ra đúng bộ đề đó.

### 3.3.3. Vì sao phải có bộ giữ riêng

Đây là điểm cốt lõi về phương pháp của báo cáo này.

Mọi bản sửa trong dự án — bộ đọc số của script chấm, chốt chặn `loai_kiem`, kiến trúc
recompute, cơ chế cứu đáp án — đều rút ra từ quan sát trên `de_chuan.csv`. Con số đo trên
bộ đó **không còn là một phép thử độc lập**: nó đo lẫn cả công sức chỉnh riêng cho bộ ấy.

Bộ giữ riêng sinh ra với tham số `--tranh` để **loại tường minh** mọi câu đã có trong bộ
chuẩn. Chi tiết đáng lưu ý: nếu chỉ đổi seed mà không dùng `--tranh` thì hai bộ vẫn trùng
tới **41%**, vì pool tham số hẹp. Đây là loại rò rỉ dữ liệu rất dễ bỏ sót.

Bộ giữ riêng **chưa từng được dùng để sửa bất cứ thứ gì**. Đó là lý do mọi con số nộp báo
cáo trong Chương 4 lấy từ bộ này.

### 3.3.4. Vai trò của bộ đề khó

Bộ 300 bài này **không dùng để đối chiếu ngưỡng**, mà để **dò trần năng lực**. Nó được
soạn cố ý khó: 30% bài ở mức vận dụng cao, so với 13% của bộ chuẩn. Kết quả trên bộ này
(72,0%) thấp hơn ngưỡng 75% là điều đã dự kiến khi thiết kế, và được báo cáo nguyên trạng
ở Mục 4.6.

## 3.4. Memory pool trong thiết kế thực nghiệm

Memory pool là dữ liệu **vận hành**, không phải dữ liệu huấn luyện, nhưng nó ảnh hưởng
trực tiếp tới kết quả đo vì nội dung của nó được bơm vào prompt.

| Kho | Nội dung | Cách hình thành |
|---|---|---|
| Kho định lý | Công thức chuẩn sách giáo khoa | Soạn sẵn, cố định — không đổi giữa các lần đo |
| Kho lời giải | Ví dụ mẫu cho prompt | Tự tích luỹ từ những lượt đã qua kiểm chứng PASS |

Kho lời giải **thay đổi theo thời gian**, nên khi đo phải đặt `VMA_LUU_LOI_GIAI_MAU=0` để
đóng băng kho. Nếu không, bài thứ 150 chạy trên một hệ thống khác với bài thứ nhất và phép
đo mất tính dừng — kết quả không còn diễn giải được.

Đây cũng là biến độc lập của một thí nghiệm ablation riêng, trình bày ở Mục 4.4.9.

## 3.5. Giao thức đo

### 3.5.1. Môi trường đo

| Hạng mục | Giá trị |
|---|---|
| GPU | NVIDIA RTX 3060 Laptop, 6 GB VRAM |
| Mô hình | qwen3:4b (Q4_K_M, 2,5 GB) |
| Cấu hình | **Cấu hình D** (xem 3.6) |
| Số bài đo | 600 (150 + 150 + 300) |
| Thời gian chạy tham khảo | 20 bài ≈ 11 phút; 150 bài ≈ 80 phút; toàn bộ ≈ 4 giờ |

Ràng buộc vận hành khi đo: **không dùng giao diện web trong lúc chạy bench**, vì các
request tranh cùng một GPU và làm hỏng mọi số đo thời gian.

Một tính chất quan trọng của phép đo: **máy khác GPU thì thời gian sẽ khác, độ chính xác
thì không** — độ chính xác chỉ phụ thuộc mô hình và cấu hình, không phụ thuộc phần cứng.

### 3.5.2. Bộ chấm tự động — `scripts/bench.py`

Bộ chấm **không so chuỗi**. Nó chấm theo ba nhánh tuỳ loại câu hỏi:

| Nhánh | Cách chấm |
|---|---|
| Số (numeric) | Tính biểu thức bằng SymPy, dung sai 2%, **có quy đổi đơn vị** |
| Trắc nghiệm | So phương án đã chọn |
| Biểu thức | Rút gọn tượng trưng rồi so |

Nhờ vậy `1/2`, `0,5` và `50%` được coi là cùng một đáp số; `0,0018 m` và `1,8 mm` cũng
vậy.

Bộ đọc số này đã qua **ba vòng sửa**, mỗi vòng bắt nguồn từ một lỗi chấm oan đo được:

| Lỗi | Hậu quả |
|---|---|
| Bóc số dẫn đầu thay vì tính biểu thức | `5/36` → 5, `√73` → 73; chấm oan 4 bài |
| So số trần, không quy đổi đơn vị | `0,0018 m` bị coi là khác `1,8 mm` |
| Không đọc được `\frac` lồng nhau và `e` là cơ số tự nhiên | chấm oan 4 bài, **tất cả ở mức vận dụng cao** |

Sau vòng sửa cuối, kết quả được chấm lại toàn bộ bằng bản mạnh nhất: **0 bài chấm oan** ở
cả ba bộ đề.

Đây là một điểm phương pháp đáng nêu: **lỗi của bộ chấm và lỗi của hệ thống trông giống
hệt nhau trong bảng kết quả**. Nếu không rà lại bộ chấm, ta sẽ đi sửa mô hình cho một lỗi
mà thực ra nằm ở thước đo.

### 3.5.3. Hai thời điểm đo — tách bạch bắt buộc

Đây là chi tiết quyết định tính đúng đắn của chỉ số 3:

- **Chỉ số 1 (độ chính xác)** chấm trên **đáp án cuối cùng**, tức sau khi cơ chế cứu đáp
  án đã chạy.
- **Chỉ số 3 (tỉ lệ phát hiện lời giải sai)** chấm trên **đáp án của Subject Agent**, tức
  **trước** bước cứu.

Trộn hai thời điểm này là sai lệch nghiêm trọng: một bài mà Subject Agent giải sai, Verify
bắt đúng, rồi Manager cứu thành công sẽ bị đếm thành "Verify báo oan" — tức hệ thống bị
trừ điểm ở đúng chỗ nó làm việc tốt nhất.

### 3.5.4. Định nghĩa chỉ số

| Chỉ số | Định nghĩa |
|---|---|
| Accuracy | Tỉ lệ bài có đáp án cuối khớp ground truth theo bộ chấm ba nhánh |
| Sai số ± | Khoảng tin cậy 95% cho tỉ lệ trên mẫu tương ứng (n = 150 hoặc n = 300) |
| Đạt mốc 45 s | Tỉ lệ lượt có tổng thời gian end-to-end ≤ 45 giây |
| Phát hiện sai (chặt) | Trong số bài Subject Agent giải **sai**, tỉ lệ bài Verify kết luận FAIL |
| Phát hiện sai (nới) | Như trên, nhưng tính cả các trường hợp Verify nêu cảnh báo mà không FAIL |
| Báo oan | Trong số bài Subject Agent giải **đúng**, tỉ lệ bài Verify kết luận FAIL |

### 3.5.5. Công cụ phụ trợ

| Script | Chức năng |
|---|---|
| `eval/kiem_de_chuan.py` | Tự kiểm bộ đề bằng SymPy trước khi dùng để đo |
| `scripts/tien_do.py` | Báo tiến độ một lượt bench đang chạy |
| `scripts/cuu_log.py` | Cứu kết quả khi bench bị ngắt giữa chừng |
| `scripts/cham_lai.py` | Chấm lại kết quả đã có bằng bộ đọc số mạnh hơn, không chạy lại mô hình |
| `scripts/soi_verify.py` | In toàn bộ phép kiểm của Verify trên một bài cụ thể |

`cham_lai.py` đáng chú ý về phương pháp: nó cho phép sửa thước đo mà **không phải chạy lại
4 giờ suy luận**, nhờ vậy việc rà soát bộ chấm trở nên khả thi.

## 3.6. Thiết kế đối chứng A/B

Mọi cơ chế cải tiến trong hệ thống đều đặt **sau một cờ cấu hình**, bật/tắt được, để có
thể đối chứng A/B thay vì tin vào cảm nhận.

| Cờ | Mặc định | Tác dụng |
|---|---|---|
| `VMA_LOC_TINH_LAI_DO_DANG` | bật | Chặn kết quả tính lại còn ký hiệu tự do |
| `VMA_KIEM_KHOI_LUONG_MOL` | bật | Soát M(chất) bằng `chem_tool` |
| `VMA_BO_QUA_LLM_REVIEW` | bật | Bỏ lượt gọi LLM khi các phép kiểm tất định đã đủ căn cứ |
| `VMA_DUNG_KHO_DINH_LY` | bật | Chèn công thức vào prompt |
| `VMA_DUNG_KHO_LOI_GIAI` | bật | Chèn ví dụ mẫu vào prompt |
| `VMA_LUU_LOI_GIAI_MAU` | bật | Cất lời giải đã kiểm chứng (phải **tắt** khi đo) |
| `VMA_MAX_RETRY_ROUNDS` | 0 | Số vòng Verify được bắt giải lại |
| `VMA_AGENTS_SUY_NGHI` | rỗng | Tác tử nào được bật chế độ suy nghĩ của Qwen3 |

Ba khối cấu hình được dùng trong báo cáo:

| Cấu hình | Đặc điểm |
|---|---|
| **A** | Mốc nền — kiến trúc recompute cũ, không có các chốt chặn về sau |
| **C** | Bật chế độ suy nghĩ cho bộ tính lại — tối ưu độ chính xác, bỏ qua thời gian |
| **D** | **Cấu hình hiện tại** — kiến trúc recompute mới, tắt suy nghĩ, tắt vòng giải lại |

Kết quả đối chứng ba cấu hình trình bày ở Mục 4.4.5.

## 3.7. Thiết kế đánh giá chất lượng lời giảng (chỉ số 4)

Chỉ số này **đã bỏ theo thống nhất**, nhưng toàn bộ hạ tầng đã được dựng xong và vẫn còn
trong mã nguồn. Phần này ghi lại thiết kế vì nó thể hiện cách tiếp cận chống thiên vị.

```powershell
python eval/thu_loi_giang.py --so-bai 30    # thu lời giảng, KHÔNG bị cắt do hết giờ
python eval/phieu_cham.py xuat              # dựng phiếu HTML tự chứa, nhúng KaTeX
python eval/phieu_cham.py gop <thư mục>     # gộp CSV giáo viên gửi lại
```

Ba thiết kế chống thiên vị đã cài sẵn trong quy trình chấm:

- **Chấm mù** — không đánh dấu bài nào do hệ thống sinh, bài nào chép từ sách giải.
- **Mẫu neo** — trộn lời giải từ sách giải vào bộ chấm. Nếu chính sách giải cũng chỉ được
  4,1 điểm thì mốc 4/5 cho máy là khắt khe, và ta có **bằng chứng** để nói điều đó.
- **Có cả bài sai** — lấy mẫu theo đúng tỉ lệ đúng/sai thật, không chọn mẫu thiên vị.

Phiếu chấm là một file HTML tự chứa (754 KB, nhúng KaTeX): giáo viên mở bằng trình duyệt,
không cần mạng và không cần tài khoản.

Dữ kiện khách quan duy nhất còn giữ được về chỉ số này: **0/20 lời giảng bị cắt giữa
chừng** ở cấu hình hiện tại.

## 3.8. Bộ kiểm thử tự động

**222 kiểm thử**, chạy trong ~14 giây, **không cần Ollama** — nghĩa là chạy được trên máy
không có GPU và trong môi trường tích hợp liên tục.

| Tệp | Phạm vi phủ |
|---|---|
| `test_tools.py` | SymPy, hoá học, đơn vị |
| `test_arbiter.py` | Trọng tài ghi đè số |
| `test_recompute.py` | So sánh đáp số, chặn kết quả dở dang |
| `test_json_cuu.py` | Cứu JSON bị cắt |
| `test_kiem_symbolic.py` | Bộ kiểm SymPy và chốt chặn loại bài |
| `test_khoi_luong_mol.py` | Soát khối lượng mol |
| `test_bo_qua_llm_review.py` | Đường tắt của Verify |
| `test_memory_pool.py` | Hai kho |
| `test_bench_cham.py` | Bộ đọc số của script chấm |
| `test_so_hoc_the_ky_hieu.py` | Thế ký hiệu, chặn báo oan đổi đơn vị, báo cáo trung thực |
| `test_sinh_bai_tuong_tu.py` | Khớp chủ đề, không trùng đề gốc, **soát đáp án cả 175 mẫu bằng SymPy** |

Đáng chú ý: `test_sinh_bai_tuong_tu.py` có một kiểm thử tính lại **toàn bộ 175 mẫu** từ
cột `bieu_thuc_kiem` rồi đối chiếu với đáp án đã lưu — đúng phép soát đã dùng cho 600 bài
ground truth. Kiểm thử này đạt, nghĩa là đáp án của mọi bài sinh ra đều đúng, bảo đảm về
mặt kiến tạo chứ không phải may rủi.

**Giới hạn cần biết:** không kiểm thử nào chạm tới `manager` hay luồng tác tử. Chúng bảo
vệ tầng tất định — tầng dễ vỡ nhất khi tái cấu trúc — nhưng **sẽ không bắt được hồi quy ở
tầng prompt**. Bộ đề chuẩn là lưới thứ hai, và là lưới duy nhất bắt được loại lỗi đó.

## 3.9. Các mối đe doạ tới tính hợp lệ của phép đo

Phần này liệt kê thẳng những điều có thể làm sai lệch kết luận, kèm biện pháp đã áp dụng.

| Mối đe doạ | Biện pháp đã áp dụng | Còn tồn dư |
|---|---|---|
| Rò rỉ dữ liệu giữa bộ phát triển và bộ đánh giá | Bộ giữ riêng sinh với `--tranh`, trùng 0% | Không |
| Rò rỉ khuôn mẫu trong dữ liệu PhoBERT | Câu cùng khuôn giữ trong cùng một tập | Không |
| Phép đo trôi do memory pool ghi trong lúc đo | Tắt `VMA_LUU_LOI_GIAI_MAU` khi đo | Không |
| Lỗi của thước đo bị nhầm thành lỗi của hệ thống | Ba vòng sửa bộ đọc số, chấm lại toàn bộ | 0 bài chấm oan còn lại |
| Trộn hai thời điểm đo cho chỉ số 1 và 3 | Tách bạch tường minh trong `bench.py` | Không |
| Đề tự soạn có văn phong đều tay hơn đề thi thật | Ghi nhận công khai ở cột `nguon = tu_soan` | **Còn** — xem 4.6 |
| Số đo chỉ số 3 lấy khi `_check_arithmetic` còn hỏng | Ghi rõ là **cận dưới**, không trích số mới khi chưa chạy lại | **Còn** — xem 4.5 |
| Nhiễu do dùng giao diện trong lúc đo | Quy trình cấm dùng giao diện khi chạy bench | Không |

---
---

# CHƯƠNG 4. CÁC ÁP DỤNG THỰC TẾ, QUÁ TRÌNH CÀI ĐẶT VÀ KẾT QUẢ THỰC NGHIỆM

## 4.1. Các áp dụng thực tế

### 4.1.1. Người học tự học ở nhà

Kịch bản chính. Học sinh nhập đề bài đang bế tắc, nhận về:

- lời giải từng bước với công thức hiển thị chuẩn (KaTeX);
- một đáp số kèm **tín hiệu độ tin cậy** — verdict PASS/FAIL, `confidence`, và cảnh báo
  khi cơ chế cứu đáp án đã can thiệp;
- một bài giảng viết theo văn phong sư phạm, chảy chữ theo thời gian thực;
- **một bài tập tương tự** để tự luyện ngay, đáp án giấu sau nút bấm, kèm nút "Gợi ý" chỉ
  đưa công thức cần dùng.

Điểm khác biệt so với việc hỏi một chatbot thông thường là ở **tín hiệu độ tin cậy**. Hệ
thống nói rõ khi nó không chắc, thay vì trình bày mọi thứ với cùng một giọng tự tin.
Hướng dẫn sử dụng còn đưa ra một quy tắc thực dụng cho người dùng: *PASS + không cảnh báo
+ trọng tài không phải phân xử* là tổ hợp đáng tin nhất; có bất kỳ dấu hiệu nào trong ba
thứ đó thì nên đọc kỹ các bước giải trước khi tin đáp số.

### 4.1.2. Giáo viên soạn đề luyện tập

Tác tử sinh bài tương tự tạo ra đề mới cùng dạng trong 43 ms, **đáp án bảo đảm đúng theo
kiến tạo**. Mỗi lần gọi bốc một bộ tham số mới nên cùng một mẫu cho ra vô số đề khác nhau.
Giáo viên có thể sinh hàng loạt bài luyện cho một chủ đề cụ thể mà không phải tự kiểm tra
lại đáp án từng bài.

### 4.1.3. Phòng máy trường học không có Internet ổn định

Đây là kịch bản mà các giải pháp dựa trên API thương mại không đáp ứng được:

| Ràng buộc thực tế | Cách hệ thống đáp ứng |
|---|---|
| Không có mạng ra ngoài | Chạy hoàn toàn cục bộ, chỉ cần `localhost` |
| Không có ngân sách trả phí API | **Chi phí vận hành bằng không** sau khi cài đặt |
| Máy cấu hình phổ thông | GPU 4 GB VRAM là đủ (mô hình chiếm 2,9 GB) |
| Dữ liệu học sinh không nên gửi ra ngoài | Không một byte nào rời khỏi máy |

Kiến trúc HTTP giữa backend và Ollama còn cho phép **tách máy**: một máy có GPU chạy
Ollama phục vụ nhiều máy trạm không GPU trong cùng mạng nội bộ.

### 4.1.4. Nền tảng kỹ thuật có thể mở rộng

Kiến trúc chuyên biệt hoá vai trò khiến việc thêm một môn học mới chỉ tốn **một file
prompt**, không phải sửa luồng điều phối. Tầng kiểm chứng tất định là một thư viện độc
lập, dùng lại được cho bất kỳ hệ thống nào cần đối chiếu kết quả của LLM với công cụ tính
toán.

### 4.1.5. Giá trị phương pháp cho các dự án tương tự

Ba mẫu thiết kế trong đề tài có thể áp dụng lại ở lĩnh vực khác:

1. **Đường tính toán độc lập chạy song song** — chi phí gần như bằng 0 nếu vai phụ nhanh
   hơn vai chính, mà đổi lại được một nguồn đối chiếu.
2. **Ràng buộc đầu ra bằng grammar JSON** — mạnh hơn mọi lời dặn trong prompt.
3. **Đặt mọi cải tiến sau một cờ cấu hình** — biến "tôi nghĩ nó tốt hơn" thành một phép đo
   A/B thực hiện được.

## 4.2. Quá trình cài đặt

### 4.2.1. Yêu cầu môi trường

| Thứ | Bản đang dùng | Kiểm tra |
|---|---|---|
| Python | 3.13 | `python --version` |
| Node.js | 22 | `node -v` |
| Ollama | 0.32+ | `ollama --version` |

Yêu cầu phần cứng tối thiểu: **GPU 4 GB VRAM** (mô hình chiếm 2,9 GB ở `num_ctx` = 4096),
**RAM 8 GB**, **ổ trống 12 GB**.

### 4.2.2. Ba nhóm thư viện

| Nhóm | Tệp khai báo | Thành phần chính |
|---|---|---|
| Lõi, bắt buộc | `backend/requirements.txt` | autogen-agentchat, autogen-ext[ollama], fastapi, uvicorn, pydantic, sse-starlette, httpx, **sympy**, **pint**, python-dotenv, pytest |
| Học sâu, **tuỳ chọn** | `backend/requirements-ml.txt` | torch (bản CPU), transformers, underthesea, scikit-learn |
| Giao diện | `frontend/package.json` | React, TypeScript, Vite, KaTeX |

Nhóm học sâu để ở chế độ **tuỳ chọn** có chủ đích: thiếu nó hệ thống vẫn chạy đủ, Router
tự lùi về luật từ khoá. Điều này giúp người chỉ muốn xem sản phẩm không phải cài hơn 1 GB
thư viện.

Riêng `torch` phải cài **bản CPU** bằng lệnh chỉ định nguồn:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Cài bản mặc định sẽ kéo về bản CUDA nặng ~2,5 GB và **tranh VRAM với Ollama**, trong khi
PhoBERT chạy CPU chỉ mất ~50 ms mỗi câu — thừa nhanh so với ngân sách 45 giây.

### 4.2.3. Trình tự cài đặt lần đầu

```powershell
# 1. Tải mô hình ngôn ngữ (2,5 GB, lưu ngoài thư mục dự án)
ollama pull qwen3:4b

# 2. Backend
cd backend
python -m pip install -r requirements.txt
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ml.txt
python ml/train_phobert.py          # ~12 phút, sinh ra mô hình PhoBERT

# 3. Frontend
cd ../frontend
npm install

# 4. Cấu hình
cd ..
copy .env.example .env
```

**Thời gian cài đặt từ máy trắng: 30–45 phút**, thực hiện một lần.

Trọng số PhoBERT sau huấn luyện nặng **517 MB** nên **không nằm trong repo** (vượt hạn mức
100 MB mỗi file của GitHub). Người lấy dự án về phải tự chạy `python ml/train_phobert.py`
một lần. Tương tự, trọng số Qwen3 do Ollama quản lý ở
`C:\Users\<user>\.ollama\models`, nằm ngoài thư mục dự án.

### 4.2.4. Khởi động hằng ngày — ba tiến trình

| Cửa sổ | Lệnh | Cổng |
|---|---|---|
| 1 | `ollama serve` (bỏ qua nếu đã chạy dạng ứng dụng nền) | 11434 |
| 2 | `python -m uvicorn main:app --port 8000` (từ `backend/`) | 8000 |
| 3 | `npm run dev` (từ `frontend/`) | 5173 |

Kiểm tra nhanh: mở `http://localhost:8000/api/health`, phải thấy JSON có `"status":"ok"`
kèm cấu hình đang chạy. Endpoint này cũng là cách xác nhận `.env` đã có hiệu lực hay chưa.

**Làm nóng trước khi dùng thật:** lượt hỏi đầu tiên luôn chậm thêm 8–15 giây vì Ollama
phải nạp mô hình vào VRAM. Khi trình diễn, cần hỏi trước một câu bất kỳ.

### 4.2.5. Khối lượng mã nguồn

| Phần | Số dòng |
|---|---|
| Backend (Python) | **11 847** |
| — trong đó: 8 tác tử | 1 730 |
| — trong đó: 5 module công cụ tất định | 1 135 |
| Frontend (TypeScript + TSX) | **1 908** |
| Kiểm thử | 222 test trong 11 tệp |

### 4.2.6. Cấu trúc thư mục

```
ViMultiAgent/
├── backend/
│   ├── agents/          8 tác tử: planner, router, 3 subject, verify,
│   │                    explain, recompute, sinh bài tương tự
│   │   ├── manager.py   điều phối toàn luồng, phát sự kiện SSE
│   │   └── base.py      lớp vỏ chung dựng trên AutoGen + Ollama
│   ├── tools/           SymPy, hoá học, đơn vị, trọng tài số học
│   ├── memory/          kho định lý + kho lời giải mẫu
│   ├── ml/              dataset + PhoBERT phân loại môn học
│   ├── eval/            3 bộ đề, script sinh đề, công cụ chấm lời giảng
│   ├── scripts/         bench, chấm lại, chẩn đoán
│   ├── tests/           222 kiểm thử
│   ├── core/            schema, cấu hình, SQLite, cứu JSON
│   ├── api/routes.py    REST + SSE
│   └── main.py          điểm khởi động FastAPI
├── frontend/            React + TypeScript + Vite, hiển thị Markdown + KaTeX
└── vimultiagent.db      SQLite: lịch sử + memory pool
```

### 4.2.7. Giao diện và API

Bố cục màn hình:

| Vùng | Nội dung |
|---|---|
| Ô nhập trên cùng | Đề bài; `Ctrl + Enter` để gửi nhanh |
| Ba nút Toán / Lý / Hoá | Điền sẵn đề mẫu |
| Cột trái | Năm vai của quy trình, sáng dần theo tiến trình |
| Đáp án | Hiện **trước khi** lời giảng chảy xong |
| Các bước giải | Từng bước có công thức KaTeX |
| Lời giảng | Chảy chữ theo thời gian thực |
| Thẻ *Bài tập tương tự* | Sinh đề luyện cùng dạng, không gọi LLM |
| Dòng cuối | Tổng thời gian và có đạt mốc KPI không |

Bảng endpoint:

| Method | Đường dẫn | Trả về | Dùng để |
|---|---|---|---|
| GET | `/api/health` | JSON | Kiểm tra backend + cấu hình đang chạy |
| POST | `/api/solve` | **SSE** | Giải bài, có tiến trình và streaming |
| POST | `/api/solve_sync` | JSON | Giải bài, chờ trọn gói — tiện cho script |
| POST | `/api/bai_tuong_tu` | JSON | Sinh bài luyện cùng dạng |
| GET | `/api/history?limit=20` | JSON | Lượt hỏi gần đây |
| GET | `/api/stats` | JSON | Tổng hợp số lượt, thời gian TB, tỉ lệ PASS theo môn |

Các loại sự kiện SSE của `/api/solve`: `agent` (một vai bắt đầu/kết thúc), `recompute_info`,
`arbiter`, **`dap_an`** (chốt đáp số, phát trước khi giảng), `token` (một mẩu chữ của lời
giảng), `retry`, `cuu_dap_an`, `done`, `error`.

## 4.3. Kết quả thực nghiệm

Toàn bộ số liệu dưới đây đo ở **cấu hình D**, trên **600 bài** thuộc ba bộ đề rời nhau,
sau khi đã chấm lại bằng bộ đọc số mạnh nhất (**0 bài chấm oan** ở cả ba bộ).

### 4.3.1. Đối chiếu bộ chỉ số đăng ký

Số liệu lấy từ **bộ đề giữ riêng 150 bài**.

| Chỉ số | Ngưỡng | Đo được | Kết luận |
|---|---|---|---|
| Accuracy bài toán STEM cấp THPT tiếng Việt | ≥ 75% | **78,7% ± 6,6** | ✅ **Đạt** |
| Latency end-to-end | ≤ 45 s | **150/150 = 100%**, trung bình 30,4 s | ✅ **Đạt** |
| Solution verification rate (chặt) | ≥ 85% | 53,1% * | ❌ **Chưa đạt** |
| Solution verification rate (nới) | ≥ 85% | 71,9% * | ❌ **Chưa đạt** |
| Explanation quality | ≥ 4/5 | Đã bỏ theo thống nhất | — |

\* Đo khi phép kiểm `_check_arithmetic` còn hỏng (xem Mục 4.5), nên là **cận dưới** của
bản hiện tại.

Trên toàn bộ **600 bài** thuộc ba bộ đề rời nhau: **600/600 lượt dưới 45 giây**, không một
ngoại lệ nào.

### 4.3.2. Kết quả trên cả ba bộ đề

| Bộ đề | n | Accuracy | Đạt mốc 45 s | Phát hiện sai | Báo oan |
|---|---|---|---|---|---|
| Chuẩn (phát triển) | 150 | 80,0% ± 6,4 | **150/150** | 60,0% | 18,3% |
| **Giữ riêng** | 150 | **78,7% ± 6,6** | **150/150** | 53,1% | 11,0% |
| Khó | 300 | 72,0% ± 5,1 | **300/300** | 45,2% | 15,7% |

**Bằng chứng các cải tiến tổng quát thật.** Chênh lệch giữa bộ phát triển và bộ giữ riêng
chỉ **1,3 điểm** (80,0% so với 78,7%), nằm gọn trong sai số ±6,6. Nếu các bản sửa chỉ là
"may đo" riêng cho bộ phát triển thì khoảng cách phải lớn hơn nhiều. Đây là kết quả quan
trọng nhất về mặt phương pháp trong toàn bộ báo cáo.

### 4.3.3. Phân rã theo mức độ nhận thức

| Mức | Bộ chuẩn | Bộ giữ riêng | Bộ khó |
|---|---|---|---|
| Nhận biết | 97,6% | 90,4% | 75,7% |
| Thông hiểu | 73,9% | 80,4% | 82,6% |
| Vận dụng | 73,8% | 71,4% | 78,8% |
| **Vận dụng cao** | 70,0% | **52,9%** | **54,4%** |

Vận dụng cao là **điểm gãy duy nhất và nhất quán** trên cả ba bộ đề. Ba mức còn lại dao
động trong khoảng 71–98%, còn mức vận dụng cao tụt xuống 52,9–70,0%.

Đây cũng là lời giải thích cho con số 72,0% của bộ đề khó: bộ này có 90 bài vận dụng cao
(30%) so với 20 bài (13%) của bộ chuẩn.

**Phát biểu an toàn rút ra từ dữ liệu:** *hệ thống dùng được tới hết mức Vận dụng; ở mức
Vận dụng cao thì chưa đủ tin cậy.*

### 4.3.4. Phân rã theo môn học

| Môn | Bộ chuẩn | Bộ giữ riêng | Bộ khó |
|---|---|---|---|
| Toán | 84,0% | 82,0% | 70,0% |
| Vật lý | 78,0% | 70,0% | **66,0%** |
| Hoá học | 78,0% | 84,0% | **80,0%** |

Vật lý là môn yếu nhất trên bài khó; Hoá học ổn định nhất — nhiều khả năng nhờ **hai phép
kiểm tất định riêng cho môn này** (bảo toàn nguyên tố và khối lượng mol). Đây là bằng
chứng gián tiếp cho thấy tầng kiểm chứng có tác dụng thật: môn nào có nhiều phép kiểm tất
định hơn thì kết quả ổn định hơn khi độ khó tăng.

Trên bộ đề khó, sáu chủ đề sai gần như toàn bộ: tích phân từng phần, giới hạn, tiếp tuyến
(Toán); điện tích Coulomb, lượng tử, dao động điều hoà (Vật lý). Đáng chú ý, **hình học
không phải điểm yếu** — 80,4% so với đại số 77,8%.

### 4.3.5. Phân rã thời gian và đường găng

**Đường găng:** `5,5 + 0,0 + max(8,6 ; 5,1) + 4,7 + 11,6 = 30,3 giây`

| Vai | Giây | Ghi chú |
|---|---|---|
| Planner | 5,5 | |
| Router | 0,0 | PhoBERT quyết định 94,7% số bài, ~50 ms |
| Subject Agent | 8,6 | |
| Recompute | 5,1 | chạy song song, **ẩn hoàn toàn dưới Subject Agent** |
| Verify | 4,7 | |
| Explain | 11,6 | vai tốn nhiều nhất sau khi đã tối ưu |

Hai điểm đáng chú ý:

1. **Bộ tính lại độc lập gần như miễn phí về thời gian.** Nó chạy 5,1 giây song song với
   Subject Agent 8,6 giây, nên không cộng vào đường găng. Đây là điều kiện tiên quyết để
   cơ chế đối chiếu chéo khả thi trong ngân sách 45 giây.
2. **Người dùng thấy đáp án sớm hơn ~11,6 giây** so với lúc lời giảng chảy xong, nhờ sự
   kiện `dap_an` phát ngay trước Explain.

### 4.3.6. Đường đánh đổi độ chính xác – độ trễ

Ba cấu hình, cùng bộ đề chuẩn 150 bài:

| | A | C | **D (hiện tại)** |
|---|---|---|---|
| Accuracy | 80,7% | **90,0%** | 80,0% |
| Đạt mốc 45 s | 100% | **3,3%** | **100%** |
| Thời gian trung bình | 30,4 s | 65,1 s | **30,0 s** |
| Phát hiện sai | 60,0% | 31,2% | 60,0% |

Cấu hình C đạt độ chính xác cao nhất (90,0%) nhưng **trượt mốc thời gian gần như hoàn
toàn** (3,3%). Nguyên nhân đã truy được: bật chế độ suy nghĩ cho bộ tính lại khiến vai này
tốn **41,6 giây** và **trở thành đường găng** — đo được 149/150 bài có recompute chậm hơn
Subject Agent, tức cơ chế chạy song song mất sạch tác dụng.

Cấu hình D đạt tốc độ của A với độ chính xác tương đương, và điều quan trọng là nó đạt
được **bằng cách đổi kiến trúc chứ không phải cắt xén**:

> Bộ tính lại chuyển từ *"tự suy luận ra đáp số"* sang *"trích đề về dạng máy đọc được rồi
> để SymPy tự giải"*. Mô hình chỉ còn phải chép lại đề cho đúng cấu trúc — việc nó làm
> tốt. Phần tính toán giao hẳn cho SymPy — việc SymPy không bao giờ sai.
> **41,6 giây → 5,1 giây.**

Đây là kết quả kỹ thuật đáng chú ý nhất của đề tài: một cải tiến 8 lần về tốc độ đến từ
việc **phân bổ lại trách nhiệm giữa thành phần thần kinh và thành phần ký hiệu**, không
đến từ việc cắt token hay hạ chất lượng.

### 4.3.7. Kết quả phần học sâu

**Bộ phân loại PhoBERT** — kết quả mong đợi sau khi chạy `ml/train_phobert.py`:

```
Độ chính xác trên test: 0,94
  seed       47/47 = 100,0%
  template   67/67 = 100,0%
  hard       36/45 =  80,0%
```

Phân rã theo nguồn dữ liệu cho thấy đúng điều đã dự đoán khi thiết kế dataset: con số trên
nhóm `template` gần như luôn tuyệt đối và **không có giá trị phân định**; chỉ nhóm `hard`
— câu cố tình không chứa từ khoá đặc trưng — mới phân biệt được các phương pháp. Đây chính
là nhóm mà luật từ khoá buộc phải đoán bừa.

**Hiệu quả của Router ba tầng** — đo trên 150 bài:

| Tầng | Tỉ lệ quyết định | Thời gian |
|---|---|---|
| PhoBERT | **94,7%** | ~50 ms |
| Luật từ khoá | 2,7% | 0 ms |
| LLM | 2,7% | 2–4 giây |
| **Trung bình cả vai** | | **0,05 giây** |

Nếu định tuyến bằng LLM như thiết kế ban đầu, riêng vai này đã chiếm 2–4 giây, tức 4–9%
ngân sách 45 giây, cho một bài toán mà một mô hình 135 triệu tham số giải được trong 50 ms.

Thời gian huấn luyện: **~12 phút trên CPU**, thực hiện một lần. Con số này thấp vì bài
toán rất nhẹ — phân loại 3 lớp trên 535 câu huấn luyện với mô hình nền 135 triệu tham số.
Việc huấn luyện chạy trên CPU nên **không cần tắt Ollama**; hai thứ không tranh tài nguyên
của nhau.

### 4.3.8. Tác tử sinh bài tập tương tự

| Chỉ tiêu | Kết quả |
|---|---|
| Thời gian đáp ứng | **43 ms** (gồm cả lần nạp kho đầu tiên) |
| Số lượt gọi LLM | **0** |
| Số mẫu phủ | 175 (61 Toán · 57 Lý · 57 Hoá) |
| Bảo đảm đáp án | Kiểm thử tính lại toàn bộ 175 mẫu bằng SymPy — **đạt** |
| Ảnh hưởng tới chỉ số độ trễ | **Không** — nằm ngoài `solve_stream` |

So với thiết kế gốc theo tinh thần MetaGPT (để LLM nghĩ ra đề mới), cách tiếp cận này
mạnh hơn ở một điểm cốt lõi: **đáp án đúng theo kiến tạo, không phải theo may rủi**.

### 4.3.9. Tối ưu bộ nhớ ngữ cảnh

`num_ctx` mặc định hạ từ 8192 xuống **4096**, đo trực tiếp bằng `ollama ps`:

| `num_ctx` | VRAM | Thời gian TB | Lời giảng bị cắt | Mô hình nằm trọn GPU |
|---|---|---|---|---|
| 8192 | 3,3 GB | 30,0 s | — | ✅ |
| **4096 (mặc định)** | **2,9 GB** | **30,5 s** | 1/20 | ✅ |
| 1900 | 2,7 GB | 30,5 s | 1/20 | ✅ |

Nhu cầu ngữ cảnh thật chỉ **~1720 token** (prompt dài nhất 620 + trần đầu ra 1100), nên
8192 thừa gấp 4,8 lần. Hạ xuống 4096 tiết kiệm **400 MB VRAM** mà tốc độ không đổi — đủ để
máy 4 GB chạy được thay vì đòi 6 GB.

**Vì sao dừng ở 4096 chứ không lấy 1900.** Mức 1900 đã đo và không hỏng gì trên bộ đề hiện
có. Nhưng bộ đề đánh giá có lời giải khá đều, khoảng 5 bước, còn người dùng thật có thể
hỏi bài dài hơn:

| Số bước lời giải | Prompt Explain | + 900 token đầu ra | 1900 có đủ? |
|---|---|---|---|
| 5 bước | 672 | 1572 | ✅ dư 328 |
| 10 bước | ~880 | 1780 | ⚠️ dư 120 |
| 15 bước | ~1080 | 1980 | ❌ **thiếu** |

Bài 15 bước sẽ bị cắt lời giảng ở mức 1900 mà vẫn chạy tốt ở 4096. Bộ đề không có bài nào
như vậy nên phép đo không bắt được — đó là **giới hạn của phép đo, không phải bằng chứng
1900 an toàn**. Đổi 200 MB lấy biên an toàn tụt từ 2,4 lần xuống 1,24 lần là không đáng
cho một giá trị mặc định. Mức 1900 được giữ làm **phương án cho máy VRAM chật**, đặt qua
`VMA_NUM_CTX=1900`.

### 4.3.10. Kết quả các thí nghiệm ablation

**Vòng giải lại (retry loop).** Đo A/B trên cùng 20 bài:

| | Số bài đúng | Thời gian thêm |
|---|---|---|
| Có vòng giải lại | 17/20 | +5 giây mỗi lượt |
| **Không có** | **18/20** | — |

Vòng giải lại cứu được 1 bài nhưng làm hỏng 2. Nguyên nhân đã truy được: vòng này được
kích hoạt bởi Verify, mà Verify báo oan tới 18–28%, nên **phần lớn lần giải lại là đi sửa
một lời giải vốn đã đúng**. Vì vậy `VMA_MAX_RETRY_ROUNDS` mặc định đặt 0.

Cần nói rõ: **đây không phải cắt xén tính năng** — mã nguồn vòng sửa sai vẫn còn nguyên,
bật lại chỉ là một dòng cấu hình.

**Memory pool.** Đo trên 50 bài Hoá, có và không có memory pool đều cho **42/50**. Ba bài
được cứu, ba bài bị làm hỏng — triệt tiêu nhau. **Không có bằng chứng nó cải thiện độ
chính xác**, và điều này được báo cáo nguyên trạng.

**Chốt chặn `loai_kiem`.** Can thiệp này dịch chuyển cân bằng giữa hai loại lỗi:

| | Phát hiện sai | Báo oan |
|---|---|---|
| Trước chốt chặn `loai_kiem` | 70,4% | 27,6% |
| Sau | 60,0% | 18,3% |

Đây là kết quả quan trọng cho phần bàn luận ở Mục 4.6: các can thiệp chỉ **dịch chuyển cân
bằng**, chưa nâng được đồng thời cả hai chỉ tiêu.

**Trần token của Planner.** Đo trên cùng 20 bài:

| Trần token Planner | Số bài đúng | Thời gian Subject Agent |
|---|---|---|
| **400** | **18/20 (90,0%)** | 12,4 s |
| 250 | 13/20 (65,0%) | 7,7 s |

Mất 5 bài để đổi lấy 2,6 giây. Ở mức vận dụng cao, tỉ lệ đúng tụt từ 2/2 xuống 0/2.

## 4.4. Bàn luận — ca nghiên cứu: một phép kiểm báo đạt suốt nhiều ngày mà chưa từng chạy

Đây là ca đáng ghi lại nhất của dự án, vì nó minh hoạ một dạng lỗi **nguy hiểm hơn lỗi
sai**: phép kiểm báo đạt trong khi nó không hề chạy.

### 4.4.1. Hiện tượng

Ngày 2026-08-10, chạy thử giao diện với đề *"đốt cháy hoàn toàn 4,6 gam Na trong O₂ dư"*.
Lời giải trả về:

| Bước | `expression` | `result` | |
|---|---|---|---|
| 2 | `nNa = mNa/MNa` | 0,2 mol | đúng |
| 3 | `nNa2O = nNa/2` | 0,1 mol | đúng |
| 4 | `mNa2O = nNa2O * MNa2O` | **3,8 g** | **sai, phải là 6,2** |

Verify vẫn kết luận *"số học các bước khớp"*.

### 4.4.2. Nguyên nhân

Bản cũ của `_check_arithmetic`:

```python
rhs = expr.split("=")[-1]
a = sympy_tool.evaluate(rhs)
if va is None or vb is None:
    continue          # <- rơi vào đây
```

Mô hình gần như **luôn** viết vế phải bằng công thức chữ và chỉ để con số ở trường
`result`. SymPy gặp toàn ký hiệu tự do nên trả `None`, và bước bị bỏ qua **im lặng**. Cả 4
bước đều bị bỏ qua, rồi hàm vẫn trả về `passed=True`.

### 4.4.3. Hệ quả kép

Vế thứ nhất: phép kiểm vô dụng. Vế thứ hai nặng hơn nhiều: **Verify Agent đọc dòng "số học
khớp" đó rồi yên tâm kết luận PASS**. Một phép kiểm chết không chỉ vô dụng — nó còn **phát
ra tín hiệu giả làm hỏng phán đoán của tầng phía trên**.

### 4.4.4. Bản sửa

Thế giá trị vào ký hiệu trước khi tính, lấy từ vế trái các bước trước và từ bảng nguyên tử
khối, kèm ba chốt chặn chống báo oan (chi tiết ở Mục 2.4.6).
`tests/test_so_hoc_the_ky_hieu.py` dựng lại nguyên ca thật này và chốt cả ba chốt chặn.

### 4.4.5. Bài học phương pháp

> Bộ kiểm thử **181 bài lúc đó đều đạt**, vì không kiểm thử nào dựng lời giải viết bằng
> công thức chữ — đúng dạng mà mô hình luôn sinh ra. Lỗi chỉ lộ ra khi có người ngồi đọc
> một đáp án cụ thể trên giao diện.
>
> **Test bảo vệ được điều ta nghĩ tới. Chỉ có dùng thật mới lộ ra điều ta không nghĩ tới.**

Hệ quả đối với báo cáo này: mọi con số của **chỉ số 3** trong toàn bộ tài liệu đều đo
**trước** bản sửa nói trên. Chúng là số đo trung thực của hệ thống ở thời điểm đó và phải
hiểu là **cận dưới** của bản hiện tại. Chạy lại `bench.py` sẽ cho số cao hơn, nhưng nhóm
không cho rằng đủ để chạm ngưỡng 85%. Các con số accuracy và độ trễ **không bị ảnh hưởng**
bởi lỗi này.

## 4.5. Hạn chế đã biết

Phần này nêu thẳng mọi hạn chế, không né tránh.

**1. Chỉ số 3 chưa đạt — 53,1% so với ngưỡng 85%.** Nguyên nhân gốc: tầng kiểm chứng bị
giới hạn bởi **chất lượng trích xuất của mô hình 4B** — nó không phân biệt nổi "tính f(3)"
với "tính f′(3)", nên mọi phép kiểm tất định phía sau đều phải dè dặt. Hai lần can thiệp
gần đây chỉ **dịch chuyển cân bằng** giữa "bắt đúng lời giải sai" và "báo oan lời giải
đúng" (70,4%/27,6% → 60,0%/18,3%), chứ không nâng được đồng thời cả hai. Siết chặt tiêu
chí thì bắt được nhiều hơn nhưng báo oan tăng, và mỗi lần báo oan là một lần hệ thống đi
sửa một lời giải vốn đã đúng.

**2. Số đo chỉ số 3 đã lỗi thời.** Toàn bộ con số phát hiện sai đo khi `_check_arithmetic`
đang hỏng (Mục 4.4). Chúng là **cận dưới**. Không nên trích số mới nào cho tới khi chạy
lại `bench.py`.

**3. Bài Hoá không có trọng tài SymPy.** `kiem_symbolic` chỉ nhận năm dạng Toán, nên
`_loai_kiem_hop_le` từ chối mọi bài Hoá. Hệ quả dây chuyền: đường tắt của Verify đòi điều
kiện "bộ tính lại đã xác nhận độc lập", điều kiện đó không bao giờ thoả với Hoá, nên **mọi
bài Hoá đều phải qua vòng LLM soi lại** — nguồn báo oan lớn nhất còn lại.

**4. Vận dụng cao là điểm gãy nhất quán.** 52,9% trên bộ giữ riêng và 54,4% trên bộ khó,
so với 80–90% ở ba mức còn lại. Đây là **giới hạn năng lực thật của mô hình 4 tỉ tham số**,
không phải lỗi kỹ thuật có thể vá.

**5. Accuracy trên bộ đề khó là 72,0%**, dưới ngưỡng 75%. Bộ này có 30% bài vận dụng cao
so với 13% của bộ chuẩn, được soạn cố ý khó để dò trần năng lực, không phải để đối chiếu
ngưỡng.

**6. Bộ đề tự soạn.** Cột `nguon` ghi `tu_soan` — sinh bằng mẫu có tham số, đáp án đúng
theo kiến tạo, nhưng **văn phong đều tay hơn đề thi thật**. Đây là hạn chế còn tồn dư của
thiết kế thực nghiệm.

**7. Memory pool chưa chứng minh được giá trị.** Đo trên 50 bài Hoá cho kết quả y hệt khi
tắt (42/50 cả hai).

**8. Kiểm thử không phủ tầng tác tử.** 222 kiểm thử bảo vệ tầng tất định nhưng không chạm
tới `manager` hay luồng tác tử, nên **không bắt được hồi quy ở tầng prompt**.

**9. Chỉ số 4 không có số đo.** Hạ tầng chấm mù đã dựng xong và còn trong mã nguồn, nhưng
buổi chấm chưa được tổ chức và chỉ số đã bỏ theo thống nhất.

## 4.6. Về tuyên bố tính đột phá

Bản đăng ký ban đầu ghi *"đầu tiên tại Việt Nam có cơ chế self-verification bằng tác tử
độc lập"*. Cụm **"đầu tiên tại Việt Nam"** là một tuyên bố **không kiểm chứng được**: nếu
được yêu cầu chứng minh, nhóm không có căn cứ nào để chống đỡ.

Đề nghị diễn đạt lại theo đúng những gì **chứng minh được bằng số đo**:

> Hệ thống đa tác tử giải bài tập STEM tiếng Việt chạy **hoàn toàn ngoại tuyến trên máy
> phổ thông** (GPU 4–6 GB, không cần khoá API của bất kỳ dịch vụ nào), kết hợp tác tử LLM
> với **tầng kiểm chứng tất định** (SymPy, cân bằng nguyên tố, khối lượng mol, kiểm thứ
> nguyên) và **tác tử tính lại độc lập chạy song song** — đạt **78,7%** độ chính xác trên
> bộ đề giữ riêng với **100% lượt dưới 45 giây**.

Bốn điểm mạnh có thể bảo vệ được bằng bằng chứng, xếp theo sức thuyết phục:

1. **Chạy offline hoàn toàn, chi phí vận hành bằng không.** Không khoá API, không phụ
   thuộc dịch vụ nước ngoài — quan trọng với bối cảnh trường học Việt Nam.
2. **Cơ chế tự kiểm chứng bằng đường tính toán độc lập.** Một mô hình đơn lẻ không có khả
   năng này; nó cũng không thể tự phát hiện mình nhớ sai khối lượng mol.
3. **Số liệu tái lập được, có bộ giữ riêng.** Đề sinh với seed cố định, đáp án tính bằng
   SymPy, có bộ held-out chưa từng dùng để sửa gì.
4. **Trung thực về hạn chế.** Chỉ số 3 chưa đạt và điều đó được ghi rõ, kèm phân tích
   nguyên nhân tới tận gốc.

## 4.7. Hướng phát triển

| Hướng | Nội dung | Kỳ vọng |
|---|---|---|
| Mở rộng trọng tài SymPy sang mảng Hoá | Xây bộ kiểm tất định cho các dạng bài Hoá phổ biến (bảo toàn khối lượng, hiệu suất phản ứng, dung dịch) | Gỡ nguồn báo oan lớn nhất còn lại; nâng chỉ số 3 |
| Chạy lại toàn bộ phép đo chỉ số 3 | Sau bản sửa `_check_arithmetic` | Có số đúng cho bản hiện tại thay vì cận dưới |
| Thử mô hình 8B trên máy đủ VRAM | Máy 12 GB VRAM trở lên | Kỳ vọng cải thiện rõ ở mức vận dụng cao |
| Nhận đề bằng ảnh chụp | Thêm tầng OCR trước Planner | Mở rộng kịch bản dùng thật |
| Tổ chức chấm chất lượng lời giảng | Hạ tầng đã sẵn sàng, chỉ cần tổ chức buổi chấm | Có số cho chỉ số 4 |
| Bổ sung đề thi thật vào bộ đánh giá | Giảm hạn chế "văn phong đều tay" của đề tự soạn | Tăng tính đại diện của phép đo |

## 4.8. Kết luận

Đề tài đã xây dựng thành công ViMultiAgent — hệ đa tác tử giải bài tập STEM tiếng Việt bậc
THPT, chạy hoàn toàn ngoại tuyến trên máy cấu hình phổ thông, với tám tác tử chuyên biệt
hoá vai trò trên khung AutoGen và một tầng kiểm chứng tất định độc lập với mô hình ngôn
ngữ.

Về **kết quả định lượng**: hệ thống đạt **78,7% ± 6,6** độ chính xác trên bộ đề giữ riêng
150 bài (ngưỡng ≥ 75%) và **600/600 lượt dưới 45 giây** trên toàn bộ ba bộ đề (ngưỡng
≤ 45 s). Chênh lệch giữa bộ phát triển và bộ giữ riêng chỉ 1,3 điểm — bằng chứng cho thấy
các cải tiến tổng quát thật. Chỉ số tỉ lệ phát hiện lời giải sai đạt 53,1%, **chưa đạt**
ngưỡng 85%, với nguyên nhân đã được truy vết tới tận gốc: chất lượng trích xuất của mô
hình 4 tỉ tham số.

Về **đóng góp kỹ thuật**: giá trị lớn nhất của hệ thống không nằm ở con số 78,7%, mà ở chỗ
nó **tự phát hiện được lỗi của chính nó** thông qua đường tính toán độc lập — năng lực mà
một lời gọi mô hình đơn lẻ không có. Kết quả tối ưu độ trễ (41,6 giây → 5,1 giây cho vai
tính lại) cho thấy hướng đi đúng là **phân bổ lại trách nhiệm giữa thành phần thần kinh và
thành phần ký hiệu**, chứ không phải cắt token hay hạ chất lượng.

Về **phương pháp**: đề tài duy trì một kỷ luật đo đạc chặt — ba bộ đề rời nhau, một bộ giữ
riêng chưa từng dùng để sửa gì, đáp án bảo đảm đúng theo kiến tạo và được SymPy kiểm lại,
mọi cải tiến đặt sau cờ để đối chứng A/B, và mọi hạn chế được báo cáo nguyên trạng. Ca
nghiên cứu ở Mục 4.4 — một phép kiểm báo đạt suốt nhiều ngày mà chưa từng chạy — là bài
học phương pháp có giá trị vượt ra ngoài phạm vi đề tài này.

---
---

# TÀI LIỆU THAM KHẢO

1. Wu, Q., Bansal, G., Zhang, J., Wu, Y., Li, B., Zhu, E., Jiang, L., Zhang, X., Zhang,
   S., Liu, J., Awadallah, A. H., White, R. W., Burger, D., Wang, C. (2023). *AutoGen:
   Enabling Next-Gen LLM Applications via Multi-Agent Conversation*. arXiv:2308.08155.

2. Hong, S., Zhuge, M., Chen, J., Zheng, X., Cheng, Y., Zhang, C., Wang, J., Wang, Z.,
   Yau, S. K. S., Lin, Z., Zhou, L., Ran, C., Xiao, L., Wu, C., Schmidhuber, J. (2024).
   *MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework*. ICLR 2024.

3. Nguyen, D. Q., Nguyen, A. T. (2020). *PhoBERT: Pre-trained language models for
   Vietnamese*. Findings of EMNLP 2020.

4. Qwen Team, Alibaba Cloud. *Qwen3 Technical Report* (2025).

5. Meurer, A. và cộng sự (2017). *SymPy: symbolic computing in Python*. PeerJ Computer
   Science 3:e103.

6. Ollama. Tài liệu chính thức. <https://ollama.com>

7. FastAPI. Tài liệu chính thức. <https://fastapi.tiangolo.com>

8. Thư viện `underthesea` — bộ công cụ xử lý ngôn ngữ tự nhiên tiếng Việt.
   <https://github.com/undertheseanlp/underthesea>

**Tài nguyên gợi ý của đề tài — tình trạng sử dụng:**

| Tài nguyên | Tình trạng | Cụ thể |
|---|---|---|
| `microsoft/autogen` | ✅ **Dùng thật** | `autogen-agentchat>=0.7`, `autogen-ext[ollama]>=0.7`; lớp vỏ chung của các tác tử ở `agents/base.py` |
| MetaGPT | ⚠️ Tham khảo ý tưởng | Kế thừa tư tưởng **role specialization**, **không dùng mã nguồn** |
| WolframAlpha API | ❌ Không dùng | Cần khoá API và kết nối mạng, trái với yêu cầu chạy ngoại tuyến; SymPy thay thế được toàn bộ phần tính toán |

---
---

# PHỤ LỤC

## Phụ lục A. Quy trình dựng lại toàn bộ số liệu báo cáo

Tổng thời gian máy chạy khoảng **3–4 giờ**.

```powershell
cd E:\DeepLearning\ViMultiAgent\backend

# 1. Tắt ghi kho lời giải để phép đo đứng yên
#    (đặt VMA_LUU_LOI_GIAI_MAU=0 trong .env, khởi động lại backend)

# 2. Tự kiểm bộ đề trước — bộ đề sai thì mọi số sau đều vô nghĩa
python eval/kiem_de_chuan.py

# 3. Chỉ số 1 + 3: độ chính xác và ma trận Verify, 150 bài (~80 phút)
python scripts/bench.py --de eval/data/de_chuan.csv --out reports/chuan
python scripts/bench.py --de eval/data/de_giu_rieng.csv --out reports/giu_rieng

# 4. Trần năng lực: bộ đề khó 300 bài (~160 phút, chạy qua đêm)
python scripts/bench.py --de eval/data/de_kho.csv --out reports/kho

# 5. Phần học sâu: bảng so sánh ba phương pháp phân loại
python ml/compare.py

# 6. Kiểm thử tất định (không cần Ollama, ~14 giây)
python -m pytest

# 7. Đường đánh đổi accuracy–latency: lặp bước 3 với ba khối A/B/C trong .env.example
```

Kết quả CSV nằm ở `eval/reports/`.

> **Lưu ý:** máy khác GPU thì **thời gian sẽ khác, độ chính xác thì không** — độ chính xác
> chỉ phụ thuộc mô hình và cấu hình. Nếu độ chính xác lệch, kiểm tra `/api/health` và
> `.env` trước tiên.

## Phụ lục B. Bảng cấu hình đầy đủ

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `VMA_MODEL_HEAVY` | `qwen3:4b` | Mô hình cho Subject Agent và Verify |
| `VMA_MODEL_LIGHT` | `qwen3:4b` | Mô hình cho Planner, Router, Explain |
| `VMA_SLA_SECONDS` | `45` | Mốc thời gian mục tiêu cho một lượt hỏi |
| `VMA_AGENT_TIMEOUT` | `60` | Hạn cho một lượt gọi tác tử |
| `VMA_TIMEOUT_RECOMPUTE` | `20` | Hạn riêng cho bộ tính lại |
| `VMA_MAX_RETRY_ROUNDS` | `0` | Số lần Verify được bắt giải lại |
| `VMA_AGENTS_SUY_NGHI` | *(rỗng)* | Tác tử nào được bật chế độ suy nghĩ của Qwen3 |
| `VMA_NUM_CTX` | `4096` | Cửa sổ ngữ cảnh (đặt 1900 cho máy VRAM chật) |
| `VMA_TEMPERATURE` | `0.2` | Nhiệt độ sinh |
| `VMA_MAX_TOKENS_PLANNER` | `400` | **Không hạ xuống 250** |
| `VMA_MAX_TOKENS_ROUTER` | `150` | |
| `VMA_MAX_TOKENS_SUBJECT` | `1100` | |
| `VMA_MAX_TOKENS_VERIFY` | `350` | |
| `VMA_MAX_TOKENS_EXPLAIN` | `900` | Nới từ 700 vì 54% lời giảng bị cắt |
| `VMA_MAX_TOKENS_RECOMPUTE` | `2200` | |
| `VMA_LOC_TINH_LAI_DO_DANG` | bật | Chặn kết quả tính lại còn ẩn |
| `VMA_KIEM_KHOI_LUONG_MOL` | bật | Soát M(chất) bằng `chem_tool` |
| `VMA_DUNG_SAI_KHOI_LUONG_MOL` | `0.015` | Dung sai 1,5% cho cách làm tròn của SGK |
| `VMA_BO_QUA_LLM_REVIEW` | bật | Bỏ LLM khi phép kiểm tất định đủ căn cứ |
| `VMA_DUNG_KHO_DINH_LY` | bật | Chèn công thức vào prompt |
| `VMA_DUNG_KHO_LOI_GIAI` | bật | Chèn ví dụ mẫu |
| `VMA_LUU_LOI_GIAI_MAU` | bật | Cất lời giải đã kiểm chứng (**tắt khi đo**) |

Đổi `.env` xong phải **khởi động lại backend** thì mới có hiệu lực.

## Phụ lục C. Câu hỏi thường gặp và trả lời có căn cứ

| Câu hỏi | Trả lời |
|---|---|
| Vì sao chọn mô hình 4B mà không lớn hơn? | 8B nặng 6,0 GB, tràn 27% xuống CPU, tốc độ còn 16,3 token/giây — chậm gấp 4,5 lần, trượt mốc 45 giây |
| Máy cấu hình tối thiểu là gì? | GPU 4 GB (mô hình chiếm 2,9 GB), RAM 8 GB, ổ trống 12 GB |
| Có bao nhiêu kiểm thử? | 222, chạy trong 14 giây, không cần Ollama |
| Sao không dùng WolframAlpha như đề bài gợi ý? | Cần khoá API và kết nối mạng, trái yêu cầu chạy ngoại tuyến; SymPy thay được toàn bộ phần tính toán |
| Sai số ±6,6 tính thế nào? | Khoảng tin cậy 95% cho tỉ lệ trên mẫu n = 150 |
| Vì sao tắt vòng giải lại? | Đo được là lỗ ròng: 17/20 khi bật so với 18/20 khi tắt, và tốn thêm 5 giây mỗi lượt |
| Trang web có huấn luyện Qwen không? | **Không.** Qwen chỉ được dùng suy luận qua HTTP. Mô hình duy nhất nhóm huấn luyện là PhoBERT (~12 phút trên CPU) |
| Trọng số mô hình để ở đâu? | Qwen do Ollama quản lý ở `~/.ollama/models`; PhoBERT (517 MB) sinh ra khi chạy `train_phobert.py`. Cả hai **không nằm trong repo** vì vượt hạn mức 100 MB của GitHub |
| Mất bao lâu để huấn luyện? | PhoBERT ~12 phút trên CPU, một lần. Cài đặt từ máy trắng 30–45 phút. Chạy đo đầy đủ 600 bài ~4 giờ |

## Phụ lục D. Bộ tài liệu kèm theo

| Tệp | Trả lời câu hỏi |
|---|---|
| `README.md` | Chạy nhanh thế nào? |
| `INSTALL.md` | Cài trên máy mới thế nào? |
| `HUONGDAN.md` | Dùng và vận hành thế nào? API, script, cấu hình, kịch bản demo |
| `TAILIEU.md` | Bên trong hoạt động ra sao? Số liệu đầy đủ |
| `GIAITRINH.md` | Giải trình: dataset, thời gian train, đối chiếu chỉ số |
| `ppt.md` | Nội dung 14 slide báo cáo |
| **`BAOCAO.md`** | **Báo cáo đề tài (tài liệu này)** |
