#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""hwpx-reader — HWPX(한글) 문서 읽기 전용 MCP 서버 (FastMCP, stdio).

읽기 코어는 hwpx_reader.core, 저수준 원시함수는 hwpx-core 에 위임한다.
한글(HWP) 프로그램은 필요 없다.

── MCP 호스트 등록 예 ──
  "hwpx-reader": {
    "type": "local",
    "command": ["hwpx-reader-mcp"]          // 콘솔 스크립트(설치 시)
  }
소스로 직접 실행:
  "command": ["<python>", "-m", "hwpx_reader.server"],
  "environment": {"PYTHONPATH": "<hwpx-reader/src>;<hwpx-core/src>"}
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict

from . import core
from .core import HwpxReadError

logging.basicConfig(
    level=logging.INFO, stream=sys.stderr,
    format="%(asctime)s - hwpx-reader - %(levelname)s - %(message)s")
log = logging.getLogger("hwpx-reader")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "hwpx-reader",
    instructions=(
        "기존 HWPX(한글) 문서를 읽기 전용으로 조회하는 서버. 문서 생성은 "
        "hwpx-skeleton(표준서식)·hwpx-writer(자유 구성)를 쓴다."))

# 응답 상한 — 응답은 그대로 LLM 컨텍스트에 들어가므로 모든 조회 도구가 상한을 갖고,
# 잘리면 반드시 truncated 로 알린다(무음 절단 금지). 작은 컨텍스트 모델(7B 급)을 쓰면
# 환경변수로 낮춰 잡는다.
def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, "") or default)
        return v if v > 0 else default
    except ValueError:
        log.warning("%s 값이 정수가 아님 — 기본 %d 적용", name, default)
        return default


_MAX_TEXT_CHARS = _env_int("HWPX_READER_MAX_TEXT_CHARS", 60_000)
_MAX_TABLE_ROWS = _env_int("HWPX_READER_MAX_TABLE_ROWS", 500)
_MAX_HITS = _env_int("HWPX_READER_MAX_HITS", 200)
_MAX_OUTLINE_ITEMS = _env_int("HWPX_READER_MAX_OUTLINE_ITEMS", 200)
_MAX_MEMOS = _env_int("HWPX_READER_MAX_MEMOS", 200)

# 접근 루트 제한(opt-in): 설정하면 그 하위 경로만 읽는다.
# 미설정이면 서버 계정이 읽을 수 있는 모든 절대경로 허용 — 상시 서버에서는
# 파일 존재 오라클·임의 문서 탐침이 되므로 지정 권장.
_READER_ROOT = os.environ.get("HWPX_READER_ROOT", "").strip()


def _err(msg: str) -> Dict[str, Any]:
    return {"status": "error", "message": msg}


def _ok(**kw) -> Dict[str, Any]:
    return {"status": "success", **kw}


def _check_path(path: str):
    """공통 경로 검증 — 절대경로 강제(서버 CWD 는 임의라 상대경로는 엉뚱한 곳을
    가리킴) + HWPX_READER_ROOT 설정 시 그 하위만 허용. 위반 시 오류 dict."""
    if not isinstance(path, str) or not path.strip():
        return _err("path 가 비어 있습니다.")
    if not os.path.isabs(path):
        return _err(f"path 는 절대 경로여야 합니다: {path!r}")
    if _READER_ROOT:
        try:
            Path(path).resolve().relative_to(Path(_READER_ROOT).resolve())
        except ValueError:
            return _err(f"허용 루트({_READER_ROOT}) 밖의 경로는 읽을 수 없습니다.")
    return None


@mcp.tool()
def read_text(path: str, dedupe: bool = True,
              include_tables: bool = True, offset: int = 0) -> Dict[str, Any]:
    """HWPX 파일의 전체 텍스트를 문서 순서대로 추출한다.

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
        dedupe: 연속 중복 줄을 하나로 합칠지. 기본 True.
        include_tables: 표 안 텍스트도 포함할지. 기본 True.
        offset: 문자 시작 위치(0부터). 응답이 truncated=true 면
            next_offset 값을 넣어 다시 호출해 이어 읽는다.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        text = core.core_read_text(path, dedupe=dedupe, include_tables=include_tables)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("read_text 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0
    chunk = text[offset:offset + _MAX_TEXT_CHARS]
    truncated = offset + len(chunk) < len(text)
    return _ok(text=chunk, char_count=len(text), offset=offset,
               next_offset=offset + len(chunk) if truncated else None,
               truncated=truncated)


@mcp.tool()
def read_tables(path: str) -> Dict[str, Any]:
    """HWPX 파일 내 모든 표를 [표][행][열] 문자열 배열로 추출한다.
    표당 500행 상한 — 잘린 표가 있으면 truncated=true, truncated_tables=잘린 표 수.

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        tables = core.core_read_tables(path)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("read_tables 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    # 행 상한 절단은 무음이면 LLM 이 잘린 표를 온전한 것으로 믿는다 → 반드시 표시
    truncated_tables = sum(1 for t in tables if len(t) > _MAX_TABLE_ROWS)
    return _ok(table_count=len(tables),
               tables=[t[:_MAX_TABLE_ROWS] for t in tables],
               truncated=truncated_tables > 0,
               truncated_tables=truncated_tables)


@mcp.tool()
def outline(path: str, min_pt: float = 15.5) -> Dict[str, Any]:
    """큰 글씨 문단을 제목/소제목으로 추정해 문서 개요를 반환한다.
    최대 200건 — 초과분은 잘리고 truncated=true (min_pt 를 높여 재호출).

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
        min_pt: 이 크기(pt) 이상을 제목으로 간주. 기본 15.5.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        items = core.core_outline(path, min_pt=min_pt)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("outline 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    # min_pt 를 낮게 주면 전 문단이 제목으로 잡힌다 — 상한 없이는 컨텍스트 폭파
    return _ok(headings=items[:_MAX_OUTLINE_ITEMS],
               heading_count=len(items),
               truncated=len(items) > _MAX_OUTLINE_ITEMS)


@mcp.tool()
def read_structure(path: str) -> Dict[str, Any]:
    """제목 기준으로 섹션을 나눠 계층 구조로 반환한다(공공기관 표준서식에 최적).
    총 60,000자 상한 — 넘으면 truncated=true (이후 내용은 read_text 의 offset 으로).

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        data = core.core_read_structure(path)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("read_structure 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    # read_text 와 동일한 총량 상한 — 대용량 문서에서 이 도구만 무제한이면
    # 60k 컷을 우회하는 셈이 된다. 자르면 truncated 로 알리고 이어읽기 경로 안내.
    budget = _MAX_TEXT_CHARS
    sections_out = []
    truncated = False
    for s in data.get("sections", []):
        if budget <= 0:
            truncated = True
            break
        heading = s.get("heading", "")
        budget -= len(heading)
        lines = []
        for ln in s.get("lines", []):
            if budget <= 0:
                truncated = True
                break
            lines.append(ln)
            budget -= len(ln)
        sections_out.append({"heading": heading, "lines": lines})
    resp = _ok(file=data.get("file", ""), sections=sections_out,
               section_count=len(data.get("sections", [])), truncated=truncated)
    if truncated:
        resp["hint"] = "이후 내용은 read_text 를 offset 으로 나눠 읽으세요."
    return resp


@mcp.tool()
def search(path: str, keyword: str, context: bool = False) -> Dict[str, Any]:
    """HWPX 파일에서 키워드가 포함된 줄을 찾는다.
    최대 200건 반환 — hit_count 는 전체 수, 잘리면 truncated=true.

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
        keyword: 찾을 문자열.
        context: True 면 앞/뒤 줄도 함께 반환.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        hits = core.core_search(path, keyword, context=context)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("search 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    # hit_count 는 전체 수 — hits 가 잘렸으면 truncated 로 명시(수량 불일치 혼동 방지)
    return _ok(hit_count=len(hits), hits=hits[:_MAX_HITS],
               truncated=len(hits) > _MAX_HITS)


@mcp.tool()
def info(path: str) -> Dict[str, Any]:
    """HWPX 파일의 메타데이터/통계 요약(제목·문단수·표수·미리보기 등)을 반환한다.

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        meta = core.core_info(path)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("info 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    return _ok(**meta)


@mcp.tool()
def read_memos(path: str) -> Dict[str, Any]:
    """문서에 달린 메모(검토 의견)를 문서 순서대로 반환한다.
    최대 200건 — memo_count 는 전체 수, 잘리면 truncated=true.

    검토본을 받았을 때 무엇을 지적받았는지 회수하는 경로다. 각 항목의 anchor 는
    그 메모가 걸린 본문 글자라, 어느 대목을 두고 한 말인지 그대로 알 수 있다.

    Args:
        path: 읽을 .hwpx 파일의 절대 경로.
    """
    bad = _check_path(path)
    if bad:
        return bad
    try:
        memos = core.core_read_memos(path)
    except HwpxReadError as e:
        return _err(str(e))
    except Exception as e:  # noqa
        log.exception("read_memos 실패")
        return _err(f"예상치 못한 오류: {e!r}")
    return _ok(memo_count=len(memos), memos=memos[:_MAX_MEMOS],
               truncated=len(memos) > _MAX_MEMOS)


def main() -> None:
    log.info("hwpx-reader 시작 (stdio)%s",
             f" · 허용 루트 {_READER_ROOT}" if _READER_ROOT
             else " · 허용 루트 미설정(모든 절대경로 허용 — HWPX_READER_ROOT 로 제한 가능)")
    mcp.run()


if __name__ == "__main__":
    main()
