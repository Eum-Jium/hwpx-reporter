# -*- coding: utf-8 -*-
"""표준서식 자동화 2단계 고도화 추진계획 (planning) — 3쪽·이미지 포함 테스트.

목차: 1.추진배경 2.주요내용 3.추진방안 4.향후계획(샘플 4단) — 추진경과·현황은
2단에, 기대효과·소요 자원은 3단에 담고 향후계획은 마지막.
표 2개 + 이미지자리 2개 조합으로 3쪽을 채운다.
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
    {"headers": ["구분", "시기", "주요 내용"],
     "rows": [["1단계", "’26. 8.", "자동 생성 체계 구축·배포"],
              ["2단계", "’26. 10～11.", "부서 담당자 실무 교육"],
              ["3단계", "’26. 12.", "협의회 개최·순위 확정"],
              ["4단계", "’27. 1～6.", "유형 확대·설정 전환"]]},
    {"headers": ["구분", "현재", "목표(’27년)"],
     "rows": [["지원 유형", "9종", "15종"],
              ["반영 기간", "3주", "1주 이내"],
              ["검사 항목", "5개", "12개"],
              ["수작업 편집", "6종", "없음"],
              ["규칙 반영", "개발 필요", "담당자 직접"],
              ["표본 점검", "미실시", "배포 전 상시"]]},
]

IMAGES = [{"captions": ["고도화 체계 구성도"]},
          {"captions": ["단계별 적용 절차도"]}]

BODY = """1. 추진배경
□ (배경) 1단계 자동 생성 체계 안착에 따른 확장 요구 증가
◦ 서식 9종 자동 생성 체계 정착하고 교육까지 마친 뒤 부서마다 새 유형 추가와 기능 개선 요구 잇따라 다음 단계 준비 필요
□ (근거) 실무협의회에서 정한 우선순위와 후속 조치 방향
◦ 실무협의회에서 추가할 유형과 정비 순서 이미 정해 두었으므로 그 결과 실제 개발 계획으로 옮기는 작업 이번 계획에서 구체화

2. 주요내용
□ (경과) 도입·교육·협의회 순으로 3단계 거쳐 기반 확보
[표1]
◦ 도구 배포와 실무 교육 차례로 거치며 사용 부서 꾸준히 늘어나 현재는 전 부서가 표준서식 자동 생성 기능 일상적으로 이용
□ (현황) 지원 유형 9종에 머물러 신규 수요 대응 곤란
◦ 회의록·행사계획 등 자주 쓰는 유형 아직 빠져 있어 해당 문서 작성은 지금도 예전처럼 일일이 수작업 편집에 그대로 의존
□ (문제) 서식 규칙 변경 시 반영까지 걸리는 기간 장기화
◦ 규칙 하나 고치려면 코드 수정과 검증 절차 나란히 거쳐야 해 부서 요청부터 실제 반영까지 평균 3주 넘게 걸리고 있는 상황

3. 추진방안
□ (확장) 지원 유형 9종에서 15종으로 단계적 확대
◦ 협의회에서 정한 우선순위 따라 회의록과 행사계획 유형 먼저 추가한 뒤 나머지 여섯 종은 내년 상반기 안에 차례대로 반영
□ (구조) 서식 규칙 코드 분리 및 설정 파일 방식 전환
◦ 규칙 코드에서 떼어 설정 파일로 옮기면 담당자가 직접 고칠 수 있어 반영 기간 대폭 줄어드는 구조로 단계적 전환 추진 예정
[이미지1]
□ (검증) 자동 검사 확대 및 배포 전 점검 절차 강화
◦ 생성 문서 규격 자동 검사 항목 늘리고 배포 전 표본 점검 더해 서식 오류 사전에 걸러내는 이중 점검 체계 새로 갖춰 마련
□ (효과) 지원 범위 확대 및 반영 기간 3주에서 1주로 단축
[표2]
◦ 유형 확대로 수작업 편집 남아 있던 문서까지 자동화 범위 안에 들어와 부서 전체 문서 작성 부담 한층 크게 줄어드는 효과
□ (자원) 별도 증원 없이 기존 인력과 예산 범위에서 추진
◦ 개발은 현 담당 인력이 분기별 과제로 나누어 맡고 설정 파일 전환 작업 또한 기존 전산 자원 범위에서 큰 무리 없이 소화
□ (역할) 개발·검증·안내 역할 나누어 담당자별 분담
◦ 코드 수정은 개발 담당이 맡고 생성 문서 검증과 부서 안내는 서식 담당이 나누어 맡는 방식으로 작업 중복과 누락 함께 방지
[이미지2]
* 설정 파일: 서식 규칙을 코드에서 분리해 담당자가 직접 고치는 방식

4. 향후계획
□ 추진 일정
◦ ’26. 12.	: 설정 파일 구조 설계
◦ ’27.  1.	: 회의록·행사계획 유형 추가
◦ ’27.  3.	: 자동 검사 확대 적용
◦ ’27.  6.	: 나머지 유형 반영 완료"""


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

    tilde = [s.strip()[:30] for s in BODY.splitlines() if "~" in s]
    tilde += [c for t in TABLES for r in t["rows"] for c in r if "~" in c]
    print("ASCII 물결(~) 잔존:", tilde or "없음")

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
                       or long_head or tilde)


if __name__ == "__main__":
    good = check()
    if "--render" in sys.argv and good:
        import hwpx_skeleton as HS
        from outdir import out_dir
        r = HS.render("plan",
                      {"title": "표준서식 자동화 2단계 고도화 추진계획"},
                      output_dir=out_dir(), body=BODY,
                      tables=TABLES, images=IMAGES)
        print("\n렌더:", r["status"], os.path.abspath(r["path"]))
        print("본문:", r["body_result"])
