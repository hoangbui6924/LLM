Tiến độ 5 ngày
Ngày 1
Thiết kế kiến trúc.
Cài Ollama + mô hình.
Xây FastAPI.
Tạo Planner và Router Agent.
Ngày 2
Xây 3 Subject Agent (Toán, Lý, Hóa).
Tích hợp SymPy.
Kiểm thử các câu hỏi mẫu.
Ngày 3
Thêm Verify Agent và Explain Agent.
Hoàn thiện luồng Multi-Agent.
Ngày 4
Làm giao diện React.
Hiển thị Markdown và LaTeX.
Kết nối frontend với backend.
Ngày 5
Kiểm thử.
Chuẩn bị báo cáo.
Chuẩn bị slide và demo.

1. Mục tiêu hệ thống

Xây dựng ViMultiAgent – hệ thống đa tác tử hỗ trợ giải các bài toán STEM bằng tiếng Việt.

Hệ thống cần có khả năng:

Tiếp nhận câu hỏi STEM tiếng Việt.
Phân tích và xác định môn học.
Chuyển bài toán đến tác tử chuyên môn phù hợp.
Sinh lời giải từng bước.
Kiểm tra lại lời giải.
Trả kết quả cho người dùng.


2. Kiến trúc tổng thể
                 +----------------+
                 |   React Web    |
                 +-------+--------+
                         |
                     REST API
                         |
                 +-------v--------+
                 |    FastAPI     |
                 +-------+--------+
                         |
              +----------+----------+
              | Multi-Agent Manager |
              +----------+----------+
                         |
      +------------------+------------------+
      |        |          |         |        |
 Planner   Router   Subject   Verify  Explain
                      Agent     Agent   Agent
                         |
          +--------------+--------------+
          |              |              |
      Math Agent   Physics Agent   Chemistry Agent
                         |
                  +------+------+
                  |   SymPy     |
                  +-------------+
                         |
                    Ollama (Qwen)

3. Các Agent

Đây là phần quan trọng nhất.

3.1 Planner Agent

Nhiệm vụ

Phân tích yêu cầu.
Xác định loại câu hỏi.
Chuẩn hóa đầu vào.
Ví dụ
Tính đạo hàm của hàm số...

↓

Đây là bài toán đại số.

3.2 Router Agent
Sau khi Planner hoàn thành

Router quyết định
Math

↓

Math Agent
hoặc
Chemistry

↓

Chemistry Agent

3.3 Subject Agent

Có ba Agent

Math Agent
Bạn là giáo viên Toán THPT...
Physics Agent
Bạn là giáo viên Vật lý...
Chemistry Agent
Bạn là giáo viên Hóa...

Mỗi Agent chỉ chuyên giải môn của mình.

3.4 Verify Agent

Sau khi Subject Agent giải xong

Verify Agent sẽ

kiểm tra logic
kiểm tra đáp án
phát hiện sai sót

Ví dụ

Nếu lời giải sai

↓

yêu cầu Math Agent giải lại

3.5 Explain Agent

Không sinh đáp án mới.

Chỉ chuyển kết quả thành

Bước 1

...

Bước 2

...

Bước 3

...

Đáp án

4. Luồng hoạt động
User

↓

Planner

↓

Router

↓

Subject Agent

↓

SymPy

↓

Verify

↓

Explain

↓

User

5. Công nghệ
Backend
FastAPI (Python)
Lý do
nhẹ
dễ viết API
hỗ trợ AI rất tốt
tích hợp LangGraph dễ

Frontend
React + TypeScript
Lý do
giao diện đẹp
dễ kết nối REST API
hiển thị Markdown
hiển thị LaTeX

Ngôn ngữ
Python
Dùng cho
AI
Multi-Agent
SymPy
Backend

TypeScript
Dùng cho
Frontend

6. Framework Multi-Agent
LangGraph ⭐ (Khuyến nghị)

Ưu điểm

đúng bản chất Multi-Agent
quản lý workflow
dễ mở rộng
được dùng nhiều với LLM

7. LLM

Mình đề xuất

Ollama

↓

Qwen3 8B Instruct

Ưu điểm

miễn phí
chạy offline
hỗ trợ tiếng Việt khá tốt
không cần API Key

8. Công cụ tính toán

Không nên để LLM tự tính.

Nên dùng

SymPy

Ví dụ
solve()
factor()
integrate()
diff()

Điều này giúp kết quả chính xác hơn và thể hiện việc kết hợp LLM + Tool, đúng với yêu cầu đề tài.


9. Cơ sở dữ liệu

Đối với bài tập lớn

Chỉ cần SQLite.

Lưu

Question

Answer

Time

Subject

10. Frontend

Các màn hình

Trang chủ
Nhập câu hỏi

Kết quả

Lời giải
↓
Đáp án
↓
Các Agent đã hoạt động

Ví dụ
Planner
✓
Router
✓
Math Agent
✓
Verify
✓
Explain
✓

11. Cấu trúc thư mục
ViMultiAgent/
│
├── backend/
│   ├── agents/
│   │    ├── planner.py
│   │    ├── router.py
│   │    ├── math_agent.py
│   │    ├── physics_agent.py
│   │    ├── chemistry_agent.py
│   │    ├── verify_agent.py
│   │    └── explain_agent.py
│   │
│   ├── tools/
│   │    └── sympy_tool.py
│   │
│   ├── api/
│   │    └── routes.py
│   │
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │    ├── pages/
│   │    ├── components/
│   │    └── services/
│   │
│   └── package.json
│
└── README.md

12. Công nghệ tổng hợp

| Thành phần         | Công nghệ                  |
| ------------------ | -------------------------- |
| Ngôn ngữ Backend   | Python 3.12                |
| Backend API        | FastAPI                    |
| Multi-Agent        | LangGraph                  |
| LLM                | Qwen3 8B Instruct (Ollama) |
| Công cụ tính toán  | SymPy                      |
| Frontend           | React + TypeScript + Vite  |
| Hiển thị công thức | KaTeX hoặc MathJax         |
| Giao tiếp          | REST API (JSON)            |
| Cơ sở dữ liệu      | SQLite                     |
| Quản lý mã nguồn   | Git + GitHub               |

Đừng cố xây dựng một hệ thống quá lớn. Hãy tập trung vào luồng phối hợp của các Agent, vì đó là cốt lõi của đề tài. Một sản phẩm có 6 Agent hoạt động rõ ràng, giao diện thể hiện được quá trình xử lý, kết hợp LLM với SymPy để kiểm chứng kết quả sẽ thuyết phục hơn nhiều so với việc tích hợp quá nhiều công nghệ nhưng hoạt động không ổn định.

Nó sẽ là sử dụng autogen để xây dựng multiagent với kiến trúc role specialization trong đó mỗi agent sẽ dựa trên 1 llm open source ( sử dụng ollama), ngoài ra có sử dụng thư viện sympy, wolfram alpha api để hỗ trợ, từ đó xây dựng một chương trình giải bài tập stem, tiêu chí: có frontend chat kèm streaming explanation, hiệu quả của mỗi agent, hiệu quả của hệ thống tổng thể từ lúc đặt câu hỏi cho đến hết <= 45s