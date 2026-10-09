# -*- coding: utf-8 -*-
"""HWPUNIT 척도 상수.

⚠️ 이중 척도 함정(과거 실측으로 확인):
  - 글자 크기(charPr.height):        1pt = 100 HWPUNIT
  - 문단 여백/내어쓰기(hc:margin 하위 intent/left): 1pt = 200 HWPUNIT
두 값을 혼동하면 내어쓰기가 절반(예: 목표 38.6pt → 19.3pt)으로 찍힌다.
"""

# 글자 크기 척도 (charPr.height ÷ 100 = pt)
HWPUNIT_PER_PT_CHAR = 100

# 문단 margin(내어쓰기/여백) 척도 (pt × 200 = HWPUNIT)
HWPUNIT_PER_PT_MARGIN = 200


def char_pt(height: int) -> float:
    """charPr.height(HWPUNIT) → pt."""
    return height / HWPUNIT_PER_PT_CHAR


def margin_hwpunit(pt: float) -> int:
    """문단 여백/내어쓰기 pt → HWPUNIT."""
    return int(round(pt * HWPUNIT_PER_PT_MARGIN))
