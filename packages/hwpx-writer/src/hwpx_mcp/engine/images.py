"""
images.py — 이미지 임베딩.

python-hwpx의 add_image(bytes, fmt)가 BinData 기록 + manifest 등록을 처리한다
(그 함수는 header binDataList 에도 적는데, 정본 한/글 문서에는 그 목록이 아예 없다 —
등록 자리는 **content.hpf 의 opf:manifest** 다. 남겨 두어도 한/글이 문제 삼지 않는
것은 왕복으로 확인했다).

`<hp:pic>` 은 **hwpx_core.bindata 가 낸 것을 그대로 쓴다.** 종전 이 파일의
`_emit_pic_run` 은 `effects`·`sz`·`pos`·`outMargin` 이 통째로 빠져 있어 한/글이
조용히 버릴 물건이었고, 그래서 EMBED_PIC 이 기본 꺼짐이었다. 이제 세 렌더 경로
(skeleton·모드 B·writer)가 **한 벌의 틀**을 쓴다 — 같은 버그 클래스를 경로마다
따로 고치던 것이 이 리포의 상습 함정이었다.

검증(2026-08-19): `tools/verify/hwp_resave.py` 왕복에서 그림·BinData·opf:item 이
그대로 살아 돌아왔고 `hashkey` 는 없어도 됐다. 근거는 `hwpx_core/bindata.py` 첫머리.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from lxml import etree as LET
from hwpx_core import bindata as BD
from .builder import CellFmt, _hp
from .constants import FONT_TABLE, SIZE_REF, mm

logger = logging.getLogger("hwpx_mcp.engine")

# 한/글 왕복 대조로 구조를 확인한 뒤 기본을 켬으로 돌렸다(위 주석 참조).
# 실패해도 캡션 박스 자리표로 떨어지므로 문서가 깨지지는 않는다.
EMBED_PIC = True

# 이미지 소스 제한: LLM 이 임의 로컬 파일을 문서에 임베드하는 유출 채널 차단
ALLOWED_FORMATS = {"png", "jpg", "jpeg", "gif", "bmp"}
try:
    MAX_IMAGE_BYTES = int(os.getenv("HWPX_MCP_IMAGE_MAX_BYTES", str(20 * 1024 * 1024)))
except ValueError:
    logger.warning("HWPX_MCP_IMAGE_MAX_BYTES 값이 정수가 아님 — 기본 20MB 적용")
    MAX_IMAGE_BYTES = 20 * 1024 * 1024

if not os.getenv("HWPX_MCP_IMAGE_ROOT", ""):
    # 미설정 = 서버 계정이 읽을 수 있는 모든 경로 허용(개발 편의 기본).
    # 상시 서버에서는 반출 채널이 되므로 허용 루트 지정을 권장.
    logger.warning("HWPX_MCP_IMAGE_ROOT 미설정 — 모든 경로의 이미지 임베드 허용. "
                   "상시 배포 시 허용 루트 지정 권장.")
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)


def _sniff_format(head: bytes):
    for magic, fmt in _MAGIC:
        if head.startswith(magic):
            return fmt
    return None


def check_image_source(image_path: str = "", image_b64: str = "") -> str:
    """
    도구 인자 단계 이미지 검증 — 확장자·매직바이트·크기 상한, (설정 시) 루트 제한.
    위반 시 ValueError. 통과 시 실제 포맷 문자열 반환.
    HWPX_MCP_IMAGE_ROOT 환경변수를 지정하면 그 하위 경로만 허용.
    """
    if image_path:
        p = Path(image_path).resolve()
        root = os.getenv("HWPX_MCP_IMAGE_ROOT", "")
        if root:
            try:
                p.relative_to(Path(root).resolve())
            except ValueError:
                raise ValueError(f"이미지는 {root} 하위 경로만 허용: {p}")
        if not p.is_file():
            raise ValueError(f"이미지 파일 없음: {p}")
        ext = p.suffix.lstrip(".").lower()
        if ext not in ALLOWED_FORMATS:
            raise ValueError(f"허용되지 않는 이미지 확장자 .{ext} (허용: {sorted(ALLOWED_FORMATS)})")
        size = p.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise ValueError(f"이미지가 상한({MAX_IMAGE_BYTES} bytes) 초과: {size} bytes")
        with p.open("rb") as f:
            head = f.read(16)
        fmt = _sniff_format(head)
        if fmt is None:
            raise ValueError(f"이미지 파일이 아님(매직바이트 불일치): {p.name}")
        return fmt
    # b64 경로: 디코드 전 크기 추정 → 디코드 → 매직 검사
    if len(image_b64) * 3 // 4 > MAX_IMAGE_BYTES:
        raise ValueError(f"이미지 b64 가 상한({MAX_IMAGE_BYTES} bytes) 초과")
    try:
        data = base64.b64decode(image_b64, validate=True)
    except Exception:
        raise ValueError("image_b64 가 올바른 base64 가 아님")
    fmt = _sniff_format(data[:16])
    if fmt is None:
        raise ValueError("image_b64 가 이미지가 아님(매직바이트 불일치)")
    return fmt


def load_image_bytes(block: dict):
    """block에서 이미지 bytes + 포맷 추출. (path 또는 b64) — 렌더 시점 재검증 포함."""
    if block.get("path"):
        fmt = check_image_source(image_path=block["path"])   # add 이후 파일이 바뀌었을 수 있음
        return Path(block["path"]).read_bytes(), fmt
    if block.get("b64"):
        data = base64.b64decode(block["b64"])
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"이미지가 상한({MAX_IMAGE_BYTES} bytes) 초과")
        return data, (_sniff_format(data[:16]) or block.get("format") or "png").lower()
    raise ValueError("image block requires 'path' or 'b64'")


def emit_image(doc, block: dict):
    """
    이미지 블록 렌더.
    - 바이너리는 항상 임베드(BinData).
    - EMBED_PIC(기본 켬)이면 <hp:pic> run 삽입, 실패하거나 끄면 캡션 박스 자리표.
    """
    caption = block.get("caption", "")
    data = b""
    try:
        data, fmt = load_image_bytes(block)
        item_id = doc._doc.add_image(data, fmt)   # BinData/manifest/binDataList
        logger.info("image embedded: %s (%s, %d bytes)", item_id, fmt, len(data))
    except Exception as e:
        logger.warning("image embed failed: %s", e)
        item_id = None

    if EMBED_PIC and item_id:
        try:
            _emit_pic_run(doc, item_id, block, data)
            if caption:
                _emit_caption(doc, caption)
            return
        except Exception as e:
            logger.warning("pic run failed, fallback to placeholder: %s", e)

    # 안전 플레이스홀더: 캡션 박스
    tbl = doc.table(1, 1)
    tbl.set_width(120, col_ratios=[1])
    label = f"[그림] {caption}" if caption else "[그림 삽입 위치]"
    tbl.cell(0, 0, label, CellFmt(font_size=SIZE_REF, align="CENTER",
                                  text_color="#888888",
                                  font_hangul=FONT_TABLE, font_latin=FONT_TABLE))


def _emit_caption(doc, caption: str):
    from .builder import RunFmt, ParaFmt
    p = doc.para(text="", para_fmt=ParaFmt(align="CENTER", line_spacing=130))
    p.add_run(caption, fmt=RunFmt(font_size=SIZE_REF, font_hangul=FONT_TABLE, font_latin=FONT_TABLE))


def _emit_pic_run(doc, item_id: str, block: dict, data: bytes = b""):
    """<hp:pic> run 을 새 단락에 삽입한다. 틀은 hwpx_core.bindata 한 벌을 쓴다.

    ⚠️ writer 만 파서가 lxml 이라 다른 두 경로처럼 Element 를 그대로 받을 수 없다
    — 그래서 bindata 는 **문자열**을 낸다. 여기서 lxml 로 다시 읽어 붙인다.

    크기는 원본 비율을 지킨다. 종전에는 width_mm·height_mm 을 그대로 orgSz 로 써서
    비율을 무시했고(120×80mm 고정), 세로 그림이 납작하게 눌렸다.
    """
    from .builder import ParaFmt
    px_w = px_h = 0
    if data:
        try:
            px_w, px_h = BD.image_size(data)
        except Exception as e:                       # noqa — 크기를 못 읽어도 넣는다
            logger.warning("이미지 원본 크기 판독 실패(비율 무시): %s", e)
    box_w = mm(block["width_mm"]) if block.get("width_mm") else 0
    box_h = mm(block["height_mm"]) if block.get("height_mm") else 0
    if px_w and px_h:
        w, h = BD.fit_box(px_w, px_h, box_w or mm(120), box_h)
    else:
        w, h = (box_w or mm(120)), (box_h or mm(80))

    p = doc.para(text="", para_fmt=ParaFmt(align="CENTER"))
    para_el = p._para.element
    run = LET.SubElement(para_el, _hp("run"), charPrIDRef="0")
    run.append(LET.fromstring(BD.pic_xml(
        item_id, w, h, px_w=px_w, px_h=px_h, treat_as_char=True,
        obj_id=2300000001 + len(list(para_el)))))
