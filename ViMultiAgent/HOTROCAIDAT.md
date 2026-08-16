# Hỗ trợ cài đặt — máy mới tinh, nhận dự án qua file nén

Dành cho người **vừa mua laptop, mới chỉ có VS Code**, và nhận dự án dưới dạng file
nén chứ không phải tải từ GitHub. Làm tuần tự từ trên xuống, không nhảy cóc.

Thời gian: **50–70 phút**, phần lớn là ngồi chờ tải. Cần mạng trong lúc cài. Cài xong
thì chương trình chạy **hoàn toàn ngoại tuyến** — không cần tài khoản hay API key của
bất kỳ dịch vụ nào.

Tài liệu này viết cho người chưa từng dùng dòng lệnh. Mỗi lệnh đều kèm **kết quả đúng
trông như thế nào**, để bạn tự biết bước vừa rồi có thành công không.

---

# Phần A — Dành cho người GỬI

Đọc mục này rồi mới nén. Nén sai thì người nhận mất thêm nửa tiếng hoặc phải tải lại
600 MB.

## A.1. Ba thứ phải xử lý trước khi nén

**Bắt buộc loại bỏ `frontend/node_modules/` (111 MB).** Thư mục này chứa thư viện
JavaScript đã biên dịch **theo đúng hệ điều hành và phiên bản Node của máy bạn**. Chép
sang máy khác thường lỗi, và người nhận sẽ phải xoá đi cài lại. Lệnh `npm install`
dựng lại nó trong 2–3 phút từ `package.json`.

**Nên giữ `backend/ml/phobert_router/` (517 MB).** Đây là trọng số PhoBERT đã huấn
luyện, thư mục tự chứa đủ cả tokenizer lẫn model. Giữ nó thì người nhận đỡ được hai
việc: tải 540 MB mô hình nền từ Hugging Face, và chạy 12 phút huấn luyện. Nếu file nén
quá lớn để gửi thì bỏ ra cũng được — người nhận huấn luyện lại theo mục 6.2, kết quả
tương đương.

**Nên loại bỏ mọi thư mục `__pycache__`.** Bytecode Python sinh tự động, vô dụng trên
máy khác.

## A.2. Lệnh nén

Mở PowerShell, dán nguyên khối này:

```powershell
$goc = "E:\DeepLearning\ViMultiAgent"
$tam = "E:\_goi_tam\ViMultiAgent"
$dich = "E:\ViMultiAgent_gui.zip"

Remove-Item "E:\_goi_tam" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $tam -Force | Out-Null
robocopy $goc $tam /E /XD node_modules __pycache__ .venv .git /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy loi $LASTEXITCODE" }

Add-Type -AssemblyName System.IO.Compression.FileSystem
Remove-Item $dich -Force -ErrorAction SilentlyContinue
[System.IO.Compression.ZipFile]::CreateFromDirectory("E:\_goi_tam", $dich, "Optimal", $false)
Remove-Item "E:\_goi_tam" -Recurse -Force

Write-Host "Xong: $dich  ($([math]::Round((Get-Item $dich).Length/1MB,1)) MB)"
```

Mất khoảng **1 phút**. Kết quả:

```
Xong: E:\ViMultiAgent_gui.zip  (425 MB)
```

Ba chi tiết trong khối lệnh trên đều có lý do, đừng sửa bừa:

**Thư mục tạm phải đặt tên đúng `ViMultiAgent`.** Tên thư mục tạm chính là tên thư mục
gốc bên trong file nén. Đặt tên khác thì người nhận giải nén ra được một thư mục tên
lạ, và mọi đường dẫn trong tài liệu đều lệch.

**Dùng `ZipFile::CreateFromDirectory` chứ không dùng `Compress-Archive`.** Cùng cho ra
file `.zip` đọc được như nhau, nhưng `Compress-Archive` nạp dữ liệu qua đường ống của
PowerShell nên với 500 MB nó chậm hơn nhiều lần và ngốn RAM. Bản .NET nén xong trong
38 giây.

**Chọn ổ còn nhiều chỗ trống.** Quy trình cần gấp đôi dung lượng trong chốc lát: một
bản chép tạm 522 MB cộng file nén 425 MB. Dòng cuối tự xoá bản tạm sau khi nén xong.

> **Kiểm tra trước khi gửi:** mở file `.zip`, thư mục gốc phải tên `ViMultiAgent`, bên
> trong có `backend`, `frontend` và các file `.md`. Đường dẫn
> `ViMultiAgent\backend\ml\phobert_router\model.safetensors` phải tồn tại và nặng
> khoảng 515 MB nếu bạn muốn kèm sẵn phần học sâu.

**Nên đặt tên file nén là `ViMultiAgent.zip`.** Nút Extract All của Windows đề xuất
tạo một thư mục mang tên file nén, nên đặt tên khác — ví dụ `ViMultiAgent_gui.zip` —
sẽ khiến người nhận giải nén ra `ViMultiAgent_gui\ViMultiAgent\...`, lồng thừa một cấp.
Không hỏng gì, chỉ hơi rườm rà, và mục 2.2 có hướng dẫn cách tránh. Đặt trùng tên thì
khỏi phải nghĩ:

```powershell
Rename-Item "E:\ViMultiAgent_gui.zip" "ViMultiAgent.zip"
```

## A.3. Những thứ vẫn nằm trong file nén

Ba thứ này không bị loại, và đều vô hại — ghi ra để bạn khỏi giật mình khi mở file nén
ra xem:

| Thứ | Nặng | Vì sao không sao |
|---|---|---|
| `.env` | 5 KB | Chứa đúng bốn giá trị mặc định đã ghi trong `INSTALL.md`, không có gì riêng tư của máy bạn |
| `vimultiagent.db` | 86 KB | Lịch sử hỏi đáp trên máy bạn. Người nhận xoá được theo mục 6.4 |
| `frontend/dist/` | 1 MB | Bản giao diện đã dựng sẵn. Người nhận vẫn chạy `npm run dev` như thường |

Nếu `.env` của bạn có sửa khác mặc định, **nên xoá nó khỏi bản gửi** — người nhận sẽ
chạy với cấu hình khác báo cáo mà không biết.

---

# Phần B — Dành cho người NHẬN

# 1. Làm quen với terminal trước đã

Toàn bộ hướng dẫn này gõ lệnh vào **terminal của VS Code**. Nếu bạn chưa từng dùng,
đọc mục này một lần rồi thôi.

## 1.1. Mở terminal

Mở VS Code, rồi làm một trong hai cách:

- Menu trên cùng: **Terminal → New Terminal**
- Hoặc bấm phím tắt: `` Ctrl + ` `` (phím dấu huyền, nằm ngay dưới phím Esc)

Một khung hiện ra ở nửa dưới màn hình. Đó là terminal.

## 1.2. Đảm bảo đang dùng PowerShell

Nhìn góc phải khung terminal, có chữ ghi loại terminal đang chạy. Phải là
**PowerShell** hoặc **pwsh**. Nếu là `cmd` hay `bash`:

- Bấm mũi tên **∨** cạnh dấu **+** ở góc phải khung terminal
- Chọn **PowerShell**

Mọi lệnh trong tài liệu này viết cho PowerShell. Gõ vào cmd sẽ lỗi.

## 1.3. Ba thao tác cần biết

| Việc | Cách làm |
|---|---|
| **Dán lệnh** | `Ctrl + V`, hoặc bấm chuột phải |
| **Chạy lệnh** | Gõ xong bấm `Enter` |
| **Dừng lệnh đang chạy** | `Ctrl + C` |

## 1.4. Biết mình đang đứng ở thư mục nào

Đây là chỗ người mới hay lạc nhất. Terminal luôn "đứng" trong một thư mục, và lệnh chỉ
chạy đúng khi bạn đứng đúng chỗ.

Gõ:

```powershell
pwd
```

Kết quả trông như:

```
Path
----
D:\ViMultiAgent\backend
```

Đó là thư mục bạn đang đứng. Dùng `cd <tên thư mục>` để đi vào, `cd ..` để lùi ra một
cấp.

**Mỗi khi tài liệu này ghi một lệnh, phía trên nó luôn nói rõ phải đứng ở đâu.** Nếu
lệnh báo lỗi "không tìm thấy file", 90% là do đang đứng sai chỗ — gõ `pwd` kiểm tra.

---

# 2. Giải nén cho đúng chỗ

## 2.1. Bỏ chặn file nén — làm TRƯỚC khi giải nén

Windows đánh dấu mọi file tải từ mạng là "không tin cậy", và dấu đó lây sang toàn bộ
file bên trong sau khi giải nén. Sau đó Python và Node sẽ báo lỗi rất khó hiểu.

- Chuột phải vào file `ViMultiAgent.zip`
- Chọn **Properties** (Thuộc tính)
- Nhìn xuống đáy cửa sổ: nếu thấy dòng *"This file came from another computer..."* thì
  **tích vào ô Unblock** bên cạnh
- Bấm **OK**

Không thấy dòng đó thì file vốn đã sạch, đi tiếp.

## 2.2. Chọn chỗ giải nén

Chuột phải vào file zip → **Extract All...** → chọn thư mục → **Extract**.

### Sửa ô đường dẫn đích, đừng bấm OK luôn

Thư mục gốc **bên trong** file nén luôn tên `ViMultiAgent`, bất kể file `.zip` tên gì.
Nhưng nút **Extract All** của Windows mặc định đề xuất tạo thêm một thư mục mang tên
file nén. Bấm OK luôn thì được:

```
D:\ViMultiAgent_gui\ViMultiAgent\backend\...
        ^^^^^^^^^^^ thừa một cấp
```

Cách tránh: trong hộp thoại Extract, **sửa ô đường dẫn đích** từ `D:\ViMultiAgent_gui`
thành chỉ `D:\`. Kết quả ra đúng:

```
D:\ViMultiAgent\backend\...
```

Ai dùng 7-Zip thì chọn **Extract Here** là ra thẳng, không cần sửa gì.

> **Lỡ lồng thừa một cấp thì sao?** Về chức năng **không ảnh hưởng gì** — mọi đường dẫn
> trong dự án đều tương đối so với thư mục `ViMultiAgent`, nên `cd backend`,
> `python -m pytest`, `npm run dev` đều chạy y hệt. Chỉ phiền hai chỗ: đường dẫn dài
> thêm một cấp, và lúc mở VS Code phải nhớ chọn thư mục `ViMultiAgent` **bên trong**.
> Chọn nhầm thư mục ngoài thì cây thư mục bên trái chỉ hiện đúng một thư mục con thay
> vì thấy ngay `backend` và `frontend`. Không muốn sửa lại thì cứ để vậy cũng được.

### Chọn ổ nào, thư mục nào

Hai nguyên tắc chọn chỗ:

**Đừng để trong OneDrive, Google Drive, hay Dropbox.** Các dịch vụ này khoá file giữa
chừng để đồng bộ, sẽ làm hỏng lúc `npm install` hoặc lúc chương trình ghi cơ sở dữ
liệu. Lưu ý thư mục `Documents` và `Desktop` trên Windows 11 **thường đã bị OneDrive
đồng bộ sẵn** — nhận ra bằng biểu tượng đám mây nhỏ trên các file.

**Đường dẫn không dấu tiếng Việt, không quá sâu.**

| Nên | Không nên |
|---|---|
| `D:\ViMultiAgent` | `C:\Users\Bùi Hoàng\OneDrive\Tài liệu\Đồ án\ViMultiAgent` |
| `C:\Code\ViMultiAgent` | `C:\Users\...\Downloads\new folder (2)\ViMultiAgent` |

## 2.3. Mở dự án trong VS Code

Mở VS Code → menu **File → Open Folder...** → chọn thư mục `ViMultiAgent` vừa giải nén
→ bấm **Select Folder**.

Bên trái phải thấy cây thư mục có `backend`, `frontend`, `INSTALL.md`, `README.md`.
Thấy đúng như vậy là mở đúng chỗ.

Mở terminal (`` Ctrl + ` ``) rồi kiểm tra:

```powershell
pwd
```

Phải ra đúng đường dẫn thư mục `ViMultiAgent`, ví dụ `D:\ViMultiAgent`.

---

# 3. Cài ba công cụ nền

Máy mới chưa có gì cả. Cài đủ ba thứ này, theo đúng thứ tự.

> **Cài xong cả ba, PHẢI đóng hẳn VS Code rồi mở lại.** VS Code chỉ đọc danh sách
> chương trình của máy lúc khởi động. Không mở lại thì terminal vẫn báo "không tìm thấy
> python" dù bạn vừa cài xong.

Có hai đường: **mục 3.1** cài cả ba bằng một khối lệnh, **mục 3.2–3.4** tải và bấm
chuột theo cách thường. Chọn một trong hai, không làm cả hai.

## 3.1. Cách nhanh — cài cả ba bằng PowerShell

Windows 10 và 11 có sẵn công cụ `winget` để cài phần mềm bằng lệnh, không cần mở trình
duyệt. Kiểm tra máy bạn có chưa:

```powershell
winget --version
```

```
v1.29.280
```

Ra số phiên bản là dùng được. Báo *"không phải lệnh hợp lệ"* thì máy thiếu **App
Installer** — vào Microsoft Store tìm và cài, hoặc bỏ qua mục này mà làm theo mục
3.2–3.4.

**Cài cả ba, dán nguyên khối:**

```powershell
winget install --id Python.Python.3.13 --source winget --accept-package-agreements --accept-source-agreements
winget install --id OpenJS.NodeJS.LTS --source winget --accept-package-agreements --accept-source-agreements
winget install --id Ollama.Ollama --source winget --accept-package-agreements --accept-source-agreements
```

Mỗi lệnh in ra thanh tiến trình rồi kết thúc bằng:

```
Successfully installed
```

Tổng cộng tải khoảng **760 MB**, mất 5–15 phút tuỳ mạng.

Ba tham số phía sau có mục đích rõ ràng: `--source winget` buộc lấy từ kho chính thức
chứ không phải Microsoft Store, còn hai cờ `--accept-*` bỏ qua câu hỏi đồng ý điều
khoản — thiếu chúng thì lệnh dừng lại chờ bạn gõ `Y` và dễ bị tưởng là treo.

> **Ưu điểm lớn nhất:** bản Python cài qua `winget` **tự thêm vào PATH**, không có ô
> tích nào để quên. Đây chính là lỗi phổ biến nhất của cách cài thủ công.

**Sau khi cài xong, đóng hẳn VS Code rồi mở lại**, và nhảy thẳng xuống mục 3.5 để kiểm
tra. Bỏ qua mục 3.2, 3.3, 3.4.

> **Nếu `python --version` vẫn báo lỗi hoặc mở ra Microsoft Store:** Windows có sẵn một
> "phím tắt giả" tên `python` trỏ vào Store, và nó đứng trước Python thật trong PATH.
> Tắt đi: **Settings → Apps → Advanced app settings → App execution aliases**, gạt tắt
> hai dòng **python.exe** và **python3.exe**. Rồi mở lại VS Code.

---

Ba mục dưới đây là **cách thủ công**, chỉ làm nếu bạn không dùng được `winget`.

## 3.2. Python — chạy toàn bộ backend

**Tải ở đâu:** vào <https://www.python.org/downloads/>

Ngay giữa trang có nút vàng lớn ghi **"Download Python 3.13.x"**. Bấm vào đó. File tải
về tên kiểu `python-3.13.8-amd64.exe`, khoảng 25 MB.

**Cách cài — có một ô tích quyết định cả quy trình:**

1. Mở file `.exe` vừa tải
2. Màn hình đầu tiên hiện ra, **nhìn xuống đáy cửa sổ**
3. Có ô vuông ghi **"Add python.exe to PATH"** — **TÍCH VÀO Ô ĐÓ**
4. Rồi mới bấm **"Install Now"** ở giữa
5. Chờ 1–2 phút, hiện "Setup was successful" thì bấm **Close**

> **Quên ô tích đó thì sao?** Mọi lệnh `python` sau này đều báo *"python không phải là
> lệnh hợp lệ"*. Cách sửa duy nhất là vào Control Panel gỡ Python ra rồi cài lại từ
> đầu. Đây là lỗi phổ biến nhất khi cài trên máy mới.

Yêu cầu tối thiểu: **Python 3.11 trở lên**.

## 3.3. Node.js — chạy giao diện web

**Tải ở đâu:** vào <https://nodejs.org/>

Trang chủ có hai nút. Bấm nút có chữ **LTS** (viết tắt của Long Term Support — bản ổn
định). File tải về tên kiểu `node-v22.20.0-x64.msi`, khoảng 30 MB.

**Cách cài:** mở file `.msi`, bấm **Next** qua tất cả các màn hình, không cần đổi gì.

> Đến màn hình hỏi *"Automatically install the necessary tools"* thì **để trống, đừng
> tích**. Cái đó cài thêm khoảng 3 GB công cụ biên dịch C++ mà dự án này không dùng
> đến, và mất thêm 20 phút.

Yêu cầu tối thiểu: **Node 20 trở lên**.

## 3.4. Ollama — chạy mô hình ngôn ngữ trên máy

Đây là phần thay thế cho việc gọi API của OpenAI hay Google. Nhờ nó mà hệ thống chạy
được ngoại tuyến.

**Tải ở đâu:** vào <https://ollama.com/download>

Trang tự nhận diện Windows và hiện nút **"Download for Windows"**. Bấm vào. File tải về
tên `OllamaSetup.exe`, khoảng 700 MB.

**Cách cài:** mở file, bấm **Install**. Cài xong Ollama **tự chạy nền ngay** — nhìn khay
hệ thống góc phải dưới màn hình (cạnh đồng hồ), bấm mũi tên **∧** sẽ thấy biểu tượng
con lạc đà alpaca.

## 3.5. Kiểm tra cả ba — bước không được bỏ

**Đóng hẳn VS Code rồi mở lại.** Mở terminal (`` Ctrl + ` ``), dán từng lệnh một:

```powershell
python --version
```

```
Python 3.13.8
```

```powershell
node -v
```

```
v22.20.0
```

```powershell
npm -v
```

```
10.9.3
```

```powershell
ollama --version
```

```
ollama version is 0.32.13
```

Số phiên bản của bạn có thể khác, không sao — miễn Python từ 3.11 và Node từ 20.

**Dòng nào báo lỗi kiểu này:**

```
python : The term 'python' is not recognized as the name of a cmdlet, function,
script file, or operable program.
```

thì thứ đó chưa cài xong hoặc chưa vào PATH. Với Python: cài lại bằng `winget` ở mục
3.1, hoặc gỡ ra cài lại thủ công và nhớ ô tích ở mục 3.2. Với Node và Ollama: thường
chỉ cần đóng VS Code mở lại lần nữa.

## 3.6. Mở khoá chạy script cho PowerShell

Windows mặc định **chặn mọi script PowerShell**, kể cả script đi kèm npm. Không làm
bước này thì lát nữa `npm install` sẽ báo:

```
npm : File C:\Program Files\nodejs\npm.ps1 cannot be loaded because running
scripts is disabled on this system.
```

Chạy trước cho gọn:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Nó hỏi xác nhận, gõ `Y` rồi `Enter`.

> Lệnh này chỉ áp cho tài khoản của bạn (`CurrentUser`), không đụng cấu hình toàn máy,
> và `RemoteSigned` vẫn chặn script tải từ mạng chưa ký. Đây là mức mà tài liệu chính
> thức của Microsoft khuyến nghị cho máy lập trình.

---

# 4. Cài extension cho VS Code

Mở VS Code, bấm biểu tượng **bốn ô vuông** ở thanh dọc bên trái, hoặc bấm
`Ctrl + Shift + X`. Ô tìm kiếm hiện ra ở trên cùng.

Với mỗi extension: gõ tên vào ô tìm kiếm, nhìn kết quả đầu tiên, **kiểm tra đúng nhà
phát hành** rồi bấm nút **Install** màu xanh.

## 4.1. Bắt buộc

| Gõ tìm | Nhà phát hành | Vì sao cần |
|---|---|---|
| `Python` | **Microsoft** | Chạy và gỡ lỗi Python. Cài nó là tự kéo theo Pylance và Python Debugger, không cần cài riêng |

## 4.2. Rất nên có cho dự án này

| Gõ tìm | Nhà phát hành | Vì sao cần |
|---|---|---|
| `Rainbow CSV` | **mechatroner** | Tô màu từng cột file CSV. Kết quả đo nằm ở `backend/eval/reports/*.csv` với **31 cột** — không có nó thì đọc bằng mắt gần như không nổi |
| `Markdown All in One` | **Yu Zhang** | Xem trước tài liệu `.md`. Bấm `Ctrl+Shift+V` để mở khung xem — cần để đọc các file `BAOCAO_SO_SANH_*.md` có nhúng ảnh biểu đồ |
| `PowerShell` | **Microsoft** | Gợi ý cú pháp cho các lệnh trong tài liệu này |

## 4.3. Tuỳ thích

| Gõ tìm | Nhà phát hành | Vì sao |
|---|---|---|
| `oxlint` | **Oxc** | Bộ soát lỗi mà frontend đang dùng (`npm run lint`) |
| `Error Lens` | **Alexander** | Hiện lỗi ngay trên dòng code thay vì phải rê chuột vào |

**Không cần cài ESLint hay Prettier.** Dự án dùng `oxlint`, cài ESLint vào chỉ tạo ra
hàng loạt báo lỗi giả.

## 4.4. Cài nhanh bằng lệnh — cách khác

Nếu ngại bấm chuột, dán nguyên khối này vào terminal:

```powershell
code --install-extension ms-python.python
code --install-extension mechatroner.rainbow-csv
code --install-extension yzhang.markdown-all-in-one
code --install-extension ms-vscode.powershell
```

Mỗi dòng in ra `Extension 'xxx' was successfully installed.` là xong.

## 4.5. Chọn trình thông dịch Python — bước hay bị bỏ sót

Sau khi cài extension Python:

1. Bấm `Ctrl + Shift + P` (mở bảng lệnh)
2. Gõ `Python: Select Interpreter`
3. Bấm `Enter`
4. Chọn dòng có phiên bản 3.11 trở lên, ví dụ `Python 3.13.8 64-bit`

**Bỏ qua bước này thì VS Code gạch đỏ khắp màn hình dù code hoàn toàn đúng**, vì nó
không biết tìm thư viện ở đâu.

---

# 5. Cài thư viện của dự án

## 5.1. Thư viện backend — bắt buộc

Trong terminal, đi vào thư mục `backend`:

```powershell
cd backend
```

Kiểm tra đã vào đúng chưa:

```powershell
pwd
```

```
Path
----
D:\ViMultiAgent\backend
```

Rồi cài:

```powershell
python -m pip install -r requirements.txt
```

Mất **3–5 phút**. Màn hình chạy rất nhiều dòng `Collecting...` và `Downloading...`,
kết thúc bằng dòng kiểu:

```
Successfully installed autogen-agentchat-0.7.5 fastapi-0.115.6 sympy-1.13.3 ...
```

Bộ này gồm AutoGen (khung Multi-Agent), FastAPI (máy chủ web), SymPy (tính toán tất
định) và Pint (kiểm đơn vị vật lý).

> Có thể hiện dòng vàng `WARNING: You are using pip version...` — bỏ qua, không ảnh
> hưởng gì.

## 5.2. Thư viện học sâu — hai lệnh, ĐỪNG gộp làm một

Vẫn đứng ở `backend`. Lệnh thứ nhất:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Tải khoảng **250 MB**, mất 2–5 phút.

Lệnh thứ hai:

```powershell
python -m pip install -r requirements-ml.txt
```

Cài `transformers` (nạp PhoBERT), `underthesea` (tách từ tiếng Việt) và `scikit-learn`
(mốc so sánh TF-IDF).

> **Vì sao phải ghi thêm `--index-url https://download.pytorch.org/whl/cpu`:** gõ
> `pip install torch` trơn sẽ kéo về bản CUDA nặng khoảng **2,5 GB** thay vì 250 MB, và
> trên máy VRAM thấp nó còn tranh bộ nhớ với Ollama. PhoBERT chỉ 135 triệu tham số,
> chạy trên CPU mất khoảng 50 mili giây mỗi câu — thừa nhanh, không cần GPU.

## 5.3. Thư viện frontend

Lùi ra rồi vào `frontend`:

```powershell
cd ..\frontend
```

```powershell
npm install
```

Mất **2–3 phút**, kết thúc bằng dòng kiểu:

```
added 187 packages, and audited 188 packages in 2m
```

Đây là bước dựng lại `node_modules` mà người gửi đã cố ý loại khỏi file nén.

> Hiện dòng `X vulnerabilities` màu vàng là bình thường với mọi dự án Node. **Đừng**
> chạy `npm audit fix` — lệnh đó hay nâng thư viện lên phiên bản không tương thích và
> làm hỏng giao diện.

---

# 6. Nạp dữ liệu

Đây là khác biệt giữa "code chạy được" và "chương trình hoạt động đúng". Có ba loại dữ
liệu; hai loại phải nạp thêm, một loại đã có sẵn trong file nén.

## 6.1. Mô hình ngôn ngữ qwen3:4b — PHẢI TẢI

Đứng ở đâu cũng được, lệnh này không phụ thuộc thư mục:

```powershell
ollama pull qwen3:4b
```

Tải **2,5 GB**, tuỳ mạng mất **5–20 phút**. Màn hình hiện thanh tiến trình:

```
pulling manifest
pulling 359d7dd4bcda: 100% ▕██████████████████▏ 2.5 GB
verifying sha256 digest
writing manifest
success
```

Kiểm tra lại:

```powershell
ollama list
```

```
NAME        ID              SIZE      MODIFIED
qwen3:4b    359d7dd4bcda    2.5 GB    2 minutes ago
```

Đây là bộ não giải bài. Không có nó thì chương trình vẫn khởi động nhưng mọi câu hỏi
đều báo lỗi.

> **Model lưu ở đâu:** `C:\Users\<tên bạn>\.ollama`, **không phải** thư mục dự án. Ổ C
> phải còn trống ít nhất **4 GB**. Đây là chỗ hay bất ngờ với người có ổ C nhỏ.

## 6.2. Bộ phân loại môn học PhoBERT — kiểm tra trước, huấn luyện sau

Đây là phần học sâu của đề tài: một mô hình PhoBERT được huấn luyện lại để đọc đề bài
và đoán nó thuộc môn Toán, Lý hay Hoá.

**Bước 1 — kiểm tra người gửi có kèm sẵn không.** Vào thư mục `backend`:

```powershell
cd ..\backend
```

```powershell
Test-Path ml\phobert_router\model.safetensors
```

Kết quả là một trong hai:

```
True
```

→ Người gửi đã kèm trọng số. **Bỏ qua phần còn lại của mục 6.2**, đi tiếp mục 6.3.

```
False
```

→ Phải tự huấn luyện, làm tiếp bước 2.

**Bước 2 — huấn luyện lại.** Vẫn đứng ở `backend`:

```powershell
python ml/train_phobert.py
```

Mất khoảng **12 phút trên CPU**. Lần đầu tải thêm mô hình nền PhoBERT khoảng 540 MB.
Không cần tắt Ollama vì việc này chạy trên CPU, không tranh GPU.

Chạy xong in ra ở cuối:

```
Độ chính xác trên test: 0.94
  seed       47/47 = 1.0000
  template   67/67 = 1.0000
  hard       36/45 = 0.8000
```

Dữ liệu huấn luyện (810 câu đã gán nhãn) nằm sẵn trong `backend/ml/data/`. **Không
cần** chạy `build_dataset.py`.

> **Bỏ hẳn bước này thì sao?** Hệ thống **vẫn chạy đủ** — Router tự lùi về luật từ khoá.
> Nhưng đo được trên 150 bài: **94,7% quyết định định tuyến hiện do PhoBERT đảm nhiệm**.
> Bỏ nó là mất hẳn phần học sâu, và những câu không chứa từ khoá đặc trưng phải hỏi
> LLM — mỗi lần tốn thêm 2–4 giây.

## 6.3. Dữ liệu đã có sẵn — không cần làm gì

| Dữ liệu | Nằm ở | Là gì |
|---|---|---|
| Ba bộ đề chấm | `backend/eval/data/` | `de_chuan` 150 bài · `de_giu_rieng` 150 bài · `de_kho` 300 bài, đều đã giải tay sẵn đáp án |
| Dataset PhoBERT | `backend/ml/data/` | 810 câu gán nhãn, chia sẵn train/val/test |
| Kho định lý | `backend/memory/kho_dinh_ly.py` | Công thức chuẩn sách giáo khoa, nằm trong mã nguồn |
| Kết quả đo cũ | `backend/eval/reports/` | Số liệu của báo cáo, để đối chiếu khi bạn chạy lại |

## 6.4. Xoá lịch sử của máy cũ — tuỳ chọn

File `vimultiagent.db` ở thư mục gốc chứa lịch sử hỏi đáp trên máy người gửi. Muốn bắt
đầu sạch thì xoá, chương trình tự tạo lại file rỗng lúc khởi động:

```powershell
Remove-Item ..\vimultiagent.db
```

---

# 7. Chạy chương trình

Cần **ba thứ chạy cùng lúc**, mỗi thứ một terminal riêng. Trong VS Code, bấm dấu **+**
ở góc phải khung terminal để mở thêm; danh sách các terminal hiện bên phải, bấm để
chuyển qua lại.

## 7.1. Terminal 1 — Ollama

Kiểm tra Ollama có đang chạy nền không:

```powershell
ollama ps
```

Ra một bảng, **kể cả bảng rỗng chỉ có dòng tiêu đề**, nghĩa là Ollama đang chạy:

```
NAME    ID    SIZE    PROCESSOR    CONTEXT    UNTIL
```

→ Tốt, **đóng terminal này**, không cần làm gì thêm.

Nếu báo lỗi kết nối thì Ollama chưa chạy, gõ:

```powershell
ollama serve
```

Để nguyên terminal này, đừng đóng, đừng bấm `Ctrl+C`.

> **Mẹo cho buổi demo:** chạy `$env:OLLAMA_KEEP_ALIVE = "-1"` **trước** lệnh
> `ollama serve` thì model nằm thường trú trong VRAM, mất hẳn 10–15 giây nạp lại ở câu
> hỏi đầu tiên.

## 7.2. Terminal 2 — Backend

Mở terminal mới (dấu **+**), rồi:

```powershell
cd backend
```

```powershell
python -m uvicorn main:app --port 8000
```

Chờ đến khi thấy hai dòng cuối:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Đọc kỹ dòng này ở phía trên**, nó cho biết phần học sâu có chạy không:

```
[ViMultiAgent] PhoBERT router: đã nạp, tầng 1 hoạt động.
```

Nếu thay vào đó là khối này:

```
[ViMultiAgent] CẢNH BÁO: KHÔNG có PhoBERT router (chưa có thư mục ml/phobert_router).
  Router sẽ chạy bằng luật từ khoá + LLM. Chương trình vẫn giải được bài,
  nhưng định tuyến kém chính xác hơn và chậm hơn khi luật không khớp.
```

thì mục 6.2 chưa xong. Chương trình vẫn giải được bài nên **rất dễ bỏ qua** — nhưng
tầng học sâu đang không chạy, và đó là phần đóng góp chính của đề tài.

Để nguyên terminal này chạy.

## 7.3. Terminal 3 — Frontend

Mở terminal thứ ba, rồi:

```powershell
cd frontend
```

```powershell
npm run dev
```

Hiện ra:

```
  VITE v8.2.0  ready in 412 ms

  ➜  Local:   http://localhost:5173/
```

Giữ `Ctrl` rồi bấm vào đường link đó, hoặc tự mở trình duyệt vào
<http://localhost:5173>.

## 7.4. Tắt chương trình

Bấm `Ctrl + C` trong từng terminal. Ollama thì cứ để chạy nền cũng được.

---

# 8. Kiểm tra đã cài đúng

## 8.1. Backend còn sống không

Mở trình duyệt vào <http://localhost:8000/api/health>. Phải thấy:

```json
{
  "status": "ok",
  "model_heavy": "qwen3:4b",
  "sla_seconds": 45.0,
  "tools": { "sympy": true, "units": true }
}
```

## 8.2. Chạy bộ kiểm thử

Mở terminal mới, vào `backend`:

```powershell
cd backend
```

```powershell
python -m pytest
```

Phải kết thúc bằng:

```
222 passed in 9.38s
```

Mất khoảng 10–15 giây. Bộ này **không cần Ollama** — nếu đạt đủ 222 thì phần lõi tính
toán đã đúng, lỗi nếu có nằm ở khâu kết nối mô hình.

## 8.3. Model có nằm trong GPU không

Sau khi đã giải ít nhất một bài:

```powershell
ollama ps
```

```
NAME        ID              SIZE      PROCESSOR    UNTIL
qwen3:4b    359d7dd4bcda    3.5 GB    100% GPU     4 minutes from now
```

Cột **PROCESSOR** phải ghi **100% GPU**. Dưới 100%, ví dụ `73% GPU/27% CPU`, nghĩa là
model đang tràn sang CPU: chương trình vẫn chạy đúng nhưng chậm gấp 3–10 lần, và mọi
số đo thời gian sẽ không khớp báo cáo.

Máy không có card đồ hoạ rời thì cột này ghi `100% CPU`, mỗi câu mất 5–10 phút. Vẫn
demo được, chỉ là phải kiên nhẫn.

## 8.4. Giải thử một bài

Trên giao diện web, bấm nút **Lý** để điền đề mẫu, rồi bấm **Giải bài**. Quan sát:

- Năm vai sáng dần: Planner → Router → Subject → Verify → Explain
- **Đáp án hiện ra trước khi lời giảng chảy xong** — hệ thống phát đáp số ngay khi
  chốt, không bắt chờ giảng bài
- Lời giải chảy chữ theo thời gian thực
- Dòng cuối báo tổng thời gian, khoảng **25–35 giây** trên máy có GPU 6 GB
- Cuối cột phải hiện thẻ **Bài tập tương tự** — bấm "Sinh bài" phải ra đề mới **tức
  thì** (không gọi LLM)

> **Câu hỏi đầu tiên luôn lâu bất thường**, thêm 10–15 giây, vì Ollama phải nạp model
> 2,5 GB lên GPU. Các lượt sau nhanh hơn hẳn. Đừng tưởng hệ thống treo.

---

# 9. Lỗi thường gặp trên máy mới

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `python : The term 'python' is not recognized...` | Quên tích "Add python.exe to PATH" | Cài lại bằng `winget` (mục 3.1), hoặc gỡ trong Control Panel rồi cài lại nhớ ô tích (mục 3.2) |
| Gõ `python` thì mở ra Microsoft Store | Phím tắt giả của Windows chắn mất Python thật | Tắt App execution aliases, xem cuối mục 3.1 |
| `npm : ... running scripts is disabled on this system` | Chưa mở khoá PowerShell | Làm mục 3.6 |
| `npm` không phải lệnh hợp lệ | Chưa mở lại VS Code sau khi cài Node | Đóng **hẳn** VS Code rồi mở lại |
| VS Code gạch đỏ khắp file `.py` dù code đúng | Chưa chọn trình thông dịch | Mục 4.5 |
| `ModuleNotFoundError: No module named 'torch'` | Chưa cài phần học sâu | Làm lại hai lệnh mục 5.2 |
| `ModuleNotFoundError: No module named 'underthesea'` | Thiếu bộ tách từ tiếng Việt | `python -m pip install -r requirements-ml.txt` |
| `[Errno 10048] ... address already in use` | Cổng 8000 còn server cũ chạy | Mục 9.1 |
| Giao diện trắng trơn ở cổng 5173 | Chưa `npm install` | Làm lại mục 5.3 |
| Bấm "Giải bài" không có phản hồi gì | Backend chưa chạy | Kiểm tra Terminal 2 và mở `/api/health` |
| Backend báo lỗi kết nối Ollama | Ollama chưa chạy | `ollama ps`, trống thì `ollama serve` |
| Trả lời chậm hơn 60 giây mỗi câu | Model chạy trên CPU | `ollama ps`, xem cột PROCESSOR |
| Router luôn báo "Quyết định bằng luật" | Chưa có PhoBERT | Mục 6.2 |
| `npm install` treo hoặc lỗi quyền | Thư mục nằm trong OneDrive | Chuyển dự án ra `D:\ViMultiAgent` |
| Lệnh nào cũng báo "không tìm thấy file" | Đang đứng sai thư mục | Gõ `pwd` kiểm tra, xem mục 1.4 |

## 9.1. Giải phóng cổng 8000

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

Nhìn cột `OwningProcess`, lấy số đó thay vào lệnh sau:

```powershell
Stop-Process -Id 12345 -Force
```

---

# 10. Danh sách kiểm tra cuối cùng

- [ ] `python --version` ra 3.11 trở lên
- [ ] `node -v` ra v20 trở lên
- [ ] `ollama --version` ra số phiên bản
- [ ] VS Code đã cài extension **Python** của Microsoft
- [ ] Đã chọn trình thông dịch Python (`Ctrl+Shift+P` → Select Interpreter)
- [ ] `ollama list` thấy `qwen3:4b`
- [ ] `Test-Path ml\phobert_router\model.safetensors` ra `True`
- [ ] `python -m pytest` đạt **222 passed**
- [ ] Backend in `PhoBERT router: đã nạp` lúc khởi động, KHÔNG phải khối CẢNH BÁO
- [ ] `/api/health` trả `"status": "ok"`
- [ ] Giải thử một bài mỗi môn, thấy đủ năm vai chạy
- [ ] Đã hỏi trước một câu bất kỳ để Ollama nạp model — tránh lượt demo đầu bị chậm

---

# 11. Đọc tiếp gì

| Tài liệu | Nội dung |
|---|---|
| `HUONGDAN.md` | Cách dùng: API, các script, cấu hình, kịch bản demo |
| `CHAYBENCHMARK.md` | Cách chạy đo hiệu năng và so sánh một tác tử với đa tác tử |
| `INSTALL.md` | Bản cài đặt cho người tải từ repo, có phân tích phần cứng sâu hơn |
| `TAILIEU.md` | Tài liệu kỹ thuật: kiến trúc, từng agent, từng công cụ |
| `BAOCAO.md` | Báo cáo đề tài |
