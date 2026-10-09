# -*- coding: utf-8 -*-
"""hwpx-report-policy 동작 고정 테스트 (asyncio.run 사용 — 추가 플러그인 불필요)."""
import asyncio

from hwpx_report_policy import ReportPolicy, WEAK_7B, STRONG
from hwpx_report_policy import language as L, body as B, length as LEN

# ── 순수 함수 ─────────────────────────────────────────────
def test_find_hanja():
    assert L.find_hanja({"fields": {"title": "AI 자동화"}, "body": "□ 한국어"}) == []
    assert "body" in L.find_hanja({"fields": {}, "body": "□ 水質"})
    assert any("fields.t" in x for x in L.find_hanja({"fields": {"t": "報告"}, "body": ""}))


def test_has_hanja():
    assert L.has_hanja("完了") and not L.has_hanja("완료")


def test_check_line_lengths():
    # □ 38자 초과 → 지적, ◦ 66 미만 → 지적 (◦ 66~70 — 두 줄 꽉 채움)
    body = "□ " + "가" * 40 + "\n◦ " + "가" * 60
    issues = LEN.check_line_lengths(body)
    assert len(issues) == 2
    # 규격 내면 지적 없음 (◦ 전체 68자)
    assert LEN.check_line_lengths("□ 짧은 핵심\n◦ " + "가" * 66) == []


def test_sanitize_reply():
    import json
    ev = [{"name": "render_from_skeleton", "error": False,
           "result": json.dumps({"status": "success", "template_label": "기획 보고서",
                                  "path": "/x/y.hwpx", "body_result": {"filled": True, "lines": 8}})}]
    # 한자 없으면 그대로
    assert L.sanitize_reply("정상 응답", ev) == "정상 응답"
    # 한자 있으면 도구결과 기반 요약
    out = L.sanitize_reply("報告 完了", ev)
    assert "기획 보고서" in out and "y.hwpx" in out and "8줄" in out


def test_user_wants_blank():
    assert B.user_wants_blank([{"role": "user", "content": "빈 양식만 줘"}])
    assert not B.user_wants_blank([{"role": "user", "content": "기획 보고서 만들어줘"}])


def test_extract_body_from_conversation():
    conv = [{"role": "assistant",
             "content": "### 1. 개요\n□ **핵심** 항목\n◦ 세부 내용\n### 2. 계획\n◦ 다음"}]
    out = B.extract_body_from_conversation(conv)
    assert "1. 개요" in out and "**" not in out and "###" not in out
    # 헤딩/항목 부족하면 빈 문자열
    assert B.extract_body_from_conversation([{"role": "assistant", "content": "그냥 텍스트"}]) == ""


# ── 게이트 (prepare_render_args) ──────────────────────────
def _policy(config=WEAK_7B):
    async def _no_llm(messages, options):
        raise AssertionError("llm_chat 가 호출되면 안 됨")
    return ReportPolicy(config, llm_chat=_no_llm,
                        guide_text=lambda k: f"[{k} 지침]",
                        guided_types={"planning"},
                        template_specs={"planning": {}})


def _prep(policy, args, guides_read=None, last_guide_key=None, conversation=None):
    return asyncio.run(policy.prepare_render_args(
        args, guides_read=guides_read if guides_read is not None else set(),
        last_guide_key=last_guide_key, conversation=conversation or []))


def test_gate_empty_body_rejects():
    reject, body, notes = _prep(_policy(), {"template_key": "planning", "body": ""})
    assert reject is not None and "body 인자가 비어" in reject["message"]


def test_gate_guide_not_read_rejects_with_guide():
    gr = set()
    reject, body, notes = _prep(_policy(), {"template_key": "planning", "body": "□ 핵심\n◦ " + "가" * 60},
                                guides_read=gr)
    assert reject is not None and "[planning 지침]" in reject["message"]
    assert "planning" in gr  # 지침 전달됨 표시


def test_gate_hanja_rejects():
    reject, body, notes = _prep(_policy(), {"template_key": "planning", "body": "□ 水質 관리"},
                                guides_read={"planning"})
    assert reject is not None and "한자" in reject["message"]


def test_gate_clean_passes():
    reject, body, notes = _prep(_policy(),
                                {"template_key": "planning", "fields": {}, "body": "□ 짧은 핵심\n◦ " + "가" * 60},
                                guides_read={"planning"})
    assert reject is None and body.startswith("□")


def test_gate_template_key_fallback():
    reject, body, notes = _prep(_policy(), {"template_key": "", "body": "□ 핵심\n◦ " + "가" * 60,
                                            "template_key_missing": True},
                                guides_read={"planning"}, last_guide_key="planning")
    # 폴백으로 planning 채워짐 → 통과
    assert reject is None


def test_strong_config_bypasses_hanja_and_guide():
    # STRONG: 한자 허용 + 지침 강제 없음 → 한자 body 도 통과
    reject, body, notes = _prep(_policy(STRONG), {"template_key": "planning", "body": "□ 水質"},
                                guides_read=set())
    assert reject is None


def test_user_guard_toggle():
    assert _policy(WEAK_7B).user_guard()          # WEAK: 가드 있음
    assert _policy(STRONG).user_guard() == ""      # STRONG: 없음


# ── 코드리뷰 회귀 테스트 (2026-07) ─────────────────────────
import dataclasses


def test_config_frozen_no_cross_contamination():
    # 프리셋 불변 — 런타임 변이 불가(공유 인스턴스여도 서로 오염 안 됨)
    try:
        WEAK_7B.reject_hanja = False
        assert False, "frozen 이어야 함"
    except dataclasses.FrozenInstanceError:
        pass
    assert WEAK_7B.reject_hanja is True
    assert STRONG.reject_hanja is False and STRONG.autofix_length is False


def test_recovered_body_bypasses_guide_gate():
    # #1: _recovered_body=True 면 지침 미독이어도 통과(rescue 경로)
    reject, body, notes = _prep(
        _policy(),
        {"template_key": "planning", "body": "□ 핵심\n◦ " + "가" * 60, "_recovered_body": True},
        guides_read=set())
    assert reject is None
    assert notes.get("body_recovered_from_reply") is True


def test_rescue_render_succeeds_without_guide_read():
    # #1: 지침 미독 + 본문은 답변에만 → rescue 가 살려냄(이전엔 None 유실). 마커 전달 확인.
    captured = {}

    async def render_fn(a):
        captured.update(a)
        return {"status": "success", "path": "x.hwpx", "template_label": "기획 보고서"}

    conv = [{"role": "assistant",
             "content": "1. 개요\n□ 항목 하나\n◦ 세부 설명\n2. 계획\n◦ 다음 단계"}]
    ev = asyncio.run(_policy().rescue_render(
        {"template_key": "planning"}, conversation=conv,
        last_guide_key=None, render_fn=render_fn))
    assert ev is not None and ev["name"] == "render_from_skeleton"
    assert captured.get("_recovered_body") is True   # 지침 게이트 우회 표시가 전달됨


def test_rescue_render_none_result_no_crash():
    # #2: render_fn 이 None 반환해도 크래시 없이 None
    async def render_fn(a):
        return None

    conv = [{"role": "assistant", "content": "1. 개요\n□ 항목\n◦ 세부\n2. 계획\n◦ 다음"}]
    ev = asyncio.run(_policy().rescue_render(
        {"template_key": "planning"}, conversation=conv,
        last_guide_key=None, render_fn=render_fn))
    assert ev is None


def test_non_string_body_no_crash():
    # #2: 7B 가 body 를 리스트로 흘려도 크래시 없이 빈 본문 취급 → empty-body reject
    reject, body, notes = _prep(
        _policy(),
        {"template_key": "planning", "body": ["□ a", "◦ b"]},
        guides_read={"planning"})
    assert reject is not None and "body" in reject["message"]


def test_none_args_no_crash():
    # None 인자여도 크래시 없이 진행
    reject, body, notes = _prep(_policy(), None, guides_read=set())
    assert reject is None and body == ""


def test_autofix_length_branch():
    # 이전엔 미커버였던 autofix 경로: 주입 llm_chat 이 규격 길이로 재작성
    fixed = "◦ " + "가" * 61

    async def llm(messages, options):
        return fixed

    p = ReportPolicy(WEAK_7B, llm_chat=llm, guide_text=lambda k: "g",
                     guided_types={"planning"}, template_specs={"planning": {}})
    reject, body, notes = asyncio.run(p.prepare_render_args(
        {"template_key": "planning", "body": "□ 짧은 핵심\n◦ 너무짧음"},
        guides_read={"planning"}, last_guide_key=None, conversation=[]))
    assert reject is None
    assert notes.get("length_autofix", 0) >= 1
    assert fixed in body


def test_body_recovery_branch():
    # 빈 body + 대화에 본문 → 복구 + notes 표시
    conv = [{"role": "assistant",
             "content": "1. 개요\n□ 항목 하나\n◦ 세부 설명\n2. 계획\n◦ 다음 단계"}]
    reject, body, notes = _prep(
        _policy(), {"template_key": "planning", "body": ""},
        guides_read=set(), conversation=conv)
    assert reject is None
    assert notes.get("body_recovered_from_reply") is True
    assert "개요" in body


# ── 길이 예시는 자기 규격을 통과해야 한다 ─────────────────
def test_length_examples_satisfy_their_own_spec():
    """모델에 보여주는 길이 예시가 규격을 어기면 모델이 예시를 따라간다.

    숫자 지시보다 예시가 강하게 먹히므로, 예시가 곧 사실상의 규격이 된다.
    """
    for marker, example in LEN._LEN_EXAMPLE.items():
        assert LEN.check_line_lengths(example) == [], (
            f"{marker} 예시가 자기 규격을 위반한다({len(example)}자): {example}")
        # 재작성 목표 밴드(lo~hi) 안이어야 한다 — 상한만 보면 짧은 예시가 빠져나간다
        _, _, lo, hi = LEN._LEN_SPEC[marker]
        assert lo <= len(example) <= hi, (
            f"{marker} 예시가 재작성 목표 {lo}~{hi}자 밖이다({len(example)}자): {example}")
