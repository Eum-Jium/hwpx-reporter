# -*- coding: utf-8 -*-
"""style.py 회귀: detect_level 오검출(**·두자리숫자), 날짜 마침표, build_flow ** 제거."""
from hwpx_skeleton.style import (
    detect_level, build_flow, _strip_trailing_period,
)


# ── M2: ** 볼드 마크다운 ─────────────────────────────────
def test_bold_wrapped_box_detected_as_box():
    assert detect_level("**□ 중요 항목**") == "□"


def test_bold_wrapped_heading_detected_as_heading():
    assert detect_level("**1. 개요**") == "heading"


def test_plain_ref_marker_still_ref():
    assert detect_level("* 관련근거: 행정기본법") == "*"


def test_build_flow_strips_bold_markers():
    flow = build_flow(["1. 개요", "**□ 중요 항목**"])
    texts = [f["text"] for f in flow if not f.get("blank")]
    assert any("중요 항목" in t and "**" not in t for t in texts)
    # □ 규격(15pt)으로 판정되어야 함 (참고 13pt 아님)
    box = next(f for f in flow if "중요 항목" in f.get("text", ""))
    assert box["size"] == 15


# ── M3: 두 자리 숫자 시작 줄 ─────────────────────────────
def test_year_line_is_not_heading():
    assert detect_level("2026년 예산 확보 필요") == "□"


def test_percent_line_is_not_heading():
    assert detect_level("50% 절감 달성") == "□"


def test_decimal_line_is_not_heading():
    assert detect_level("3.5배 성장 전망") == "□"


def test_numbered_headings_still_detected():
    assert detect_level("1. 추진배경") == "heading"
    assert detect_level("12. 기타사항") == "heading"
    assert detect_level("Ⅱ 추진계획") == "heading"


# ── 날짜 종결 마침표 보존 ────────────────────────────────
def test_trailing_period_removed_for_prose():
    assert _strip_trailing_period("보고서를 작성함.") == "보고서를 작성함"


def test_date_final_period_preserved():
    assert _strip_trailing_period("시행일: 2026. 7. 2.") == "시행일: 2026. 7. 2."


def test_hierarchy_promotion_survives_bold():
    # □ 아래 ◦ 없이 등장한 - 는 ◦ 로 승격 (** 가 섞여도)
    flow = build_flow(["□ 항목", "**- 세부**"])
    texts = [f["text"] for f in flow if not f.get("blank")]
    assert any(t.lstrip().startswith("◦") and "세부" in t for t in texts)
