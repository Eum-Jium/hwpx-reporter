# -*- coding: utf-8 -*-
"""줄바꿈 폭 모델 — 이제 hwpx_core.linebreak 가 단일 기준이다.

도구가 갖고 있던 모델을 코어로 올렸다(08-18). 렌더가 검사하지 않으면 규칙은
사람이 기억해야 하고, 기억은 샌다 — 붙임 본문에서 실제로 샜다. 이 파일은
기존 도구·견본 스크립트가 계속 돌도록 이름만 다시 내보낸다.
"""
import _repo_path                        # noqa: F401  — 설치본 그림자 차단
from hwpx_core.linebreak import (        # noqa: F401
    R, EPS, SPACE, HANGUL, HANGUL_BOLD, NOTE_SCALE,
    MARKER_X, MARKER_W, CONT_X, CHAR_W,
    width, break_points, seg_width, fill_ratio, check,
    check_lines, BOX_ONE_LINE_MAX, DOT_TWO_LINE, TAIL_FILL_MIN,
    _bold_span,
)

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    body = open(sys.argv[1], encoding="utf-8").read()
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s[0] not in "□◦-·*" or "	" in s:
            continue
        parts = break_points(s)
        flag = "" if all(c for _, c in parts[:-1]) else "   ← 낱말 중간에서 끊김"
        print(f"[{len(parts)}줄]{flag}")
        for seg, clean in parts:
            print(f"    |{seg}|")
