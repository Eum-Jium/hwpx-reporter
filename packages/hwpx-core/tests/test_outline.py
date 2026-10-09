# -*- coding: utf-8 -*-
"""골격 단일 기준(hwpx_core.outline) 자체 검사 — 260928 부터 이름은 샘플, 마지막 단만 검사."""
import hwpx_core as C
from hwpx_core import outline as O


def test_three_types_and_their_outlines():
    # 260831: 기본 유형 plain 이 앞에 섰다 — 공문서 골격이 어울리지 않는 문서용.
    assert O.TYPES == ("plain", "plan", "result", "review")
    assert O.outline_for("plain") == ()                 # 골격을 강제하지 않는다
    assert O.check_outline(["시간표", "주간 목표"], "plain") == []
    assert O.outline_for("plan") == ("추진배경", "주요내용", "추진방안", "향후계획")
    assert O.outline_for("result") == ("추진배경", "주요내용", "추진결과", "향후계획")
    # 검토보고는 기승전결을 세우지 않는다 — 3단
    assert O.outline_for("review") == ("개요", "세부내용", "검토의견")
    # rev 7 중간판의 basic 은 별칭으로 받는다
    assert O.resolve("basic") == "review"


def test_only_report_types_have_a_future_plan():
    assert O.HAS_FUTURE_PLAN == frozenset({"plan", "result"})
    assert "review" not in O.HAS_FUTURE_PLAN


def test_legacy_keys_resolve():
    assert O.resolve("training_plan") == "plan"
    assert O.resolve("meeting_result") == "result"
    assert O.resolve("plan") == "plan"
    assert O.resolve("우리부서양식") == "우리부서양식"   # 모르는 키는 그대로
    assert O.outline_for("business_result")[2] == "추진결과"


def test_normalize_strips_numbering():
    for raw in ("1. 추진배경", "Ⅰ. 추진배경", "(1) 추진배경", "1) 추진 배경", " 추진배경 "):
        assert O.normalize_heading(raw) == "추진배경", raw


def test_clean_outline_is_silent():
    assert C.check_outline(["1. 추진배경", "2. 주요내용", "3. 추진방안", "4. 향후계획"],
                           "plan") == []


def test_section_names_are_free_but_last_is_future_plan():
    # 260928 — 이름 고정 검사를 뗐다(V4). 단 수·이름은 자유, 마지막 단만 향후계획.
    five = ["1. 추진배경", "2. 현황", "3. 주요내용", "4. 추진방안", "5. 향후계획"]
    assert C.check_outline(five, "plan") == []
    assert C.check_outline(["1. 개요", "2. 운영결과", "3. 향후계획"], "result") == []
    warns = C.check_outline(["1. 추진배경", "2. 주요내용"], "plan")
    assert len(warns) == 1 and "마지막 단이 '주요내용'" in warns[0]


def test_review_outline_is_not_checked():
    assert C.check_outline(["1. 개요", "2. 경위", "3. 검토의견"], "review") == []
    assert C.check_outline(["1. 사안", "2. 판단"], "review") == []


def test_unknown_template_accepts_either_third_name():
    # 밖에서 가져온 양식은 유형을 모른다 — 계획·결과 어느 쪽 이름이든 받는다
    for third in ("추진방안", "추진결과"):
        body = ["1. 추진배경", "2. 주요내용", f"3. {third}", "4. 향후계획"]
        assert C.check_outline(body, None) == []
        assert C.check_outline(body, "우리부서양식") == []


def test_stdlib_only():
    # 모드 B 가 이 파일을 통째로 적재한다 — 서드파티를 물면 그 경로가 죽는다
    import ast
    import os
    src = os.path.join(os.path.dirname(O.__file__), "outline.py")
    with open(src, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"re"}, mods


# ── 마지막 단 향후계획 — 일정 줄만, 다섯 줄 상한 ────────────
SCHED = ["□ 추진 일정",
         "◦ ’26.  9.	: 착수",
         "◦ ’26. 10.	: 시행",
         "◦ ’26. 11.	: 점검"]
# V4 꼴 — 마크다운 `- '26. 8월  내용` 이 □ 일정 줄로 온다
SCHED_V4 = ["□ '26. 8월	대상 정수장 확정",
            "□ '26. 9월	시범 운영",
            "□ '26. 10월	결과 보고"]


def test_schedule_only_block_is_clean():
    assert C.check_future_plan(SCHED) == []
    assert C.check_future_plan(SCHED_V4) == []


def test_non_schedule_line_is_pushed_forward():
    warns = C.check_future_plan(SCHED_V4 + ["◦ 이수자 명부는 인사기록과 연계해 활용"])
    assert any("앞 단으로 옮길 것" in w for w in warns)
    warns = C.check_future_plan(SCHED + ["□ (평가) 만족도 조사 시행"])
    assert any("일정이 아닌 줄" in w for w in warns)


def test_schedule_lines_capped_at_five():
    five = SCHED_V4 + ["□ '26. 11월	확대", "□ '26. 12월	정착"]
    assert C.check_future_plan(five) == []
    warns = C.check_future_plan(five + ["□ '27. 1월	평가"])
    assert any("일정 줄이 6개다" in w for w in warns)
