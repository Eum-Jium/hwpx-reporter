# -*- coding: utf-8 -*-
"""3차 코드리뷰(소형 Qwen 전제) 수정 회귀 — reader."""
import os

import pytest

import hwpx_reader.server as srv


def _tool(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


def _sample_hwpx() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = os.path.join(here, "..", "..", "hwpx-skeleton", "src",
                       "hwpx_skeleton", "assets", "templates", "standard.hwpx")
    return os.path.abspath(tpl)


# ── m14: 절대경로 강제 + 루트 제한(opt-in) ────────────────
def test_relative_path_rejected():
    r = _tool("read_text")(path="output/x.hwpx")
    assert r["status"] == "error" and "절대 경로" in r["message"]


def test_reader_root_restriction(monkeypatch, tmp_path):
    monkeypatch.setattr(srv, "_READER_ROOT", str(tmp_path))
    r = _tool("read_text")(path=_sample_hwpx())
    assert r["status"] == "error" and "허용 루트" in r["message"]


def test_all_tools_share_path_guard():
    for name in ("read_tables", "outline", "read_structure", "search", "info"):
        kwargs = {"path": "relative.hwpx"}
        if name == "search":
            kwargs["keyword"] = "x"
        r = _tool(name)(**kwargs)
        assert r["status"] == "error" and "절대 경로" in r["message"], name


# ── m15: read_text offset 이어읽기 + search truncated ─────
def test_read_text_offset_pagination(monkeypatch):
    monkeypatch.setattr(srv, "_MAX_TEXT_CHARS", 40)
    p = _sample_hwpx()
    first = _tool("read_text")(path=p)
    assert first["status"] == "success"
    if not first["truncated"]:
        pytest.skip("템플릿 텍스트가 40자 이하")
    parts, nxt = [first["text"]], first["next_offset"]
    for _ in range(500):
        r = _tool("read_text")(path=p, offset=nxt)
        parts.append(r["text"])
        if not r["truncated"]:
            assert r["next_offset"] is None
            break
        nxt = r["next_offset"]
    assert len("".join(parts)) == first["char_count"]   # 조각 합 = 전체


def test_search_truncated_flag(monkeypatch):
    monkeypatch.setattr(srv, "_MAX_HITS", 1)
    p = _sample_hwpx()
    txt = _tool("read_text")(path=p)["text"]
    ch = next((c for c in txt if not c.isspace()), None)
    assert ch, "빈 템플릿"
    r = _tool("search")(path=p, keyword=ch)
    assert r["status"] == "success"
    if r["hit_count"] > 1:
        assert r["truncated"] is True and len(r["hits"]) == 1
    else:
        assert r["truncated"] is False
