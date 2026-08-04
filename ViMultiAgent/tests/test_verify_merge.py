"""Quy tắc hợp nhất verdict và bộ chặn subtopic lạc miền.

Cả hai đều xuất phát từ một lần chạy thật (bài Fe + HCl, xem docs/04-ket-qua.md):
subtopic bị gán "so_phuc" cho bài Hoá, và verdict ra FAIL với tỉ số 3 thắng 1.
"""

from __future__ import annotations

import asyncio

from vimultiagent.agents import verifier
from vimultiagent.agents.analyzer import subtopic_matches_domain
from vimultiagent.core.schemas import (
    ProblemSpec,
    Solution,
    SolutionStep,
    Verdict,
    VerdictItem,
)


def _spec() -> ProblemSpec:
    return ProblemSpec(domain="chemistry", subtopic="kim_loai_axit",
                       question_type="numeric", raw_text="Hòa tan 5,6 gam Fe...")


def _sol() -> Solution:
    return Solution(steps=[SolutionStep(id=1, goal_vi="Tính mol")],
                    final_answer="2,24 lít")


def _merge(items: list[VerdictItem], agreement: bool) -> Verdict:
    """Chạy ĐÚNG `verifier.verify()`, chỉ thay các tầng bằng kết quả dựng sẵn.

    Cố ý KHÔNG chép lại đoạn hợp nhất vào đây. Một test chép lại logic của code sẽ
    pass kể cả khi code thật hỏng — nó chỉ kiểm tra rằng bản sao khớp bản sao.
    """
    t1_items = [i for i in items if i.check_type not in ("independent", "stepwise")]
    t2 = next((i for i in items if i.check_type == "independent"), None)
    t3 = next((i for i in items if i.check_type == "stepwise"), None)

    async def fake_t2(client, spec, sol, profile=None):  # noqa: ANN001, ARG001
        return t2, "2,24 lít", []

    async def fake_t3(client, spec, sol, profile=None):  # noqa: ANN001, ARG001
        return t3, None, []

    tiers = ["T1"] + (["T2"] if t2 else []) + (["T3"] if t3 else [])

    async def run() -> Verdict:
        rep, _ = await verifier.verify(None, _spec(), _sol(), tiers=tiers)  # type: ignore[arg-type]
        return rep.verdict

    orig = (verifier.verify_t1, verifier.verify_t2, verifier.verify_t3)
    verifier.verify_t1 = lambda spec, sol: list(t1_items)  # type: ignore[assignment]
    verifier.verify_t2 = fake_t2                            # type: ignore[assignment]
    verifier.verify_t3 = fake_t3                            # type: ignore[assignment]
    try:
        # `agreement` do chính verify() suy ra từ item của T2 — không đặt tay,
        # nếu không thì lại đang kiểm một trạng thái mà code thật không tạo ra.
        assert t2 is None or t2.passed == agreement
        return asyncio.run(run())
    finally:
        verifier.verify_t1, verifier.verify_t2, verifier.verify_t3 = orig


def test_t3_một_mình_không_được_phủ_quyết_khi_t2_đã_đồng_thuận() -> None:
    """Đúng tình huống bài Fe + HCl: prm ✓ symbolic ✓ independent ✓ stepwise ✗."""
    items = [
        VerdictItem(check_type="prm_advisory", passed=True),
        VerdictItem(check_type="symbolic", passed=True),
        VerdictItem(check_type="independent", passed=True),
        VerdictItem(check_type="stepwise", passed=False, detail_vi="bước 3 đáng ngờ"),
    ]
    assert _merge(items, agreement=True) == Verdict.UNCERTAIN


def test_t3_vẫn_bác_bỏ_được_khi_t2_KHÔNG_đồng_thuận() -> None:
    """Không được nới lỏng quá tay: T2 bất đồng + T3 thấy lỗi thì vẫn phải FAIL."""
    items = [
        VerdictItem(check_type="independent", passed=False),
        VerdictItem(check_type="stepwise", passed=False),
    ]
    assert _merge(items, agreement=False) == Verdict.FAIL


def test_chỉ_t2_bất_đồng_thì_uncertain() -> None:
    items = [VerdictItem(check_type="independent", passed=False)]
    assert _merge(items, agreement=False) == Verdict.UNCERTAIN


def test_kiểm_tra_tất_định_trượt_thì_vẫn_fail() -> None:
    items = [
        VerdictItem(check_type="substitution", passed=False),
        VerdictItem(check_type="stepwise", passed=False),
    ]
    assert _merge(items, agreement=True) == Verdict.FAIL


def test_mọi_thứ_đạt_thì_pass() -> None:
    assert _merge([VerdictItem(check_type="symbolic", passed=True)], True) == Verdict.PASS


# --- subtopic lạc miền -----------------------------------------------------


def test_bắt_được_subtopic_lạc_miền() -> None:
    assert not subtopic_matches_domain("so_phuc", "chemistry")   # ca thật đã xảy ra
    assert not subtopic_matches_domain("dao_dong_dieu_hoa", "math")
    assert not subtopic_matches_domain("este_lipit", "physics")


def test_không_đụng_tới_subtopic_hợp_lệ() -> None:
    assert subtopic_matches_domain("so_phuc", "math")
    assert subtopic_matches_domain("dao_dong_dieu_hoa", "physics")
    assert subtopic_matches_domain("este_lipit", "chemistry")
    assert subtopic_matches_domain("con_lac_lo_xo", "physics")


def test_không_kết_luận_được_thì_giữ_nguyên() -> None:
    """Bộ này chỉ bắt lỗi RÕ RÀNG. Nhầm hướng kia sẽ vứt bỏ subtopic hợp lệ."""
    assert subtopic_matches_domain("mot_chu_de_la", "math")
    assert subtopic_matches_domain("", "chemistry")
