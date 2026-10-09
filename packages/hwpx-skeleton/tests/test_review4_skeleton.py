# -*- coding: utf-8 -*-
"""4차 코드리뷰(도구 중심) 수정 회귀 — skeleton 에러 봉투 통일.

세 도구 모두 예외가 {"status":"error"} 봉투로 나가야 한다
(생예외 = MCP isError 생텍스트 → status 분기 오케스트레이터 파싱 불가).
"""
import hwpx_skeleton.server as srv


def _tool(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


def _boom(*a, **k):
    raise OSError("디스크 오류 시뮬레이션")


def test_get_writing_guide_exception_enveloped(monkeypatch):
    monkeypatch.setattr(srv.guides, "get_writing_guide", _boom)
    r = _tool("get_writing_guide")(template_key="planning")
    assert r["status"] == "error"
    assert r["stage"] == "get_writing_guide" and "OSError" in r["message"]


def test_list_templates_exception_enveloped(monkeypatch):
    monkeypatch.setattr(srv.renderer, "list_templates", _boom)
    r = _tool("list_templates")()
    assert r["status"] == "error"
    assert r["stage"] == "list_templates" and "OSError" in r["message"]


def test_get_writing_guide_missing_key_has_stage():
    r = _tool("get_writing_guide")(template_key="없는유형")
    assert r["status"] == "error" and r["stage"] == "get_writing_guide"


def test_happy_paths_still_enveloped():
    lt = _tool("list_templates")()
    assert lt["status"] == "success" and lt["templates"]
    gw = _tool("get_writing_guide")(template_key="planning")
    assert gw["status"] == "success" and gw["guide"]


def test_plain_has_no_guide_but_is_not_an_error():
    """기본 유형 plain 은 지침이 없다 — 주 경로(list → guide → render)의 둘째 단계가
    에러 봉투로 끊기지 않게 success 에 빈 지침을 준다."""
    r = _tool("get_writing_guide")(template_key="plain")
    assert r["status"] == "success" and r["guide"] == ""
