# -*- coding: utf-8 -*-
"""26-09-02 실측 회귀 — 한/글이 문서를 여는 데서 멈추던 원인들.

docx 32쪽짜리 가이드라인을 hwpx 로 다시 조판하다 걸린 것들이다.
근거는 각 테스트의 docstring 과 builder.py 주석에 남겼다.
"""
import zipfile

import pytest
from lxml import etree as LET

from hwpx_mcp.engine.builder import Doc, RunFmt, ParaFmt
from hwpx_mcp.engine.constants import mm

HH = "{http://www.hancom.co.kr/hwpml/2011/head}"
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def _parts(path):
    with zipfile.ZipFile(path) as z:
        return (LET.fromstring(z.read("Contents/header.xml")),
                LET.fromstring(z.read("Contents/section0.xml")))


@pytest.fixture
def built(tmp_path):
    d = Doc()
    # 서로 다른 글꼴 넷 — 스켈레톤 기본(함초롬돋움·함초롬바탕) 위에 쌓인다
    for face in ("휴먼명조", "HY헤드라인M", "한양중고딕", "맑은 고딕"):
        d.para("글꼴 %s 확인" % face, fmt=RunFmt(font_size=15, font_hangul=face,
                                              font_latin=face))
    t = d.table(3, 2)
    for r in range(3):
        for c in range(2):
            t.cell(r, c, "칸 %d-%d" % (r, c))
    out = tmp_path / "review6.hwpx"
    d.save(str(out))
    return out


def test_모든_언어계열_글꼴수가_같다(built):
    """글꼴을 HANGUL/LATIN 에만 넣으면 나머지 다섯 계열이 없는 번호를 가리킨다.

    charPr 의 fontRef 는 일곱 계열에 같은 번호를 쓴다. 종전 엔진은 요청한 계열에만
    등록해서 HANJA·SYMBOL 등이 2개인데 4번을 참조했고, 그 파일을 한/글이 열면
    Open 에서 무한 대기했다.
    """
    header, _ = _parts(built)
    counts = {ff.get("lang"): len(ff.findall(HH + "font"))
              for ff in header.iter(HH + "fontface")}
    assert len(set(counts.values())) == 1, f"계열별 글꼴 수가 어긋난다: {counts}"
    assert counts["HANGUL"] >= 6      # 스켈레톤 2 + 새로 넣은 4


def test_fontRef_가_실재하는_번호만_가리킨다(built):
    header, _ = _parts(built)
    per_lang = {ff.get("lang"): len(ff.findall(HH + "font"))
                for ff in header.iter(HH + "fontface")}
    for ref in header.iter(HH + "fontRef"):
        for lang_attr, key in (("hangul", "HANGUL"), ("latin", "LATIN"),
                               ("hanja", "HANJA"), ("japanese", "JAPANESE"),
                               ("other", "OTHER"), ("symbol", "SYMBOL"),
                               ("user", "USER")):
            idx = int(ref.get(lang_attr))
            assert idx < per_lang[key], (
                f"{key} 는 {per_lang[key]}개인데 {idx}번을 참조한다 (댕글링)")


def test_표_셀에_안쪽여백이_들어간다(built):
    """cellMargin 이 사방 0 이면 글자가 테두리에 붙는다."""
    _, section = _parts(built)
    margins = list(section.iter(HP + "cellMargin"))
    assert margins, "표에 cellMargin 이 없다"
    for cm in margins:
        assert int(cm.get("left")) > 0 and int(cm.get("top")) > 0


def test_줄높이를_낮출_수_있다(tmp_path):
    """기본 12.7mm 고정이라 줄 많은 표가 그것만으로 쪽을 넘긴다."""
    d = Doc()
    t = d.table(4, 2)
    t.set_row_height(8.0)
    out = tmp_path / "rowh.hwpx"
    d.save(str(out))
    _, section = _parts(out)
    heights = {cs.get("height") for cs in section.iter(HP + "cellSz")}
    assert heights == {str(mm(8.0))}, heights


def test_page_break_는_문단에_실린다(tmp_path):
    """표에는 pageBreak 속성을 못 걸어서, 앞에 작은 빈 문단을 놓아 실어 보낸다."""
    d = Doc()
    d.para("첫 쪽")
    d.page_break()
    t = d.table(2, 2)
    t.cell(0, 0, "둘째 쪽 표")
    out = tmp_path / "pb.hwpx"
    d.save(str(out))
    _, section = _parts(out)
    breaks = [p for p in section.iter(HP + "p") if p.get("pageBreak") == "1"]
    assert len(breaks) == 1
    assert not "".join(breaks[0].itertext()).strip(), "쪽나눔 문단은 비어 있어야 한다"


def _empty_count(path):
    _, section = _parts(path)
    return [p for p in section.iter(HP + "p") if not "".join(p.itertext()).strip()]


def test_vspace_는_빈문단_개수로_여백을_만든다(tmp_path):
    """큰 space_before 는 한/글이 쪽을 넘겨버려서 못 쓴다.

    스켈레톤 자체가 빈 문단을 하나 갖고 있으므로, 넣은 것과 안 넣은 것의 차이로 잰다.
    """
    def build(gap_mm, name):
        d = Doc()
        d.para("위")
        if gap_mm:
            d.vspace(gap_mm)
        d.para("아래")
        out = tmp_path / name
        d.save(str(out))
        return out

    base = _empty_count(build(0, "base.hwpx"))
    with_gap = _empty_count(build(52.8, "vs.hwpx"))     # 빈 줄 5.28mm × 10
    assert len(with_gap) - len(base) == 10, (len(with_gap), len(base))
    for p in with_gap:
        assert p.get("pageBreak") in (None, "0")
