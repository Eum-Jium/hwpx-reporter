# -*- coding: utf-8 -*-
"""정책 토글. 약한 모델(7B)일수록 많이 켠다. 강한 모델이면 대부분 끈다."""
from __future__ import annotations
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class PolicyConfig:
    """LLM 출력 품질 보정 정책 on/off.

    대부분은 '모델이 약해서 필요한' 보정이다. 단 reject_hanja/sanitize_reply 는
    모델 크기가 아니라 Qwen 계열(중국계)의 언어 습성(한자 혼입) 대응이므로
    강한 Qwen 에서도 유지를 권장한다(QWEN_STRONG 프리셋).
    불변(frozen) — 프리셋을 공유 인스턴스로 써도 런타임 변이로 서로 오염되지 않는다.
    강도를 바꾸려면 PolicyConfig(...) 로 새 인스턴스를 만든다.
    """
    reject_hanja: bool = True            # fields/body/intent 에 한자 있으면 거부
    enforce_guide_read: bool = True      # 지침 안 읽고 본문 쓰면 지침 동봉해 재작성 요구
    enforce_nonempty_body: bool = True   # body 누락 시 거부(복구 실패 시). 끄면 빈 양식 렌더 허용
    recover_body: bool = True            # body 를 답변에만 쓴 경우 대화에서 복구
    autofix_length: bool = True          # □/◦ 줄 분량 규격 위반 시 줄 단위 재작성
    rescue_render: bool = True           # 렌더 실패로 끝나면 대화에서 본문 뽑아 직접 렌더
    sanitize_reply: bool = True          # 응답에 한자 섞이면 도구결과 기반 요약으로 대체
    template_key_fallback: bool = True   # template_key 누락 시 직전 읽은 지침 유형으로 보완
    language_guard: bool = True          # '순수 한국어' 지시 자동 첨부(시스템 프롬프트 1회)
    max_line_fixes: int = 12             # 한 번에 자동 보정할 최대 줄 수
    max_autofix_llm_calls: int = 18      # 렌더 1회당 분량보정 LLM 호출 총량 상한

    def summary(self) -> str:
        """기동 로그용 요약 — 켜진 불리언 토글 나열."""
        on = [f.name for f in fields(self)
              if isinstance(getattr(self, f.name), bool) and getattr(self, f.name)]
        return "+".join(on) if on else "(all-off)"


# 프리셋 -----------------------------------------------------------------
# 로컬 qwen2.5:7b-instruct 기준 — 전부 켬
WEAK_7B = PolicyConfig()

# 느린 줄단위 분량 자동보정만 끔 (한자·지침·복구·정화는 유지)
FAST = PolicyConfig(autofix_length=False)

# 강한 Qwen 계열용 — 고비용 보정은 끄되 한자 게이트는 유지.
# 한자 혼입은 모델이 약해서가 아니라 Qwen 공통 습성이라 모델 크기와 무관.
QWEN_STRONG = PolicyConfig(
    reject_hanja=True,
    enforce_guide_read=False,
    enforce_nonempty_body=False,
    recover_body=False,
    autofix_length=False,
    rescue_render=False,
    sanitize_reply=False,
    template_key_fallback=False,
    language_guard=False,
)

# 강한 모델(비-Qwen 계열) — 보정 전부 끔 (엔진의 결정론적 서식만 신뢰)
STRONG = PolicyConfig(
    reject_hanja=False,
    enforce_guide_read=False,
    enforce_nonempty_body=False,
    recover_body=False,
    autofix_length=False,
    rescue_render=False,
    sanitize_reply=False,
    template_key_fallback=False,
    language_guard=False,
)

# 정책 완전 비활성 (엔진 원형 동작). frozen 이라 STRONG 별칭이어도 안전.
OFF = STRONG

# 환경변수 HWPX_POLICY 값 → 프리셋 ---------------------------------------
PRESETS = {
    "weak": WEAK_7B,
    "fast": FAST,
    "strong-qwen": QWEN_STRONG,
    "strong": STRONG,
    "off": OFF,
}
_ALIASES = {"qwen": "strong-qwen", "qwen-strong": "strong-qwen"}


def resolve_preset(name, default: str = "weak"):
    """환경변수 값 → (PolicyConfig, 확정 프리셋명, 경고 or None).

    공백·대소문자에 관대하고(cmd 의 `set X=v && ...` 꼬리 공백 포함),
    미인식 값은 default 로 폴백하되 경고 문자열을 함께 돌려준다 —
    호출부는 이를 반드시 로그로 남겨 무음 폴백을 막는다.
    """
    raw = (name or "").strip().lower()
    if not raw:
        return PRESETS[default], default, None
    key = _ALIASES.get(raw, raw)
    if key in PRESETS:
        return PRESETS[key], key, None
    warn = (f"알 수 없는 HWPX_POLICY 값 {name!r} — 기본 '{default}' 적용. "
            f"사용 가능: {', '.join(PRESETS)}")
    return PRESETS[default], default, warn
