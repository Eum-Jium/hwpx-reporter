# -*- coding: utf-8 -*-
"""붙임 별지 — 본문 뒤에 상세자료를 붙이는 경로.

실무 보고서는 본문을 1~3쪽으로 끊고 상세자료를 뒤로 뺀다. 그 별지가 붙임이다.
정본(08-18 요청서 견본) 실측을 기준으로 삼았고, 그 견본에서 쪽 나눔이 명시된
곳은 붙임 넷 중 하나뿐이었다 — 나머지는 앞 내용이 길어 우연히 넘어간 것이라
본문이 몇 줄만 줄어도 표제가 앞쪽 하단에 남는다. 여기서는 표제마다 쪽을 끊는다.
"""
import os
import re

import hwpx_core as C
from hwpx_skeleton import render
from hwpx_skeleton import renderer as R

BODY = "\n".join([
    "1. 추진배경", "□ 배경 한 줄",
    "2. 주요내용", "◦ 내용 한 줄",
    "3. 추진방안", "□ 방안 한 줄",
    "4. 향후계획", "□ 추진 일정",
    "◦ ’26.  9.\t: 착수", "◦ ’26. 10.\t: 시행", "◦ ’26. 11.\t: 점검",
])
ATTS = [
    {"title": "세부 편성표", "body": "□ (편성) 과정별 구성",
     "tables": [{"headers": ["과정", "대상"], "rows": [["기본", "전 직원"]]}]},
    {"title": "제출 서식", "body": "□ (작성) 부서별로 적어 제출"},
]


def _paras(path):
    m = C.read_members(path)
    sec = C.xmlcompat.parse(m[C.section_names(m)[0]])
    return list(C.iter_body_paragraphs(sec))


# ── 목록: 본문 끝에 붙고 '끝.' 으로 닫는다 ─────────────────
def test_list_lines_numbered_and_closed():
    lines = R.attach_list_lines(["가", "나", "다"])
    assert lines[0] == "붙임  1. 가."
    assert lines[1].startswith(" " * C.tablespec.ATTACH_LIST_INDENT + "2.")
    assert lines[-1].endswith("  끝.")


def test_single_attachment_is_not_numbered():
    # 하나뿐이면 번호를 매기지 않는다(실무 관례)
    assert R.attach_list_lines(["계획서"]) == ["붙임  계획서 1부.  끝."]


def test_no_attachment_no_list():
    assert R.attach_list_lines([]) == [] and R.attach_list_lines(None) == []


# ── 별지: 쪽을 새로 열고 표제를 세운다 ─────────────────────
def test_each_attachment_starts_a_new_page(tmp_path):
    r = render("plan", {"title": "붙임"}, body=BODY, attachments=ATTS,
               output_dir=str(tmp_path))
    assert r["status"] == "success" and r["warnings"] == []
    assert r["body_result"]["attachments_added"] == 2

    # 표제만 고른다 — 목록 줄('붙임  1. …')과 섞이지 않게 번호 형태로 거른다
    caps = [p for p in _paras(r["path"])
            if re.match(r"^붙임 \d", C.para_text(p).strip())]
    assert len(caps) == 2
    for cap in caps:
        assert cap.get("pageBreak") == "1", "별지는 쪽을 새로 연다"


def test_caption_carries_number_and_title(tmp_path):
    r = render("plan", {"title": "붙임"}, body=BODY, attachments=ATTS,
               output_dir=str(tmp_path), filename="cap")
    texts = [C.para_text(p).strip() for p in _paras(r["path"])]
    assert any(t.startswith("붙임 1") and "세부 편성표" in t for t in texts)
    assert any(t.startswith("붙임 2") and "제출 서식" in t for t in texts)
    # 목록도 함께 있어야 한다 — 목록만 있고 별지가 없으면 읽는 사람이 찾지 못한다
    assert any(t.startswith("붙임  1. 세부 편성표.") for t in texts)


def test_attachment_tables_are_rendered(tmp_path):
    r = render("plan", {"title": "붙임"}, body=BODY, attachments=ATTS,
               output_dir=str(tmp_path), filename="tbl")
    assert r["body_result"]["tables_added"] == 1
    texts = [C.para_text(p).strip() for p in _paras(r["path"])]
    assert any("기본" in t and "전 직원" in t for t in texts)


def test_body_only_document_is_unchanged(tmp_path):
    # 붙임을 안 주면 목록도 별지도 생기지 않는다
    r = render("plan", {"title": "본문만"}, body=BODY, output_dir=str(tmp_path),
               filename="plain")
    texts = [C.para_text(p).strip() for p in _paras(r["path"])]
    assert not any(t.startswith("붙임") for t in texts)
    assert r["body_result"].get("attachments_added", 0) == 0


# ── 표제는 양식 견본을 복제한다 ────────────────────────────
def test_standard_template_carries_a_caption_prototype():
    # 폭·테두리·정렬을 코드로 지어내면 정본과 어긋난다(표제가 가운데로 몰렸다).
    # 표와 같이 **양식 안의 견본**을 복제한다 — 그 견본이 있는지 본다.
    path = R.template_file("plan")
    m = C.read_members(path)
    sec = C.xmlcompat.parse(m[C.section_names(m)[0]])
    proto = R._find_attach_proto(sec, C.HP)
    assert proto is not None, "standard.hwpx 에 붙임 표제 견본이 없다"
    tbl = next(e for e in proto.iter() if C.xmlcompat.local_name(e) == "tbl")
    assert (tbl.get("rowCnt"), tbl.get("colCnt")) == ("1", "3")


def test_caption_prototype_is_removed_when_unused(tmp_path):
    # 견본은 양식에만 있고 결과 문서에는 남지 않는다
    r = render("plan", {"title": "본문만"}, body=BODY, output_dir=str(tmp_path),
               filename="noproto")
    texts = [C.para_text(p).strip() for p in _paras(r["path"])]
    assert not any("붙임 제목" in t for t in texts)


# ── 별지 절 제목은 그 문서 안의 번호다 ────────────────────
def test_attachment_section_numbers_stay_literal(tmp_path):
    # 본문 헤딩은 자동 번호다. 별지에 그대로 쓰면 번호가 5·6 으로 이어져
    # 별지 안의 '1.' 이 사라진다 — 별지 절 제목은 자동 번호를 끄고 글자로 둔다.
    atts = [{"title": "서식",
             "body": "\n".join(["1. 작성요령", "□ 항목별로 채운다",
                                "2. 제출", "□ 기한 엄수"])}]
    r = render("plan", {"title": "헤딩"}, body=BODY, attachments=atts,
               output_dir=str(tmp_path), filename="head")
    assert r["warnings"] == []
    texts = [C.para_text(p).strip() for p in _paras(r["path"])]
    assert "1. 작성요령" in texts and "2. 제출" in texts
    # 본문 헤딩은 자동 번호 그대로 — 번호가 글자로 남지 않는다
    assert "추진배경" in texts and "1. 추진배경" not in texts


def test_thin_attachment_is_reported(tmp_path):
    # 붙임도 한 쪽을 채운다. 예외를 뒀더니 견본부터 아래를 3분의 2 비웠다(08-18).
    thin = [{"title": "얇은 붙임", "body": "□ 한 줄뿐"}]
    r = render("plan", {"title": "얇음"}, body=BODY, attachments=thin,
               output_dir=str(tmp_path), filename="thin")
    warns = r["body_result"]["warnings"]
    assert any("한 쪽을 못 채운다" in w for w in warns), warns


def test_full_attachment_is_quiet(tmp_path):
    # 최대 추정치로 보므로 거짓 경고가 없다 — 채울 만한 분량이면 조용하다
    full = [{"title": "채운 붙임",
             "body": "\n".join(["□ 편성 원칙", "◦ " + "가" * 60,
                                "□ 시간 배분", "◦ " + "나" * 60]),
             "tables": [{"headers": ["구분", "내용"],
                         "rows": [["", ""] for _ in range(18)]}]}]
    r = render("plan", {"title": "채움"}, body=BODY, attachments=full,
               output_dir=str(tmp_path), filename="full")
    assert not any("한 쪽을 못 채운다" in w for w in r["body_result"]["warnings"])


def test_table_markers_are_scoped_to_each_attachment(tmp_path):
    # 붙임 안의 '[표1]' 은 그 붙임의 첫 표다 — 전체 표 번호를 셀 이유가 없다
    atts = [
        {"title": "가", "body": "\n".join(["□ 앞", "[표1]"]),
         "tables": [{"headers": ["A"], "rows": [["1"]]}]},
        {"title": "나", "body": "\n".join(["□ 뒤", "[표1]"]),
         "tables": [{"headers": ["B"], "rows": [["2"]]}]},
    ]
    r = render("plan", {"title": "표마커"}, body=BODY, attachments=atts,
               output_dir=str(tmp_path), filename="mark")
    assert not any("마커 중복" in w for w in r["body_result"]["warnings"])
    assert r["body_result"]["tables_added"] == 2


def test_outline_check_ignores_attachments(tmp_path):
    # 골격 검사는 본문에만 건다 — 별지는 4단/3단 대상이 아니다
    atts = [{"title": "서식", "body": "□ 개요\n◦ 세부내용\n□ 검토의견"}]
    r = render("plan", {"title": "골격"}, body=BODY, attachments=atts,
               output_dir=str(tmp_path), filename="outline")
    assert r["warnings"] == []
