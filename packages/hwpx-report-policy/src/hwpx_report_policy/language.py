# -*- coding: utf-8 -*-
"""언어 드리프트 방어: 한자 탐지·거부, 응답 정화."""
from __future__ import annotations
import re
import json

# CJK 통합(4E00-9FFF)·확장A(3400-4DBF)에 더해 KS X 1001 기원 호환한자(F900-FAFF),
# 확장 B~I(20000-2EE5F), 호환 보충(2F800-2FA1F)까지 — 한글 블록과 비중첩
_HANJA = re.compile(
    r"[㐀-䶿一-鿿豈-﫿"
    r"\U00020000-\U0002EE5F\U0002F800-\U0002FA1F]")


def has_hanja(s: str) -> bool:
    return bool(_HANJA.search(s or ""))


def find_hanja(args: dict) -> list:
    """render 인자 중 문서에 실제로 들어가는 값(fields/body/intent)에서
    한자 포함 항목 목록. fields 의 비문자열 값도 렌더러가 str() 로 문서에
    넣으므로 같은 규칙으로 변환해 검사한다."""
    bad = []
    for k, v in (args.get("fields") or {}).items():
        s = v if isinstance(v, str) else ("" if v is None else str(v))
        if _HANJA.search(s):
            bad.append(f"fields.{k}='{s}'")
    b = args.get("body") or ""
    if isinstance(b, str) and _HANJA.search(b):
        bad.append("body")
    intent = args.get("intent") or ""
    if isinstance(intent, str) and _HANJA.search(intent):
        bad.append(f"intent='{intent}'")
    return bad


def sanitize_reply(reply: str, events: list) -> str:
    """응답에 한자가 섞이면(모델 언어 드리프트) 도구 결과 기반 한국어 요약으로 대체."""
    if not _HANJA.search(reply or ""):
        return reply
    for ev in reversed(events):   # 한 턴에 렌더가 여러 번이면 최신 성공본을 요약
        if ev.get("name") == "render_from_skeleton" and not ev.get("error"):
            # result 문자열은 표시용 2000자 절단본일 수 있음 → 원본 객체 우선
            res = ev.get("result_obj")
            if not isinstance(res, dict):
                try:
                    res = json.loads(ev.get("result", "{}"))
                except Exception:
                    continue
            if res.get("status") == "success":
                lines = [f"{res.get('template_label', '보고서')}가 생성되었습니다.",
                         "", f"파일: {res.get('path', '')}"]
                br = res.get("body_result")
                if br and br.get("filled"):
                    lines.append(f"본문 {br.get('lines', 0)}줄을 표준 서식에 맞춰 채웠습니다.")
                return "\n".join(lines)
    return "(요청을 처리했으나 응답 생성에 문제가 있었습니다. 파일 목록을 확인해 주세요.)"
