"""
builder.py — 완전한 서식을 지원하는 HWPX 빌더 (프로덕션 하드닝판)

원본: skill/hwpx/scripts/hwpx_full.py
변경점 (프로덕션):
  - import 시 pip install 제거 (배포는 pyproject deps로)
  - stdout print 제거 → logging(stderr). [stdio MCP는 stdout이 프로토콜 채널]
  - _add_border_fill: 면별 (type, width, color) + 이중선 + fill 지원 (16-상태 테두리용)
  - secCnt/여백 패치: 정규식 → lxml 구조적 편집
"""
from __future__ import annotations

import logging
import os
import zipfile
import shutil
import re
from dataclasses import dataclass
from typing import Optional

# lxml/ET 호환 패치 (python-hwpx 내부가 ET.Element/SubElement를 사용)
# ⚠️ 종전에는 `_hwpx_doc.ET.Element = LET.Element` 로 **표준 라이브러리 모듈 객체
#    자체**를 덮어써, 같은 프로세스의 모든 코드가 lxml 함수를 집어 들었다(전역 오염).
#    skeleton 을 ElementTree 로 옮기자 그 자리에서 트리 타입이 섞여 터졌다(08-16).
#    python-hwpx 만 lxml 을 보도록 **대역 모듈**을 만들어 끼운다.
import types
import xml.etree.ElementTree as _ET
import hwpx.oxml.document as _hwpx_doc
from lxml import etree as LET

_lxml_ET = types.SimpleNamespace(
    **{k: getattr(_ET, k) for k in dir(_ET) if not k.startswith("__")})
_lxml_ET.Element = LET.Element
_lxml_ET.SubElement = LET.SubElement
_hwpx_doc.ET = _lxml_ET

from hwpx import HwpxDocument

from .constants import mm, pt_to_hwp, HWPUNIT_PER_MM, HFT_FONTS

logger = logging.getLogger("hwpx_mcp.engine")

_ASSET_SKELETON = os.path.join(os.path.dirname(__file__), "assets", "Skeleton.hwpx")


def _new_document():
    """
    빈 HWPX 문서 생성. python-hwpx 자산(Skeleton.hwpx)이 없으면
    패키지 번들 Skeleton으로 폴백 → 어느 PC에서든 자체 완결.
    """
    try:
        return HwpxDocument.new()
    except FileNotFoundError:
        logger.warning("python-hwpx Skeleton 자산 없음 — 번들 Skeleton 사용")
        with open(_ASSET_SKELETON, "rb") as f:
            return HwpxDocument.open(f.read())

# ── 네임스페이스 ─────────────────────────────────────────
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
OPF = "http://www.idpf.org/2007/opf/"


def _hh(tag): return f"{{{HH}}}{tag}"
def _hp(tag): return f"{{{HP}}}{tag}"
def _hc(tag): return f"{{{HC}}}{tag}"


# ── 서식 데이터클래스 ────────────────────────────────────
@dataclass
class RunFmt:
    """글자 서식 (표준서식: 휴먼명조 15pt)"""
    font_size: int = 15
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikeout: bool = False
    color: str = "#000000"
    bg_color: str = "none"
    font_hangul: str = "휴먼명조"
    font_latin: str = "휴먼명조"


@dataclass
class ParaFmt:
    """문단 서식 (표준서식: 양쪽정렬, 줄간격 155%)"""
    align: str = "JUSTIFY"
    line_spacing: int = 155
    space_before: int = 0
    space_after: int = 0
    indent_left: int = 0
    indent_right: int = 0
    indent_first: int = 0


@dataclass
class CellFmt:
    """표 셀 서식"""
    bg_color: str = "none"
    text_color: str = "#000000"
    font_size: int = 12          # 표 기본 12pt (맑은 고딕)
    bold: bool = False
    align: str = "LEFT"
    v_align: str = "CENTER"
    border_color: str = "#000000"
    border_width: str = "0.12 mm"
    border_type: str = "SOLID"
    border_sides: dict = None     # {"left":"NONE",...} 또는 {"left":(type,width,color),...}
    border_fill_id: int = None    # 명시적 borderFill ID (16-상태 테두리에서 사용)
    font_hangul: str = "맑은 고딕"
    font_latin: str = "맑은 고딕"


# ── 내부 헬퍼: 폰트/charPr/paraPr/borderFill ─────────────
def _find_or_add_font(header_elem, font_name: str, lang: str) -> int:
    """글꼴을 fontfaces 에 등록하고 그 번호를 돌려준다.

    ⚠️ 새 글꼴은 **일곱 언어 계열 전부에 같은 번호로** 넣는다. charPr 의 fontRef 는
       hangul·latin·hanja·japanese·other·symbol·user 에 같은 번호를 쓰는데, 종전에는
       요청받은 계열에만 넣어서 나머지 다섯이 **없는 번호를 가리켰다**(댕글링 참조).
       그런 파일을 한/글이 열면 Open 에서 멈춘다 — 26-09-02 실측: 글꼴 5개를 쓴
       31쪽 문서가 HANGUL/LATIN 만 5개, 나머지는 2개인 채로 4번을 참조해 무한 대기.
       스켈레톤은 일곱 계열이 같은 목록으로 출발하므로, 언제나 전부에 덧붙이면
       번호가 어긋나지 않는다.
    """
    fontfaces = header_elem.find(f".//{_hh('fontfaces')}")
    if fontfaces is None:
        return 0
    faces = fontfaces.findall(_hh('fontface'))
    target = next((ff for ff in faces if ff.get('lang') == lang), None)
    if target is None:
        return 0

    for i, f in enumerate(target.findall(_hh('font'))):
        if f.get('face') == font_name:
            return i

    new_id = len(target.findall(_hh('font')))
    # 관례: 한컴 글꼴은 HFT 로 선언(한/글 전용 형식), 나머지는 TTF
    font_type = "HFT" if font_name in HFT_FONTS else "TTF"
    for ff in faces:
        idx = len(ff.findall(_hh('font')))
        font_el = LET.SubElement(ff, _hh('font'),
            id=str(idx), face=font_name, type=font_type, isEmbedded="0")
        LET.SubElement(font_el, _hh('typeInfo'),
            familyType="FCAT_GOTHIC", weight="6", proportion="4",
            contrast="0", strokeVariation="1", armStyle="1",
            letterform="1", midline="1", xHeight="1")
        ff.set('fontCnt', str(idx + 1))
    return new_id


def _norm_side(spec, default_color="#000000"):
    """면 스펙 정규화 → (type, width, color)"""
    if spec is None:
        return None
    if isinstance(spec, str):        # "NONE" / "SOLID"
        if spec == "NONE":
            return ("NONE", "0.0 mm", "#FFFFFF")
        return (spec, "0.12 mm", default_color)
    if isinstance(spec, (tuple, list)):
        t = spec[0]
        w = spec[1] if len(spec) > 1 else "0.12 mm"
        c = spec[2] if len(spec) > 2 else default_color
        if t == "NONE":
            return ("NONE", "0.0 mm", "#FFFFFF")
        return (t, w, c)
    return None


def _add_border_fill(header_elem, bg_color: str = "none",
                     border_type: str = "SOLID",
                     border_color: str = "#000000",
                     border_width: str = "0.12 mm",
                     border_sides: dict = None) -> int:
    """
    borderFill 추가 후 ID 반환.
    border_sides: 면별 스펙. 값은 "NONE"/"SOLID"(str) 또는 (type, width, color)(tuple).
                  미지정 시 4면 border_type/width/color 일괄 적용.
    """
    bfs = header_elem.find(f".//{_hh('borderFills')}")
    existing = bfs.findall(_hh('borderFill'))
    new_id = max((int(e.get('id', 0)) for e in existing), default=0) + 1

    bf = LET.SubElement(bfs, _hh('borderFill'),
        id=str(new_id), threeD="0", shadow="0",
        centerLine="NONE", breakCellSeparateLine="0")
    LET.SubElement(bf, _hh('slash'), type="NONE", Crooked="0", isCounter="0")
    LET.SubElement(bf, _hh('backSlash'), type="NONE", Crooked="0", isCounter="0")

    default_side = _norm_side((border_type, border_width, border_color)) \
        if border_type != "NONE" else ("NONE", "0.0 mm", "#FFFFFF")
    for side in ('left', 'right', 'top', 'bottom'):
        spec = None
        if border_sides and side in border_sides:
            spec = _norm_side(border_sides[side], border_color)
        if spec is None:
            spec = default_side
        t, w, c = spec
        LET.SubElement(bf, _hh(f'{side}Border'), type=t, width=w, color=c)

    LET.SubElement(bf, _hh('diagonal'), type="SOLID", width="0.1 mm", color="#000000")

    face = bg_color if (bg_color and bg_color != "none") else "none"
    brush = LET.SubElement(bf, _hc('fillBrush'))
    LET.SubElement(brush, _hc('winBrush'),
        faceColor=face, hatchColor="#999999", alpha="0")

    bfs.set('itemCnt', str(len(bfs.findall(_hh('borderFill')))))
    return new_id


def _next_id(container, tag) -> int:
    """비연속 ID 대비: max(id)+1 (len() 아님)."""
    els = container.findall(_hh(tag))
    return max((int(e.get('id', -1)) for e in els), default=-1) + 1


def _add_char_pr(header_elem, fmt: RunFmt) -> int:
    char_prs = header_elem.find(f".//{_hh('charProperties')}")
    new_id = _next_id(char_prs, 'charPr')

    hangul_idx = _find_or_add_font(header_elem, fmt.font_hangul, 'HANGUL')
    latin_idx = _find_or_add_font(header_elem, fmt.font_latin, 'LATIN')
    ref, ref_l = str(hangul_idx), str(latin_idx)

    cp = LET.SubElement(char_prs, _hh('charPr'),
        id=str(new_id), height=str(pt_to_hwp(fmt.font_size)),
        textColor=fmt.color,
        shadeColor=fmt.bg_color if fmt.bg_color != "none" else "none",
        useFontSpace="0", useKerning="0", symMark="NONE", borderFillIDRef="2")
    LET.SubElement(cp, _hh('fontRef'),
        hangul=ref, latin=ref_l, hanja=ref,
        japanese=ref, other=ref_l, symbol=ref_l, user=ref_l)
    for attr in ('ratio', 'spacing', 'relSz', 'offset'):
        vals = "100" if attr in ('ratio', 'relSz') else "0"
        LET.SubElement(cp, _hh(attr),
            hangul=vals, latin=vals, hanja=vals,
            japanese=vals, other=vals, symbol=vals, user=vals)
    if fmt.bold:
        LET.SubElement(cp, _hh('bold'))
    if fmt.italic:
        LET.SubElement(cp, _hh('italic'))
    LET.SubElement(cp, _hh('underline'),
        type="SOLID" if fmt.underline else "NONE", shape="SOLID", color="#000000")
    LET.SubElement(cp, _hh('strikeout'),
        shape="SOLID" if fmt.strikeout else "NONE", color="#000000")
    LET.SubElement(cp, _hh('outline'), type="NONE")
    LET.SubElement(cp, _hh('shadow'), type="NONE", color="#C0C0C0", offsetX="10", offsetY="10")

    char_prs.set('itemCnt', str(len(char_prs.findall(_hh('charPr')))))
    return new_id


def _add_para_pr(header_elem, fmt: ParaFmt, border_fill_id: int = 2) -> int:
    para_prs = header_elem.find(f".//{_hh('paraProperties')}")
    new_id = _next_id(para_prs, 'paraPr')

    pp = LET.SubElement(para_prs, _hh('paraPr'),
        id=str(new_id), tabPrIDRef="0", condense="0",
        fontLineHeight="0", snapToGrid="1",
        suppressLineNumbers="0", checked="0", textDir="LTR")
    LET.SubElement(pp, _hh('align'), horizontal=fmt.align, vertical="BASELINE")
    LET.SubElement(pp, _hh('heading'), type="NONE", idRef="0", level="0")
    LET.SubElement(pp, _hh('breakSetting'),
        breakLatinWord="KEEP_WORD", breakNonLatinWord="BREAK_WORD",
        widowOrphan="0", keepWithNext="0", keepLines="0",
        pageBreakBefore="0", lineWrap="BREAK")
    LET.SubElement(pp, _hh('autoSpacing'), eAsianEng="0", eAsianNum="0")

    sw = LET.SubElement(pp, _hp('switch'))
    case = LET.SubElement(sw, _hp('case'))
    case.set(_hp('required-namespace'), "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")
    _build_margin_spacing(case, fmt)
    default = LET.SubElement(sw, _hp('default'))
    _build_margin_spacing(default, fmt)

    LET.SubElement(pp, _hh('border'),
        borderFillIDRef=str(border_fill_id),
        offsetLeft="0", offsetRight="0", offsetTop="0", offsetBottom="0",
        connect="0", ignoreMargin="0")

    para_prs.set('itemCnt', str(len(para_prs.findall(_hh('paraPr')))))
    return new_id


def _build_margin_spacing(parent, fmt: ParaFmt):
    margin = LET.SubElement(parent, _hh('margin'))
    LET.SubElement(margin, _hc('intent'), value=str(fmt.indent_first), unit="HWPUNIT")
    LET.SubElement(margin, _hc('left'), value=str(fmt.indent_left), unit="HWPUNIT")
    LET.SubElement(margin, _hc('right'), value=str(fmt.indent_right), unit="HWPUNIT")
    LET.SubElement(margin, _hc('prev'), value=str(fmt.space_before), unit="HWPUNIT")
    LET.SubElement(margin, _hc('next'), value=str(fmt.space_after), unit="HWPUNIT")
    LET.SubElement(parent, _hh('lineSpacing'),
        type="PERCENT", value=str(fmt.line_spacing), unit="HWPUNIT")


def _get_header_obj(doc: HwpxDocument):
    """python-hwpx 내부 header 객체 접근 (private API — 버전 결합 주의)"""
    return doc._root._headers[0]


def _get_header_elem(doc: HwpxDocument):
    """header XML element 접근"""
    return _get_header_obj(doc)._element


# ── 저장 후 구조적 마무리 (lxml, 정규식 아님) ────────────
def _finalize(path: str, page_margin: dict = None):
    """
    저장된 HWPX ZIP을 lxml로 구조적 편집:
      1) secCnt 갱신 + content.hpf manifest/spine 보정 (다중 섹션)
      2) 페이지 여백 패치 (있으면)
    """
    with zipfile.ZipFile(path, 'r') as z:
        names = z.namelist()
        files = {n: z.read(n) for n in names}

    sections = sorted(
        [n for n in names if re.match(r'Contents/section\d+\.xml$', n)],
        key=lambda x: int(re.search(r'\d+', x).group()),
    )
    sec_cnt = len(sections)

    # 1) header secCnt (구조적)
    if sec_cnt > 1 and 'Contents/header.xml' in files:
        root = LET.fromstring(files['Contents/header.xml'])
        root.set('secCnt', str(sec_cnt))
        files['Contents/header.xml'] = LET.tostring(root, xml_declaration=True,
                                                    encoding='UTF-8', standalone=True)
        # content.hpf manifest/spine
        hpf_root = LET.fromstring(files['Contents/content.hpf'])
        manifest = hpf_root.find(f'.//{{{OPF}}}manifest')
        spine = hpf_root.find(f'.//{{{OPF}}}spine')
        have_ids = {it.get('id') for it in manifest.findall(f'{{{OPF}}}item')}
        have_refs = {r.get('idref') for r in spine.findall(f'{{{OPF}}}itemref')}
        for sec_file in sections:
            sid = re.search(r'(section\d+)', sec_file).group(1)
            if sid not in have_ids:
                LET.SubElement(manifest, f'{{{OPF}}}item', id=sid,
                    href=f'Contents/{sid}.xml', **{'media-type': 'application/xml'})
            if sid not in have_refs:
                LET.SubElement(spine, f'{{{OPF}}}itemref', idref=sid, linear='yes')
        files['Contents/content.hpf'] = LET.tostring(hpf_root, xml_declaration=True,
                                                    encoding='UTF-8', standalone=True)

    # 2) 페이지 여백 (구조적 — 속성 순서 무관)
    if page_margin:
        for name in sections:
            root = LET.fromstring(files[name])
            for margin in root.iter(_hp('margin')):
                margin.set('header', str(page_margin['header']))
                margin.set('footer', str(page_margin['footer']))
                margin.set('left', str(page_margin['left']))
                margin.set('right', str(page_margin['right']))
                margin.set('top', str(page_margin['top']))
                margin.set('bottom', str(page_margin['bottom']))
            files[name] = LET.tostring(root, xml_declaration=True,
                                       encoding='UTF-8', standalone=True)

    # 재압축 (mimetype 첫 번째, 비압축)
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        if 'mimetype' in files:
            zi = zipfile.ZipInfo('mimetype')
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, files.pop('mimetype'))
        for n, data in files.items():
            zout.writestr(n, data)
    shutil.move(tmp, path)


# ── 공개 API: Para / Doc / Table ─────────────────────────
class Para:
    """문단 객체 — add_run()으로 인라인 서식 추가"""
    def __init__(self, doc, hwpx_para, header_elem, owner: 'Doc' = None):
        self._doc = doc
        self._para = hwpx_para
        self._header = header_elem
        self._owner = owner   # Doc 서식 캐시 공유 (run 마다 charPr 신규 생성 방지)

    def add_run(self, text: str, fmt: Optional[RunFmt] = None, **kwargs) -> 'Para':
        if fmt is None:
            fmt = RunFmt(**{k: v for k, v in kwargs.items()
                            if k in RunFmt.__dataclass_fields__})
        if self._owner is not None:
            char_id = self._owner._get_char_id(fmt)
        else:
            char_id = _add_char_pr(self._header, fmt)
        self._para.add_run(text, char_pr_id_ref=char_id)
        return self


class Doc:
    """완전한 서식을 지원하는 HWPX 문서 빌더 (공공기관 표준서식 기본값)."""

    def __init__(self):
        self._doc = _new_document()
        self._header_obj = _get_header_obj(self._doc)
        self._header = self._header_obj._element
        self._char_cache: dict = {}
        self._para_cache: dict = {}
        self._page_margin = None

    # 캐시된 charPr/paraPr ID
    def _get_char_id(self, fmt: RunFmt) -> int:
        key = (fmt.font_size, fmt.bold, fmt.italic, fmt.underline,
               fmt.strikeout, fmt.color, fmt.bg_color,
               fmt.font_hangul, fmt.font_latin)
        if key not in self._char_cache:
            self._char_cache[key] = _add_char_pr(self._header, fmt)
        return self._char_cache[key]

    def _get_para_id(self, fmt: ParaFmt) -> int:
        key = (fmt.align, fmt.line_spacing, fmt.space_before, fmt.space_after,
               fmt.indent_left, fmt.indent_right, fmt.indent_first)
        if key not in self._para_cache:
            self._para_cache[key] = _add_para_pr(self._header, fmt)
        return self._para_cache[key]

    def add_char_pr(self, fmt: RunFmt) -> int:
        return self._get_char_id(fmt)

    def add_border_fill(self, **kwargs) -> int:
        return _add_border_fill(self._header, **kwargs)

    def heading(self, text: str, level: int = 1, font_size: int = None,
                color: str = "#000000", align: str = None,
                space_before: int = 200, space_after: int = 100,
                line_spacing: int = None,
                font_hangul: str = None, font_latin: str = None) -> 'Doc':
        defaults = {
            1: {"size": 23, "font": "HY헤드라인M", "align": "CENTER", "ls": 130},
            2: {"size": 16, "font": "HY헤드라인M", "align": "LEFT", "ls": 165},
            3: {"size": 16, "font": "HY헤드라인M", "align": "LEFT", "ls": 160},
            4: {"size": 15, "font": "휴먼명조", "align": "LEFT", "ls": 155},
        }
        d = defaults.get(level, defaults[3])
        pt = font_size or d["size"]
        fn_h = font_hangul or d["font"]
        fn_l = font_latin or d["font"]
        # None 센티널 — 인자를 준 호출만 레벨 기본값을 이긴다. font_size 에 묶으면
        # align 만 준 호출(예: 목차 CENTER)이 조용히 무시된다.
        al = align if align is not None else d["align"]
        ls = line_spacing if line_spacing is not None else d["ls"]
        cfmt = RunFmt(font_size=pt, bold=True, color=color, font_hangul=fn_h, font_latin=fn_l)
        pfmt = ParaFmt(align=al, line_spacing=ls, space_before=space_before, space_after=space_after)
        self._doc.add_paragraph(text, char_pr_id_ref=self._get_char_id(cfmt),
                                para_pr_id_ref=self._get_para_id(pfmt))
        return self

    def para(self, text: str = "", fmt: Optional[RunFmt] = None,
             para_fmt: Optional[ParaFmt] = None, **kwargs) -> Para:
        pfmt = para_fmt or ParaFmt(
            align=kwargs.pop('align', 'JUSTIFY'),
            line_spacing=kwargs.pop('line_spacing', 155),
            space_before=kwargs.pop('space_before', 0),
            space_after=kwargs.pop('space_after', 0),
            indent_left=kwargs.pop('indent_left', 0),
            indent_first=kwargs.pop('indent_first', 0),
        )
        cfmt = fmt or RunFmt(**{k: v for k, v in kwargs.items()
                                if k in RunFmt.__dataclass_fields__})
        hwpx_para = self._doc.add_paragraph(
            text, char_pr_id_ref=self._get_char_id(cfmt),
            para_pr_id_ref=self._get_para_id(pfmt))
        return Para(self._doc, hwpx_para, self._header, owner=self)

    def blank(self) -> 'Doc':
        self._doc.add_paragraph("")
        return self

    # 빈 줄 하나의 높이 (15pt · 줄간격 100%). 26-09-02 한/글 실측 5.28mm.
    BLANK_LINE_MM = 5.28

    def vspace(self, height_mm: float, font_size: int = 15) -> 'Doc':
        """세로 여백을 빈 문단 개수로 만든다.

        ⚠️ 큰 여백을 ParaFmt.space_before 로 주면 안 된다 — 한/글이 그 문단을
           다음 쪽으로 넘겨버린다(26-09-02 실측: 40mm 이상에서 재현). 표지처럼
           수십 mm 를 벌려야 하면 이 메서드를 쓴다.
        """
        line = self.BLANK_LINE_MM * font_size / 15.0
        pfmt = ParaFmt(align='LEFT', line_spacing=100)
        cfmt = RunFmt(font_size=font_size)
        for _ in range(max(0, round(height_mm / line))):
            self._doc.add_paragraph("", char_pr_id_ref=self._get_char_id(cfmt),
                                    para_pr_id_ref=self._get_para_id(pfmt))
        return self

    def page_break(self) -> 'Doc':
        """쪽나눔. 다음에 오는 내용이 새 쪽에서 시작한다.

        ⚠️ 표에는 pageBreak 속성을 걸 수 없어서, 표 앞에서 쪽을 넘기려면 이렇게
           작은 빈 문단에 실어 보내야 한다(26-09-02).
        """
        pfmt = ParaFmt(align='LEFT', line_spacing=100)
        cfmt = RunFmt(font_size=4)
        p = self._doc.add_paragraph("", char_pr_id_ref=self._get_char_id(cfmt),
                                    para_pr_id_ref=self._get_para_id(pfmt))
        p.element.set('pageBreak', '1')
        return self

    def note(self, text: str, indent_level: int = 3, **kwargs) -> Para:
        pfmt = ParaFmt(align='JUSTIFY', line_spacing=160,
                       indent_left=mm(3) * max(indent_level, 3))
        cfmt = RunFmt(font_size=13, font_hangul="한양중고딕", font_latin="한양중고딕",
                      **{k: v for k, v in kwargs.items() if k in RunFmt.__dataclass_fields__})
        hwpx_para = self._doc.add_paragraph(
            text, char_pr_id_ref=self._get_char_id(cfmt),
            para_pr_id_ref=self._get_para_id(pfmt))
        return Para(self._doc, hwpx_para, self._header, owner=self)

    def bullet(self, text: str, level: int = 1, marker: str = None, **kwargs) -> Para:
        markers = {1: "□", 2: "◦", 3: "-", 4: "·", 5: "*"}
        m = marker or markers.get(level, "□")
        indent = mm(3) * (level - 1)
        if level >= 5:
            fs, fn = 13, "한양중고딕"
        else:
            fs = kwargs.get('font_size', 15)
            fn = kwargs.get('font_hangul', '휴먼명조')
        pfmt = ParaFmt(align='JUSTIFY', line_spacing=kwargs.get('line_spacing', 155),
                       indent_left=indent)
        cfmt = RunFmt(font_size=fs, font_hangul=fn, font_latin=fn,
                      bold=kwargs.get('bold', False), color=kwargs.get('color', '#000000'))
        full_text = f" {m} {text}"
        hwpx_para = self._doc.add_paragraph(
            full_text, char_pr_id_ref=self._get_char_id(cfmt),
            para_pr_id_ref=self._get_para_id(pfmt))
        return Para(self._doc, hwpx_para, self._header, owner=self)

    def table(self, rows: int, cols: int) -> 'Table':
        tbl = self._doc.add_table(rows, cols)
        return Table(tbl, self._doc, self._header, rows, cols, owner=self)

    def set_header(self, text: str) -> 'Doc':
        self._doc.set_header_text(text)
        return self

    def set_footer(self, text: str) -> 'Doc':
        self._doc.set_footer_text(text)
        return self

    def set_page_margin(self, top=15, bottom=15, left=23, right=23,
                        header=10, footer=10) -> 'Doc':
        self._page_margin = {
            'top': mm(top), 'bottom': mm(bottom),
            'left': mm(left), 'right': mm(right),
            'header': mm(header), 'footer': mm(footer),
        }
        return self

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        # 헤더 raw-lxml 편집(charPr/paraPr/borderFill)을 저장에 반영
        # [python-hwpx 2.18: serialize()는 dirty 파트만 포함]
        self._header_obj.mark_dirty()
        self._doc.save_to_path(path)
        _finalize(path, self._page_margin)
        size = os.path.getsize(path)
        abs_path = os.path.abspath(path)
        logger.info("HWPX saved: %s (%d bytes)", abs_path, size)
        return abs_path


class Table:
    """표 객체 — 셀 채우기, 병합, 너비 설정 (한글 호환)."""

    def __init__(self, hwpx_tbl, doc, header_elem, rows, cols, owner: 'Doc' = None):
        self._tbl = hwpx_tbl
        self._doc = doc
        self._header = header_elem
        self._owner = owner   # Doc 서식 캐시 공유 (셀마다 charPr/paraPr 신규 생성 방지)
        self.rows = rows
        self.cols = cols
        self.set_width(164)   # 기본: A4 콘텐츠폭
        self.set_padding()    # 셀 안쪽 여백 (기본 0 이면 글자가 테두리에 붙는다)

    def set_padding(self, lr_mm: float = 1.5, tb_mm: float = 0.8) -> 'Table':
        """셀 안쪽 여백.

        ⚠️ python-hwpx 가 만드는 표는 cellMargin 이 사방 0 이라 글자가 테두리에
           닿는다(26-09-02). 생성 시 기본으로 넣고, 필요하면 다시 부른다.
        """
        for cm in self._tbl.element.iter(_hp('cellMargin')):
            cm.set('left', str(mm(lr_mm)))
            cm.set('right', str(mm(lr_mm)))
            cm.set('top', str(mm(tb_mm)))
            cm.set('bottom', str(mm(tb_mm)))
        return self

    def set_row_height(self, height_mm: float) -> 'Table':
        """줄 높이의 최솟값 (내용이 넘치면 한/글이 알아서 늘린다).

        ⚠️ 기본값이 3600 HWPUNIT(12.7mm)이라 줄이 많은 표 — 목차처럼 — 는 그것만으로
           쪽을 넘긴다(26-09-02 실측: 17줄 목차가 216mm 를 먹고 두 쪽으로 갈렸다).
        """
        h = mm(height_mm)
        for cs in self._tbl.element.iter(_hp('cellSz')):
            cs.set('height', str(h))
        sz = self._tbl.element.find(_hp('sz'))
        if sz is not None:
            sz.set('height', str(h * self.rows))
        return self

    def _char_id(self, fmt: RunFmt) -> int:
        if self._owner is not None:
            return self._owner._get_char_id(fmt)
        return _add_char_pr(self._header, fmt)

    def _para_id(self, fmt: ParaFmt) -> int:
        if self._owner is not None:
            return self._owner._get_para_id(fmt)
        return _add_para_pr(self._header, fmt)

    def set_width(self, width_mm: float, col_ratios: list = None) -> 'Table':
        total_w = mm(width_mm)
        el = self._tbl.element
        sz = el.find(_hp('sz'))
        if sz is not None:
            sz.set('width', str(total_w))
        if col_ratios is None:
            col_ratios = [1] * self.cols
        ratio_sum = sum(col_ratios) or 1
        col_widths = [int(total_w * r / ratio_sum) for r in col_ratios]
        col_widths[-1] = total_w - sum(col_widths[:-1])
        for tc in el.iter(_hp('tc')):
            addr = tc.find(_hp('cellAddr'))
            cell_sz = tc.find(_hp('cellSz'))
            cell_span = tc.find(_hp('cellSpan'))
            if addr is not None and cell_sz is not None:
                col_idx = int(addr.get('colAddr', 0))
                col_span = int(cell_span.get('colSpan', 1)) if cell_span is not None else 1
                if col_idx < len(col_widths):
                    cell_sz.set('width', str(sum(col_widths[col_idx:col_idx + col_span])))
        return self

    def cell(self, row: int, col: int, text: str,
             fmt: Optional[CellFmt] = None, **kwargs) -> 'Table':
        """셀 채우기. \\n 줄바꿈(첫 줄 자동 Bold). fmt 또는 키워드 서식."""
        if fmt is None:
            fmt = CellFmt(**{k: v for k, v in kwargs.items()
                             if k in CellFmt.__dataclass_fields__})

        # borderFill 결정: 명시적 ID 우선, 아니면 배경/테두리로 생성
        if getattr(fmt, 'border_fill_id', None) is not None:
            bf_id = fmt.border_fill_id
        else:
            bt = getattr(fmt, 'border_type', 'SOLID')
            bs = getattr(fmt, 'border_sides', None)
            if (fmt.bg_color and fmt.bg_color != "none") or bt != "SOLID" or bs:
                bf_id = _add_border_fill(self._header, bg_color=fmt.bg_color,
                                         border_type=bt, border_color=fmt.border_color,
                                         border_width=fmt.border_width, border_sides=bs)
            else:
                bf_id = 3   # 기본 실선 테두리

        rfmt = RunFmt(font_size=fmt.font_size, bold=fmt.bold, color=fmt.text_color,
                      font_hangul=getattr(fmt, 'font_hangul', '맑은 고딕'),
                      font_latin=getattr(fmt, 'font_latin', '맑은 고딕'))
        cid = self._char_id(rfmt)

        lines = text.split('\n') if '\n' in text else [text]
        if len(lines) > 1:
            # 첫 줄 자동 Bold 용 charPr 는 다중 줄일 때만 필요
            rfmt_bold = RunFmt(font_size=fmt.font_size, bold=True, color=fmt.text_color,
                               font_hangul=getattr(fmt, 'font_hangul', '맑은 고딕'),
                               font_latin=getattr(fmt, 'font_latin', '맑은 고딕'))
            cid_bold = self._char_id(rfmt_bold)
            cell_map = self._tbl.get_cell_map()
            tc = cell_map[row][col]
            if tc is not None:
                cell_obj = getattr(tc, 'cell', tc)
                existing = cell_obj.paragraphs
                if existing:
                    existing[0].add_run(lines[0], char_pr_id_ref=cid_bold)
                for line in lines[1:]:
                    cell_obj.add_paragraph(line, char_pr_id_ref=cid)
        else:
            self._tbl.set_cell_text(row, col, text)

        self._apply_cell_style(row, col, fmt, bf_id, cid,
                               keep_ids=(cid_bold,) if len(lines) > 1 else ())
        return self

    def _apply_cell_style(self, row, col, fmt: CellFmt, bf_id: int, cid: int = None,
                          keep_ids: tuple = ()):
        try:
            cell_map = self._tbl.get_cell_map()
            tc = cell_map[row][col]
            if tc is None:
                return
            cell_obj = getattr(tc, 'cell', tc)   # python-hwpx 2.9+: tc.cell.element
            el = cell_obj.element
            el.set('borderFillIDRef', str(bf_id))

            align = getattr(fmt, 'align', 'LEFT')
            pid = self._para_id(ParaFmt(align=align, line_spacing=140))
            for p_el in el.findall(f".//{_hp('p')}"):
                p_el.set('paraPrIDRef', str(pid))

            if cid is None:
                cid = self._char_id(RunFmt(
                    font_size=fmt.font_size, bold=fmt.bold, color=fmt.text_color,
                    font_hangul=getattr(fmt, 'font_hangul', '맑은 고딕'),
                    font_latin=getattr(fmt, 'font_latin', '맑은 고딕')))
            # keep_ids: cell() 이 이미 다른 charPr 로 심어둔 run(다중 줄 첫 줄 Bold)을
            # 보존한다 — 전부 덮으면 '첫 줄 자동 Bold' 계약이 소실된다.
            keep = {str(k) for k in keep_ids}
            for run_el in el.findall(f".//{_hp('run')}"):
                if run_el.get('charPrIDRef') in keep:
                    continue
                run_el.set('charPrIDRef', str(cid))

            # 수직 정렬
            v = getattr(fmt, 'v_align', 'CENTER')
            sub = el.find(_hp('subList'))
            if sub is not None and v:
                sub.set('vertAlign', v)
        except Exception as e:
            logger.warning("cell style failed at (%d,%d): %s", row, col, e)

    def merge(self, r1: int, c1: int, r2: int, c2: int) -> 'Table':
        """
        셀 병합 — 직접 XML 조작 (한글 호환).
        앵커 셀만 남기고 피병합 셀을 XML에서 제거 (python-hwpx merge_cells는 남겨서 깨짐).
        """
        el = self._tbl.element
        col_span = c2 - c1 + 1
        row_span = r2 - r1 + 1
        for ri, tr in enumerate(el.findall(_hp('tr'))):
            if ri < r1 or ri > r2:
                continue
            tcs = tr.findall(_hp('tc'))
            to_remove = []
            for tc in tcs:
                addr = tc.find(_hp('cellAddr'))
                if addr is None:
                    continue
                row_idx = int(addr.get('rowAddr', -1))
                col_idx = int(addr.get('colAddr', -1))
                if row_idx == r1 and col_idx == c1:
                    cell_span = tc.find(_hp('cellSpan'))
                    if cell_span is None:
                        cell_span = LET.SubElement(tc, _hp('cellSpan'))
                    cell_span.set('colSpan', str(col_span))
                    cell_span.set('rowSpan', str(row_span))
                    cell_sz = tc.find(_hp('cellSz'))
                    if cell_sz is not None:
                        total_w = int(cell_sz.get('width', 0))
                        for tc2 in tcs:
                            a2 = tc2.find(_hp('cellAddr'))
                            if a2 is None:
                                continue
                            c2i = int(a2.get('colAddr', -1))
                            if c1 < c2i <= c2 and int(a2.get('rowAddr', -1)) == ri:
                                s2 = tc2.find(_hp('cellSz'))
                                if s2 is not None:
                                    total_w += int(s2.get('width', 0))
                        cell_sz.set('width', str(total_w))
                elif r1 <= row_idx <= r2 and c1 <= col_idx <= c2:
                    # 앵커(r1,c1)는 위 분기에서 처리되므로 여기 도달하지 않음.
                    # c1 == col_idx 도 제거해야 세로 병합(rowSpan)이 깨지지 않는다.
                    to_remove.append(tc)
            for tc in to_remove:
                tr.remove(tc)
        return self
