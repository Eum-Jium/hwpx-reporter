# -*- coding: utf-8 -*-
"""5차 코드리뷰 수정 회귀 — hwpx-core 읽기 원시함수 (reader 가 소비).

중첩 표의 행·텍스트 중복 계상 금지 + 주석 노드 내성.
"""
from lxml import etree

import hwpx_core as C

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _sec(inner_xml: str):
    return etree.fromstring(
        f'<hp:sec xmlns:hp="{HP}">{inner_xml}</hp:sec>'.encode("utf-8"))


def _p(text: str) -> str:
    return f"<hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p>"


def test_nested_table_rows_not_duplicated():
    inner = f"<hp:tbl><hp:tr><hp:tc><hp:subList>{_p('INNER')}</hp:subList></hp:tc></hp:tr></hp:tbl>"
    outer = (f"<hp:tbl><hp:tr><hp:tc><hp:subList>{_p('OUTER')}{inner}"
             f"</hp:subList></hp:tc></hp:tr></hp:tbl>")
    tables = C.extract_tables(_sec(outer))
    assert tables == [[["OUTER"]], [["INNER"]]]   # 유령 행·중복 텍스트 없음


def test_para_text_survives_xml_comment():
    sec = _sec("<hp:p><!-- 편집기 주석 --><hp:run><hp:t>본문</hp:t></hp:run></hp:p>")
    p = next(sec.iter(f"{{{HP}}}p"))
    assert C.para_text(p) == "본문"


def test_parse_charmap_survives_comment():
    hdr = (b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">'
           b'<!-- note --><hh:charPr id="7" height="1500"/></hh:head>')
    assert C.parse_charmap(hdr) == {"7": 1500}
