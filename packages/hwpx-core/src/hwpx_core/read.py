# -*- coding: utf-8 -*-
"""문단/표/글자크기 읽기 원시함수. reader·skeleton 공유.

파서 중립 — lxml 트리든 표준 ElementTree 든 같은 함수가 돈다
(엔진을 한 벌로 두기 위함. getparent 대신 위에서 훑어 내려간다).

주의: para_text 는 tab→'\\t', lineBreak→'\\n' 를 포함한다. 항목부호/크기 판정에
쓸 때는 호출부에서 .strip() 하므로 안전하다(선행 탭은 제거됨).
"""
from __future__ import annotations
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

from .ns import HP, local
from .xmlcompat import parent_map


def para_text(p) -> str:
    """문단 p 의 표시 텍스트. t/tab/lineBreak 를 문서 순서대로 이어붙인다.

    ⚠️ `hp:t` 는 mixed content 다 — `<hp:t>’26. 9.<hp:tab/>: 설계</hp:t>` 처럼
    자식 요소 **뒤(tail)** 에 텍스트가 붙는다. tail 을 안 읽으면 탭이 있는 줄은
    앞부분만 읽혀, 검토 경로가 일정 줄 내용을 통째로 못 본다(08-16 발견).
    """
    parts: List[str] = []
    pm = parent_map(p)
    for el in p.iter():
        ln = local(el.tag)
        if ln == "t":
            parts.append(el.text or "")
            continue
        if ln == "tab":
            parts.append("\t")
        elif ln == "lineBreak":
            parts.append("\n")
        # t 안의 인라인 요소는 tail 이 곧 뒤따르는 표시 텍스트다
        # (tab·lineBreak 말고 markpen 류가 와도 글자를 잃지 않는다)
        if local(pm.get(el).tag if pm.get(el) is not None else "") == "t":
            parts.append(el.tail or "")
    return "".join(parts)


def iter_body_paragraphs(sec):
    """표(tc/cellzone) 안이 아닌 최상위 본문 문단만 순회."""
    # ⚠️ id() 로 요소를 비교하면 안 된다 — lxml 은 요소 프록시를 임시로 만들었다
    #    버리므로 죽은 프록시의 주소가 재사용돼 엉뚱한 노드가 같다고 판정된다
    #    (실제로 이 함수가 본문 문단을 0개로 돌려준 적 있다). 참조를 붙들어 두는
    #    부모 사전으로 거슬러 오른다 — lxml·ElementTree 양쪽에서 같게 동작한다.
    pm = parent_map(sec)
    for p in sec.iter(f"{{{HP}}}p"):
        anc, in_cell = pm.get(p), False
        while anc is not None:
            if local(anc.tag) in ("tc", "cellzone"):
                in_cell = True
                break
            anc = pm.get(anc)
        if not in_cell:
            yield p


def _inside(el, stop, name: str) -> bool:
    """el 이 stop 아래의 name 태그(중첩 표 등)에 들어 있는가.

    조상을 거슬러 오르는 대신 stop 아래의 name 태그들이 품은 요소를 모아
    확인한다 — ElementTree 에는 getparent 가 없다(파서 중립).
    """
    pm = parent_map(stop)
    anc = pm.get(el)
    while anc is not None and anc is not stop:
        if local(anc.tag) == name:
            return True
        anc = pm.get(anc)
    return False


def cell_text(tc) -> str:
    """표 셀(tc) 안 문단들을 줄바꿈으로 이어 반환.

    셀 안에 중첩된 표의 문단은 제외한다 — 그 표는 extract_tables 가
    별도 표로 다루므로 여기 포함하면 같은 텍스트가 중복 집계된다.
    """
    parts = []
    for p in tc.iter(f"{{{HP}}}p"):
        if _inside(p, tc, "tbl"):
            continue
        t = para_text(p).strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


def extract_tables(sec) -> List[List[List[str]]]:
    """섹션 내 모든 표를 [표][행][열] 문자열 배열로 추출.

    중첩 표는 자기 자신의 표 항목으로만 나온다 — tbl.iter(tr) 가 중첩 표의
    행까지 하강하므로, 행의 소속 표가 지금 순회 중인 표인지 확인해 거른다.
    """
    tables = []
    for tbl in sec.iter(f"{{{HP}}}tbl"):
        rows = []
        for tr in tbl.iter(f"{{{HP}}}tr"):
            if _inside(tr, tbl, "tbl"):
                continue
            row = [cell_text(tc) for tc in tr.findall(f"{{{HP}}}tc")]
            if row:
                rows.append(row)
        if rows:
            tables.append(rows)
    return tables


def parse_charmap(header_bytes: Optional[bytes]) -> Dict[str, int]:
    """header.xml 바이트 → {charPr id: height(HWPUNIT)}. height 는 1pt=100 척도."""
    if not header_bytes:
        return {}
    try:
        hdr = ET.fromstring(header_bytes)
    except ET.ParseError:
        return {}
    cm: Dict[str, int] = {}
    for cp in hdr.iter():
        if local(cp.tag) == "charPr":
            try:
                cm[cp.get("id")] = int(cp.get("height", "0"))
            except (TypeError, ValueError):
                continue
    return cm


def para_charsize(p, charmap: Dict[str, int]) -> float:
    """문단 첫 run 의 글자 크기(pt). charPr.height / 100."""
    run = p.find(f"{{{HP}}}run")
    cid = run.get("charPrIDRef") if run is not None else None
    return charmap.get(cid, 0) / 100 if cid else 0.0
