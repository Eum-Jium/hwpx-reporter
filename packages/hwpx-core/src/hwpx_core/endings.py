# -*- coding: utf-8 -*-
"""문장 종결 — 개조식은 **체언(순수 명사)으로 끊는다**.

    □ (편성) 직무 연관도에 따라 3개 과정으로 편성      ← 체언
    □ (편성) 직무 연관도에 따라 3개 과정으로 나눈다    ← 용언(서술형) ✗

`~함/~됨/~임/~둠` 같은 명사형 어미도 쓰지 않는다. 이 규칙은 SKILL.md·지침·
writer 프롬프트의 산문에만 있었고, 그러다 **붙임 별지를 쓰면서 통째로 서술형으로
썼다**(08-18). 산문으로만 있는 규칙은 잊힌다 — 그래서 코드로 내린다.

과거형(`표준화하였음`·`완료됐음`·`받았음`)도 같은 금지 대상인데 08-19 까지
**통째로 빠져 있었다** — 금지 목록이 현재형 어간만 담고 있었기 때문이다.
글자를 나열하는 대신 받침으로 판정한다(아래 `_is_past_nominal` 주석).

검사는 한쪽으로만 문다: '다' 로 끝나는 어절과 위 명사형 어미만 잡는다. 체언인지
아닌지를 형태소 없이 가릴 수는 없으므로, **확실한 것만 잡고 나머지는 통과**시킨다
(틀린 경고가 나오면 경고 자체를 안 믿게 된다 — outline·volume 과 같은 원칙).

**stdlib 만 쓴다** — markers.py·gaps.py 와 같은 이유(모드 B 가 파일째 적재한다).
"""
import re

# 명사형 어미 — 규칙이 이름을 대고 금지한 것들.
# ⚠️ 여기 담긴 것은 **현재형 어간 + ㅁ** 뿐이라 과거형을 통째로 놓쳤다
# (`표준화하였음`·`완료됐음`·`받았음` 이 전부 통과했다). 과거형은 아래
# `_is_past_nominal` 이 따로 본다 — 글자를 나열해서는 다 못 담는다.
NOUN_SUFFIX_ENDINGS = ("함", "됨", "임", "둠")

# `음` 을 그냥 금지어에 넣을 수는 없다 — 마음·처음·다음·얼음·믿음·도움·모음·
# 묶음·죽음·웃음·걸음이 전부 걸린다. 뒤의 것들은 어원이 용언 명사형인데 **체언으로
# 굳은 말**이라 글자만 봐서는 못 가른다(_NOUN_EXCEPTIONS 가 '포함'·'책임' 계열에
# 하는 일과 같은 종류의 문제다).
#
# 대신 **받침**을 본다. 한국어 과거 시제 선어말어미는 `-았/었/였-` 하나이고,
# 축약형(했·됐·왔·갔·셨·줬·봤·뒀·냈·졌…)까지 **예외 없이 종성 ㅆ 을 남긴다**.
# 반대로 체언에는 ㅆ 받침 뒤에 `음` 이 오는 말이 없다. 그래서
#   "끝 글자가 `음` 이고 그 앞 글자의 받침이 ㅆ" = 과거형 명사꼴
# 이 오탐 없이 성립한다. 실측(2026-08-19): 과거형 21개 전건 적발 · 체언 20개
# 전건 통과. 글자를 여덟 개 나열하는 안도 검토했지만 줬음·봤음·뒀음·췄음·쳤음·
# 쐈음·냈음·섰음·샀음·졌음 열 개를 놓쳐 이쪽을 쓴다.
_HANGUL_BASE = 0xAC00
_JONG_COUNT = 28
_JONG_SSANGSIOT = 20        # 종성 ㅆ 의 자리 (있·했·왔 의 받침)


def _is_past_nominal(word: str) -> bool:
    """`-았/었/였-` 계열 과거형의 명사꼴(`…았음`·`했음`·`줬음`)인지."""
    if len(word) < 2 or not word.endswith("음"):
        return False
    code = ord(word[-2]) - _HANGUL_BASE
    if not 0 <= code < 11172:               # 한글 음절이 아니면 판정하지 않는다
        return False
    return code % _JONG_COUNT == _JONG_SSANGSIOT

# '함'·'임' 으로 끝나는 **명사**들. 어미와 글자가 같아 그냥 두면 거짓 경고가 난다
# (실제로 '자동 포함' 이 서술형으로 잡혔다). '됨'·'둠' 은 명사 사례가 없어 뺀다.
_NOUN_EXCEPTIONS = frozenset({
    "포함", "불포함", "미포함", "명함",
    "책임", "위임", "선임", "주임", "담임", "소임", "연임", "전임", "후임",
    "상임", "겸임", "부임", "취임", "해임", "재임", "역임",
})

# 끝에 붙어도 종결로 보지 않는 것(따옴표·괄호·마침표 등)
_TRIM = " \t.…\"'”’)〕】」』"

_MARKERS = "□☐◦-·*"


def _tail(text: str) -> str:
    """종결로 볼 마지막 어절."""
    s = (text or "").rstrip(_TRIM)
    if not s:
        return ""
    return s.split()[-1].rstrip(_TRIM) if s.split() else ""


def is_verb_ending(text: str) -> bool:
    """서술형(용언) 종결로 끝나는지 — 확실한 것만 True."""
    tail = _tail(text)
    if not tail:
        return False
    if tail.endswith("다"):
        return True
    if tail in _NOUN_EXCEPTIONS:
        return False
    return tail.endswith(NOUN_SUFFIX_ENDINGS) or _is_past_nominal(tail)


def ending_word(text: str) -> str:
    """종결어(마지막 어절). 종결어 중복을 볼 때 쓴다."""
    return _tail(text)


def check_endings(lines, where: str = "본문"):
    """개조식 종결을 어긴 줄을 경고 문자열 목록으로 반환.

    항목 줄(□·◦·*)만 본다 — 헤딩과 표 마커는 문장이 아니다.
    연달아 같은 종결어로 끝나는 것도 함께 잡는다(규칙: 같은 명사로 연달아 끝내지
    않는다). 둘 다 렌더를 막지 않고 사실만 남긴다.
    """
    warns = []
    prev_word = None
    for raw in (lines or []):
        s = (raw or "").strip()
        if not s or s[0] not in _MARKERS:
            # 섹션이 바뀌면 종결어 흐름도 끊긴다 — 헤딩 너머까지 중복으로 보지 않는다
            prev_word = None
            continue
        if re.match(r"^\[(표|이미지|붙임)\s*\d*\]?", s):
            continue
        if is_verb_ending(s):
            warns.append(f"[종결] {where}에 서술형 종결이 있다 — '{_tail(s)}' "
                         f"({s[:26]}…) 체언으로 끊을 것")
        word = ending_word(s)
        if word and word == prev_word:
            warns.append(f"[종결] 같은 종결어가 잇달아 쓰였다 — '{word}' "
                         f"({s[:26]}…) 다른 말로 바꿀 것")
        prev_word = word
    return warns
