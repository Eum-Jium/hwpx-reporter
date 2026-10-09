# -*- coding: utf-8 -*-
"""그림 임베드 — 한/글 왕복으로 확인한 것들이 코드에 그대로 남아 있는지.

왕복 대조(`tools/verify/hwp_resave.py`)는 한/글이 있는 PC 에서만 돌아간다. 여기서는
그때 **확정된 결론**이 코드에서 어긋나지 않게 붙든다 — hashkey 를 안 적는다는 것,
글자처럼 놓인 그림의 textWrap, 치수 관계식.
"""
import xml.etree.ElementTree as ET
import zlib

import pytest

from hwpx_core import bindata as B


def _png(w: int, h: int) -> bytes:
    """최소한의 PNG — IHDR 만 정확하면 크기 판독에는 충분하다."""
    def chunk(tag, body):
        return (len(body).to_bytes(4, "big") + tag + body
                + zlib.crc32(tag + body).to_bytes(4, "big"))
    ihdr = w.to_bytes(4, "big") + h.to_bytes(4, "big") + bytes([8, 6, 0, 0, 0])
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00" * (w * 4 + 1) * h))
            + chunk(b"IEND", b""))


HPF = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
       b'<opf:package xmlns:opf="http://www.idpf.org/2007/opf/"'
       b' xmlns:dc="http://purl.org/dc/elements/1.1/"'
       b' xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
       b'<opf:manifest>'
       b'<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
       b'<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
       b'<opf:item id="settings" href="settings.xml" media-type="application/xml"/>'
       b'</opf:manifest></opf:package>')


def _members():
    return {B.CONTENT_HPF: HPF}


# ── 크기 판독 ────────────────────────────────────────────────
def test_png_size():
    assert B.image_size(_png(240, 120)) == (240, 120)


def test_gif_and_bmp_size():
    gif = b"GIF89a" + (64).to_bytes(2, "little") + (32).to_bytes(2, "little") + b"\x00" * 8
    assert B.image_size(gif) == (64, 32)
    bmp = b"BM" + b"\x00" * 16 + (30).to_bytes(4, "little") + (20).to_bytes(4, "little")
    assert B.image_size(bmp) == (30, 20)


def test_not_an_image_is_refused():
    with pytest.raises(B.BinDataError):
        B.load_bytes({"b64": "aGVsbG8="})          # 'hello' — 그림이 아니다


def test_dim_is_96dpi():
    # imgDim = 원본 픽셀 ÷ 96 × 7200 (정본 image2 실측: 842px → 63180)
    assert B.px_to_hwpunit(842) == 63150          # 정본 63180 과 반올림 차이
    assert B.px_to_hwpunit(240) == 18000


# ── BinData 등록 ─────────────────────────────────────────────
def test_add_image_registers_member_and_manifest():
    m = _members()
    item = B.add_image(m, _png(10, 10))
    assert item == "image1"
    assert "BinData/image1.png" in m
    hpf = m[B.CONTENT_HPF].decode("utf-8")
    assert '<opf:item id="image1" href="BinData/image1.png"' in hpf
    assert 'isEmbeded="1"' in hpf
    # 정본 순서 — header 다음, section0 앞
    assert hpf.index('id="image1"') < hpf.index('id="section0"')


def test_hashkey_is_not_written():
    """한/글은 hashkey 를 요구하지 않는다 — 왕복으로 확인했다(bindata 첫머리).

    만들 방법을 모르는 값이라 지어내면 안 된다. 넣지 않는 것이 확인된 답이다.
    """
    m = _members()
    B.add_image(m, _png(4, 4))
    assert b"hashkey" not in m[B.CONTENT_HPF]


def test_same_bytes_are_embedded_once():
    """정본은 로고 하나를 열두 군데 쓴다 — 멤버는 하나여야 한다."""
    m = _members()
    data = _png(8, 8)
    assert B.add_image(m, data) == B.add_image(m, data) == "image1"
    assert len([k for k in m if k.startswith("BinData/")]) == 1


def test_different_bytes_get_new_ids():
    m = _members()
    assert B.add_image(m, _png(8, 8)) == "image1"
    assert B.add_image(m, _png(9, 9)) == "image2"


def test_manifest_keeps_unused_xmlns():
    """등록하면서 루트의 안 쓰이는 xmlns 선언을 잃으면 구버전 한/글이 안 연다."""
    m = _members()
    B.add_image(m, _png(4, 4))
    out = m[B.CONTENT_HPF]
    for decl in (b'xmlns:dc="', b'xmlns:hpf="', b'xmlns:opf="'):
        assert decl in out


def test_unsupported_format_refused():
    m = _members()
    with pytest.raises(B.BinDataError):
        B.add_image(m, b"not an image at all")


# ── hp:pic ───────────────────────────────────────────────────
def test_pic_has_every_required_part():
    """정본 실측 목록. 넷(effects·sz·pos·outMargin)이 종전 writer 에서 빠져 있었다."""
    el = B.pic_element("image1", 4000, 2000, px_w=240, px_h=120)
    names = [c.tag.rsplit("}", 1)[-1] for c in el]
    assert names == ["offset", "orgSz", "curSz", "flip", "rotationInfo",
                     "renderingInfo", "img", "imgRect", "imgClip", "inMargin",
                     "imgDim", "effects", "sz", "pos", "outMargin"]


def test_pic_size_and_scale():
    el = B.pic_element("image1", 4000, 2000, px_w=240, px_h=120)
    q = {c.tag.rsplit("}", 1)[-1]: c for c in el}
    assert q["imgDim"].attrib == {"dimwidth": "18000", "dimheight": "9000"}
    assert q["sz"].get("width") == "4000" and q["sz"].get("height") == "2000"
    assert q["curSz"].attrib == {"width": "4000", "height": "2000"}
    # scaMatrix = 표시 ÷ 원본 (정본 image2: 1926/20280 = 0.09497)
    sca = [c for c in q["renderingInfo"] if c.tag.endswith("scaMatrix")][0]
    assert float(sca.get("e1")) == pytest.approx(4000 / 18000, abs=1e-6)
    assert float(sca.get("e5")) == pytest.approx(2000 / 9000, abs=1e-6)


def test_inline_pic_uses_the_wrap_hangul_normalizes_to():
    """글자처럼 놓인 그림에 IN_FRONT_OF_TEXT 를 쓰면 한/글이 고쳐서 돌려준다.

    왕복에서 TOP_AND_BOTTOM 으로 바뀌어 돌아왔으므로 처음부터 그렇게 쓴다 —
    안 그러면 왕복 대조가 매번 '다르게 읽었다'로 뜬다.
    """
    inline = B.pic_element("image1", 100, 100, treat_as_char=True)
    floating = B.pic_element("image1", 100, 100, treat_as_char=False)
    assert inline.get("textWrap") == "TOP_AND_BOTTOM"
    assert floating.get("textWrap") == "IN_FRONT_OF_TEXT"


def test_pos_relates_to_para_and_column():
    """띄우기의 가로 기준은 판면(COLUMN), 세로는 문단(PARA) — PDF 좌표로 확인했다."""
    el = B.pic_element("image1", 100, 100, treat_as_char=False,
                       horz_offset=30000, vert_offset=2000)
    pos = [c for c in el if c.tag.endswith("pos")][0]
    assert pos.get("treatAsChar") == "0"
    assert pos.get("horzRelTo") == "COLUMN" and pos.get("vertRelTo") == "PARA"
    assert pos.get("horzOffset") == "30000" and pos.get("vertOffset") == "2000"


def test_pic_xml_parses_standalone():
    """세 렌더 경로가 각자 자기 파서로 읽는다 — 홀로도 파싱돼야 한다."""
    ET.fromstring(B.pic_xml("image1", 100, 50))


def test_module_loads_as_a_bare_file():
    """모드 B 방식 — 패키지 문맥 없이 **파일 하나만** importlib 로 적재해도 돌아야 한다.

    `from . import xmlcompat` 만 두었다가 이 경로에서 ImportError 가 났다. 지금
    코드는 패키지로만 임포트되니 드러나지 않았을 뿐이고, 누가 이 모듈을
    `hwpx_full._load_core_module` 목록에 올리면 그 자리에서 터질 물건이었다.
    """
    import importlib.util
    import pathlib

    path = pathlib.Path(B.__file__)
    spec = importlib.util.spec_from_file_location("_bare_bindata", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                 # 여기서 터지면 회귀다
    assert mod.px_to_hwpunit(240) == 18000
    # xmlcompat 이 필요한 길까지 실제로 밟아 본다(등록은 그것 없이는 못 한다)
    members = {B.CONTENT_HPF: HPF}
    assert mod.add_image(members, _png(4, 4)) == "image1"
    assert b"hashkey" not in members[B.CONTENT_HPF]


def test_fit_box_keeps_ratio():
    assert B.fit_box(240, 120, 0, 2000) == (4000, 2000)
    assert B.fit_box(240, 120, 3000, 0) == (3000, 1500)
    # 둘 다 주면 더 조이는 쪽을 따른다
    assert B.fit_box(240, 120, 3000, 2000) == (3000, 1500)
