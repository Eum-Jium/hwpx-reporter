# -*- coding: utf-8 -*-
"""메모(검토 의견) 읽기/쓰기 — 단일 기준.

한/글의 메모는 별도 주석 파트가 아니라 **본문 안의 필드**다. 메모를 달 글자
범위를 `hp:fieldBegin type="MEMO"` … `hp:fieldEnd` 로 감싸고, 메모 내용은
fieldBegin 안의 `hp:subList` 에 문단으로 들어간다. 이 구조는 실무에서 돌아온
검토본(메모 3건)의 XML 을 뜯어 확인한 것이다.

조각이 셋이고 **하나라도 빠지면 한/글이 메모를 안 보여 준다**:
  1. header.xml `hh:refList` 끝에 `hh:memoProperties`(메모 상자 모양)
  2. 섹션의 `hp:secPr@memoShapeIDRef` 가 그 모양을 가리킴
  3. 본문의 fieldBegin/fieldEnd 쌍 + subList(메모 내용)

`Contents/memoExtended.xml` 은 **넣지 않는다** — 답글이 없으면 빈 파트이고,
2021 확장이라 구버전 한/글이 못 연다(ensure_memo_parts 주석).

파서 중립 · stdlib 만 쓴다 — 요소는 전부 `parent.makeelement` 로 만든다.
읽기 경로(reader)는 lxml 트리, 쓰기 경로(skeleton)는 ElementTree 트리를
넘기는데, 한쪽 팩토리로 만든 요소를 다른 트리에 넣으면 터진다.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .ns import HP as HP_DEFAULT, local
from .xmlcompat import hp_uri, hh_uri, parent_map, parse, serialize
from .zipio import (HwpxError, validate_hwpx, read_members, write_hwpx,
                    section_names, HEADER)

KST = timezone(timedelta(hours=9))

# 메모 파트/매니페스트
MEMO_PART = "Contents/memoExtended.xml"
CONTENT_HPF = "Contents/content.hpf"
HE = "http://www.hancom.co.kr/hwpml/2021/extended"     # 2021 확장(메모 답글 연결)

# 메모 상자 모양 — 정본 실측값(연두 테두리/채움). memoType 의 'NOMAL' 은 오타가
# 아니라 한/글이 실제로 쓰는 철자다. NORMAL 로 고치면 한/글이 못 읽는다.
MEMO_SHAPE = {"width": "15591", "lineWidth": "1", "lineType": "SOLID",
              "lineColor": "#B6D7AE", "fillColor": "#F0FFE9",
              "activeColor": "#CFF1C7", "memoType": "NOMAL"}

# subList(메모 내용 그릇) 속성 — 정본 그대로
_SUBLIST = {"id": "", "textDirection": "HORIZONTAL", "lineWrap": "BREAK",
            "vertAlign": "TOP", "linkListIDRef": "0", "linkListNextIDRef": "0",
            "textWidth": "0", "textHeight": "0", "hasTextRef": "0",
            "hasNumRef": "0"}

# Command 파라미터의 꼬리. 한/글이 넣는 리터럴이라 그대로 둔다.
_CMD_TAIL = "\\;;"
# 메모 필드의 MemoShapeIDRef 파라미터 — 65535(0xFFFF)는 '지정 없음', 곧 secPr 의
# memoShapeIDRef 를 따르라는 뜻이다(정본 3건 모두 이 값).
_SHAPE_INHERIT = "65535"


# ── 읽기 ──────────────────────────────────────────────────

def _sub_text(fb, hp: str) -> str:
    """메모 필드 안 subList 의 문단 텍스트(문단 사이 줄바꿈)."""
    lines: List[str] = []
    for sub in fb.iter("{%s}subList" % hp):
        for p in sub.iter("{%s}p" % hp):
            lines.append("".join((t.text or "") for t in p.iter("{%s}t" % hp)))
    return "\n".join(lines)


def _under_field(el, pm) -> bool:
    """el 이 메모 필드(fieldBegin) 안쪽인가 — 메모 내용과 앵커를 가른다.

    `sec.iter()` 는 fieldBegin 다음에 그 자식(subList=메모 내용)을 먼저 훑고
    형제로 넘어간다. 걸러 내지 않으면 메모 내용이 앵커 텍스트에 섞인다.
    """
    anc = pm.get(el)
    while anc is not None:
        if local(anc.tag) == "fieldBegin":
            return True
        anc = pm.get(anc)
    return False


def read_memos(sec) -> List[Dict[str, Any]]:
    """섹션 트리에서 메모를 문서 순서대로 읽는다.

    반환: [{"id", "number", "author", "created", "text", "anchor"}, …]
    anchor 는 메모가 걸린 본문 글자(fieldBegin~fieldEnd 사이)다.
    """
    hp = hp_uri(sec, HP_DEFAULT)
    pm = parent_map(sec)
    out: List[Dict[str, Any]] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    open_ids: List[str] = []
    for el in sec.iter():
        ln = local(el.tag)
        if ln == "fieldBegin" and el.get("type") == "MEMO":
            params = {}
            for pel in el.iter():
                if local(pel.tag).endswith("Param"):
                    params[pel.get("name") or ""] = pel.text or ""
            item = {"id": el.get("id") or "",
                    "number": params.get("Number", ""),
                    "author": params.get("Author", ""),
                    "created": params.get("CreateDateTime", ""),
                    "text": _sub_text(el, hp),
                    "anchor": ""}
            out.append(item)
            by_id[item["id"]] = item
            open_ids.append(item["id"])
            continue
        if ln == "fieldEnd":
            ref = el.get("beginIDRef") or ""
            if ref in open_ids:
                open_ids.remove(ref)
            continue
        if not open_ids or _under_field(el, pm):
            continue
        # 앵커도 본문이다 — 탭·강제줄바꿈을 para_text 와 같은 규칙으로 담는다
        piece = (el.text or "") if ln == "t" else (
            "\t" if ln == "tab" else "\n" if ln == "lineBreak" else "")
        if piece:
            for mid in open_ids:
                by_id[mid]["anchor"] += piece
    return out


def read_memos_from(path: str) -> List[Dict[str, Any]]:
    """파일에서 메모를 읽는다(섹션 순서대로 이어 붙인다)."""
    validate_hwpx(path)
    members = read_members(path, lambda n: not n.startswith("BinData/"))
    out: List[Dict[str, Any]] = []
    for name in section_names(members):
        try:
            out.extend(read_memos(parse(members[name])))
        except Exception:      # noqa — 섹션 하나가 손상돼도 나머지는 읽는다
            continue
    return out


# ── 쓰기: 문서 조각 준비 ──────────────────────────────────

def _mk(parent, uri: str, name: str, attrib: Optional[Dict[str, str]] = None):
    """parent 와 **같은 팩토리**로 자식 요소를 만들어 붙인다(파서 중립)."""
    el = parent.makeelement("{%s}%s" % (uri, name), dict(attrib or {}))
    parent.append(el)
    return el


def ensure_memo_shape(hdr) -> str:
    """header 에 메모 상자 모양을 보장하고 그 id 를 돌려준다.

    이미 있으면 첫 memoPr 의 id 를 그대로 쓴다 — 메모가 이미 달린 문서에
    덧붙일 때 모양을 하나 더 만들면 기존 메모의 참조가 흔들린다.
    """
    hh = hh_uri(hdr)
    ref = None
    for el in hdr.iter():
        ln = local(el.tag)
        if ln == "memoPr":
            return el.get("id") or "1"
        if ln == "refList" and ref is None:
            ref = el
    if ref is None:                      # refList 가 없는 문서는 다루지 않는다
        raise HwpxError("header.xml 에 refList 가 없다 — 메모 모양을 넣을 자리가 없다.")
    # 스키마 순서상 memoProperties 는 refList 의 끝(styles 뒤)이다
    props = _mk(ref, hh, "memoProperties", {"itemCnt": "1"})
    _mk(props, hh, "memoPr", dict({"id": "1"}, **MEMO_SHAPE))
    return "1"


def memo_style(hdr) -> Dict[str, str]:
    """메모 문단이 쓸 스타일/문단모양/글자모양 id.

    한/글 문서에는 보통 '메모'(engName=Memo) 스타일이 있다. 없는 양식이면
    0번(바탕글)으로 떨어뜨린다 — 없는 id 를 참조하면 문서가 열리지 않는다.
    """
    style_id = para_id = char_id = "0"
    for el in hdr.iter():
        if local(el.tag) != "style":
            continue
        if el.get("name") == "메모" or el.get("engName") == "Memo":
            style_id = el.get("id") or "0"
            para_id = el.get("paraPrIDRef") or "0"
            char_id = el.get("charPrIDRef") or "0"
            break
    return {"style": style_id, "para": para_id, "char": char_id}


def ensure_memo_parts(members: Dict[str, bytes]) -> List[str]:
    """memoExtended.xml 파트를 **만들지 않는다**. 손댄 조각을 반환(늘 비어 있다).

    memosEx 는 메모 **답글(스레드) 연결**만 담는다 — 메모 자체의 등록부가 아니다
    (실물에는 본문에 없는 유령 id 가 하나 남아 있는데도 한/글이 그냥 연다).
    답글이 없으면 비어 있고, 한/글도 다시 저장할 때 빈 파트를 아예 지운다.

    한때는 "정본과 같은 모양이라 잃을 것이 없다"며 빈 파트를 넣어 두었는데 그
    판단이 틀렸다. 이 파트는 **2021 확장**(hwpml/2021/extended)이라, content.hpf
    에 등록된 그 항목을 구버전 한/글이 만나면 **파일을 아예 안 연다**. 검토본이
    다른 PC 에서 안 열린 두 원인 중 하나였고, 파트를 빼면 열린다(변종 대조로 확인).

    원본에 이미 있으면 그대로 둔다 — 한/글이 답글까지 적어 둔 파트다.
    """
    return []


# ── 쓰기: 메모 필드 조립 ──────────────────────────────────

_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _stamp(when=None):
    """작성시각 → (CreateDateTime 문자열, FILETIME 하위 32비트, 상위 32비트).

    **작성시각의 정본은 CreateDateTime 이 아니라 Command 의 숫자 두 자리다.**
    그 둘은 Windows FILETIME(1601년부터 100ns 단위)의 하위·상위 32비트이고,
    한/글은 문서를 열 때 그 값으로 CreateDateTime 을 **다시 계산해 덮어쓴다**.
    아무 정수나 넣어도 파일은 열리지만 메모 상자에 엉뚱한 날짜가 뜬다 —
    처음에 임의값을 넣었더니 한/글이 2785년으로 고쳐 저장했다(재저장 시험에서 발견).

    CreateDateTime 문자열은 한/글 관례를 따라 **로컬 시각(KST)에 Z 를 붙인다**
    (정본: FILETIME 은 02:02:06 UTC 인데 문자열은 11:02:06Z). 진짜 UTC 로 적으면
    한/글이 고쳐 쓰기 전까지 9시간 이른 시각이 보인다.
    """
    if when is None:
        when = datetime.now(KST)
    elif isinstance(when, str):
        try:
            # 한/글이 적는 형식 — 'Z' 가 붙어 있어도 그 값은 로컬 시각이다
            when = datetime.strptime(when.strip().rstrip("Z"),
                                     "%Y-%m-%dT%H:%M:%S").replace(tzinfo=KST)
        except ValueError:
            raise HwpxError(
                "created 형식이 아니다(YYYY-MM-DDTHH:MM:SSZ): %r" % when)
    elif when.tzinfo is None:
        when = when.replace(tzinfo=KST)
    ticks = int((when.astimezone(timezone.utc) - _FILETIME_EPOCH)
                .total_seconds() * 10_000_000)
    return (when.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ticks & 0xFFFFFFFF, ticks >> 32)


def _clean_author(name: str) -> str:
    """Command 파라미터가 '/' 로 끊기는 형식이라 작성자에서 '/' 를 뺀다."""
    return re.sub(r"[/\\]", "", str(name or "").strip()) or "reviewer"


def _build_field(run, hp: str, *, fid: int, field_id: int, number: int,
                 text: str, author: str, stamp, style: Dict[str, str]):
    """fieldBegin(파라미터 7개 + subList) 요소를 만들어 돌려준다."""
    fb = run.makeelement("{%s}fieldBegin" % hp, {
        "id": str(fid), "type": "MEMO", "name": "", "editable": "1",
        "dirty": "1", "zorder": str(number), "fieldid": str(field_id)})
    params = _mk(fb, hp, "parameters", {"cnt": "7", "name": ""})

    def _p(kind: str, name: str, value: str):
        el = _mk(params, hp, kind, {"name": name})
        el.text = value

    # Command = MEMO/<모양>/<번호>/<FILETIME 하위>/<FILETIME 상위>/<작성자>/\;;
    # 숫자 두 자리가 작성시각의 정본이다 — _stamp 주석 참조.
    created, ft_low, ft_high = stamp
    _p("integerParam", "Prop", "0")
    _p("stringParam", "Command",
       "MEMO/%s/%d/%d/%d/%s/%s" % (_SHAPE_INHERIT, number, ft_low, ft_high,
                                   author, _CMD_TAIL))
    _p("stringParam", "ID", "memo%d" % number)
    _p("integerParam", "Number", str(number))
    _p("stringParam", "Author", author)
    _p("stringParam", "MemoShapeIDRef", _SHAPE_INHERIT)
    _p("stringParam", "CreateDateTime", created)

    sub = _mk(fb, hp, "subList", _SUBLIST)
    for line in (text.splitlines() or [""]):
        p = _mk(sub, hp, "p", {"id": "0", "paraPrIDRef": style["para"],
                               "styleIDRef": style["style"], "pageBreak": "0",
                               "columnBreak": "0", "merged": "0"})
        r = _mk(p, hp, "run", {"charPrIDRef": style["char"]})
        _mk(r, hp, "t").text = line
    return fb


def _drop_lineseg(p, hp: str) -> None:
    """문단의 linesegarray 를 걷어낸다.

    fieldBegin/fieldEnd 는 한/글의 글자 흐름에서 **각각 한 칸을 차지한다** —
    남겨 두면 저장된 줄 좌표(textpos)가 한 칸씩 밀려 글자가 겹쳐 보인다.
    지우면 한/글이 열 때 다시 계산한다(renderer 의 _clear_lineseg 와 같은 이유).
    """
    for seg in list(p.findall("{%s}linesegarray" % hp)):
        p.remove(seg)


def _split_and_wrap(t, run, hp: str, start: int, length: int, fb, fe) -> None:
    """앵커 앞/뒤를 갈라 그 사이에 메모 필드를 끼운다.

    `hp:t` 는 mixed content 라 자식(tab·markpen 등)이 있을 수 있다 — 자식과
    그 tail 은 **뒤 조각이 통째로** 물려받는다(앞 조각에 남기면 순서가 뒤집혀
    탭이 앵커 앞으로 튀어나온다).
    """
    text = t.text or ""
    moved = list(t)
    mid = run.makeelement(t.tag, {})
    mid.text = text[start:start + length]
    post = run.makeelement(t.tag, {})
    post.text = text[start + length:]
    for c in moved:
        t.remove(c)
        post.append(c)
    t.text = text[:start]
    post.tail, t.tail = t.tail, None

    i = list(run).index(t)
    ctrl_b = run.makeelement("{%s}ctrl" % hp, {})
    ctrl_b.append(fb)
    ctrl_e = run.makeelement("{%s}ctrl" % hp, {})
    ctrl_e.append(fe)
    for off, el in enumerate((ctrl_b, mid, ctrl_e, post), start=1):
        run.insert(i + off, el)


def _max_id(sec) -> int:
    """섹션 안에서 쓰인 가장 큰 정수 id — 새 컨트롤 id 를 그 위에서 딴다."""
    top = 0
    for el in sec.iter():
        v = el.get("id")
        if v and v.isdigit():
            top = max(top, int(v))
    return top


def _next_number(sec, hp: str) -> int:
    """이 섹션에 이미 달린 메모의 다음 번호(1부터)."""
    n = 0
    for el in sec.iter("{%s}fieldBegin" % hp):
        if el.get("type") != "MEMO":
            continue
        for pel in el.iter():
            if pel.get("name") == "Number" and (pel.text or "").isdigit():
                n = max(n, int(pel.text))
    return n + 1


def _find_anchor(sec, hp: str, pm, anchor: str, nth: int):
    """앵커가 든 (t, run, 시작위치) 를 문서 순서로 찾는다. 없으면 None.

    이미 메모가 걸린 글자(fieldBegin 안)는 후보에서 뺀다 — 메모 내용에 같은
    말이 있으면 메모 안에 메모를 다는 꼴이 된다.
    """
    hit = 0
    for t in sec.iter("{%s}t" % hp):
        if _under_field(t, pm):
            continue
        pos = (t.text or "").find(anchor)
        if pos < 0:
            continue
        hit += 1
        if hit < nth:
            continue
        run = pm.get(t)
        if run is None or local(run.tag) != "run":
            return None
        return t, run, pos
    return None


def add_memos(members: Dict[str, bytes], memos: List[Dict[str, Any]],
              author: str = "", created: Optional[str] = None) -> Dict[str, Any]:
    """members(hwpx 조각 사전)에 메모를 달고 결과를 보고한다. members 를 고친다.

    memos: [{"anchor": 메모를 걸 본문 글자, "text": 메모 내용,
             "author": 작성자(선택), "nth": 같은 글자가 여럿일 때 몇 번째(기본 1)}, …]

    앵커를 못 찾으면 **조용히 넘기지 않고** skipped 에 사유를 남긴다 — 메모가
    빠진 문서를 온전한 것으로 믿고 넘기는 쪽이 훨씬 나쁘다.
    """
    if HEADER not in members:
        raise HwpxError("header.xml 이 없다 — 메모를 달 수 없다.")
    sec_names = section_names(members)
    if not sec_names:
        raise HwpxError("본문 섹션이 없다 — 메모를 달 수 없다.")

    hdr = parse(members[HEADER])
    had_shape = any(local(el.tag) == "memoPr" for el in hdr.iter())
    shape_id = ensure_memo_shape(hdr)
    style = memo_style(hdr)
    stamp = _stamp(created)
    default_author = _clean_author(author)

    secs = {name: parse(members[name]) for name in sec_names}
    touched = set()
    added: List[Dict[str, Any]] = []
    skipped: List[str] = []

    # 컨트롤 id 는 문서 전체에서 겹치면 안 된다 — 모든 섹션의 최대값 위에서 딴다.
    next_id = max(_max_id(s) for s in secs.values()) + 1
    field_id = next_id                      # 문서 안 메모들이 공유하는 필드 식별자
    next_id += 1
    numbers = {name: _next_number(secs[name], hp_uri(secs[name], HP_DEFAULT))
               for name in sec_names}

    for i, spec in enumerate(memos or []):
        if not isinstance(spec, dict):
            skipped.append("%d번째 항목: dict 가 아니다(anchor·text 가 필요하다)"
                           % (i + 1))
            continue
        anchor = str(spec.get("anchor") or "")
        text = str(spec.get("text") or "")
        if not anchor.strip():
            skipped.append("%d번째 항목: anchor 가 비어 있다" % (i + 1))
            continue
        if not text.strip():
            skipped.append("%r: text 가 비어 있다" % anchor)
            continue
        try:
            nth = max(1, int(spec.get("nth") or 1))
        except (TypeError, ValueError):
            nth = 1

        placed = False
        for name in sec_names:
            sec = secs[name]
            hp = hp_uri(sec, HP_DEFAULT)
            # 트리를 고칠 때마다 부모 사전을 새로 뜬다(xmlcompat.parent_map 주석)
            pm = parent_map(sec)
            found = _find_anchor(sec, hp, pm, anchor, nth)
            if not found:
                continue
            t, run, pos = found
            para = pm.get(run)
            number = numbers[name]
            who = _clean_author(spec.get("author") or default_author)
            fb = _build_field(run, hp, fid=next_id, field_id=field_id,
                              number=number, text=text, author=who,
                              stamp=_stamp(spec["created"]) if spec.get("created")
                              else stamp, style=style)
            fe = run.makeelement("{%s}fieldEnd" % hp,
                                 {"beginIDRef": str(next_id),
                                  "fieldid": str(field_id)})
            _split_and_wrap(t, run, hp, pos, len(anchor), fb, fe)
            if para is not None and local(para.tag) == "p":
                _drop_lineseg(para, hp)
            added.append({"number": number, "anchor": anchor, "text": text,
                          "author": who, "section": name})
            numbers[name] = number + 1
            next_id += 1
            touched.add(name)
            placed = True
            break
        if not placed:
            skipped.append(
                "%r: 본문에서 찾지 못했다(한 <hp:t> 안에 통째로 들어 있는 글자만 "
                "앵커로 쓸 수 있다 — 탭·각주로 쪼개진 줄이면 더 짧게 잡을 것)"
                % anchor)

    if not added:
        return {"status": "success", "added": 0, "memos": [],
                "skipped": skipped, "parts": []}

    # 메모 모양을 이번에 만들었을 때만 secPr 를 손댄다 — 이미 메모가 있던 문서의
    # 참조를 바꾸면 기존 메모 상자 모양이 통째로 뒤바뀐다.
    for name in touched:
        sec = secs[name]
        if not had_shape:
            hp = hp_uri(sec, HP_DEFAULT)
            for sp in sec.iter("{%s}secPr" % hp):
                sp.set("memoShapeIDRef", shape_id)
        # like= 로 원본 바이트를 준다 — 안 주면 안 쓰이는 xmlns 선언이 빠져
        # 구버전 한/글이 파일을 못 연다(xmlcompat._restore_xmlns 주석).
        members[name] = serialize(sec, like=members[name])
    members[HEADER] = serialize(hdr, like=members[HEADER])
    parts = ensure_memo_parts(members)
    return {"status": "success", "added": len(added), "memos": added,
            "skipped": skipped, "parts": parts}


def annotate(path: str, memos: List[Dict[str, Any]],
             out_path: Optional[str] = None, author: str = "",
             suffix: str = "_메모") -> Dict[str, Any]:
    """hwpx 파일에 메모를 달아 **새 파일로** 저장한다.

    out_path 를 안 주면 원본 옆에 `<이름>_메모.hwpx` 로 낸다 — 검토본은 원본을
    덮어쓰지 않는 것이 기본이다(원본과 대조할 수 없으면 검토가 무의미하다).
    """
    validate_hwpx(path)
    members = read_members(path)
    res = add_memos(members, memos, author=author)
    if not res["added"]:
        res["status"] = "error"
        res["message"] = "메모를 하나도 달지 못했다 — skipped 를 보라."
        return res
    if not out_path:
        stem, ext = os.path.splitext(path)
        out_path = stem + suffix + (ext or ".hwpx")
    if os.path.abspath(out_path) == os.path.abspath(path):
        raise HwpxError("원본을 덮어쓸 수 없다 — out_path 를 다른 경로로 줄 것.")
    res["path"] = write_hwpx(out_path, members)
    return res
