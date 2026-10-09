# -*- coding: utf-8 -*-
"""3차 코드리뷰(소형 Qwen 전제) 수정 회귀 — skeleton."""
import copy

from hwpx_skeleton import renderer
import hwpx_skeleton.server as srv


def _tool(obj):
    return getattr(obj, "fn", obj)


# ── C6: 출력 기본값이 CWD 에 의존하지 않는다 ───────────────
def test_default_output_dir_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = renderer.default_output_dir()
    assert str(tmp_path) not in d


# ── M12: 예외도 status=error 봉투로 (isError 생텍스트 금지) ─
def test_render_tool_wraps_exceptions(monkeypatch):
    def boom(**kw):
        raise OSError(13, "액세스가 거부되었습니다")
    monkeypatch.setattr(renderer, "render", boom)
    r = _tool(srv.render_from_skeleton)(template_key="planning", fields={}, body="")
    assert r["status"] == "error" and r["stage"] == "render"
    # OSError(13,...) 은 PermissionError 서브클래스로 승격됨 — 유형명이 봉투에 남는지만 확인
    assert "PermissionError" in r["message"] and "렌더 실패" in r["message"]


# ── m18: review 는 검토보고 양식 (한때 basic 은 렌더 안 되는 설명 페이지였다) ───
def test_review_key_is_the_review_report_form(tmp_path):
    # 서식 설명은 references/format_spec.md 로 갔고, 이 키는 이제 본문을 채운다.
    # 골격은 계획·결과의 4단이 아니라 3단(개요·세부내용·검토의견)이다.
    # (옛 이름 basic 도 별칭으로 받는다 — test_outline 이 확인한다.)
    r = renderer.render(template_key="review", fields={"title": "검토보고"},
                        output_dir=str(tmp_path),
                        body="\n".join(["1. 개요", "□ 무엇을 설명하는지",
                                        "2. 세부내용", "◦ 사실",
                                        "3. 검토의견", "□ 판단"]))
    assert r["status"] == "success"
    assert r["body_result"]["filled"] is True
    assert r["warnings"] == []


# ── m17: 범위 밖 인덱스 필드는 applied 가 아니라 skipped ───
def test_out_of_range_field_reported_as_skipped(tmp_path, monkeypatch):
    spec = copy.deepcopy(renderer.TEMPLATE_SPECS["plan"])
    spec["fields"]["title"]["index"] = 9999   # 템플릿 개정으로 자리 소실 시뮬레이션
    monkeypatch.setitem(renderer.TEMPLATE_SPECS, "plan", spec)
    r = renderer.render(template_key="plan", fields={"title": "제목"},
                        output_dir=str(tmp_path), body=None)
    assert r["status"] == "success"
    assert "title" not in r["applied"]
    assert any("title" in s and "치환 실패" in s for s in r["skipped"])
