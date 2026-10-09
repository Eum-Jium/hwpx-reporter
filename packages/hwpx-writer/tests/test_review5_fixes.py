# -*- coding: utf-8 -*-
"""5차 코드리뷰 수정 회귀 — writer.

마커 오인(본문 글자 파괴)·bullet 교체 누락·store 동시성·
셀 첫 줄 Bold 소실·heading align 무시.
"""
import threading
import zipfile

from lxml import etree

import hwpx_mcp.server as srv
from hwpx_mcp.engine.render import _detect_line, _strip_marker, render_from_blocks

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def fn(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


# ── 본문 첫 글자를 마커로 오인하지 않는다 ─────────────────
def test_detect_line_keeps_ambiguous_leading_chars():
    assert _detect_line("-5% 절감 달성")[0] is None          # 음수
    assert _detect_line("○○부와 협의 완료")[0] is None       # 자리표 원
    assert _detect_line("ㅁ자형 구조물 설치")[0] is None      # 한글 낱자
    assert _detect_line("ㅇㅇ기관 방문")[0] is None


def test_detect_line_still_accepts_spaced_aliases():
    assert _detect_line("○ 세부 내용")[0] == "◦"
    assert _detect_line("ㅁ 핵심 항목")[0] == "□"
    assert _detect_line("- 세부 근거")[0] == "-"
    assert _strip_marker("○ 세부 내용", "◦") == "세부 내용"
    assert _detect_line("□ 핵심")[0] == "□"                  # 순수 기호는 그대로


def test_add_bullet_keeps_placeholder_org_name():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_bullet")(document_id=did, section_key=sk, text="○○부와 협의 완료")
    blocks = fn("get_document")(document_id=did)["sections"][0]["blocks"]
    assert blocks[-1]["text"] == "○○부와 협의 완료"


# ── set_section_body 가 bullet 도 교체한다 (표는 보존) ─────
def test_set_section_body_replaces_bullets_keeps_tables():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_bullet")(document_id=did, section_key=sk, text="옛 항목 1")
    fn("add_bullet")(document_id=did, section_key=sk, text="옛 항목 2")
    fn("add_table")(document_id=did, section_key=sk,
                    headers=["a"], rows=[["1"]])
    r = fn("set_section_body")(document_id=did, section_key=sk, text="□ 새 본문")
    assert r["status"] == "success"
    blocks = fn("get_document")(document_id=did)["sections"][0]["blocks"]
    types = [b["type"] for b in blocks]
    assert types == ["paragraph", "table"]          # bullet 소멸, 표 보존
    assert blocks[0]["text"] == "□ 새 본문"
    assert r["preserved_blocks"] == 1


# ── store: 동시 수정에서 갱신 유실 없음 + 원자적 쓰기 ──────
def test_store_concurrent_modify_loses_nothing():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]

    def add(i):
        fn("add_bullet")(document_id=did, section_key=sk, text=f"동시 항목 {i}")

    threads = [threading.Thread(target=add, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    blocks = fn("get_document")(document_id=did)["sections"][0]["blocks"]
    texts = {b["text"] for b in blocks}
    assert texts == {f"동시 항목 {i}" for i in range(8)}     # 8건 전부 생존


def test_store_write_leaves_no_tmp():
    did = fn("create_document")(title="x")["document_id"]
    path = srv.store._path(did)
    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()


# ── 렌더 골든: 셀 첫 줄 Bold 보존 + 목차 헤딩 CENTER ───────
def _charpr_is_bold(hdr, cid: str) -> bool:
    for cp in hdr.iter(f"{{{HH}}}charPr"):
        if cp.get("id") == cid:
            return cp.find(f"{{{HH}}}bold") is not None
    return False


def test_multiline_cell_first_line_stays_bold(tmp_path):
    out = str(tmp_path / "cell.hwpx")
    render_from_blocks({"title": "t", "blocks": [
        {"type": "table", "style": "gov",
         "headers": ["구분"], "rows": [["제목줄\n설명줄"]]},
    ]}, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    bolds = []
    for t in sec.iter(f"{{{HP}}}t"):
        if t.text in ("제목줄", "설명줄"):
            run = t.getparent()
            bolds.append((t.text, _charpr_is_bold(hdr, run.get("charPrIDRef"))))
    assert ("제목줄", True) in bolds       # 첫 줄 자동 Bold 유지
    assert ("설명줄", False) in bolds      # 이후 줄은 본문 서식


def test_toc_heading_centered(tmp_path):
    out = str(tmp_path / "toc.hwpx")
    render_from_blocks({"title": "t", "blocks": [
        {"type": "toc", "entries": ["1. 개요"]},
        {"type": "heading", "text": "1. 개요", "level": 2},
    ]}, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    pid = None
    for t in sec.iter(f"{{{HP}}}t"):
        if t.text == "목  차":
            pid = t.getparent().getparent().get("paraPrIDRef")
    assert pid is not None
    horizontals = {pp.get("id"): al.get("horizontal")
                   for pp in hdr.iter(f"{{{HH}}}paraPr")
                   for al in pp.iter(f"{{{HH}}}align")}
    assert horizontals.get(pid) == "CENTER"
