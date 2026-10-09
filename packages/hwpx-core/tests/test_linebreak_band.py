# -*- coding: utf-8 -*-
"""자수 경고 값 — 260928 V4 규격(□ 한 줄 38자까지 · ◦ 두 줄 66~70자)."""
from hwpx_core import linebreak as L


def _분량(line):
    return [w for w in L.check_lines([line]) if "자다" in w]


def test_band_values():
    assert L.BOX_ONE_LINE_MAX == 38
    assert L.DOT_TWO_LINE == (66, 70)
    assert not hasattr(L, "BOX_TWO_LINE")          # □ 두 줄 허용은 뗐다


def test_box_is_one_line_only():
    assert _분량("□ " + "가" * 36) == []           # 38자
    warns = _분량("□ " + "가" * 68)                 # 70자 — 옛 두 줄 규격 안이었다
    assert warns and "◦ 로 내릴 것" in warns[0]


def test_dot_band_66_to_70():
    for n in (66, 70):
        assert _분량("◦ " + "가" * (n - 2)) == [], n
    for n in (64, 72):
        assert _분량("◦ " + "가" * (n - 2)), n
