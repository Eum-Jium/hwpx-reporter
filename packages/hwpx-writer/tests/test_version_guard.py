"""
python-hwpx private API 접점 회귀 가드.
업그레이드로 이 접점이 깨지면 시끄럽게 실패해야 한다(엔진이 조용히 오작동 방지).
"""
import hwpx
from hwpx_mcp.config import PINNED_HWPX_VERSION
from hwpx_mcp.engine.builder import Doc, _get_header_elem, _hp


def test_pinned_version():
    assert hwpx.__version__ == PINNED_HWPX_VERSION, (
        f"python-hwpx {hwpx.__version__} != 핀 {PINNED_HWPX_VERSION}. "
        f"private API 접점 재검증 필요.")


def test_header_element_touchpoint():
    d = Doc()
    hdr = _get_header_elem(d._doc)          # doc._root._headers[0]._element
    assert hdr is not None
    assert hdr.find(f".//{{http://www.hancom.co.kr/hwpml/2011/head}}charProperties") is not None


def test_table_cell_touchpoint():
    d = Doc()
    tbl = d.table(2, 2)
    cell_map = tbl._tbl.get_cell_map()
    tc = cell_map[0][0]
    cell_obj = getattr(tc, "cell", tc)      # python-hwpx 2.9+: tc.cell.element
    assert hasattr(cell_obj, "element")
    assert cell_obj.element.tag.endswith("tc")


def test_add_image_touchpoint():
    """python-hwpx add_image(bytes, fmt) 존재/시그니처 확인."""
    import base64
    d = Doc()
    assert hasattr(d._doc, "add_image")
    # 1x1 투명 PNG
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    item_id = d._doc.add_image(png, "png")
    assert isinstance(item_id, str) and item_id
