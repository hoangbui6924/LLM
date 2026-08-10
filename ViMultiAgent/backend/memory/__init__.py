"""Memory pool — mục (2) của đề bài: theorem database + solved examples.

Hai kho, hai vai trò khác nhau:

* `kho_dinh_ly`  — công thức và định lý chương trình THPT, soạn sẵn, KHÔNG đổi.
                   Vá đúng chỗ mô hình 4B yếu nhất: nhớ sai công thức.
* `kho_loi_giai` — lời giải ĐÃ QUA KIỂM CHỨNG của những lượt trước, tích luỹ dần.
                   Đây là phần khiến hệ thống khá lên khi dùng nhiều, thay vì
                   đứng yên như hiện tại.

Cả hai đều tra cứu bằng từ khoá và `Plan.topic`, KHÔNG dùng embedding: thêm một
mô hình nhúng là thêm vài trăm MB RAM tranh chỗ với Ollama trên máy 6 GB VRAM,
trong khi `topic` mà Planner sinh ra đã là khoá phân loại sẵn có.
"""

from memory import kho_dinh_ly, kho_loi_giai

__all__ = ["kho_dinh_ly", "kho_loi_giai"]
