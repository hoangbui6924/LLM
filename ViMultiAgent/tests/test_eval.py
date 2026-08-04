"""Test cho bộ chấm tự động và bộ sinh dữ liệu PRM.

Chấm sai thì mọi con số trong báo cáo đều sai — đây là chỗ đáng có test nhất
của cả dự án.
"""

from __future__ import annotations

import random

import pytest

from eval.metrics import aggregate, answers_match, is_unit_error, score_item, verifier_prf
from vimultiagent.models.prm import mutate, synth


# ---------------------------------------------------------------------------
# So khớp đáp án
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pred,gold",
    [
        ("0,4 s", "0.397"),                 # dấu phẩy VN + làm tròn trong dung sai
        ("1,2 mm", "1.2"),
        ("3,975×10⁻¹⁹ J", "3.975e-19"),     # chỉ số trên + ký hiệu khoa học
        ("2,24 lít", "2.24"),
        ("e - 1", "1.71828"),               # đáp án ký hiệu
        ("1/6", "0.16667"),                 # phân số
        ("sqrt(2)/2", "0.7071"),
        ("y = 2", "2"),                     # có tiền tố biến
        ("50 Ω", "50"),
    ],
)
def test_answers_match_positive(pred, gold):
    assert answers_match(pred, gold)


@pytest.mark.parametrize(
    "pred,gold",
    [("0,5", "5"), ("120 cm", "1.2"), ("2,24 lít", "6.72"), ("", "5"), ("18", "15")],
)
def test_answers_match_negative(pred, gold):
    assert not answers_match(pred, gold)


def test_unit_error_flagged():
    """Sai đúng một luỹ thừa 10 là dấu hiệu lỗi quy đổi — phải tách riêng được
    để đo hiệu quả của tool layer."""
    assert is_unit_error("120", "1.2")
    assert is_unit_error("0.4", "400")
    assert not is_unit_error("18", "15")


def test_score_item_mcq_prefers_label():
    r = score_item("0,4 s", "A", {"type": "mcq", "answer": "A", "answer_value": "0.397"})
    assert r["correct"] and r["matched_by"] == "choice"

    r2 = score_item("0,4 s", "B", {"type": "mcq", "answer": "A", "answer_value": "0.397"})
    assert not r2["correct"]


def test_verifier_prf_counts_correctly():
    rows = [
        {"verdict": "FAIL", "correct": False},      # TP — bắt đúng
        {"verdict": "FAIL", "correct": True},       # FP — báo oan
        {"verdict": "PASS", "correct": False},      # FN — bỏ sót (đắt nhất)
        {"verdict": "PASS", "correct": True},       # TN
    ]
    m = verifier_prf(rows)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5


def test_aggregate_reports_kpis():
    rows = [
        {"correct": True, "latency_ms": 10_000, "domain": "math", "verdict": "PASS"},
        {"correct": False, "latency_ms": 60_000, "domain": "physics", "verdict": "FAIL"},
    ]
    a = aggregate(rows)
    assert a["accuracy"] == 0.5
    assert a["within_45s"] == 0.5          # KPI độ trễ ≤ 45 s
    assert a["by_domain"]["math"]["accuracy"] == 1.0


# ---------------------------------------------------------------------------
# Sinh dữ liệu PRM
# ---------------------------------------------------------------------------


def test_synth_generates_unique_problems():
    items = synth.generate(200, seed=1)
    assert len(items) == 200
    assert len({i["problem"] for i in items}) == 200, "bộ sinh bị lặp đề"


def test_synth_covers_all_domains():
    doms = {i["domain"] for i in synth.generate(100, seed=1)}
    assert doms == {"math", "physics", "chemistry"}


def test_synth_steps_are_nonempty():
    for it in synth.generate(50, seed=2):
        assert len(it["steps"]) >= 3
        assert all(s.strip() for s in it["steps"])


def test_mutation_changes_exactly_one_step():
    rng = random.Random(0)
    for it in synth.generate(40, seed=3):
        m = mutate.mutate_solution(it["steps"], rng)
        if m is None:
            continue
        diffs = [i for i, (a, b) in enumerate(zip(it["steps"], m["steps"])) if a != b]
        assert diffs == [m["error_step"]], "đột biến phải chạm đúng MỘT bước"


def test_mutate_many_produces_distinct_types():
    rng = random.Random(7)
    items = synth.generate(60, seed=4)
    types: set[str] = set()
    for it in items:
        for m in mutate.mutate_many(it["steps"], rng, k=3):
            types.add(m["mutation_type"])
    # Bộ dữ liệu phải phủ nhiều loại lỗi, nếu không PRM chỉ học được một kiểu
    assert len(types) >= 4, f"chỉ sinh được {types}"
