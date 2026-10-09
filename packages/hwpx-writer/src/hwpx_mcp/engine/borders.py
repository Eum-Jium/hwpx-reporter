"""
borders.py — 정부문서 표 테두리 (16-상태 매트릭스).

kor_hwpx_generator/hwpx_renderer.py 의 hdr_bf/data_bf 선택 로직과
rebuild_template.py 의 borderFill 면별 스펙을 이식.
클론은 미리 구운 고정 ID를 썼지만, 여기서는 우리 엔진의 동적 borderFill로
동일한 "의미"를 표당 필요한 상태만 생성해 재사용한다.
"""
from __future__ import annotations

from .constants import BORDER_STATES
from .builder import _add_border_fill


def _row_position(ri: int, n_data_rows: int) -> str:
    """데이터행 위치 판정 → first / mid / last / only"""
    is_first = ri == 0
    is_last = ri == n_data_rows - 1
    if is_first and is_last:
        return "only"
    if is_first:
        return "first"
    if is_last:
        return "last"
    return "mid"


class GovTableBorders:
    """
    표 하나에 대한 16-상태 테두리 관리자.
    필요한 (행위치, 열위치) 상태의 borderFill만 동적 생성해 캐시.

    사용:
        gb = GovTableBorders(header_elem, has_header=True, n_data_rows=3, col_count=3)
        bf_id = gb.border_fill_id(row_index, col_index)  # 전체 표 기준 행 인덱스
    """

    def __init__(self, header_elem, has_header: bool, n_data_rows: int, col_count: int):
        self._header = header_elem
        self._has_header = has_header
        self._n_data_rows = n_data_rows
        self._col_count = col_count
        self._cache: dict = {}   # state_key → borderFill id

    def _state_key(self, row_index: int, col_index: int) -> tuple:
        is_last_col = (col_index == self._col_count - 1)
        col_pos = "l" if is_last_col else "nl"

        if self._has_header and row_index == 0:
            row_pos = "hdr_only" if self._n_data_rows == 0 else "header"
        else:
            data_ri = row_index - (1 if self._has_header else 0)
            row_pos = _row_position(data_ri, self._n_data_rows)
        return (row_pos, col_pos)

    def _make_fill(self, state_key: tuple) -> int:
        left, right, top, bottom, fill = BORDER_STATES[state_key]
        sides = {"left": left, "right": right, "top": top, "bottom": bottom}
        bg = fill if fill else "none"
        return _add_border_fill(self._header, bg_color=bg, border_sides=sides)

    def border_fill_id(self, row_index: int, col_index: int) -> int:
        key = self._state_key(row_index, col_index)
        if key not in self._cache:
            self._cache[key] = self._make_fill(key)
        return self._cache[key]
