# -*- coding: utf-8 -*-
"""hwpx-skeleton 렌더 동작/방어 테스트."""
import os
import zipfile
import tempfile

import hwpx_skeleton as HS
import hwpx_skeleton.renderer as R


def test_render_roundtrip():
    out = tempfile.mkdtemp()
    r = HS.render("planning",
                  {"title": "테스트 보고서"},
                  output_dir=out,
                  body="1. 추진배경\n□ 핵심 항목\n◦ 배경과 원인을 담은 세부 설명 문장",
                  intent="테스트 보고")
    assert r["status"] == "success"
    assert r["body_result"]["filled"] is True
    assert os.path.getsize(r["path"]) > 1000


def test_list_templates():
    tpls = HS.list_templates()
    # 기본(plain) + 공문서 셋. plain 이 앞에 서는 것은 기본으로 쓰는 자리라서다(260831).
    assert [t["key"] for t in tpls] == ["plain", "plan", "result", "review"]
    assert all(t["exists"] for t in tpls)


def test_paren_shrink():
    """0.2.3: 문장 중간 부연 괄호만 2pt 작게(라벨 괄호·헤딩은 그대로)."""
    import zipfile
    from lxml import etree
    r = HS.render("sample", {"title": "괄호"}, output_dir=tempfile.mkdtemp(),
                  body="1. 개요\n□ 운영비 15% 절감(월 0.8억원), 확대 필요\n"
                       "◦ 1단계(북부) : 갑동, 을동 등 5개소")
    z = zipfile.ZipFile(r["path"])
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    HH = hdr.nsmap.get("hh")
    heights = {cp.get("id"): int(cp.get("height"))
               for cp in hdr.iter(f"{{{HH}}}charPr")}
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    HP = sec.nsmap.get("hp")
    seen = {}
    for run in sec.iter(f"{{{HP}}}run"):
        txt = "".join(t.text or "" for t in run.iter(f"{{{HP}}}t")).strip()
        if txt:
            seen[txt] = heights.get(run.get("charPrIDRef"))
    assert seen["(월 0.8억원)"] == 1300                       # 15pt → 13pt
    # 앞뒤 조각은 본문 크기 그대로 (마커는 ☐ 로 정규화됨)
    assert seen["☐ 운영비 15% 절감"] == 1500
    # 09-22: '1단계(북부)' 의 괄호는 더는 위첨자로 떨어져 나가지 않는다 — 줄이 한 조각 그대로, 본문 크기
    assert "북부" not in seen and seen["◦ 1단계(북부) : 갑동, 을동 등 5개소"] == 1500


def test_sample_template_four_sections():
    """0.2.3: sample 뼈대 — 4단 견본이 body 로 교체되고 유형명 흔적이 없다."""
    import zipfile
    from lxml import etree
    import hwpx_core as C
    out = tempfile.mkdtemp()
    r = HS.render("sample", {"title": "제목"}, output_dir=out,
                  body="1. 개요\n□ 핵심 항목\n2. 주요내용\n□ 내용\n"
                       "3. 추진방안\n□ 방안\n4. 향후계획\n□ 일정",
                  intent="취지 한 줄")
    assert r["status"] == "success" and r["body_result"]["filled"] is True
    z = zipfile.ZipFile(r["path"])
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    charmap = C.parse_charmap(z.read("Contents/header.xml"))
    heads = [C.para_text(p).strip() for p in sec.iter()
             if etree.QName(p.tag).localname == "p"
             and (C.para_charsize(p, charmap) or 0) >= 16
             and C.para_text(p).strip()]
    assert heads[-4:] == ["개요", "주요내용", "추진방안", "향후계획"]


def test_unknown_template_returns_error():
    r = HS.render("nope", {}, output_dir=tempfile.mkdtemp())
    assert r["status"] == "error"


def test_non_string_args_do_not_crash():
    """2차 리뷰: 정수 title(슬러그)·리스트 body·리스트 fields 도 크래시 없이 처리."""
    out = tempfile.mkdtemp()
    r = HS.render("planning", {"title": 2026}, output_dir=out)   # 비문자열 title
    assert r["status"] == "success"
    r2 = HS.render("planning", ["not", "a", "dict"], output_dir=out,
                   body=["리스트", "본문"], intent=123)           # 전부 비정형
    assert r2["status"] == "success"                              # 빈값 취급, 안내문구 유지


def test_bold_body_line_renders_box_size():
    """2차 리뷰 M2: '**□ …**' 줄이 참고(13pt)가 아닌 □(15pt)로 렌더."""
    out = tempfile.mkdtemp()
    r = HS.render("planning", {"title": "t"}, output_dir=out,
                  body="1. 개요\n**□ 중요 항목**\n◦ 세부 내용 설명 문장")
    assert r["status"] == "success" and r["body_result"]["filled"] is True
    import lxml.etree as ET
    import hwpx_core as C
    members = C.read_members(r["path"])
    xml = members[C.SECTION0].decode("utf-8")
    assert "중요 항목" in xml and "**" not in xml


def test_corrupt_template_section_missing(monkeypatch):
    # #5(코드리뷰): section0.xml 없는 손상 스켈레톤 → KeyError 아닌 error dict
    d = tempfile.mkdtemp()
    with zipfile.ZipFile(os.path.join(d, R.STANDARD_TEMPLATE), "w") as z:
        z.writestr("mimetype", b"application/hwp+zip")   # section0.xml 없음
    monkeypatch.setattr(R, "TEMPLATE_DIR", d)
    r = R.render("plan", {"title": "x"}, output_dir=d,
                 body="1. 추진배경\n□ 항목\n◦ 세부")
    assert r["status"] == "error" and "섹션" in r["message"]


def test_tables_and_image_caption_alias(tmp_path):
    """0.2.0 표/이미지자리 + 단수 'caption' 오입력 승격(Agent 흔한 실수)."""
    r = HS.render("planning", {"title": "표이미지"},
                  output_dir=str(tmp_path),
                  body="1. 배경\n□ 항목",
                  tables=[{"headers": ["구분", "내용"], "rows": [["1", "시범"]]}],
                  images=[{"caption": "구성도"}])
    assert r["status"] == "success"
    assert r["body_result"]["tables_added"] == 1
    assert r["body_result"]["images_added"] == 1
    sec = zipfile.ZipFile(r["path"]).read("Contents/section0.xml").decode("utf-8")
    assert "이미지 삽입" in sec
    assert "구성도" in sec        # 별칭 승격으로 캡션 반영
    assert "시범" in sec          # 표 데이터 반영

    # 헤더행만 볼드 — 데이터행은 볼드 제거 (그리드 프로토가 전 행 볼드였음)
    import re
    hdrx = zipfile.ZipFile(r["path"]).read("Contents/header.xml").decode("utf-8")
    bold_ids = set(re.findall(
        r'<hh:charPr id="(\d+)"(?:(?!</hh:charPr>).)*?<hh:bold/>', hdrx, re.S))
    tblx = re.search(r'<hp:tbl id="2000000001".*?</hp:tbl>', sec, re.S).group(0)
    rows_x = re.findall(r"<hp:tr>.*?</hp:tr>", tblx, re.S)
    hdr_cids = set(re.findall(r'charPrIDRef="(\d+)"', rows_x[0]))
    data_cids = set(re.findall(r'charPrIDRef="(\d+)"', rows_x[1]))
    assert hdr_cids & bold_ids, "표 헤더행이 볼드가 아님"
    assert not (data_cids & bold_ids), "표 데이터행에 볼드 잔존"


def test_label_formats():
    """0.2.3: 말머리 라벨=굵게 · 부연 괄호=2pt 작게 · 09-22: '1단계(북부)' 라벨은 위첨자 아님(괄호 보존)."""
    import zipfile
    from lxml import etree
    r = HS.render("sample", {"title": "서식"}, output_dir=tempfile.mkdtemp(),
                  body=("1. 개요\n□ (필요성) 절감(연 12억원) 확인\n"
                        "2. 추진방안\n◦ 1단계(북부) : 갑동 등 5개소"))
    z = zipfile.ZipFile(r["path"])
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    HH = hdr.nsmap.get("hh")
    info = {}
    for cp in hdr.iter(f"{{{HH}}}charPr"):
        flags = {etree.QName(c).localname for c in cp}
        info[cp.get("id")] = (int(cp.get("height")),
                              "bold" in flags, "supscript" in flags)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    HP = sec.nsmap.get("hp")
    seen = {}
    for run in sec.iter(f"{{{HP}}}run"):
        txt = "".join(t.text or "" for t in run.iter(f"{{{HP}}}t")).strip()
        if txt:
            seen[txt] = info.get(run.get("charPrIDRef"))
    assert seen["필요성"] == (1500, True, False)      # 말머리 = 굵게
    assert "북부" not in seen                                              # 09-22: 괄호 라벨 위첨자 뗌
    assert seen["◦ 1단계(북부) : 갑동 등 5개소"] == (1500, False, False)   # 줄 그대로 · 굵지도 위첨자도 아님
    assert seen["(연 12억원)"] == (1300, False, False)  # 부연 = 2pt 작게


def test_label_hanging_indent():
    """0.2.3: 말머리('☐ (필요성) …') 줄은 내어쓰기를 여는 괄호 폭만큼 더 준다.

    실측: 기본 □ 30.7pt(-6140) → 말머리 줄 37.68pt(-7536).
    접힌 둘째 줄이 여는 괄호 다음에 맞춰 떨어지게 하는 관례.
    """
    import re
    import zipfile
    r = HS.render("sample", {"title": "내어쓰기"}, output_dir=tempfile.mkdtemp(),
                  body=("1. 개요\n□ (점검결과) 균열 12건 확인, 우기 전 보수 필요\n"
                        "□ 말머리 없는 항목 줄"))
    hdr = zipfile.ZipFile(r["path"]).read("Contents/header.xml").decode("utf-8")
    intents = re.findall(r'<hh:paraPr id="\d+"(?:(?!</hh:paraPr>).)*?'
                         r'intent value="(-\d+)"', hdr, re.S)
    assert "-7536" in intents, "말머리 줄 내어쓰기 보정이 없다"
    assert "-6140" in intents, "말머리 없는 줄은 기본 내어쓰기여야 한다"


def test_version_matches_pyproject():
    """__version__ 과 pyproject version 이 어긋나면 배포 때 휠 판 확인이 헛돈다."""
    import re
    from pathlib import Path
    pkg = Path(R.__file__).resolve().parents[2]          # …/packages/hwpx-skeleton
    toml_path = pkg / "pyproject.toml"
    if not toml_path.exists():                            # 휠 설치본에서는 건너뛴다
        import pytest
        pytest.skip("소스 체크아웃에서만 검사")
    toml = toml_path.read_text(encoding="utf-8")
    declared = re.search(r'^version = "([\d.]+)"', toml, re.M).group(1)
    assert HS.__version__ == declared, f"{HS.__version__} != {declared}"


def _xml_invariants(path):
    """생성 문서의 구조 불변식 — id 유일·itemCnt 정합·dangling ref 0·secPr 1개."""
    import zipfile
    from lxml import etree
    z = zipfile.ZipFile(path)
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    HH, HP = hdr.nsmap.get("hh"), sec.nsmap.get("hp")
    char_ids = [c.get("id") for c in hdr.iter(f"{{{HH}}}charPr")]
    para_ids = [p.get("id") for p in hdr.iter(f"{{{HH}}}paraPr")]
    assert len(char_ids) == len(set(char_ids)), "charPr id 중복"
    assert len(para_ids) == len(set(para_ids)), "paraPr id 중복"
    cp_box = hdr.find(f".//{{{HH}}}charProperties")
    pp_box = hdr.find(f".//{{{HH}}}paraProperties")
    assert int(cp_box.get("itemCnt")) == len(char_ids), "charPr itemCnt 불일치"
    assert int(pp_box.get("itemCnt")) == len(para_ids), "paraPr itemCnt 불일치"
    used_c = {r.get("charPrIDRef") for r in sec.iter(f"{{{HP}}}run")}
    used_p = {p.get("paraPrIDRef") for p in sec.iter(f"{{{HP}}}p")}
    assert used_c <= set(char_ids) | {None}, "존재하지 않는 charPr 참조"
    assert used_p <= set(para_ids) | {None}, "존재하지 않는 paraPr 참조"
    assert len(list(sec.iter(f"{{{HP}}}secPr"))) == 1, "secPr 개수 이상"
    return len(char_ids), len(para_ids)


def test_structure_invariants_and_no_charpr_explosion():
    """0.2.3: charPr 생성기가 3종 늘었다 — 구조 정합과 증식 상한을 함께 고정."""
    lines = ["1. 개요"]
    for i in range(60):
        lines.append("□ (필요성%d) 절감(월 %d억원) 확인, 1단계(북부) 확대 필요" % (i, i))
        lines.append("◦ 세부 %d 줄로 부연(연 12억원)과 라벨 2단계(남부권) 을 함께 담는다" % i)
    r = HS.render("sample", {"title": "불변식"}, output_dir=tempfile.mkdtemp(),
                  body="\n".join(lines))
    assert r["status"] == "success"
    n_char, n_para = _xml_invariants(r["path"])
    assert n_char < 60, f"charPr 증식({n_char})"     # 캐시가 base 단위로 도는지
    assert n_para < 60, f"paraPr 증식({n_para})"


def test_intent_dropped_without_body():
    """0.2.3: body 없이 렌더해도 취지 견본 문구가 남지 않는다."""
    import zipfile
    r = HS.render("sample", {"title": "취지"}, output_dir=tempfile.mkdtemp())
    sec = zipfile.ZipFile(r["path"]).read("Contents/section0.xml").decode("utf-8")
    assert "보고 취지" not in sec and "\U000f0090" not in sec


def test_reference_line_keeps_parentheses():
    """0.2.3: '*' 참고 줄은 서식 분할 대상이 아니다 — 괄호 문자가 유실되면 안 된다."""
    import zipfile
    r = HS.render("sample", {"title": "참고"}, output_dir=tempfile.mkdtemp(),
                  body="1. 개요\n□ 항목\n* 참고 문구(북부) 및 절감(연 12억원) 이다")
    sec = zipfile.ZipFile(r["path"]).read("Contents/section0.xml").decode("utf-8")
    assert "참고 문구(북부)" in sec and "(연 12억원)" in sec


def test_table_width_and_indent():
    """0.2.3: 표·이미지자리 폭 162.5mm(46063) 고정 · 앞 들여쓰기 3칸."""
    import re
    import zipfile
    r = HS.render("sample", {"title": "표"}, output_dir=tempfile.mkdtemp(),
                  body="1. 개요\n□ 항목\n[표1]\n[이미지1]",
                  tables=[{"headers": ["구분", "값"], "rows": [["a", "1"]]}],
                  images=[{"count": 1, "captions": ["구성도"]}])
    sec = zipfile.ZipFile(r["path"]).read("Contents/section0.xml").decode("utf-8")
    widths = re.findall(r'<hp:sz width="(\d+)"[^>]*height="\d+"', sec)
    assert widths.count("46063") >= 2, f"표/이미지자리 폭 불일치: {widths}"
    assert sec.count("<hp:t>   </hp:t>") >= 2, "표·이미지자리 앞 3칸 들여쓰기 없음"


def test_tab_becomes_hp_tab():
    """0.2.3: 일정 줄의 탭 문자가 <hp:tab/> 요소로 변환된다."""
    import zipfile
    r = HS.render("sample", {"title": "탭"}, output_dir=tempfile.mkdtemp(),
                  body="1. 향후계획\n□ '26. 9월\t투자심의 상정")
    sec = zipfile.ZipFile(r["path"]).read("Contents/section0.xml").decode("utf-8")
    assert "<hp:tab/>" in sec and "투자심의 상정" in sec


# ── 【주관】 줄 한 줄 맞춤 ────────────────────────────────────────────────
# 견본 담당자가 셋이면 줄이 판면(48188)을 넘어 날짜 꼬리('18)')가 둘째 줄에
# 떨어진다(08-18 실물). 장평 95% + 오른쪽 정렬로 맞추되 **글자는 안 바꾼다**.

def _owner_para(path):
    import re
    z = zipfile.ZipFile(path)
    sec = z.read("Contents/section0.xml").decode("utf-8")
    hdr = z.read("Contents/header.xml").decode("utf-8")
    i = sec.find("【주관】")
    assert i > 0, "견본에 【주관】 줄이 없다"
    para = sec[sec.rfind("<hp:p ", 0, i):sec.find("</hp:p>", i) + 7]
    return para, hdr


def _prop(hdr, kind, pid):
    import re
    m = re.search(r'<hh:%s id="%s"[ >].*?</hh:%s>' % (kind, pid, kind), hdr, re.S)
    assert m, (kind, pid)
    return m.group(0)


def test_주관_줄은_장평_95로_한_줄에_들어간다():
    import re
    r = HS.render("plan", {"title": "주관"}, output_dir=tempfile.mkdtemp())
    assert r["owner_line_fitted"] is True
    para, hdr = _owner_para(r["path"])
    cids = sorted(set(re.findall(r'charPrIDRef="(\d+)"', para)), key=int)
    assert cids, para
    for cid in cids:
        ratio = re.search(r'<hh:ratio[^/]*/>', _prop(hdr, "charPr", cid)).group(0)
        # 한 종류만 줄이면 숫자·괄호가 그대로 남아 줄이 여전히 넘친다
        assert set(re.findall(r'="(\d+)"', ratio)) == {str(R.OWNER_RATIO)}, ratio


def test_주관_줄_자간은_손대지_않는다():
    """양식이 -1/-3/-7 로 이미 잡아 뒀다 — 장평과 같이 줄이면 글자가 뭉개진다."""
    import re
    r = HS.render("plan", {"title": "주관"}, output_dir=tempfile.mkdtemp())
    para, hdr = _owner_para(r["path"])
    got = set()
    for cid in set(re.findall(r'charPrIDRef="(\d+)"', para)):
        sp = re.search(r'<hh:spacing[^/]*/>', _prop(hdr, "charPr", cid)).group(0)
        got |= set(re.findall(r'="(-?\d+)"', sp))
    assert got == {"-1", "-3", "-7"}, got


def test_주관_줄은_오른쪽_정렬로_날짜_꼬리를_끝에_붙인다():
    import re
    r = HS.render("plan", {"title": "주관"}, output_dir=tempfile.mkdtemp())
    para, hdr = _owner_para(r["path"])
    ppid = re.search(r'paraPrIDRef="(\d+)"', para).group(1)
    align = re.search(r'<hh:align[^/]*/>', _prop(hdr, "paraPr", ppid)).group(0)
    assert 'horizontal="RIGHT"' in align, align


def test_주관_줄_맞춤이_글자를_바꾸지_않는다():
    """담당자·직급·내선은 사람이 한/글에서 고치는 자리다 — 줄여서도 잘라서도 안 된다."""
    import re
    day = "’26. 8. 19"
    r = HS.render("plan", {"title": "주관", "date": day},
                  output_dir=tempfile.mkdtemp())
    para, _ = _owner_para(r["path"])
    txt = "".join(re.findall(r"<hp:t>(.*?)</hp:t>", para, re.S))
    assert "홍길동 처장(0000)" in txt and "김철수 부장(0001)" in txt, txt
    assert "이몽룡 과장(0002)" in txt and day in txt, txt


def test_본문_없이_렌더해도_주관_줄은_맞춘다():
    """견본 담당자 셋은 본문이 없어도 넘친다 — 본문 유무와 무관한 조치다."""
    r = HS.render("result", {"title": "본문 없음"}, output_dir=tempfile.mkdtemp())
    assert r["status"] == "success" and r["owner_line_fitted"] is True
