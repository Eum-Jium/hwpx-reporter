# -*- coding: utf-8 -*-
"""
공공기관 보고서 서식 규칙 (사용자 수정 스켈레톤 전수 분석으로 검증, 2026-07-02).

주의: LEVEL_SPEC 의 font/bold(및 flow 항목의 font/bold/line_spacing)는 규격
문서화·외부 소비자용이다. 렌더러(fill_body)는 size 만 사용하고 실제 글꼴은
스켈레톤 프로토타입 문단 복제로 결정되므로, 여기 값을 바꿔도 출력은 안 변한다.

핵심 원리:
  - 전체 줄간격 160% (취지 박스만 150%)
  - 문단 사이 간격은 '빈 문단'을 끼워 넣고 그 빈 문단의 글자 크기로 조절
      8pt = 새 섹션(1. 헤딩) 앞         5pt = 헤딩→첫☐ / ☐ 항목 사이
      3pt = ☐ → 하위 ◦ 사이           1pt = 제목/일시 아래 미세 간격
  - 단위별 들여쓰기는 공백 문자(스페이스)로:
      헤딩(1.)=0칸  ☐=1칸  ◦=2칸  -=3칸  ·=4칸  *(참고)=4칸  붙임 둘째줄=6칸
"""
import re

from hwpx_core import gaps as _GAPS
from hwpx_core.markers import canon_marker, strip_marker

LINE_SPACING = 160          # 본문 기본 줄간격 %
LINE_SPACING_INTENT = 150   # 취지(󰂐) 박스 줄간격 %

# 단위(마커)별 규격: (앞 공백 칸수, 글자크기 pt, 글꼴)
LEVEL_SPEC = {
    "heading": {"lead": 0, "size": 16, "font": "HY헤드라인M", "bold": True},   # 1. 2. …
    "□":       {"lead": 1, "size": 15, "font": "휴먼명조",    "bold": False},
    "◦":       {"lead": 2, "size": 15, "font": "휴먼명조",    "bold": False},
    "-":       {"lead": 3, "size": 15, "font": "휴먼명조",    "bold": False},
    "·":       {"lead": 4, "size": 15, "font": "휴먼명조",    "bold": False},
    "*":       {"lead": 4, "size": 13, "font": "한양중고딕",  "bold": False},  # 참고
}

# 빈 줄(간격 조절용 빈 문단) 크기 규칙 — hwpx_core.gaps 단일 기준을 재수출한다.
# 스킬 모드 B 와 같은 표를 써야 같은 본문이 같은 간격으로 렌더된다.
GAP_RULES = _GAPS.GAP_RULES                # {(직전, 다음): pt}
GAP_RULES_LIST = _GAPS.gap_rules_list()    # 0.2.5 까지의 (직전, 다음, pt) 리스트 뷰
GAP_DEFAULT = _GAPS.GAP_DEFAULT
GAP_AFTER_TITLE = _GAPS.GAP_AFTER_TITLE            # 제목/일시 아래
GAP_BEFORE_FIRST_HEADING = _GAPS.GAP_BEFORE_FIRST_HEADING  # 취지박스 → 첫 헤딩


def marker_of(line: str):
    """줄 선두의 정식 마커(□ ◦ - · *). 마커 줄이 아니면 None.

    판정은 hwpx_core.markers 단일 기준 — 본문 실문자와 겹치는 별칭(- ○ ㅁ ㅇ)은
    뒤에 공백이 있어야 마커다("-5% 절감"·"○○부와 협의"는 본문).
    """
    s = line.lstrip()
    if "**" in s:
        s = s.replace("**", "").lstrip()
    return canon_marker(s)


def detect_level(line: str) -> str:
    """줄의 단위 감지. **볼드** 마크다운은 제거 후 판정
    (제거 전 판정하면 '**□ …**' 이 '*' 참고체로 오검출됨)."""
    s = line.lstrip()
    if "**" in s:
        s = s.replace("**", "").lstrip()
    if not s:
        return ""
    c = marker_of(s)
    if c:
        return c
    # '숫자.'(뒤에 숫자 아님) 또는 로마숫자 = 헤딩
    # 두 자리 숫자 시작("2026년"·"50%")이나 소수("3.5배")를 헤딩으로 오판하지 않도록 제한
    if re.match(r"\d{1,2}\.(?!\d)", s) or s[0] in "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ":
        return "heading"
    return "□"  # 모호하면 본문급(서식만 □ 를 따른다 — 계층 상태는 바꾸지 않는다)


def gap_pt(prev_level: str, next_level: str) -> int:
    """두 단위 사이 빈 줄 크기(pt). 판정은 hwpx_core.gaps 단일 기준."""
    return _GAPS.gap_pt(prev_level, next_level)


def normalize_lead(line: str) -> str:
    """단위에 맞는 앞 공백으로 교정. (마커는 유지)"""
    lvl = detect_level(line)
    if not lvl:
        return ""
    spec = LEVEL_SPEC.get(lvl)
    if not spec:
        return line.strip()
    return " " * spec["lead"] + line.strip()


def build_flow(lines):
    """
    내용 줄 목록 → 표준 간격 규칙이 적용된 문단 시퀀스.

    입력: ["1. 추진배경", "□ 배경 설명", "◦ 세부내용", ...]
    출력: [{"text": str(앞공백 포함), "size": pt, "font": str, "bold": bool,
            "line_spacing": %} 또는
           {"blank": True, "size": pt(빈 줄 크기), "line_spacing": 160}]
    """
    # 마크다운 볼드는 복제 렌더에서 해석 불가 — 레벨 판정 전에 일괄 제거
    lines = [l.replace("**", "") if isinstance(l, str) else l for l in lines]
    lines = _enforce_hierarchy(lines)
    flow = []
    prev_lvl = None
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue  # 입력의 빈 줄은 무시 (간격은 규칙으로 자동 생성)
        lvl = detect_level(line)
        spec = LEVEL_SPEC.get(lvl, LEVEL_SPEC["□"])
        content = _strip_trailing_period(line.strip())
        if prev_lvl is not None:
            flow.append({"blank": True, "size": gap_pt(prev_lvl, lvl),
                         "line_spacing": LINE_SPACING})
        flow.append({
            "text": " " * spec["lead"] + content,
            "size": spec["size"], "font": spec["font"], "bold": spec["bold"],
            "line_spacing": LINE_SPACING,
        })
        prev_lvl = lvl
    return flow


def _enforce_hierarchy(lines):
    """
    계층 구조 교정: □ 바로 아래에 - 가 오면(◦ 를 건너뜀) 그 - 를 ◦ 로 승격.
    올바른 구조는 □ → ◦ → -. 한 □ 블록에서 아직 ◦ 가 없는 상태의 첫 -(들)을
    ◦ 로 바꾸고, ◦ 가 한 번 나온 뒤의 - 는 그대로 둔다.

    상태 전이는 **실제 마커 줄에서만** 일어난다 — detect_level 은 모호한 줄을
    서식상 □ 로 떨어뜨리므로, 그걸로 판정하면 '[표1]' 같은 제어 줄이나 평문이
    새 □ 블록으로 오인돼 뒤따르는 - 가 통째로 ◦ 로 오승격된다.
    """
    out = []
    seen_o_since_box = False   # 현재 □ 블록에서 ◦ 를 봤는지
    in_box = False             # □ 블록 안인지
    for raw in lines:
        s = raw.strip()
        if not s:
            out.append(raw)
            continue
        m = marker_of(s)
        if m is None and detect_level(s) == "heading":
            in_box = False
            seen_o_since_box = False
        elif m == "□":
            in_box = True
            seen_o_since_box = False
        elif m == "◦":
            seen_o_since_box = True
        elif m == "-" and in_box and not seen_o_since_box:
            # □ 아래 ◦ 없이 등장한 - → ◦ 로 승격
            s = "◦ " + strip_marker(s)
            seen_o_since_box = True
        out.append(s)
    return out


def _strip_trailing_period(text: str) -> str:
    """개조식 종결 규칙: 줄 맨 끝의 마침표(./。)를 제거. 문장 중간의
    소수점·약어 등은 마지막 글자가 아니므로 영향받지 않는다.
    단 '2026. 7. 2.' 처럼 숫자 바로 뒤 마침표는 날짜의 '일' 표기라 보존."""
    t = text.rstrip(" ")
    if re.search(r"\d\.$", t):
        return t
    return t.rstrip(".。 ")


if __name__ == "__main__":
    import sys, json
    sys.stdout.reconfigure(encoding="utf-8")
    demo = [
        "1. 추진배경",
        "□ AI 기반 업무 자동화 필요성 증가",
        "◦ 반복 업무 증가 및 담당 인력 감소",
        "- 세부 근거 데이터",
        "* 관련근거: 행정기본법 제3조",
        "2. 추진계획",
        "□ 단계별 도입 방안",
    ]
    for item in build_flow(demo):
        if item.get("blank"):
            print(f"  ␣ (빈 줄 {item['size']}pt)")
        else:
            print(f"  {item['size']}pt {item['font']:6s} | '{item['text']}'")
