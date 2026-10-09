# -*- coding: utf-8 -*-
"""고정 골격 — 규칙이 흩어져 어긋나는 것을 막는 정합성 테스트.

골격은 outline.py(코드) · SKILL.md(스킬) · guidelines/*.md(지침) · prompt.py(writer)
네 곳에 있다. 한 곳만 고치면 나머지가 반대로 가르치고, 그러면 모델은 더 자주
읽는 쪽을 따른다 — 어느 쪽이 정답인지는 사람도 못 맞힌다.
"""
import os

import hwpx_core as C
from hwpx_core import outline as O
from hwpx_skeleton import TEMPLATE_SPECS, guides, render
from hwpx_skeleton import renderer as R
from hwpx_mcp.prompt import SYSTEM_PROMPT

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SKILL_MD = os.path.join(_REPO, "skill", "hwpx", "SKILL.md")

BODY_OK = "\n".join([
    "1. 추진배경", "□ 배경 한 줄",
    "2. 주요내용", "◦ 내용 한 줄",
    "3. {s3}", "□ 방안 한 줄",
    "4. 향후계획", "□ 추진 일정",
    "◦ ’26.  9.\t: 착수", "◦ ’26. 10.\t: 시행", "◦ ’26. 11.\t: 점검",
])


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

# 260831: 스킬이 둘로 갈렸다 — 엔진(hwpx)과 양식·관행(hwpx-template).
# 규칙이 '어디에' 적혔나가 아니라 '스킬 한 벌 안에 있나'를 본다.
_TPL_MD = os.path.join(_REPO, "skill", "hwpx-template", "SKILL.md")


def _skills():
    """엔진 + 양식 스킬을 이어 붙인 것 — 둘은 함께 올라간다."""
    return _read(_SKILL_MD) + "\n" + _read(_TPL_MD)



# ── 유형은 셋, 양식은 한 벌 ────────────────────────────────
def test_types():
    """공문서 유형 셋 + 기본(plain). plain 은 골격을 강제하지 않는다(260831)."""
    assert set(TEMPLATE_SPECS) == {"plain", "plan", "result", "review"} == set(O.TYPES)
    assert O.outline_for("plain") == ()          # 골격 없음
    assert O.check_outline(["아무 제목", "둘째"], "plain") == []


def test_official_types_share_one_template_file():
    """공문서 셋은 양식 한 벌을 쓴다 — 서식은 같고 골격만 다르다.

    plain 은 따로다: 【주관】·취지 상자가 없는 별도 파일이라 서식 자체가 다르다.
    """
    official = {k: v for k, v in TEMPLATE_SPECS.items() if k != "plain"}
    assert {spec["file"] for spec in official.values()} == {R.STANDARD_TEMPLATE}
    assert os.path.exists(R.template_file("plan"))
    assert R.template_file("plan") == R.template_file("result") == R.template_file("review")
    assert R.template_file("plain") != R.template_file("plan")
    assert os.path.exists(R.template_file("plain"))


def _body_for(key):
    """그 유형의 고정 골격을 그대로 채운 최소 본문."""
    want = O.outline_for(key)
    if len(want) == 3:            # 검토보고 — 일정 블록이 없다
        return "\n".join([f"1. {want[0]}", "□ 무엇을 설명하는지",
                          f"2. {want[1]}", "◦ 사실 위주 설명",
                          f"3. {want[2]}", "□ 담당자 판단"])
    return BODY_OK.format(s3=want[2])


def test_legacy_keys_still_render(tmp_path):
    # 스킬 이전 판·저장된 프롬프트가 옛 이름으로 부른다 — 깨뜨리지 않는다
    # ('basic' 은 rev 7 중간판에서 잠깐 냈던 이름 → review 로 받는다)
    for legacy, want in O.ALIASES.items():
        r = render(legacy, {"title": "별칭"}, output_dir=str(tmp_path),
                   filename=legacy, body=_body_for(legacy))
        assert r["status"] == "success", (legacy, r.get("message"))
        assert r["template"] == want
        assert r["warnings"] == [], (legacy, r["warnings"])


def test_format_spec_document_exists():
    # 서식 설명은 렌더되지 않는 양식이 아니라 문서로 둔다
    assert os.path.exists(os.path.join(_REPO, "skill", "hwpx", "references",
                                       "format_spec.md"))


def test_review_report_has_its_own_outline(tmp_path):
    body = "\n".join(["1. 개요", "□ 무엇을 설명하는지",
                      "2. 세부내용", "◦ 사실 위주 설명",
                      "3. 검토의견", "□ 담당자 판단"])
    r = render("review", {"title": "검토보고"}, output_dir=str(tmp_path), body=body)
    assert r["status"] == "success" and r["warnings"] == []
    # 260928 — 검토보고는 목차를 검사하지 않는다(단 이름은 샘플)
    r2 = render("review", {"title": "다른 단"}, output_dir=str(tmp_path), filename="x",
                body="1. 사안\n□ 경위 설명\n2. 판단\n□ 담당자 판단")
    assert not any("[골격]" in w for w in r2["warnings"])


# ── 골격 검사가 실제로 문다 ────────────────────────────────
def test_render_warns_on_broken_outline(tmp_path):
    # 260928 — 이름은 자유, 마지막 단만 향후계획. 옛 교육계획 목차(행정사항으로 끝남)가 걸린다
    body = ("1. 추진배경\n□ 배경\n2. 교육개요\n◦ 개요\n"
            "3. 세부 추진계획\n□ 계획\n4. 행정사항\n◦ 협조")
    r = render("plan", {"title": "옛 목차"}, output_dir=str(tmp_path), body=body)
    assert r["status"] == "success"          # 막지 않는다
    골격 = [w for w in r["warnings"] if w.startswith("[골격]")]
    assert len(골격) == 1 and "마지막 단이 '행정사항'" in 골격[0]
    assert r["outline"]["found"] == ["추진배경", "교육개요", "세부추진계획", "행정사항"]


def test_render_is_quiet_when_outline_matches(tmp_path):
    for key in ("plan", "result"):
        r = render(key, {"title": "고정 골격"}, output_dir=str(tmp_path), filename=key,
                   body=BODY_OK.format(s3=O.outline_for(key)[2]))
        assert r["warnings"] == [] and r["outline"] is None


def test_result_type_swaps_only_the_third_slot():
    plan, result = O.outline_for("plan"), O.outline_for("result")
    assert plan[0] == result[0] and plan[1] == result[1] and plan[3] == result[3]
    assert (plan[2], result[2]) == ("추진방안", "추진결과")


def test_free_section_names_are_accepted():
    # 260928 — 부제·다른 이름을 막지 않는다(V4 · 큰 모델에 자유도). 마지막 단만 본다
    assert C.check_outline(["1. 추진배경(회의목적)", "2. 현황", "3. 주요내용",
                            "4. 추진방안", "5. 향후계획"], "plan") == []


def test_headless_body_is_not_judged():
    assert C.check_outline([], "plan") == []


# ── 네 곳이 같은 값을 가르친다 ─────────────────────────────
def test_skill_md_teaches_the_fixed_outline():
    skill = _skills()
    for name in ("추진배경", "주요내용", "추진방안", "향후계획", "추진결과"):
        assert name in skill, name
    # 260928 — 이름은 샘플, 마지막 단만 규칙이다
    assert "샘플 골격" in skill and "마지막 단은 `향후계획`" in skill
    assert "고정 4단" not in skill
    # 옛 유형별 목차 나열이 남아 있으면 모델이 그쪽을 따른다
    assert "보고서 유형별 기본 목차" not in skill
    assert "회의개요(일시·장소·참석자)" not in skill


def test_guidelines_teach_the_fixed_outline():
    stems = {f[:-3] for f in os.listdir(guides.GUIDELINES_DIR) if f.endswith(".md")}
    assert stems == {"plan", "result", "review"}
    for key in stems:
        text = guides.get_writing_guide(key)
        want = O.outline_for(key)
        assert f"샘플 {len(want)}단" in text, key
        for i, name in enumerate(want, 1):
            assert f"{i}. {name}" in text, (key, name)


def test_writer_prompt_teaches_the_fixed_outline():
    for name in O.outline_for("plan"):
        assert name in SYSTEM_PROMPT, name
    assert "추진결과" in SYSTEM_PROMPT
    # 옛 '섹션 후보' 나열(자유롭게 제안)이 남아 있으면 고정이 무너진다
    assert "적합한 섹션을 자유롭게 제안" not in SYSTEM_PROMPT
    assert "현황 및 문제점, 추진방향 및 계획" not in SYSTEM_PROMPT


# ── 4번은 일정만 ───────────────────────────────────────────
def test_render_warns_when_future_plan_holds_other_blocks(tmp_path):
    body = "\n".join([BODY_OK.format(s3="추진방안"),
                      "□ (평가) 만족도 조사 시행",
                      "◦ 결과는 차년도 과정에 반영"])
    r = render("plan", {"title": "일정 외 블록"}, output_dir=str(tmp_path), body=body)
    assert r["status"] == "success"
    assert sum("앞 단으로 옮길 것" in w for w in r["warnings"]) == 2


def test_render_warns_when_schedule_exceeds_five(tmp_path):
    # 260928 — 개수 규칙(2쪽 3개·3쪽 4개)은 뗐다. 다섯 줄 상한만 남았다
    extra = ["◦ ’26. 12.\t: 확대", "◦ ’27.  1.\t: 정착", "◦ ’27.  2.\t: 평가"]
    body = "\n".join([BODY_OK.format(s3="추진방안")] + extra)
    r = render("plan", {"title": "일정 6개"}, output_dir=str(tmp_path), body=body)
    assert any("일정 줄이 6개다" in w for w in r["warnings"])
    fewer = "\n".join(BODY_OK.format(s3="추진방안").splitlines()[:-1])   # 두 줄도 된다
    r2 = render("plan", {"title": "일정 2개"}, output_dir=str(tmp_path), filename="y", body=fewer)
    assert not any("[골격]" in w for w in r2["warnings"])


def test_review_report_rule_is_taught_everywhere():
    skill = _skills()
    for name in O.outline_for("review"):
        assert name in skill, name
        assert name in SYSTEM_PROMPT, name
    assert "세부내용" in guides.get_writing_guide("review")
    # 유형을 고르는 규칙이 스킬과 프롬프트에 함께 있어야 한다
    assert "무엇을 할 것인가" in skill and "이 사안을 어떻게 볼 것인가" in skill
    assert "무엇을 할 것인가" in SYSTEM_PROMPT


def test_schedule_rule_is_taught_everywhere():
    skill = _skills()
    # 260928 — 스킬은 V4 일정 줄(날짜가 앞 · 다섯 줄 상한). 261011 — writer·지침 md 도 같은 규칙
    assert "날짜가 앞에 오는 일정 줄" in skill and "다섯 줄이 상한" in skill
    assert "2쪽까지 3개" not in skill
    assert "□ 추진 일정" in SYSTEM_PROMPT and "다섯 줄이 상한" in SYSTEM_PROMPT
    assert "2쪽까지 3개" not in SYSTEM_PROMPT
    for key in ("plan", "result"):
        text = guides.get_writing_guide(key)
        assert "추진 일정" in text and "다섯 줄이 상한" in text, key
        assert "2쪽까지 3개" not in text, key


def test_skill_md_lists_every_check():
    """렌더가 무는 검사는 SKILL.md 의 목록에 이름이 올라 있어야 한다.

    검사를 늘리고 문서에 안 적으면, 모델은 경고를 보고도 무슨 규칙인지 모른다.
    """
    skill = _skills()
    for mod in ("outline.py", "endings.py", "linebreak.py", "volume.py"):
        assert mod in skill, mod
    for tag in ("[골격]", "[종결]", "[분량]"):
        assert tag in skill, tag
