import logging
import pytest


@pytest.fixture(autouse=True, scope="session")
def _quiet_logs():
    logging.getLogger("hwpx").setLevel(logging.CRITICAL)


@pytest.fixture
def sample_doc():
    """대표 공공기관 보고서 블록 JSON (병합·셀스타일·다양한 항목부호 포함)."""
    return {
        "title": "AI 보고서 자동화 추진계획",
        "meta": {"date": "'26. 5. 21.", "department": "○○처"},
        "blocks": [
            {"type": "heading", "text": "1. 추진배경", "level": 2},
            {"type": "paragraph",
             "text": "□ **AI 기반** 보고서 자동화로 반복업무 절감\n"
                     "◦ 표준서식 자동 적용\n- 세부 실행방안 마련\n* 참고: 호스트 연동"},
            {"type": "heading", "text": "2. 현황 및 문제점", "level": 2},
            {"type": "table", "style": "gov",
             "headers": ["구분", "내용", "비고"],
             "rows": [["서식", "통일 안됨", "개선"], ["품질", "편차 큼", "표준화"]]},
            {"type": "heading", "text": "3. 추진방안", "level": 2},
            {"type": "table", "style": "gov",
             "headers": ["단계", "목표", "기한"],
             "rows": [["기반", "표준화", "25~26"], ["중간", "솔루션", "~28"],
                      ["완성", "고도화", "~30"]],
             "merges": [{"r1": 0, "c1": 0, "r2": 0, "c2": 1}],
             "cell_styles": [{"r": 0, "c": 2, "bg": "#B5D4F4", "bold": True}]},
        ],
    }
