# ViMultiAgent — Tài liệu kỹ thuật

Mô tả **trạng thái hiện tại của mã nguồn**. Mọi con số trong tài liệu này đều là
số đo thật, kèm cỡ mẫu và cấu hình đã dùng.

Cập nhật: 2026-08-10 · 222 kiểm thử đạt · cấu hình D · đo trên 600 bài

> **Cảnh báo về số liệu.** Ngày 2026-08-10 phát hiện `_check_arithmetic` chưa từng
> chạy được trên lời giải viết bằng công thức chữ (xem 4.6) và đã sửa. Mọi con số
> **chỉ số 3** trong tài liệu này đo TRƯỚC bản sửa đó, nên là **cận dưới** — chúng
> vẫn là số đo trung thực của hệ thống lúc đó, nhưng chưa phản ánh bản hiện tại.
> Các số accuracy và độ trễ không bị ảnh hưởng.

---

## 1. Tổng quan

Hệ thống đa tác tử giải bài tập STEM (Toán – Vật lý – Hoá học) bậc THPT bằng
tiếng Việt, **chạy hoàn toàn ngoại tuyến**, không dùng API key của bất kỳ dịch vụ
nào.

| Thành phần | Công nghệ |
|---|---|
| Khung đa tác tử | AutoGen (`autogen-agentchat`) |
| Mô hình ngôn ngữ | Qwen3:4b qua Ollama, chạy cục bộ |
| Phân loại môn học | PhoBERT fine-tune (nhóm tự huấn luyện) |
| Tính toán tất định | SymPy, Pint, bộ công cụ hoá tự viết |
| Backend | FastAPI + SSE |
| Frontend | React + TypeScript + Vite + KaTeX |
| Lưu trữ | SQLite |

### Nguyên tắc xuyên suốt

> **LLM quyết định LÀM GÌ, công cụ quyết định KẾT QUẢ LÀ BAO NHIÊU.**

Mô hình 4B chọn hướng giải khá tốt nhưng tính toán không đáng tin. Vì vậy mọi con
số quy được về số thuần đều do SymPy quyết định, không phải do mô hình.

---

## 2. Luồng xử lý

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
 Verify ───────► 5 phép kiểm tất định + LLM review
    │
    ▼
 Chốt đáp án ──► phát sự kiện `dap_an` cho giao diện
    │
    ▼
 Explain ──────► giảng bài, streaming từng chữ
    │
    ▼
 (xong — đồng hồ đo độ trễ dừng ở đây)

    ┈┈┈┈┈┈ NGOÀI luồng đo, do người dùng bấm nút ┈┈┈┈┈┈
    ▼
 Sinh bài tương tự ──► POST /api/bai_tuong_tu, không gọi LLM, ~43 ms
```

Manager là một **async generator**: phát sự kiện ngay khi từng agent xong việc,
nhờ vậy giao diện vẽ được tiến trình theo thời gian thực.

Tác tử Sinh bài tập tương tự cố ý **nằm ngoài** `solve_stream`. Gộp vào là cộng
thẳng thời gian sinh đề vào chỉ số độ trễ end-to-end — thứ tốn nhiều công nhất mới
đạt được 600/600 bài dưới 45 giây.

---

## 3. Tám tác tử

Bản yêu cầu đòi năm vai (phân tích đề · giải · kiểm tra · giải thích · sinh bài
tương tự). Hệ thống có đủ cả năm, cộng ba vai nhóm tự thêm: **Router** (định tuyến
môn bằng PhoBERT) và **bộ tính lại độc lập** — hai thứ không có trong yêu cầu
nhưng là nơi phần lớn độ tin cậy đến từ đó. Ba Subject Agent tính là một vai.

### 3.1 Planner Agent

Đọc hiểu đề, **không giải**. Trả về `Plan` gồm: `subject`, `topic`,
`question_type`, `givens`, `unknowns`, `choices`, `normalized_question`,
`steps_outline`, `confidence`.

**Chốt chặn đáng chú ý** — `_giu_nguyen_so_lieu()`: bản chuẩn hoá chỉ được giữ khi
dãy chữ số khớp tuyệt đối với đề gốc.

> Đo được: qwen3:4b chép `x = 5cos(10πt)` thành `x = 5cos(1:0πt)` và `R = 110 Ω`
> thành `R = 1:110 Ω`. JSON hoàn chỉnh, `done_reason` là "stop" — model thật sự
> viết sai chứ không phải bị cắt. Hậu quả nặng: mọi agent phía sau giải rất đúng
> trên một đề đã hỏng, và không tầng kiểm chứng nào phát hiện vì chúng đối chiếu
> với đề ĐÃ SAI.

**Không được hạ trần token xuống 250.** Đo trên cùng 20 bài: 400 token cho 18/20
đúng, 250 token chỉ 13/20 — mất 5 bài để đổi lấy 2,6 giây.

### 3.2 Router Agent

Chọn Subject Agent theo ba tầng, rẻ trước đắt sau:

```
PhoBERT (~50 ms)  →  luật từ khoá (0 ms)  →  LLM (2–4 giây)
```

Đo trên 150 bài: **PhoBERT quyết định 94,7%**, luật từ khoá 2,7%, LLM 2,7%. Thời
gian trung bình của cả vai: **0,05 giây**.

**PhoBERT chỉ được chốt khi luật từ khoá không phản đối.** Lý do rút từ lỗi thật:
câu xác suất bi bị PhoBERT xếp vào Vật lý với độ tin cậy 0,90; câu dao động điều
hoà bị xếp vào Toán với 0,86. Độ tin cậy cao mà vẫn sai nên nâng ngưỡng vô ích —
nguyên nhân là lệch phân bố: dữ liệu huấn luyện gồm câu ngắn, đề vận dụng thì dài
nhiều mệnh đề. Luật từ khoá ngược lại, càng dài càng chắc. Hai nguồn bù khuyết
cho nhau; bất đồng thì đẩy xuống LLM.

### 3.3 Ba Subject Agent

Toán, Lý, Hoá — chung khung `subject.py`, khác nhau ở system prompt. Đây chính là
**role specialization**: cùng mô hình nền, khác vai trò và kỷ luật chuyên môn.

Ràng buộc `min_length=1` trên `Solution.steps` đi thẳng vào grammar JSON của
Ollama, nên mô hình **không thể** sinh mảng rỗng — mạnh hơn mọi lời dặn trong
prompt. Trước khi có ràng buộc này, mô hình từng buột ra đáp số với `steps` rỗng
và `confidence` 1.0, khiến toàn bộ tầng kiểm chứng mất tác dụng.

### 3.4 Bộ tính lại độc lập (recompute)

Chạy **song song** với Subject Agent. Đây là vai được cải tổ lớn nhất.

**Kiến trúc cũ**: bắt mô hình vừa suy luận vừa cho ra một biểu thức đã thay số.
Đo được: **42,4 giây** mỗi lượt, và chỉ cho kết quả dùng được ở **~16%** số bài.

**Kiến trúc hiện tại**: tách đôi trách nhiệm.

| Bước | Ai làm | Chi phí |
|---|---|---|
| Trích cấu trúc bài toán: loại bài, hàm gốc, biến, cận | LLM, **tắt suy nghĩ** | ~5 giây |
| Lấy đạo hàm / tính tích phân / thế nghiệm | **SymPy** | ~0 giây |

Mô hình chỉ **chép lại đề** dưới dạng máy đọc được. Kết quả: **5,1 giây**, ẩn hoàn
toàn dưới Subject Agent (8,1 giây), và kết luận là tất định thay vì phỏng đoán.

**Hai chốt chặn bắt buộc:**

1. `_loai_kiem_hop_le()` — loại bài mô hình khai phải khớp **từ khoá trong đề gốc**.
   Đo được: 33/34 ca báo oan là do mô hình gán nhầm. Điển hình là đề *"Cho
   f(x) = 3x² + 5x − 1, tính f(3)"* bị gán `dao_ham`, SymPy tính đạo hàm tại 3 ra
   23 trong khi đáp án đúng là giá trị hàm số 41, rồi kết luận lời giải sai.

2. `_con_ky_hieu_tu_do()` — đề hỏi một con số mà kết quả còn ẩn thì coi như chưa
   tính xong. Trước khi có chốt này, cơ chế cứu đáp án lấy nguyên hàm chưa thay cận
   (`x*(3x+4)`) đè lên đáp số **đúng**, làm hỏng 6 bài trên 150.

### 3.5 Verify Agent

**Không tin LLM.** Chạy các phép kiểm tất định trước, rồi mới đưa kết quả cho LLM
đọc. Làm ngược lại thì mô hình 4B sẽ "đồng ý" với lập luận trôi chảy nhưng sai.

**Một phép kiểm tất định thất bại là FAIL, bất kể LLM nói gì.**

Năm phép kiểm tất định:

| Phép kiểm | Áp dụng cho | Cơ chế |
|---|---|---|
| `_check_answer_present` | mọi bài | có bước giải và đáp số không |
| `_check_arithmetic` | mọi bài | SymPy tính lại từng bước **sau khi thế ký hiệu**, ngưỡng lệch 1% |
| `_check_units` | Vật lý | soát thứ nguyên bằng Pint |
| `_check_chemistry` | Hoá | bảo toàn nguyên tố, kèm phương trình cân bằng đúng |
| `_check_khoi_luong_mol` | Hoá | đối chiếu M(chất) với bảng nguyên tử khối |

Cộng thêm phép kiểm từ bộ tính lại độc lập.

**Đường tắt**: khi không phép kiểm nào hỏng **và** bộ tính lại đã xác nhận đáp số,
bỏ luôn lượt gọi LLM. Điều kiện thứ hai là mấu chốt — thiếu nó thì "mọi phép kiểm
đều đạt" có thể chỉ nghĩa là chẳng phép kiểm nào chạy được.

### 3.6 Explain Agent

Ràng buộc cứng: **không được sinh đáp án mới**, chỉ diễn đạt lại lời giải đã chốt.

Đây là agent duy nhất chạy streaming, và là agent duy nhất **gọi thẳng thư viện
`ollama`** thay vì qua AutoGen — vì cần mồi sẵn câu mở đầu.

> Đo được ba cách ép qwen3:4b viết tiếng Việt, cùng một đề:
> - system prompt tiếng Việt, cấm đích danh từ tiếng Anh → **vẫn tiếng Anh**
> - thêm "BẮT BUỘC trả lời bằng TIẾNG VIỆT" ở cuối user → **vẫn tiếng Anh**
> - mồi sẵn `**Tóm tắt đề**\n` vào lượt trợ lý → **tiếng Việt**
>
> Mô hình 4B phớt lờ chỉ dẫn nhưng không thể phớt lờ văn bản nó đang phải viết tiếp.

Trần token đặt **900**, không phải 700: đo được 54% lời giảng chạm trần 700 và bị
cắt giữa chừng. Ở 900 tỉ lệ này còn 32%.

### 3.7 Tác tử Sinh bài tập tương tự

`agents/sinh_bai_tuong_tu.py` — vai thứ năm của bản yêu cầu. Giải xong một bài thì
sinh **một** bài cùng dạng để học sinh tự luyện.

**Không dùng LLM.** Mô hình 4B trong dự án này từng tính 0,1 × 62 = 3,8; một đề do
nó bịa ra sẽ mang đúng chất lượng đó. Đề sai đưa cho học sinh còn tệ hơn không đưa
gì — người học không có cách nào biết mình sai hay đề sai.

Thay vào đó dùng lại **175 mẫu đề tham số hoá** trong `eval/` — chính bộ đã dựng
600 bài ground truth. Mỗi mẫu mã hoá sẵn công thức, còn đáp án do Python tính từ
đúng những con số vừa bốc vào đề. **Sai số học là không thể xảy ra về mặt kiến tạo.**

Đây vẫn là *sinh* chứ không phải *tra cứu*: mỗi lần gọi bốc một bộ tham số mới, nên
cùng một mẫu cho ra vô số đề khác nhau (có test chứng minh).

Cách tìm mẫu — tụt dần bốn nấc, dừng ở nấc đầu tiên có kết quả:

1. cùng môn **và** trùng khít `topic`
2. cùng môn và `topic` chứa nhau
3. cùng môn và cùng mức độ
4. cùng môn

Không có mẫu nào thì **trả `None`**, không bịa — giống mọi tầng tất định khác.

So `topic` phải **bỏ dấu trước**: Planner sinh `khối_lượng_mol` còn mẫu ghi
`khoi_luong_mol`. Đã có lần chấm điểm chủ đề không bao giờ khớp chỉ vì thiếu bước
này, nên có test riêng chốt lại.

| | |
|---|---|
| Số mẫu | 175 (61 Toán · 57 Lý · 57 Hoá) |
| Thời gian đáp ứng | **43 ms** (gồm cả lần nạp kho đầu tiên) |
| Số lượt gọi LLM | **0** |
| Bảo đảm đáp án | tính bằng công thức, có test soát toàn bộ 175 mẫu bằng SymPy |

Giao diện giấu đáp án sau một nút bấm, kèm nút "Gợi ý" chỉ đưa công thức cần dùng.
Hiện sẵn đáp số thì bài luyện mất hết tác dụng.

---

## 4. Tầng kiểm chứng tất định

Bốn module trong `tools/`, tổng 32 hàm. Điểm chung: **không tốn token nào**, kết
luận không bao giờ sai.

### 4.1 `sympy_tool.py`

Parse biểu thức chịu được LaTeX bẩn mà mô hình hay sinh. Hàm quan trọng nhất là
`check_substitution` — thế nghiệm ngược vào phương trình gốc.

### 4.2 `arbiter.py` — trọng tài số học

Với mỗi bước, nếu vế phải của `expression` quy được về **một số thuần** thì giá trị
đó **ghi đè** lên `result` của mô hình. Không xin phép.

Chỉ can thiệp khi thoả toàn bộ: (1) vế phải ra một số, không còn ký hiệu tự do,
(2) `result` cũng đọc ra được một số, (3) hai số lệch **quá 1%**.

Ngưỡng 1% có chủ đích: mô hình làm tròn 0,39738 thành 0,397 là hợp lệ. Sai số học
thật thì lệch hàng chục phần trăm hoặc sai dấu.

### 4.3 `chem_tool.py`

Không phụ thuộc thư viện ngoài. Tự cài đặt:

- **Khối lượng mol** — parser công thức có ngoặc lồng và muối ngậm nước (`CuSO4.5H2O`)
- **Cân bằng phương trình** — giải bằng không gian null của ma trận nguyên tố

Khi mô hình sai hệ số, phản hồi **kèm luôn phương trình đúng** để vòng sau có cái
mà sửa thay vì đoán lần nữa.

### 4.4 `kiem_symbolic.py`

Cho SymPy **tự giải lại** bài toán. Năm loại kiểm được: `dao_ham`, `tich_phan`,
`gioi_han`, `phuong_trinh`, `tiep_tuyen`.

Ba trạng thái trả về, và trạng thái thứ ba khó nhất:

| Trả về | Nghĩa |
|---|---|
| `True` | SymPy tính lại và khớp đáp án |
| `False` | SymPy tính lại và **khác** đáp án |
| `None` | **không đủ căn cứ — tuyệt đối không đoán** |

Hàm `_khop()` so ba tầng: rút gọn tượng trưng → hiệu quy về số → **thử tại nhiều
điểm**. Tầng thứ ba là chỗ bản đầu tiên thiếu, khiến `7x + 1` so `5x + 5` trả về
"không so sánh được" thay vì "khác nhau" — tức tiếp tuyến sai lọt lưới.

### 4.5 `units_tool.py`

Kiểm thứ nguyên bằng Pint, có bảng ánh xạ ký hiệu tiếng Việt (`lít`, `gam`, `Ω`).

### 4.6 Thế ký hiệu trong `_check_arithmetic` — và một phép kiểm chưa từng chạy

Đây là ca đáng ghi lại nhất của dự án, vì nó minh hoạ một dạng lỗi nguy hiểm hơn
lỗi sai: **phép kiểm báo đạt trong khi nó không hề chạy.**

Ngày 2026-08-10, chạy thử giao diện với đề *"đốt cháy hoàn toàn 4,6 gam Na trong
O₂ dư"*. Lời giải trả về:

| Bước | `expression` | `result` | |
|---|---|---|---|
| 2 | `nNa = mNa/MNa` | 0,2 mol | đúng |
| 3 | `nNa2O = nNa/2` | 0,1 mol | đúng |
| 4 | `mNa2O = nNa2O * MNa2O` | **3,8 g** | **sai, phải là 6,2** |

Verify vẫn kết luận *"số học các bước khớp"*. Nguyên nhân nằm ở bản cũ:

```python
rhs = expr.split("=")[-1]
a = sympy_tool.evaluate(rhs)
if va is None or vb is None:
    continue          # <- rơi vào đây
```

Mô hình gần như **luôn** viết vế phải bằng công thức chữ và chỉ để con số ở
`result`. SymPy gặp toàn ký hiệu tự do nên trả `None`, và bước bị bỏ qua im lặng.
Cả 4 bước đều bị bỏ qua, rồi hàm vẫn trả về `passed=True`.

Hệ quả kép, và vế thứ hai mới nặng: Verify Agent **đọc dòng "số học khớp" đó** rồi
yên tâm kết luận PASS. Một phép kiểm chết không chỉ vô dụng — nó còn phát ra tín
hiệu giả làm hỏng phán đoán của tầng phía trên.

**Bản sửa** thế giá trị vào ký hiệu trước khi tính, lấy từ hai nguồn:

| Nguồn | Ví dụ |
|---|---|
| Vế trái các bước **trước** | `nNa2O` = 0,1 lấy từ kết quả bước 3 |
| Bảng nguyên tử khối | `MNa2O` → `chem_tool.molar_mass` = 61,98 |

Thế ở mức **văn bản** chứ không qua SymPy, vì `implicit_multiplication_application`
xé `nNa2O` thành `n*N*a**2*O` và ký hiệu ghép sẽ không bao giờ khớp bảng tra.

Ba chốt chặn báo oan:

- **Thiếu dù một ký hiệu là bỏ qua bước.** Thà không kiểm còn hơn kiểm bừa.
- **Lệch đúng một luỹ thừa của 10 thì bỏ qua.** Ca thật phải chặn: bước 1 ghi
  `A = 6 cm`, bước 3 dùng `v = A·ω` với A tính bằng mét — thế thẳng ra 120 trong
  khi bước ghi 1,2. Lời giải đúng, chỉ là ký hiệu đổi đơn vị giữa chừng. Cái giá
  phải trả là bỏ sót lỗi lệch đúng 10 lần; chấp nhận được vì báo oan phá cả lời
  giải đúng, còn bỏ sót chỉ là không cải thiện.
- **Báo cáo trung thực.** Dòng kết luận giờ ghi rõ *"Số học khớp ở 2/4 bước thế
  được số"* hoặc *"chưa kiểm được số học"*, không còn khẳng định suông.

`tests/test_so_hoc_the_ky_hieu.py` chốt cả ba, dựng lại nguyên ca thật.

> **Bài học phương pháp, đáng đưa vào báo cáo.** Bộ kiểm thử 181 bài lúc đó **đều
> đạt**, vì không test nào dựng lời giải viết bằng công thức chữ — đúng dạng mà mô
> hình luôn sinh ra. Lỗi chỉ lộ ra khi có người ngồi đọc một đáp án cụ thể trên
> giao diện. Test bảo vệ được điều ta nghĩ tới; chỉ có dùng thật mới lộ ra điều ta
> không nghĩ tới.

---

## 5. Cơ chế cứu đáp án

Nằm ở `manager.py`. Hai tình huống, cùng một nguyên tắc:

1. Subject Agent không ra được đáp số nào
2. Ra đáp số nhưng **không qua được kiểm chứng**, và công cụ tính ra số khác

Cả hai đều lấy giá trị của bộ tính lại độc lập, kèm cảnh báo rõ ràng trên giao diện.

**Lời giải ĐÃ qua kiểm chứng thì tuyệt đối không đụng vào.**

Đo được trên 150 bài ở cấu hình hiện tại: cơ chế này **không kích hoạt lần nào**,
vì Subject Agent và bộ tính lại hiếm khi bất đồng sau khi có các chốt chặn.

---

## 6. Memory pool

Hai kho, tra cứu bằng từ khoá và `Plan.topic`. **Không dùng embedding** — thêm một
mô hình nhúng là thêm vài trăm MB RAM tranh chỗ với Ollama trên máy 6 GB VRAM.

### 6.1 `kho_dinh_ly.py`

Khoảng 70 mục công thức chương trình THPT. Chấm điểm hai nguồn: `topic` khớp được
3 điểm, mỗi từ khoá trúng 1 điểm. Lấy tối đa 3 mục, dưới ngưỡng thì **trả rỗng** —
chèn công thức lạc đề còn tệ hơn không chèn gì.

So topic **sau khi bỏ dấu**: prompt dặn Planner sinh slug không dấu nhưng mô hình
trả về `khối_lượng_mol`; so thẳng thì điểm khớp topic không bao giờ kích hoạt.

### 6.2 `kho_loi_giai.py`

Bảng SQLite riêng, **chỉ cất lời giải có verdict PASS và không kèm cảnh báo**. Cất
lời giải sai là tự đầu độc.

Hai chi tiết phòng thủ: kho **không bao giờ trả về chính câu đang giải** (nếu không
hệ thống chỉ chép đáp án cũ), và mọi lỗi truy cập kho đều bị nuốt.

**Kết quả đo trung thực**: trên 50 bài Hoá, có và không có memory pool đều cho
**42/50**. Ba bài được cứu, ba bài bị làm hỏng — triệt tiêu nhau. Không có bằng
chứng nó cải thiện độ chính xác.

---

## 7. Yếu tố học sâu

Cần tách bạch hai thứ.

### 7.1 PhoBERT fine-tune — phần nhóm tự huấn luyện

| | |
|---|---|
| Mô hình nền | `vinai/phobert-base`, 135 triệu tham số |
| Nhiệm vụ | phân loại 3 lớp Toán / Lý / Hoá |
| Dữ liệu | **810 câu tự xây**: 535 train · 116 val · 159 test |
| Trọng số | 517 MB, huấn luyện ~12 phút trên CPU |
| Suy luận | ~50 ms mỗi câu, chạy CPU |

Tập test chia theo nguồn: `seed` 47 câu, `template` 67, **`hard` 45**. Con số trên
nhóm template gần như luôn đẹp; chỉ nhóm `hard` mới phân định được các phương pháp.

`ml/segment.py` tách từ tiếng Việt bằng `underthesea` — **bắt buộc** với PhoBERT.

`ml/compare.py` đối chiếu ba phương pháp: luật từ khoá / TF-IDF + Logistic
Regression / PhoBERT. Mốc TF-IDF là mốc so sánh quan trọng nhất — nếu PhoBERT không
vượt được nó thì dùng transformer ở đây là thừa, và phải nói thẳng điều đó.

### 7.2 Qwen3:4b — học sâu nhưng KHÔNG do nhóm huấn luyện

Nhóm chỉ **sử dụng suy luận**, không huấn luyện, không tinh chỉnh. Trình bày nó như
đóng góp học sâu của nhóm là không trung thực.

---

## 8. Cấu hình

`.env` hiện đặt **cấu hình D**:

```
VMA_SLA_SECONDS=45.0
VMA_AGENTS_SUY_NGHI=          # tắt chế độ suy nghĩ của Qwen3
VMA_MAX_RETRY_ROUNDS=0        # tắt vòng giải lại
VMA_TIMEOUT_RECOMPUTE=20.0
```

Các bản sửa đều đặt sau cờ, bật/tắt được để đối chứng A/B:

| Cờ | Mặc định | Tác dụng |
|---|---|---|
| `VMA_LOC_TINH_LAI_DO_DANG` | bật | chặn kết quả tính lại còn ẩn |
| `VMA_KIEM_KHOI_LUONG_MOL` | bật | soát M(chất) bằng `chem_tool` |
| `VMA_BO_QUA_LLM_REVIEW` | bật | bỏ LLM khi phép kiểm tất định đủ căn cứ |
| `VMA_DUNG_KHO_DINH_LY` | bật | chèn công thức vào prompt |
| `VMA_DUNG_KHO_LOI_GIAI` | bật | chèn ví dụ mẫu |
| `VMA_LUU_LOI_GIAI_MAU` | bật | cất lời giải đã kiểm chứng |

### Vì sao tắt vòng giải lại

Đo A/B trên **cùng 20 bài**: có vòng giải lại 17/20 đúng, không có 18/20. Nó cứu
được 1 bài nhưng làm hỏng 2, và tốn thêm 5 giây mỗi lượt.

Nguyên nhân đã truy được: vòng giải lại được kích hoạt bởi Verify, mà Verify báo
oan tới 18–28%. Phần lớn lần giải lại là đi **sửa một lời giải vốn đã đúng**.

Bỏ nó không phải cắt xén — **vòng sửa sai vẫn còn nguyên trong mã nguồn**, bật lại
là một dòng cấu hình.

---

## 9. Hạ tầng đo đạc

### 9.1 Ba bộ đề, rời hẳn nhau

| Bộ | Số bài | Dùng để |
|---|---|---|
| `de_chuan.csv` | 150 | phát triển và gỡ lỗi |
| `de_giu_rieng.csv` | 150 | **kiểm chứng sạch** — chưa dùng |
| `de_kho.csv` | 300 | dò trần năng lực, 90 bài vận dụng cao |

Sinh bằng `build_de_chuan.py` và `build_de_kho.py`: mỗi mẫu đề mã hoá sẵn một công
thức, **đáp án do Python tính từ chính các số đưa vào đề**. Sai số học là không thể
xảy ra về mặt kiến tạo.

`kiem_de_chuan.py` dùng SymPy đối chiếu lại cột `bieu_thuc_kiem`. Cả ba bộ đều đạt
**100%**.

Bộ giữ riêng dùng tham số `--tranh` để loại tường minh mọi câu đã có — chỉ đổi seed
thì vẫn trùng tới 41% vì pool tham số hẹp.

### 9.2 `scripts/bench.py`

Chấm ba nhánh: số (dung sai 2%, **có quy đổi đơn vị**), trắc nghiệm, biểu thức
(rút gọn tượng trưng).

Bộ đọc số đã qua ba vòng sửa, mỗi vòng từ một lỗi đo được:

| Lỗi | Hậu quả |
|---|---|
| Bóc số dẫn đầu thay vì tính biểu thức | `5/36`→5, `√73`→73; chấm oan 4 bài |
| So số trần không quy đổi đơn vị | `0,0018 m` bị coi khác `1,8 mm` |
| Không đọc được `\frac` lồng nhau và `e` là cơ số tự nhiên | chấm oan 4 bài, **tất cả ở mức vận dụng cao** |

Báo cáo tách **hai thời điểm đo**: chỉ số 1 chấm trên đáp án cuối (sau bước cứu),
chỉ số 3 chấm trên đáp án của Subject Agent (**trước** bước cứu). Trộn hai thứ là
sai lệch nghiêm trọng — bài mà Subject sai, Verify bắt đúng, rồi Manager cứu thành
công sẽ bị đếm thành "Verify báo oan".

### 9.3 Công cụ phụ trợ

| Script | Việc |
|---|---|
| `tien_do.py` | báo tiến độ một lượt bench đang chạy |
| `cuu_log.py` | cứu kết quả khi bench bị ngắt giữa chừng |
| `cham_lai.py` | chấm lại kết quả đã có bằng bộ đọc số mạnh hơn |
| `soi_verify.py` | in toàn bộ phép kiểm của Verify trên một bài cụ thể |

`eval/phieu_cham.py` dựng file HTML tự chứa (754 KB, nhúng KaTeX) để giáo viên
chấm chất lượng lời giảng, kèm mẫu neo và script gộp điểm.

---

## 10. Kết quả đo

Toàn bộ số liệu dưới đây đo ở **cấu hình D**, trên **600 bài** thuộc ba bộ đề rời
nhau. Bộ đọc số đã chấm lại bằng bản mạnh nhất: **0 bài chấm oan** ở cả ba bộ.

### 10.1 Bảng tổng hợp

| Bộ đề | n | Accuracy | Đạt 45s | Phát hiện sai | Báo oan |
|---|---|---|---|---|---|
| Chuẩn | 150 | 80,0% ± 6,4 | **150/150** | 60,0% | 18,3% |
| **Giữ riêng** | 150 | **78,7% ± 6,6** | **150/150** | 53,1% | 11,0% |
| Khó | 300 | 72,0% ± 5,1 | **300/300** | 45,2% | 15,7% |

**600/600 lượt dưới 45 giây**, không có ngoại lệ nào trên cả ba bộ.

### 10.2 Con số nộp báo cáo

Nên lấy từ **bộ giữ riêng**, không phải bộ chuẩn.

Mọi bản sửa trong dự án đều rút ra từ `de_chuan.csv` — bộ đọc số, chốt chặn
`loai_kiem`, kiến trúc recompute, cơ chế cứu. Con số trên bộ đó **không còn là phép
thử độc lập**. Bộ giữ riêng trùng 0% và chưa từng được dùng để sửa gì.

| Chỉ số | Ngưỡng | Bộ giữ riêng | |
|---|---|---|---|
| Accuracy | ≥ 75% | **78,7% ± 6,6** | ✅ |
| Latency | ≤ 45s | **150/150 = 100%**, tb 30,4s | ✅ |
| Phát hiện sai (chặt) | ≥ 85% | 53,1% * | ❌ |
| Phát hiện sai (nới) | ≥ 85% | 71,9% * | ❌ |
| Explanation quality | ≥ 4/5 | **đã bỏ theo yêu cầu** | — |

\* Đo khi `_check_arithmetic` còn hỏng (mục 4.6). Hiểu là **cận dưới** của bản hiện
tại. Muốn có số đúng phải chạy lại `bench.py`.

**Chênh lệch giữa bộ chuẩn và bộ giữ riêng chỉ 1,3 điểm** (80,0% so với 78,7%),
nằm gọn trong sai số ±6,6. Đây là bằng chứng các cải tiến **tổng quát thật**, không
phải may đo riêng cho bộ phát triển.

### 10.3 Theo mức độ — điểm gãy rất rõ

| Mức | Bộ chuẩn | Bộ giữ riêng | Bộ khó |
|---|---|---|---|
| Nhận biết | 97,6% | 90,4% | 75,7% |
| Thông hiểu | 73,9% | 80,4% | 82,6% |
| Vận dụng | 73,8% | 71,4% | 78,8% |
| **Vận dụng cao** | 70,0% | **52,9%** | **54,4%** |

Vận dụng cao là **điểm gãy duy nhất và nhất quán** trên cả ba bộ. Bộ khó có 90 bài
VDC (30%) so với 20 bài (13%) của bộ chuẩn — đó là lý do chính khiến accuracy tổng
tụt xuống 72,0%.

### 10.4 Theo môn

| Môn | Bộ chuẩn | Bộ giữ riêng | Bộ khó |
|---|---|---|---|
| Toán | 84,0% | 82,0% | 70,0% |
| Lý | 78,0% | 70,0% | **66,0%** |
| Hoá | 78,0% | 84,0% | **80,0%** |

Vật lý là môn yếu nhất trên bài khó; Hoá ổn định nhất — nhiều khả năng nhờ hai phép
kiểm tất định riêng cho môn này (bảo toàn nguyên tố và khối lượng mol).

### 10.5 Bộ nhớ ngữ cảnh

`num_ctx` mặc định hạ từ 8192 xuống **4096**, đo trực tiếp bằng `ollama ps`:

| `num_ctx` | VRAM | Thời gian TB | Lời giảng bị cắt | Model nằm trọn GPU |
|---|---|---|---|---|
| 8192 | 3,3 GB | 30,0s | — | ✅ |
| **4096 (mặc định)** | **2,9 GB** | **30,5s** | 1/20 | ✅ |
| 1900 | 2,7 GB | 30,5s | 1/20 | ✅ |

Nhu cầu ngữ cảnh thật chỉ **~1720 token** (prompt dài nhất 620 + trần đầu ra 1100),
nên 8192 thừa gấp 4,8 lần. Hạ xuống 4096 tiết kiệm **400 MB VRAM** mà tốc độ không
đổi — đủ để máy 4 GB chạy được thay vì đòi 6 GB.

**Vì sao dừng ở 4096 chứ không lấy 1900.** Mức 1900 đã đo và không hỏng gì: độ dài
lời giảng 644 chunk so với 647, cùng cực đại 901, cùng 10,9s. Lý do là Explain bị
chặn bởi **trần token** (900) chứ không phải bởi ngữ cảnh.

Nhưng bộ đề đánh giá có lời giải khá đều, khoảng 5 bước. Người dùng thật có thể hỏi
bài dài hơn:

| Số bước lời giải | Prompt Explain | + 900 đầu ra | 1900 có đủ? |
|---|---|---|---|
| 5 bước | 672 | 1572 | ✅ dư 328 |
| 10 bước | ~880 | 1780 | ⚠️ dư 120 |
| 15 bước | ~1080 | 1980 | ❌ **thiếu** |

Bài 15 bước sẽ bị cắt lời giảng ở 1900 mà vẫn chạy tốt ở 4096. Bộ đề không có bài
nào như vậy nên phép đo không bắt được — đó là **giới hạn của phép đo**, không phải
bằng chứng 1900 an toàn. Đổi 200 MB lấy biên an toàn tụt từ 2,4 lần xuống 1,24 lần
là không đáng cho một giá trị mặc định. **1900 là phương án cho máy VRAM chật**,
đặt qua `VMA_NUM_CTX=1900`, không phải mặc định.

### 10.6 Thời gian

**Đường găng**: `5,5 + 0,0 + max(8,6 ; 5,1) + 4,7 + 11,6 = 30,3 giây`

| Vai | Giây | Ghi chú |
|---|---|---|
| Planner | 5,5 | |
| Router | 0,0 | PhoBERT quyết định 94,7% số bài |
| Subject | 8,6 | |
| Recompute | 5,1 | chạy song song, **ẩn dưới Subject** |
| Verify | 4,7 | |
| Explain | 11,6 | vai tốn nhiều nhất sau khi tối ưu |

Người dùng thấy **đáp án sớm hơn ~11,6 giây** so với lúc lời giảng chảy xong, nhờ
sự kiện `dap_an` phát ngay trước Explain.

### 10.7 Đường đánh đổi accuracy – latency

Ba cấu hình, cùng bộ đề chuẩn 150 bài:

| | A | C | **D** |
|---|---|---|---|
| Accuracy | 80,7% | **90,0%** | 80,0% |
| Đạt mốc 45s | 100% | 3,3% | **100%** |
| Thời gian TB | 30,4s | 65,1s | **30,0s** |
| Phát hiện sai | 60,0% | 31,2% | 60,0% |

Cấu hình C đạt độ chính xác cao nhất nhưng trượt mốc thời gian gần như hoàn toàn.
Nguyên nhân: bật chế độ suy nghĩ cho bộ tính lại khiến vai này tốn 41,6 giây và
**trở thành đường găng** — 149/150 bài có recompute chậm hơn Subject Agent, tức cơ
chế chạy song song mất hết tác dụng.

Cấu hình D đạt tốc độ của A với độ chính xác tương đương, nhờ **đổi kiến trúc** chứ
không phải cắt xén: bộ tính lại chuyển từ "tự suy luận ra đáp số" sang "trích cấu
trúc cho SymPy tự giải".

### 10.8 Bộ đề khó 300 bài (đo ở **cấu hình C**)

Tổng 82,7%. Toán 83,0% · Lý 79,0% · Hoá 86,0%.
Vận dụng cao là điểm gãy rõ nhất: 62,7% (Toán+Lý) và 68,4% (Hoá).

Sáu chủ đề sai gần như toàn bộ: tích phân từng phần, giới hạn, tiếp tuyến (Toán);
điện tích Coulomb, lượng tử, dao động điều hoà (Lý).

Hình học **không** phải điểm yếu — 80,4% so với đại số 77,8%.

---

## 11. Hạn chế đã biết

**Chỉ số 3 chưa đạt.** Hai lần can thiệp gần đây chỉ dịch chuyển cân bằng giữa
"bắt đúng" và "báo oan" chứ không nâng được cả hai:

| | Phát hiện sai | Báo oan |
|---|---|---|
| Trước chốt chặn `loai_kiem` | 70,4% | 27,6% |
| Sau | 60,0% | 18,3% |

Nguyên nhân gốc: tầng kiểm chứng bị giới hạn bởi **chất lượng trích xuất của mô
hình 4B** — nó không phân biệt nổi "tính f(3)" với "tính f'(3)", nên mọi phép kiểm
tất định phía sau đều phải dè dặt.

**Số đo chỉ số 3 đã lỗi thời.** Toàn bộ con số phát hiện sai trong tài liệu này đo
khi `_check_arithmetic` **đang chết** (mục 4.6). Chúng là số đo trung thực của hệ
thống lúc đó và nên hiểu là **cận dưới**. Bản sửa ngày 2026-08-10 chưa được đo lại
trên bộ đề — **đừng trích số mới nào cho tới khi chạy `bench.py`**.

**Bài Hoá không có trọng tài SymPy.** `kiem_symbolic` chỉ nhận năm dạng Toán, nên
`_loai_kiem_hop_le` từ chối mọi bài Hoá. Hệ quả dây chuyền: đường tắt của Verify
đòi "bộ tính lại đã xác nhận độc lập", điều kiện đó không bao giờ thoả với Hoá, nên
**mọi bài Hoá đều phải qua vòng LLM soi lại** — nguồn báo oan lớn nhất còn lại.

**Chỉ số 2 đã bỏ theo yêu cầu.** Công cụ chấm mù vẫn còn trong `eval/`
(`thu_loi_giang.py`, `mau_neo.py`, `phieu_cham.py`) và dựng lại được, nhưng phiếu
đã sinh thì đã xoá. Dữ kiện khách quan duy nhất còn giữ: **0/20 lời giảng bị cắt**.

**Vận dụng cao là điểm gãy nhất quán.** 52,9% trên bộ giữ riêng và 54,4% trên bộ
khó, so với 80–90% ở ba mức còn lại. Đây là giới hạn năng lực thật của mô hình 4B,
không phải lỗi kỹ thuật có thể vá.

**Accuracy trên bộ đề khó là 72,0%**, dưới ngưỡng 75%. Bộ này có 30% bài vận dụng
cao so với 13% của bộ chuẩn — được soạn cố ý khó để **dò trần năng lực**, không
phải để đối chiếu ngưỡng. Con số dùng cho chỉ số 1 nên lấy từ bộ giữ riêng (78,7%).

**Bộ đề tự soạn.** Cột `nguon` ghi `tu_soan` — sinh bằng mẫu có tham số, đáp án
đúng theo kiến tạo, nhưng văn phong đều tay hơn đề thi thật.

**Memory pool chưa chứng minh được giá trị.** Đo trên 50 bài Hoá cho kết quả y hệt
khi tắt (42/50 cả hai).

---

## 12. Kiểm thử

**222 kiểm thử**, chạy trong ~14 giây, không cần Ollama.

| Tệp | Phủ |
|---|---|
| `test_tools.py` | SymPy, hoá học, đơn vị |
| `test_arbiter.py` | trọng tài ghi đè số |
| `test_recompute.py` | so sánh đáp số, chặn kết quả dở dang |
| `test_json_cuu.py` | cứu JSON bị cắt |
| `test_kiem_symbolic.py` | bộ kiểm SymPy và chốt chặn loại bài |
| `test_khoi_luong_mol.py` | soát khối lượng mol |
| `test_bo_qua_llm_review.py` | đường tắt của Verify |
| `test_memory_pool.py` | hai kho |
| `test_bench_cham.py` | bộ đọc số của bench |
| **`test_so_hoc_the_ky_hieu.py`** | thế ký hiệu, chặn báo oan đổi đơn vị, báo cáo trung thực |
| **`test_sinh_bai_tuong_tu.py`** | khớp chủ đề, không trùng đề gốc, **soát đáp án cả 175 mẫu bằng SymPy** |

Đáng chú ý trong bảng: `test_sinh_bai_tuong_tu.py` có một test tính lại **toàn bộ
175 mẫu** từ cột `bieu_thuc_kiem` rồi đối chiếu đáp án đã lưu — đúng phép soát đã
dùng cho 600 bài ground truth. Nó đạt, nghĩa là đáp án của mọi bài sinh ra đều
đúng, bảo đảm về mặt kiến tạo chứ không phải may rủi.

**Giới hạn cần biết**: không test nào chạm tới `manager` hay luồng agent. Chúng bảo
vệ tầng tất định — tầng dễ vỡ nhất khi refactor — nhưng **sẽ không bắt được hồi quy
ở tầng prompt**. Bộ đề chuẩn là lưới thứ hai, và là lưới duy nhất bắt được loại lỗi
đó.

Và như mục 4.6 cho thấy, **cả hai lưới vẫn để lọt** một phép kiểm chết suốt nhiều
ngày. Lưới thứ ba là ngồi đọc đáp án thật trên giao diện — không tự động hoá được,
nhưng là thứ duy nhất bắt được loại lỗi "báo đạt mà không chạy".
