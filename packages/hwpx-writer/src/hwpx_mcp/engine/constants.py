"""
HWPX 엔진 상수.

kor_hwpx_generator/hwpx_renderer.py + rebuild_template.py 에서 이식한
실측 상수 및 공공기관 표준서식 기본값.
"""

# ── 단위 변환 ────────────────────────────────────────────
HWPUNIT_PER_MM = 283.46          # 1mm = 283.46 HWPUNIT
HWPUNIT_PER_PT = 100             # 1pt = 100 (charPr height 단위)


def mm(value: float) -> int:
    """밀리미터 → HWPUNIT"""
    return int(value * HWPUNIT_PER_MM)


def pt_to_hwp(pt: float) -> int:
    """포인트 → charPr height 단위 (1/100pt)"""
    return int(pt * HWPUNIT_PER_PT)


# ── 공공기관 표준서식 (실측 template 기준) ────────────────
# 페이지 여백 (mm)
PAGE_MARGIN = {
    "top": 15, "bottom": 15,
    "left": 23, "right": 23,
    "header": 10, "footer": 10,
}

# 폰트
FONT_TITLE = "HY헤드라인M"       # 문서 제목 23pt / 중간제목 16pt
FONT_BODY = "휴먼명조"           # 본문 15pt
FONT_REF = "한양중고딕"          # 참고/주석 13pt
FONT_TABLE = "맑은 고딕"         # 표 본문 12pt

# 한컴 전용(HFT) 형식으로 선언할 글꼴 — 관례(한/글 작성 시 HFT 선택).
# 맑은 고딕 등 Windows 폰트는 HFT 버전이 없으므로 TTF 유지.
HFT_FONTS = {"휴먼명조", "한양중고딕", "한양견고딕"}

# 폰트 크기 (pt)
SIZE_DOC_TITLE = 23             # 정본 양식 제목 실측 23pt
SIZE_HEADING = 16               # 중간제목(Ⅰ,Ⅱ) / 소제목(1.,2.)
SIZE_BODY = 15
SIZE_REF = 13
SIZE_TABLE = 12

# 필수 폰트 (config.py 폰트 체크에서 사용)
REQUIRED_FONTS = [FONT_TITLE, FONT_BODY, FONT_REF, FONT_TABLE]

# 줄간격 (%)
LINE_SPACING_BODY = 160         # 정본(skeleton) 실측 160% — 취지박스만 150
LINE_SPACING_TITLE = 130

# ── 내어쓰기 intent 상수 (표준서식 스켈레톤 실측, 문단여백 스케일 1pt=200) ──
# 표준서식 스켈레톤(정본 양식)의 한글 '문단모양-내어쓰기' 실측값과 동일 기준:
# □ 30.7pt · ◦ 38.6pt · - 36.5pt · * 33.8pt  (hwpx-skeleton renderer._HANG_PT)
# 왼쪽여백(left)은 0 으로 두고 intent 음수만 쓴다 — 첫 줄은 여백선, 둘째 줄부터
# |intent| 만큼 들여져 텍스트 시작과 정렬된다.
HANG_INTENT = {
    "□": -6140,
    "◦": -7720,     # ◦ = U+25E6 (WHITE BULLET, 반드시 이 문자)
    "-": -7300,
    "·": -7300,     # 실측치 없음 — 폭이 유사한 "-" 값 준용
    "*": -6760,
}

# 항목부호 계층 (짧은 문서)
BULLET_MARKERS = {1: "□", 2: "◦", 3: "-", 4: "·", 5: "*"}

# 항목부호별 앞칸 — 스켈레톤 규칙과 동일하게 '공백 문자'로 넣는다
# (문단 들여쓰기 아님. hwpx-skeleton style.LEVEL_SPEC lead 와 단일 기준:
#  헤딩 0 · □ 1 · ◦ 2 · - 3 · · 4 · * 4)
LEAD_SPACES = {"□": 1, "◦": 2, "-": 3, "·": 4, "*": 4}

# ── 줄머리 기호 감지 (hwpx_renderer.py:78-94 _detect_level) ──
# prefix → (indent_spaces, font, size, hang_marker)
#   Ⅰ~ⅴ  : HY헤드라인M 16pt, 내어쓰기 없음(로마숫자 heading)
#   □/☐/ㅁ: 휴먼명조 15pt, □ 내어쓰기 (☐=U+2610 표준서식 원본 → □ 로 정규화)
#   ◦/○/ㅇ: 휴먼명조 15pt, ◦ 내어쓰기
#   -     : 휴먼명조 15pt, - 내어쓰기
#   */※   : 한양중고딕 13pt, * 내어쓰기 (참고내용)
ROMAN_CHARS = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅰⅱⅲⅳⅴ"

# ── 표 열너비 알고리즘 (hwpx_renderer.py:192-219) ──
TABLE_WIDTH = 43922             # 고정 표 폭 (HWPUNIT) — A4 콘텐츠폭 기준
COL_MIN_WIDTH = 2000            # 열 최소 폭 (HWPUNIT)
CJK_CODEPOINT_THRESHOLD = 0x3000  # ord > 0x3000 → 전각(2배 가중)


def char_weight(s: str) -> int:
    """한글/한자 등 전각 문자 2배 가중"""
    return sum(2 if ord(c) > CJK_CODEPOINT_THRESHOLD else 1 for c in str(s))


def calc_col_widths(headers, rows, table_width: int = TABLE_WIDTH) -> list:
    """
    각 열의 최대 글자수(전각 2배 가중) 기준 비례 배분.
    hwpx_renderer.py:_calc_col_widths 이식.
    """
    col_count = len(headers) if headers else (len(rows[0]) if rows else 0)
    if col_count == 0:
        return []

    max_weights = []
    for ci in range(col_count):
        weights = [char_weight(headers[ci])] if headers and ci < len(headers) else [0]
        for row in rows:
            if ci < len(row):
                weights.append(char_weight(str(row[ci])))
        max_weights.append(max(weights) + 2)   # 여백 여유

    total = sum(max_weights) or 1
    widths = [max(COL_MIN_WIDTH, int(table_width * w / total)) for w in max_weights]
    diff = table_width - sum(widths)
    widths[-1] = max(COL_MIN_WIDTH, widths[-1] + diff)
    return widths


# ── 16-상태 표 테두리 스펙 (rebuild_template.py:16-64) ──
# 테두리 선 스타일 (type, width)
BORDER_NONE = ("NONE", "0.12 mm")
BORDER_S12 = ("SOLID", "0.12 mm")    # 얇은 내부 격자
BORDER_S30 = ("SOLID", "0.3 mm")     # 굵은 외곽
BORDER_DS = ("DOUBLE_SLIM", "0.7 mm")  # 이중선 (헤더 밑줄)
HEADER_FILL = "#F2F2F2"              # 헤더행 배경

# 각 (행위치, 열위치) → (left, right, top, bottom, fill) 면별 스펙
# 행위치: header / first / mid / last / only / hdr_only
# 열위치: nl(비마지막) / l(마지막)
#   left  : 비마지막열=NONE, 마지막열=S12 (인접 셀 공유선 회피, 좌우 외곽 없음)
#   right : 비마지막열=S12,  마지막열=NONE
BORDER_STATES = {
    ("header", "nl"): (BORDER_NONE, BORDER_S12, BORDER_S30, BORDER_DS, HEADER_FILL),
    ("header", "l"):  (BORDER_S12, BORDER_NONE, BORDER_S30, BORDER_DS, HEADER_FILL),
    ("first", "nl"):  (BORDER_NONE, BORDER_S12, BORDER_DS, BORDER_S12, None),
    ("first", "l"):   (BORDER_S12, BORDER_NONE, BORDER_DS, BORDER_S12, None),
    ("mid", "nl"):    (BORDER_NONE, BORDER_S12, BORDER_S12, BORDER_S12, None),
    ("mid", "l"):     (BORDER_S12, BORDER_NONE, BORDER_S12, BORDER_S12, None),
    ("last", "nl"):   (BORDER_NONE, BORDER_S12, BORDER_S12, BORDER_S30, None),
    ("last", "l"):    (BORDER_S12, BORDER_NONE, BORDER_S12, BORDER_S30, None),
    ("only", "nl"):   (BORDER_NONE, BORDER_S12, BORDER_DS, BORDER_S30, None),
    ("only", "l"):    (BORDER_S12, BORDER_NONE, BORDER_DS, BORDER_S30, None),
    ("hdr_only", "nl"): (BORDER_NONE, BORDER_S12, BORDER_S30, BORDER_S30, HEADER_FILL),
    ("hdr_only", "l"):  (BORDER_S12, BORDER_NONE, BORDER_S30, BORDER_S30, HEADER_FILL),
}
