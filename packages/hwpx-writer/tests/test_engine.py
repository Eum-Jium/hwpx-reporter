"""엔진: 렌더 골든 구조, 열너비, 병합, 무수리 스모크."""
import zipfile
from lxml import etree

from hwpx_mcp.engine.render import render_from_blocks
from hwpx_mcp.engine.constants import calc_col_widths, char_weight, TABLE_WIDTH
from hwpx_mcp.validation import validate_hwpx

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def test_char_weight_cjk():
    assert char_weight("AB") == 2
    assert char_weight("가나") == 4       # 전각 2배
    assert char_weight("A가") == 3


def test_calc_col_widths_sums_to_total():
    w = calc_col_widths(["구분", "내용", "비고"], [["가", "나다라", "1"]])
    assert len(w) == 3
    assert sum(w) == TABLE_WIDTH          # 마지막 열이 오차 흡수
    assert all(x >= 2000 for x in w)


def test_render_produces_valid_hwpx(tmp_path, sample_doc):
    out = str(tmp_path / "doc.hwpx")
    render_from_blocks(sample_doc, out)
    problems = validate_hwpx(out)
    assert problems == [], f"무결성 문제: {problems}"


def test_no_repair_smoke(tmp_path, sample_doc):
    """한글 수리 유발 클래스(댕글링 참조/병합 잔존/mimetype) 없음."""
    out = str(tmp_path / "doc.hwpx")
    render_from_blocks(sample_doc, out)
    assert validate_hwpx(out) == []


def test_merge_removes_covered_cells(tmp_path):
    doc = {"title": "t", "blocks": [
        {"type": "table", "style": "gov",
         "headers": ["A", "B", "C"], "rows": [["1", "2", "3"]],
         "merges": [{"r1": 0, "c1": 0, "r2": 0, "c2": 1}]},
    ]}
    out = str(tmp_path / "m.hwpx")
    render_from_blocks(doc, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    tbl = next(sec.iter(f"{{{HP}}}tbl"))
    first_tr = tbl.findall(f"{{{HP}}}tr")[0]
    tcs = first_tr.findall(f"{{{HP}}}tc")
    # 3열이었으나 0~1 병합 → 첫 행 셀은 2개(앵커 colSpan=2 + C)
    assert len(tcs) == 2
    anchor = tcs[0].find(f"{{{HP}}}cellSpan")
    assert anchor is not None and anchor.get("colSpan") == "2"


def test_gov_border_states_distinct(tmp_path):
    """16-상태: 헤더행과 데이터행이 서로 다른 borderFill을 받음."""
    doc = {"title": "t", "blocks": [
        {"type": "table", "style": "gov",
         "headers": ["A", "B"], "rows": [["1", "2"], ["3", "4"]]},
    ]}
    out = str(tmp_path / "b.hwpx")
    render_from_blocks(doc, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    tbl = next(sec.iter(f"{{{HP}}}tbl"))
    bf_by_pos = {}
    for tc in tbl.iter(f"{{{HP}}}tc"):
        a = tc.find(f"{{{HP}}}cellAddr")
        bf_by_pos[(a.get("rowAddr"), a.get("colAddr"))] = tc.get("borderFillIDRef")
    # 헤더(0,0) 와 데이터(1,0) 는 다른 상태
    assert bf_by_pos[("0", "0")] != bf_by_pos[("1", "0")]


def test_page_margin_applied(tmp_path, sample_doc):
    out = str(tmp_path / "pm.hwpx")
    render_from_blocks(sample_doc, out)
    z = zipfile.ZipFile(out)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    margin = next(sec.iter(f"{{{HP}}}margin"))
    # 좌우 23mm = 6519 근사
    assert abs(int(margin.get("left")) - int(23 * 283.46)) <= 2
    assert abs(int(margin.get("top")) - int(15 * 283.46)) <= 2


def test_hancom_fonts_declared_as_hft(tmp_path):
    """한컴 전용 글꼴(휴먼명조·한양중고딕)은 HFT, TTF 존재 글꼴은 TTF 로 선언."""
    doc = {"title": "폰트", "blocks": [
        {"type": "heading", "text": "Ⅰ. 확인", "level": 2},
        {"type": "paragraph", "text": "□ 본문\n* 참고"},
        {"type": "table", "headers": ["A"], "rows": [["1"]]},
    ]}
    out = str(tmp_path / "f.hwpx")
    render_from_blocks(doc, out)
    z = zipfile.ZipFile(out)
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    types = {}
    for font in hdr.iter(f"{{{HH}}}font"):
        types.setdefault(font.get("face"), set()).add(font.get("type"))
    from hwpx_mcp.engine.constants import HFT_FONTS
    for face, ts in types.items():
        expected = "HFT" if face in HFT_FONTS else "TTF"
        assert ts == {expected}, f"{face}: {ts} (기대 {expected})"
    # 본문/참고 글꼴이 실제로 선언됐는지 (미사용 조기귀환으로 인한 헛통과 방지)
    assert "휴먼명조" in types and "한양중고딕" in types
