"""SQLite — lưu lịch sử hỏi đáp (mục 9 của đề bài).

Chỉ cần bốn cột theo yêu cầu: Question, Answer, Time, Subject. Ta lưu thêm
thời lượng và verdict vì đó là số liệu để viết báo cáo về hiệu quả hệ thống.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from core.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT    NOT NULL,
    answer      TEXT    NOT NULL DEFAULT '',
    subject     TEXT    NOT NULL DEFAULT '',
    verdict     TEXT    NOT NULL DEFAULT '',
    duration_ms REAL    NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


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


def save(
    question: str,
    answer: str,
    subject: str,
    verdict: str,
    duration_ms: float,
) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO history (question, answer, subject, verdict, duration_ms)"
            " VALUES (?, ?, ?, ?, ?)",
            (question, answer, subject, verdict, duration_ms),
        )
        return int(cur.lastrowid or 0)


def recent(limit: int = 20) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def stats() -> dict[str, Any]:
    """Số liệu tổng hợp — dùng cho phần đánh giá hiệu quả trong báo cáo."""
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) n, AVG(duration_ms) avg_ms,"
            " SUM(CASE WHEN verdict='PASS' THEN 1 ELSE 0 END) n_pass"
            " FROM history"
        ).fetchone()
        by_subject = c.execute(
            "SELECT subject, COUNT(*) n, AVG(duration_ms) avg_ms"
            " FROM history GROUP BY subject"
        ).fetchall()
    n = int(row["n"] or 0)
    return {
        "total": n,
        "avg_ms": float(row["avg_ms"] or 0.0),
        "pass_rate": (float(row["n_pass"] or 0) / n) if n else 0.0,
        "by_subject": [dict(r) for r in by_subject],
    }
