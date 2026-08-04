"""Khoá lại đường nạp dữ liệu thật cho PRM.

Đường này trước đây bị đứt âm thầm: `load_real_examples` chỉ đọc memory pool, mà
benchmark luôn chạy `remember=False` nên pool vĩnh viễn rỗng. Không có test thì lần
sau nó đứt lại mà không ai biết — và chỉ phát hiện ra sau khi đã chạy benchmark 1,5 giờ.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vimultiagent.models.prm import harvest


def _sol(steps: list[dict[str, Any]], answer: str = "2,24 lít") -> dict[str, Any]:
    return {"steps": steps, "final_answer": answer, "final_answer_latex": "",
            "mcq_choice": None, "unit": "lít", "self_confidence": 0.8}


def _step(i: int, goal: str, expr: str = "", res: str = "", tool_ok: bool | None = None):
    st: dict[str, Any] = {
        "id": i, "goal_vi": goal, "knowledge_ref": [], "expression_latex": expr,
        "result_latex": res, "justification_vi": "vì công thức áp dụng được",
        "tool_calls": [],
    }
    if tool_ok is not None:
        st["tool_calls"] = [{"tool": "moles", "args": {}, "ok": tool_ok,
                             "result": "0,1", "error": None, "flags": {}}]
    return st


@pytest.fixture
def fake_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(harvest, "REPORTS", reports)
    monkeypatch.setattr(
        harvest, "load_problem_texts",
        lambda: {"c01": "Hòa tan 5,6 gam Fe bằng HCl dư.", "c02": "Đề hai.", "c03": "Đề ba."},
    )
    return reports


def _write(reports: Path, rows: list[dict[str, Any]]) -> None:
    (reports / "x_full.json").write_text(
        json.dumps({"summary": {}, "rows": rows}, ensure_ascii=False), encoding="utf-8"
    )


def test_giữ_lời_giải_đúng_và_ghép_văn_bản_bằng_hàm_dùng_chung(fake_reports: Path) -> None:
    _write(fake_reports, [{
        "id": "c01", "domain": "chemistry", "subtopic": "kim_loai_axit", "correct": True,
        "solution": _sol([_step(1, "Tính số mol Fe", "n = 5,6/56", "0,1 mol"),
                          _step(2, "Tính thể tích", "V = 0,1×22,4", "2,24 lít")]),
    }])
    rows, stat = harvest.harvest(["*_full.json"])
    assert stat["kept"] == 1
    r = rows[0]
    assert r["source_problem_id"] == "c01"          # để chia tập theo nguồn, chống rò rỉ
    assert r["problem"].startswith("Hòa tan")       # tra ngược được nội dung đề
    assert len(r["steps"]) == 2
    # Văn bản bước phải gồm ĐỦ các trường, đúng như PRM nhận lúc suy luận —
    # không phải chỉ goal_vi như memory pool từng ghi.
    assert "5,6/56" in r["steps"][0] and "0,1 mol" in r["steps"][0]


def test_bỏ_lời_giải_sai_thay_vì_đoán_nhãn_bước(fake_reports: Path) -> None:
    """Đáp số sai chỉ cho biết CÓ bước sai, không cho biết bước nào."""
    _write(fake_reports, [{
        "id": "c01", "domain": "chemistry", "subtopic": "x", "correct": False,
        "solution": _sol([_step(1, "a", "x", "1"), _step(2, "b", "y", "2")]),
    }])
    _, stat = harvest.harvest(["*_full.json"])
    assert stat["kept"] == 0 and stat["incorrect"] == 1


def test_bỏ_khi_công_cụ_báo_lỗi(fake_reports: Path) -> None:
    _write(fake_reports, [{
        "id": "c01", "domain": "chemistry", "subtopic": "x", "correct": True,
        "solution": _sol([_step(1, "a", "x", "1", tool_ok=False),
                          _step(2, "b", "y", "2")]),
    }])
    _, stat = harvest.harvest(["*_full.json"])
    assert stat["kept"] == 0 and stat["tool_failed"] == 1


def test_báo_cáo_cũ_không_có_solution_thì_nói_rõ(fake_reports: Path) -> None:
    _write(fake_reports, [{"id": "c01", "domain": "math", "correct": True}])
    _, stat = harvest.harvest(["*_full.json"])
    assert stat["kept"] == 0 and stat["no_solution"] == 1


def test_giữ_kín_theo_id(fake_reports: Path) -> None:
    _write(fake_reports, [
        {"id": "c01", "domain": "math", "subtopic": "x", "correct": True,
         "solution": _sol([_step(1, "a", "x", "1"), _step(2, "b", "y", "2")])},
        {"id": "c02", "domain": "math", "subtopic": "x", "correct": True,
         "solution": _sol([_step(1, "c", "z", "3"), _step(2, "d", "w", "4")])},
    ])
    _, stat = harvest.harvest(["*_full.json"], exclude_ids={"c02"})
    assert stat["kept"] == 1 and stat["excluded"] == 1


def test_data_build_đọc_được_file_thu_hoạch(tmp_path: Path, monkeypatch) -> None:
    """Mắt xích cuối: file harvest ghi ra phải được data_build nạp vào huấn luyện."""
    from vimultiagent.models.prm import data_build

    f = tmp_path / "real_solutions.jsonl"
    f.write_text(json.dumps({
        "id": "real_c01_0", "source_problem_id": "c01", "problem": "Đề bài",
        "steps": ["B một đầy đủ", "B hai đầy đủ"], "domain": "chemistry", "subtopic": "x",
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    got = data_build._read_real_file(f)
    assert len(got) == 1 and got[0]["steps"] == ["B một đầy đủ", "B hai đầy đủ"]


def test_bản_ghi_cũ_chỉ_có_sketch_vẫn_lùi_về_được(tmp_path: Path) -> None:
    from vimultiagent.models.prm import data_build

    f = tmp_path / "solved_examples.jsonl"
    f.write_text(json.dumps({
        "id": "ex_1", "problem": "Đề", "solution_sketch": "mục tiêu một → mục tiêu hai",
        "domain": "math", "subtopic": "y",
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    got = data_build._read_real_file(f)
    assert len(got) == 1 and len(got[0]["steps"]) == 2
