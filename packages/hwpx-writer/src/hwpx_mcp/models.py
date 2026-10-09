"""
models.py — 입력 검증 + 응답 헬퍼.

FastMCP는 함수 시그니처로 스키마를 만들지만, 여기서 문서 도메인 규칙
(직사각형 표, hex 색상, report_type 등)을 방어적으로 검증한다.
"""
from __future__ import annotations

import re
from typing import Any

REPORT_TYPES = {"기획", "현황", "회의", "행사"}
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ValidationError(Exception):
    """도구 입력 검증 실패."""


def ok(**kw) -> dict:
    d = {"status": "success"}
    d.update(kw)
    return d


def err(stage: str, message: str, **kw) -> dict:
    d = {"status": "error", "stage": stage, "message": message}
    d.update(kw)
    return d


def validate_hex(color: str, field: str = "color"):
    if color in (None, "", "none"):
        return
    if not _HEX_RE.match(str(color)):
        raise ValidationError(f"{field} 는 #RRGGBB 형식이어야 함: {color!r}")


def validate_report_type(rt: str):
    if rt not in REPORT_TYPES:
        raise ValidationError(f"report_type 은 {sorted(REPORT_TYPES)} 중 하나여야 함: {rt!r}")


def _validate_cell_scalar(v, where: str):
    # 통과시키면 렌더의 str() 이 "{'a': 1}" 류를 문서에 그대로 박는다(응답은 success)
    if isinstance(v, (dict, list, tuple, set)):
        raise ValidationError(
            f"{where} 는 문자·숫자여야 함(객체/배열 불가): {type(v).__name__}")


def validate_table(headers, rows):
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise ValidationError("headers/rows 는 리스트여야 함")
    if not headers and not rows:
        raise ValidationError("표에 headers 또는 rows 중 하나는 있어야 함")
    ncol = len(headers) if headers else (len(rows[0]) if rows else 0)
    if ncol == 0:
        raise ValidationError("표 열 개수가 0")
    for j, h in enumerate(headers):
        _validate_cell_scalar(h, f"headers[{j}]")
    for i, r in enumerate(rows):
        if not isinstance(r, list):
            raise ValidationError(f"rows[{i}] 는 리스트여야 함")
        if len(r) != ncol:
            raise ValidationError(
                f"rows[{i}] 열 수 불일치: {len(r)} (기대 {ncol}). "
                f"모든 행의 열 수가 같아야 함(직사각형).")
        for j, c in enumerate(r):
            _validate_cell_scalar(c, f"rows[{i}][{j}]")
    return ncol


def validate_merge(r1, c1, r2, c2, n_rows, n_cols):
    for name, v in (("r1", r1), ("c1", c1), ("r2", r2), ("c2", c2)):
        if not isinstance(v, int):
            raise ValidationError(f"{name} 는 정수여야 함")
    if not (0 <= r1 <= r2 < n_rows) or not (0 <= c1 <= c2 < n_cols):
        raise ValidationError(
            f"병합 범위 오류 (r1{r1},c1{c1})-(r2{r2},c2{c2}) / 표 {n_rows}x{n_cols}")
    if r1 == r2 and c1 == c2:
        raise ValidationError("병합 범위가 단일 셀 — 최소 2셀 이상이어야 함")


_CELL_ALIGNS = {"LEFT", "CENTER", "RIGHT", "JUSTIFY"}


def validate_cell_style(cell: dict, n_rows: int, n_cols: int):
    if not isinstance(cell, dict):
        raise ValidationError("cell 은 객체여야 함")
    r, c = cell.get("row"), cell.get("col")
    if not isinstance(r, int) or not isinstance(c, int):
        raise ValidationError("cell.row / cell.col 은 정수여야 함")
    if not (0 <= r < n_rows) or not (0 <= c < n_cols):
        raise ValidationError(f"cell 위치 범위 초과 ({r},{c}) / 표 {n_rows}x{n_cols}")
    if cell.get("bg"):
        validate_hex(cell["bg"], "cell.bg")
    if cell.get("text_color"):
        validate_hex(cell["text_color"], "cell.text_color")
    align = cell.get("align")
    if align is not None and align not in _CELL_ALIGNS:
        raise ValidationError(f"cell.align 은 {sorted(_CELL_ALIGNS)} 중 하나여야 함: {align!r}")
    bold = cell.get("bold")
    if bold is not None and not isinstance(bold, bool):
        raise ValidationError(f"cell.bold 는 true/false 여야 함: {bold!r}")
    fs = cell.get("font_size")
    if fs is not None:
        # 문자열이 통과하면 pt_to_hwp 의 "12"*100 문자열 반복으로 서식이 파괴됨
        if isinstance(fs, bool) or not isinstance(fs, (int, float)) or not (6 <= fs <= 72):
            raise ValidationError(f"cell.font_size 는 6~72 숫자여야 함: {fs!r}")


def validate_col_ratios(col_ratios, n_cols: int):
    if not isinstance(col_ratios, list):
        raise ValidationError("col_ratios 는 리스트여야 함")
    if len(col_ratios) != n_cols:
        raise ValidationError(
            f"col_ratios 길이 불일치: {len(col_ratios)} (표 열 수 {n_cols})")
    for i, r in enumerate(col_ratios):
        if isinstance(r, bool) or not isinstance(r, (int, float)) or r <= 0:
            raise ValidationError(f"col_ratios[{i}] 는 양수여야 함: {r!r}")
