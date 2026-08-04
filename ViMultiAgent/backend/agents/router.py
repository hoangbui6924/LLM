"""Router Agent — mục 3.2.

Router chọn Subject Agent theo ba tầng, rẻ trước đắt sau:

    PhoBERT (~30 ms)  ->  luật từ khoá (0 ms)  ->  LLM (2-4 giây)

Tầng nào đủ chắc thì dừng ở đó. Hỏi LLM để phân loại môn là lãng phí: đó là bài
toán dễ, mà 3-4 giây chiếm gần 10% ngân sách 45 giây của cả lượt.

PhoBERT đứng trước luật từ khoá vì nó xử lý được nhóm câu **không chứa từ khoá
đặc trưng** — chỗ mà luật buộc phải đoán bừa. Nhưng luật vẫn được giữ nguyên làm
lớp dự phòng: chưa huấn luyện PhoBERT thì hệ thống vẫn chạy đầy đủ.
"""

from __future__ import annotations

import re

from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Plan, Route
from ml import classifier

SYSTEM = """Bạn là Router Agent. Cho một đề bài STEM tiếng Việt, hãy chọn đúng MỘT môn.

Trả JSON: subject ("math"|"physics"|"chemistry"), agent_name
("math_agent"|"physics_agent"|"chemistry_agent"), reason_vi (một câu ngắn),
confidence (0..1), decided_by = "llm".

Căn cứ chọn:
- math: đại số, giải tích, hình học, tổ hợp, xác suất, dãy số, logarit
- physics: lực, chuyển động, điện, từ, sóng, dao động, nhiệt, quang, hạt nhân
- chemistry: phản ứng, nguyên tố, mol, nồng độ, dung dịch, hữu cơ, vô cơ
"""

# Dưới ngưỡng này coi như PhoBERT không chắc, nhường cho tầng sau. Chọn 0,85 vì
# nhóm câu ranh giới thường rơi vào vùng 0,4-0,7; để thấp hơn thì mô hình sẽ tự
# tin sai ở đúng những câu khó nhất.
NGUONG_PHOBERT = 0.85

_AGENT_OF = {
    "math": "math_agent",
    "physics": "physics_agent",
    "chemistry": "chemistry_agent",
}

# Từ khoá đặc trưng. Cố tình chọn từ ÍT chồng lấn giữa các môn.
_RULES: dict[str, list[str]] = {
    "chemistry": [
        "phản ứng", "phương trình hoá học", "phương trình hóa học", "mol", "nồng độ",
        "dung dịch", "kết tủa", "oxi hoá", "oxi hóa", "khử", "axit", "bazơ", "muối",
        "hidrocacbon", "hiđrocacbon", "este", "ancol", "kim loại", "phi kim",
        "nguyên tử khối", "khối lượng mol", "hoá trị", "hóa trị", "điện phân",
    ],
    "physics": [
        "vận tốc", "gia tốc", "lực", "khối lượng riêng", "dao động", "con lắc",
        "sóng", "tần số", "biên độ", "điện trở", "cường độ dòng", "hiệu điện thế",
        "công suất", "nhiệt lượng", "quang", "thấu kính", "hạt nhân", "phóng xạ",
        "động năng", "thế năng", "ma sát", "trọng lực", "từ trường", "cảm ứng",
    ],
    "math": [
        "đạo hàm", "nguyên hàm", "tích phân", "giới hạn", "phương trình", "bất phương trình",
        "hàm số", "đồ thị", "logarit", "lôgarit", "cấp số", "tổ hợp", "chỉnh hợp",
        "xác suất", "ma trận", "vectơ", "véc tơ", "hình chóp", "mặt cầu", "tiệm cận",
        "khảo sát", "cực trị", "số phức",
    ],
}


def _by_rule(text: str) -> tuple[str, float, str]:
    low = text.lower()
    score = {k: 0 for k in _RULES}
    hit: dict[str, list[str]] = {k: [] for k in _RULES}
    for subj, kws in _RULES.items():
        for kw in kws:
            if re.search(rf"(?<!\w){re.escape(kw)}", low):
                score[subj] += 1
                hit[subj].append(kw)
    best = max(score, key=lambda k: score[k])
    total = sum(score.values())
    if total == 0:
        return "math", 0.0, "không có từ khoá đặc trưng"
    # Chắc chắn khi môn thắng chiếm ưu thế rõ rệt.
    conf = score[best] / total
    return best, conf, "từ khoá: " + ", ".join(hit[best][:3])


async def run(plan: Plan) -> tuple[Route, AgentSpan | None]:
    text = f"{plan.raw_question}\n{plan.normalized_question}"

    # Ưu tiên 1: bộ phân loại PhoBERT do nhóm fine-tune. ~30 ms trên CPU, rẻ hơn
    # hỏi LLM khoảng trăm lần. Chỉ tin khi mô hình đủ chắc; dưới ngưỡng thì câu
    # hỏi đang nằm ở vùng ranh giới, lúc đó mới đáng tiêu token cho LLM.
    subj, conf, why = _by_rule(text)

    kq = classifier.du_doan(plan.normalized_question or plan.raw_question)
    if kq is not None:
        mon, do_tin = kq
        # PhoBERT chỉ được CHỐT khi luật từ khoá không phản đối.
        #
        # Đo được trên đề thật: câu xác suất bi ("rút 4 viên, xác suất có đúng 2
        # viên đỏ") bị PhoBERT xếp vào physics với độ tin cậy 0,90; câu dao động
        # điều hoà bị xếp vào math với 0,86. Độ tin cậy cao mà vẫn sai, nên chỉ
        # nâng ngưỡng là vô ích.
        #
        # Nguyên nhân: dữ liệu huấn luyện gồm câu NGẮN, còn đề vận dụng thì dài
        # và nhiều mệnh đề — lệch phân bố. Luật từ khoá thì ngược lại, càng dài
        # càng nhiều từ khoá nên càng chắc. Hai nguồn bù khuyết cho nhau.
        #
        # Bất đồng thì không bên nào được tự quyết, đẩy xuống cho LLM.
        luat_khong_phan_doi = conf == 0.0 or subj == mon
        if do_tin >= NGUONG_PHOBERT and luat_khong_phan_doi:
            return (
                Route(
                    subject=mon,  # type: ignore[arg-type]
                    agent_name=_AGENT_OF[mon],
                    reason_vi=f"PhoBERT phân loại là {mon} (độ tin cậy {do_tin:.2f}).",
                    confidence=do_tin,
                    decided_by="phobert",
                    phobert_confidence=do_tin,
                ),
                None,
            )

    # Ưu tiên 2: luật từ khoá. Planner đã tự tin và luật đồng ý => khỏi gọi LLM.
    if conf >= 0.6 and (plan.confidence < 0.4 or plan.subject == subj):
        return (
            Route(
                subject=subj,  # type: ignore[arg-type]
                agent_name=_AGENT_OF[subj],
                reason_vi=f"Quyết định bằng luật ({why}).",
                confidence=conf,
                decided_by="rule",
                phobert_confidence=kq[1] if kq else None,
            ),
            None,
        )

    route, span = await run_structured(
        name="router",
        system=SYSTEM,
        task=f"Đề bài:\n{plan.normalized_question}",
        out_type=Route,
        model=config.MODEL_LIGHT,
        max_tokens=config.MAX_TOKENS_ROUTER,
    )
    if route is None:
        route = Route(
            subject=subj,  # type: ignore[arg-type]
            agent_name=_AGENT_OF[subj],
            reason_vi=f"LLM không trả lời được, lùi về luật ({why}).",
            confidence=conf,
            decided_by="rule",
        )
    else:
        route.agent_name = _AGENT_OF.get(route.subject, "math_agent")
        route.decided_by = "llm"
    return route, span
