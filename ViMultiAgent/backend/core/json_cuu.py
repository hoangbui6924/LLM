"""Cứu JSON bị cắt giữa chừng.

Vì sao cần
----------
Đầu ra của mọi agent là JSON theo schema. Khi model chạm trần `num_predict`,
chuỗi bị cắt ngang:

    {"steps":[{"id":1,"goal_vi":"Tính đạo hàm","expression":"y' = 3x^2 - 6x

Pydantic từ chối cả cụm. Lời giải đã làm gần xong bị vứt sạch, hệ thống trả về
kết quả rỗng — mất trắng vì thiếu vài ký tự đóng ngoặc.

Module này cắt bỏ phần tử dở dang cuối cùng rồi đóng lại các ngoặc còn mở, thu
về phần đã hoàn chỉnh. Ba bước đầu của lời giải vẫn hơn không có gì.

Giới hạn cố ý
-------------
Chỉ cứu JSON bị **cắt cụt**. Không sửa JSON sai cú pháp ở giữa, không đoán giá
trị thiếu, không bịa trường. Nếu phần cứu được vẫn không hợp schema thì trả None
để tầng trên tự xử lý — thà không có còn hơn có dữ liệu bịa.
"""

from __future__ import annotations

import json
from typing import Any

# Ký tự có thể kết thúc một giá trị hợp lệ: đóng ngoặc, đóng chuỗi, chữ số,
# hoặc chữ cái cuối của true/false/null.
_KET_THUC_GIA_TRI = set('}]"0123456789eEl')


def _ke_tiep(s: str, i: int) -> str:
    """Ký tự có nghĩa đầu tiên sau vị trí i, bỏ qua khoảng trắng."""
    j = i
    while j < len(s) and s[j] in " \n\r\t":
        j += 1
    return s[j] if j < len(s) else ""


def _quet(s: str) -> tuple[list[str], int]:
    """Duyệt chuỗi, trả về (ngăn xếp ngoặc còn mở, vị trí an toàn cuối cùng).

    "Vị trí an toàn" là chỉ số ngay sau một GIÁ TRỊ đã kết thúc trọn vẹn.

    Điểm dễ sai nhất: một chuỗi ký tự có thể là KHOÁ hoặc GIÁ TRỊ. Cắt ngay sau
    khoá thì còn lại `{"expression"` — khoá treo lơ lửng, JSON hỏng. Phân biệt
    bằng ký tự kế tiếp: theo sau là dấu hai chấm thì đó là khoá, bỏ qua.
    """
    ngan_xep: list[str] = []
    trong_chuoi = False
    thoat = False
    an_toan = -1

    for i, ch in enumerate(s):
        if trong_chuoi:
            if thoat:
                thoat = False
            elif ch == "\\":
                thoat = True
            elif ch == '"':
                trong_chuoi = False
                # Là khoá thì đừng đánh dấu — cắt ở đó sẽ để khoá không có giá trị.
                if ngan_xep and _ke_tiep(s, i + 1) != ":":
                    an_toan = i + 1
            continue

        if ch == '"':
            trong_chuoi = True
        elif ch == "{":
            ngan_xep.append("}")
        elif ch == "[":
            ngan_xep.append("]")
        elif ch in "}]":
            if ngan_xep:
                ngan_xep.pop()
            if ngan_xep:
                an_toan = i + 1
        elif ch in _KET_THUC_GIA_TRI and ngan_xep:
            # Số hoặc true/false/null chỉ chắc chắn kết thúc khi có dấu phân cách
            # phía sau. Ký tự cuối chuỗi thì không biết còn chữ số nào bị cắt mất.
            #
            # Phải dùng TẬP HỢP chứ không phải `in ",}]"`: chuỗi rỗng là chuỗi con
            # của mọi chuỗi nên `"" in ",}]"` trả về True, khiến ký tự cuối cùng
            # luôn bị coi là đã kết thúc trọn vẹn — đúng cái ta cần loại trừ.
            if _ke_tiep(s, i + 1) in {",", "}", "]"}:
                an_toan = i + 1

    return ngan_xep, an_toan


def cuu(tho: str) -> dict[str, Any] | None:
    """Thử đọc JSON, nếu bị cắt thì cứu phần đã hoàn chỉnh. Không được thì None."""
    if not tho:
        return None

    dau = tho.find("{")
    if dau < 0:
        return None
    s = tho[dau:]

    # Nguyên vẹn thì khỏi cứu.
    try:
        kq = json.loads(s)
        return kq if isinstance(kq, dict) else None
    except json.JSONDecodeError:
        pass

    ngan_xep, an_toan = _quet(s)
    if not ngan_xep or an_toan <= 0:
        return None

    than = s[:an_toan].rstrip().rstrip(",")

    # Đóng ngược lại các ngoặc còn mở. Ngăn xếp lấy theo trạng thái CUỐI chuỗi,
    # nhưng ta đã cắt về `an_toan` nên phải quét lại phần giữ lại.
    ngan_xep_moi, _ = _quet(than)
    if not ngan_xep_moi:
        return None

    ung_vien = than + "".join(reversed(ngan_xep_moi))
    try:
        kq = json.loads(ung_vien)
        return kq if isinstance(kq, dict) else None
    except json.JSONDecodeError:
        return None
