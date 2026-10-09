# -*- coding: utf-8 -*-
"""hwpx-core — HWPX(한글) 저수준 읽기/쓰기 공용 툴킷.

reader·skeleton(및 다른 도구)이 공유하는 zip·XML·charmap 원시함수를 모은다.
python-hwpx 기반 writer 는 저수준 스택이 달라 zip/XML 원시함수는 쓰지 않지만,
항목부호 판정(markers)과 그림 임베드(bindata)는 세 렌더 경로가 같아야 하므로 공유한다.
"""
from .ns import HP, HH, local
from .zipio import (
    HwpxError, validate_hwpx, read_members, write_hwpx,
    section_names, SECTION0, HEADER,
)
from .read import (
    para_text, iter_body_paragraphs, cell_text, extract_tables,
    parse_charmap, para_charsize,
)
from .markers import CANON, AMBIGUOUS, lead_marker, canon_marker, strip_marker
from .gaps import gap_pt
from .schedule import pad_tab_date
from .outline import outline_for, check_outline, check_future_plan
from .volume import fills_page, shortfall_lines
from .endings import check_endings, is_verb_ending
from .linebreak import check_lines, break_points
from .memo import read_memos, read_memos_from, add_memos, annotate
from .bindata import add_image, pic_xml, pic_element, image_size
from .mdconv import clean_md, tabify, convert_rows, convert_md
from . import (units, markers, gaps, schedule, tablespec, xmlcompat, outline,
               volume, endings, linebreak, memo, bindata, mdconv)

__all__ = [
    "HP", "HH", "local",
    "clean_md", "tabify", "convert_rows", "convert_md",
    "HwpxError", "validate_hwpx", "read_members", "write_hwpx",
    "section_names", "SECTION0", "HEADER",
    "para_text", "iter_body_paragraphs", "cell_text", "extract_tables",
    "parse_charmap", "para_charsize",
    "CANON", "AMBIGUOUS", "lead_marker", "canon_marker", "strip_marker",
    "gap_pt", "pad_tab_date", "outline_for", "check_outline", "check_future_plan",
    "read_memos", "read_memos_from", "add_memos", "annotate",
    "add_image", "pic_xml", "pic_element", "image_size",
    "fills_page", "shortfall_lines", "check_endings", "is_verb_ending", "check_lines", "break_points", "require_version",
    "units", "markers", "gaps", "schedule", "tablespec", "xmlcompat", "outline",
    "volume", "endings", "linebreak", "memo", "bindata",
]
__version__ = "0.1.6"


def require_version(caller: str, series: str = "0.1") -> None:
    """호출 패키지가 기대하는 hwpx-core 계열인지 **임포트 시점**에 확인한다.

    내부 패키지들은 서로를 pyproject 의존성으로 적지 않는다 — 이 이름들은 어떤
    인덱스에도 없어서 pip 이 해결해 줄 수 없고(로컬 경로로 같이 설치해야 한다),
    적어 두면 한 개만 설치할 때 pip 이 **공개 PyPI 에서 같은 이름을 찾는다**
    (dependency confusion). 즉 선언은 실익 0, 위험만 남는다. 판이 맞는지 보는
    일은 선언이 아니라 여기서 한다 — 실제로 돌 때 확인하므로 더 정확하다.

    ※ 언젠가 이 이름들을 PyPI 에 실제로 게시하면, 그때는 pyproject 에 핀을
      되살리는 편이 낫다(그 시점엔 인덱스 해석이 곧 정답이므로).
    """
    if __version__ != series and not __version__.startswith(series + "."):
        raise ImportError(
            f"{caller} 는 hwpx-core {series}.x 를 기대하는데 설치된 판은 "
            f"{__version__} 이다. 다섯 패키지를 리포의 로컬 경로로 함께 설치할 것: "
            "pip install -e packages/hwpx-core -e packages/hwpx-reader "
            "-e packages/hwpx-skeleton -e packages/hwpx-writer "
            "-e packages/hwpx-report-policy")
