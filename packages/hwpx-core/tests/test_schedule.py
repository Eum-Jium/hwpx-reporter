# -*- coding: utf-8 -*-
"""일정 줄 날짜 자릿수 맞춤 — 탭 앞 열의 폭을 두 자리에 맞춘다."""
import hwpx_core as C


def test_pads_one_digit_month_to_two_digit_width():
    got = C.pad_tab_date("◦ ’26. 9.\t: 표준 모델 설계")
    assert got == "◦ ’26.  9.\t: 표준 모델 설계"
    # 두 자리 월과 탭 앞 길이가 같아야 같은 탭 스톱에 선다
    two = "◦ ’26. 10.\t: 시범 적용"
    assert len(got.split("\t")[0]) == len(two.split("\t")[0])


def test_pads_day_as_well():
    assert C.pad_tab_date("◦ ’26. 9. 3.\t: 착수") == "◦ ’26.  9.  3.\t: 착수"
    assert C.pad_tab_date("◦ ’26. 9. 3(목)\t: 착수") == "◦ ’26.  9.  3(목)\t: 착수"


def test_idempotent():
    once = C.pad_tab_date("◦ ’26. 9.\t: 착수")
    assert C.pad_tab_date(once) == once


def test_leaves_lines_without_tab_alone():
    # 정렬할 열이 없으면 본문 문장이다 — 건드리지 않는다
    s = "◦ ’26. 9. 준공을 목표로 상반기 중 설계 완료"
    assert C.pad_tab_date(s) == s


def test_leaves_content_after_tab_alone():
    # 뒤 열은 왼쪽 정렬이라 폭을 맞출 이유가 없다
    s = "◦ ’26. 10.\t: 1. 3차 회의 개최"
    assert C.pad_tab_date(s) == s


def test_ignores_non_date_digits():
    assert C.pad_tab_date("◦ 만족도 4.3\t: 목표 4.0 이상") == "◦ 만족도 4.3\t: 목표 4.0 이상"
    assert C.pad_tab_date("") == ""
