# -*- coding: utf-8 -*-
"""HWPX 읽기 코어 — hwpx-core 원시함수 위에 얹은 조회/집계 로직.

read_text / read_tables / outline / read_structure / search / info / read_memos 의
실제 계산부.
저수준 zip·XML·charmap 은 전부 hwpx_core 에 위임한다(중복 제거).
"""
from __future__ import annotations
import os
from typing import Any, Dict, List

from lxml import etree

from hwpx_core import (
    HP, HwpxError, validate_hwpx, read_members, section_names, HEADER,
    para_text, iter_body_paragraphs, extract_tables, parse_charmap, para_charsize,
    read_memos_from,
)

# 하위호환: 기존 코드가 기대하던 예외명 유지
HwpxReadError = HwpxError


def _skip_bindata(name: str) -> bool:
    """조회용 멤버 필터 — BinData(임베드 이미지)는 텍스트 추출에 불필요한데
    수백 MB 일 수 있어 메모리 적재에서 제외한다(XML·Preview 만 로드)."""
    return not name.startswith("BinData/")


def core_read_text(path: str, dedupe: bool = True, include_tables: bool = True) -> str:
    validate_hwpx(path)
    members = read_members(path, _skip_bindata)
    out: List[str] = []
    prev = None
    for name in section_names(members):
        try:
            sec = etree.fromstring(members[name])
        except etree.XMLSyntaxError:
            continue
        paras = sec.iter(f"{{{HP}}}p") if include_tables else iter_body_paragraphs(sec)
        for p in paras:
            line = para_text(p).strip()
            if not line:
                continue
            if dedupe and line == prev:
                continue
            out.append(line)
            prev = line
    return "\n".join(out)


def core_read_tables(path: str) -> List[List[List[str]]]:
    validate_hwpx(path)
    members = read_members(path, _skip_bindata)
    tables: List[List[List[str]]] = []
    for name in section_names(members):
        try:
            sec = etree.fromstring(members[name])
        except etree.XMLSyntaxError:
            continue
        tables.extend(extract_tables(sec))
    return tables


def core_outline(path: str, min_pt: float = 15.5) -> List[Dict[str, Any]]:
    validate_hwpx(path)
    members = read_members(path, _skip_bindata)
    cm = parse_charmap(members.get(HEADER))
    items: List[Dict[str, Any]] = []
    seen = set()
    for name in section_names(members):
        try:
            sec = etree.fromstring(members[name])
        except etree.XMLSyntaxError:
            continue
        for p in iter_body_paragraphs(sec):
            txt = para_text(p).strip()
            if not txt:
                continue
            size = para_charsize(p, cm)
            if size >= min_pt and txt not in seen:
                items.append({"text": txt, "size_pt": round(size, 1)})
                seen.add(txt)
    return items


def core_read_structure(path: str) -> Dict[str, Any]:
    validate_hwpx(path)
    members = read_members(path, _skip_bindata)
    cm = parse_charmap(members.get(HEADER))
    sections: List[Dict[str, Any]] = []
    current = {"heading": "(머리)", "lines": []}
    for name in section_names(members):
        try:
            sec = etree.fromstring(members[name])
        except etree.XMLSyntaxError:
            continue
        for p in iter_body_paragraphs(sec):
            txt = para_text(p).strip()
            if not txt:
                continue
            if para_charsize(p, cm) >= 15.5:
                if current["lines"] or current["heading"] != "(머리)":
                    sections.append(current)
                current = {"heading": txt, "lines": []}
            else:
                current["lines"].append(txt)
    if current["lines"] or current["heading"] != "(머리)":
        sections.append(current)
    return {"file": os.path.basename(path), "sections": sections}


def core_search(path: str, keyword: str, context: bool = False) -> List[Dict[str, Any]]:
    validate_hwpx(path)
    if not keyword:
        raise HwpxReadError("검색어가 비어 있습니다.")
    lines = core_read_text(path, dedupe=True, include_tables=True).split("\n")
    hits: List[Dict[str, Any]] = []
    for i, line in enumerate(lines):
        if keyword in line:
            item: Dict[str, Any] = {"index": i, "line": line}
            if context:
                item["prev"] = lines[i - 1] if i > 0 else ""
                item["next"] = lines[i + 1] if i + 1 < len(lines) else ""
            hits.append(item)
    return hits


def core_info(path: str) -> Dict[str, Any]:
    validate_hwpx(path)
    members = read_members(path, _skip_bindata)
    sec_names = section_names(members)
    n_para = n_tbl = 0
    title = ""
    for name in sec_names:
        try:
            sec = etree.fromstring(members[name])
        except etree.XMLSyntaxError:
            continue
        for p in iter_body_paragraphs(sec):
            txt = para_text(p).strip()
            if txt:
                n_para += 1
                if not title:
                    title = txt
        n_tbl += len(extract_tables(sec))
    preview = ""
    if "Preview/PrvText.txt" in members:
        try:
            preview = members["Preview/PrvText.txt"].decode("utf-8", "replace")
        except Exception:  # noqa
            preview = ""
    return {
        "file": os.path.basename(path),
        "path": os.path.abspath(path),
        "size_kb": round(os.path.getsize(path) / 1024, 1),
        "section_files": len(sec_names),
        "paragraph_count": n_para,
        "table_count": n_tbl,
        "title_guess": title,
        "has_preview": bool(preview),
        "preview_snippet": preview[:200],
    }


def core_read_memos(path: str) -> List[Dict[str, Any]]:
    """문서에 달린 메모(검토 의견)를 문서 순서대로.

    계산은 hwpx_core.memo 가 한다 — 메모 구조를 아는 곳을 한 군데로 둔다
    (읽기와 쓰기가 갈리면 우리가 단 메모를 우리가 못 읽는 일이 생긴다).
    """
    validate_hwpx(path)
    return read_memos_from(path)
