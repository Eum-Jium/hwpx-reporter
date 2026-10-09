# -*- coding: utf-8 -*-
"""표 규격(폭·행 높이·열 배분) — 두 생성 경로의 단일 기준.

skeleton(모드 A)과 스킬 모드 B(hwpx_full)가 같은 표를 그려야 한다. 종전에는
각자 하드코딩해 **전체 폭 46063 vs 47531, 첫 열 10231 vs 9099** 로 갈렸고,
그 결과 "첫 열 7자" 같은 작성 규칙이 모드 B 에서는 6자쯤에서 깨졌다.
모드 B 는 lxml 이 없는 환경의 폴백이라 평소엔 드러나지 않지만, 정작 폴백이
작동하는 순간 같은 본문이 다른 모양으로 나온다(08-15 감사).

**stdlib 만 쓴다** — gaps.py·markers.py 와 같은 이유(모드 B 가 파일째 적재한다).

값의 근거:
  TOTAL_W  표 전체 너비 162.5mm — 본문폭보다 조금 좁게 잡아 좌우 여백을 준다.
           1mm = 7200/25.4 HWPUNIT → 162.5mm = 46063.
  FIRST_W  첫 열 기본폭. 13pt 기준 **7자**가 한 줄에 들어간다(실무에서 넓힌 값).
           나머지 열은 균등 배분이며 13pt 기준 13자 안팎. 항목명이 이보다 길면
           first_col_w 가 내용에 맞춰 넓힌다 — 고정으로 두면 접힌다(08-18).
  ROW_H    행 높이. 셀 글자가 13pt 라 여백이 넉넉했고, 쪽을 맞출 때 실무에서
           먼저 줄이는 자리라 2148 → 1900 으로 한 단 낮췄다(08-15).
           1900 아래로는 13pt 글자에 여백이 빠듯해진다.
"""

TOTAL_W = 46063         # 표 전체 너비(162.5mm)
FIRST_W = 10231         # 첫 열 기본폭이자 **하한**(13pt 기준 7자).
                        # 더 긴 항목명은 first_col_w 가 내용에 맞춰 넓힌다
ROW_H = 1900            # 데이터 행 높이
LEAD_SPACES = 3         # 표 앞 들여쓰기(공백 칸 수) — 실무 확인: 1칸 → 3칸

# 이미지자리(모드 B 전용 값이지만 폭은 표와 같은 기준을 써야 좌우가 맞는다)
IMG_CELL_H = 17865      # 이미지칸 높이
IMG_CAPTION_H = 2385    # 캡션칸 높이


# 길이 척도. **글자 크기·문단 여백과는 척도가 다르다**(units.py 의 이중 척도 주석
# 참조) — 표·칸의 폭과 높이는 이 환산을 쓴다. 162.5mm → 46063 이 TOTAL_W 다.
HWPUNIT_PER_MM = 7200 / 25.4        # 283.4645…


def mm(value) -> int:
    """밀리미터 → HWPUNIT(길이)."""
    return int(round(float(value) * HWPUNIT_PER_MM))


# ── 첫 열은 내용에 맞춰 넓힌다 ─────────────────────────────────────────
# FIRST_W(7자)는 **기본값이자 하한**이다. 고정으로만 쓰던 동안 `야간 순찰(회/월)`
# (9자)처럼 조금 긴 항목명이 두 줄로 접혀 행이 두 배로 높아졌다(08-18 실물).
# 그렇다고 무한정 넓히면 나머지 열이 좁아져 본문이 접힌다 — 전체의 42%가 상한이고,
# 나머지 열이 min_w 아래로 내려가는 배분도 막는다. 전체너비는 어느 쪽이든 보존된다.
CHAR_W_13PT = 1300      # 13pt 전각 한 자의 폭. 반각(영숫자·괄호)은 절반으로 센다
CELL_PAD = 1100         # 칸 좌우 여백 — FIRST_W(7자)에서 역산한 값
FIRST_MAX_RATIO = 0.42  # 첫 열이 차지할 수 있는 최대 비율


def text_w(s, char_w: int = CHAR_W_13PT) -> int:
    """글자열의 표시 폭(HWPUNIT) — 전각은 char_w, 반각은 그 절반으로 센다."""
    import unicodedata
    return sum(char_w if unicodedata.east_asian_width(ch) in "WF" else char_w // 2
               for ch in (str(s) if s is not None else ""))


def first_col_w(texts, total: int = None, min_w: int = None, n: int = 2) -> int:
    """첫 열에 들어갈 글자들을 받아 그 열의 폭을 정한다.

    texts: 첫 열 칸의 글자 목록(헤더 첫 칸 + 각 행의 첫 칸).
    반환값은 언제나 FIRST_W 이상이다 — 짧은 항목명만 있는 표는 종전과 같은 폭이
    나온다(정본 표 모양이 문서마다 달라지지 않게).
    """
    W = TOTAL_W if total is None else int(total)
    floor = MIN_COL_W if min_w is None else int(min_w)
    need = max([text_w(t) for t in (texts or [])] or [0]) + CELL_PAD
    # 상한 둘: 전체의 42% · 나머지 열이 floor 를 지킬 수 있는 폭.
    cap = min(int(W * FIRST_MAX_RATIO), W - floor * max(1, int(n) - 1))
    return max(FIRST_W, min(need, cap))


# 열 하나의 최소 너비. 13pt 글자 한 자(1300)에 셀 좌우 여백을 더한 값이다 —
# 이보다 좁으면 글자가 셀을 넘거나 세로로 한 자씩 떨어진다.
MIN_COL_W = 2000

# 도해(모눈)용 최소 너비. 한/글이 강제하는 하한이다 —
#     최소 열 너비 = 칸 안여백 × 2 + 283
# 이라는 것을 실측했다(08-18, 안여백 283/141/0 으로 61열 표를 찍어 대조:
# 283 이면 선언 790 이 849 로 밀려 표가 판면 밖으로 나갔고, 141·0 이면 790 이
# 그대로 살았다). 그래서 **여백을 0 까지 낮췄을 때의 하한**이 이 값이고,
# 여백은 renderer 가 모눈 촘촘함에 맞춰 이 식대로 자동으로 낮춘다.
GRID_MIN_COL_W = 283                # ≈1mm (여백 0 일 때의 하한)
GRID_MIN_CONTENT = 283              # 위 식의 상수항

# 도해 빈 칸의 글자 크기(pt). **이 값이 없으면 모눈이 성립하지 않는다** —
# 한/글은 칸마다 그 칸 글꼴 한 자가 들어갈 자리를 최소 너비로 잡는다. 빈 칸이
# 본문 13pt 를 물려받으면 44열 표가 162.5mm 로 안 들어가 지면 밖(228mm)까지
# 늘어난다(08-18 실측). 정본 체계도의 빈 칸은 1.0~1.5pt 였다 — 그래서 81열이
# 한 쪽에 들어간다. 행 높이가 들쭉날쭉해지는 것도 같은 원인이다.
GRID_EMPTY_PT = 1.0

# 도해 칸의 안여백(HWPUNIT, 네 변 공통) **상한**. 1mm — 정본과 같은 값이다.
# 모눈이 촘촘해 열이 좁으면 renderer 가 GRID_MIN_CONTENT 식에 맞춰 더 낮춘다.
# 빈 칸 글꼴을 1pt 로 낮춰도 칸 안여백이 **기본값(-1)** 이면 한/글이 자기 기본
# 여백을 쓰는데, 그 값이 커서 열마다 최소 13pt 폭이 잡힌다 — 44열 표가 지면
# 밖까지 늘어난 진짜 원인이었다(08-18). 정본 체계도는 네 변 모두 283 을 명시하고
# hasMargin="1" 을 켜 둔다. 그래서 849 폭 칸이 성립한다.
GRID_CELL_MARGIN = 283

# 도해 칸의 줄 간격(%). 양식 본문 표는 160% 인데, 정본 체계도의 글자 칸은
# **120%** 를 쓴다(실측: 110~140, 최빈 120). 160 을 물려받으면 같은 10pt 줄이
# 15.7pt 자리를 차지해 원본(11.7pt)보다 34% 성겨진다 — 도해가 세로로 길어지는
# 가장 큰 원인이었다.
GRID_LINE_SPACING = 120

# 행 높이 하한. 정본 체계도의 가장 낮은 칸이 666(≈2.35mm)이었다 — 그보다 낮게도
# 그릴 수 있게 두되, 0 에 가까운 값은 막는다(한/글이 행을 뭉갠다).
MIN_ROW_H = 200


def col_widths(n: int, ratios=None, min_w: int = None, total: int = None,
               first_texts=None):
    """열 n 개의 너비 목록. 합은 언제나 표 전체 너비(total, 기본 TOTAL_W).

    ratios 없음 = 종전 배분(첫 열 고정 + 나머지 균등).
    ratios 있음 = 그 비율대로 나눈다(첫 열 고정폭을 쓰지 않는다).

    비율로만 받는 이유: 라벨-값 표처럼 첫 열이 좁고 끝 열만 넓어야 하는 표가
    실무에 흔한데 균등 배분으로는 못 만든다. 그렇다고 폭을 HWPUNIT 로 직접
    받으면 합이 TOTAL_W 를 벗어나 **같은 문서 안에서 표마다 좌우가 어긋난다**
    (표 폭을 고정한 이유가 그것이다). 비율만 받고 합 보존은 여기서 한다.

    min_w: 열 하나의 최소 너비(기본 MIN_COL_W). 도해 모드는 GRID_MIN_COL_W 를
        준다 — 모눈 칸은 글자가 아니라 선을 놓는 자리라 훨씬 좁아도 된다.
    total: 표 전체 너비(기본 TOTAL_W). 도해는 본문 표보다 넓은 **판면 폭**을
        쓴다 — 정본 체계도가 그렇고, 붙임 표제도 같은 이유로 더 넓다.
    first_texts: 첫 열에 들어갈 글자 목록. 주면 첫 열을 그 내용에 맞춰 넓힌다
        (first_col_w 참조). 안 주면 종전대로 FIRST_W 고정이다. ratios 를 준
        표에는 쓰이지 않는다 — 그쪽은 비율이 곧 지시다.

    잘못된 ratios 는 ValueError — 호출부가 잡아 기본 배분으로 떨어뜨리고
    사유를 warnings 에 남긴다. 표가 통째로 빠지는 것보다 낫다.
    """
    floor = MIN_COL_W if min_w is None else int(min_w)
    W = TOTAL_W if total is None else int(total)
    if ratios is None:
        if n <= 1:
            return [W]
        first = (FIRST_W if first_texts is None
                 else first_col_w(first_texts, W, floor, n))
        rest = (W - first) // (n - 1)
        widths = [first] + [rest] * (n - 1)
        widths[-1] += W - sum(widths)            # 합 보정(전체너비 보존)
        return widths

    vals = list(ratios)
    if len(vals) != n:
        raise ValueError(f"열 비율 개수({len(vals)})가 열 수({n})와 다르다")
    out = []
    for v in vals:
        # bool 은 int 의 하위형이라 따로 막는다(True 가 1 로 새어 들어온다)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ValueError(f"열 비율은 0 보다 큰 수여야 한다: {v!r}")
        out.append(float(v))
    # 합 보정은 **나머지가 큰 열부터** 1씩 나눠 준다(최대잉여법). 종전처럼 끝 열에
    # 몰아 주면 40열 모눈에서 끝 칸만 23 넓어져 오른쪽 격자가 어긋난다.
    ssum = sum(out)
    exact = [W * v / ssum for v in out]
    widths = [int(x) for x in exact]
    order = sorted(range(n), key=lambda i: exact[i] - widths[i], reverse=True)
    for i in range(W - sum(widths)):
        widths[order[i % n]] += 1
    narrow = [i for i, w in enumerate(widths) if w < floor]
    if narrow:
        raise ValueError(
            f"열 비율이 {[i + 1 for i in narrow]}번 열을 너무 좁게 만든다 "
            f"(최소 {floor}, 나온 값 {[widths[i] for i in narrow]})")
    return widths

# ── 붙임 별지 표제 ────────────────────────────────────────
# 본문 뒤에 붙는 별지의 머리다. 문단이 아니라 **1행 3열 표**로 만든다 —
# [붙임 N] 상자 · 사이 빈칸 · 제목. 정본 실측(08-18, 요청서 견본):
#   6068 / 848 / 40989 (합 47905). 본문 표(TOTAL_W)보다 넓다 — 별지 머리는
#   본문 폭이 아니라 판면 폭에 맞춰 놓는 관례다.
ATTACH_CAP_W = (6068, 848, 40989)
ATTACH_CAP_TOTAL_W = sum(ATTACH_CAP_W)
ATTACH_CAP_H = 2500        # 표제 행 높이

# 본문 끝 붙임 목록: `붙임  1. 제목.` 뒤 줄은 6칸 들여쓰기(style.py 규정과 같은 값).
ATTACH_LIST_INDENT = 6
