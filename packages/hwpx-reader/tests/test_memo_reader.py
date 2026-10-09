# -*- coding: utf-8 -*-
"""메모 회수 경로 — 파일에 달린 검토 의견을 reader 가 그대로 읽어 오는가.

쓰기(hwpx_core.memo)와 읽기(reader)가 갈리면 우리가 단 메모를 우리가 못 읽는다.
그래서 zip 으로 저장한 실제 파일을 거쳐 왕복시킨다.
"""
import hwpx_core as C
from hwpx_core import memo as M
from hwpx_reader import core

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"

_HEADER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<hh:head xmlns:hh="{HH}"><hh:refList>'
           '<hh:styles itemCnt="1"><hh:style id="16" name="메모" engName="Memo"'
           ' paraPrIDRef="11" charPrIDRef="3"/></hh:styles>'
           '</hh:refList></hh:head>')
_SECTION = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
            f' xmlns:hp="{HP}">'
            '<hp:p id="1"><hp:run charPrIDRef="0">'
            '<hp:secPr id="" memoShapeIDRef="0"/></hp:run></hp:p>'
            '<hp:p id="10"><hp:run charPrIDRef="7">'
            '<hp:t>◦ 공용 인프라 활용</hp:t></hp:run></hp:p></hs:sec>')


def _doc(tmp_path, memos):
    members = {"mimetype": b"application/hwp+zip",
               C.HEADER: _HEADER.encode("utf-8"),
               C.SECTION0: _SECTION.encode("utf-8")}
    res = C.add_memos(members, memos, author="홍길동")
    assert res["added"] == len(memos), res["skipped"]
    return C.write_hwpx(str(tmp_path / "검토본.hwpx"), members)


def test_reader_reads_what_core_wrote(tmp_path):
    path = _doc(tmp_path, [{"anchor": "공용 인프라",
                            "text": "[인프라]\n협조 여부 확인필요"}])
    got = core.core_read_memos(path)
    assert len(got) == 1
    assert got[0]["text"] == "[인프라]\n협조 여부 확인필요"
    assert got[0]["anchor"] == "공용 인프라"      # 메모 내용과 섞이지 않는다
    assert got[0]["author"] == "홍길동"
    assert got[0]["number"] == "1"


def test_plain_document_has_no_memos(tmp_path):
    members = {"mimetype": b"application/hwp+zip",
               C.HEADER: _HEADER.encode("utf-8"),
               C.SECTION0: _SECTION.encode("utf-8")}
    path = C.write_hwpx(str(tmp_path / "원본.hwpx"), members)
    assert core.core_read_memos(path) == []


def test_read_memos_rejects_non_hwpx(tmp_path):
    bad = tmp_path / "문서.hwpx"
    bad.write_bytes(b"not a zip")
    try:
        core.core_read_memos(str(bad))
    except core.HwpxReadError:
        return
    raise AssertionError("HWPX 가 아닌 파일을 조용히 통과시켰다")


def test_memo_extended_part_is_not_written(tmp_path):
    """2021 확장 파트를 넣으면 구버전 한/글이 파일을 아예 안 연다."""
    path = _doc(tmp_path, [{"anchor": "공용 인프라", "text": "확인필요"}])
    members = C.read_members(path)
    assert M.MEMO_PART not in members
    assert M.CONTENT_HPF not in members
