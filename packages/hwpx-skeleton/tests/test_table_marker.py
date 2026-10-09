# -*- coding: utf-8 -*-
"""(0.2.2) 본문 위치 마커 '[표N]'/'[이미지N]' — 표가 마커 자리에 삽입되는지 검증."""
import io
import re
import zipfile

import pytest

from hwpx_skeleton import renderer


BODY_MARKER = "\n".join([
    "1. 개요",
    "□ 마커 앞 문단",
    "[표1]",
    "□ 마커 뒤 문단",
])
BODY_PLAIN = "\n".join([
    "1. 개요",
    "□ 마커 없는 문단",
])
TABLES = [{"headers": ["구분", "값"], "rows": [["예산", "38"]]}]


def _section_xml(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def _render(tmp_path, body, tables):
    res = renderer.render(template_key="planning", fields={"title": "마커 테스트"},
                          output_dir=str(tmp_path), body=body, tables=tables)
    assert res["status"] == "success", res
    return res


def test_marker_inserts_table_between_paragraphs(tmp_path):
    res = _render(tmp_path, BODY_MARKER, TABLES)
    br = res["body_result"]
    assert br["tables_added"] == 1
    xml = _section_xml(res["path"])
    i_before = xml.index("마커 앞 문단")
    i_tbl = xml.index("<hp:tbl", i_before)          # 앞 문단 이후에 표가 등장
    i_after = xml.index("마커 뒤 문단")
    assert i_before < i_tbl < i_after, (i_before, i_tbl, i_after)
    assert "[표1]" not in xml                        # 마커 줄 자체는 소비됨


def test_without_marker_table_appends_at_end(tmp_path):
    res = _render(tmp_path, BODY_PLAIN, TABLES)
    assert res["body_result"]["tables_added"] == 1
    xml = _section_xml(res["path"])
    i_last_text = xml.index("마커 없는 문단")
    assert xml.index("<hp:tbl", i_last_text) > i_last_text   # 본문 뒤에 표


def test_marker_without_matching_table_warns_and_drops_line(tmp_path):
    res = _render(tmp_path, BODY_MARKER, None)      # tables 미전달
    br = res["body_result"]
    assert br["tables_added"] == 0
    assert any("[표1]" in w for w in br["warnings"])
    assert "[표1]" not in _section_xml(res["path"])  # 마커가 본문에 노출되지 않음


def test_duplicate_marker_uses_first_position_only(tmp_path):
    body = BODY_MARKER + "\n[표1]"
    res = _render(tmp_path, body, TABLES)
    br = res["body_result"]
    assert br["tables_added"] == 1
    assert any("중복" in w for w in br["warnings"])
