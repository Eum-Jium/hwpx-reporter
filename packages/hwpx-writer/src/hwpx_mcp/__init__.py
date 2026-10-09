"""HWPX 보고서 생성 MCP 서버."""
import hwpx_core as _core

# core 판 확인은 pyproject 핀이 아니라 여기서 한다 — 이유는 require_version 참조.
_core.require_version("hwpx-writer", "0.1")

__version__ = "0.1.1"
