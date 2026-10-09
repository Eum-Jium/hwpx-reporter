# -*- coding: utf-8 -*-
"""hwpx-report-policy — 공공기관 보고서 LLM 출력 품질 보정 미들웨어.

약한 모델(7B)의 흔한 실패(한자 누출·본문 누락·분량 이탈·중도 포기)를 보정한다.
엔진/전송에 의존하지 않는 순수 정책 계층 — 콜백 주입으로 결합을 끊는다.
모델을 교체하면 PolicyConfig 토글만 바꾼다(WEAK_7B ↔ STRONG).

    from hwpx_report_policy import ReportPolicy, WEAK_7B, STRONG
    policy = ReportPolicy(WEAK_7B, llm_chat=..., guide_text=..., guided_types=..., template_specs=...)
"""
from .config import (PolicyConfig, WEAK_7B, FAST, QWEN_STRONG, STRONG, OFF,
                     PRESETS, resolve_preset)
from .policy import ReportPolicy, USER_GUARD, SYSTEM_GUARD
from . import language, body, length

__all__ = [
    "ReportPolicy", "PolicyConfig",
    "WEAK_7B", "FAST", "QWEN_STRONG", "STRONG", "OFF",
    "PRESETS", "resolve_preset",
    "USER_GUARD", "SYSTEM_GUARD",
    "language", "body", "length",
]
__version__ = "0.1.0"
