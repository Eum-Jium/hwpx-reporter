# -*- coding: utf-8 -*-
"""단위 사이 빈 문단 크기(간격) 규칙 — 두 생성 경로의 단일 기준.

skeleton(style.gap_pt)과 스킬 모드 B(hwpx_full)가 같은 표를 써야 한다. 표가
갈라지면 같은 본문이 경로에 따라 다른 간격으로 렌더돼, 이 제품이 보장한다고
말하는 '정본 간격'이 경로마다 달라진다(실제로 · 조합에서 5pt vs 3pt 로 갈렸다).

규칙 자체는 세 줄로 요약된다:
    다음 단위가 heading  → 8pt (새 섹션 앞 크게 띄움)
    다음 단위가 □        → 5pt (같은 급 항목 사이)
    그 외(하위·참고)     → 3pt (블록 내부는 촘촘히)
아래 표는 이 규칙을 실측으로 확정한 조합만 명시한 것이고, 표에 없는 조합은
GAP_DEFAULT 로 떨어진다.

**stdlib 만 쓴다** — markers.py 와 같은 이유(모드 B 가 파일째 적재한다).
단위 이름은 정식 기호(□ ◦ - · *) + "heading" + "para"(마커 없는 평문).
"""

GAP_RULES = {
    # 새 섹션 앞
    ("□", "heading"): 8, ("◦", "heading"): 8, ("-", "heading"): 8,
    ("·", "heading"): 8, ("*", "heading"): 8, ("para", "heading"): 8,
    # 같은 급(□) 사이
    ("heading", "□"): 5, ("□", "□"): 5, ("◦", "□"): 5, ("-", "□"): 5,
    ("·", "□"): 5, ("*", "□"): 5,
    # 블록 내부 하강·형제
    ("□", "◦"): 3, ("◦", "◦"): 3, ("◦", "-"): 3, ("-", "-"): 3,
    ("-", "·"): 3, ("·", "·"): 3,
    # 참고(*) 앞
    ("□", "*"): 3, ("◦", "*"): 3, ("-", "*"): 3, ("·", "*"): 3,
}
GAP_DEFAULT = 5
GAP_AFTER_TITLE = 1            # 제목/일시 아래 미세 간격
GAP_BEFORE_FIRST_HEADING = 8   # 취지 박스 → 첫 헤딩


def gap_pt(prev_unit: str, next_unit: str) -> int:
    """두 단위 사이 빈 문단 크기(pt)."""
    return GAP_RULES.get((prev_unit, next_unit), GAP_DEFAULT)


def gap_rules_list():
    """(직전, 다음, pt) 3-튜플 목록 — 규격 문서화·외부 소비자용 뷰.

    0.2.5 까지 style.GAP_RULES 가 이 형태의 리스트였다. 단일 기준을 dict 로
    옮기면서 순회하던 소비자가 깨지지 않도록 변환 뷰를 남긴다.
    """
    return [(p, n, pt) for (p, n), pt in GAP_RULES.items()]
