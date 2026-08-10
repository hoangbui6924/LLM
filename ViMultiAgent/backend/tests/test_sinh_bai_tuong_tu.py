"""Kiểm tác tử Sinh bài tập tương tự.

Điều quan trọng nhất bộ này giữ: **đáp án của bài sinh ra phải đúng**. Đề sai đưa
cho học sinh còn tệ hơn không đưa gì — người học không có cách nào biết mình sai
hay đề sai. Vì vậy có hẳn một test tính lại đáp án bằng SymPy từ `bieu_thuc_kiem`
của mẫu, đúng cách `eval/kiem_de_chuan.py` soát 600 bài ground truth.
"""

from __future__ import annotations

import random

import pytest
import sympy as sp

from agents import sinh_bai_tuong_tu as S


class TestKhopChuDe:
    @pytest.mark.parametrize(
        "mon, topic",
        [
            ("math", "dao_ham"),
            ("math", "tich_phan"),
            ("physics", "dao_dong_dieu_hoa"),
            ("chemistry", "khoi_luong_mol"),
            ("chemistry", "tinh_theo_pthh"),
        ],
    )
    def test_sinh_dung_chu_de(self, mon, topic):
        bai = S.sinh(mon=mon, topic=topic, seed=7)
        assert bai is not None
        assert S._bo_dau(bai.topic) == topic

    def test_topic_co_dau_van_khop(self):
        """Planner sinh `khối_lượng_mol`, mẫu ghi `khoi_luong_mol` — phải khớp.

        Đã có lần chấm điểm chủ đề không bao giờ khớp chỉ vì thiếu bước bỏ dấu.
        """
        bai = S.sinh(mon="chemistry", topic="khối_lượng_mol", seed=3)
        assert bai is not None
        assert bai.topic == "khoi_luong_mol"

    def test_khong_co_chu_de_thi_tut_ve_cung_mon(self):
        bai = S.sinh(mon="math", topic="chu_de_khong_ton_tai_abc", seed=5)
        assert bai is not None
        assert bai.de_bai

    def test_mon_la_thi_tra_none_chu_khong_bia(self):
        assert S.sinh(mon="van_hoc", topic="tho") is None


class TestDapAnDungVeKienTao:
    def test_moi_mau_deu_ra_dap_an_khop_bieu_thuc_kiem(self):
        """Tính lại `bieu_thuc_kiem` bằng SymPy, phải trùng `answer_value`.

        Đây là phép soát đã dùng cho 600 bài ground truth. Nếu nó đạt thì đáp án
        của MỌI bài sinh ra đều đúng — bảo đảm về mặt kiến tạo, không phải may rủi.
        """
        r = random.Random(20260810)
        so_kiem = 0
        for mon, ds in S._nap_kho().items():
            for fn, _topic, _muc in ds:
                d = fn(r)
                bt, gt = d.get("bieu_thuc_kiem"), d.get("answer_value")
                if not bt or gt is None or not isinstance(gt, (int, float)):
                    continue
                tinh = float(sp.sympify(bt).evalf())
                assert tinh == pytest.approx(float(gt), rel=1e-6, abs=1e-9), (
                    f"{mon}/{d.get('topic')}: công thức `{bt}` ra {tinh} "
                    f"nhưng mẫu lưu {gt}"
                )
                so_kiem += 1
        assert so_kiem > 100, f"chỉ kiểm được {so_kiem} mẫu, quá ít để yên tâm"


class TestKhongTrungDeVuaGiai:
    def test_khong_tra_lai_dung_de_goc(self):
        goc = S.sinh(mon="math", topic="dao_ham", seed=1)
        assert goc is not None
        for lan in range(20):
            moi = S.sinh(
                mon="math", topic="dao_ham", cau_hoi_goc=goc.de_bai, seed=lan
            )
            assert moi is not None
            assert moi.de_bai != goc.de_bai

    def test_goi_nhieu_lan_ra_de_khac_nhau(self):
        """Là SINH chứ không phải tra cứu: cùng chủ đề phải ra nhiều đề khác nhau."""
        cac_de = {S.sinh(mon="math", topic="dao_ham", seed=i).de_bai for i in range(15)}
        assert len(cac_de) > 3


class TestDangTraVe:
    def test_du_truong_va_dap_an_khong_rong(self):
        bai = S.sinh(mon="physics", topic="dao_dong_dieu_hoa", seed=11)
        assert bai is not None
        assert bai.de_bai.strip()
        assert bai.dap_an.strip()
        assert bai.nguon == "mau_tat_dinh"

    @pytest.mark.parametrize(
        "gia_tri, mong_doi",
        [(8.0, "8"), (0.1, "0,1"), (61.9789, "61,9789"), (-1.5, "-1,5"), (None, "")],
    )
    def test_viet_so_kieu_viet_nam(self, gia_tri, mong_doi):
        assert S._viet_so(gia_tri) == mong_doi
