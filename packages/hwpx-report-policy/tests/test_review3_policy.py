# -*- coding: utf-8 -*-
"""3차 코드리뷰(소형 Qwen 전제) 수정 회귀 테스트."""
import asyncio

from hwpx_report_policy import (ReportPolicy, PolicyConfig, WEAK_7B, FAST,
                                  QWEN_STRONG, STRONG, OFF, PRESETS,
                                  resolve_preset)
from hwpx_report_policy import language as L, body as B, length as LEN


def _policy(config=WEAK_7B, guide_text=lambda k: f"[{k} 지침]"):
    async def _no_llm(messages, options):
        raise AssertionError("llm_chat 가 호출되면 안 됨")
    return ReportPolicy(config, llm_chat=_no_llm,
                        guide_text=guide_text,
                        guided_types={"planning"},
                        template_specs={"planning": {}})


def _prep(policy, args, guides_read=None, last_guide_key=None, conversation=None):
    return asyncio.run(policy.prepare_render_args(
        args, guides_read=guides_read if guides_read is not None else set(),
        last_guide_key=last_guide_key, conversation=conversation or []))


# ── C4: HWPX_POLICY 프리셋 리졸버 ─────────────────────────
def test_resolve_preset_strips_and_lowercases():
    # cmd `set X=fast && ...` 의 꼬리 공백 재현
    cfg, name, warn = resolve_preset("fast ")
    assert cfg is FAST and name == "fast" and warn is None
    cfg, name, warn = resolve_preset("  STRONG\t")
    assert cfg is STRONG and name == "strong" and warn is None


def test_resolve_preset_off_and_aliases():
    cfg, name, warn = resolve_preset("off")
    assert cfg is OFF and name == "off" and warn is None
    for alias in ("qwen", "qwen-strong", "strong-qwen"):
        cfg, name, warn = resolve_preset(alias)
        assert cfg is QWEN_STRONG and name == "strong-qwen" and warn is None


def test_resolve_preset_unknown_warns_not_silent():
    cfg, name, warn = resolve_preset("stronk")
    assert cfg is WEAK_7B and name == "weak"
    assert warn and "stronk" in warn      # 무음 폴백 금지 — 경고 필수


def test_resolve_preset_empty_default():
    cfg, name, warn = resolve_preset(None)
    assert cfg is WEAK_7B and name == "weak" and warn is None
    assert set(PRESETS) == {"weak", "fast", "strong-qwen", "strong", "off"}


# ── M6: 빈 body 게이트 토글 ───────────────────────────────
def test_strong_allows_empty_body():
    # STRONG/OFF = "엔진 원형 동작" — 빈 body 도 거부하지 않음(빈 양식 렌더)
    for cfg in (STRONG, OFF, QWEN_STRONG):
        reject, body, notes = _prep(_policy(cfg),
                                    {"template_key": "planning", "body": ""})
        assert reject is None, f"{cfg}: 빈 body 가 거부됨"


def test_weak_still_rejects_empty_body():
    reject, body, notes = _prep(_policy(WEAK_7B),
                                {"template_key": "planning", "body": ""})
    assert reject is not None


def test_blank_keywords_expanded():
    assert B.user_wants_blank([{"role": "user", "content": "틀만 만들어줘"}])
    assert B.user_wants_blank([{"role": "user", "content": "본문 없이 골격만"}])
    # 채움 의도가 같이 오면 빈 양식 아님
    assert not B.user_wants_blank(
        [{"role": "user", "content": "틀만 잡고 내용은 채워줘"}])


# ── M7: 한자 게이트 intent·비문자열 커버 ───────────────────
def test_find_hanja_covers_intent():
    bad = L.find_hanja({"fields": {}, "body": "□ 한국어",
                        "intent": "水質 管理 보고"})
    assert any("intent" in x for x in bad)


def test_find_hanja_covers_nonstring_fields():
    bad = L.find_hanja({"fields": {"title": ["報告", "x"]}, "body": ""})
    assert any("fields.title" in x for x in bad)


def test_gate_rejects_hanja_intent():
    reject, body, notes = _prep(
        _policy(QWEN_STRONG),
        {"template_key": "planning", "body": "□ 한국어", "intent": "水質 보고"})
    assert reject is not None and "intent" in reject["message"]


# ── M8: QWEN_STRONG 프리셋 성격 ───────────────────────────
def test_qwen_strong_keeps_hanja_gate_only():
    p = _policy(QWEN_STRONG)
    # 한자는 거부
    reject, _, _ = _prep(p, {"template_key": "planning", "body": "□ 水質"})
    assert reject is not None and "한자" in reject["message"]
    # 지침 미독은 통과(강모델 전제), 가드도 없음
    reject, _, _ = _prep(p, {"template_key": "planning",
                             "body": "□ 핵심\n◦ " + "가" * 60}, guides_read=set())
    assert reject is None
    assert p.system_guard() == "" and p.user_guard() == ""


# ── M9: options 백엔드 중립화 ─────────────────────────────
def test_autofix_options_are_backend_neutral():
    seen = {}

    async def llm(messages, options):
        seen.update(options)
        return "◦ " + "가" * 61

    body, n = asyncio.run(LEN.autofix_lengths("◦ 너무짧음", llm))
    assert n == 1
    assert "temperature" in seen and "num_ctx" not in seen


# ── M10: autofix 서두(프리앰블) 채택 차단 ──────────────────
def test_rewrite_rejects_preamble_only_output():
    async def llm(messages, options):
        return "알겠습니다. 다음과 같이 수정했습니다:"   # 마커 줄 없음

    body, n = asyncio.run(LEN.autofix_lengths("□ " + "가" * 40, llm))
    assert n == 0 and body == "□ " + "가" * 40   # 원문 유지, 서두 미채택


def test_rewrite_picks_marker_line_after_preamble():
    async def llm(messages, options):
        return "알겠습니다. 다음과 같이 수정했습니다:\n□ 인공지능 기반 내부 행정업무 효율화"

    body, n = asyncio.run(LEN.autofix_lengths("□ " + "가" * 40, llm))
    assert n == 1 and body == "□ 인공지능 기반 내부 행정업무 효율화"


# ── m7: 절단된 result 대신 result_obj 우선 ────────────────
def test_sanitize_reply_prefers_result_obj():
    ev = [{"name": "render_from_skeleton", "error": False,
           "result": '{"status": "success", "template_l',   # 2000자 절단 시뮬레이션
           "result_obj": {"status": "success", "template_label": "기획 보고서",
                          "path": "/x/y.hwpx",
                          "body_result": {"filled": True, "lines": 8}}}]
    out = L.sanitize_reply("報告 完了", ev)
    assert "기획 보고서" in out and "y.hwpx" in out


# ── m9: 지침 파일 없으면 게이트 생략 ───────────────────────
def test_guide_gate_skipped_when_guide_missing():
    p = _policy(WEAK_7B, guide_text=lambda k: None)
    reject, body, notes = _prep(
        p, {"template_key": "planning", "body": "□ 핵심\n◦ " + "가" * 60},
        guides_read=set())
    assert reject is None   # 빈 지침을 동봉해 거부하지 않는다


# ── m10: 시스템 프롬프트 가드 ─────────────────────────────
def test_system_guard_toggle():
    assert "한국어" in _policy(WEAK_7B).system_guard()
    assert _policy(STRONG).system_guard() == ""
