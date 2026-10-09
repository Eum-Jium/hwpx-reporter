# -*- coding: utf-8 -*-
"""4차 코드리뷰(도구 중심) 수정 회귀 — reader 응답 상한 정책 통일.

모든 조회 도구: 상한 보유 + 잘리면 truncated 로 명시(무음 절단 금지).
"""
import os

import hwpx_reader.server as srv


def _tool(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


def _sample_hwpx() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = os.path.join(here, "..", "..", "hwpx-skeleton", "src",
                       "hwpx_skeleton", "assets", "templates", "standard.hwpx")
    return os.path.abspath(tpl)


# ── M2: read_tables 절단 표시 ─────────────────────────────
def test_read_tables_truncation_flagged(monkeypatch):
    monkeypatch.setattr(srv, "_MAX_TABLE_ROWS", 2)
    monkeypatch.setattr(srv.core, "core_read_tables",
                        lambda p: [[["r1"], ["r2"], ["r3"]], [["only"]]])
    r = _tool("read_tables")(path=_sample_hwpx())
    assert r["status"] == "success"
    assert r["truncated"] is True and r["truncated_tables"] == 1
    assert len(r["tables"][0]) == 2 and len(r["tables"][1]) == 1
    assert r["table_count"] == 2


def test_read_tables_real_file_not_truncated():
    r = _tool("read_tables")(path=_sample_hwpx())
    assert r["status"] == "success"
    assert r["truncated"] is False and r["truncated_tables"] == 0


# ── M2: outline 상한 + heading_count ──────────────────────
def test_outline_capped(monkeypatch):
    monkeypatch.setattr(srv, "_MAX_OUTLINE_ITEMS", 2)
    monkeypatch.setattr(srv.core, "core_outline",
                        lambda p, min_pt: [{"text": f"h{i}", "size_pt": 16.0}
                                           for i in range(5)])
    r = _tool("outline")(path=_sample_hwpx())
    assert r["status"] == "success"
    assert r["truncated"] is True
    assert r["heading_count"] == 5 and len(r["headings"]) == 2


def test_outline_real_file_not_truncated():
    r = _tool("outline")(path=_sample_hwpx())
    assert r["status"] == "success"
    assert r["truncated"] is False
    assert r["heading_count"] == len(r["headings"])


# ── M2: read_structure 총량 상한(read_text 와 동일 예산) ──
def test_read_structure_budget_truncation(monkeypatch):
    monkeypatch.setattr(srv, "_MAX_TEXT_CHARS", 10)
    monkeypatch.setattr(srv.core, "core_read_structure",
                        lambda p: {"file": "x.hwpx", "sections": [
                            {"heading": "H" * 5, "lines": ["L" * 20]},
                            {"heading": "h2", "lines": ["z"]}]})
    r = _tool("read_structure")(path=_sample_hwpx())
    assert r["status"] == "success"
    assert r["truncated"] is True
    assert r["section_count"] == 2 and len(r["sections"]) == 1
    assert "read_text" in r.get("hint", "")   # 이어읽기 경로 안내


def test_read_structure_real_file_not_truncated():
    r = _tool("read_structure")(path=_sample_hwpx())
    assert r["status"] == "success"
    assert r["truncated"] is False and "hint" not in r
    assert r["section_count"] == len(r["sections"])


# ── 상한 환경변수 파싱 방어 ───────────────────────────────
def test_env_int_fallback(monkeypatch):
    monkeypatch.setenv("HWPX_READER_TEST_CAP", "abc")
    assert srv._env_int("HWPX_READER_TEST_CAP", 7) == 7
    monkeypatch.setenv("HWPX_READER_TEST_CAP", "-3")
    assert srv._env_int("HWPX_READER_TEST_CAP", 7) == 7
    monkeypatch.setenv("HWPX_READER_TEST_CAP", "12")
    assert srv._env_int("HWPX_READER_TEST_CAP", 7) == 12
