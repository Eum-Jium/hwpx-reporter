# -*- coding: utf-8 -*-
"""쪽 분량 — 특히 이미지자리가 지면에서 먹는 높이.

종전에는 "이미지자리 1개 ≈ 170pt" 가 tools/README 산문에만 있었고 코드에도
시험에도 없었다. 2026-08-19 PDF 좌표 실측은 **202.5pt** 였다 — 검사가 없으면
산문은 틀린 채로 남는다.
"""
import pytest

from hwpx_core import volume as V


def test_placeholder_slot_matches_render():
    """자리표 이미지자리 = 그림칸 178.65 + 캡션칸 23.85 (PDF 가로선 y 355.5→534.0)."""
    assert V.IMG_SLOT_PT == pytest.approx(202.5)
    assert V.image_slot_pt() == pytest.approx(202.5)


def test_real_image_slot_follows_the_picture():
    """20mm 로 넣은 그림의 칸이 렌더에서 62.3pt 였다(모델값 62.35)."""
    assert V.image_slot_pt(20) - V.IMG_CAPTION_PT == pytest.approx(62.35, abs=0.1)


def test_taller_picture_costs_more_page():
    assert V.image_slot_pt(40) > V.image_slot_pt(20) > V.image_slot_pt(5)


def test_images_add_height():
    lines = ["□ 항목", "◦ 세부"]
    plain = V.height_bounds(lines)[1]
    withimg = V.height_bounds(lines, images=[{"height_mm": 20}])[1]
    assert withimg - plain == pytest.approx(V.image_slot_pt(20))


def test_marker_line_is_not_counted_twice():
    """'[이미지1]' 줄은 자리 표시일 뿐 한 줄을 먹지 않는다."""
    a = V.height_bounds(["□ 항목", "[이미지1]"], images=[{"height_mm": 20}])[1]
    b = V.height_bounds(["□ 항목"], images=[{"height_mm": 20}])[1]
    assert a == pytest.approx(b)


def test_marker_without_images_still_counts_the_line():
    """높이를 안 더했으면 줄도 빼지 않는다 — 안 그러면 실제보다 짧게 잡힌다."""
    a = V.height_bounds(["□ 항목", "[이미지1]"])[1]
    b = V.height_bounds(["□ 항목"])[1]
    assert a > b


def test_image_marker_matches_the_renderer():
    """core 와 renderer 가 같은 마커를 봐야 한다 — 갈리면 한쪽만 세고 만다."""
    from hwpx_skeleton import renderer
    for s in ("[이미지1]", "[그림2]", "[ 이미지 10 ]"):
        assert bool(V._IMG_MARK.match(s)) == bool(renderer._IMG_MARK.match(s))
    for s in ("[표1]", "이미지1", "[이미지]"):
        assert bool(V._IMG_MARK.match(s)) == bool(renderer._IMG_MARK.match(s))


def test_fills_page_sees_images():
    """그림이 큰 쪽은 글자가 적어도 '못 채운다' 고 하지 않는다."""
    lines = ["□ 항목", "[이미지1]"]
    assert not V.fills_page(lines)
    # 180mm 그림 하나면 판면(247mm)의 3분의 2를 넘는다 — 아래 여백 상한 안이다
    assert V.fills_page(lines, images=[{"height_mm": 180}])


def test_shortfall_shrinks_when_images_are_counted():
    lines = ["□ 항목", "[이미지1]"]
    assert V.shortfall_lines(lines, images=[{"height_mm": 100}]) < \
        V.shortfall_lines(lines)
