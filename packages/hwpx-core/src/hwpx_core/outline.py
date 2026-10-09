# -*- coding: utf-8 -*-
"""문서 골격 — 유형별 섹션 구성의 단일 기준.

★260928 — 아래 이름들은 이제 **샘플(시작점)**이다. 검사는 「계획·결과의 마지막 단 =
향후계획 · 거기엔 일정 줄만(다섯 줄 상한)」 둘만 본다(V4 에이전트와 같은 규칙).
아래 「이름을 고정해 변수를 없앤다」는 V1~V3 의 판단이고, 큰 모델에선 자유도가 이겼다.

보고서(계획·결과)의 큰 틀은 **왜 → 무엇을 → 어떻게 → 언제** 하나다:

    1. 추진배경   왜 하는가
    2. 주요내용   무엇을 하는가 (대상·개요·현황 등 사실관계)
    3. 추진방안   어떻게 하는가   ← 결과보고는 '추진결과'(어떻게 됐나)
    4. 향후계획   언제 무엇을 하는가

유형은 셋이다 — **계획(plan) · 결과(result) · 검토(review)**. 계획과 결과는
위 4단을 함께 쓰고 3번 자리만 갈린다. 소재(교육·행사·회의·사업)는 유형이 아니다
— 지침 md 안의 절이 맡는다.

종전에는 유형마다 목차가 달랐다(교육계획은 교육개요·세부 추진계획·행정사항,
회의계획은 안건·회의순서 …). 사람이 쓰면 그때그때 적당한 이름이 나오지만,
모델이 쓰면 같은 유형에서도 판마다 이름이 흔들려 문서 품질이 모델 교체에
따라 달라진다. 이름을 고정하면 그 변수가 사라진다 — 이 모듈이 그 고정값이다.

검토보고(review)만 골격이 다르다 — **개요 → 세부내용 → 검토의견** 3단이다.
기승전결이 필요 없는 1~2쪽짜리라, 위 4단으로 맞추면 1·3·4번이 빈 껍데기가 된다.
쓰는 자리는 사안을 사실 위주로 설명하고 담당자 판단을 붙이는 보고다.

세 유형은 **보고가 답하는 질문**으로 갈린다 — 이 한 줄이 선택 규칙이다:
    무엇을 할 것인가   → plan     (일정·역할·예산을 정한다)
    무엇을 했는가      → result   (한 일의 실적을 보고한다)
    이 사안을 어떻게 볼 것인가 → review (사실을 설명하고 판단을 붙인다)

부제·괄호 덧말은 넣지 않는다(`추진배경(회의목적)` ✗). 소재별 설명은 헤딩이
아니라 `hwpx_skeleton/assets/guidelines/{plan,result,review}.md` 의 본문이 맡는다.

**stdlib 만 쓴다** — markers.py·gaps.py 와 같은 이유(모드 B 가 파일째 적재한다).
"""
import re

# 1·2·4번 = 계획·결과 공통. 3번은 SECTION3 에서 유형별로 채운다.
SECTION_1 = "추진배경"
SECTION_2 = "주요내용"
SECTION_4 = "향후계획"

SECTION3_PLAN = "추진방안"      # 계획·기획류 — 어떻게 할 것인가
SECTION3_RESULT = "추진결과"    # 결과보고류 — 어떻게 됐나

# 검토보고(review)는 기승전결을 세우지 않는다 — 사안 하나를 설명하고 판단을
# 붙여 끝나는 1~2쪽짜리다. 4단에 맞추면 1·3·4번이 빈 껍데기가 된다.
SECTIONS_REVIEW = ("개요", "세부내용", "검토의견")

# 유형은 셋이다. 소재(교육·행사·회의·사업)는 유형이 아니라 지침 md 안의 절이고,
# 양식은 세 유형이 같은 파일 한 벌을 쓴다(서식은 같고 골격만 다르다).
PLAN = "plan"
RESULT = "result"
REVIEW = "review"
# ★260831 — **골격이 없는 유형.** 공문서 세 유형과 달리 목차를 강제하지 않는다.
# 계획표·안내문·개인 문서처럼 4단이 어울리지 않는 글이 이 엔진으로도 나와야
# 하는데, 그때까지는 어느 키를 골라도 "고정 4단으로 맞출 것" 경고가 따라붙었다.
# 기본으로 쓰는 자리다 — 공문서 관행이 필요할 때만 plan/result/review 를 고른다.
PLAIN = "plain"
TYPES = (PLAIN, PLAN, RESULT, REVIEW)

# 4번 향후계획을 두는 유형 — 검토보고는 일정을 따로 세우지 않는다.
HAS_FUTURE_PLAN = frozenset({PLAN, RESULT})

# 옛 유형 키 → 지금 키(plan·result·review). 스킬 이전 판·저장된 프롬프트가 이 이름으로 부른다.
ALIASES = {
    "planning": PLAN, "sample": PLAN, "training_plan": PLAN,
    "event_plan": PLAN, "meeting_plan": PLAN,
    "business_result": RESULT, "event_result": RESULT,
    "training_result": RESULT, "meeting_result": RESULT,
    # rev 7 중간판에서 잠깐 'basic' 으로 냈던 이름 — 뜻이 안 보여 review 로 고쳤다.
    # (그보다 앞서 'basic' 은 렌더되지 않는 서식 설명 페이지였다. 지금 그 설명은
    #  references/format_spec.md 에 있다.)
    "basic": REVIEW,
}


def resolve(key):
    """옛 유형 키를 지금 키로 옮긴다. 모르는 키는 그대로 돌려준다."""
    return ALIASES.get(key, key)


RESULT_TYPES = frozenset({RESULT} | {k for k, v in ALIASES.items() if v == RESULT})

_NUM = re.compile(r"^\s*(?:\d{1,2}\.|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\.?|\(\d{1,2}\)|\d{1,2}\))\s*")


def outline_for(template_key=None):
    """유형의 고정 골격을 순서대로 반환 — 계획·결과는 4단, 검토보고는 3단.

    template_key 가 None(밖에서 가져온 양식 등)이면 계획류 4단으로 잡는다.
    """
    key = resolve(template_key)
    if key == PLAIN:
        return ()                      # 골격 없음 — 검사도 건너뛴다
    if key == REVIEW:
        return SECTIONS_REVIEW
    third = SECTION3_RESULT if key in RESULT_TYPES else SECTION3_PLAN
    return (SECTION_1, SECTION_2, third, SECTION_4)


# ── 마지막 단 향후계획 — 일정만 둔다 ─────────────────────────
# 다른 유형의 블록(평가·협조·활용 …)이 섞이면 '언제'를 묻는 자리가 흐려진다.
# 그런 내용은 앞 단(어떻게)이 받는다.
# ★260928 — V4 꼴로 바꿨다. 일정 줄은 **날짜가 말머리 노릇을 하는 줄**이다 —
#   마크다운 `- '26. 8월  내용` 이 `□ '26. 8월\t내용` 으로 온다. 그래서 □·◦ 를 가리지
#   않고 **탭 든 줄 = 일정**으로 센다. 종전의 `□ 추진 일정` 리드 한 줄과 개수 규칙
#   (2쪽 3개 · 3쪽 4개)은 뗐고, 상한 다섯만 남겼다(넘으면 묶는다).
#   종전 꼴(`□ 추진 일정` + ◦ 일정 줄)도 그대로 통과한다 — 리드 하나는 받아 준다.
SCHEDULE_LEAD = "추진 일정"
SCHEDULE_MAX = 5


def check_future_plan(lines, pages=None):
    """향후계획 블록이 '일정만' 규칙을 지키는지 본다.

    lines = 향후계획 헤딩 **뒤의 본문 줄들**(마커 포함). 반환은 경고 문자열 목록.
    일정 줄은 탭으로 날짜와 내용을 가르는 줄이다(`□ '26. 8월\\t…` · `◦ ’26.  9.\\t: …`).
    참고행(*)은 각주를 받는 자리라 세지 않는다. `pages` 는 옛 호출부 호환용이다(안 쓴다).
    """
    # plain 은 향후계획 자체가 없는 유형이라 검사하지 않는다(260831).
    warns = []
    leads, sched, other = [], [], []
    for raw in (lines or []):
        s = (raw or "").strip()
        if not s or s[0] not in "□☐◦-·":
            continue
        if "\t" in s:
            sched.append(s)
        elif s[0] in "□☐" and not leads and \
                SCHEDULE_LEAD.replace(" ", "") in s.replace(" ", ""):
            leads.append(s)            # 옛 꼴의 리드 한 줄은 받아 준다
        else:
            other.append(s)

    for s in other:
        warns.append(f"[골격] 향후계획에 일정이 아닌 줄이 있다 — '{s[:24]}…' 는 "
                     f"앞 단으로 옮길 것(향후계획은 날짜로 시작하는 일정 줄만 둔다)")
    if len(sched) > SCHEDULE_MAX:
        warns.append(f"[골격] 일정 줄이 {len(sched)}개다 — {SCHEDULE_MAX}줄이 상한, 넘으면 묶을 것")
    return warns


def normalize_heading(text: str) -> str:
    """헤딩 줄에서 번호·공백을 걷어낸 순수 섹션 이름."""
    if not text:
        return ""
    return _NUM.sub("", str(text)).strip().replace(" ", "")


def check_outline(headings, template_key=None):
    """헤딩 목록이 골격 규칙과 어긋나는 지점을 경고 문자열 목록으로 반환.

    빈 목록 = 이상 없음. 렌더를 막지는 않는다 — 사용자가 준 양식이나 정당한
    예외(붙임 한 장짜리 등)까지 실패로 되돌리면 우회 경로가 생기고, 그러면
    규칙이 아니라 우회가 표준이 된다. 대신 결과에 사실을 남겨 호출자(모델)가
    매번 보게 한다.

    ★260928 — **이름 고정 검사를 뗐다**(V4 와 맞춤 — 목차는 가변).
      `outline_for` 의 단 이름은 이제 **샘플**(시작점)이다. 단 수·이름은 소재에 맞춰 바꾸고,
      채울 말이 없는 단은 뺀다. 남은 규칙은 하나 — 계획·결과는 **마지막 단이 향후계획**
      (일정은 거기 둔다). 검토보고(review)는 검사하지 않는다.

    헤딩이 하나도 없으면 판단하지 않는다(골격을 세운 문서가 아니다).
    """
    found = [normalize_heading(h) for h in (headings or [])]
    found = [h for h in found if h]
    if not found:
        return []

    want = outline_for(template_key)
    if not want or resolve(template_key) == REVIEW:     # plain·review — 목차를 강제하지 않는다
        return []
    if found[-1] != SECTION_4:
        return [f"[골격] 마지막 단이 '{found[-1]}' 이다 — 마지막 단은 '{SECTION_4}'"
                f"(언제 무엇을 할지 · 일정 줄만)"]
    return []
