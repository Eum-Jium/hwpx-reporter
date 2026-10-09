# -*- coding: utf-8 -*-
"""6차 코드리뷰 수정 회귀 — 마커 외 4건.

공백 필드 게이트 · date 치환 안전성 · 간격 규칙 단일화 · 지침 자산 누락 내성.
"""
import os

import pytest
from lxml import etree

import hwpx_core as C
import hwpx_skeleton as HS
from hwpx_core import gaps as CORE_GAPS
from hwpx_skeleton import guides
from hwpx_skeleton.style import gap_pt


def _owner_line(path: str) -> str:
    members = C.read_members(path)
    sec = etree.fromstring(members[C.section_names(members)[0]])
    for p in C.iter_body_paragraphs(sec):
        t = C.para_text(p)
        if "주관" in t:
            return t
    return ""


# ── 공백만 있는 필드는 '없는 값'으로 처리 ─────────────────
def test_whitespace_field_is_skipped_not_blanked(tmp_path):
    r = HS.render("planning", {"title": "   "}, output_dir=str(tmp_path))
    assert r["status"] == "success"
    assert "title" not in r["applied"]                      # 빈 문자열로 덮지 않는다
    assert any(s.startswith("title(") for s in r["skipped"]), r["skipped"]


def test_whitespace_title_does_not_break_date_stamp(tmp_path):
    # 제목을 빈 문자열로 덮으면 비어있지 않은 t 를 세는 날짜 인덱스가 밀려
    # 견본 날짜가 그대로 남았다 — 이제 날짜는 정상 스탬프돼야 한다.
    r = HS.render("planning", {"title": " "}, output_dir=str(tmp_path))
    assert "date" in r["applied"], r
    assert "’26.7.13" not in _owner_line(r["path"])          # 견본 날짜 잔존 금지


# ── date 치환: 정규식 템플릿 해석·제어문자 방어 ────────────
def test_date_backslash_is_literal(tmp_path):
    raw = chr(92) + "1 26.8.5"        # '\1' — 치환 템플릿이면 그룹 참조로 먹힌다
    r = HS.render("planning", {"title": "제목", "date": raw},
                  output_dir=str(tmp_path))
    assert r["status"] == "success"
    assert r["applied"]["date"] == raw
    assert raw in _owner_line(r["path"])                     # 문자 그대로 보존


def test_date_control_char_stripped_consistently(tmp_path):
    r = HS.render("planning", {"title": "제목", "date": chr(1) + " 26.8.5"},
                  output_dir=str(tmp_path))
    assert r["status"] == "success"                          # lxml 예외로 죽지 않는다
    assert chr(1) not in r["applied"]["date"]
    # 돌려준 값과 문서 내용이 일치해야 한다
    assert r["applied"]["date"] in _owner_line(r["path"])


# ── 간격 규칙: skeleton == core == 스킬 모드 B ─────────────
PAIRS = [("·", "heading"), ("·", "·"), ("-", "·"), ("·", "□"), ("*", "□"),
         ("□", "◦"), ("◦", "□"), ("heading", "□"), ("para", "heading")]


def test_skeleton_gap_delegates_to_core():
    for prev, nxt in PAIRS:
        assert gap_pt(prev, nxt) == CORE_GAPS.gap_pt(prev, nxt), (prev, nxt)


def test_skill_mode_b_has_no_own_gap_table():
    # 모드 B(hwpx_full)는 간격을 스스로 정하지 않고 모드 A 엔진으로 찍는다 — 간격 표나
    # 간격 계산을 따로 들고 있으면 두 경로가 다시 갈라진다(261011 에 남은 사본을 걷었다).
    src = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "skill", "hwpx", "scripts", "hwpx_full.py"))
    if not os.path.exists(src):
        pytest.skip("skill/ 없음")
    text = open(src, encoding="utf-8").read()
    assert "_auto_gap" not in text and "_GAP_CHAR" not in text


# ── 지침 자산이 없어도 import·렌더는 계속된다 ──────────────
def test_missing_guidelines_dir_yields_empty_set(monkeypatch, tmp_path):
    monkeypatch.setattr(guides, "GUIDELINES_DIR", str(tmp_path / "없는폴더"))
    assert guides._scan_guided_types() == frozenset()        # 예외 없이 빈 집합


def test_guided_types_still_derived_from_files():
    stems = {f[:-3] for f in os.listdir(guides.GUIDELINES_DIR) if f.endswith(".md")}
    assert guides.GUIDED_TYPES == stems == {"plan", "result", "review"}
