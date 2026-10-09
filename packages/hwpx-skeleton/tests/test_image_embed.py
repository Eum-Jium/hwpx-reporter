# -*- coding: utf-8 -*-
"""실물 그림이 문서에 들어가는 두 길 — 이미지자리 칸과 표에 얹는 표장.

한/글 왕복·PDF 좌표로 확인한 결과를 코드가 지키는지 본다. 특히 **표에 얹는 그림은
표 문단 앞의 별도 문단에 매단다**는 것 — 같은 문단에 두면 표가 통째로 밀린다
(renderer._build_table_pics_p 주석에 실측 근거가 있다).
"""
import os
import zipfile

import pytest

from hwpx_skeleton import renderer as R
import hwpx_skeleton as HS

BODY = "\n".join([
    "1. 추진배경", " □ 그림", "[표1]", "[이미지1]",
    "2. 주요내용", " □ 내용", "3. 추진방안", " □ 방안",
    "4. 향후계획", " □ 추진 일정",
    "  ◦ 확인\t’26. 8. 19.", "  ◦ 반영\t’26. 8. 20.", "  ◦ 정리\t’26. 8. 21.",
])


@pytest.fixture(scope="module")
def logo(tmp_path_factory):
    """가로:세로 2:1 인 최소 PNG — 비율 유지 확인에 쓴다."""
    import struct
    import zlib

    def chunk(tag, body):
        return (len(body).to_bytes(4, "big") + tag + body
                + zlib.crc32(tag + body).to_bytes(4, "big"))
    w, h = 240, 120
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00" * (w * 4 + 1) * h))
            + chunk(b"IEND", b""))
    p = tmp_path_factory.mktemp("img") / "logo.png"
    p.write_bytes(data)
    return str(p)


def _render(tmp_path, **kw):
    res = HS.render("plan", {"title": "그림 시험"}, output_dir=str(tmp_path),
                    filename="t", body=BODY, **kw)
    assert res["status"] == "success", res
    return res, zipfile.ZipFile(res["path"])


def _placeholder_in(sec: str) -> bool:
    """자리표는 '<이미지 삽입>' 이라 XML 에서 &lt;…&gt; 로 이스케이프돼 있다."""
    import html
    return html.escape(R.IMG_PLACEHOLDER) in sec


def _pics(z):
    return z.read("Contents/section0.xml").decode("utf-8").count("<hp:pic")


def _bins(z):
    return [n for n in z.namelist() if n.startswith("BinData/")]


# ── 이미지자리에 실물 넣기 ────────────────────────────────────
def test_placeholder_stays_when_no_source(tmp_path):
    res, z = _render(tmp_path, images=[{"captions": ["구성도"]}])
    assert _pics(z) == 0 and not _bins(z)
    assert _placeholder_in(z.read("Contents/section0.xml").decode("utf-8"))


def test_real_image_replaces_placeholder(tmp_path, logo):
    res, z = _render(tmp_path, images=[{"captions": ["구성도"], "path": logo}])
    assert _pics(z) == 1
    assert _bins(z) == ["BinData/image1.png"]
    sec = z.read("Contents/section0.xml").decode("utf-8")
    assert not _placeholder_in(sec)   # 그림 옆에 자리표 글자가 남으면 안 된다
    assert "구성도" in sec                      # 캡션은 그대로


def test_one_image_used_twice_is_embedded_once(tmp_path, logo):
    res, z = _render(tmp_path, images=[
        {"captions": ["왼쪽", "오른쪽"], "sources": [{"path": logo}, {"path": logo}]}])
    assert _pics(z) == 2
    assert len(_bins(z)) == 1


def test_height_mm_is_honoured(tmp_path, logo):
    """20mm 를 주면 표시 높이가 20mm(5669 HWPUNIT)이고 원본 비율(2:1)을 지킨다."""
    res, z = _render(tmp_path, images=[{"path": logo, "height_mm": 20}])
    sec = z.read("Contents/section0.xml").decode("utf-8")
    i = sec.find("<hp:pic")
    import re
    sz = re.search(r'<hp:sz width="(\d+)"[^>]*height="(\d+)"', sec[i:]).groups()
    assert int(sz[1]) == pytest.approx(20 / 25.4 * 7200, abs=2)
    assert int(sz[0]) == pytest.approx(int(sz[1]) * 2, abs=2)


def test_missing_file_falls_back_with_a_reason(tmp_path):
    """조용히 빈 칸을 내지 않는다 — 자리표로 두고 사유를 남긴다."""
    res, z = _render(tmp_path, images=[{"path": str(tmp_path / "없다.png")}])
    assert _pics(z) == 0
    warns = res["body_result"]["warnings"]
    assert any("이미지1" in w and "실패" in w for w in warns), warns


# ── 표에 얹는 표장 ───────────────────────────────────────────
TBL = {"grid": {"rows": 8, "cols": 10}, "row_heights": [4] * 8,
       "cells": [{"r": 0, "c": 0, "text": "가", "borders": {"all": "SOLID 0.15"}}]}


def test_table_pics_go_in_their_own_paragraph_before_the_table(tmp_path, logo):
    """⚠️ 표와 같은 문단에 두면 표가 통째로 (+88.1pt, +20.8pt) 밀린다 — 실측.

    그래서 그림은 표 문단 **앞의 별도 문단**에 매단다. 이 시험이 깨지면 렌더는
    성공해도 지면에서 도해가 판면 밖으로 나간다.
    """
    tb = dict(TBL, pics=[{"path": logo, "x_mm": 20, "y_mm": 10, "height_mm": 4.3}])
    res, z = _render(tmp_path, tables=[tb])
    sec = z.read("Contents/section0.xml").decode("utf-8")
    assert _pics(z) == 1
    i, t = sec.find("<hp:pic"), sec.find('<hp:tbl id="2000000001"')
    assert 0 < i < t, "그림이 표 앞에 없다"
    # 그림과 표 사이에 문단 경계가 있어야 한다(같은 문단이면 밀린다)
    assert "</hp:p>" in sec[i:t], "그림이 표와 같은 문단에 있다"


def test_table_pic_is_floating(tmp_path, logo):
    """칸 안에 넣는 것이 아니라 얹는 것이다 — 상자 글자를 밀면 안 된다."""
    tb = dict(TBL, pics=[{"path": logo, "x_mm": 20, "y_mm": 10, "height_mm": 4.3}])
    res, z = _render(tmp_path, tables=[tb])
    sec = z.read("Contents/section0.xml").decode("utf-8")
    pic = sec[sec.find("<hp:pic"):sec.find("</hp:pic>")]
    assert 'treatAsChar="0"' in pic and 'horzRelTo="COLUMN"' in pic


def test_table_pic_y_is_measured_from_the_table_top(tmp_path, logo):
    """호출부는 표 윗변 기준으로 준다 — 원점인 그림 문단은 그보다 한 줄 높다."""
    tb = dict(TBL, pics=[{"path": logo, "x_mm": 0, "y_mm": 0, "height_mm": 4.3}])
    res, z = _render(tmp_path, tables=[tb])
    sec = z.read("Contents/section0.xml").decode("utf-8")
    pic = sec[sec.find("<hp:pic"):sec.find("</hp:pic>")]
    import re
    off = int(re.search(r'vertOffset="(\d+)"', pic).group(1))
    assert off == pytest.approx(R.TBL_PIC_ANCHOR_PT / 72 * 7200, abs=1)


def test_table_without_pics_gains_no_paragraph(tmp_path):
    """그림이 없으면 종전과 한 글자도 달라지면 안 된다."""
    a = _render(tmp_path / "a", tables=[TBL])[1]
    b = _render(tmp_path / "b", tables=[dict(TBL, pics=[])])[1]
    assert (a.read("Contents/section0.xml")
            == b.read("Contents/section0.xml"))


def test_bad_table_pic_is_reported_not_silent(tmp_path):
    tb = dict(TBL, pics=[{"path": "/없는/파일.png", "x_mm": 1, "y_mm": 1}])
    res, z = _render(tmp_path, tables=[tb])
    assert _pics(z) == 0
    warns = res["body_result"]["warnings"]
    assert any("얹을 그림" in w for w in warns), warns
