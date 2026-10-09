# -*- coding: utf-8 -*-
"""본문 복구: 모델이 body 인자 대신 답변 텍스트에 본문을 써버린 경우 대비."""
from __future__ import annotations
import re

_BLANK_KEYWORDS = ("빈 양식", "빈양식", "빈 문서", "빈문서", "내용 없이", "내용없이",
                   "본문 없이", "본문없이")
# 약한 신호: "양식만 맞춰서 내용 채워줘" 처럼 채움 지시와 함께 오면 빈 양식 의도가 아님
_BLANK_WEAK = ("서식만", "양식만", "틀만", "골격만", "뼈대만")
_FILL_INTENT = re.compile(r"채워|채우|내용[을은는이가 ]{0,3}(넣|포함|작성|써)")

_MARKER_LINE = re.compile(r"^\s*(?:[①-⑮]|\d+[.)]|[□☐◦○●\-*※])\s")


def user_wants_blank(conversation: list) -> bool:
    """가장 최근 사용자 메시지에 '빈 양식만' 의도가 있는지."""
    for msg in reversed(conversation or []):
        if msg.get("role") == "user":
            text = msg.get("content", "")
            if any(k in text for k in _BLANK_KEYWORDS):
                return True
            if any(k in text for k in _BLANK_WEAK):
                return not _FILL_INTENT.search(text)
            return False
    return False


def _current_turn(conversation: list) -> list:
    """마지막 user 메시지 이후(현재 턴)의 메시지만.
    이전 턴의 다른 보고서 본문이 새 요청 문서로 유입되는 것을 차단한다."""
    conv = conversation or []
    for i in range(len(conv) - 1, -1, -1):
        if conv[i].get("role") == "user":
            return conv[i + 1:]
    return conv


def extract_body_from_conversation(conversation: list) -> str:
    """현재 턴의 assistant 메시지에서 항목부호(□◦-* / 1.)로 시작하는 줄을 뽑아 body 재구성.
    마크다운 헤더(##)·볼드(**)는 정리. 헤딩 2개+항목 2개 이상이면 유효 본문으로 간주.
    스캔 범위는 마지막 user 메시지 이후로 한정(이전 턴 본문 유입 방지)."""
    for msg in reversed(_current_turn(conversation)):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or ""
        lines = []
        for raw in content.splitlines():
            s = raw.strip()
            if not s:
                continue
            s = re.sub(r"^#{1,6}\s*", "", s)
            s = s.replace("**", "")
            if _MARKER_LINE.match(s):
                lines.append(s)
        n_head = sum(1 for l in lines if re.match(r"^\d+[.)]", l))
        n_item = sum(1 for l in lines if l[0] in "□☐◦○●-*")
        if n_head >= 2 and n_item >= 2:
            return "\n".join(lines)
    return ""
