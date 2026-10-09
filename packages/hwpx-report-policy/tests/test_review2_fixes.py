# -*- coding: utf-8 -*-
"""2차 리뷰 수정 회귀: 턴 경계 복구(C2), 양식만 오탐, 호환한자, 최신 이벤트 요약, LLM 총량 상한."""
import asyncio
import json

from hwpx_report_policy import ReportPolicy, WEAK_7B
from hwpx_report_policy import language as L, body as B, length as LEN

BODY_MD = "### 1. 개요\n□ 이전 보고서 핵심 항목\n◦ 이전 세부 내용\n### 2. 계획\n◦ 다음 단계"


# ── C2: 본문 복구 턴 경계 ────────────────────────────────
def test_recovery_ignores_previous_turn():
    """이전 턴의 본문은 새 요청 복구에 쓰이면 안 됨."""
    conv = [
        {"role": "user", "content": "기획 보고서 써줘"},
        {"role": "assistant", "content": BODY_MD},          # 1턴 결과물
        {"role": "user", "content": "이번엔 회의결과 보고서 써줘"},  # 새 턴, 본문 없음
    ]
    assert B.extract_body_from_conversation(conv) == ""


def test_recovery_uses_current_turn():
    conv = [
        {"role": "user", "content": "기획 보고서 써줘"},
        {"role": "assistant", "content": BODY_MD},          # 현재 턴 답변
    ]
    out = B.extract_body_from_conversation(conv)
    assert "1. 개요" in out and "이전 보고서 핵심 항목" in out


def test_gate_rejects_when_only_previous_turn_body():
    """빈 body + 현재 턴에 복구할 본문 없음 → 이전 턴 유입 대신 거부(재작성 요구)."""
    async def _no_llm(messages, options):
        raise AssertionError("llm_chat 호출 금지")
    policy = ReportPolicy(WEAK_7B, llm_chat=_no_llm,
                          guide_text=lambda k: f"[{k} 지침]",
                          guided_types={"planning"},
                          template_specs={"planning": {}})
    conv = [
        {"role": "user", "content": "기획 보고서 써줘"},
        {"role": "assistant", "content": BODY_MD},
        {"role": "user", "content": "다른 주제로 하나 더"},
    ]
    reject, body, notes = asyncio.run(policy.prepare_render_args(
        {"template_key": "planning", "body": ""},
        guides_read={"planning"}, last_guide_key="planning", conversation=conv))
    assert reject is not None and body == ""
    assert "body_recovered_from_reply" not in notes


# ── 양식만 오탐 ──────────────────────────────────────────
def test_blank_weak_keyword_with_fill_intent_is_not_blank():
    conv = [{"role": "user", "content": "회의결과 양식만 맞춰서 내용 채워줘"}]
    assert not B.user_wants_blank(conv)


def test_blank_weak_keyword_alone_is_blank():
    assert B.user_wants_blank([{"role": "user", "content": "양식만 뽑아줘"}])
    assert B.user_wants_blank([{"role": "user", "content": "빈 양식 주세요"}])


# ── 호환 한자 블록 ───────────────────────────────────────
def test_compat_hanja_detected():
    assert L.has_hanja("樂")            # 樂 이체 (KS X 1001 호환한자)
    assert L.has_hanja("\U00020000")        # 확장 B
    assert not L.has_hanja("순수 한국어 문장")
    assert not L.has_hanja("한글ABC 123 ◦□")


# ── sanitize_reply 최신 이벤트 ───────────────────────────
def test_sanitize_reply_uses_latest_success():
    def ev(path):
        return {"name": "render_from_skeleton", "error": False,
                "result": json.dumps({"status": "success", "template_label": "기획 보고서",
                                       "path": path, "body_result": {"filled": True, "lines": 3}})}
    events = [ev("/old/v1.hwpx"), ev("/new/v2.hwpx")]
    out = L.sanitize_reply("報告", events)
    assert "v2.hwpx" in out and "v1.hwpx" not in out


# ── autofix LLM 호출 총량 상한 ───────────────────────────
def test_autofix_total_llm_call_cap():
    calls = {"n": 0}

    async def bad_llm(messages, options):
        calls["n"] += 1
        return "◦ 짧음"          # 항상 규격 미달 → 줄당 3회 전부 소진 유도

    body = "\n".join("◦ 너무짧은줄" for _ in range(12))   # 최악: 12줄 × 3회 = 36회
    fixed, n = asyncio.run(LEN.autofix_lengths(body, bad_llm,
                                               max_fixes=12, max_llm_calls=6))
    assert calls["n"] <= 6
