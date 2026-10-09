# -*- coding: utf-8 -*-
"""hwpx-skeleton MCP 서버 (FastMCP, stdio).

공공기관 표준서식 스켈레톤에 필드·본문을 채워 완성 .hwpx 를 생성하는
결정론적 엔진을 MCP 도구 3종으로 노출한다. LLM 방어로직(한자·분량·복구)은
포함하지 않는다 — 그 정책은 상위 오케스트레이터/정책 계층이 담당한다.

── MCP 호스트 등록 예(command·args·env 형식) ──
  "hwpx-skeleton": {
    "command": "<python>", "args": ["-m", "hwpx_skeleton.server"],
    "env": {"HWPX_SKELETON_STORAGE": "<출력 폴더 절대경로>"}
  }
콘솔 스크립트로 설치했다면 "command": "hwpx-skeleton-mcp" 만 넣어도 된다.
"""
from __future__ import annotations

import os
import sys
import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from hwpx_core import outline as _outline

from . import renderer, guides

logging.basicConfig(
    level=logging.INFO, stream=sys.stderr,
    format="%(asctime)s - hwpx-skeleton - %(levelname)s - %(message)s")
log = logging.getLogger("hwpx-skeleton")

# 출력 폴더: 환경변수 우선, 없으면 renderer 의 안전 기본값
# (소스 체크아웃=모노레포 루트 output/, 휠 설치본=사용자 데이터 디렉토리 —
#  CWD 폴백은 서비스 기동(임의 CWD)에서 즉사하므로 쓰지 않는다)
STORAGE = os.environ.get("HWPX_SKELETON_STORAGE") or renderer.default_output_dir()

mcp = FastMCP(
    "hwpx-skeleton",
    instructions=(
        "공공기관 표준서식 보고서(계획·결과·검토보고·기본 문서) "
        "완성본을 만드는 주 경로. list_templates → get_writing_guide(계획·결과·"
        "검토만 — plain 은 지침 없음) → render_from_skeleton 순서로 쓴다. "
        "표준서식이 아닌 자유 구성 문서나 "
        "표 중심 문서는 hwpx-writer 서버의 create_document 계열을 쓴다."))


# 에러 계약: 세 도구 모두 예외를 {"status":"error"} 봉투로 통일한다.
# (그대로 던지면 MCP SDK 의 isError 생텍스트가 되어 status 로 분기하는
#  오케스트레이터가 파싱하지 못한다 — render_from_skeleton 과 동일 규칙)
@mcp.tool()
def list_templates() -> Dict[str, Any]:
    """사용 가능한 공공기관 표준서식 스켈레톤 목록과 유형별 입력 필드를 반환한다."""
    try:
        return {"status": "success", "templates": renderer.list_templates()}
    except Exception as e:  # noqa
        log.exception("list_templates 실패")
        return {"status": "error", "stage": "list_templates",
                "message": f"{type(e).__name__}: {e}"}


@mcp.tool()
def get_writing_guide(template_key: str) -> Dict[str, Any]:
    """보고서 유형별 세부 작성지침(md)을 반환한다. body 를 작성하기 전에 읽는다.

    Args:
        template_key: plan · result · review 중 하나(옛 유형 키 planning·
            business_result·meeting_plan 등도 받는다). plain(기본 문서)은 공문서
            관행 검사를 걸지 않아 지침이 없다 — guide 를 빈 글로 돌려준다.
    """
    if _outline.resolve((template_key or "").strip()) == _outline.PLAIN:
        return {"status": "success", "template_key": (template_key or "").strip(),
                "guide": "",
                "message": "plain 은 따로 지침이 없다 — 바로 render_from_skeleton 을 부른다."}
    try:
        guide = guides.get_writing_guide(template_key)
    except Exception as e:  # noqa
        log.exception("get_writing_guide 실패")
        return {"status": "error", "stage": "get_writing_guide",
                "message": f"지침 읽기 실패({type(e).__name__}): {e}"}
    if guide is None:
        return {"status": "error", "stage": "get_writing_guide",
                "message": f"지침 없음: {template_key!r} (본문 유형이 아니거나 파일 없음)"}
    return {"status": "success", "template_key": (template_key or "").strip(),
            "guide": guide}


@mcp.tool()
def render_from_skeleton(template_key: str,
                         fields: Optional[Dict[str, str]] = None,
                         body: Optional[str] = "",
                         intent: Optional[str] = None,
                         tables: Optional[list] = None,
                         images: Optional[list] = None,
                         attachments: Optional[list] = None) -> Dict[str, Any]:
    """공공기관 표준서식 스켈레톤에 필드·본문을 채워 새 .hwpx 로 저장한다.
    표준서식 완성본은 이 도구가 정답이다(자유 구성 문서는 hwpx-writer 의
    create_document 계열 사용).

    제목 파란 박스·표·폰트 등 원본 서식은 그대로 유지되고, 본문의 간격·계층·
    내어쓰기는 코드가 자동 적용한다. 공문서 유형(plan·result·review)은 골격·종결·
    줄 길이 규격에 어긋난 줄을 warnings 로 알린다(고치지는 않는다). 표·그림·붙임을
    채우며 난 경고는 body_result.warnings 에 따로 온다.

    Args:
        template_key: 사용할 스켈레톤 키(list_templates 참조).
        fields: 필드명 → 값. title · owner · date(【주관】 줄 — date 를 비우면 오늘,
            owner 를 비우면 양식 견본 그대로).
        body: 보고서 본문 전체(줄바꿈 구분). 각 줄:
            '1. 헤딩' / '□ 항목' / '◦ 세부' / '* 참고'.
            빈 문자열이면 양식 안내 문구를 유지한다.
        intent: 취지 한 줄 요약(제목 아래 취지 박스). 예: '~방안 보고'.
        tables: 표 목록. [{"headers": [...], "rows": [[...], ...],
            "col_ratios": [3,2,2], "cells": [{"r":1,"c":2,"align":"LEFT"}]}, …].
            col_ratios 는 열 너비 비율(열 수만큼, 전체 폭은 고정), cells 는 셀별
            정렬(LEFT·CENTER·RIGHT·JUSTIFY)·볼드. 둘 다 생략하면 정본 기본값.
        images: 이미지자리 목록. [{"captions": ["구성도", …]}, …] (칸 1~3개).
            같은 항목에 "path"(그림 파일 경로) 또는 "b64"(base64)를 주면 그림이
            들어가고, 없으면 빈 자리와 캡션만 남는다.
        attachments: 본문 뒤 별지. [{"title": 제목, "body": 본문 줄,
            "tables": [...]}, …]. 본문 끝에 붙임 목록이 자동으로 붙는다.

    본문 줄에 '[표1]' '[이미지1]' 을 쓰면 해당 항목이 그 자리에 들어가고,
    안 쓰면 문서 끝에 붙는다.
    """
    # 에러 계약 통일: 명시 오류와 동일하게 예외도 {"status":"error"} 봉투로.
    # (그대로 던지면 MCP SDK 의 isError 생텍스트가 되어 status 로 분기하는
    #  오케스트레이터가 파싱하지 못한다)
    try:
        return renderer.render(
            template_key=template_key,
            fields=fields or {},
            output_dir=STORAGE,
            body=body or None,
            intent=intent,
            tables=tables,
            images=images,
            attachments=attachments,
        )
    except Exception as e:  # noqa
        log.exception("render_from_skeleton 실패")
        return {"status": "error", "stage": "render",
                "message": f"렌더 실패({type(e).__name__}): {e}"}


def main() -> None:
    try:
        os.makedirs(STORAGE, exist_ok=True)
    except OSError as e:
        log.error("출력 폴더 생성 실패: %s (%s) — HWPX_SKELETON_STORAGE 환경변수로 "
                  "쓰기 가능한 경로를 지정하라", STORAGE, e)
        raise SystemExit(1)
    log.info("hwpx-skeleton 시작 (stdio) · 출력 %s", STORAGE)
    mcp.run()


if __name__ == "__main__":
    main()
