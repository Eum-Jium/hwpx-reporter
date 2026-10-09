# -*- coding: utf-8 -*-
"""표준서식 문서 작성 교육 결과보고 (training_result) — 규칙 전부 적용해 작성·검증.

목차: 1.추진배경 2.주요내용 3.추진결과 4.향후계획(결과 샘플 4단).
train_body(교육계획)의 결과보고 — 계획 대비 실적을 표로 대조한다.
**1쪽 목표 + 표 2개** 조합 테스트(종전 1쪽 문서는 표 1개였다).
물결은 전각 ～, 날짜 뒤 요일 (목) 도 그대로 렌더된다.
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
    {"headers": ["구분", "내용"],
     "rows": [["일시", "’26. 10. 15(목)·11. 12(목) 각 14:00～17:20"],
              ["대상", "부서별 문서 담당자 40명"]]},
    {"headers": ["구분", "계획", "실적"],
     "rows": [["참석 인원", "40명", "37명(93%)"],
              ["만족도", "4.0 이상", "4.3"]]},
]

BODY = """1. 추진배경
□ (배경) 자동 생성 도구 배포 이후 부서별 활용 편차 해소
◦ 도구 배포만으로 표준 서식 정착 어렵다는 판단에 따라 부서별 문서 담당자 대상 실무 교육 두 차례 나누어 집중 실시 완료

2. 주요내용
□ (개요) 기본·실습 2개 과정 2회 운영 및 담당자 37명 이수
[표1]

3. 추진결과
□ (성과) 참석률 93% 기록 및 만족도 4.3점 확보
[표2]
◦ 실습 과정에서 각자 맡은 보고서 직접 작성해 보도록 하여 교육 직후 서식 문의 건수 절반 수준까지 줄어드는 효과 함께 확인

4. 향후계획
□ 추진 일정
◦ ’26. 12.	: 교재·질의응답 게시판 공개
◦ ’27.  1.	: 심화 과정 수요 조사
◦ ’27.  3.	: 심화 과정 개설 여부 결정"""


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

    ascii_tilde = [s.strip()[:30] for s in BODY.splitlines() if "~" in s]
    ascii_tilde += [c for t in TABLES for r in t["rows"] for c in r if "~" in c]
    print("ASCII 물결(~) 잔존:", ascii_tilde or "없음")

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
    return ok and not (bad_end or dup or josa or banned or risky or thin
                       or long_head or ascii_tilde)


if __name__ == "__main__":
    good = check()
    if "--render" in sys.argv and good:
        import hwpx_skeleton as HS
        from outdir import out_dir
        r = HS.render("result",
                      {"title": "표준서식 문서 작성 교육 결과보고"},
                      output_dir=out_dir(), body=BODY, tables=TABLES)
        print("\n렌더:", r["status"], os.path.abspath(r["path"]))
        print("본문:", r["body_result"])
