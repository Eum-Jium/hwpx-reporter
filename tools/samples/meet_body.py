# -*- coding: utf-8 -*-
"""표준서식 개선 실무협의회 개최 계획 (meeting_plan) — 규칙 전부 적용해 작성·검증.

목차: 1.추진배경 2.주요내용 3.추진방안 4.향후계획(샘플 4단).
회의개요·안건·회의순서는 2·3단에 담는다.
검사 8종은 train_body 와 동일 — 렌더 전에 전건 통과시킨다.
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
    {"headers": ["구분", "시간", "주요 내용"],
     "rows": [["개회", "14:00～14:10", "개최 취지 설명"],
              ["보고", "14:10～14:40", "부서 요구 목록 검토 결과"],
              ["토의·정리", "14:40～16:00", "유형 추가·순서 확정"]]},
]

BODY = """1. 추진배경
□ (목적) 교육 이후 접수된 서식 개선 요구 처리 방향 정립
◦ 교육 이후 부서별로 나온 서식 요구와 개선 의견 상당수 쌓인 만큼 전부 반영하면 유지보수 부담 커져 수용 범위 조정 필요

2. 주요내용
□ (개요) 문서 담당 부서 과장 등 12명 참석 실무협의회 개최
◦ 일시·장소 : ’26. 12. 3(목) 14:00～16:00, 본관 3층 소회의실
□ (안건) 신규 서식 유형 추가 여부와 정비 우선순위 결정
◦ 부서별 요구 목록 함께 검토해 추가할 유형 추리되 별도 예산 없이 현 담당 인력으로 소화 가능한 범위에서 정비 순서 확정

3. 추진방안
□ (진행) 안건별 시간 배분해 결정 사항 회의 중 마무리
[표1]

4. 향후계획
□ 추진 일정
◦ ’26. 11.	: 부서별 요구 목록 취합
◦ ’26. 12.	: 실무협의회 개최
◦ ’27.  1.	: 정비 계획 수립"""


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
        print(f"{len(s):3d}자 {len(rs)}줄 {rs[-1][1]:5.1f}% | {s[:30]}")


if __name__ == "__main__":
    good = check()
    if "--dump" in sys.argv:
        print()
        dump()
    if "--render" in sys.argv and good:
        import hwpx_skeleton as HS
        from outdir import out_dir
        r = HS.render("plan",
                      {"title": "표준서식 개선 실무협의회 개최 계획"},
                      output_dir=out_dir(), body=BODY, tables=TABLES)
        print("\n렌더:", r["status"], os.path.abspath(r["path"]))
        print("본문:", r["body_result"])
