# -*- coding: utf-8 -*-
"""단위별 분량 규격 검증 + 줄 단위 자동 재작성.

autofix_lengths 는 LLM 을 호출한다. 전송은 주입된 llm_chat 콜백에 위임(오프라인 순수 로직).
llm_chat 시그니처: async (messages: list[dict], options: dict) -> str

options 계약(백엔드 중립): 이 모듈은 {"temperature": float} 만 담는다.
컨텍스트 길이·토큰 상한 등 백엔드 고유 파라미터는 콜백(어댑터) 책임이다.
콜백이 예외를 던지면 해당 줄 보정을 조용히 포기한다(문서 생성 자체는 계속).
"""
from __future__ import annotations
import re
from typing import Awaitable, Callable, Optional, Tuple

from .language import has_hanja

# 단위별 분량 규격: (min, max, 목표lo, 목표hi)
# □ 한 줄 38자 이내(재작성 목표 30~38), ◦ 66~70자(두 줄 꽉 채움)
# — 엔진 경고(hwpx_core.linebreak)·스킬·에이전트 도구와 같은 숫자다. 다만 엔진은 두 줄로 넘어간 ◦ 만
#   보고, 여기는 자수만 본다(일정 줄·라벨 나열은 예외). 상위 계층(도구 lint·작성지침)도 같은 숫자를 쓴다.
_LEN_SPEC = {"□": (0, 38, 30, 38), "◦": (66, 70, 66, 70)}

# 길이 감각 보정용 예시 문장 (숫자 지시보다 예시가 소형 모델에 훨씬 잘 먹힘)
_LEN_EXAMPLE = {
    # □ 는 30~38 밴드의 한가운데(34자) — 짧은 예시를 보이면 재작성이 밴드 아래로 수렴한다.
    "□": "☐ (추진배경) 인공지능 도입으로 내부 행정업무 효율화 추진",
    # ⚠️예시는 반드시 자기 규격을 통과해야 한다(check_line_lengths 로 검증).
    #   규격 밖 예시를 보여주면 모델은 숫자가 아니라 예시 길이를 따라간다.
    #   66~70 밴드의 한가운데(68자)를 쓴다 — 상한에 붙이면 조금만 늘어도 위반이다.
    # ⚠️종결은 순수 명사(체언) — 예시가 '~함' 으로 끝나면 모델이 그 어미를 따라간다
    "◦": "◦ 최근 3년간 민원 접수 건수 18% 증가에도 담당 인력은 그대로여서 처리 지연이 잦아 접수 단계 자동 분류제 도입 시급",
}

LlmChat = Callable[[list, dict], Awaitable[str]]


def line_spec(s: str):
    """줄의 단위 규격 반환. 대상 아니면 None."""
    if s.startswith(("□", "☐")):
        return _LEN_SPEC["□"]
    if s.startswith("◦"):
        return _LEN_SPEC["◦"]
    return None


# 일정 줄(날짜 시작)·목록형 줄(라벨 : 나열)은 짧은 게 정상 — 길이 검사 제외
_FREE_RE = re.compile(r"^(?:[('’~∼\s]*\d{2}\s*[.년]|[^:：]{1,24}[:：]\s)")


def line_violation(s: str) -> Optional[Tuple[int, int]]:
    """줄이 분량 규격을 위반하면 재작성 목표 (lo, hi) 를, 아니면 None 을 반환.

    check_line_lengths(검사)와 autofix_lengths(수정)가 반드시 이 단일 판정을
    공유한다 — 판정이 갈리면 검사기가 통과시킨 줄을 수정기가 재작성한다.
    """
    spec = line_spec(s)
    if not spec:
        return None
    if _FREE_RE.match(s[1:].strip()):
        return None
    mn, mx, lo, hi = spec
    if s.startswith(("□", "☐")):
        # □ 는 한 줄(≤38자)뿐이다 — 넘치는 내용은 □ 를 늘리지 않고 ◦ 로 내린다.
        # (종전 □ 두 줄 68~76 허용은 260928 엔진에서 뗐다.)
        if len(s) <= 38:
            return None
        return (lo, hi)
    if mn <= len(s) <= mx:
        return None
    return (lo, hi)


def check_line_lengths(body: str) -> list:
    """□/◦ 줄이 규격을 벗어나면 지적 목록 반환. 판정은 line_violation 과 동일."""
    issues = []
    for line in body.splitlines():
        s = line.strip()
        if line_violation(s) is None:
            continue
        mn, mx, lo, hi = line_spec(s)
        if s.startswith(("□", "☐")):
            issues.append(f"'{s[:18]}…' {len(s)}자 → 한 줄(38자 이내)로 줄이고 "
                          f"넘치는 내용은 ◦ 로 내려라")
        elif len(s) < mn:
            issues.append(f"'{s[:18]}…' {len(s)}자 → {lo}~{hi}자로 늘려라")
        else:
            issues.append(f"'{s[:18]}…' {len(s)}자 → {lo}~{hi}자로 줄여라")
    return issues


def _len_dist(n: int, lo: int, hi: int) -> int:
    return lo - n if n < lo else (n - hi if n > hi else 0)


async def _rewrite_line(llm_chat: LlmChat, line: str, lo: int, hi: int,
                        budget: dict = None) -> str:
    """한 줄을 목표 분량으로 재작성. 모델이 글자 수를 못 세므로:
    목표 길이 예시 제시 + 결과 길이에 따라 방향 바꿔 최대 3회 반복,
    범위 진입 실패 시 가장 근접한 후보 채택(오차 12자 이내).
    budget={"left": n} 지정 시 남은 LLM 호출 수를 소비(렌더당 총량 상한)."""
    s = line.strip()
    marker = s[0]
    example = _LEN_EXAMPLE["□"] if marker in "□☐" else _LEN_EXAMPLE["◦"]
    current = s
    best, best_d = "", 10 ** 9
    for attempt in range(3):
        if budget is not None:
            if budget["left"] <= 0:
                break
            budget["left"] -= 1
        n = len(current)
        direction = "더 길게 풀어" if n < lo else "압축해 짧게"
        messages = [
            {"role": "system",
             "content": "너는 공공기관 보고서 문장 교정기다. 순수 한국어 개조식으로만 "
                        "답한다 — 명사(체언)로 끝내고 ~함/~임/~됨으로 끝내지 않는다. "
                        "한자·중국어 금지. "
                        "원문에 없는 사실·날짜·수치·이름을 절대 지어내지 마라."},
            {"role": "user",
             "content": f"다음 항목을 의미는 유지한 채 {direction} 써라.\n"
                        f"목표 길이는 아래 예시와 비슷하게({len(example)}자 안팎):\n"
                        f"예시: {example}\n"
                        f"'{marker}' 마커로 시작하는 한 줄만 출력하라.\n"
                        f"항목: {current}"},
        ]
        options = {"temperature": 0.3 + 0.15 * attempt}
        try:
            out = (await llm_chat(messages, options) or "").strip()
        except Exception:
            break
        # 마커로 시작하는 첫 줄만 후보로 인정 — 서두("알겠습니다…")를 붙이는
        # 채팅 습성이 마커를 얻어 본문으로 채택되는 것을 차단.
        accepted = ("□", "☐") if marker in "□☐" else (marker,)
        out = next((ln.strip() for ln in out.splitlines()
                    if ln.strip().startswith(accepted)), "")
        if not out or has_hanja(out):
            continue
        d = _len_dist(len(out), lo, hi)
        if d == 0:
            return out
        if d < best_d:
            best, best_d = out, d
        current = out
    return best if best and best_d <= 12 else ""


async def autofix_lengths(body: str, llm_chat: LlmChat,
                          max_fixes: int = 12,
                          max_llm_calls: int = 18) -> Tuple[str, int]:
    """규격 벗어난 줄들을 한 줄씩 재작성. (보정된 body, 보정 줄 수) 반환.
    max_llm_calls: 렌더 1회당 LLM 호출 총량 상한 — 줄당 최대 3회 재시도가
    누적돼 수 분간 잠기는 것을 방지(느린 로컬 7B 기준)."""
    lines = body.splitlines()
    fixed, n_fixed = [], 0
    budget = {"left": max_llm_calls}
    for line in lines:
        s = line.strip()
        viol = line_violation(s)   # check_line_lengths 와 동일 판정 — 규격 내
        if viol and n_fixed < max_fixes and budget["left"] > 0:   # 줄은 건드리지 않는다
            lo, hi = viol
            new = await _rewrite_line(llm_chat, s, lo, hi, budget)
            if new:
                lead = len(line) - len(line.lstrip(" "))
                fixed.append(" " * lead + new)
                n_fixed += 1
                continue
        fixed.append(line)
    return "\n".join(fixed), n_fixed
