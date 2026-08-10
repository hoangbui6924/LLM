"""Kho lời giải đã kiểm chứng — nửa "solved examples" của memory pool.

Đây là phần khiến hệ thống KHÁ LÊN khi dùng nhiều, thay vì đứng yên. Hiện tại mỗi
lượt giải là một tờ giấy trắng: bài thứ 300 được giải bằng đúng bộ não mà bài thứ
nhất dùng, không có ký ức nào bắc cầu. Bảng `history` có lưu câu hỏi và đáp án
nhưng KHÔNG lưu các bước giải, nên hàng trăm lượt đã chạy đều không tái dùng được.

Nguyên tắc
----------
1. **Chỉ cất lời giải đã qua kiểm chứng.** Verify trả PASS mới lưu. Cất lời giải
   sai vào kho là tự đầu độc: lần sau nó được đem ra làm mẫu và nhân bản cái sai.
2. **Tra cứu bằng từ khoá, không dùng embedding.** Thêm mô hình nhúng là thêm vài
   trăm MB RAM tranh chỗ với Ollama trên máy 6 GB VRAM. `Plan.topic` mà Planner
   sinh ra đã là khoá phân loại sẵn có.
3. **Không bao giờ làm hỏng lượt giải.** Mọi lỗi truy cập kho đều bị nuốt và trả
   về rỗng — không có ví dụ mẫu thì giải như cũ, chứ không được đổ.
4. **Không tự lấy lại chính mình.** Câu hỏi trùng khít bị loại khỏi kết quả tra,
   nếu không hệ thống sẽ chép lại đáp án cũ thay vì giải.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from typing import Any, Iterator

from core.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS loi_giai_mau (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT    NOT NULL,
    subject     TEXT    NOT NULL DEFAULT '',
    topic       TEXT    NOT NULL DEFAULT '',
    level       TEXT    NOT NULL DEFAULT '',
    steps_json  TEXT    NOT NULL DEFAULT '[]',
    final_answer TEXT   NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_lgm_subject_topic ON loi_giai_mau (subject, topic);
"""

# Từ quá phổ biến, xuất hiện ở mọi đề nên không phân biệt được gì.
_TU_DUNG = {
    "tinh", "cho", "cua", "va", "voi", "duoc", "co", "la", "mot", "cac", "bao",
    "nhieu", "hay", "tim", "biet", "sau", "khi", "trong", "den", "tu", "theo",
    "bang", "gam", "mol", "lit", "ml", "phuong", "trinh", "bai", "toan",
}


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with _conn() as c:
        c.executescript(_SCHEMA)


def _bo_dau(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(ch) != "Mn"
    ).replace("đ", "d")


def _tu_khoa(s: str) -> set[str]:
    """Tập từ có nghĩa để so khớp, bỏ số và từ dừng."""
    return {
        t for t in re.findall(r"[a-z]{3,}", _bo_dau(s))
        if t not in _TU_DUNG
    }


def luu(
    question: str,
    subject: str,
    topic: str,
    steps: list[dict[str, Any]],
    final_answer: str,
    level: str = "",
) -> bool:
    """Cất một lời giải ĐÃ QUA KIỂM CHỨNG. Trả True nếu lưu được.

    Không ném lỗi ra ngoài: lưu hỏng thì lượt hỏi vẫn phải trả lời bình thường.
    """
    if not question.strip() or not steps or not final_answer.strip():
        return False
    try:
        init()
        with _conn() as c:
            # Cùng một câu hỏi thì chỉ giữ bản mới nhất, tránh kho phình vì chạy
            # bench lặp lại trên cùng bộ đề.
            c.execute("DELETE FROM loi_giai_mau WHERE question = ?", (question.strip(),))
            c.execute(
                "INSERT INTO loi_giai_mau (question, subject, topic, level, steps_json,"
                " final_answer) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    question.strip(),
                    subject,
                    topic,
                    level,
                    json.dumps(steps, ensure_ascii=False),
                    final_answer.strip(),
                ),
            )
        return True
    except Exception:  # noqa: BLE001 — kho hỏng không được làm hỏng câu trả lời
        return False


def tim(subject: str, topic: str, cau_hoi: str, so_luong: int = 1) -> list[dict[str, Any]]:
    """Tìm lời giải mẫu gần nhất. Trả danh sách rỗng khi không có gì hợp.

    Chấm điểm: cùng topic +3, mỗi từ khoá chung +1. Câu hỏi TRÙNG KHÍT bị loại —
    lấy lại chính nó thì hệ thống chỉ chép đáp án, không còn giải.
    """
    try:
        init()
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM loi_giai_mau WHERE subject = ? ORDER BY id DESC LIMIT 400",
                (subject,),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return []

    if not rows:
        return []

    tu_de = _tu_khoa(cau_hoi)
    chuan = cau_hoi.strip()
    cham: list[tuple[int, dict[str, Any]]] = []

    for r in rows:
        if r["question"].strip() == chuan:
            continue
        # So topic sau khi bỏ dấu: model sinh slug lúc có dấu lúc không
        # (`khối_lượng_mol` và `khoi_luong_mol`), so thẳng thì trượt.
        diem = 3 if topic and _bo_dau(r["topic"]) == _bo_dau(topic) else 0
        diem += len(tu_de & _tu_khoa(r["question"]))
        if diem >= 3:
            cham.append((diem, dict(r)))

    cham.sort(key=lambda x: -x[0])
    return [d for _, d in cham[:so_luong]]


def doan_van(subject: str, topic: str, cau_hoi: str, so_luong: int = 1) -> str:
    """Ví dụ mẫu dạng văn bản, chèn thẳng vào prompt. Rỗng nếu không có gì hợp."""
    mau = tim(subject, topic, cau_hoi, so_luong)
    if not mau:
        return ""

    khoi: list[str] = []
    for m in mau:
        try:
            steps = json.loads(m["steps_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        dong = [f"Đề tương tự đã giải đúng: {m['question']}"]
        for st in steps[:5]:
            goal = (st.get("goal_vi") or "").strip()
            expr = (st.get("expression") or "").strip()
            kq = (st.get("result") or "").strip()
            dong.append(f"  Bước {st.get('id', '?')}: {goal}" + (f" | {expr}" if expr else "")
                        + (f" => {kq}" if kq else ""))
        dong.append(f"  Đáp số: {m['final_answer']}")
        khoi.append("\n".join(dong))

    if not khoi:
        return ""
    return (
        "Tham khảo cách làm dưới đây, nhưng SỐ LIỆU CỦA ĐỀ NÀY KHÁC — phải tính lại "
        "từ đầu, tuyệt đối không chép đáp số:\n" + "\n\n".join(khoi)
    )


def thong_ke() -> dict[str, Any]:
    """Số liệu về kho, dùng cho endpoint theo dõi và cho báo cáo."""
    try:
        init()
        with _conn() as c:
            tong = c.execute("SELECT COUNT(*) n FROM loi_giai_mau").fetchone()["n"]
            theo_mon = c.execute(
                "SELECT subject, COUNT(*) n FROM loi_giai_mau GROUP BY subject"
            ).fetchall()
            theo_topic = c.execute(
                "SELECT topic, COUNT(*) n FROM loi_giai_mau GROUP BY topic"
                " ORDER BY n DESC LIMIT 10"
            ).fetchall()
        return {
            "tong": tong,
            "theo_mon": {r["subject"]: r["n"] for r in theo_mon},
            "topic_nhieu_nhat": {r["topic"]: r["n"] for r in theo_topic},
        }
    except Exception as e:  # noqa: BLE001
        return {"tong": 0, "loi": str(e)}
