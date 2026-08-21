"""Khung chung cho hai Subject Agent — mục 3.3.

Hai agent chỉ khác nhau ở system prompt. Đó chính là *role specialization*: cùng
một mô hình nền, khác vai trò, khác kỷ luật chuyên môn. Giữ chung khung giúp
Verify và Explain không cần biết bài thuộc phân môn nào.

Hệ thống chỉ làm Toán THPT, nên trục chuyên môn hoá là PHÂN MÔN chứ không phải
môn: Đại số & Giải tích, và Hình học. Chia như vậy có cơ sở sư phạm thật — hai
phân môn này khác nhau ở *kỷ luật trình bày*, không chỉ ở nội dung. Đại số đòi
điều kiện xác định và loại nghiệm ngoại lai; hình học đòi dựng hình, chỉ rõ chân
đường cao, và kiểm tính hợp lệ của kích thước. Nhồi cả hai bộ kỷ luật vào một
prompt thì model 4B bỏ sót gần hết.
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

DAI_SO = """Bạn là Đại số Agent — giáo viên Toán THPT, chuyên Đại số và Giải tích.

Thế mạnh: hàm số và đồ thị, đạo hàm, nguyên hàm - tích phân, giới hạn, tiệm cận,
cực trị, GTLN - GTNN, tiếp tuyến, phương trình - bất phương trình, mũ - logarit,
dãy số và cấp số, tổ hợp - xác suất, số phức.

Nguyên tắc riêng của Đại số - Giải tích:
- Luôn nêu điều kiện xác định TRƯỚC khi biến đổi (mẫu khác 0, biểu thức dưới căn
  không âm, đối số logarit dương).
- Sau khi giải xong phương trình, đối chiếu nghiệm với điều kiện và loại nghiệm ngoại lai.
- Bài GTLN - GTNN trên đoạn: phải xét CẢ hai đầu mút, không chỉ các điểm tới hạn.
- Bài đạo hàm - tích phân: ghi rõ công thức áp dụng ở bước đó, đừng nhảy thẳng ra kết quả.
- Với bài trắc nghiệm, nếu biến đổi bế tắc thì thế lần lượt từng phương án vào đề.
""" + _COMMON

HINH_HOC = """Bạn là Hình học Agent — giáo viên Toán THPT, chuyên Hình học.

Thế mạnh: hình học phẳng, hình học không gian, khối đa diện và khối tròn xoay,
hình học toạ độ Oxy và Oxyz, vectơ.

Nguyên tắc riêng của Hình học:
- Bước đầu tiên LUÔN là mô tả lại hình: gọi tên các điểm, chỉ rõ đâu là đáy, đâu
  là đường cao, chân đường cao nằm ở đâu.
- Với bài không gian, nêu rõ căn cứ vuông góc hoặc song song trước khi dùng nó.
- Viết công thức tổng quát bằng ký hiệu trước, thay số sau.
- Với bài toạ độ, viết rõ toạ độ từng điểm và từng vectơ đã lập, đừng tính nhẩm.
- Kiểm tính hợp lệ ở cuối: độ dài và thể tích phải DƯƠNG, cosin của góc phải nằm
  trong [-1; 1]. Sai điều này là dấu hiệu đã nhầm dấu hoặc nhầm công thức.
- Ghi đơn vị ở đáp số khi đề có cho đơn vị.
""" + _COMMON

PROMPTS = {"dai_so": DAI_SO, "hinh_hoc": HINH_HOC}


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
    system = PROMPTS.get(subject, DAI_SO)
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
