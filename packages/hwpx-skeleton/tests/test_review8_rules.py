# -*- coding: utf-8 -*-
"""작성 규칙이 여러 파일에 흩어져 어긋나는 것을 막는 정합성 테스트.

규칙은 SKILL.md(스킬) · guidelines/*.md(유형별) · prompt.py(writer) ·
length.py(정책 예시) 네 곳에 있다. 한 곳만 고치면 나머지가 반대로 가르친다.
"""
import os
import re

import hwpx_core as C
import hwpx_skeleton as HS
from hwpx_report_policy.length import _LEN_EXAMPLE, check_line_lengths
from hwpx_skeleton import guides
from hwpx_mcp.prompt import SYSTEM_PROMPT
from lxml import etree

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SKILL_MD = os.path.join(_REPO, "skill", "hwpx", "SKILL.md")
_VERB_END = ("함", "됨", "임", "둠")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

# 260831: 스킬이 둘로 갈렸다 — 엔진(hwpx)과 양식·관행(hwpx-template).
# 규칙이 '어디에' 적혔나가 아니라 '스킬 한 벌 안에 있나'를 본다.
_TPL_MD = os.path.join(_REPO, "skill", "hwpx-template", "SKILL.md")


def _skills():
    """엔진 + 양식 스킬을 이어 붙인 것 — 둘은 함께 올라간다."""
    return _read(_SKILL_MD) + "\n" + _read(_TPL_MD)



# ── 종결: 체언으로 끊는다 ─────────────────────────────────
def test_policy_length_examples_end_with_noun():
    # 모델은 숫자가 아니라 예시를 따라간다 — 예시가 '~함' 이면 그 어미가 돌아온다
    for marker, ex in _LEN_EXAMPLE.items():
        assert not ex.rstrip().endswith(_VERB_END), (marker, ex)


def test_exemplar_document_ends_with_noun():
    members = C.read_members(os.path.join(_REPO, "docs", "example_business_result.hwpx"))
    sec = etree.fromstring(members[C.section_names(members)[0]])
    for p in C.iter_body_paragraphs(sec):
        t = C.para_text(p).strip()
        if t and t[0] in "☐□◦":
            assert not t.endswith(_VERB_END), t


def test_writer_prompt_teaches_noun_ending():
    assert "체언" in SYSTEM_PROMPT
    # 옛 지시("개조식 문체 사용 (~하였음, …)")가 남아 있으면 안 된다.
    # 지금은 같은 어미를 '쓰지 않는다' 는 금지 예시로만 언급한다.
    assert "문체 사용 (~하였음" not in SYSTEM_PROMPT
    assert "용언 어미로 끝내지 않는다" in SYSTEM_PROMPT


# ── 계층: □→◦ 두 단계, '-' 는 새로 쓰지 않는다 ────────────
def test_skill_md_and_guidelines_agree_on_two_levels():
    skill = _skills()
    # 260928 — 스킬은 V4 문구로 가르친다: □ 는 ◦ 를 묶는 이름, □ 하나에 ◦ 둘~셋
    assert "항목(□) 하나에 세부(◦)를 둘~셋" in skill
    assert "□→◦→-" not in skill
    for name in os.listdir(guides.GUIDELINES_DIR):
        if not name.endswith(".md"):
            continue
        text = _read(os.path.join(guides.GUIDELINES_DIR, name))
        assert "□→◦→-" not in text, name
        assert "하위 항목(-)" not in text, name


def test_writer_prompt_does_not_recommend_dash_level():
    assert "□ ◦ - *" not in SYSTEM_PROMPT
    assert "□, ◦, - 등" not in SYSTEM_PROMPT


# ── 분량 규격: 한 벌만 존재 ───────────────────────────────
def test_length_spec_numbers_match_across_surfaces():
    skill = _skills()
    # 260928 — 스킬은 V4 규격(□ 30~38 한 줄 · ◦ 66~70)이고 엔진 경고 값과 같다
    for token in ("30~38자", "66~70자"):
        assert token in skill, token
    for old in ("68~76자", "68~72자"):
        assert old not in skill, old
    assert C.linebreak.DOT_TWO_LINE == (66, 70) and C.linebreak.BOX_ONE_LINE_MAX == 38
    # 261011 — writer 프롬프트도 같은 규격(옛 35~40/70~80·68~76·68~72 금지)
    assert "30~38자" in SYSTEM_PROMPT and "66~70자" in SYSTEM_PROMPT
    for old in ("68~76자", "68~72자", "최소 35자", "70~80"):
        assert old not in SYSTEM_PROMPT, old


def test_policy_examples_pass_their_own_spec():
    for ex in _LEN_EXAMPLE.values():
        assert check_line_lengths(ex) == [], ex


# ── 종결어 중복 금지 규칙이 문서에 있다 ────────────────────
def test_no_duplicate_ending_rule_documented():
    assert "끝 명사는 달리한다" in _skills()          # 260928 V4 문구


# ── 마커 글리프 교정에 경계 규칙이 적용된다 ────────────────
def test_render_keeps_body_chars_that_look_like_markers(tmp_path):
    r = HS.render("business_result", {"title": "경계 검증"}, output_dir=str(tmp_path),
                  body="1. 개요\n□ 상위 항목\n◦ 세부 내용\n○○부와 협의 완료\n"
                       "ㅁ자형 구조물 설치\n○ 별칭 정상\n· 미세 항목")
    assert r["status"] == "success"
    members = C.read_members(r["path"])
    sec = etree.fromstring(members[C.section_names(members)[0]])
    lines = [C.para_text(p).strip() for p in C.iter_body_paragraphs(sec)]
    assert "○○부와 협의 완료" in lines, lines      # 첫 글자 보존
    assert "ㅁ자형 구조물 설치" in lines, lines
    assert "◦ 별칭 정상" in lines, lines           # 별칭은 정식 기호로 교정
    assert any(l.startswith("·") for l in lines), lines   # · 를 - 로 바꾸지 않는다


# ── 첫 헤딩 앞 간격 (08-15) ───────────────────────────────
def test_first_heading_gap_is_eight_pt(tmp_path):
    """첫 헤딩 앞 빈 문단도 섹션 사이와 같은 8pt — 양식 원본은 1·3·5pt 로 제각각이었다."""
    import zipfile
    from lxml import etree
    import hwpx_skeleton as HS
    from hwpx_skeleton.style import GAP_BEFORE_FIRST_HEADING

    HH = "http://www.hancom.co.kr/hwpml/2011/head"
    HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    body = "1. 개요\n□ 첫 항목 내용 확인\n2. 다음\n□ 두 번째 항목 확인"
    for key in ("sample", "planning", "business_result", "training_result",
                "meeting_plan", "event_plan"):
        r = HS.render(key, {"title": "간격 검증"}, output_dir=str(tmp_path), body=body)
        assert r["status"] == "success", (key, r)
        assert r["body_result"].get("first_gap_pt") == GAP_BEFORE_FIRST_HEADING, key
        z = zipfile.ZipFile(r["path"])
        sec = etree.fromstring(z.read("Contents/section0.xml"))
        hdr = etree.fromstring(z.read("Contents/header.xml"))
        ch = {c.get("id"): int(c.get("height"))
              for c in hdr.iter(f"{{{HH}}}charPr")}
        paras = [p for p in sec if etree.QName(p.tag).localname == "p"]
        idx = None
        for i, p in enumerate(paras):
            txt = "".join(t.text or "" for t in p.iter(f"{{{HP}}}t")).strip()
            runs = p.findall(f"{{{HP}}}run")
            cid = runs[0].get("charPrIDRef") if runs else None
            if txt and ch.get(cid, 0) >= 1600 and p.find(f".//{{{HP}}}tbl") is None:
                idx = i
                break
        assert idx, f"{key}: 첫 헤딩을 찾지 못함"
        prev = paras[idx - 1]
        assert not "".join(t.text or "" for t in prev.iter(f"{{{HP}}}t")).strip(), key
        cid = prev.findall(f"{{{HP}}}run")[0].get("charPrIDRef")
        assert ch[cid] == GAP_BEFORE_FIRST_HEADING * 100, (key, ch[cid])


# ── 인쇄 방식(모아찍기) 정규화 (08-15) ────────────────────
def test_print_method_is_basic_not_nup(tmp_path):
    """settings.xml 의 PrintMethod=4(2쪽 모아 찍기)를 0(기본)으로 되돌린다.

    양식에 4 가 박혀 있어 복제 문서마다 따라붙었고, PDF 로 내보내면 A4 가로 한 장에
    두 쪽씩 붙어 나왔다(한/글 앱 설정이 아니라 **문서 파일 값**이 이긴다).
    """
    import re
    import zipfile
    import hwpx_skeleton as HS

    pat = re.compile(rb'name="PrintMethod" type="short">(\d+)<')
    for key in ("sample", "planning", "business_result", "training_result",
                "meeting_plan", "event_plan"):
        r = HS.render(key, {"title": "인쇄 방식 검증"}, output_dir=str(tmp_path),
                      body="1. 개요\n□ 인쇄 방식 확인용 본문")
        assert r["status"] == "success", (key, r)
        data = zipfile.ZipFile(r["path"]).read("settings.xml")
        m = pat.search(data)
        assert m, f"{key}: settings.xml 에 PrintMethod 가 없다"
        assert m.group(1) == b"0", (key, m.group(1))


# ── 규칙 전달 경로: 유형별 가이드에도 공통 규칙이 있다 (08-15) ──
def test_every_guideline_carries_common_rules():
    """get_writing_guide(유형) 만 읽어도 규칙을 받게 한다.

    종전에는 sample.md 에만 있어, planning 등 8개 유형은 가이드를 읽어도
    계층·분량·어절 규칙이 오지 않았다(규칙 전달 누수).
    """
    for name in os.listdir(guides.GUIDELINES_DIR):
        if not name.endswith(".md"):
            continue
        text = _read(os.path.join(guides.GUIDELINES_DIR, name))
        assert "## 공통 작성 규칙" in text, name
        for token in ("□ → ◦ 두 단계", "30~38자", "66~70자",
                      "어절 경계", "순수 명사", "첫 열 7자"):
            assert token in text, (name, token)


def test_guide_api_returns_common_rules():
    # 파일이 아니라 실제 API 반환값으로 확인 (로딩 경로가 끊기면 파일만 봐선 못 잡는다)
    for key in ("planning", "training_result", "meeting_plan", "event_result"):
        md = HS.get_writing_guide(key)
        assert "## 공통 작성 규칙" in md, key
        assert "어절 경계" in md, key


# ── 어절 경계·표 셀 한계가 SKILL.md 에도 있다 (08-15) ──────
def test_skill_md_documents_word_boundary_and_cell_limits():
    skill = _skills()
    # 260928 — 어절 경계는 엔진 경고(낱말 쪼개짐)가 알린다 · 표 셀 한계는 V4 문구
    assert "낱말이 줄 사이에서 쪼개짐" in skill
    assert "7자를 넘기면 접힌다" in skill and "13자를 넘기면 접힌다" in skill
    # writer 프롬프트에도 어절 규칙이 있어야 한다(종전부터 있던 문장)
    assert "낱말 중간에서 끊기지 않게" in SYSTEM_PROMPT


# ── 쪽 경계 보호: keepWithNext (08-15) ────────────────────
def test_keep_with_next_on_headings_and_before_tables(tmp_path):
    """헤딩·표앞·각주앞 문단만 다음과 묶는다. 본문 ◦ 까지 묶으면 쪽 끝에 큰 공백이 생긴다."""
    import zipfile
    from lxml import etree
    import hwpx_skeleton as HS

    HH = "http://www.hancom.co.kr/hwpml/2011/head"
    HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    body = "\n".join([
        "1. 개요", "□ (개요) 표 앞 항목 확인용 리드", "[표1]",
        "◦ 표 뒤에 오는 일반 서술 문단으로 묶이지 않아야 하는 자리",
        "2. 다음", "□ (근거) 각주* 붙은 항목", "* 각주: 설명 줄",
    ])
    r = HS.render("planning", {"title": "쪽 보호 검증"}, output_dir=str(tmp_path),
                  body=body, tables=[{"headers": ["구분", "값"], "rows": [["가", "1"]]}])
    assert r["status"] == "success", r
    assert r["body_result"]["kept_with_next"] > 0

    z = zipfile.ZipFile(r["path"])
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    keep = {pp.get("id") for pp in hdr.iter(f"{{{HH}}}paraPr")
            if any(bs.get("keepWithNext") == "1"
                   for bs in pp.iter(f"{{{HH}}}breakSetting"))}
    assert keep, "keepWithNext paraPr 가 생성되지 않았다"

    def text(p):
        return "".join(t.text or "" for t in p.iter(f"{{{HP}}}t")).strip()

    on, off = [], []
    for p in sec.iter(f"{{{HP}}}p"):
        t = text(p)
        if not t:
            continue
        (on if p.get("paraPrIDRef") in keep else off).append(t)

    # 헤딩은 자동 번호라 텍스트에 '1.' 이 남지 않는다 — 제목 글자로 찾는다
    assert "개요" in on and "다음" in on, on                # 헤딩
    assert any("(개요)" in t for t in on), on               # 표 앞 항목
    assert any("(근거)" in t for t in on), on               # 각주 앞 항목
    # 표 뒤 일반 서술은 묶이지 않는다
    assert any(t.startswith("◦") and "표 뒤에" in t for t in off), off


# ── 표 규격: 두 생성 경로가 같은 값을 쓴다 (08-15) ────────
def test_table_spec_is_single_source():
    """모드 A(skeleton)와 모드 B(hwpx_full)의 표 폭·행높이가 같아야 한다.

    종전에는 각자 하드코딩해 전체 폭 46063 vs 47531, 첫 열 10231 vs 9099 로
    갈렸다. 모드 B 는 lxml 없는 환경의 폴백이라 평소엔 안 드러나지만, 정작
    폴백이 작동하는 순간 같은 본문이 다른 모양으로 나온다.
    """
    import importlib.util

    from hwpx_core import tablespec
    from hwpx_skeleton import renderer as R

    # 모드 A 별칭이 단일 기준을 그대로 쓴다
    assert R.TABLE_TOTAL_W == tablespec.TOTAL_W
    assert R.TABLE_FIRST_W == tablespec.FIRST_W
    assert R.TABLE_ROW_H == tablespec.ROW_H
    assert R.TABLE_LEAD_SPACES == tablespec.LEAD_SPACES

    # 모드 B 는 vendor 를 파일째 적재한다 — 빌드 산출물이 있을 때만 검사
    full_py = os.path.join(_REPO, "skill", "hwpx", "scripts", "hwpx_full.py")
    vendor = os.path.join(_REPO, "skill", "hwpx", "scripts", "vendor",
                          "hwpx_core", "tablespec.py")
    if not os.path.exists(vendor):
        return  # build_skill.py 미실행 상태
    spec = importlib.util.spec_from_file_location("_vendor_tablespec", vendor)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.TOTAL_W == tablespec.TOTAL_W
    assert mod.FIRST_W == tablespec.FIRST_W
    assert mod.ROW_H == tablespec.ROW_H
    assert mod.col_widths(3) == tablespec.col_widths(3)

    # 옛 하드코딩 값이 되살아나지 않게 — 주석의 이력 설명은 걸러내고 할당문만 본다.
    # 261011 부터 모드 B 는 표를 엔진에 맡겨 이 치수를 들고 있지 않다. 다시 생기면
    # 단일 기준(_TBL_MOD)에서 읽어야 한다.
    src = _read(full_py)
    names = ("_TABLE_WIDTH", "_TABLE_FIRST_W", "_CELL_HEIGHT",
             "_IMG_CELL_H", "_IMG_CAPTION_H")     # 치수만(테두리 ID 등은 제외)
    assigns = [l for l in src.splitlines()
               if any(re.match(rf"\s*{n}\s*=", l) for n in names)]
    for line in assigns:
        assert "_TBL_MOD." in line, line          # 전부 단일 기준에서 읽어야 한다
        assert not re.search(r"=\s*\d", line), line   # 숫자 직접 대입 금지


def test_col_widths_keeps_total_and_first_column():
    from hwpx_core import tablespec
    for n in range(1, 7):
        w = tablespec.col_widths(n)
        assert len(w) == n
        assert sum(w) == tablespec.TOTAL_W, n
        if n > 1:
            assert w[0] == tablespec.FIRST_W, n


# ── 두 진입점이 같은 문서를 낸다 (08-16) ──────────────────
def test_mode_a_and_b_produce_same_document(tmp_path):
    """모드 B(hwpx_full.Doc)는 모드 A 와 같은 엔진을 부르는 얇은 어댑터다.

    종전에는 B 가 XML 을 따로 조립해, 같은 본문이 경로에 따라 다른 문서가 됐다.
    """
    import importlib.util
    import re
    import sys
    import zipfile

    import hwpx_skeleton as HS

    scripts = os.path.join(_REPO, "skill", "hwpx", "scripts")
    if not os.path.exists(os.path.join(scripts, "vendor", "hwpx_skeleton")):
        import pytest
        pytest.skip("skill vendor/ 미생성 — python skill/build_skill.py 후 실행")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "_hwpx_full_parity", os.path.join(scripts, "hwpx_full.py"))
    full = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(full)

    body = ["1. 개요", "□ (검증) 두 진입점 결과 비교",
            "◦ 같은 본문을 넣으면 같은 문서가 나와야 한다는 규칙 확인", "[표1]"]
    table = {"headers": ["구분", "값"], "rows": [["가", "1"], ["나", "2"]]}

    a = HS.render("sample", {"title": "진입점 대조"}, body="\n".join(body),
                  tables=[table], output_dir=str(tmp_path), filename="modeA")
    assert a["status"] == "success", a

    doc = full.Doc("진입점 대조")
    doc.body("\n".join(body[:-1]))            # [표1] 은 table() 이 자리를 만든다
    t = doc.table(3, 2)
    for r, row in enumerate([table["headers"]] + table["rows"]):
        for c, v in enumerate(row):
            t.cell(r, c, v)
    b_path = doc.save(os.path.join(str(tmp_path), "modeB.hwpx"))

    def digest(path):
        xml = zipfile.ZipFile(path).read("Contents/section0.xml").decode("utf-8")
        texts = [x for x in re.findall(r"<hp:t>([^<]*)</hp:t>", xml) if x.strip()]
        cells = re.findall(r'<hp:cellSz width="(\d+)" height="(\d+)"', xml)
        return texts, cells

    ta, ca = digest(a["path"])
    tb, cb = digest(b_path)
    assert ta == tb, (ta, tb)
    assert ca == cb, (ca, cb)


def test_mode_b_has_no_own_xml_assembly():
    """모드 B 가 XML 을 다시 자체 조립하지 않는지 — 두 벌로 갈라지는 회귀 방지."""
    src = _read(os.path.join(_REPO, "skill", "hwpx", "scripts", "hwpx_full.py"))
    assert "import hwpx_skeleton" in src, "모드 B 가 엔진을 부르지 않는다"
    for gone in ("<hp:tc ", "<hp:tbl ", "<hp:cellSz", "__BODY_CONTENT__"):
        assert gone not in src, f"자체 XML 조립 잔존: {gone}"


# ── 양식 선택 판단 규칙이 문서에 있다 (08-16) ─────────────
def test_skill_md_has_template_choice_rules():
    """'쓸 수 있다'만 있고 '언제 쓰라'가 없으면 판단이 흔들린다.

    특히 파일 없이 "우리 양식으로" 라고만 했을 때 임의로 내장 양식을 골라
    진행하면, 사용자는 자기 서식으로 나온 줄 알고 결재에 올린다.
    """
    skill = _skills()
    assert "### 양식 선택 규칙" in skill
    for token in ("파일을 달라고 요청",          # 파일 없이 진행 금지
                  "inspect_template",            # 먼저 진단
                  "묻는다",                      # 못 쓰는 양식이면 확인
                  "조용히 다른 양식으로 바꿔 찍지 않는다"):
        assert token in skill, token


# ── 스킬 판 번호(rev) 표기 (08-16) ────────────────────────
def test_skill_md_carries_rev_marker():
    """업로드한 스킬이 어느 판인지 파일명으로 알 수 있어야 한다.

    번호의 단일 출처는 SKILL.md 의 주석이고, build_skill.py 가 그것을 읽어
    `hwpx-skill-rev{N}.zip` 으로 내보낸다. 표기가 사라지면 빌드가 실패한다.
    """
    import re as _re

    skill = _skills()
    m = _re.search(r"<!--\s*skill-rev:\s*(\d+)\s*-->", skill)
    assert m, "SKILL.md 에 '<!-- skill-rev: N -->' 표기가 없다"
    rev = int(m.group(1))
    assert rev >= 1
    # 본문에도 사람이 읽을 수 있게 같은 번호가 있어야 한다(주석만 있으면 안 보인다)
    assert f"**rev {rev}**" in skill, rev

    build = _read(os.path.join(_REPO, "skill", "build_skill.py"))
    assert "skill-rev" in build and "hwpx-skill-rev" in build


# ── 일정 줄 날짜 자릿수 (08-16) ───────────────────────────
def test_schedule_date_padded_in_all_rule_files():
    """한 자리 월은 두 자리보다 좁아 앞쪽 탭 스톱에 멈춘다.

    규칙을 한 곳에만 적으면 다른 경로가 반대로 가르친다(08-15 감사 4번).
    SKILL.md 의 **예시**까지 봐야 한다 — 예시가 안 메운 날짜면 규칙 문장이
    있어도 모델은 예시를 따라간다.
    """
    skill = _skills()
    # 260928 — 스킬 원고는 `'26. 8월` 꼴이고 한 자리 월 패딩은 렌더러가 한다(엔진 스킬 표에 적혀 있다)
    assert "한 자리 월은 앞에 공백 한 칸" in skill and "렌더러가 보정" in skill
    assert "’26. 9." not in skill, "SKILL.md 예시가 아직 안 메운 날짜다"

    for name in os.listdir(guides.GUIDELINES_DIR):
        if name.endswith(".md"):
            assert "한 자리 월·일" in _read(os.path.join(guides.GUIDELINES_DIR, name)), name
    assert "한 자리 월·일 앞에는 공백" in SYSTEM_PROMPT


def test_renderer_pads_schedule_date():
    """규칙을 아는 것과 지켜지는 것은 다르다 — 렌더 결과로 확인한다."""
    import tempfile

    body = ("1. 추진배경\n□ (배경) 표준 서식 정착\n"
            "◦ ’26. 9.\t: 표준 모델 설계\n◦ ’26. 10.\t: 시범 적용")
    r = HS.render("planning", {"title": "일정 자릿수"},
                  output_dir=tempfile.mkdtemp(), body=body)
    assert r["status"] == "success"
    members = C.read_members(r["path"])
    sec = etree.fromstring(members[C.section_names(members)[0]])
    lines = [C.para_text(p) for p in C.iter_body_paragraphs(sec)]
    sched = [t for t in lines if "표준 모델 설계" in t]
    assert sched and "’26.  9." in sched[0], sched
    # 탭 앞 폭이 두 자리 월 줄과 같아야 열이 선다
    other = [t for t in lines if "시범 적용" in t][0]
    assert len(sched[0].split("\t")[0]) == len(other.split("\t")[0])


# ── 쪽 단위 분량 감각 (08-16) ─────────────────────────────
def test_page_budget_rule_in_all_rule_files():
    """자수 규격만 있고 쪽 감각이 없으면 '2쪽으로' 요청에서 분량이 어긋난다.

    실제로 겪은 실패다 — 1.1쪽치 본문을 2쪽 양식에 담아 마지막 블록만 넘어가고,
    리드(□)만 1쪽 끝에 남았다. 고칠 자리는 조판이 아니라 본문 분량이었다.
    """
    skill = _skills()
    # 260928 — 스킬은 쪽 감각을 줄 수 대신 재는 기계(view_layout)로 준다
    for token in ("view_layout(md, target_pages", "줄이라는 요청은 줄을 지우라는 뜻",
                  "표는 머리글까지 행마다 약 0.04장"):
        assert token in skill, token

    for name in os.listdir(guides.GUIDELINES_DIR):
        if name.endswith(".md"):
            text = _read(os.path.join(guides.GUIDELINES_DIR, name))
            assert "쪽수는 양식이 아니라" in text, name
            assert "29~32줄" in text, name
    assert "29~32줄" in SYSTEM_PROMPT
