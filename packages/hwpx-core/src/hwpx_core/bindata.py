# -*- coding: utf-8 -*-
"""그림 임베드 — BinData 멤버 등록과 `hp:pic` 조립.

**stdlib 만 쓰고, 파일 하나로도 실린다** — gaps.py·markers.py·tablespec.py 와 같은
이유다. 스킬 모드 B 는 `vendor/hwpx_core/*.py` 를 importlib 로 **파일째** 적재할 수
있어야 한다(패키지 문맥 없이). 이 모듈은 `xmlcompat` 이 필요해 처음에는
`from . import xmlcompat` 만 두었는데, 그러면 파일째 적재에서 `ImportError` 가 난다
— 지금 경로는 패키지로 임포트하니 드러나지 않았을 뿐이고, 누가 이 모듈을
`_load_core_module` 목록에 올리는 순간 터질 물건이었다. 아래에서 두 길을 다 연다.

`hp:pic` 를 문자열로 내는 것도 같은 이유다. 렌더 경로가 셋(skeleton·모드 B·writer)
인데 writer 만 lxml 이라 Element 를 그대로 건네줄 수 없다. 문자열이면 각자 자기
파서로 읽어 붙이면 되고, **틀은 한 벌**로 남는다 — 같은 버그 클래스가 여러 경로에
흩어지는 것이 이 리포의 상습 함정이었다.

## 실측 근거 (2026-08-19, `hwp_resave` 왕복 + PDF 좌표)

정본 견본에서 읽은 구조를 그대로 세워 한/글에 되물었다. 파일이 열리는 것만으로는
판정이 안 된다 — 한/글이 인식 못 한 조각은 조용히 사라지므로 재저장본에 남는지가
유일한 증명이다. 그림 2개(글자처럼 하나·띄우기 하나)를 넣어 확인한 것:

- **`hashkey` 는 안 넣어도 된다.** 정본에는 `hashkey="2D3mgf6JM6LJ/0HaUe+jLQ=="`
  같은 16바이트 값이 붙어 있는데 파일 바이트의 md5 도 sha1 도 아니라 만들 방법을
  몰랐다. 빼고 넣었더니 한/글이 그림을 그대로 읽고, 재저장할 때도 **안 붙였다**.
  BinData 바이트도 3814 → 3814 로 동일하다. 즉 한/글이 요구하지 않는 값이다.
- **`imgDim` 은 한/글이 재저장 때 버린다.** 우리가 쓴 것을 읽기는 해도 자기가
  다시 쓸 때는 안 적는다. 정본에는 있으므로 그대로 적되, 왕복 대조에서 이것이
  사라진 것은 실패가 아니다.
- **`treatAsChar="1"` 이면 `textWrap` 이 `TOP_AND_BOTTOM` 으로 정규화된다.**
  `IN_FRONT_OF_TEXT` 로 써 넣었더니 한/글이 고쳐서 돌려줬다(글자처럼 놓인 그림은
  글자 앞에 뜰 수 없으니 당연하다). 그래서 처음부터 그렇게 쓴다.
- 그 밖(`orgSz`·`curSz`·`imgClip`·`sz`·`scaMatrix`·`binaryItemIDRef`)은 쓴 값이
  그대로 돌아왔다.

## 치수 관계 (정본 image2 실측 + PDF 좌표 확인)

- `imgDim` = 원본 픽셀 ÷ 96dpi × 7200  (842px → 63180)
- `scaMatrix` e1/e5 = `curSz` ÷ `orgSz`  (1926/20280 = 0.09497)
- `imgRect` = (0,0)~(orgSz), 안 자른 그림의 `imgClip` = (0,0)~(imgDim)
- `rotationInfo` center = `curSz` ÷ 2
- **지면에 나오는 크기는 `hp:sz`(=`curSz`)가 정한다** — 4000×2000 HWPUNIT 로 쓴
  그림이 PDF 에서 정확히 14.1×7.1mm 로 나왔다(4000/7200×25.4 = 14.11).
- 띄우기(`treatAsChar="0"`)의 원점: `horzRelTo="COLUMN"` 은 **판면 왼쪽**,
  `vertRelTo="PARA"` 는 **그 문단의 위**다. horzOffset 30000 을 준 그림이 판면
  왼끝(56.6pt)에서 300pt 떨어진 356.4pt 에 앉았다(30000/7200×72 = 300).
"""
from __future__ import annotations

import struct
from typing import Dict, Optional, Tuple

try:                                  # 패키지로 임포트될 때 — 평소의 길
    from . import xmlcompat
except ImportError:                   # 파일째 적재될 때(모드 B 방식) — 옆 파일을 직접 읽는다
    # ⚠️ `import xmlcompat` 로 적지 않는다. 그러면 sys.path 어딘가의 **남의**
    #    xmlcompat 을 물 수 있다. 이 파일 옆의 것만 경로로 집어 온다.
    import importlib.util as _ilu
    import os as _os

    _spec = _ilu.spec_from_file_location(
        "_hwpx_xmlcompat", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                         "xmlcompat.py"))
    xmlcompat = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(xmlcompat)

CONTENT_HPF = "Contents/content.hpf"
BINDATA_DIR = "BinData/"

# HWPUNIT = 1/7200 inch. 그림 원본 픽셀은 96dpi 로 환산한다(정본 실측과 일치).
HWPUNIT_PER_INCH = 7200
IMAGE_DPI = 96

# 정본 content.hpf 가 쓰는 media-type 표기 그대로. jpeg 는 `image/jpg` 다
# (표준 MIME 은 image/jpeg 지만 한/글이 적는 값은 이쪽이다 — 실측).
MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpg",
    "jpeg": "image/jpg",
    "gif": "image/gif",
    "bmp": "image/bmp",
}

_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)


class BinDataError(Exception):
    """그림 임베드 실패(형식 불명·크기 판독 불가 등)."""


# ── 그림 파일 판독 (외부 의존 없이) ────────────────────────────
def sniff_format(data: bytes) -> Optional[str]:
    """매직바이트로 그림 형식 판정. 그림이 아니면 None."""
    for magic, fmt in _MAGIC:
        if data.startswith(magic):
            return fmt
    return None


def image_size(data: bytes) -> Tuple[int, int]:
    """그림의 원본 픽셀 (가로, 세로). 판독 못 하면 BinDataError.

    `imgDim` 을 세우려면 픽셀 수가 필요한데 그것 하나 때문에 Pillow 를 끌어올 수는
    없다(core 는 stdlib 전용이다). 네 형식의 머리만 읽는다.
    """
    fmt = sniff_format(data)
    if fmt == "png":
        # IHDR 은 언제나 첫 청크다: 8(시그니처) + 4(길이) + 4('IHDR') 뒤에 w,h
        if len(data) >= 24 and data[12:16] == b"IHDR":
            return struct.unpack(">II", data[16:24])
    elif fmt == "gif":
        if len(data) >= 10:
            return struct.unpack("<HH", data[6:10])
    elif fmt == "bmp":
        if len(data) >= 26:
            return tuple(abs(v) for v in struct.unpack("<ii", data[18:26]))
    elif fmt == "jpg":
        return _jpeg_size(data)
    raise BinDataError("그림 크기를 읽지 못했다(형식 불명이거나 잘린 파일)")


def _jpeg_size(data: bytes) -> Tuple[int, int]:
    """JPEG 세그먼트를 훑어 SOFn 에서 크기를 읽는다."""
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        # SOFn — 단 DHT(C4)·JPG(C8)·DAC(CC) 는 크기가 아니다
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seg_len
    raise BinDataError("JPEG 에서 크기(SOF)를 찾지 못했다")


def load_bytes(block) -> Tuple[bytes, str]:
    """`{"path": …}` 또는 `{"b64": …}` 에서 (바이트, 형식)을 꺼낸다.

    세 렌더 경로가 같은 입력 모양을 받게 하려고 여기 둔다. 문자열을 그냥 주면
    경로로 읽는다(에이전트가 흔히 그렇게 낸다).
    """
    import base64
    import os

    if isinstance(block, (bytes, bytearray)):
        data = bytes(block)
    else:
        if isinstance(block, str):
            block = {"path": block}
        if not isinstance(block, dict):
            raise BinDataError("그림 자리에 경로도 b64 도 없다")
        if block.get("path"):
            path = os.path.abspath(str(block["path"]))
            if not os.path.isfile(path):
                raise BinDataError(f"그림 파일 없음: {path}")
            with open(path, "rb") as f:
                data = f.read()
        elif block.get("b64"):
            try:
                data = base64.b64decode(str(block["b64"]), validate=True)
            except Exception:
                raise BinDataError("b64 가 올바른 base64 가 아니다")
        else:
            raise BinDataError("그림 자리에 경로도 b64 도 없다")

    fmt = sniff_format(data)
    if fmt is None:
        # 확장자만 믿지 않는다 — 매직바이트가 아니면 한/글이 조용히 빈 칸을 낸다
        raise BinDataError("그림 파일이 아니다(매직바이트 불일치)")
    return data, fmt


def px_to_hwpunit(px: int, dpi: int = IMAGE_DPI) -> int:
    """원본 픽셀 → HWPUNIT. `imgDim` 은 96dpi 기준이다(정본 실측)."""
    return int(round(px / dpi * HWPUNIT_PER_INCH))


def mm_to_hwpunit(mm: float) -> int:
    """mm → HWPUNIT."""
    return int(round(mm / 25.4 * HWPUNIT_PER_INCH))


def hwpunit_to_mm(hu: int) -> float:
    """HWPUNIT → mm."""
    return hu / HWPUNIT_PER_INCH * 25.4


# ── BinData 등록 ──────────────────────────────────────────────
def item_ids(members: Dict[str, bytes]) -> Dict[str, str]:
    """이미 등록된 {binaryItemID: 멤버경로}. 같은 그림을 두 번 넣지 않으려고 쓴다."""
    hpf = members.get(CONTENT_HPF)
    if not hpf:
        return {}
    root = xmlcompat.parse(hpf)
    out = {}
    for el in root.iter():
        if xmlcompat.local_name(el) != "item":
            continue
        href = el.get("href") or ""
        if href.startswith(BINDATA_DIR):
            out[el.get("id") or ""] = href
    return out


def add_image(members: Dict[str, bytes], data: bytes, fmt: str = "",
              item_id: str = "") -> str:
    """그림 바이트를 zip 멤버로 넣고 `content.hpf` 의 opf:manifest 에 등록한다.

    members 를 **제자리에서** 고치고 `binaryItemIDRef` 로 쓸 id 를 반환한다.
    같은 바이트가 이미 들어 있으면 그 id 를 그대로 준다(로고 하나를 열두 군데
    쓰는 것이 정본의 방식이라 중복 적재를 막는 편이 실익이 크다).

    `hashkey` 는 **일부러 안 적는다** — 모듈 첫머리의 실측 근거 참조.
    """
    if CONTENT_HPF not in members:
        raise BinDataError(f"{CONTENT_HPF} 가 없는 문서에는 그림을 넣을 수 없다")
    fmt = (fmt or sniff_format(data) or "").lower()
    if fmt not in MEDIA_TYPES:
        raise BinDataError(
            f"지원하지 않는 그림 형식: {fmt or '판독 실패'} "
            f"(허용: {sorted(set(MEDIA_TYPES))})")

    existing = item_ids(members)
    for eid, href in existing.items():
        if members.get(href) == data:
            return eid

    if not item_id:
        n = 1
        while f"image{n}" in existing:
            n += 1
        item_id = f"image{n}"
    if item_id in existing:
        raise BinDataError(f"이미 쓰이는 그림 id: {item_id}")

    # 정본은 확장자를 대문자로 적지만(`image1.PNG`) 한/글은 우리가 적은 소문자
    # 경로도 그대로 읽고 되돌려줬다(왕복 실측) — 소문자로 통일한다.
    href = f"{BINDATA_DIR}{item_id}.{fmt}"
    members[href] = data
    _register_item(members, item_id, href, MEDIA_TYPES[fmt])
    return item_id


def _register_item(members: Dict[str, bytes], item_id: str, href: str,
                   media_type: str) -> None:
    """opf:manifest 에 `<opf:item …/>` 를 끼운다.

    ⚠️ 자리는 **content.hpf 의 opf:manifest** 다 — header.xml 이 아니다. 정본
    header.xml 에는 binDataList 자체가 없었다(writer 의 옛 주석이 그쪽을 가리켰다).
    정본 순서를 따라 `section0` 앞, 즉 header 다음에 넣는다.

    `like=` 로 원본 바이트를 준다 — 안 주면 안 쓰이는 xmlns 선언이 빠져 구버전
    한/글이 파일을 아예 안 연다(`xmlcompat._restore_xmlns` 주석과 같은 함정이다).
    """
    src = members[CONTENT_HPF]
    root = xmlcompat.parse(src)
    manifest = None
    for el in root.iter():
        if xmlcompat.local_name(el) == "manifest":
            manifest = el
            break
    if manifest is None:
        raise BinDataError("content.hpf 에 opf:manifest 가 없다")

    uri = xmlcompat.uri_of(manifest)
    tag = f"{{{uri}}}item" if uri else "item"
    item = xmlcompat.ET.Element(tag, {
        "id": item_id, "href": href, "media-type": media_type,
        "isEmbeded": "1",
    })
    at = len(manifest)
    for i, el in enumerate(manifest):
        if (el.get("href") or "").startswith("Contents/section"):
            at = i
            break
    manifest.insert(at, item)
    members[CONTENT_HPF] = xmlcompat.serialize(root, like=src)


# ── hp:pic 조립 ───────────────────────────────────────────────
def pic_xml(item_id: str, width: int, height: int,
            px_w: int = 0, px_h: int = 0,
            org_w: int = 0, org_h: int = 0,
            treat_as_char: bool = True,
            vert_offset: int = 0, horz_offset: int = 0,
            horz_rel_to: str = "",
            obj_id: int = 0, z_order: int = 0,
            hp: str = xmlcompat.HP_DEFAULT,
            hc: str = xmlcompat.HC_DEFAULT) -> str:
    """`<hp:pic>` 한 개를 XML 문자열로 낸다. 각 렌더 경로가 자기 파서로 읽어 붙인다.

    Args:
        item_id: `add_image` 가 준 id (`binaryItemIDRef`)
        width, height: **지면에 나올 크기**(HWPUNIT). 이 값이 곧 렌더 크기다
        px_w, px_h: 원본 픽셀. 주면 `imgDim` 을 세운다(안 주면 표시 크기로 대신)
        org_w, org_h: 삽입 당시 크기. 기본은 `imgDim` — 그러면 scaMatrix 가
            표시÷원본이 되어 정본과 같은 모양이 된다
        treat_as_char: True = 글자처럼(본문 흐름 안), False = 띄우기(칸 위에 얹기)
        vert_offset, horz_offset: 띄우기일 때 문단 위·판면 왼쪽에서의 거리(HWPUNIT)
        horz_rel_to: 가로 기준. 기본은 띄우기 `COLUMN`(판면) · 글자처럼 `PARA`
        obj_id: 도형 식별자. 한 문서 안에서만 겹치지 않으면 된다
    """
    dim_w = px_to_hwpunit(px_w) if px_w else int(width)
    dim_h = px_to_hwpunit(px_h) if px_h else int(height)
    org_w = int(org_w) or dim_w
    org_h = int(org_h) or dim_h
    width, height = int(width), int(height)
    obj_id = int(obj_id) or 1
    tac = 1 if treat_as_char else 0
    # 글자처럼 놓인 그림은 글자 앞에 뜰 수 없다 — 한/글이 그렇게 고쳐 돌려줬으므로
    # 처음부터 그 값으로 쓴다(모듈 첫머리 실측 참조).
    wrap = "TOP_AND_BOTTOM" if tac else "IN_FRONT_OF_TEXT"
    rel = horz_rel_to or ("PARA" if tac else "COLUMN")
    sca_x = round(width / org_w, 6) if org_w else 1
    sca_y = round(height / org_h, 6) if org_h else 1

    return (
        '<hp:pic xmlns:hp="%s" xmlns:hc="%s" id="%d" zOrder="%d"'
        ' numberingType="PICTURE" textWrap="%s" textFlow="BOTH_SIDES" lock="0"'
        ' dropcapstyle="None" href="" groupLevel="0" instid="%d" reverse="0">'
        '<hp:offset x="0" y="0"/>'
        '<hp:orgSz width="%d" height="%d"/>'
        '<hp:curSz width="%d" height="%d"/>'
        '<hp:flip horizontal="0" vertical="0"/>'
        '<hp:rotationInfo angle="0" centerX="%d" centerY="%d" rotateimage="1"/>'
        '<hp:renderingInfo>'
        '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:scaMatrix e1="%s" e2="0" e3="0" e4="0" e5="%s" e6="0"/>'
        '<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '</hp:renderingInfo>'
        '<hc:img binaryItemIDRef="%s" bright="0" contrast="0" effect="REAL_PIC"'
        ' alpha="0"/>'
        '<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="%d" y="0"/>'
        '<hc:pt2 x="%d" y="%d"/><hc:pt3 x="0" y="%d"/></hp:imgRect>'
        '<hp:imgClip left="0" right="%d" top="0" bottom="%d"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        '<hp:imgDim dimwidth="%d" dimheight="%d"/>'
        '<hp:effects/>'
        '<hp:sz width="%d" widthRelTo="ABSOLUTE" height="%d"'
        ' heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="%d" affectLSpacing="0" flowWithText="1"'
        ' allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="%s"'
        ' vertAlign="TOP" horzAlign="LEFT" vertOffset="%d" horzOffset="%d"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '</hp:pic>'
        % (hp, hc, obj_id, int(z_order), wrap, obj_id, org_w, org_h,
           width, height, width // 2, height // 2, sca_x, sca_y, item_id,
           org_w, org_w, org_h, org_h, dim_w, dim_h, dim_w, dim_h,
           width, height, tac, rel, int(vert_offset), int(horz_offset)))


def pic_element(item_id: str, width: int, height: int, **kw):
    """`pic_xml` 을 ElementTree 요소로. stdlib 경로(skeleton·모드 B)가 쓴다.

    lxml 경로(writer)는 자기 파서로 `pic_xml()` 문자열을 읽어야 한다 — 파서가
    다른 트리에 남의 요소를 붙일 수는 없다.
    """
    return xmlcompat.ET.fromstring(pic_xml(item_id, width, height, **kw))


def fit_box(px_w: int, px_h: int, max_w: int = 0, max_h: int = 0) -> Tuple[int, int]:
    """원본 비율을 지키며 상자 안에 맞춘 표시 크기(HWPUNIT).

    상한을 하나만 주면 그쪽에만 맞춘다. 둘 다 안 주면 원본 크기(96dpi 환산).
    """
    w, h = px_to_hwpunit(px_w), px_to_hwpunit(px_h)
    if not w or not h:
        raise BinDataError("원본 픽셀이 0 이다")
    scale = min([s for s in (max_w / w if max_w else None,
                             max_h / h if max_h else None) if s] or [1.0])
    return max(1, int(round(w * scale))), max(1, int(round(h * scale)))
