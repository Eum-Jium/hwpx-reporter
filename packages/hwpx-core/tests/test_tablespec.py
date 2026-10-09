# -*- coding: utf-8 -*-
"""표 규격 — 열 너비 배분.

폭 계산이 갈리면 같은 본문이 경로마다 다른 모양으로 나온다(08-15 감사에서
46063 vs 47531 로 갈려 있었다). 그래서 **합이 언제나 TOTAL_W** 인 것을 여기서
못박는다 — 비율을 받든 안 받든, 나머지 나눗셈이 떨어지든 안 떨어지든.
"""
import pytest

from hwpx_core import tablespec as TS


def test_기본배분은_첫열_고정에_나머지_균등():
    w = TS.col_widths(4)
    assert w[0] == TS.FIRST_W
    assert len(set(w[1:])) <= 2          # 균등(합 보정으로 끝 열만 ±)
    assert sum(w) == TS.TOTAL_W


@pytest.mark.parametrize("n", range(1, 13))
def test_열이_몇_개든_합은_전체너비(n):
    assert sum(TS.col_widths(n)) == TS.TOTAL_W


def test_비율대로_나눈다():
    w = TS.col_widths(3, [1, 4, 2])
    assert sum(w) == TS.TOTAL_W
    # 나눗셈 나머지가 끝 열에 붙으므로 정확 비교 대신 근사로 본다
    assert abs(w[1] / w[0] - 4) < 0.01
    assert abs(w[2] / w[0] - 2) < 0.01


def test_비율은_소수도_받는다():
    w = TS.col_widths(2, [1.5, 2.5])
    assert sum(w) == TS.TOTAL_W
    assert abs(w[1] / w[0] - 2.5 / 1.5) < 0.01


def test_비율_개수가_열_수와_다르면_거부():
    with pytest.raises(ValueError):
        TS.col_widths(3, [1, 2])


@pytest.mark.parametrize("bad", [[1, 0], [1, -2], [1, "2"], [1, None], [1, True]])
def test_0이하_비수치_불리언은_거부(bad):
    # True 는 int 하위형이라 그냥 두면 1 로 새어 들어간다 — 따로 막는지 본다
    with pytest.raises(ValueError):
        TS.col_widths(2, bad)


def test_한_글자도_못_담을_열은_거부():
    with pytest.raises(ValueError) as e:
        TS.col_widths(2, [1, 200])
    assert "좁게" in str(e.value)


def test_거부된_비율은_기본배분으로_되돌릴_수_있다():
    """호출부(renderer)가 잡아 기본 배분으로 떨어뜨리는 계약."""
    try:
        TS.col_widths(2, [1, 200])
    except ValueError:
        assert TS.col_widths(2) == [TS.FIRST_W, TS.TOTAL_W - TS.FIRST_W]


def test_균등_비율은_칸이_1_이내로_고르게_선다():
    """나머지를 끝 열에 몰면 모눈 오른쪽 격자가 어긋난다(40열이면 끝 칸만 +23)."""
    w = TS.col_widths(40, [1] * 40, TS.GRID_MIN_COL_W)
    assert sum(w) == TS.TOTAL_W
    assert max(w) - min(w) <= 1, (min(w), max(w))


def test_모눈은_최소폭을_낮춰_받는다():
    """내용표 최소폭(글자 한 자)을 그대로 걸면 모눈이 통째로 거부된다."""
    with pytest.raises(ValueError):
        TS.col_widths(40, [1] * 40)                     # 기본 최소폭이면 거부
    w = TS.col_widths(40, [1] * 40, TS.GRID_MIN_COL_W)  # 도해 최소폭이면 통과
    assert len(w) == 40


def test_밀리미터_환산은_전체폭_근거와_맞는다():
    assert TS.mm(162.5) == TS.TOTAL_W
    assert TS.mm(1) == 283


# ── 첫 열은 내용에 맞춰 넓힌다 ─────────────────────────────────────────
# 고정 7자였던 동안 `야간 순찰(회/월)`(9자)이 두 줄로 접혀 행이 두 배로 높아졌다
# (08-18 실물). 넓히되 나머지 열을 굶기면 안 되므로 상한이 둘이다.

def test_짧은_항목명이면_종전_폭_그대로다():
    """정본 표 모양이 문서마다 달라지지 않게 — FIRST_W 는 하한이다."""
    assert TS.col_widths(4, first_texts=["구분", "가", "나"])[0] == TS.FIRST_W
    assert TS.col_widths(4)[0] == TS.FIRST_W          # 안 주면 종전 그대로


def test_긴_항목명이면_한_줄에_들어가게_넓힌다():
    w = TS.col_widths(4, first_texts=["구분", "야간 순찰(회/월)"])
    assert w[0] > TS.FIRST_W
    assert w[0] >= TS.text_w("야간 순찰(회/월)") + TS.CELL_PAD
    assert sum(w) == TS.TOTAL_W                        # 전체너비는 그대로


def test_첫_열은_전체의_42퍼센트를_못_넘는다():
    """넓히기만 하면 나머지 열이 좁아져 이번엔 본문 쪽이 접힌다."""
    w = TS.col_widths(4, first_texts=["가" * 40])
    assert w[0] == int(TS.TOTAL_W * TS.FIRST_MAX_RATIO)
    assert sum(w) == TS.TOTAL_W


def test_나머지_열이_최소폭을_못_지키면_안_넓힌다():
    """열이 많은 표에서 첫 열까지 넓히면 나머지가 글자 폭 아래로 내려간다."""
    assert TS.col_widths(20, first_texts=["가" * 40])[0] == TS.FIRST_W


def test_표시폭은_전각과_반각을_나눠_센다():
    """숫자·괄호를 전각으로 세면 첫 열이 쓸데없이 넓어진다."""
    assert TS.text_w("가나") == 2 * TS.CHAR_W_13PT
    assert TS.text_w("ab") == TS.CHAR_W_13PT
    assert TS.text_w("") == 0 and TS.text_w(None) == 0


def test_비율을_준_표에는_첫_열_자동폭이_끼어들지_않는다():
    """비율은 곧 지시다 — 자동폭이 덮으면 호출자가 준 배분이 사라진다."""
    a = TS.col_widths(3, [1, 4, 2])
    b = TS.col_widths(3, [1, 4, 2], first_texts=["야간 순찰(회/월)"])
    assert a == b
