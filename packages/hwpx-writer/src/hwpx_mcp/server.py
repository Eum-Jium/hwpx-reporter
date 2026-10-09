"""
server.py — HWPX 보고서 생성 MCP 서버 (FastMCP).

MCP 호스트가 stdio 또는 HTTP로 연결.
LLM은 호스트가 담당 — 이 서버는 순수 도구/프롬프트만 제공.
"""
from __future__ import annotations

import functools
import inspect
import logging
from pathlib import Path
from typing import Any, Literal, Optional

from fastmcp import FastMCP
from hwpx_core.markers import lead_marker, strip_marker

from .config import (
    configure_logging, check_hwpx_version, check_fonts,
    MCP_TRANSPORT, MCP_HOST, MCP_PORT, MCP_AUTH_TOKEN, HWPX_DIR,
)
from .store import DocumentStore, doc_to_blocks_json
from .prompt import SYSTEM_PROMPT
from .models import (
    ok, err, ValidationError,
    validate_report_type, validate_table,
    validate_merge, validate_cell_style, validate_col_ratios,
)

configure_logging()
logger = logging.getLogger("hwpx_mcp.server")
check_hwpx_version(strict=False)
check_fonts()

mcp = FastMCP(
    "공공기관 보고서 작성",
    instructions=(
        "자유 구성 공공기관 보고서(섹션·항목부호·표·이미지 조립)용 서버. "
        "create_document → set_section_body/add_bullet/add_table → render_hwpx "
        "순서로 쓴다. 기획·사업결과·행사·교육·회의 '표준서식' 완성본은 이 서버가 "
        "아니라 hwpx-skeleton 서버의 render_from_skeleton 이 정답이다."))
store = DocumentStore()


def _safe(stage: str):
    """도구 본문을 감싸 예외를 구조화 에러로 변환. 원본 시그니처 보존(FastMCP 스키마용)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except ValidationError as e:
                return err(stage, str(e))
            except ValueError as e:
                return err(stage, str(e))
            except Exception as e:
                logger.exception("%s 실패", stage)
                return err(stage, f"{type(e).__name__}: {e}")
        wrapper.__signature__ = inspect.signature(fn)   # *args 래퍼 회피
        return wrapper
    return deco


def _find_section_or_raise(doc, section_key):
    s = store.find_section(doc, section_key)
    if s is None:
        raise ValidationError(
            f"section_key '{section_key}' 없음. 존재: {[x.key for x in doc.sections]}")
    return s


def _tables_in(section):
    return [b for b in section.blocks if b.get("type") in ("simple_table", "table")]


# ── 1. 문서 생성 ─────────────────────────────────────────
@mcp.tool()
@_safe("create_document")
def create_document(title: str,
                    report_type: Literal["기획", "현황", "회의", "행사"] = "기획",
                    author: str = "", department: str = "",
                    doc_date: str = "", sections: Optional[list] = None) -> dict:
    """
    자유 구성 공공기관 보고서 문서를 생성한다. (표준서식 완성본은
    hwpx-skeleton 의 render_from_skeleton 사용 — 이 도구가 아님)
    report_type: "기획" | "현황" | "회의" | "행사" (미지정 시 유형별 기본 섹션 자동)
    sections: [{"key":"background","heading":"추진배경"}, ...] 객체 배열
    (문자열 배열 불가, 미지정 시 유형 기본값)
    """
    validate_report_type(report_type)
    if not title or not title.strip():
        raise ValidationError("title 은 비어 있을 수 없음")
    if sections is not None:
        if (not isinstance(sections, list)
                or not all(isinstance(s, dict) and str(s.get("key", "")).strip()
                           and str(s.get("heading", "")).strip() for s in sections)):
            raise ValidationError(
                'sections 형식 오류 — [{"key":"background","heading":"추진배경"}] '
                "형태의 객체 배열이어야 함(key·heading 필수, 문자열 배열 불가)")
        # key 중복은 이후 section_key 지정이 항상 첫 섹션만 가리키는 잠복 상태가 됨
        keys = [str(s["key"]).strip() for s in sections]
        dups = sorted({k for k in keys if keys.count(k) > 1})
        if dups:
            raise ValidationError(f"sections key 중복: {dups} — key 는 고유해야 함")
    doc = store.create_report(title=title.strip(), report_type=report_type,
                              author=author, department=department,
                              doc_date=doc_date, sections=sections)
    return ok(document_id=doc.document_id, title=doc.title, report_type=doc.report_type,
              sections=[{"key": s.key, "heading": s.heading} for s in doc.sections],
              created_at=doc.created_at)


# ── 2. 섹션 추가 ─────────────────────────────────────────
@mcp.tool()
@_safe("add_section")
def add_section(document_id: str, heading: str, key: str = "",
                after_section_key: str = "") -> dict:
    """
    섹션을 추가한다. key 미지정 시 'sec_N' 자동 생성(사용 중이면 다음 번호).
    after_section_key 지정 시 해당 섹션 뒤에 삽입.
    """
    from .store import Section
    with store.modify(document_id) as doc:
        if not heading.strip():
            raise ValidationError("heading 은 비어 있을 수 없음")
        skey = key.strip()
        if skey:
            if store.find_section(doc, skey):
                raise ValidationError(f"section_key '{skey}' 중복")
        else:
            # 자동 키는 기존 키와 충돌하지 않는 번호까지 전진 (사용자 지정 sec_N 과 공존)
            n = len(doc.sections) + 1
            while store.find_section(doc, f"sec_{n}"):
                n += 1
            skey = f"sec_{n}"
        new_sec = Section(key=skey, heading=heading.strip())
        if after_section_key:
            idx = next((i for i, s in enumerate(doc.sections) if s.key == after_section_key), None)
            if idx is None:
                raise ValidationError(f"after_section_key '{after_section_key}' 없음")
            doc.sections.insert(idx + 1, new_sec)
        else:
            doc.sections.append(new_sec)
    return ok(document_id=document_id, section_key=skey,
              index=doc.sections.index(new_sec), updated_at=doc.updated_at)


# ── 3. 섹션 본문 입력 ────────────────────────────────────
@mcp.tool()
@_safe("set_section_body")
def set_section_body(document_id: str, section_key: str, text: str,
                     append: bool = False) -> dict:
    """
    섹션 본문(문단)을 입력한다.
    □ ◦ - * 로 시작하는 줄은 표준 항목부호로, **텍스트**는 볼드로 자동 처리.
    append=False(기본)는 기존 문단·항목부호(bullet) 블록을 교체하며
    표·이미지 블록은 보존한다. append=True 는 맨 뒤에 문단을 추가한다.
    """
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        para = {"type": "paragraph", "text": text}
        if append:
            section.blocks.append(para)
        else:
            # 본문 텍스트(문단+bullet)만 교체 — 표/이미지까지 지우면 "문구만 다듬는"
            # 재호출 한 번에 조립해 둔 표·병합·셀스타일이 통째로 사라지고(응답은
            # success 라 감지 불가), bullet 을 남기면 재작성마다 옛 항목이 중복 누적된다.
            new_blocks, replaced = [], False
            for b in section.blocks:
                if b.get("type") in ("paragraph", "bullet"):
                    if not replaced:
                        new_blocks.append(para)
                        replaced = True
                    # 나머지 문단·bullet 은 교체 대상이므로 버림
                else:
                    new_blocks.append(b)
            if not replaced:
                new_blocks.append(para)
            section.blocks = new_blocks
    preserved = sum(1 for b in section.blocks
                    if b.get("type") not in ("paragraph", "bullet"))
    return ok(document_id=document_id, section_key=section_key,
              block_count=len(section.blocks), preserved_blocks=preserved,
              updated_at=doc.updated_at)


# ── 4. 항목부호 단락 ─────────────────────────────────────
# 렌더가 marker 를 자동 부착하므로 text 선두의 기호는 중복("□ □ ...")이 된다.
# 경계 규칙(- ○ ㅁ ㅇ 는 뒤 공백 필수)은 hwpx_core.markers 단일 기준을 따른다 —
# 음수("-5%")·자리표("○○부")·한글 낱자("ㅁ자형")를 기호로 먹지 않기 위해서다.
def _strip_leading_marker(text: str) -> str:
    return strip_marker(text) if lead_marker(text) else text


@mcp.tool()
@_safe("add_bullet")
def add_bullet(document_id: str, section_key: str, text: str,
               level: int = 1, marker: str = "") -> dict:
    """
    항목부호 단락 추가. level 1=□ 2=◦ 3=- 4=· 5=*(참고). marker로 기호 직접 지정 가능.
    기호는 자동 부착되므로 text 에는 내용만 넣는다(선두 기호는 중복 방지 위해 제거됨).
    """
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        if not (1 <= level <= 5):
            raise ValidationError("level 은 1~5")
        marker = (marker or "").strip()
        if marker and (len(marker) > 2 or any(ch.isspace() for ch in marker)):
            raise ValidationError(f"marker 는 공백 없는 1~2자 기호여야 함: {marker!r}")
        section.blocks.append({"type": "bullet", "text": _strip_leading_marker(text),
                               "level": level, "marker": marker or None})
    return ok(document_id=document_id, section_key=section_key,
              block_count=len(section.blocks), updated_at=doc.updated_at)


# ── 5. 표 추가 ───────────────────────────────────────────
@mcp.tool()
@_safe("add_table")
def add_table(document_id: str, section_key: str,
              headers: list, rows: list,
              col_ratios: Optional[list] = None,
              style: Literal["gov", "plain"] = "gov") -> dict:
    """
    표를 추가한다. style="gov"(정부문서 테두리) | "plain".
    headers 는 첫 행(제목행) 문자열 배열, rows 는 데이터행의 배열(각 행 = 셀 배열).
    모든 행 열 수 동일(직사각형).
    """
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        ncol = validate_table(headers, rows)
        if style not in ("gov", "plain"):
            raise ValidationError('style 은 "gov" 또는 "plain"')
        block = {"type": "table", "headers": headers, "rows": rows, "style": style}
        if col_ratios:
            validate_col_ratios(col_ratios, ncol)
            block["col_ratios"] = col_ratios
        section.blocks.append(block)
    return ok(document_id=document_id, section_key=section_key,
              table_index=len(_tables_in(section)) - 1, updated_at=doc.updated_at)


# ── 6. 셀 병합 ★ ─────────────────────────────────────────
@mcp.tool()
@_safe("merge_cells")
def merge_cells(document_id: str, section_key: str, table_index: int,
                r1: int, c1: int, r2: int, c2: int) -> dict:
    """
    표의 셀을 병합한다 (제목행 가로 병합 등). 행 인덱스는 제목행 포함 0부터.
    (r1,c1)=좌상단, (r2,c2)=우하단.
    """
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        tables = _tables_in(section)
        if not (0 <= table_index < len(tables)):
            raise ValidationError(f"table_index {table_index} 범위 초과 (표 {len(tables)}개)")
        tb = tables[table_index]
        n_rows = (1 if tb.get("headers") else 0) + len(tb.get("rows", []))
        n_cols = len(tb.get("headers") or (tb["rows"][0] if tb.get("rows") else []))
        validate_merge(r1, c1, r2, c2, n_rows, n_cols)
        # 기존 병합과 겹치면 앵커가 이미 삭제된 셀일 수 있어 손상 파일이 됨 → 거부
        for mg in tb.get("merges", []) or []:
            if not (r2 < mg["r1"] or mg["r2"] < r1 or c2 < mg["c1"] or mg["c2"] < c1):
                raise ValidationError(
                    f"병합 범위가 기존 병합 ({mg['r1']},{mg['c1']})-({mg['r2']},{mg['c2']}) 과 겹침")
        tb.setdefault("merges", []).append({"r1": r1, "c1": c1, "r2": r2, "c2": c2})
    return ok(document_id=document_id, table_index=table_index,
              merges=len(tb["merges"]), updated_at=doc.updated_at)


# ── 7. 표 수정 (셀별 스타일 ★) ───────────────────────────
@mcp.tool()
@_safe("update_table")
def update_table(document_id: str, section_key: str, table_index: int,
                 headers: Optional[list] = None, rows: Optional[list] = None,
                 cell: Optional[dict] = None) -> dict:
    """
    표 수정. headers/rows 교체 또는 cell 로 특정 셀 스타일.
    cell = {"row":r,"col":c,"bg":"#RRGGBB","align":"CENTER","bold":true,
            "text_color":"#RRGGBB","font_size":12}  (스타일 키는 필요한 것만)
    """
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        tables = _tables_in(section)
        if not (0 <= table_index < len(tables)):
            raise ValidationError(f"table_index {table_index} 범위 초과 (표 {len(tables)}개)")
        tb = tables[table_index]
        if headers is not None:
            tb["headers"] = headers
        if rows is not None:
            tb["rows"] = rows
        dropped = {}
        if headers is not None or rows is not None:
            validate_table(tb.get("headers", []), tb.get("rows", []))
            # 표 크기가 바뀌면 기존 병합/셀스타일/열비율이 스테일 → 범위 초과분 제거(무시하면 손상 파일)
            n_rows = (1 if tb.get("headers") else 0) + len(tb.get("rows", []))
            n_cols = len(tb.get("headers") or (tb["rows"][0] if tb.get("rows") else []))
            if tb.get("merges"):
                kept = [m for m in tb["merges"] if m["r2"] < n_rows and m["c2"] < n_cols]
                if len(kept) != len(tb["merges"]):
                    dropped["dropped_merges"] = len(tb["merges"]) - len(kept)
                tb["merges"] = kept
            if tb.get("cell_styles"):
                kept = [c for c in tb["cell_styles"] if c.get("r", 0) < n_rows and c.get("c", 0) < n_cols]
                if len(kept) != len(tb["cell_styles"]):
                    dropped["dropped_cell_styles"] = len(tb["cell_styles"]) - len(kept)
                tb["cell_styles"] = kept
            if tb.get("col_ratios") and len(tb["col_ratios"]) != n_cols:
                dropped["dropped_col_ratios"] = True
                tb.pop("col_ratios")
        if cell is not None:
            n_rows = (1 if tb.get("headers") else 0) + len(tb.get("rows", []))
            n_cols = len(tb.get("headers") or (tb["rows"][0] if tb.get("rows") else []))
            validate_cell_style(cell, n_rows, n_cols)
            cs = tb.setdefault("cell_styles", [])
            cs[:] = [c for c in cs if not (c.get("r") == cell["row"] and c.get("c") == cell["col"])]
            entry = {"r": cell["row"], "c": cell["col"]}
            for k_src, k_dst in (("bg", "bg"), ("align", "align"), ("bold", "bold"),
                                 ("text_color", "text_color"), ("font_size", "font_size")):
                if k_src in cell:
                    entry[k_dst] = cell[k_src]
            cs.append(entry)
    return ok(document_id=document_id, table_index=table_index,
              updated_at=doc.updated_at, **dropped)


# ── 8. 이미지 (임베드) ───────────────────────────────────
@mcp.tool()
@_safe("add_image")
def add_image(document_id: str, section_key: str,
              image_path: str = "", image_b64: str = "",
              caption: str = "", width_mm: int = 120) -> dict:
    """
    이미지를 섹션에 추가(임베드). image_path 또는 image_b64 중 정확히 하나.
    바이너리는 HWPX BinData에 임베드되고 본문에 그림으로 들어간다(실패하면 캡션 박스).
    width_mm 는 10~170 (본문 폭 164mm).
    """
    from .engine.images import check_image_source
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        if not image_path and not image_b64:
            raise ValidationError("image_path 또는 image_b64 필요")
        if image_path and image_b64:
            # 한쪽 무음 폐기 방지 — 어느 소스가 쓰였는지 호출자가 모르는 상태를 만들지 않는다
            raise ValidationError("image_path 와 image_b64 는 동시 지정 불가 — 하나만 지정")
        if isinstance(width_mm, bool) or not isinstance(width_mm, (int, float)) \
                or not (10 <= width_mm <= 170):
            raise ValidationError(f"width_mm 는 10~170 숫자여야 함: {width_mm!r}")
        fmt = check_image_source(image_path=image_path, image_b64=image_b64)
        block = {"type": "image", "caption": caption, "width_mm": width_mm, "format": fmt}
        if image_path:
            block["path"] = image_path
        else:
            block["b64"] = image_b64
        section.blocks.append(block)
    return ok(document_id=document_id, section_key=section_key,
              block_count=len(section.blocks), updated_at=doc.updated_at)


# ── 9. 그림 자리 표 (플레이스홀더) ───────────────────────
@mcp.tool()
@_safe("add_image_placeholder")
def add_image_placeholder(document_id: str, section_key: str, captions: list) -> dict:
    """
    그림(사진)을 넣을 빈 칸 표를 추가. captions 길이 = 열(그림) 수.
    그림 파일은 사용자가 한글에서 직접 삽입.
    """
    with store.modify(document_id) as doc:
        section = _find_section_or_raise(doc, section_key)
        if not isinstance(captions, list) or not captions:
            raise ValidationError("captions 는 비어있지 않은 리스트여야 함")
        section.blocks.append({"type": "image_table", "captions": captions})
    return ok(document_id=document_id, section_key=section_key,
              column_count=len(captions), updated_at=doc.updated_at)


# ── 10. 목차 ─────────────────────────────────────────────
@mcp.tool()
@_safe("add_toc")
def add_toc(document_id: str, enabled: bool = True) -> dict:
    """문서 맨 앞에 목차 생성(섹션 제목 기준). 사용자가 요청할 때만.
    enabled=false 로 이미 켠 목차를 해제할 수 있다."""
    with store.modify(document_id) as doc:
        doc.meta["include_toc"] = bool(enabled)
    return ok(document_id=document_id, include_toc=bool(enabled),
              section_count=len(doc.sections), updated_at=doc.updated_at)


# ── 11. 문서 조회 ────────────────────────────────────────
def _redacted_blocks(blocks: list) -> list:
    """조회 응답용: 이미지 b64 원문은 생략(수만 자가 LLM 컨텍스트를 폭파함)."""
    out = []
    for b in blocks:
        if b.get("b64"):
            b = {**b, "b64": f"<{len(b['b64'])} chars 생략>"}
        out.append(b)
    return out


@mcp.tool()
@_safe("get_document")
def get_document(document_id: str) -> dict:
    """현재 문서 구조/내용 반환."""
    doc = store.get(document_id)
    return ok(document_id=doc.document_id, title=doc.title, report_type=doc.report_type,
              meta=doc.meta,
              sections=[{"key": s.key, "heading": s.heading,
                         "blocks": _redacted_blocks(s.blocks)}
                        for s in doc.sections],
              updated_at=doc.updated_at)


@mcp.tool()
@_safe("list_documents")
def list_documents(limit: int = 20) -> dict:
    """최근 수정순 문서 목록(document_id·title·updated_at).
    세션이 끊기거나 컨텍스트가 초기화되어 document_id 를 잃었을 때
    이 도구로 되찾은 뒤 get_document 로 이어간다."""
    docs = store.list_recent(limit)
    return ok(documents=docs, count=len(docs))


# ── 12. HWPX 렌더 ────────────────────────────────────────
@mcp.tool()
@_safe("render_hwpx")
def render_hwpx(document_id: str) -> dict:
    """문서를 공공기관 표준서식 HWPX 파일로 생성. 파일 경로 반환."""
    from .engine.render import render_from_blocks
    from .validation import validate_hwpx
    doc = store.get(document_id)
    blocks_json = doc_to_blocks_json(doc)
    out_path = str(Path(HWPX_DIR) / f"{document_id}.hwpx")
    path = render_from_blocks(blocks_json, out_path)
    p = Path(path)
    problems = validate_hwpx(str(p))   # 손상 파일을 무경고 success 로 반환하지 않기 위한 최종 검사
    if problems:
        logger.warning("render_hwpx 무결성 경고 %s: %s", document_id, problems)
    return ok(document_id=document_id, file_path=str(p), filename=p.name,
              size_bytes=p.stat().st_size if p.exists() else 0,
              validation_problems=problems)


# ── MCP 프롬프트 ─────────────────────────────────────────
@mcp.prompt()
def gov_report_guide() -> str:
    """공공기관 표준서식 보고서 작성 규칙 및 작업 흐름."""
    return SYSTEM_PROMPT


def main():
    logger.info("HWPX MCP 서버 시작 (transport=%s)", MCP_TRANSPORT)
    if MCP_TRANSPORT == "http":
        kwargs = dict(transport="http", host=MCP_HOST, port=MCP_PORT)
        # 인증 토큰이 설정되면 bearer 인증 적용.
        # fail-closed: 부착 실패 시 기동 거부 — 경고만 남기고 무인증으로 열리면
        # 운영자는 인증이 걸렸다고 믿는 채 네트워크 전체에 무방비 노출된다.
        if MCP_AUTH_TOKEN:
            try:
                from fastmcp.server.auth import StaticTokenVerifier  # type: ignore
                mcp.auth = StaticTokenVerifier(tokens={MCP_AUTH_TOKEN: {"sub": "gov"}})
                logger.info("HTTP bearer 인증 활성화")
            except Exception as e:
                logger.error("bearer 인증 부착 실패(FastMCP 버전 확인 필요): %s — "
                             "무인증 기동을 거부한다", e)
                raise SystemExit(1)
        mcp.run(**kwargs)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
