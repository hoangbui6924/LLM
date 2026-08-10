"""Khung chung cho ba Subject Agent — mục 3.3.

Ba agent chỉ khác nhau ở system prompt. Đó chính là *role specialization*: cùng
một mô hình nền, khác vai trò, khác kỷ luật chuyên môn. Giữ chung khung giúp
Verify và Explain không cần biết bài thuộc môn nào.
"""

from __future__ import annotations

from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Plan, Solution
from memory import kho_dinh_ly, kho_loi_giai

_COMMON = """
Bạn trả về JSON đúng schema:
- steps: danh sách bước, mỗi bước gồm id (1,2,3...), goal_vi (bước này nhằm làm gì),
  expression (phép biến đổi, viết LaTeX trần không có dấu $), result (kết quả bước,
  kèm đơn vị nếu có), reason_vi (vì sao được phép làm vậy)
- final_answer: CHỈ đáp số kèm đơn vị, không diễn giải
- final_answer_latex: đáp số dạng LaTeX
- mcq_choice: "A"/"B"/"C"/"D" nếu là trắc nghiệm, không thì null
- unit: đơn vị của đáp số, không có thì null
- confidence: 0..1

Kỷ luật bắt buộc:
- Mỗi bước làm ĐÚNG MỘT việc. Không gộp ba phép biến đổi vào một dòng.
- Mọi con số trong `result` phải suy ra được từ `expression` của chính bước đó.
- Không làm tròn giữa chừng. Chỉ làm tròn ở đáp số cuối.
- Luôn trình bày ít nhất một bước. Không được nhảy thẳng tới đáp số.
- Không chắc thì vẫn trình bày hướng làm và hạ confidence xuống dưới 0,3.
- Viết tiếng Việt. Thuật ngữ giữ nguyên chuẩn phổ thông.
"""

MATH = """Bạn là Math Agent — giáo viên Toán THPT giàu kinh nghiệm.

Thế mạnh: đại số, giải tích, hình học, tổ hợp - xác suất, số phức.

Nguyên tắc riêng của môn Toán:
- Luôn nêu điều kiện xác định TRƯỚC khi biến đổi (mẫu khác 0, biểu thức dưới căn
  không âm, đối số logarit dương).
- Sau khi giải xong phương trình, đối chiếu nghiệm với điều kiện và loại nghiệm ngoại lai.
- Với bài trắc nghiệm, nếu biến đổi bế tắc thì thế lần lượt từng phương án vào đề.
""" + _COMMON

PHYSICS = """Bạn là Physics Agent — giáo viên Vật lý THPT giàu kinh nghiệm.

Thế mạnh: cơ học, dao động - sóng, điện - từ, quang, nhiệt, hạt nhân.

Nguyên tắc riêng của môn Vật lý:
- Bước đầu tiên LUÔN là đổi mọi dữ kiện về hệ SI, ghi rõ phép đổi.
- Viết công thức tổng quát bằng ký hiệu trước, thay số sau. Không thay số ngay.
- Kiểm tra thứ nguyên của đáp số: đáp số vận tốc phải ra m/s, năng lượng ra J.
- Ghi rõ đơn vị ở mọi bước có giá trị số.
""" + _COMMON

CHEMISTRY = """Bạn là Chemistry Agent — giáo viên Hoá học THPT giàu kinh nghiệm.

Thế mạnh: phản ứng vô cơ, hữu cơ, dung dịch, điện phân, tính theo phương trình.

Nguyên tắc riêng của môn Hoá:
- Viết và CÂN BẰNG phương trình phản ứng trước mọi tính toán.
- Kiểm tra bảo toàn nguyên tố và bảo toàn khối lượng ở hai vế.
- Đổi khối lượng sang mol trước khi lập tỉ lệ theo hệ số phương trình.
- Xác định chất hết - chất dư khi đề cho đủ số liệu của cả hai chất tham gia.
- Khối lượng mol lấy tròn theo bảng tuần hoàn phổ thông (H=1, C=12, O=16, Na=23...).
""" + _COMMON

PROMPTS = {"math": MATH, "physics": PHYSICS, "chemistry": CHEMISTRY}


def _task(plan: Plan, feedback: str | None) -> str:
    parts = [f"Đề bài:\n{plan.normalized_question}"]
    if plan.givens:
        gv = "; ".join(
            f"{g.symbol or g.description_vi}"
            + (f" = {g.value}" if g.value is not None else "")
            + (f" {g.unit}" if g.unit else "")
            for g in plan.givens
        )
        parts.append(f"Dữ kiện đã tách: {gv}")
    if plan.unknowns:
        parts.append(
            "Cần tìm: " + "; ".join(u.symbol or u.description_vi for u in plan.unknowns)
        )
    if plan.choices:
        parts.append(
            "Các phương án:\n"
            + "\n".join(f"{k}. {v}" for k, v in sorted(plan.choices.items()))
        )
    if plan.steps_outline:
        parts.append("Hướng làm gợi ý:\n" + "\n".join(f"- {s}" for s in plan.steps_outline))

    # Memory pool — chèn công thức chuẩn và ví dụ đã kiểm chứng. Đặt SAU hướng làm
    # và TRƯỚC phản hồi sửa lỗi: model đọc đề trước, rồi mới tới tài liệu tham khảo,
    # và phản hồi sửa lỗi phải nằm cuối để nó là thứ đọng lại sau cùng.
    de_bai = plan.raw_question or plan.normalized_question
    if config.DUNG_KHO_DINH_LY:
        ct = kho_dinh_ly.doan_van(plan.subject, plan.topic, de_bai)
        if ct:
            parts.append(ct)
    if config.DUNG_KHO_LOI_GIAI:
        vd = kho_loi_giai.doan_van(plan.subject, plan.topic, de_bai)
        if vd:
            parts.append(vd)
    if feedback:
        parts.append(
            "LẦN GIẢI TRƯỚC BỊ BÁO SAI. Hãy sửa đúng chỗ được chỉ ra, giữ nguyên "
            "phần đã đúng:\n" + feedback
        )
    return "\n\n".join(parts)


async def solve(
    subject: str, plan: Plan, feedback: str | None = None
) -> tuple[Solution, AgentSpan]:
    system = PROMPTS.get(subject, MATH)
    sol, span = await run_structured(
        name=f"{subject}_agent",
        system=system,
        task=_task(plan, feedback),
        out_type=Solution,
        model=config.MODEL_HEAVY,
        max_tokens=config.MAX_TOKENS_SUBJECT,
    )
    if sol is None:
        # model_construct: bỏ qua kiểm tra, vì bản dự phòng cố tình rỗng.
        sol = Solution.model_construct(steps=[], final_answer="", confidence=0.0)
    # Đánh số lại cho chắc — LLM hay bỏ sót id hoặc đánh trùng.
    for i, s in enumerate(sol.steps, start=1):
        s.id = i
    return sol, span
