"""Explain Agent — mục 3.5.

Ràng buộc cứng: agent này **không được sinh đáp án mới**. Nó chỉ diễn đạt lại
lời giải đã qua kiểm chứng cho học sinh đọc hiểu. Nếu để nó tự do suy luận,
nó sẽ âm thầm "sửa" đáp số và phá bỏ toàn bộ công sức của Verify Agent.

Đây cũng là agent duy nhất chạy ở chế độ streaming — người dùng thấy chữ hiện
dần thay vì ngồi nhìn màn hình trắng suốt 40 giây.
"""

from __future__ import annotations

from typing import AsyncIterator

from agents.base import stream_text
from core import config
from core.schemas import Plan, Solution, VerifyReport

SYSTEM = """Bạn là Explain Agent. Bạn KHÔNG giải bài và KHÔNG được thay đổi đáp số.

Bạn nhận một lời giải đã có sẵn, hãy trình bày lại cho học sinh THPT dễ hiểu.

Định dạng bắt buộc, viết bằng Markdown:

**Tóm tắt đề**
(một câu, nêu cho gì và tìm gì)

**Bước 1 — <tên bước>**
(giải thích vì sao làm bước này, rồi mới đến công thức)

$$<công thức LaTeX>$$

**Bước 2 — <tên bước>**
...

**Đáp án**
(đáp số kèm đơn vị, in đậm)

**Dễ sai ở đâu**
- (1-3 gạch đầu dòng, ngắn)

Quy tắc:
- Giữ NGUYÊN đáp số được cung cấp. Tuyệt đối không tính lại, không làm tròn khác đi.
- Công thức đặt trong $$...$$ nếu đứng riêng, $...$ nếu nằm giữa câu.
- Xưng "ta", giọng thầy giáo giảng bài, không dùng "tôi" hay "bạn AI".
- Không nhắc đến agent, JSON, hay quá trình nội bộ của hệ thống.
"""


def _task(plan: Plan, sol: Solution, report: VerifyReport | None) -> str:
    parts = [
        f"Đề bài:\n{plan.raw_question or plan.normalized_question}",
        f"Lời giải đã kiểm chứng:\n{sol.as_text()}",
        f"Đáp số phải giữ nguyên: {sol.final_answer}",
    ]
    if sol.mcq_choice:
        parts.append(f"Phương án chọn: {sol.mcq_choice}")
    if report and report.verdict == "UNCERTAIN":
        parts.append(
            "Lưu ý: lời giải chưa được kiểm chứng chắc chắn. Hãy trình bày bình "
            "thường, không tự sửa đáp số."
        )
    return "\n\n".join(parts)


def stream(
    plan: Plan,
    sol: Solution,
    report: VerifyReport | None = None,
    timeout: float | None = None,
) -> AsyncIterator[str]:
    return stream_text(
        name="explain_agent",
        system=SYSTEM,
        task=_task(plan, sol, report),
        model=config.MODEL_LIGHT,
        max_tokens=config.MAX_TOKENS_EXPLAIN,
        timeout=timeout,
    )
