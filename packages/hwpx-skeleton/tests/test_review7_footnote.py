# -*- coding: utf-8 -*-
"""각주 별표 위첨자 규칙 — 낱말에 붙은 '*' 만 위첨자로 올린다."""
import zipfile

from lxml import etree

import hwpx_skeleton as HS
from hwpx_skeleton.renderer import _paren_segments

HH = "http://www.hancom.co.kr/hwpml/2011/head"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def kinds(text):
    return [(t, k) for t, k in _paren_segments(text)]


# ── 분리 규칙 ─────────────────────────────────────────────
def test_word_attached_star_becomes_superscript():
    segs = kinds("◦ 렌더링 엔진* 도입으로 서식 자동 적용")
    assert ("*", "sup") in segs
    assert segs[0] == ("◦ 렌더링 엔진", None)


def test_reference_line_marker_not_superscripted():
    # 줄 앞 참고 마커는 앞이 공백이라 각주 별표가 아니다
    line = "    * 렌더링 엔진: 서식 규칙 자동 적용하는 프로그램"
    assert kinds(line) == [(line, None)]


def test_paren_label_star_unchanged():
    # 말머리 라벨 안의 별표는 기존대로 라벨 통째 굵게 (동작 변경 없음)
    segs = kinds("□ (외부자문*) 전문가 의견 수렴")
    assert ("외부자문*", "bold") in segs
    assert ("*", "sup") not in segs


def test_digit_label_not_superscripted_anymore():
    """괄호 라벨 위첨자 규칙을 뗐다(뜻 있는 괄호까지 지웠다) — 줄이 한 조각 그대로."""
    line = "◦ 1단계(북부) 사업 착수"
    assert kinds(line) == [(line, None)]


# ── 날짜·시각 뒤 괄호는 위첨자가 아니다 (08-15) ───────────
def test_weekday_after_date_not_superscripted():
    """’26. 12. 3(목) 의 요일이 위로 뜨면 안 된다 — 공문서 표준 날짜 표기."""
    line = "◦ 일시 : ’26. 12. 3(목) 14:00～16:00"
    assert kinds(line) == [(line, None)]


def test_label_after_time_not_superscripted():
    line = "◦ 14:00(개회) 취지 설명"
    assert kinds(line) == [(line, None)]


def test_label_after_dotted_date_not_superscripted():
    line = "◦ 제출 기한 ’26. 9. 30.(월) 까지"
    assert kinds(line) == [(line, None)]


def test_digit_unit_label_not_superscripted_anymore():
    """09-22: 숫자 토큰 뒤 라벨도 더는 위첨자가 아니다 — 괄호는 글자 그대로."""
    for text in ("◦ 2차(서울) 회의 개최", "◦ 3층(대회의실) 이용", "◦ 사업비 50억원(안) 확보"):
        assert kinds(text) == [(text, None)], text


def test_star_with_following_paren_note():
    segs = kinds("◦ 표준서식* 9종 지원 (자동 적용)")
    assert ("*", "sup") in segs
    assert ("(자동 적용)", "small") in segs


def test_plain_line_untouched():
    line = "◦ 별표 없는 일반 줄"
    assert kinds(line) == [(line, None)]


# ── 실제 문서에서 위첨자 charPr 가 붙는지 ─────────────────
def test_rendered_star_run_has_supscript(tmp_path):
    r = HS.render("business_result", {"title": "각주 검증"},
                  output_dir=str(tmp_path),
                  body="1. 개요\n□ 렌더링 엔진* 구축 완료\n"
                       "◦ 서식 규칙 자동 적용으로 작성 부담 완화\n"
                       "* 렌더링 엔진: 서식 규칙 자동 적용하는 프로그램")
    assert r["status"] == "success"
    z = zipfile.ZipFile(r["path"])
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    sup_ids = {cp.get("id") for cp in hdr.iter(f"{{{HH}}}charPr")
               if cp.find(f"{{{HH}}}supscript") is not None}
    star_runs = [t.getparent().get("charPrIDRef")
                 for t in sec.iter(f"{{{HP}}}t") if (t.text or "") == "*"]
    assert star_runs, "별표만 담은 run 이 없다"
    assert any(cid in sup_ids for cid in star_runs), (star_runs, sup_ids)
