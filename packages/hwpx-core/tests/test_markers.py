# -*- coding: utf-8 -*-
"""항목부호 판정 단일 기준(hwpx_core.markers) 규격.

경계 규칙이 무너지면 본문 첫 글자가 마커로 먹혀 문서에서 사라진다 —
세 렌더 경로가 전부 이 모듈을 쓰므로 여기서 한 번에 잠근다.
"""
from hwpx_core.markers import CANON, canon_marker, lead_marker, strip_marker


# ── 본문 실문자와 겹치는 별칭은 뒤 공백이 있어야 마커 ─────
def test_ambiguous_aliases_need_space():
    for line in ("-5% 절감 달성", "○○부와 협의 완료", "ㅁ자형 구조물 설치",
                 "ㅇㅇ기관 방문", "-3.2%p 하락"):
        assert lead_marker(line) is None, line
        assert canon_marker(line) is None, line
        assert strip_marker(line) == line.strip(), line   # 한 글자도 잃지 않는다


def test_spaced_aliases_are_markers():
    assert canon_marker("○ 세부 내용") == "◦"
    assert canon_marker("ㅁ 핵심 항목") == "□"
    assert canon_marker("- 상세 근거") == "-"
    assert canon_marker("ㅇ 항목") == "◦"
    assert strip_marker("○ 세부 내용") == "세부 내용"
    assert strip_marker("- 상세 근거") == "상세 근거"


def test_unambiguous_markers_need_no_space():
    # □ ☐ ◦ · ※ 는 본문 첫 글자로 쓰이지 않으므로 공백 없이도 마커(`*` 는 260831 부터 공백이 있어야 마커)
    assert canon_marker("□핵심") == "□"
    assert canon_marker("☐ 핵심") == "□"
    assert canon_marker("※ 출처: 자료") == "*"
    assert canon_marker("· 미세 항목") == "·"
    assert strip_marker("※ 출처: 자료") == "출처: 자료"


def test_non_marker_lines():
    for line in ("1. 개요", "[표1]", "2026년 계획", "일반 본문 줄", ""):
        assert canon_marker(line) is None, line


def test_canon_maps_aliases_to_five_symbols():
    assert set(CANON.values()) == {"□", "◦", "-", "·", "*"}
    assert CANON["☐"] == "□" and CANON["○"] == "◦" and CANON["※"] == "*"


def test_lone_marker_char_is_marker():
    assert lead_marker("-") == "-"      # 마커만 있는 줄(내용 없음)
    assert strip_marker("-") == ""
