"""
render.py — 블록 JSON 문서 모델 → HWPX 파일 렌더.

입력 doc_json 구조 (kor_hwpx_generator _doc_to_blocks_json + 확장):
{
  "title": str,
  "meta": {"author","department","date"},   # 선택
  "blocks": [
    {"type":"toc", "entries":[str,...]},
    {"type":"heading", "text":str, "level":int},
    {"type":"paragraph", "text":str},         # 줄머리(□◦-*)·**bold** 자동 파싱
    {"type":"bullet", "text":str, "level":int, "marker":str},
    {"type":"table"|"simple_table", "headers":[...], "rows":[[...]],
       "col_ratios":[...]?, "style":"gov"|"plain"?,
       "merges":[{"r1","c1","r2","c2"}]?, "cell_styles":[{"r","c","bg","align","bold"}]?},
    {"type":"image_table", "captions":[...]},
    {"type":"image", "path"|"b64":..., "caption":str, "width_mm":int?},
  ]
}
"""
from __future__ import annotations

import re

from hwpx_core.markers import canon_marker, strip_marker

from .builder import Doc, RunFmt, ParaFmt, CellFmt
from .borders import GovTableBorders
from .constants import (
    mm, HANG_INTENT, ROMAN_CHARS, LEAD_SPACES, BULLET_MARKERS,
    calc_col_widths, PAGE_MARGIN,
    FONT_BODY, FONT_REF, FONT_TABLE, SIZE_BODY, SIZE_REF, SIZE_TABLE,
    HEADER_FILL,
)


# ── 줄머리 기호 감지 (_detect_level 이식) ─────────────────
def _detect_line(line: str):
    """
    줄 첫 기호 → (marker, level, font, size, is_ref)
    marker: 내어쓰기 intent 키 ("□"/"◦"/"-"/"*") 또는 None
    """
    s = line.lstrip()
    if s.startswith("**"):
        # **볼드** 시작 줄은 참고(*) 마커가 아님 — 본문으로 두고 _add_bold_runs 가 처리
        return (None, 0, FONT_BODY, SIZE_BODY, False)
    if s and s[0] in ROMAN_CHARS:
        return (None, 1, "HY헤드라인M", 16, False)   # 로마숫자 = 중간제목급
    c = canon_marker(s)   # 별칭·경계 판정은 hwpx_core.markers 단일 기준
    if c == "□":
        return ("□", 1, FONT_BODY, SIZE_BODY, False)
    if c == "◦":
        return ("◦", 2, FONT_BODY, SIZE_BODY, False)
    if c == "-":
        return ("-", 3, FONT_BODY, SIZE_BODY, False)
    if c == "·":
        return ("·", 4, FONT_BODY, SIZE_BODY, False)
    if c == "*":
        return ("*", 5, FONT_REF, SIZE_REF, True)
    return (None, 0, FONT_BODY, SIZE_BODY, False)   # 일반 본문


def _strip_marker(line: str, marker: str) -> str:
    """선두 마커 제거 — 별칭(☐→□, ○→◦, ※→*)도 hwpx_core 기준으로 함께 처리."""
    return strip_marker(line)


def _add_bold_runs(para, content: str, size: int, font: str):
    """**bold** 마크다운을 run으로 분해해 para에 추가"""
    parts = re.split(r'(\*\*[^*]+\*\*)', content)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            para.add_run(part[2:-2], fmt=RunFmt(font_size=size, bold=True,
                                                font_hangul=font, font_latin=font))
        else:
            para.add_run(part, fmt=RunFmt(font_size=size, bold=False,
                                          font_hangul=font, font_latin=font))


def _emit_body(doc: Doc, text: str):
    """섹션 본문 텍스트 → 줄별 항목부호/본문 단락 생성"""
    for raw in (text or "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            doc.blank()
            continue
        marker, level, font, size, is_ref = _detect_line(line)
        content = _strip_marker(line, marker) if marker else line.strip()

        if marker is None and level == 1:   # 로마숫자 중간제목
            doc.heading(content, level=2)
            continue

        if marker:
            # 스켈레톤 규칙과 동일: 왼쪽여백 0 + 앞칸은 '공백 문자' + 내어쓰기만
            # 음수 intent 로 (문단 들여쓰기로 계단을 만들지 않는다 — 실측 확인)
            lead = LEAD_SPACES.get(marker, 1)
            intent = HANG_INTENT.get(marker, 0)   # 음수
            pfmt = ParaFmt(align="JUSTIFY", line_spacing=160,
                           indent_left=0, indent_first=intent)
            p = doc.para(text="", para_fmt=pfmt)
            p.add_run(f"{' ' * lead}{marker} ",
                      fmt=RunFmt(font_size=size, font_hangul=font, font_latin=font))
            _add_bold_runs(p, content, size, font)
        else:
            pfmt = ParaFmt(align="JUSTIFY", line_spacing=160)
            p = doc.para(text="", para_fmt=pfmt)
            _add_bold_runs(p, content, size, font)


# ── 표 렌더 ──────────────────────────────────────────────
def _emit_table(doc: Doc, block: dict):
    headers = block.get("headers", []) or []
    rows = block.get("rows", []) or []
    style = block.get("style", "gov")
    has_header = bool(headers)

    grid = ([headers] if has_header else []) + rows
    if not grid:
        return
    n_rows = len(grid)
    n_cols = max(len(r) for r in grid)
    # 균일화 (ragged 방지) — None 은 "None" 이 아니라 빈 셀로
    grid = [["" if c is None else str(c) for c in r] + [""] * (n_cols - len(r))
            for r in grid]

    tbl = doc.table(n_rows, n_cols)

    # 열너비
    col_ratios = block.get("col_ratios")
    if col_ratios:
        tbl.set_width(164, col_ratios=col_ratios)
    else:
        widths = calc_col_widths(headers if has_header else grid[0], rows)
        tbl.set_width(164, col_ratios=widths)

    # cell_styles 인덱스
    cs_map = {}
    for cs in block.get("cell_styles", []) or []:
        cs_map[(cs.get("r"), cs.get("c"))] = cs

    gb = None
    if style == "gov":
        gb = GovTableBorders(doc._header, has_header=has_header,
                                n_data_rows=len(rows), col_count=n_cols)

    for ri in range(n_rows):
        is_header_row = has_header and ri == 0
        for ci in range(n_cols):
            override = cs_map.get((ri, ci), {})
            fmt = CellFmt(
                font_size=override.get("font_size", SIZE_TABLE),
                bold=override.get("bold", is_header_row),
                align=override.get("align", "CENTER" if is_header_row else "LEFT"),
                text_color=override.get("text_color", "#000000"),
                font_hangul=FONT_TABLE, font_latin=FONT_TABLE,
            )
            if gb is not None:
                bg = override.get("bg")
                if bg:
                    # 정부문서 테두리 + 커스텀 배경
                    left, right, top, bottom, fill = _gov_state(gb, ri, ci)
                    fmt.border_fill_id = doc.add_border_fill(
                        bg_color=bg,
                        border_sides={"left": left, "right": right, "top": top, "bottom": bottom})
                else:
                    fmt.border_fill_id = gb.border_fill_id(ri, ci)
            else:
                if override.get("bg"):
                    fmt.bg_color = override["bg"]
            tbl.cell(ri, ci, grid[ri][ci], fmt)

    # 병합
    for mg in block.get("merges", []) or []:
        tbl.merge(int(mg["r1"]), int(mg["c1"]), int(mg["r2"]), int(mg["c2"]))


def _gov_state(gb: GovTableBorders, ri: int, ci: int):
    from .constants import BORDER_STATES
    key = gb._state_key(ri, ci)
    return BORDER_STATES[key]


def _emit_image_table(doc: Doc, block: dict):
    """그림 자리 표 (윗줄 빈칸 + 아랫줄 캡션). 그림은 한글에서 직접 삽입."""
    captions = block.get("captions", []) or []
    n = len(captions) or 1
    tbl = doc.table(2, n)
    tbl.set_width(164, col_ratios=[1] * n)
    for c in range(n):
        tbl.cell(0, c, "", CellFmt(font_size=SIZE_TABLE, align="CENTER",
                                   font_hangul=FONT_TABLE, font_latin=FONT_TABLE))
    for c in range(n):
        cap = captions[c] if c < len(captions) else ""
        tbl.cell(1, c, cap, CellFmt(font_size=SIZE_REF, align="CENTER",
                                    font_hangul=FONT_TABLE, font_latin=FONT_TABLE))


def _emit_toc(doc: Doc, entries: list):
    doc.heading("목  차", level=2, align="CENTER")
    for e in entries or []:
        p = doc.para(text="", para_fmt=ParaFmt(align="JUSTIFY", line_spacing=180,
                                               indent_left=mm(3)))
        p.add_run(str(e), fmt=RunFmt(font_size=SIZE_BODY, font_hangul=FONT_BODY, font_latin=FONT_BODY))
    doc.blank()


# ── 메인 렌더 ────────────────────────────────────────────
def render_from_blocks(doc_json: dict, out_path: str) -> str:
    """블록 JSON → HWPX 파일. 저장 경로 반환."""
    title = str(doc_json.get("title", "제목 없음")).strip() or "제목 없음"
    meta = doc_json.get("meta", {}) or {}
    blocks = doc_json.get("blocks", []) or []

    doc = Doc()
    doc.set_page_margin(**PAGE_MARGIN)

    # 머리말 (작성일/부서)
    header_bits = []
    if meta.get("date"):
        header_bits.append(str(meta["date"]))
    if meta.get("department"):
        header_bits.append(str(meta["department"]))
    if header_bits:
        doc.set_header("  ".join(header_bits))

    # 문서 제목
    doc.heading(title, level=1)
    doc.blank()

    for block in blocks:
        btype = block.get("type")
        if btype == "toc":
            _emit_toc(doc, block.get("entries", []))
        elif btype == "heading":
            doc.heading(block.get("text", ""), level=block.get("level", 2))
        elif btype == "paragraph":
            _emit_body(doc, block.get("text", ""))
        elif btype == "bullet":
            # marker 미지정 시 저장된 level 로 기호 유도 (level 무시 → 평문 렌더 방지)
            try:
                lvl = int(block.get("level") or 1)
            except (TypeError, ValueError):
                lvl = 1
            marker = block.get("marker") or BULLET_MARKERS.get(lvl, "□")
            _emit_body(doc, f"{marker} {block.get('text', '')}".strip())
        elif btype in ("table", "simple_table"):
            _emit_table(doc, block)
            doc.blank()
        elif btype == "image_table":
            _emit_image_table(doc, block)
            doc.blank()
        elif btype == "image":
            from .images import emit_image
            emit_image(doc, block)
            doc.blank()

    return doc.save(out_path)
