# -*- coding: utf-8 -*-
"""6차 코드리뷰 수정 회귀 — 마커 판정 단일화.

세 렌더 경로(skeleton·writer·스킬 모드 B)가 같은 판정을 쓰는지, 그리고
본문 첫 글자를 마커로 먹던 손상이 실제 문서에서 사라졌는지 확인한다.
"""
import importlib.util
import os

import pytest
from lxml import etree

import hwpx_core as C
import hwpx_skeleton as HS
from hwpx_skeleton.style import _enforce_hierarchy, marker_of
from hwpx_mcp.engine.render import _detect_line

# 본문으로 남아야 하는 줄(마커 아님) / 마커로 잡혀야 하는 줄
PLAIN = ["-5% 절감 달성", "○○부와 협의 완료", "ㅁ자형 구조물", "ㅇㅇ기관 방문", "[표1]"]
MARKED = [("□ 정상 항목", "□"), ("○ 세부 내용", "◦"), ("- 상세 근거", "-"),
          ("※ 출처: 자료", "*"), ("· 미세", "·")]

_SKILL_SCRIPTS = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "skill", "hwpx", "scripts"))


def _load_hwpx_full():
    """스킬 모드 B 모듈 적재. vendor/ 는 build_skill.py 파생물이라 없으면 skip."""
    path = os.path.join(_SKILL_SCRIPTS, "hwpx_full.py")
    vendor = os.path.join(_SKILL_SCRIPTS, "vendor", "hwpx_core", "markers.py")
    if not os.path.exists(vendor):
        pytest.skip("skill vendor/ 미생성 — python skill/build_skill.py 후 실행")
    spec = importlib.util.spec_from_file_location("_hwpx_full_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 세 경로가 같은 판정을 낸다 ────────────────────────────
def test_three_paths_agree():
    full = _load_hwpx_full()
    for line in PLAIN + [t for t, _ in MARKED]:
        sk = marker_of(line)
        wr = _detect_line(line)[0]
        sl = full._MARKERS_MOD.canon_marker(line)
        assert sk == wr == sl, f"{line!r}: skeleton={sk} writer={wr} skill={sl}"


def test_plain_lines_are_not_markers():
    for line in PLAIN:
        assert marker_of(line) is None, line
        assert _detect_line(line)[0] is None, line


def test_marked_lines_detected():
    for line, expected in MARKED:
        assert marker_of(line) == expected, line
        assert _detect_line(line)[0] == expected, line


# ── skeleton: 계층 교정이 본문을 훼손하지 않는다 ───────────
def test_hierarchy_keeps_negative_number():
    out = _enforce_hierarchy(["□ 예산 절감 실적", "-3.2%p 하락 기록"])
    assert out[1] == "-3.2%p 하락 기록"      # 부호 보존, ◦ 승격 없음


def test_control_line_does_not_reset_hierarchy():
    out = _enforce_hierarchy(["□ 항목", "◦ 세부", "[표1]", "- 상세 근거"])
    assert out[3] == "- 상세 근거"           # ◦ 로 오승격되지 않는다


def test_hierarchy_still_promotes_real_dash():
    # □ 바로 아래 ◦ 없이 온 진짜 '- ' 는 여전히 ◦ 로 승격
    out = _enforce_hierarchy(["□ 항목", "- 세부 내용"])
    assert out[1] == "◦ 세부 내용"


def test_render_preserves_sign_end_to_end(tmp_path):
    r = HS.render("business_result", {"title": "부호 보존 검증"},
                  output_dir=str(tmp_path),
                  body="1. 개요\n□ 예산 절감 실적\n-3.2%p 하락 기록")
    assert r["status"] == "success"
    members = C.read_members(r["path"])
    sec = etree.fromstring(members[C.section_names(members)[0]])
    lines = [C.para_text(p).strip() for p in C.iter_body_paragraphs(sec)]
    assert any(l == "-3.2%p 하락 기록" for l in lines), lines


# ── 스킬 모드 B: 첫 글자 보존 + ※ 이중 마커 없음 ──────────
def test_skill_mode_b_keeps_body_chars():
    full = _load_hwpx_full()
    d = full.Doc("t").body("○○부와 협의 완료\n-5% 절감 달성")
    texts = []
    for b in d._blocks:
        if b.get("text"):
            texts.append(b["text"])
        elif b.get("para") is not None:
            texts.append("".join(r["text"] for r in b["para"]._runs))
    joined = "\n".join(texts)
    assert "○○부와 협의 완료" in joined, texts
    assert "-5% 절감 달성" in joined, texts


def test_skill_mode_b_no_double_note_marker():
    full = _load_hwpx_full()
    d = full.Doc("t").body("※ 출처: 내부 자료")
    texts = [b["text"] for b in d._blocks if b.get("text")]
    assert texts == ["    * 출처: 내부 자료"], texts


def test_skill_mode_b_note_direct_call():
    full = _load_hwpx_full()
    d = full.Doc("t")
    d.note("※ 출처: 자료")
    d.note("* 출처: 자료")
    texts = [b["text"] for b in d._blocks if b.get("text")]
    assert texts == ["    * 출처: 자료", "    * 출처: 자료"], texts
