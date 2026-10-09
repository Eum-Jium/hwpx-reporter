# -*- coding: utf-8 -*-
"""민원 대기시간 단축 추진계획 — 규칙 전부 적용해 작성·검증.

규칙: 체언 종결 / 종결어 중복 금지 / 을·를 생략 / □→◦ 두 단계 /
      두 줄은 첫 줄이 어절 경계에서 끊기게 / 일정은 날짜 줄 + 탭 / 수치는 표
"""

import collections
import os
import sys

# 검증 도구는 옆 폴더(tools/verify)에 있다
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verify"))
from linebreak import break_points  # noqa: E402

from hwpx_report_policy.length import check_line_lengths  # noqa: E402

TABLES = [
    {"headers": ["구분", "현재", "목표('27년)"],
     "rows": [["평균 대기시간", "24분", "10분 이내"],
              ["집중 시간대", "10～12시 42%", "30% 이하"],
              ["사전예약률", "7%", "40%"],
              ["무인 발급률", "12%", "35%"],
              ["상담 전담 창구", "없음", "2곳"],
              ["창구 처리 편차", "2배", "1.3배 이내"],
              ["예약 취소율", "-", "10% 이하"],
              ["안내 표시", "창구 앞", "입구·대기 화면"],
              ["처리 지연 민원", "월 12건", "월 3건 이하"]]},
]

BODY = """1. 추진배경
□ (실태) 민원 대기시간이 인근 기관 평균 대비 크게 길어진 상황
◦ 최근 3년간 민원 건수 연평균 8% 늘었으나 창구 수·인력 배치 방식 그대로 유지되어 오전 집중 시간대 대기 적체 심화
□ (근거) 민원처리법상 신속 처리 의무와 서비스헌장 이행
◦ 서비스헌장 대기 15분 기준 최근 반기 동안 계속 넘어선 상태로 별도 개선 조치 없이는 올해 헌장 이행 실적 미달 우려

2. 주요내용
□ (현황) 접수 창구 4곳 모두 오전 시간대에 이용 집중
[표1]
◦ 오전 10시부터 12시 사이 하루 접수 물량 42% 몰려 같은 시간 특정 창구 앞에만 대기 줄이 길어지는 구조적 편중 발생
◦ 창구별 하루 처리 건수 편차 뚜렷하지만 창구 인력 배치 기준은 접수 시간대와 관계없이 동일한 기준 그대로 유지되는 상태
□ (원인) 사전예약* 안내 부족과 단순 민원의 창구 유입
◦ 인터넷으로 처리 가능한 증명 발급 등 단순 민원들까지 창구로 들어와 정작 대면 상담이 필요한 민원 처리 순서 밀리는 실정
* 사전예약: 방문 전 온라인으로 시간대·담당 창구 지정하는 제도

3. 추진방안
□ (분산) 시간대별 예약제 도입 및 무인 발급기 안내 강화
◦ 예약 가능한 시간대 30분 단위로 열어 방문 시각 나눈 뒤 무인 발급 가능 항목은 청사 입구와 대기 화면에서 우선 안내
□ (배치) 집중 시간대 창구 증설 및 상담 전담 창구 분리
◦ 오전 집중 시간대에 한해 임시 창구 2곳 늘려 운영하고 상담이 필요한 민원은 전담 창구로 따로 돌려 처리 흐름 명확히 구분
□ (자원) 별도 증원 없이 기존 인력 교대 조정으로 운영
◦ 집중 시간대 추가 창구는 기존 직원 근무 교대 조정으로 메우고 무인 발급기 또한 현 보유 장비 추가 구입 없이 그대로 활용
□ (효과) 대기시간 10분 이내 진입 및 창구 혼잡 완화 기대
◦ 단순 발급 물량 상당수가 무인 창구로 옮겨가면 상담 대기 시간 줄어들고 오전 집중도 함께 낮아지면서 이용자 편의 개선 전망

4. 향후계획
□ 추진 일정
◦ ’26. 10.	: 예약 시스템 개편 착수
◦ ’26. 12.	: 시범 운영 및 이용자 의견 수렴
◦ ’27.  3.	: 전 창구 확대 시행"""


def check():
    print("분량 규격 위반:", len(check_line_lengths(BODY)))
    for i in check_line_lengths(BODY):
        print("   -", i)
    bad_end = [s.strip() for s in BODY.splitlines()
               if s.strip()[-1:] in ("함", "됨", "임", "둠")]
    print("용언 어미 종결:", bad_end or "없음")
    ends = [s.strip().split()[-1] for s in BODY.splitlines()
            if s.strip() and s.strip()[0] in "□◦" and "\t" not in s]
    dup = {w: n for w, n in collections.Counter(ends).items() if n > 1}
    print("종결어 중복:", dup or "없음")
    print("을/를 잔존:", [s.strip()[:26] for s in BODY.splitlines()
                        if s.strip()[:1] in "□◦" and ("을 " in s or "를 " in s)] or "없음")
    risky = []
    for raw in BODY.splitlines():
        s = raw.strip()
        if not s or s[0] not in "□◦" or "\t" in s:
            continue
        parts = break_points(s)
        if len(parts) > 1 and not all(k for _, k in parts[:-1]):
            risky.append(s[:34])
    print("낱말 중간 끊김(예측):", risky or "없음")


if __name__ == "__main__":
    check()
    if "--render" in sys.argv:
        import hwpx_skeleton as HS
        from outdir import out_dir
        r = HS.render("plan", {"title": "민원 대기시간 단축 추진계획"},
                      output_dir=out_dir(), body=BODY, tables=TABLES)
        print("\n렌더:", r["status"], r["path"])
        print("본문:", r["body_result"])
