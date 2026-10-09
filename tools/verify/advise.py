# -*- coding: utf-8 -*-
"""문장별로 '앞부분을 몇 pt 늘리/줄이면 첫 줄이 어절 경계로 떨어지는지' 계산.

linebreak 의 재보정 폭 모델(pt)을 그대로 쓴다. 한글 1자 ≈ 10.67pt.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linebreak import (CONT_X, EPS, HANGUL, MARKER_W, MARKER_X, NOTE_SCALE, R,
                       _bold_span, width)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def advise(line: str):
    s = line.strip()
    marker = s[0] if s and s[0] in MARKER_X else None
    scale = NOTE_SCALE if marker == "*" else 1.0
    x = MARKER_X[marker] + MARKER_W[marker] * scale if marker else CONT_X["□"]
    bold_end = _bold_span(s) if marker else -1
    ends, spaces = [], []          # ends[i] = i번째 글자까지의 끝 x / 공백 시작 x
    for i, ch in enumerate(s):
        if i == 0 and marker:
            ends.append(x)
            continue
        if ch == " ":
            spaces.append(ends[-1] if ends else x)
        x += width(ch, i <= bold_end) * scale
        ends.append(x)
    cap = R + EPS
    if ends[-1] <= cap:
        return "한 줄", None, None
    cut = next(i for i, e in enumerate(ends) if e > cap and s[i] != " ")
    if s[cut - 1] == " ":
        return "깨끗", None, None
    below = max((u for u in spaces if u <= cap), default=None)
    above = min((u for u in spaces if u > cap), default=None)
    shrink = round(cap - below, 1) if below is not None else None
    grow = round(above - cap, 1) if above is not None else None
    return "깨짐", shrink, grow


def _fmt(pt):
    return f"{pt}pt(≈{pt / HANGUL:.1f}자)"


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    lines = ([raw.strip() for raw in open(src, encoding="utf-8")]
             if src else [l.rstrip("\n") for l in sys.stdin])
    for c in lines:
        if not c or c[0] not in "□◦-·*" or "\t" in c:
            continue
        state, shrink, grow = advise(c)
        need = ""
        if state == "깨짐":
            need = f" → 앞부분 -{_fmt(shrink)}" if shrink else ""
            if grow:
                need += f" 또는 +{_fmt(grow)}"
        print(f"{len(c):3d}자 {state}{need} | {c[:34]}")
