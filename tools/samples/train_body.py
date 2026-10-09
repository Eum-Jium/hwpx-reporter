# -*- coding: utf-8 -*-
"""표준서식 문서 작성 교육 추진계획 (training_plan) — 규칙 전부 적용해 작성·검증.

규칙(엔진 경고·스킬과 같은 값):
  체언 종결 / 종결어 중복 금지 / 을·를 생략 / 계층은 □→◦ 두 단계(- · 금지) /
  □ 30~38자(한 줄), ◦ 66~70자 / 일정·목록형은 길이 규격 없음 /
  두 줄은 첫 줄이 어절 경계에서 끊기게 / 둘째 줄 91% 이상 채움 / 표 첫 열 7자 이내
"""

import collections
import os
import sys

# 검증 도구는 옆 폴더(tools/verify)에 있다
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verify"))
from linebreak import break_points, fill_ratio  # noqa: E402

from hwpx_report_policy.length import check_line_lengths  # noqa: E402

TABLES = [
    # '교육명' 행은 두지 않는다 — 제목이 이미 말하고 있고(동어반복), 그 한 행(19pt)이
    # 3번 섹션을 밀어 리드만 1쪽에 남기고 ◦·표를 2쪽으로 떨어뜨렸다(08-16 실측).
    {"headers": ["구분", "내용"],
     "rows": [["일시", "’26. 10. 15 및 11. 12 각 14:00"],
              ["장소", "본관 3층 대회의실"],
              ["대상", "부서별 문서 담당자 40명"]]},
    {"headers": ["구분", "시간", "주요 내용"],
     "rows": [["1교시", "14:00～15:00", "표준서식 규칙 이해"],
              ["2교시", "15:10～16:10", "작성 도구 사용법"],
              ["3교시", "16:20～17:20", "보고서 실습·질의응답"]]},
]

BODY = """1. 추진배경
□ (필요) 자동 생성 도구 배포에 따른 사용 방법 안내 시급
◦ 서식 규칙 자동 적용하는 작성 도구 이미 배포하였으나 부서별 활용 편차 커 표준 서식 정착까지 실무 교육 병행 절실한 상황
□ (여건) 하반기 신규 담당자 배치와 맞물린 교육 수요 집중
◦ 문서 담당자 상당수 하반기에 새로 배치되는 시기인 데다 사내 강사와 회의실 활용하면 별도 비용 없이 집합 교육 운영 가능

2. 주요내용
□ (개요) 기본 과정 중심 2회 운영 및 담당자 전원 참석
[표1]
◦ 도구 사용법과 서식 규칙 함께 다루어 교육 직후 담당자가 각자 담당 보고서 작성에 배운 내용 곧바로 적용하도록 과정 구성

3. 추진방안
□ (과정) 기본 과정과 실습 과정 나누어 단계적 편성
◦ 오전 기본 과정에서 서식 규칙과 도구 사용법 익히고 오후 실습 과정에서 각자 맡은 보고서 직접 작성하며 활용 능력 숙달
[표2]
□ (역할) 과정별 담당자 지정 및 준비·운영 업무 분담
◦ 기획·운영 : 교육 담당 — 과정 편성, 장소·기자재 준비
◦ 강의·교재 : 도구 개발 직원 — 기본·실습 과정 강의, 교재 제작
□ (교재) 실무 사례 중심으로 구성해 온라인 참고 자료* 병행 제공
◦ 부서에서 실제로 작성한 보고서 익명 처리해 교재에 담고 교육 이후에도 반복 확인하도록 사내 게시판에도 그대로 상시 게시
* 온라인 참고 자료: 사내 게시판에 올리는 사용 안내서와 서식 예시
□ (협조) 부서별 참석자 명단 제출 및 업무 조정 협조
◦ 교육 당일 담당자 자리 비우는 만큼 부서마다 민원 대응 인력 미리 조정하고 참석자 명단 9월 말까지 취합해 제출하도록 요청
□ (자원) 별도 예산 없이 사내 강사와 기존 회의실 활용
◦ 강사는 도구 개발 담당 직원이 직접 맡고 교육 장소 또한 기존 청사 회의실 그대로 활용하여 추가 예산 소요 없이 자체 운영

4. 향후계획
□ 추진 일정
◦ ’26.  9.	: 교육 계획 확정 및 참석자 모집
◦ ’26. 10.	: 1차 교육 운영
◦ ’26. 11.	: 2차 교육 및 만족도 조사"""


def check():
    ok = True
    issues = check_line_lengths(BODY)
    print("분량 규격 위반:", len(issues))
    for i in issues:
        print("   -", i)
        ok = False

    bad_end = [s.strip() for s in BODY.splitlines()
               if s.strip()[-1:] in ("함", "됨", "임", "둠")]
    print("용언 어미 종결:", bad_end or "없음")

    ends = [s.strip().split()[-1] for s in BODY.splitlines()
            if s.strip() and s.strip()[0] in "□◦" and "\t" not in s]
    dup = {w: n for w, n in collections.Counter(ends).items() if n > 1}
    print("종결어 중복:", dup or "없음")

    josa = [s.strip()[:26] for s in BODY.splitlines()
            if s.strip()[:1] in "□◦" and ("을 " in s or "를 " in s)]
    print("을/를 잔존:", josa or "없음")

    banned = [s.strip()[:30] for s in BODY.splitlines()
              if s.strip().startswith(("-", "·"))]
    print("금지 계층(- ·):", banned or "없음")

    long_head = [r[0] for t in TABLES for r in t["rows"] if len(r[0]) > 7]
    print("표 첫 열 7자 초과:", long_head or "없음")

    risky, thin = [], []
    for raw in BODY.splitlines():
        s = raw.strip()
        if not s or s[0] not in "□◦*" or "\t" in s:
            continue
        parts = break_points(s)
        if len(parts) > 1 and not all(k for _, k in parts[:-1]):
            risky.append(s[:34])
        ratios = fill_ratio(s)
        if len(ratios) > 1 and ratios[-1][1] < 91:
            thin.append(f"{ratios[-1][1]}% {s[:28]}")
    print("낱말 중간 끊김:", risky or "없음")
    print("둘째 줄 91% 미만:", thin or "없음")
    return ok and not (bad_end or dup or josa or banned or risky or thin or long_head)


def dump():
    for raw in BODY.splitlines():
        s = raw.strip()
        if not s or s[0] not in "□◦*" or "\t" in s:
            continue
        rs = fill_ratio(s)
        tail = f"{rs[-1][1]:5.1f}%" if rs else "  -  "
        print(f"{len(s):3d}자 {len(rs)}줄 {tail} | {s[:30]}")


if __name__ == "__main__":
    good = check()
    if "--dump" in sys.argv:
        print()
        dump()
    if "--render" in sys.argv and good:
        import hwpx_skeleton as HS
        from outdir import out_dir
        r = HS.render("plan",
                      {"title": "표준서식 문서 작성 교육 추진계획"},
                      output_dir=out_dir(), body=BODY, tables=TABLES)
        print("\n렌더:", r["status"], os.path.abspath(r["path"]))
        print("본문:", r["body_result"])
