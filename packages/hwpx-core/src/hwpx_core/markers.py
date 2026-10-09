# -*- coding: utf-8 -*-
"""항목부호(마커) 판정 — 세 렌더 경로의 단일 기준.

skeleton(style.detect_level) · writer(render._detect_line) · 스킬 모드 B
(hwpx_full.body) 가 전부 이 모듈을 쓴다. 별칭 목록이 갈라지면 같은 본문이
경로마다 다른 계층·간격으로 렌더되고, 경계 규칙이 갈라지면 본문 첫 글자가
마커로 오인돼 삭제된다(실제로 세 경로 모두에서 발생했다).

**stdlib 만 쓴다** — 스킬의 lxml 없는 모드 B 가 이 파일을 그대로 읽어 쓰므로
여기에 lxml 을 들이면 그 경로가 죽는다. hwpx_core 패키지의 다른 모듈도
import 하지 않는다(__init__ 이 lxml 을 끌어온다).
"""

# 별칭 → 정식 기호. ☐=U+2610(표준서식 원본) → □=U+25A1 로 정규화.
CANON = {
    "□": "□", "☐": "□", "ㅁ": "□",
    "◦": "◦", "○": "◦", "ㅇ": "◦",
    "-": "-",
    "·": "·",
    "*": "*", "※": "*",
}

# 본문 실문자와 겹치는 별칭 — 뒤에 공백이 올 때만 마커로 본다.
#   "-5% 절감"(음수) · "○○부와 협의"(기관 자리표) · "ㅁ자형 구조물"(한글 낱자)
#   "**핵심 수치**: …"(볼드로 시작하는 평문)
# 이 경계가 없으면 첫 글자가 마커로 소비돼 문서에서 사라진다.
#
# ⚠️`*` 는 260831 에 들어왔다. 개조식 본문만 받던 시절에는 `* 참고` 뿐이라 안
# 드러났는데, **마크다운을 받기 시작하면서** `**핵심 수치**: …` 가 `* *핵심 수치…`
# 로 나갔다(08-16 실측). 우회는 두 곳에 이미 있었다 — `style.detect_level` 이
# `**` 를 먼저 떼고 판정하고, 다른 변환기는 자기 안에 같은 경계를 넣었다.
# 그 우회들이 이 구멍의 흔적이다. 여기서 막으면 세 경로가 함께 낫는다.
AMBIGUOUS = frozenset("-○ㅁㅇ*")


def lead_marker(line: str):
    """줄 선두의 마커 문자(별칭 그대로). 마커가 아니면 None."""
    s = line.lstrip()
    c = s[:1]
    if c not in CANON:
        return None
    if c in AMBIGUOUS and not (len(s) == 1 or s[1].isspace()):
        return None
    return c


def canon_marker(line: str):
    """줄 선두 마커의 정식 기호(□ ◦ - · *). 마커가 아니면 None."""
    c = lead_marker(line)
    return CANON[c] if c else None


def strip_marker(line: str) -> str:
    """줄 선두 마커를 떼고 내용만 반환. 마커가 없으면 원문(양끝 공백 제거)."""
    s = line.strip()
    return s[1:].strip() if lead_marker(s) else s
