"""2차 코드리뷰 수정 회귀: 세로 병합, ** 오검출, bullet level, 심층 검증, 이미지 제한, 서식 캐시."""
import base64
import zipfile

import pytest
from lxml import etree

import hwpx_mcp.server as srv
from hwpx_mcp.engine.builder import Doc, CellFmt
from hwpx_mcp.engine.render import render_from_blocks, _detect_line
from hwpx_mcp.engine.images import check_image_source
from hwpx_mcp.models import (
    ValidationError, validate_cell_style, validate_col_ratios,
)
from hwpx_mcp.validation import validate_hwpx

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"

# 1x1 투명 PNG
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
    "h6FO1AAAAABJRU5ErkJggg==")


def fn(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


# ── C1: 세로 병합 ────────────────────────────────────────
def test_vertical_merge_removes_covered_cells(tmp_path):
    doc = {"title": "t", "blocks": [
        {"type": "table", "style": "gov",
         "headers": ["구분", "내용"],
         "rows": [["기반", "1"], ["기반", "2"]],
         "merges": [{"r1": 1, "c1": 0, "r2": 2, "c2": 0}]},   # 데이터 2행 세로 병합
    ]}
    out = str(tmp_path / "v.hwpx")
    render_from_blocks(doc, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    tbl = next(sec.iter(f"{{{HP}}}tbl"))
    trs = tbl.findall(f"{{{HP}}}tr")
    # 마지막 행의 (2,0) 피병합 셀은 제거되어 1개만 남아야 함
    assert len(trs[2].findall(f"{{{HP}}}tc")) == 1
    anchor = None
    for tc in trs[1].findall(f"{{{HP}}}tc"):
        a = tc.find(f"{{{HP}}}cellAddr")
        if a.get("rowAddr") == "1" and a.get("colAddr") == "0":
            anchor = tc.find(f"{{{HP}}}cellSpan")
    assert anchor is not None and anchor.get("rowSpan") == "2"
    assert validate_hwpx(out) == []


def test_block_merge_removes_covered_cells(tmp_path):
    """2x2 블록 병합: 앵커 제외 3개 셀 전부 제거."""
    doc = {"title": "t", "blocks": [
        {"type": "table", "style": "gov",
         "headers": ["a", "b", "c"],
         "rows": [["1", "2", "3"], ["4", "5", "6"]],
         "merges": [{"r1": 1, "c1": 0, "r2": 2, "c2": 1}]},
    ]}
    out = str(tmp_path / "blk.hwpx")
    render_from_blocks(doc, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    tbl = next(sec.iter(f"{{{HP}}}tbl"))
    trs = tbl.findall(f"{{{HP}}}tr")
    assert len(trs[1].findall(f"{{{HP}}}tc")) == 2   # 앵커(span 2x2) + c열
    assert len(trs[2].findall(f"{{{HP}}}tc")) == 1   # c열만


# ── M2: ** 시작 줄 ───────────────────────────────────────
def test_bold_line_not_ref_marker():
    marker, level, font, size, is_ref = _detect_line("**AI 플랫폼** 구축 추진")
    assert marker is None and not is_ref and size == 15


def test_ref_marker_still_detected():
    marker, level, font, size, is_ref = _detect_line("* 참고: 세부내용")
    assert marker == "*" and is_ref and size == 13


# ── M5: bullet level ─────────────────────────────────────
def test_bullet_level_renders_marker(tmp_path):
    doc = {"title": "t", "blocks": [
        {"type": "bullet", "text": "세부 사항", "level": 2, "marker": None},
        {"type": "bullet", "text": "미세 항목", "level": 4, "marker": None},
    ]}
    out = str(tmp_path / "bl.hwpx")
    render_from_blocks(doc, out)
    z = zipfile.ZipFile(out)
    xml = z.read("Contents/section0.xml").decode("utf-8")
    assert "◦" in xml and "세부 사항" in xml
    assert "·" in xml and "미세 항목" in xml


# ── M6: 심층 검증 ────────────────────────────────────────
def test_cell_style_rejects_string_font_size():
    with pytest.raises(ValidationError):
        validate_cell_style({"row": 0, "col": 0, "font_size": "12"}, 2, 2)


def test_cell_style_rejects_bad_align():
    with pytest.raises(ValidationError):
        validate_cell_style({"row": 0, "col": 0, "align": "MIDDLE"}, 2, 2)


def test_col_ratios_validation():
    with pytest.raises(ValidationError):
        validate_col_ratios(["1", "2"], 2)        # 문자열
    with pytest.raises(ValidationError):
        validate_col_ratios([1, -2], 2)           # 음수
    with pytest.raises(ValidationError):
        validate_col_ratios([1, 2, 3], 2)         # 길이 불일치
    validate_col_ratios([1, 2.5], 2)              # 정상


def test_add_table_rejects_bad_col_ratios():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    r = fn("add_table")(document_id=did, section_key=sk,
                        headers=["a", "b"], rows=[["1", "2"]], col_ratios=["1", "2"])
    assert r["status"] == "error"


# ── M4: 병합 수명주기 ────────────────────────────────────
def test_overlapping_merge_rejected():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_table")(document_id=did, section_key=sk,
                    headers=["a", "b", "c"], rows=[["1", "2", "3"]])
    assert fn("merge_cells")(document_id=did, section_key=sk, table_index=0,
                             r1=0, c1=0, r2=0, c2=1)["status"] == "success"
    r = fn("merge_cells")(document_id=did, section_key=sk, table_index=0,
                          r1=0, c1=1, r2=0, c2=2)
    assert r["status"] == "error" and "겹침" in r["message"]


def test_update_table_drops_stale_merges():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_table")(document_id=did, section_key=sk, headers=["a", "b"],
                    rows=[["1", "2"], ["3", "4"], ["5", "6"]])
    fn("merge_cells")(document_id=did, section_key=sk, table_index=0,
                      r1=1, c1=0, r2=3, c2=0)
    r = fn("update_table")(document_id=did, section_key=sk, table_index=0,
                           rows=[["1", "2"]])   # 3행 → 1행 축소
    assert r["status"] == "success" and r.get("dropped_merges") == 1
    rh = fn("render_hwpx")(document_id=did)
    assert rh["status"] == "success" and rh["validation_problems"] == []


# ── M7: 이미지 제한 ──────────────────────────────────────
def test_image_source_rejects_non_image(tmp_path):
    fake = tmp_path / "secret.png"
    fake.write_bytes(b"-----BEGIN OPENSSH PRIVATE KEY-----")
    with pytest.raises(ValueError):
        check_image_source(image_path=str(fake))         # 매직바이트 불일치
    txt = tmp_path / "note.txt"
    txt.write_text("hello")
    with pytest.raises(ValueError):
        check_image_source(image_path=str(txt))          # 확장자 불허


def test_image_source_accepts_png_and_b64(tmp_path):
    p = tmp_path / "ok.png"
    p.write_bytes(PNG_1PX)
    assert check_image_source(image_path=str(p)) == "png"
    assert check_image_source(image_b64=base64.b64encode(PNG_1PX).decode()) == "png"


def test_get_document_redacts_b64():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    b64 = base64.b64encode(PNG_1PX).decode()
    assert fn("add_image")(document_id=did, section_key=sk,
                           image_b64=b64)["status"] == "success"
    gd = fn("get_document")(document_id=did)
    img = gd["sections"][0]["blocks"][-1]
    assert "생략" in img["b64"]


# ── M13: 서식 캐시 ───────────────────────────────────────
def test_table_cells_share_char_pr():
    doc = Doc()
    before = len(doc._header.findall(f".//{{{HH}}}charPr"))
    tbl = doc.table(4, 3)
    for r in range(4):
        for c in range(3):
            tbl.cell(r, c, f"{r},{c}", CellFmt())
    after = len(doc._header.findall(f".//{{{HH}}}charPr"))
    # 12셀 동일 서식 → 신규 charPr 는 소수(캐시 미적용 시 24개 이상)
    assert after - before <= 2
