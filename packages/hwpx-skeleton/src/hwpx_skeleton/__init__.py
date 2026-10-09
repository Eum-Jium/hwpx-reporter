# -*- coding: utf-8 -*-
"""hwpx-skeleton — 공공기관 표준서식 HWPX 스켈레톤 렌더 엔진.

결정론적 렌더 엔진만 제공한다(LLM 방어로직 없음 — 그건 정책 계층 담당).
공개 API:
    render(template_key, fields, output_dir=None, body=None, intent=None)
    render(template_path='내양식.hwpx', ...)   # 밖에서 가져온 양식
    inspect_template(path)                     # 양식으로 쓸 수 있는지 진단
    list_templates()
    get_writing_guide(template_key)
    TEMPLATE_SPECS, GUIDED_TYPES, GUIDELINES_DIR
"""
import hwpx_core as _core

# core 판 확인은 pyproject 핀이 아니라 여기서 한다 — 이유는 require_version 참조.
_core.require_version("hwpx-skeleton", "0.1")

from .renderer import render, list_templates, inspect_template, TEMPLATE_SPECS  # noqa: E402
from .guides import get_writing_guide, GUIDED_TYPES, GUIDELINES_DIR  # noqa: E402

__all__ = [
    "render", "list_templates", "inspect_template", "TEMPLATE_SPECS",
    "get_writing_guide", "GUIDED_TYPES", "GUIDELINES_DIR",
]
__version__ = "0.3.3"
