"""Tác tử Sinh bài tập tương tự — vai thứ năm trong kiến trúc MetaGPT-inspired.

Giải xong một bài thì sinh cho học sinh MỘT bài cùng dạng để tự luyện.

Vì sao KHÔNG để LLM nghĩ đề
---------------------------
Model 4B trong dự án này vừa tính 0,1 x 62 = 3,8. Một cái đề do nó bịa ra sẽ mang
đúng chất lượng đó, và **đề sai đưa cho học sinh còn tệ hơn không đưa gì** — người
học không có cách nào biết mình sai hay đề sai.

Thay vào đó dùng lại 175 mẫu đề tham số hoá trong `eval/` — chính bộ đã dựng 600
bài ground truth. Mỗi mẫu mã hoá sẵn CÔNG THỨC, còn đáp án do Python tính ra từ
đúng những con số vừa bốc vào đề. Sai số học là không thể xảy ra về mặt kiến tạo.

Đây vẫn là "sinh" chứ không phải "tra cứu": mỗi lần gọi bốc một bộ tham số mới,
nên cùng một mẫu cho ra vô số đề khác nhau.

Vị trí trong luồng
------------------
CHẠY NGOÀI luồng giải, qua endpoint riêng. Nhét vào giữa `solve_stream` là cộng
thẳng thời gian sinh đề vào chỉ số độ trễ end-to-end — thứ tốn nhiều công nhất
mới đạt được 600/600 bài dưới 45 giây. Tách ra thì luồng giải không đụng một dòng.

Chi phí thực tế: không gọi LLM lần nào, nên tính bằng mili giây.
"""

from __future__ import annotations

import random
import unicodedata
from typing import Any, Callable

from core.schemas import BaiTuongTu

# Thứ tự ưu tiên khi tụt hạng tìm mẫu: cùng chủ đề -> cùng độ khó -> cùng môn.
_SO_LAN_THU = 12

_KHO: dict[str, list[tuple[Callable, str, str]]] | None = None


def _bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt để so chủ đề.

    Bắt buộc: Planner sinh ra `khối_lượng_mol` còn mẫu đề ghi `khoi_luong_mol`.
    Đã có lần chấm điểm chủ đề không bao giờ khớp chỉ vì thiếu bước này.
    """
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace(" ", "_").strip("_")


def _nap_kho() -> dict[str, list[tuple[Callable, str, str]]]:
    """Đọc nhãn `topic`/`level` của từng mẫu bằng cách gọi thử một lần.

    Gọi thử chứ không khai tay, vì nhãn nằm trong chính giá trị trả về của mẫu —
    khai riêng ra là tạo thêm một chỗ để lệch.
    """
    global _KHO
    if _KHO is not None:
        return _KHO

    kho: dict[str, list[tuple[Callable, str, str]]] = {}
    r = random.Random(0)
    for mo_dun in _cac_mo_dun_mau():
        for mon, ds in mo_dun.MAU.items():
            for fn in ds:
                try:
                    thu = fn(r)
                except Exception:
                    continue  # mẫu hỏng thì bỏ, không kéo cả kho xuống
                kho.setdefault(mon, []).append(
                    (fn, _bo_dau(thu.get("topic", "")), str(thu.get("level", "")))
                )
    _KHO = kho
    return kho


def _cac_mo_dun_mau() -> list[Any]:
    """Nạp muộn: hai module này chạy `sys.path.insert` lúc import."""
    from eval import build_de_chuan, build_de_kho

    return [build_de_chuan, build_de_kho]


def _chon_mau(mon: str, topic: str, muc: str) -> list[Callable]:
    """Tụt dần độ khớp. Trả rỗng chỉ khi cả môn không có mẫu nào."""
    ds = _nap_kho().get(mon, [])
    if not ds:
        return []
    t = _bo_dau(topic)
    for loc in (
        lambda x: t and x[1] == t,
        lambda x: t and (t in x[1] or x[1] in t) and x[1],
        lambda x: muc and x[2] == muc,
        lambda x: True,
    ):
        hop = [fn for fn in ds if loc(fn)]
        if hop:
            return [fn[0] for fn in hop]
    return []


def sinh(
    mon: str = "math",
    topic: str = "",
    cau_hoi_goc: str = "",
    muc: str = "",
    seed: int | None = None,
) -> BaiTuongTu | None:
    """Sinh MỘT bài cùng dạng. Trả None khi không có mẫu nào dùng được.

    Trả None chứ không bịa — giống mọi tầng tất định khác trong dự án, không đủ
    căn cứ thì im lặng còn hơn đưa ra thứ không bảo đảm.
    """
    cac_mau = _chon_mau(mon, topic, muc)
    if not cac_mau:
        return None

    r = random.Random(seed)
    goc = (cau_hoi_goc or "").strip()

    for _ in range(_SO_LAN_THU):
        fn = r.choice(cac_mau)
        try:
            d = fn(r)
        except Exception:
            continue
        de = str(d.get("question", "")).strip()
        if not de or de == goc:
            continue  # bốc trúng y hệt đề vừa giải thì bốc lại
        return BaiTuongTu(
            de_bai=de,
            dap_an=_viet_so(d.get("answer_value")),
            don_vi=str(d.get("answer_unit", "") or ""),
            topic=str(d.get("topic", "")),
            muc_do=str(d.get("level", "")),
            goi_y=str(d.get("ghi_chu", "") or ""),
            nguon="mau_tat_dinh",
        )
    return None


def _viet_so(x: Any) -> str:
    """Số theo lối viết Việt Nam, bỏ đuôi 0 thừa."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.4f}".rstrip("0").rstrip(".").replace(".", ",")
