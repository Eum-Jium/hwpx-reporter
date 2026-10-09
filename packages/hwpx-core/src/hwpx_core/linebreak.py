# -*- coding: utf-8 -*-
"""줄바꿈·분량 검사 — 규격이 렌더 경로에서 실제로 물리게 한다.

폭 모델은 tools/verify/linebreak.py 에서 옮겨 왔다(08-15 재보정 실측 그대로).
그 자리에 있을 때는 **사람이 따로 돌려야** 하는 도구였고, 그래서 붙임 본문을
쓰면서 아무도 돌리지 않았다 — □ 가 두 줄로 넘치고 둘째 줄이 한 낱말만 남았다.
규칙은 검사가 붙어야 지켜진다.

원 주석(실측 경위):
줄바꿈 지점 예측 — 첫 줄이 낱말 중간에서 끊기는지 미리 잡는다.

08-15 재보정: 한/글 PDF(2쪽 모아찍기, A4 가로 841×595pt) rawdict 글리프
원점(origin) 실측 기반. 단위는 전부 그 좌표계 pt (한/글 원좌표 ×0.7067).
  - 한글 advance 10.67 (휴먼명조 15pt), 줄머리 괄호 태그 볼드 한글 11.15
  - 공백 자연폭 5.27 — 양쪽정렬이 6.0 안팎으로 늘리기 "전" 값.
    줄나눔 판정은 자연폭 기준이므로 정렬된 지면 폭을 재면 안 된다.
  - 본문 오른끝 R=381.9, 마커 시작 x·연속 줄 내어쓰기 x 실측 고정값.
검증: planning 2판(끊김 3건 위치 재현 + 수정판 어절 경계 전건 재현) +
body.txt(business_result) 렌더판 전건 재현 — 재보정 시 이 셋으로 회귀 확인.

**stdlib 만 쓴다** — markers.py·gaps.py 와 같은 이유(모드 B 가 파일째 적재한다).
"""
import re


R = 381.90            # 본문 텍스트 오른끝
EPS = 0.5             # 넘침 판정 여유
SPACE = 5.27          # 공백 자연폭
HANGUL = 10.67        # 휴먼명조 15pt 한글 advance
HANGUL_BOLD = 11.15   # 줄머리 (태그) 볼드 한글
NOTE_SCALE = 9.23 / 10.67   # * 참고행(한양중고딕 13pt) 폭 축척

MARKER_X = {"□": 45.43, "◦": 50.82, "-": 56.10, "·": 58.00, "*": 58.50}
MARKER_W = {"□": 10.67, "◦": 10.67, "-": 3.54, "·": 4.08, "*": 4.60}
CONT_X = {"□": 61.37, "◦": 67.49, "-": 64.97, "·": 67.60, "*": 63.60}

CHAR_W = {"%": 8.95, "(": 3.60, ")": 3.54, ".": 2.65, ",": 2.65,
          ":": 2.65, "’": 2.88, "‘": 2.88, "·": 4.08, "-": 3.54,
          "~": 5.27, "*": 5.27}
for _d in "0123456789":
    CHAR_W[_d] = 5.27


def width(ch: str, bold: bool = False) -> float:
    """글자 하나의 자연 advance(pt). 한글·전각은 10.67(볼드 11.15)."""
    if ch in (" ", " "):
        return SPACE
    if ch in CHAR_W:
        return CHAR_W[ch]
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or o > 0x2000:
        return HANGUL_BOLD if bold else HANGUL
    return 5.27           # 그 밖의 ASCII(영문 등)


def _bold_span(s: str):
    """줄머리 괄호 태그 '□ (태그) …' 는 볼드로 렌더된다 — 그 구간의 끝 인덱스."""
    j = 1
    while j < len(s) and s[j] == " ":
        j += 1
    if j < len(s) and s[j] == "(":
        k = s.find(")", j)
        if k != -1:
            return k
    return -1


def break_points(line: str):
    """줄을 실제 렌더처럼 끊어 [(조각, 낱말중간이아닌지)] 반환."""
    s = line.strip()
    if not s:
        return [("", True)]
    marker = s[0] if s[0] in MARKER_X else None
    scale = NOTE_SCALE if marker == "*" else 1.0
    if marker:
        x = MARKER_X[marker] + MARKER_W[marker] * scale
        cont, bold_end, i = CONT_X[marker], _bold_span(s), 1
    else:
        x, cont, bold_end, i = CONT_X["□"], CONT_X["□"], -1, 0
    parts, seg_start = [], 0
    while i < len(s):
        ch = s[i]
        w = width(ch, i <= bold_end) * scale
        if ch == " ":              # 공백은 줄나눔을 유발하지 않는다(행말 공백 허용)
            x += w
            i += 1
            continue
        if x + w > R + EPS:
            parts.append((s[seg_start:i].rstrip(), s[i - 1] == " "))
            seg_start = i
            x = cont
        x += w
        i += 1
    parts.append((s[seg_start:].rstrip(), True))
    return parts


def seg_width(seg: str, marker: str, cont: bool = False) -> float:
    """조각 하나의 자연 렌더 폭(pt). cont=True 면 연속 줄(마커 없음)."""
    scale = NOTE_SCALE if marker == "*" else 1.0
    if cont:
        x, bold_end, start = 0.0, -1, 0
    else:
        x = MARKER_X[marker] + MARKER_W[marker] * scale - MARKER_X[marker]
        bold_end, start = _bold_span(seg), 1
    for i in range(start, len(seg)):
        x += width(seg[i], i <= bold_end) * scale
    return x


def fill_ratio(line: str):
    """[(조각, 채움률%)] — 마지막 줄이 얼마나 찼는지 본다.

    둘째 줄이 반만 차는 문장을 렌더 전에 걸러내는 용도. 마지막 줄은 왼쪽
    정렬이라 100% 는 원리상 나오지 않는다(어절이 딱 떨어져야 함) — 실측
    상한은 98% 안팎이고, 91% 미만이면 눈에 띄게 허전하다.
    """
    s = line.strip()
    if not s or s[0] not in MARKER_X:
        return []
    marker, parts = s[0], break_points(s)
    out, cap1 = [], R - MARKER_X[marker]
    cap2 = R - CONT_X[marker]
    for i, (seg, _) in enumerate(parts):
        cap = cap1 if i == 0 else cap2
        out.append((seg, round(seg_width(seg, marker, cont=bool(i)) / cap * 100, 1)))
    return out


def check(body: str):
    bad = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s[0] not in "□◦-·*" or "\t" in s:
            continue
        parts = break_points(s)
        if len(parts) == 1:
            continue
        for seg, clean in parts[:-1]:
            if not clean:
                bad.append((s, [p[0] for p in parts]))
                break
    return bad


# ── 분량 규격 ─────────────────────────────────────────────
# □ 는 한 줄(≤38자). ◦ 는 서술형이면 두 줄 꽉(66~70).
# ★260928 — V4 규격으로 맞췄다(□ 30~38자 · ◦ 66~70자).
#   종전 □ 두 줄(68~76) 허용을 뗐다 — 넘치는 내용은 □ 를 늘리지 않고 ◦ 로 내린다.
#   30자 미만 □ 은 경고로 올리지 않는다(확실한 것만 — 재는 도구가 보여 준다).
#   끝줄 채움 하한도 91 → 85: ◦ 66자는 끝줄 28/32(88%)라 91 이면 규격 안의 줄이 걸린다.
BOX_ONE_LINE_MAX = 38
DOT_TWO_LINE = (66, 70)
TAIL_FILL_MIN = 85.0        # 마지막 줄 채움률 하한(%) — 그 아래면 눈에 띄게 허전하다


def _skip(s: str) -> bool:
    """길이 규격을 따지지 않는 줄 — 일정(탭)·목록형(라벨 :)·참고·마커."""
    if "	" in s:
        return True
    if s.startswith("*"):
        return True
    if re.match(r"^\[(표|이미지|붙임)\s*\d+\]$", s):
        return True
    if " : " in s or s[1:].lstrip().startswith(":"):
        return True
    return False


def check_lines(lines, where: str = "본문"):
    """자수·어절 경계·끝줄 채움을 한꺼번에 본다. 경고 문자열 목록 반환.

    판정은 위 폭 모델(실측)로 하며, 렌더를 막지 않는다 — 사실만 남긴다.
    """
    warns = []
    for raw in (lines or []):
        s = (raw or "").strip()
        if not s or s[0] not in "□☐◦" or _skip(s):
            continue
        n = len(s)
        parts = break_points(s)
        rows = len(parts)
        if s[0] in "□☐":
            if n > BOX_ONE_LINE_MAX:
                warns.append(
                    f"[분량] {where} □ 가 {n}자다 — 한 줄({BOX_ONE_LINE_MAX}자 이내)로, "
                    f"넘치는 내용은 ◦ 로 내릴 것 ({s[:24]}…)")
        elif rows > 1 and not (DOT_TWO_LINE[0] <= n <= DOT_TWO_LINE[1]):
            warns.append(
                f"[분량] {where} ◦ 가 {n}자다 — 두 줄이면 "
                f"{DOT_TWO_LINE[0]}~{DOT_TWO_LINE[1]}자로 ({s[:24]}…)")
        if rows > 1:
            if not all(clean for _, clean in parts[:-1]):
                warns.append(f"[분량] {where}에 낱말이 줄 사이에서 쪼개졌다 — "
                             f"표현을 바꿔 어절 경계로 맞출 것 ({s[:24]}…)")
            fill = fill_ratio(s)
            if fill and fill[-1][1] < TAIL_FILL_MIN:
                warns.append(f"[분량] {where} 끝줄이 {fill[-1][1]:.0f}%만 찼다 — "
                             f"{TAIL_FILL_MIN:.0f}% 이상으로 ({s[:24]}…)")
    return warns
