# -*- coding: utf-8 -*-
"""
render_report.py — 공공기관 표준서식 렌더 진입점 (skeleton 방식)

양식 hwpx 원본을 복제해 제목/본문/표/이미지자리를 채운다.
취지박스·【주관】 작성자 블록·표 이중선 등 원본 서식이 그대로 유지된다.

의존성: 없다(표준 라이브러리만)

사용법:
    import sys, os
    sys.path.insert(0, os.path.join("<스킬 폴더>", "scripts"))
    from render_report import render, list_templates, get_writing_guide

    res = render(
        template_key="plan",                  # list_templates() 로 목록 확인
        fields={"title": "문서 자동화 시스템 구축 방안"},
        body="1. 추진배경\n□ 항목\n◦ 세부\n* 참고",   # 기호만 쓰면 앞칸·간격 자동
        tables=[{"headers": ["구분", "내용"], "rows": [["1", "..."]]}],
        images=[{"captions": ["현장 사진"]}],  # <이미지 삽입> 자리+캡션 (path·b64 를 주면 그림이 들어간다)
        output_dir="output",
    )
    # res = {"status": "success", "path": "...hwpx", "warnings": [...], ...}
"""
import os
import sys

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from hwpx_skeleton import (render as _render, list_templates,              # noqa: E402
                           inspect_template, TEMPLATE_SPECS)
from hwpx_skeleton.guides import get_writing_guide, GUIDED_TYPES          # noqa: E402
from hwpx_core.mdconv import convert_md                                    # noqa: E402

__all__ = ["render", "render_md", "convert_md", "list_templates",
           "inspect_template", "TEMPLATE_SPECS",
           "get_writing_guide", "GUIDED_TYPES"]


def render(*args, **kw):
    """`hwpx_skeleton.render` 그대로 — 다만 경고를 `warnings` 한 곳에 모은다.

    엔진은 규칙 경고(골격·종결·자수)를 `warnings` 에, 본문을 채우며 난 경고(표 마커·
    그림·붙임 분량)를 `body_result["warnings"]` 에 따로 싣는다. 스킬은 `warnings` 만
    보면 되도록 뒤의 것을 앞에 이어 붙인다(같은 줄은 한 번만).
    """
    res = _render(*args, **kw)
    br = res.get("body_result") if isinstance(res, dict) else None
    extra = br.get("warnings") if isinstance(br, dict) else None
    if extra:
        merged = list(res.get("warnings") or [])
        merged += [w for w in extra if w not in merged]
        res["warnings"] = merged
    return res


def render_md(md, tables=None, **kw):
    """**마크다운을 그대로 받아** 표준서식 hwpx 로 찍는다.

    `render()` 는 본문을 개조식 기호(□ ◦ *)로 받지만, 이쪽은 마크다운을 받아
    기계적으로 옮긴 뒤 렌더한다. 옮기는 규칙은 `hwpx_core.mdconv` 한 곳이 정한다
    (에이전트 도구와 **같은 변환**이다).

        | 표        → `[표N]` 마커 + 표 데이터를 뽑아 tables 로 넘긴다
        ## N. 제목  → `N. 제목`
        - 항목      → 들여쓰기 0 = □ · 2 = ◦ · 4 이상 = -
        > 참고      → `* 참고`

    Args:
        md: 마크다운 본문. 표·`[이미지N]`·인용(`>`)이 섞여 있어도 된다.
        tables: 손으로 넘길 표. 있으면 **앞에 놓이고**, md 에서 뽑은 표가 뒤에
            이어 붙는다(`[표N]` 번호도 그 순서로 매겨진다).
        **kw: `render()` 의 나머지 인자 그대로 — `template_key`(또는
            `template_path`) · `fields` · `images` · `intent` · `output_dir` 등.

    Returns:
        `render()` 와 같은 dict. `status`·`path`·`warnings` 를 그대로 본다.
    """
    given = list(tables or [])
    body, found = convert_md(md, table_offset=len(given))
    # 열 폭을 내용에 맞춘다(mcp/ 에이전트 도구와 같은 셈 · layout.table_ratios).
    #   기본 배분은 첫 열만 내용에 맞추고 나머지는 균등이라 긴 머리글이 두 줄로 접혔다.
    #   호출자가 col_ratios 를 준 표·도해(grid)는 그대로 둔다.
    try:
        from layout import table_ratios
    except Exception:                       # 재는 기계가 없어도 렌더는 한다
        table_ratios = None
    if table_ratios:
        for t in found:
            if isinstance(t, dict) and not t.get("col_ratios") and not t.get("grid"):
                r = table_ratios(t)
                if r:
                    t["col_ratios"] = r
    return render(body=body, tables=given + found, **kw)


if __name__ == "__main__":
    # 스모크: 사용 가능한 양식 목록
    for t in list_templates():
        print(f"- {t['key']}: {t.get('name', '')}")
