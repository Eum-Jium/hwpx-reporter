# -*- coding: utf-8 -*-
"""제도 체계도 견본 — 모눈 표 하나로 그린다(기관 내규 이름·날짜는 가상이다).

구조:
  · 상자 하나 = **병합한 칸 하나 + 그 안의 문단 여러 개** (줄마다 행을 쓰면
    줄 간격이 행 높이에 묶여 원본보다 성겨진다 — 실측 15.7 vs 11.7pt)
  · 좌·우 두 열은 세로 리듬이 다르므로 **촘촘한 행(2.6mm)** 위에 mm 로 배치한다.
    행이 굵으면 한쪽 상자의 높이가 반대쪽 상자까지 부풀린다.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools", "verify"))
import _repo_path            # noqa: F401,E402  — 설치본 그림자 차단
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
from outdir import out_dir
import hwpx_skeleton as HS
import hwpx_core as C
from hwpx_core import linebreak as LB
from hwpx_core import tablespec as TS

# 정본은 **테두리로도 위계를 나눈다**(실측):
#   본 계열 상자 검정 0.15 · 곁 계열 상자 회색 0.12 · 강조 빨강 0.25 · 요약 띠 회색 0.12
BOX = "SOLID 0.15 #000000"        # 본 계열
BOX_SIDE = "SOLID 0.12 #808080"   # 곁 계열(정보보안·데이터) · 요약 띠
RED = "SOLID 0.25 #FF0000"        # 강조
BLUE = "DASH 0.3 #0000FF"
ORG = "DASH 0.12 #FF4D00"
GRN = "DASH 0.12 #1E7452"
LINE = "SOLID 0.12"

COLS, PAGE_W = 61, 48190
COLW = TS.col_widths(COLS, [1] * COLS, TS.GRID_MIN_COL_W, PAGE_W)

# 열 배치 — 정본 상자 폭 실측(mm)에 맞춘다. 열 하나 = 170/61 = 2.787mm.
#   고영향 59.2 · 좌하단 법령 58.0 · 우 법령 51.0 · 가이드라인 76.5 · 윤리 원칙 37.8
OL, OR = 0, 60            # 바깥 상자
LF0, LF1 = 1, 25          # 좌 묶음틀
LC0, LC1 = 2, 24          # 좌 상자 (23열 = 64.1mm)
RF0, RF1 = 27, 59         # 우 묶음틀
NC0, NC1 = 28, 45         # 우 법령 상자 (18열 = 50.2mm ↔ 정본 51.0)
WC0, WC1 = 28, 54         # 가이드라인 상자 (27열 = 75.3mm ↔ 정본 76.5)
EC0, EC1 = 47, 58         # 윤리 원칙 (12열 = 33.4mm). 법령 상자(~45)와
                          # **한 열 띄운다** — 붙으면 두 상자가 한 덩어리로 보인다
IC0, IC1 = LC0 + 1, LC1 - 1   # 그룹 안 상자 (21열 = 58.5mm ↔ 정본 58.0)

LS = 1.20                 # 줄 간격 120% — 정본 도해와 같다
FINE = 2.6                # 행 하나(mm)
PAD_MM = 0.6              # 상자 위아래 여유 — 정본 2줄 상자는 7.4mm 다

# 정본 실측(PDF 좌표)에서 **한 단씩 내린 값**. 두 열의 크기 체계가 다른 것은
# 그대로 둔다 — 본 계열(인공지능)이 곁 계열(정보보안·데이터)보다 한 단 크고,
# 그 차이가 위계를 만든다.
MAIN = {"title": 10, "date": 8, "head": 9, "item": 8, "tag": 7, "dots": 6}
SIDE = {"title": 9, "date": 7, "head": 9, "item": 8, "tag": 6, "dots": 6}

CELL_PAD = 620            # 칸 안여백 몫(≈2×283) — 여유는 SAFETY 로만 준다
SAFETY = 0.98             # 폭 모델이 실측과 ±2% 안에서 맞는다(정본 대조)
# 실무 규칙 — **장평은 95%까지, 자간은 -10까지**. 그 이상 조이면 읽기 나빠진다.
# 순서는 자간 먼저(글자 모양이 안 변한다), 그래도 모자라면 장평.
MIN_SPACING = -10
MIN_RATIO = 95

# ── 상자에 얹는 발령기관 표장 ─────────────────────────────────
# 정본은 상자마다 **오른쪽 아래 모서리**에 발령기관 표장을 얹는다(견본 실측:
# 정부 소관 법령 4개는 정부 문장, 기관 규정 7개는 기관 로고 — 모두 띄우기
# treatAsChar="0" 라 상자 안 글자를 밀지 않는다).
# 표시 크기도 정본 실측을 따른다 — 문장 4.29mm 높이 · 로고 3.65mm 높이.
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MARK = {"gov": (os.path.join(ASSETS, "mark_gov.png"), 4.29),
        "org": (os.path.join(ASSETS, "mark_org.png"), 3.65)}
MARK_INSET = 0.5          # 상자 안쪽 변에서 띄우는 거리(mm)
# 한/글이 실제로 그리는 행은 우리가 준 높이보다 조금 높다 — 모눈이 촘촘하면
# 행마다 바닥(칸 안여백×2 + 1pt)이 걸리기 때문이다. 열 너비는 그대로인데(판면
# 폭 170.1mm 가 그대로 나왔다) 세로만 늘어난다. 렌더에서 바깥 상자 높이를 재
# 모델과 비교한 값이다 — 121.9 / 114.2 (2026-08-19 chart.pdf 가로선 y 245.6→591.1).
ROW_STRETCH = 121.9 / 114.2

acc, merges, marks = {}, [], []


def rows_for(mm):
    return max(1, int(math.ceil(mm / FINE)))


def put(r, c, borders=None, **kw):
    d = acc.setdefault((r, c), {"r": r, "c": c})
    if borders:
        d.setdefault("borders", {}).update(borders)
    d.update(kw)


def span(r0, c0, r1, c1):
    if (r1, c1) != (r0, c0):
        merges.append({"r1": r0, "c1": c0, "r2": r1, "c2": c1})


# 자간 1 당 줄 폭이 0.93% 줄어든다 — 값을 바꿔 가며 렌더해 잰 값이고 -4~-20
# 구간에서 완벽히 선형이었다. 다만 **한 칸에 문단이 여러 개인 상자**에서는 그만큼
# 안 줄어서(0.69%/1) 실제로 접혔다 — 접힘이 사라지는 보정을 실측으로 찾아 1.4 를
# 곱해 둔다(1.3 부터 사라졌다). 계산은 항상 넉넉한 쪽으로 틀리게 두는 편이 낫다.
SPACING_STEP = 0.0093 / 1.4


def text_w(s, pt):
    return sum(LB.width(ch) for ch in s) / 0.7067 * (pt / 15.0) * 100


def fit(text, c0, c1, want):
    """(글자 크기, 자간, 장평). 실무 규칙대로 **자간 -10 · 장평 95** 까지만 조인다.

    크기를 줄이면 한 도해 안에서 글자가 널뛰어 위계가 무너지므로 크기는 마지막
    수단이다. 자간을 먼저 쓰는 이유는 글자 모양이 그대로이기 때문이다.
    """
    avail = (sum(COLW[c0:c1 + 1]) - CELL_PAD) * SAFETY
    pt = want
    while True:
        need = text_w(text, pt)
        if need <= avail:
            return pt, None, None
        short = 1 - avail / need
        spac = -math.ceil(short / SPACING_STEP)
        if spac >= MIN_SPACING:
            return pt, spac, None
        # 자간 하한까지 쓰고 남은 몫을 장평으로
        left = 1 - (avail / need) / (1 - SPACING_STEP * abs(MIN_SPACING))
        ratio = 100 - math.ceil(left * 100)
        if ratio >= MIN_RATIO:
            return pt, MIN_SPACING, ratio
        if pt <= 5.5:
            return pt, MIN_SPACING, MIN_RATIO
        pt -= 0.5


def box_specs(lines, c0, c1, align, roles=MAIN):
    specs, total = [], 0.0
    for item in lines:
        text, role = item[0], item[1]
        al = item[2] if len(item) > 2 else align
        pt, spac, ratio = fit(text, c0, c1, roles[role])
        spec = {"text": text, "size": pt, "align": al,
                "bold": role in ("title", "head")}
        if spac:
            spec["spacing"] = spac
        if ratio:
            spec["ratio"] = ratio
        specs.append(spec)
        total += pt * LS
    return specs, total / 2.835 + PAD_MM


def box(r0, c0, c1, lines, style=BOX, align="CENTER", roles=MAIN, extra=0,
        mark=None):
    """상자를 r0 부터 필요한 만큼의 행에 얹는다. 끝 행 번호를 돌려준다.

    mark 를 주면 그 상자의 **오른쪽 아래 모서리**에 발령기관 표장을 얹는다.
    자리는 행·열 번호로만 적어 두고, 실제 mm 는 행 높이가 다 정해진 뒤
    `mark_pics()` 가 계산한다 — 여기서 미리 재면 뒤에 행이 늘 때 어긋난다.
    """
    specs, mm = box_specs(lines, c0, c1, align, roles)
    r1 = r0 + rows_for(mm) - 1 + extra
    span(r0, c0, r1, c1)
    put(r0, c0, lines=specs, borders={"all": style})
    if mark:
        marks.append((r1, c1, mark))
    return r1


def frame(r0, r1, c0, c1, style, tag=None, tag_bg=None, tag_w=6, roles=SIDE,
          open_right=False):
    """점선 묶음틀. open_right 면 **오른쪽 변을 안 그린다** — 정본의 좌 상단
    묶음틀이 3면뿐이고 오른쪽이 열려 있다(연결선이 그리로 빠져나간다)."""
    if tag:
        span(r0, c0, r0, c1 - tag_w)
        put(r0, c0, borders={"top": style, "left": style})
        span(r0, c1 - tag_w + 1, r0, c1)
        put(r0, c1 - tag_w + 1, text=tag, borders={"top": style, "right": style},
            bg=tag_bg, color="#FFFFFF", bold=True, align="CENTER",
            size=fit(tag, c1 - tag_w + 1, c1, roles["tag"])[0])
    else:
        span(r0, c0, r0, c1)
        b = {"top": style, "left": style}
        if not open_right:
            b["right"] = style
        put(r0, c0, borders=b)
    span(r1, c0, r1, c1)
    b = {"bottom": style, "left": style}
    if not open_right:
        b["right"] = style
    put(r1, c0, borders=b)
    for r in range(r0 + 1, r1):
        put(r, c0, borders={"left": style})
        if not open_right:
            put(r, c1, borders={"right": style})


def blue_path(r_top, r_step, r_bot, step_c, tag, tag_bg, tag_w=5):
    """인공지능 묶음틀 — **계단(ㄱ자) 하나**로 그린다.

    정본은 이 묶음이 사각형이 아니다: 위는 전체 폭이고, 고영향 상자 아래에서
    오른쪽으로 꺾여 내려가 좌 하단(참고 내용)을 **바깥에 남긴다**. 점선 색이
    갈래를 뜻하므로(파랑=인공지능) 인공지능이 아닌 묶음까지 감싸면 뜻이 어긋난다.
    """
    st = BLUE
    # 위 변 — 오른쪽 끝에 이름표를 얹는다
    span(r_top, OL + 1, r_top, RF1 - tag_w)
    put(r_top, OL + 1, borders={"top": st, "left": st})
    span(r_top, RF1 - tag_w + 1, r_top, RF1)
    put(r_top, RF1 - tag_w + 1, text=tag, borders={"top": st, "right": st},
        bg=tag_bg, color="#FFFFFF", bold=True, align="CENTER",
        size=fit(tag, RF1 - tag_w + 1, RF1, MAIN["tag"])[0])
    # 이음매를 맞춘다 — 세로 변은 만나는 가로 변의 행까지 **포함**해서 긋는다.
    # 한 행이라도 모자라면 모서리가 벌어지고, 넘치면 꼬리가 삐져나온다.
    # 왼쪽 변: 계단 가로가 놓인 행(r_step+1)의 **위**에서 끝난다
    for r in range(r_top + 1, r_step + 1):
        put(r, OL + 1, borders={"left": st})
    # 계단 가로
    span(r_step + 1, OL + 1, r_step + 1, step_c)
    put(r_step + 1, OL + 1, borders={"top": st})   # 왼쪽은 긋지 않는다(꼬리 방지)
    # 계단 아래 세로 — 아래 변이 놓인 행(r_bot)까지 내려가야 모서리가 닫힌다
    for r in range(r_step + 1, r_bot + 1):
        put(r, step_c + 1, borders={"left": st})
    # 아래 변
    span(r_bot, step_c + 1, r_bot, RF1)
    # 오른쪽 변도 이 칸에 준다 — 병합 칸이라 (r_bot, RF1) 에 따로 못 붙인다
    put(r_bot, step_c + 1, borders={"bottom": st, "left": st, "right": st})
    # 오른쪽 변 — 역시 r_bot 까지
    for r in range(r_top + 1, r_bot + 1):
        put(r, RF1, borders={"right": st})


def vline(r0, r1, c):
    for r in range(r0, r1 + 1):
        put(r, c, borders={"left": LINE})


def hline(r, cols):
    for c in cols:
        put(r, c, borders={"top": LINE})


GAP = 1                 # 상자 사이 빈 행 수
TAGROW = 1              # 태그 행 수

# ── 좌측 열 (먼저 깐다) ───────────────────────────────────────────────
IMID = (IC0 + IC1) // 2
r_hi = box(2, LC0, LC1, [("※ 고영향 인공지능 가이드라인*", "head"),
                         ("· 투명성 확보 가이드라인", "item"),
                         ("· 인공지능 안전성 확보가이드라인", "item"),
                         ("· 고영향 인공지능 판단 가이드라인", "item"),
                         ("· 고영향 인공지능 사업자 책무 가이드라인", "item"),
                         ("· 인공지능 영향평가 가이드라인", "item"),
                         (" (’26.1, 과학기술정보통신부)", "item")],
           align="LEFT", mark="gov")
hline(3, range(LF1, RF0 + 1))          # 고영향 → 기본법 연결선


sec_top = r_hi + 4                     # 좌 묶음틀2 시작
tag1 = sec_top              # 파란 틀이 없으니 바로 시작한다
r_a = box(tag1 + TAGROW, IC0, IC1, [("「국가정보보안기본지침」", "title"),
                                    ("(’26.1, 국가정보원)", "date")], roles=SIDE,
          mark="gov")
vline(r_a + 1, r_a + 1, IMID)
r_b = box(r_a + 2, IC0, IC1, [("「정보보안 운영지침」", "title"),
                              ("(보안관리부, ’24.6 )", "date")], roles=SIDE,
          mark="org")
frame(tag1, r_b + 1, LC0, LC1, ORG, tag="정보보안", tag_bg="#FF4D00", tag_w=6)

tag2 = r_b + 5              # 정보보안 ↔ 데이터 사이(정본 7.2mm)
r_c = box(tag2 + TAGROW, IC0, IC1, [("「데이터기반행정 활성화에 관한 법률」", "title"),
                                    ("(행정안전부, ’25.5)", "date")], roles=SIDE,
          mark="gov")
vline(r_c + 1, r_c + 1, IMID)
r_d = box(r_c + 2, IC0, IC1, [("「데이터 운영지침」", "title"),
                              ("(데이터관리부, ’24.9)", "date")], roles=SIDE,
          mark="org")
frame(tag2, r_d + 1, LC0, LC1, GRN, tag="데이터", tag_bg="#1E7452", tag_w=5)
# 좌 하단에는 파란 틀을 두지 않는다 — **점선 색이 갈래를 뜻한다**.
# 파랑은 인공지능 몫(태그도 파랑)이라, 인공지능이 아닌 정보보안·데이터를
# 파란 틀로 묶으면 갈래 표시가 어긋난다. 주황·초록 틀이 이미 묶고 있다.

# ── 우측 열 ───────────────────────────────────────────────
# 좌측이 더 길면 그 차이를 우측 **간격에 나눠** 두 열의 끝을 맞춘다.
# 원본도 두 열이 같은 높이에서 끝난다 — 안 맞추면 우측 묶음틀 아래가 빈다.
MID = (NC0 + NC1) // 2
R_BLOCKS = [
    ([("「인공지능기본법」", "title"), ("(’26.1, 과학기술정보통신부)", "date")],
     NC0, NC1, BOX, "CENTER", "gov"),
    ([("「AI 운영규정」", "title"), ("(’24.3, 디지털전략부)", "date")],
     NC0, NC1, BOX, "CENTER", "org"),
    ([("「AI 운영규정 세부기준」", "title"), ("(～’24.12, 디지털전략부)", "date")],
     NC0, NC1, BOX, "CENTER", "org"),
    ([("※ 인공지능 공통 가이드라인", "head"),
      ("· AI 서비스 도입 절차(’24.5, 디지털전략부)", "item"),
      ("· AI 모델 개발 지침(’24.8, 기술연구원)", "item")],
     WC0, WC1, BOX, "LEFT", "org"),
    ([("※ 인공지능 세부 이용 가이드·매뉴얼", "head"),
      ("· 업무지원 챗봇 이용 안내(’24.7, 운영관리부)", "item"),
      ("· 설비 예측정비 모델 운영 지침(’24.11, 시설관리부)", "item"),
      ("· 문서 요약 도구 이용 안내(’24.4, 정보시스템부)", "item"),
      ("· 생성형 AI 업무 활용 사례집(’24.10, 기술연구원)", "item"),
      ("· 연구 과제의 생성형 AI 활용 기준", "item"),
      ("  (’24.10, 연구기획부)", "item"),
      ("⋮", "dots", "CENTER")], WC0, WC1, BOX, "LEFT", "org"),
]
_sizes = [rows_for(box_specs(l, a, b, al, MAIN)[1])
          for l, a, b, _s, al, _m in R_BLOCKS]
_left_end = r_d + 3
_slack = max(0, (_left_end - 2 + 1) - sum(_sizes) - 1)
_ngap = len(R_BLOCKS) - 1
_gaps = [max(GAP, _slack // _ngap + (1 if i < _slack % _ngap else 0))
         for i in range(_ngap)]

_r = 2
_ends, r_eth = [], None
for i, (lines, a, b, stl, al, mk) in enumerate(R_BLOCKS):
    # 마지막(세부 이용) 상자는 ⋮ 아래에 한 행을 더 둔다
    _ends.append(box(_r, a, b, lines, style=stl, align=al, mark=mk,
                     extra=1 if i == len(R_BLOCKS) - 1 else 0))
    if i == 1:
        # 윤리 원칙 — 운영규정 오른쪽. 열이 법령 상자와 한 칸 겹치므로
        # **행이 겹치지 않게** 다음 상자를 그 아래로 민다(겹치면 병합이 깨진다).
        r_eth = box(_ends[-1] + 1, EC0, EC1,
                    [("「AI 윤리 원칙」", "title"),
                     ("(～’24.9, 디지털전략부)", "date")], style=RED, mark="org")
        hline(_ends[-1] + 2, range(MID, EC0))
    if i < _ngap:
        _r = _ends[-1] + _gaps[i] + 1
r_base, r_rule, r_std, r_com, r_det = _ends

# 상자 사이 세로 연결선 (법령 셋 사이)
vline(r_base + 1, r_base + _gaps[0], MID)
vline(r_rule + 1, r_std - 1, MID)

# 우측 묶음틀은 두 열 중 아래쪽 끝에 맞춘다
# 묶음틀 아래 변은 마지막 상자보다 한 행 아래에 둔다(병합이 겹치면 안 된다)
bottom = max(r_det, r_eth, r_d + 3) + 1
blue_path(1, r_hi + 1, bottom, RF0 - 2, "인공지능", "#0000FF")

# ── 하단 요약 띠 · 각주 ───────────────────────────────────
BAND = "AI 활용을 위한 내부 기준 체계 정비"
band_pt, band_spac, band_ratio = fit(BAND, 1, 59, 13)
band_r0 = bottom + 2
band_r1 = band_r0 + rows_for(band_pt * LS / 2.835 + 2.4) - 1
span(band_r0, 1, band_r1, 59)
put(band_r0, 1, text=BAND, borders={"all": BOX_SIDE}, bg="#D9E1F2", bold=True,
    align="CENTER", size=band_pt,
    **({"spacing": band_spac} if band_spac else {}),
    **({"ratio": band_ratio} if band_ratio else {}))
frame(0, band_r1 + 1, OL, OR, BOX)

NOTE = "*고영향 AI 는 정부 가이드라인을 따른다"
note_r = band_r1 + 2
span(note_r, 0, note_r, 34)
note_pt, note_spac, note_ratio = fit(NOTE, 0, 34, 12)
put(note_r, 0, text=NOTE, align="LEFT", size=note_pt,
    **({"spacing": note_spac} if note_spac else {}),
    **({"ratio": note_ratio} if note_ratio else {}))

ROWS = note_r + 1
HEIGHTS = [FINE] * ROWS
HEIGHTS[0] = HEIGHTS[band_r1 + 1] = 1.2         # 바깥 상자 변
HEIGHTS[note_r] = 4.4


def mark_pics():
    """기록해 둔 표장 자리를 mm 좌표로 옮긴다 — 상자 오른쪽 아래 모서리 안쪽.

    x 는 **판면 왼쪽**, y 는 **표 윗변**이 원점이다(renderer 가 그 기준으로
    띄운다). 도해는 표가 판면 왼끝에서 시작하므로 둘이 같은 원점이다.
    가로 위치는 열 너비의 누적, 세로는 행 높이의 누적으로 정확히 나온다 —
    지면에서 재 보고 맞추는 것이 아니라 표를 그린 그 수치로 계산한다.
    """
    xs = [0.0]
    for w in COLW:
        xs.append(xs[-1] + w / TS.HWPUNIT_PER_MM)
    ys = [0.0]
    for h in HEIGHTS:
        ys.append(ys[-1] + h)
    out = []
    for r1, c1, kind in marks:
        path, h_mm = MARK[kind]
        # 원본 비율에서 가로 크기를 얻는다(렌더러가 같은 계산을 하지만 자리를
        # 잡으려면 여기서도 알아야 한다)
        px_w, px_h = C.bindata.image_size(open(path, "rb").read())
        w_mm = h_mm * px_w / px_h
        out.append({"path": path, "height_mm": h_mm,
                    "x_mm": round(xs[c1 + 1] - w_mm - MARK_INSET, 2),
                    "y_mm": round(ys[r1 + 1] * ROW_STRETCH - h_mm - MARK_INSET, 2)})
    return out


PICS = mark_pics()
print("표장 %d개 — %s" % (len(PICS), ", ".join(
    "(%.1f, %.1f)" % (p["x_mm"], p["y_mm"]) for p in PICS)))

BODY = chr(10).join([
    "1. 추진배경", " □ AI 관련 기준 체계(견본)", "[표1]",
    "2. 주요내용", " □ 체계도를 모눈 표 하나로 재현",
    "3. 추진방안", " □ 상자와 선을 칸 테두리로 구성",
    "4. 향후계획", " □ 추진 일정",
    "  ◦ 확인\t’26. 8. 18.", "  ◦ 반영\t’26. 8. 19.", "  ◦ 정리\t’26. 8. 20.",
])

res = HS.render("plan", {"title": "AI 관련 기준 체계(견본)"},
                output_dir=out_dir(), filename="chart", body=BODY,
                tables=[{"grid": {"rows": ROWS, "cols": COLS},
                         "row_heights": HEIGHTS, "merges": merges,
                         "cells": list(acc.values()), "pics": PICS}])
print(res["status"], res["path"], "· 행", ROWS)
for w in res["warnings"] + (res.get("body_result") or {}).get("warnings", []):
    print("  WARN:", w)
