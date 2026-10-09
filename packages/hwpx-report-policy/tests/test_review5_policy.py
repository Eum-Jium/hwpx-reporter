# -*- coding: utf-8 -*-
"""5차 코드리뷰 수정 회귀 — policy.

검사(check)와 수정(autofix)의 판정 일치 + rescue 이벤트 키 계약.
"""
import asyncio

import hwpx_report_policy.length as LEN
from hwpx_report_policy import ReportPolicy, WEAK_7B
from hwpx_report_policy.language import sanitize_reply

VALID_ONE_LINE = "□ " + "가" * 34          # 36자 — 한 줄(38자 이내)
BAD_LONG = "□ " + "나" * 40                # 42자 — □ 는 한 줄뿐(261011)
EXEMPT_SCHEDULE = "◦ 일정: '26. 9월 시범 운영"   # 라벨 줄 — 길이 규격 면제


def test_check_and_autofix_share_judgment():
    body = "\n".join([VALID_ONE_LINE, BAD_LONG, EXEMPT_SCHEDULE])
    assert len(LEN.check_line_lengths(body)) == 1      # 위반은 1건뿐

    calls = []

    async def llm(messages, options):
        calls.append(messages[-1]["content"])
        return "□ 인공지능 기반 내부 행정업무 효율화"

    fixed, n = asyncio.run(LEN.autofix_lengths(body, llm))
    assert n == 1                                      # 위반 줄만 재작성
    lines = fixed.splitlines()
    assert lines[0] == VALID_ONE_LINE                  # 정상 □ 는 무손상
    assert lines[2] == EXEMPT_SCHEDULE                 # 면제 줄 무손상
    assert len(calls) <= 3                             # 재작성 대상 1줄 분량만 호출


def test_line_violation_matches_check_rules():
    assert LEN.line_violation(VALID_ONE_LINE) is None
    assert LEN.line_violation(BAD_LONG) is not None
    assert LEN.line_violation(EXEMPT_SCHEDULE) is None
    assert LEN.line_violation("□ 짧은 핵심") is None    # 한 줄 규격
    assert LEN.line_violation("◦ 너무짧음") is not None


# ── rescue 이벤트가 소비자와 같은 키(result_obj)를 쓴다 ────
def test_rescue_event_result_obj_reaches_sanitizer():
    big = {"status": "success", "template_label": "기획 보고서",
           "path": "out/r.hwpx", "body_result": {"filled": True, "lines": 12},
           "padding": "x" * 3000}                      # 직렬화 2000자 초과 → 절단

    async def render_fn(args):
        return big

    p = ReportPolicy(WEAK_7B, llm_chat=None, guide_text=lambda k: "g",
                     guided_types={"planning"}, template_specs={"planning": {}})
    conversation = [
        {"role": "user", "content": "기획 보고서 써줘"},
        {"role": "assistant", "content": "1. 개요\n□ 핵심 내용\n2. 계획\n◦ 세부 계획"},
    ]
    ev = asyncio.run(p.rescue_render(
        {"template_key": "planning", "fields": {}},
        conversation=conversation, last_guide_key=None, render_fn=render_fn))
    assert ev is not None
    assert isinstance(ev.get("result_obj"), dict)      # 소비자가 읽는 키

    reply = sanitize_reply("完了했습니다", [ev])         # 한자 → 정화 경로
    assert "기획 보고서" in reply and "out/r.hwpx" in reply
    assert "문제가 있었습니다" not in reply              # 폴백 문구가 아니어야 함
