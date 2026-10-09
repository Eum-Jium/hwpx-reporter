# -*- coding: utf-8 -*-
"""hwpx-reader — HWPX 읽기 전용 MCP 서버 + 코어.

라이브러리로 쓰려면 core_* 함수를 직접 호출:
    from hwpx_reader import core
    core.core_read_text(path)
"""
import hwpx_core as _core

# core 판 확인은 pyproject 핀이 아니라 여기서 한다 — 이유는 require_version 참조.
_core.require_version("hwpx-reader", "0.1")

from . import core  # noqa: E402
from .core import HwpxReadError  # noqa: E402

__all__ = ["core", "HwpxReadError"]
__version__ = "0.2.0"
