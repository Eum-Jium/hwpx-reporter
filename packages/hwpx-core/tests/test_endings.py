# -*- coding: utf-8 -*-
"""개조식 종결 검사 — 특히 **과거형 명사꼴**.

`-았/었/였-` 계열이 통째로 빠져 있었다(2026-08-19 발견). 금지 목록이 현재형
어간(`함·됨·임·둠`)만 담고 있어 `표준화하였음`·`완료됐음`·`받았음` 이 전부
통과했다. 이 검사기는 lint 에 warning 으로 걸려 있어 **거짓 양성이 0 이어야**
한다 — 그래서 과거형을 잡는 쪽과 체언을 통과시키는 쪽을 함께 붙든다.
"""
import pytest

from hwpx_core import endings as E


# ── 잡아야 하는 것 ───────────────────────────────────────────
PAST = [
    # 하였/되었 계열 (종결 검사를 빠져나가던 것들)
    "표준화하였음", "검토하였음", "참석하였음",
    "완료됐음", "확인했음", "늘었음", "줄였음", "받았음",
    # 여덟 글자를 나열하는 안이 놓치던 축약형 — 받침 규칙은 잡는다
    "줬음", "봤음", "뒀음", "췄음", "쳤음", "쐈음", "냈음", "섰음", "샀음", "졌음",
    "왔음", "갔음", "셨음",
]


@pytest.mark.parametrize("word", PAST)
def test_past_nominal_is_caught(word):
    assert E.is_verb_ending(f"◦ 관련 절차를 {word}"), word


def test_present_stem_endings_still_caught():
    """종전 규칙(함·됨·임·둠)이 그대로 살아 있는지."""
    for w in ("확대함", "수립됨", "시행임", "추진해 둠"):
        assert E.is_verb_ending(f"□ {w}"), w


def test_declarative_still_caught():
    assert E.is_verb_ending("◦ 처리 방식을 바꾼다")


# ── 통과해야 하는 것 (거짓 양성 0) ───────────────────────────
NOUNS = [
    "마음", "처음", "다음", "얼음", "믿음", "도움", "모음", "묶음", "알림음",
    # 어원이 용언 명사형이지만 체언으로 굳은 말 — 규칙으로 못 가르므로 통과해야 한다
    "죽음", "웃음", "울음", "걸음", "싸움",
    # 그냥 '음' 으로 끝나는 보통 명사
    "발음", "소음", "자음", "모음집",
]


@pytest.mark.parametrize("word", NOUNS)
def test_noun_ending_in_eum_passes(word):
    assert not E.is_verb_ending(f"◦ 확인한 것은 {word}"), word


def test_noun_exceptions_still_pass():
    for w in ("자동 포함", "담당자 책임", "기관 위임"):
        assert not E.is_verb_ending(f"□ {w}"), w


def test_plain_noun_endings_pass():
    for w in ("체계 마련", "대기시간 단축", "기반 완성"):
        assert not E.is_verb_ending(f"□ {w}"), w


# ── 판정 근거가 받침이라는 것 ────────────────────────────────
def test_rule_is_the_ssang_batchim_not_a_word_list():
    """새로 생긴 축약 과거형도 목록을 고치지 않고 잡혀야 한다.

    `-았/었/였-` 과 그 축약형은 예외 없이 종성 ㅆ 을 남긴다는 것이 근거다.
    """
    assert E._is_past_nominal("팠음") and E._is_past_nominal("깼음")
    assert not E._is_past_nominal("얼음") and not E._is_past_nominal("묶음")
    # 한글이 아닌 글자가 앞에 오면 판정하지 않는다(터지지 않아야 한다)
    assert not E._is_past_nominal("A음")
    assert not E._is_past_nominal("음")


def test_check_endings_reports_past_form():
    warns = E.check_endings(["□ 표준서식 적용률을 확인했음"], "본문")
    assert warns and "확인했음" in warns[0]
