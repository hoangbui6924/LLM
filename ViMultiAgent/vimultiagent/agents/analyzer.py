"""Tác tử PHÂN TÍCH ĐỀ.

Đây là nơi lỗi rẻ nhất để sửa. Đọc sai đơn vị ở đây (cm thay vì m) làm hỏng toàn bộ
pipeline phía sau, và Verifier sẽ tốn 3 lượt gọi LLM để phát hiện ra điều mà Analyzer
lẽ ra chỉ cần đọc đúng một lần.
"""

from __future__ import annotations

import re

from ..core.llm import LLMClient
from ..core.prompts import ANALYZER_SYSTEM, ANALYZER_USER
from ..core.schemas import AgentSpan, ProblemSpec

# Từ khoá bắt miền — dùng làm lưới an toàn khi LLM phân loại sai, và làm
# đường lui khi chưa huấn luyện xong router.
_HINTS = {
    "chemistry": [
        "mol", "dung dịch", "phản ứng", "chất", "axit", "bazơ", "muối", "kim loại",
        "oxi hoá", "oxi hóa", "khử", "este", "amin", "polime", "hiđro", "hidro",
        "nồng độ", "kết tủa", "điện phân", "ph ", "gam", "khí", "nguyên tố",
    ],
    "physics": [
        "dao động", "sóng", "điện", "dòng điện", "hiệu điện thế", "vận tốc",
        "gia tốc", "lực", "năng lượng", "công suất", "hạt nhân", "photon",
        "con lắc", "biên độ", "tần số", "chu kỳ", "cảm kháng", "dung kháng",
        "khối lượng", "quãng đường", "ánh sáng", "phóng xạ", "tia",
    ],
    "math": [
        "hàm số", "đạo hàm", "nguyên hàm", "tích phân", "phương trình", "bất phương trình",
        "logarit", "số phức", "cấp số", "tổ hợp", "xác suất", "vectơ", "mặt phẳng",
        "đường thẳng", "hình chóp", "khối trụ", "tiệm cận", "cực trị", "đồ thị",
    ],
}


def heuristic_domain(text: str) -> str:
    """Bỏ dấu cả hai phía trước khi so.

    Học sinh gõ nhanh thường không bỏ dấu ('dao dong dieu hoa'), mà từ khoá thì
    viết có dấu — so trực tiếp sẽ trượt sạch và bài Vật lý bị đẩy sang Toán.
    """
    from ..memory.store import strip_accents  # noqa: PLC0415

    t = strip_accents(text.lower())
    score = {
        d: sum(1 for kw in kws if strip_accents(kw) in t) for d, kws in _HINTS.items()
    }
    best = max(score, key=lambda k: score[k])
    return best if score[best] > 0 else "math"


# Mã subtopic đặc trưng cho từng miền. Chỉ cần đủ để phát hiện subtopic LẠC MIỀN —
# không cần liệt kê hết chương trình.
_SUBTOPIC_DOMAIN = {
    "math": (
        "so_phuc", "tich_phan", "nguyen_ham", "dao_ham", "logarit", "mu_logarit",
        "to_hop", "xac_suat", "cap_so", "hinh_oxyz", "hinh_chop", "khoi_tru",
        "tiem_can", "cuc_tri", "khao_sat_ham_so", "phuong_trinh", "bat_phuong_trinh",
    ),
    "physics": (
        "dao_dong", "con_lac", "song_co", "song_anh_sang", "dien_xoay_chieu",
        "hat_nhan", "luong_tu", "giao_thoa", "quang_dien", "phong_xa", "song_dung",
    ),
    "chemistry": (
        "este", "lipit", "amin", "amino_axit", "polime", "kim_loai", "axit",
        "dien_phan", "phan_ung_oxi_hoa_khu", "dung_dich", "ph", "stoichiometry",
        "mol", "hidrocacbon", "ancol", "cacbohidrat",
    ),
}


def subtopic_matches_domain(subtopic: str, domain: str) -> bool:
    """`subtopic` có thuộc về `domain` không.

    Trả True khi không kết luận được — bộ này chỉ để bắt lỗi RÕ RÀNG, không phải để
    phán xét mọi mã subtopic. Nhầm hướng kia sẽ vứt bỏ subtopic hợp lệ.
    """
    if not subtopic:
        return True
    s = subtopic.lower()
    owner = None
    for dom, keys in _SUBTOPIC_DOMAIN.items():
        if any(k in s for k in keys):
            owner = dom
            break
    return owner is None or owner == domain


def detect_choices(text: str) -> dict[str, str] | None:
    """Bóc phương án A/B/C/D. Đề trắc nghiệm Việt Nam viết khá đa dạng
    (A. / A) / **A.**), nên bắt bằng regex rộng rồi kiểm tính hợp lý."""
    pattern = re.compile(r"(?:^|\s|\*\*)([ABCD])[\.\)]\s*(.+?)(?=(?:\s|\*\*)[ABCD][\.\)]|$)", re.S)
    found = pattern.findall(text)
    if len(found) >= 3:
        out = {k: v.strip().strip("*").strip() for k, v in found}
        if all(len(v) < 200 for v in out.values()):
            return out
    return None


async def analyze(
    client: LLMClient, problem: str, profile: str | None = None
) -> tuple[ProblemSpec, list[AgentSpan]]:
    messages = [
        {"role": "system", "content": ANALYZER_SYSTEM},
        {"role": "user", "content": ANALYZER_USER.format(problem=problem)},
    ]
    try:
        spec, spans = await client.chat_json(
            "analyzer", messages, ProblemSpec, profile=profile
        )
    except Exception:
        # Analyzer hỏng KHÔNG được làm sập cả hệ thống — lùi về heuristic và đi tiếp.
        # Lời giải kém còn hơn không có lời giải nào.
        spec = ProblemSpec(
            domain=heuristic_domain(problem),  # type: ignore[arg-type]
            question_type="mcq" if detect_choices(problem) else "numeric",
            choices=detect_choices(problem),
            confidence=0.25,
            ambiguity_flags=["Phân tích đề tự động thất bại, dùng heuristic"],
        )
        spans = []

    spec.raw_text = problem
    if spec.choices is None:
        spec.choices = detect_choices(problem)
    if spec.choices and spec.question_type != "mcq":
        spec.question_type = "mcq"

    # Chặn subtopic LẠC MIỀN. Đã quan sát trực tiếp: bài "Fe + HCl" được gán
    # domain=chemistry nhưng subtopic="so_phuc" (số phức). Retriever dựng truy vấn
    # TỪ CHÍNH subtopic (agents/retriever.py), nên một mã sai kéo theo cả kho trả về
    # rác — lần đó là "Điện phân và định luật Faraday" cho bài kim loại + axit, và
    # rác đó chui thẳng vào mục "Kiến thức cần dùng" của lời giảng.
    #
    # Xoá thì tốt hơn giữ: Retriever vẫn còn subgoals và domain để dựng truy vấn,
    # còn một subtopic sai thì chủ động lái truy hồi đi sai hướng.
    if not subtopic_matches_domain(spec.subtopic, spec.domain):
        spec.ambiguity_flags.append(
            f"Bỏ subtopic '{spec.subtopic}' vì không thuộc miền '{spec.domain}'"
        )
        spec.subtopic = ""

    return spec, spans


def analyze_heuristic(problem: str) -> ProblemSpec:
    """Phân tích đề KHÔNG dùng LLM — chỉ từ khoá + regex.

    Bỏ được một lượt gọi model (20-40 s trên Ollama 3B). Đánh đổi: không bóc được
    givens/unknowns có cấu trúc, nên Solver phải tự đọc từ đề gốc. Với model nhỏ
    thì đánh đổi này có lợi rõ ràng — nó vốn cũng bỏ qua phần lớn givens đã bóc.
    """
    choices = detect_choices(problem)
    return ProblemSpec(
        domain=heuristic_domain(problem),  # type: ignore[arg-type]
        question_type="mcq" if choices else "numeric",
        choices=choices,
        raw_text=problem,
        confidence=0.5,
        routed_by="llm",
    )
