# -*- coding: utf-8 -*-
"""쪽 분량 — 한 쪽에 무엇이 얼마나 들어가는지의 단일 기준.

지금까지 이 수치는 SKILL.md·지침·format_spec 의 산문에만 있었다. 산문은 사람이
읽고 잊는다 — 실제로 붙임 별지를 만들면서 "서식 한 장짜리는 비어도 정상"이라고
예외를 적었고, 그러자 견본 자체가 아래를 3분의 2 비운 채로 나왔다. 규칙을 코드로
내려 **본문이든 별지든 같은 잣대**로 보게 한다.

값은 전부 A4 정본 실측(08-18 PDF 좌표):
    본문 영역 세로 700.1pt (위 70.9 ~ 아래 771.0) = 24pt 줄로 29줄
    본문 줄 24pt · 표 행 19pt · 각주 줄 21pt · 붙임 표제 35pt
    마지막 쪽 아래 여백은 5줄(129pt) 안팎까지 정상

**stdlib 만 쓴다** — markers.py·gaps.py 와 같은 이유(모드 B 가 파일째 적재한다).
"""
import re

# 본문 줄에 놓는 이미지자리 마커 — renderer 의 _IMG_MARK 와 같은 모양이다.
# 여기서 다시 세우는 이유는 core 가 skeleton 을 import 하지 않기 때문이고,
# 모양이 갈리지 않게 test_volume.py 가 두 정규식을 맞대어 본다.
_IMG_MARK = re.compile(r"^\[\s*(?:이미지|그림)\s*(\d+)\s*\]$")

PAGE_BODY_PT = 700.1        # 한 쪽 본문 영역 세로
LINE_PT = 24.0              # 본문 줄
TABLE_ROW_PT = 19.0         # 표 행
NOTE_PT = 21.0              # 각주(*) 줄
ATTACH_CAPTION_PT = 35.0    # 붙임 표제(1행 3열 표)
TAIL_MARGIN_MAX_PT = 129.0  # 마지막 쪽 아래 여백 상한

LINES_PER_PAGE = (29, 32)   # 한 쪽에 들어가는 줄 수(24pt 기준)

# ── 이미지자리 ────────────────────────────────────────────────
# 종전에는 이 값이 tools/README 산문에 "이미지자리 1개 ≈ 170pt" 로만 있었고
# 코드에는 아예 없었다 — 그림이 든 문서의 분량을 볼 잣대가 없었다는 뜻이다.
# 2026-08-19 PDF 좌표로 다시 재니 **170 이 아니라 202.5** 였다(표 가로선 y
# 355.5 → 534.0 = 178.5pt 그림칸 + 캡션칸 23.85pt). 산문에 적힌 값이 그동안
# 아무 검사도 안 거쳤던 것이다.
#
# 그림칸 높이는 이제 **실물 그림 높이를 따라간다**(tablespec.IMG_CELL_H 는
# 자리표일 때의 값이다). 같은 렌더에서 20mm 로 넣은 그림의 칸이 62.3pt 로
# 나왔고 모델값(20mm + 안여백 566 HWPUNIT = 62.35pt)과 0.05pt 안에서 맞았다.
IMG_CAPTION_PT = 23.85      # 캡션칸 (tablespec.IMG_CAPTION_H 2385)
IMG_PAD_PT = 5.66           # 그림 위아래 안여백 몫 (renderer.IMG_PAD_H 566)
IMG_PLACEHOLDER_PT = 178.65  # 자리표 그림칸 (tablespec.IMG_CELL_H 17865)
IMG_SLOT_PT = IMG_PLACEHOLDER_PT + IMG_CAPTION_PT      # 자리표 한 개 = 202.5


def image_slot_pt(height_mm=None) -> float:
    """이미지자리 한 개가 지면에서 먹는 높이(pt).

    height_mm 을 주면 그 높이의 그림이 든 칸으로, 안 주면 자리표 칸으로 센다.
    실물이 들어가면 칸이 그림에 맞춰 줄어들므로 분량도 그만큼 달라진다 —
    자리표 기준으로만 세면 로고 하나 넣은 쪽을 '넘쳤다'고 잘못 본다.
    """
    if height_mm is None:
        return IMG_SLOT_PT
    return float(height_mm) / 25.4 * 72 + IMG_PAD_PT + IMG_CAPTION_PT


def images_pt(images) -> float:
    """이미지자리 목록이 먹는 높이 합계(pt).

    한 자리에 칸이 여럿이어도 가로로 나란히 서므로 높이는 **가장 큰 그림 하나**
    분이다 — 개수로 곱하지 않는다.
    """
    total = 0.0
    for im in (images or []):
        if not isinstance(im, dict):
            continue
        total += image_slot_pt(im.get("height_mm"))
    return total


def filled_min_pt(page_body_pt: float = PAGE_BODY_PT) -> float:
    """한 쪽을 '채웠다'고 볼 최소 높이 — 아래 여백이 상한 이내가 되는 지점."""
    return page_body_pt - TAIL_MARGIN_MAX_PT


def height_bounds(lines, tables=None, caption: bool = False, images=None):
    """(최소, 최대) 높이 추정 pt.

    줄이 렌더에서 한 줄이 될지 두 줄이 될지는 폭 계산을 해야 알 수 있고, 그
    모델은 이 모듈이 들 수 없다(stdlib 전용). 대신 **한 줄~두 줄 사이**로 범위를
    준다 — 판정은 이 범위의 한쪽만 쓰는 쪽이 안전하다(아래 fills_page 주석 참조).
    """
    text, notes = 0, 0
    for raw in (lines or []):
        s = (raw or "").strip()
        if not s:
            continue
        if s[0] == "*":
            notes += 1
        else:
            text += 1
    rows = 0
    for t in (tables or []):
        if not isinstance(t, dict):
            continue
        rows += (1 if t.get("headers") else 0) + len(t.get("rows") or [])

    fixed = rows * TABLE_ROW_PT + notes * NOTE_PT + images_pt(images)
    if caption:
        fixed += ATTACH_CAPTION_PT
    # 본문의 '[이미지1]' 줄은 그 자리에 이미지자리가 들어간다는 표시일 뿐 한 줄을
    # 먹지 않는다 — 높이는 위에서 이미 셌으므로 줄에서 뺀다. **센 만큼만** 뺀다:
    # images 를 안 주고 마커만 있는 호출에서 높이는 안 더하고 줄만 빼면 실제보다
    # 짧게 잡힌다.
    counted = len([im for im in (images or []) if isinstance(im, dict)])
    marks = len([1 for raw in (lines or []) if _IMG_MARK.match((raw or "").strip())])
    text -= min(text, marks, counted)
    return (fixed + text * LINE_PT, fixed + text * 2 * LINE_PT)


def fills_page(lines, tables=None, caption: bool = False,
               page_body_pt: float = PAGE_BODY_PT, images=None) -> bool:
    """이 내용이 한 쪽을 채울 **가능성이 있는지**.

    False 는 '아무리 길게 잡아도 못 채운다' 는 뜻이다 — 최대 추정치로 판정하므로
    거짓 경고가 나오지 않는다. True 는 '못 채운다고 단정할 수 없다' 로 읽는다
    (실제 채움은 렌더 뒤 tools/verify 로 실측한다).
    """
    return (height_bounds(lines, tables, caption, images)[1]
            >= filled_min_pt(page_body_pt))


def shortfall_lines(lines, tables=None, caption: bool = False,
                    page_body_pt: float = PAGE_BODY_PT, images=None) -> int:
    """한 쪽을 채우려면 몇 줄이 더 필요한지(최대 추정 기준, 24pt 줄 환산)."""
    gap = filled_min_pt(page_body_pt) - height_bounds(lines, tables, caption,
                                                      images)[1]
    return max(0, int(gap / LINE_PT + 0.999))
