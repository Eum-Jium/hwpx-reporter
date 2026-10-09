# -*- coding: utf-8 -*-
"""claude.ai 업로드용 **양식 스킬** zip 빌드.

    python skill/build_template_skill.py

`hwpx` 스킬(엔진·작성 규칙)과 짝을 이루는 **양식만 든 스킬**을 싼다.
엔진 코드가 없어 vendor 복사도 스모크 렌더도 없다 — 파일을 그대로 담는다.

왜 따로인가: 양식은 문서를 찍는 순간에만 필요하고 조직마다 다르다.
엔진 스킬에 같이 넣으면 발동할 때마다 통째로 실린다(260831).
"""
import os
import re
import sys
import zipfile

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SKILL_DIR, "hwpx-template")
DIST = os.path.join(os.path.dirname(SKILL_DIR), "build", "skill")   # ★260928 — 빌드 결과는 build/ 한 곳
NAME = "hwpx-template"


def skill_rev() -> int:
    """SKILL.md 의 `<!-- skill-rev: N -->` — 판 번호의 단일 출처(엔진과 같은 규약)."""
    md = os.path.join(SRC, "SKILL.md")
    with open(md, encoding="utf-8") as f:
        m = re.search(r"<!--\s*skill-rev:\s*(\d+)\s*-->", f.read())
    if not m:
        raise SystemExit("SKILL.md 에 '<!-- skill-rev: N -->' 표기가 없다: %s" % md)
    return int(m.group(1))


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not os.path.isdir(SRC):
        raise SystemExit("양식 스킬 폴더가 없다: %s" % SRC)

    tpl = os.path.join(SRC, "templates")
    forms = sorted(f for f in os.listdir(tpl) if f.lower().endswith(".hwpx")) \
        if os.path.isdir(tpl) else []
    if not forms:
        raise SystemExit("templates/ 에 양식(.hwpx)이 하나도 없다 — 쌀 것이 없다")

    os.makedirs(DIST, exist_ok=True)
    rev = skill_rev()
    out = os.path.join(DIST, "%s-skill-rev%d.zip" % (NAME, rev))
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(SRC):
            for f in sorted(files):
                p = os.path.join(root, f)
                arc = os.path.join(NAME, os.path.relpath(p, SRC)).replace("\\", "/")
                z.write(p, arc)
                n += 1
    print("양식 %d개: %s" % (len(forms), ", ".join(os.path.splitext(f)[0] for f in forms)))
    print("%s  (%d개 · %s B)" % (out, n, format(os.path.getsize(out), ",d")))
    print("→ claude.ai 설정 > 기능(Capabilities) > 스킬 에 zip 업로드")
    print("⚠️엔진 스킬(hwpx)도 함께 올라가 있어야 동작한다.")


if __name__ == "__main__":
    main()
