# -*- coding: utf-8 -*-
"""메모(검토 의견) 읽기/쓰기 회귀.

실무 검토본에서 뜯어낸 구조를 그대로 지킨다.
한/글에 물어보지 않고도 깨지면 알 수 있어야 하는 것들만 모았다.
"""
import xml.etree.ElementTree as ET

import pytest

import hwpx_core as C
from hwpx_core import memo as M

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"

_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<hh:head xmlns:hh="{HH}"><hh:refList>'
    '<hh:charProperties itemCnt="1"><hh:charPr id="3" height="900"/></hh:charProperties>'
    '<hh:styles itemCnt="1">'
    '<hh:style id="16" type="PARA" name="메모" engName="Memo"'
    ' paraPrIDRef="11" charPrIDRef="3"/>'
    '</hh:styles></hh:refList></hh:head>'
)
_HPF = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/"><opf:manifest>'
        '<opf:item id="section0" href="Contents/section0.xml"/>'
        '</opf:manifest><opf:spine/></opf:package>')


def _section(*paras: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
            f' xmlns:hp="{HP}">'
            '<hp:p id="1" paraPrIDRef="0"><hp:run charPrIDRef="0">'
            '<hp:secPr id="" memoShapeIDRef="0"/></hp:run></hp:p>'
            + "".join(paras) + '</hs:sec>')


def _p(inner: str, pid: str = "10") -> str:
    return (f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0">'
            f'<hp:run charPrIDRef="7">{inner}</hp:run>'
            f'<hp:linesegarray><hp:lineseg textpos="0"/></hp:linesegarray></hp:p>')


def _members(*paras: str):
    return {C.HEADER: _HEADER.encode("utf-8"),
            C.SECTION0: _section(*paras).encode("utf-8"),
            M.CONTENT_HPF: _HPF.encode("utf-8")}


def _sec_of(members):
    return ET.fromstring(members[C.SECTION0])


# ── 쓰기 ──────────────────────────────────────────────────

def test_anchor_wrapped_and_text_preserved():
    members = _members(_p("<hp:t>◦ 운영데이터 등 수집</hp:t>"))
    res = C.add_memos(members, [{"anchor": "운영데이터",
                                 "text": "확인필요"}], author="홍길동")
    assert res["added"] == 1 and res["skipped"] == []
    sec = _sec_of(members)
    run = sec.find(f".//{{{HP}}}p[@id='10']/{{{HP}}}run")
    kinds = [c.tag.rsplit("}", 1)[-1] for c in run]
    assert kinds == ["t", "ctrl", "t", "ctrl", "t"]     # 앞 · 시작 · 앵커 · 끝 · 뒤
    assert [c.text for c in run if c.tag.endswith("}t")] == [
        "◦ ", "운영데이터", " 등 수집"]              # 본문 글자는 한 자도 안 잃는다


def test_field_end_points_back_at_field_begin():
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "메모"}])
    sec = _sec_of(members)
    fb = sec.find(f".//{{{HP}}}fieldBegin")
    fe = sec.find(f".//{{{HP}}}fieldEnd")
    assert fb.get("type") == "MEMO"
    assert fe.get("beginIDRef") == fb.get("id")
    assert fe.get("fieldid") == fb.get("fieldid")       # 필드 식별자는 문서 공유


def test_linesegarray_dropped_on_annotated_paragraph():
    # 메모 필드는 글자 흐름에서 한 칸씩 차지한다 — 옛 줄 좌표를 남기면 글자가 겹친다
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "메모"}])
    p = _sec_of(members).find(f".//{{{HP}}}p[@id='10']")
    assert p.find(f"{{{HP}}}linesegarray") is None


def test_three_pieces_present():
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "메모"}])
    hdr = ET.fromstring(members[C.HEADER])
    shape = hdr.find(f".//{{{HH}}}memoPr")
    assert shape is not None and shape.get("memoType") == "NOMAL"   # NORMAL 아님
    sec_pr = _sec_of(members).find(f".//{{{HP}}}secPr")
    assert sec_pr.get("memoShapeIDRef") == shape.get("id")


def test_unused_xmlns_declarations_survive():
    """안 쓰이는 xmlns 선언이 빠지면 구버전 한/글이 파일을 못 연다.

    ET 는 실제로 쓰인 접두사만 다시 써낸다. 한/글은 조각마다 늘 같은 선언
    묶음을 적어 두므로, 고쳐 쓴 뒤에도 원본이 선언한 것은 그대로 남아야 한다.
    """
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    ghost = b' xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph"'
    for name, root in ((C.HEADER, b"<hh:head"), (C.SECTION0, b"<hs:sec")):
        members[name] = members[name].replace(root, root + ghost, 1)
    C.add_memos(members, [{"anchor": "확인 대상", "text": "메모"}])
    for name in (C.HEADER, C.SECTION0):
        assert b'xmlns:hp10=' in members[name], name
        ET.fromstring(members[name])            # 여전히 well-formed 여야 한다


def test_memo_extended_part_is_not_created():
    """2021 확장 파트를 넣으면 구버전 한/글이 파일을 아예 안 연다."""
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    hpf_before = members[M.CONTENT_HPF]
    res = C.add_memos(members, [{"anchor": "확인 대상", "text": "메모"}])
    assert res["added"] == 1 and res["parts"] == []
    assert M.MEMO_PART not in members
    assert members[M.CONTENT_HPF] == hpf_before
    assert b"memoextended" not in members[M.CONTENT_HPF]


def test_memo_paragraph_uses_memo_style():
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "첫 줄\n둘째 줄"}])
    sub = _sec_of(members).find(f".//{{{HP}}}subList")
    paras = sub.findall(f"{{{HP}}}p")
    assert [p.get("styleIDRef") for p in paras] == ["16", "16"]
    assert [p.get("paraPrIDRef") for p in paras] == ["11", "11"]
    assert paras[1].find(f".//{{{HP}}}t").text == "둘째 줄"


def test_missing_anchor_is_reported_not_silent():
    members = _members(_p("<hp:t>본문</hp:t>"))
    res = C.add_memos(members, [{"anchor": "없는 말", "text": "메모"}])
    assert res["added"] == 0
    assert len(res["skipped"]) == 1 and "없는 말" in res["skipped"][0]
    assert M.MEMO_PART not in members          # 하나도 못 달았으면 문서를 안 건드린다


def test_empty_text_or_anchor_is_reported():
    members = _members(_p("<hp:t>본문</hp:t>"))
    res = C.add_memos(members, [{"anchor": "본문", "text": "  "},
                                {"anchor": "", "text": "메모"}, "문자열"])
    assert res["added"] == 0 and len(res["skipped"]) == 3


def test_nth_picks_the_right_occurrence():
    members = _members(_p("<hp:t>점검 대상</hp:t>", "10"),
                       _p("<hp:t>점검 대상</hp:t>", "11"))
    C.add_memos(members, [{"anchor": "점검 대상", "text": "둘째 것", "nth": 2}])
    sec = _sec_of(members)
    assert sec.find(f".//{{{HP}}}p[@id='10']//{{{HP}}}fieldBegin") is None
    assert sec.find(f".//{{{HP}}}p[@id='11']//{{{HP}}}fieldBegin") is not None


def test_tab_inside_t_moves_to_the_tail_piece():
    # hp:t 는 mixed content 다 — 자식과 tail 을 앞 조각에 남기면 탭이 앵커 앞으로 튄다
    members = _members(_p("<hp:t>’26. 9.<hp:tab/>: 착수</hp:t>"))
    res = C.add_memos(members, [{"anchor": "’26. 9.", "text": "일정 확인"}])
    assert res["added"] == 1
    run = _sec_of(members).find(f".//{{{HP}}}p[@id='10']/{{{HP}}}run")
    ts = [c for c in run if c.tag.endswith("}t")]
    assert ts[1].text == "’26. 9." and len(ts[1]) == 0
    assert len(ts[2]) == 1 and ts[2][0].tail == ": 착수"


def test_second_pass_continues_numbering_and_keeps_shape():
    members = _members(_p("<hp:t>첫째 대상 둘째 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "첫째 대상", "text": "하나"}])
    hdr = ET.fromstring(members[C.HEADER])
    shapes = hdr.findall(f".//{{{HH}}}memoPr")
    res = C.add_memos(members, [{"anchor": "둘째 대상", "text": "둘"}])
    assert res["added"] == 1
    hdr2 = ET.fromstring(members[C.HEADER])
    assert len(hdr2.findall(f".//{{{HH}}}memoPr")) == len(shapes)   # 모양은 한 벌
    got = C.read_memos(_sec_of(members))
    assert [m["number"] for m in got] == ["1", "2"]
    ids = [m["id"] for m in got]
    assert len(set(ids)) == 2                                       # id 충돌 없음


# ── 작성시각 (2785년 사건 회귀) ────────────────────────────

def _command(sec):
    for el in sec.iter():
        if el.get("name") == "Command":
            return el.text
    return ""


def test_command_numbers_are_the_filetime_of_created():
    """Command 의 숫자 두 자리는 난수가 아니라 FILETIME 하위·상위다.

    한/글은 문서를 열 때 그 값으로 CreateDateTime 을 다시 계산해 덮어쓴다 —
    임의값을 넣었더니 2785년으로 고쳐 저장했다.
    """
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "메모",
                           "created": "2026-08-13T11:02:42Z"}])
    sec = _sec_of(members)
    parts = _command(sec).split("/")
    low, high = int(parts[3]), int(parts[4])
    stamp, want_low, want_high = M._stamp("2026-08-13T11:02:42Z")
    assert (low, high) == (want_low, want_high)
    assert stamp == "2026-08-13T11:02:42Z"
    assert C.read_memos(sec)[0]["created"] == stamp


def test_created_matches_the_real_document():
    """정본 메모 1번: Command 숫자 3184938592/31271623 ↔ 2026-08-13T11:02:06Z.

    정본은 소수점 이하(0.278초)까지 갖고 있고 CreateDateTime 문자열은 초까지만
    적는다 — 그래서 같은 초로 떨어지는지를 본다(값이 딱 같을 수는 없다).
    """
    _, low, high = M._stamp("2026-08-13T11:02:06Z")
    assert (high << 32 | low) // 10_000_000 == (
        (31271623 << 32 | 3184938592) // 10_000_000)


def test_bad_created_raises():
    with pytest.raises(C.HwpxError):
        M._stamp("2026년 8월 13일")


def test_author_slash_is_stripped():
    # Command 가 '/' 로 끊기는 형식이라 작성자에 '/' 가 있으면 자리가 밀린다
    members = _members(_p("<hp:t>확인 대상</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "메모",
                           "author": "○○처/홍길동"}])
    sec = _sec_of(members)
    assert _command(sec).split("/")[5] == "○○처홍길동"
    assert C.read_memos(sec)[0]["author"] == "○○처홍길동"


# ── 읽기 ──────────────────────────────────────────────────

def test_read_separates_memo_text_from_anchor():
    members = _members(_p("<hp:t>앞 확인 대상 뒤</hp:t>"))
    C.add_memos(members, [{"anchor": "확인 대상", "text": "[데이터]\n확인필요"}],
                author="홍길동")
    got = C.read_memos(_sec_of(members))
    assert len(got) == 1
    assert got[0]["text"] == "[데이터]\n확인필요"    # 메모 내용
    assert got[0]["anchor"] == "확인 대상"           # 걸린 본문 — 섞이면 안 된다
    assert got[0]["author"] == "홍길동"


def test_anchor_keeps_tab_like_para_text():
    members = _members(_p("<hp:t>’26. 9.<hp:tab/>: 착수</hp:t>"))
    C.add_memos(members, [{"anchor": "’26. 9.", "text": "일정"}])
    # 앵커는 필드 사이 글자만 — 탭 뒤는 필드 밖이라 들어오지 않는다
    assert C.read_memos(_sec_of(members))[0]["anchor"] == "’26. 9."


def test_read_returns_nothing_for_plain_document():
    assert C.read_memos(_sec_of(_members(_p("<hp:t>본문</hp:t>")))) == []
