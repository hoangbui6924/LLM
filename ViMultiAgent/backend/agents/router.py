"""Router Agent — mục 3.2.

Router chọn Subject Agent theo ba tầng, rẻ trước đắt sau:

    PhoBERT (~30 ms)  ->  luật từ khoá (0 ms)  ->  LLM (2-4 giây)

Tầng nào đủ chắc thì dừng ở đó. Hỏi LLM để phân loại là lãng phí: đó là bài toán
dễ, mà 3-4 giây chiếm gần 10% ngân sách 45 giây của cả lượt.

Từ ba môn về một môn — điều gì đổi
----------------------------------
Trước đây PhoBERT phân loại MÔN (Toán/Lý/Hoá). Hệ thống nay chỉ làm Toán THPT, nên
việc đó không còn ý nghĩa. PhoBERT được chuyển sang việc khó hơn và hữu ích hơn:
**phân loại DẠNG BÀI Toán** (đạo hàm, tích phân, thể tích toạ độ...), rồi Router
quy dạng bài về một trong hai phân môn để chọn agent.

Đổi như vậy được ba thứ cùng lúc, không mất gì:

* Nhãn dạng bài chi tiết hơn nhãn môn, nên bài toán phân loại thực sự cần tới mô
  hình ngôn ngữ — trước đây luật từ khoá gần như đủ, PhoBERT khó chứng minh giá trị.
* `topic` mà PhoBERT trả về được truyền tiếp cho memory pool (`kho_dinh_ly`,
  `kho_loi_giai`) — trước đây trường này phụ thuộc hoàn toàn vào Planner, mà model
  4B sinh slug sai chính tả rất thường xuyên.
* Bộ nhãn dạng bài trùng đúng với bộ dạng mà `tools/kiem_symbolic.py` kiểm chứng
  được, nên Router và tầng kiểm chứng nói chung một ngôn ngữ.
"""

from __future__ import annotations

import re

from agents.base import run_structured
from core import config
from core.schemas import AgentSpan, Plan, Route
from ml import classifier

SYSTEM = """Bạn là Router Agent của hệ thống giải Toán THPT. Mọi đề vào đây đều là
đề TOÁN. Việc của bạn là chọn đúng MỘT phân môn.

Trả JSON: subject ("dai_so"|"hinh_hoc"), agent_name ("dai_so_agent"|"hinh_hoc_agent"),
reason_vi (một câu ngắn), confidence (0..1), decided_by = "llm".

Căn cứ chọn:
- dai_so: hàm số, đạo hàm, nguyên hàm, tích phân, giới hạn, tiệm cận, cực trị,
  GTLN - GTNN, tiếp tuyến, phương trình, bất phương trình, logarit, mũ, dãy số,
  cấp số, tổ hợp - chỉnh hợp, xác suất, số phức
- hinh_hoc: tam giác, đường tròn, thể tích khối chóp - lăng trụ - nón - trụ - cầu,
  diện tích, góc, khoảng cách, mặt phẳng, mặt cầu, vectơ, toạ độ Oxy và Oxyz

Lưu ý ranh giới hay nhầm:
- "Tính diện tích hình phẳng giới hạn bởi đồ thị" là TÍCH PHÂN => dai_so.
- "Khoảng cách từ điểm đến mặt phẳng", "thể tích khối chóp" => hinh_hoc.
- Bài số phức hỏi biểu diễn trên mặt phẳng phức vẫn là dai_so.
"""

# Dưới ngưỡng này coi như PhoBERT không chắc, nhường cho tầng sau. Chọn 0,85 vì
# nhóm câu ranh giới thường rơi vào vùng 0,4-0,7; để thấp hơn thì mô hình sẽ tự
# tin sai ở đúng những câu khó nhất.
NGUONG_PHOBERT = 0.85

_AGENT_OF = {
    "dai_so": "dai_so_agent",
    "hinh_hoc": "hinh_hoc_agent",
}

# Dạng bài (nhãn PhoBERT) -> phân môn. Bộ nhãn cố ý đặt tên tự mô tả: đuôi
# `_dai_so` / `_hinh_hoc` của hai nhãn gom (`khac_*`) nói rõ nhánh, còn các nhãn
# còn lại thì `toa_do_*` là hình học, phần kia là đại số - giải tích.
#
# Bảng này là chỗ DUY NHẤT quy đổi dạng sang phân môn. Thêm dạng mới thì khai ở
# đây, không rải điều kiện ra các file khác.
NHANH_CUA_DANG: dict[str, str] = {
    # --- Đại số & Giải tích ---
    "dao_ham": "dai_so",
    "tich_phan": "dai_so",
    "gioi_han": "dai_so",
    "phuong_trinh": "dai_so",
    "tiep_tuyen": "dai_so",
    "gtln": "dai_so",
    "gtnn": "dai_so",
    "so_diem_cuc_tri": "dai_so",
    "tiem_can_ngang": "dai_so",
    "tiem_can_dung": "dai_so",
    "khac_dai_so": "dai_so",
    # --- Hình học ---
    "toa_do_khoang_cach": "hinh_hoc",
    "toa_do_the_tich": "hinh_hoc",
    "toa_do_kc_diem_mp": "hinh_hoc",
    "khac_hinh_hoc": "hinh_hoc",
}

# Từ khoá đặc trưng. Cố tình chọn từ ÍT chồng lấn giữa hai phân môn.
#
# Ranh giới Đại số - Hình học ở THPT mờ hơn ranh giới Toán - Lý - Hoá rất nhiều
# (một bài toạ độ Oxyz vẫn phải giải hệ phương trình), nên luật ở đây chỉ bắt các
# dấu hiệu KHÔNG thể nhầm: đối tượng hình học có tên riêng, và tên phép tính giải
# tích. Từ chung chung như "phương trình", "tính giá trị" bị loại khỏi cả hai bên.
_RULES: dict[str, list[str]] = {
    "hinh_hoc": [
        "hình chóp", "khối chóp", "lăng trụ", "khối hộp", "tứ diện", "hình nón",
        "khối nón", "hình trụ", "khối trụ", "mặt cầu", "khối cầu", "hình cầu",
        "mặt phẳng", "đường thẳng đi qua", "vectơ", "véc tơ", "toạ độ", "tọa độ",
        "oxyz", "oxy", "tam giác", "đường tròn", "hình vuông", "hình thang",
        "hình bình hành", "thể tích", "diện tích xung quanh", "diện tích toàn phần",
        "khoảng cách từ", "góc giữa", "trung điểm", "trọng tâm", "bán kính",
        "đường cao", "cạnh bên", "đáy", "trực tâm", "hình chiếu",
    ],
    "dai_so": [
        "đạo hàm", "nguyên hàm", "tích phân", "giới hạn", "tiệm cận", "cực trị",
        "cực đại", "cực tiểu", "đồng biến", "nghịch biến", "logarit", "lôgarit",
        "log", "phương trình mũ", "bất phương trình", "hàm số", "đồ thị hàm số",
        "cấp số", "tổ hợp", "chỉnh hợp", "hoán vị", "xác suất", "số phức",
        "môđun", "tiếp tuyến", "giá trị lớn nhất", "giá trị nhỏ nhất",
        "khảo sát", "dãy số", "biệt thức", "vi-ét",
    ],
}


def _by_rule(text: str) -> tuple[str, float, str]:
    low = text.lower()
    score = {k: 0 for k in _RULES}
    hit: dict[str, list[str]] = {k: [] for k in _RULES}
    for nhanh, kws in _RULES.items():
        for kw in kws:
            if re.search(rf"(?<!\w){re.escape(kw)}", low):
                score[nhanh] += 1
                hit[nhanh].append(kw)
    best = max(score, key=lambda k: score[k])
    total = sum(score.values())
    if total == 0:
        return "dai_so", 0.0, "không có từ khoá đặc trưng"
    # Chắc chắn khi phân môn thắng chiếm ưu thế rõ rệt.
    conf = score[best] / total
    return best, conf, "từ khoá: " + ", ".join(hit[best][:3])


async def run(plan: Plan) -> tuple[Route, AgentSpan | None]:
    text = f"{plan.raw_question}\n{plan.normalized_question}"

    # Ưu tiên 1: bộ phân loại PhoBERT do nhóm fine-tune. ~30 ms trên CPU, rẻ hơn
    # hỏi LLM khoảng trăm lần. Chỉ tin khi mô hình đủ chắc; dưới ngưỡng thì câu
    # hỏi đang nằm ở vùng ranh giới, lúc đó mới đáng tiêu token cho LLM.
    nhanh_luat, conf, why = _by_rule(text)

    kq = classifier.du_doan(plan.normalized_question or plan.raw_question)
    if kq is not None:
        dang, do_tin = kq
        # Nhãn lạ (mô hình cũ, hoặc labels.json lệch với mã nguồn) thì bỏ qua hẳn
        # tầng này thay vì tra bảng rồi ném KeyError giữa luồng.
        nhanh_phobert = NHANH_CUA_DANG.get(dang)

        # PhoBERT chỉ được CHỐT khi luật từ khoá không phản đối.
        #
        # Giữ nguyên nguyên tắc đã đo được từ bản ba môn: dữ liệu huấn luyện gồm
        # câu NGẮN, còn đề vận dụng thì dài và nhiều mệnh đề — lệch phân bố, nên
        # độ tin cậy cao mà vẫn sai là chuyện thường. Luật từ khoá thì ngược lại,
        # càng dài càng nhiều từ khoá nên càng chắc. Hai nguồn bù khuyết cho nhau,
        # bất đồng thì không bên nào được tự quyết, đẩy xuống cho LLM.
        luat_khong_phan_doi = conf == 0.0 or nhanh_luat == nhanh_phobert
        if nhanh_phobert and do_tin >= NGUONG_PHOBERT and luat_khong_phan_doi:
            return (
                Route(
                    subject=nhanh_phobert,  # type: ignore[arg-type]
                    agent_name=_AGENT_OF[nhanh_phobert],
                    topic=dang,
                    reason_vi=f"PhoBERT nhận dạng bài `{dang}` (độ tin cậy {do_tin:.2f}).",
                    confidence=do_tin,
                    decided_by="phobert",
                    phobert_confidence=do_tin,
                ),
                None,
            )

    # Ưu tiên 2: luật từ khoá. Planner đã tự tin và luật đồng ý => khỏi gọi LLM.
    if conf >= 0.6 and (plan.confidence < 0.4 or plan.subject == nhanh_luat):
        return (
            Route(
                subject=nhanh_luat,  # type: ignore[arg-type]
                agent_name=_AGENT_OF[nhanh_luat],
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
            subject=nhanh_luat,  # type: ignore[arg-type]
            agent_name=_AGENT_OF[nhanh_luat],
            reason_vi=f"LLM không trả lời được, lùi về luật ({why}).",
            confidence=conf,
            decided_by="rule",
        )
    else:
        route.agent_name = _AGENT_OF.get(route.subject, "dai_so_agent")
        route.decided_by = "llm"
    return route, span
