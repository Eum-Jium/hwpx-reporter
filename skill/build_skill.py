# -*- coding: utf-8 -*-
"""claude.ai 업로드용 스킬 zip 빌드.

리포를 클론한 상태에서 실행한다 — 의존성은 없다(표준 라이브러리만):

    python skill/build_skill.py

하는 일:
  1. packages/ 의 hwpx-core·hwpx-skeleton 소스를 skill/hwpx/scripts/vendor/ 로 복사
  1b. V4 도구(agent/mcp_tool_v2_report_agent.py)에서 재는 기계를 떼어 vendor/v4_measure.py 로
      (V4 도구가 없는 공개 리포에서는 정본 빌드가 남긴 skill/v4_measure.py 를 쓴다)
  2. 스킬 폴더를 렌더 스모크 테스트로 검증(V4 꼴 원고 · 재는 기계가 V4 도구와 같은 쪽지를 내는지)
  3. build/skill/hwpx-skill-rev<N>.zip 패키징 (claude.ai 스킬 업로드 형식: 최상위 hwpx/)

vendor/ 는 packages/·V4 도구의 파생물이다 — 손으로 고치지 않는다.
소스를 고쳤으면 이 스크립트를 다시 돌려 zip 을 새로 뽑는다.
"""
import os
import re
import shutil
import sys
import zipfile

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SKILL_DIR)
HWPX = os.path.join(SKILL_DIR, "hwpx")
SCRIPTS = os.path.join(HWPX, "scripts")
VENDOR = os.path.join(SCRIPTS, "vendor")
DIST = os.path.join(REPO, "build", "skill")          # ★260928 — 빌드 결과는 build/ 한 곳


def build_vendor():
    if os.path.exists(VENDOR):
        shutil.rmtree(VENDOR)
    for pkg, mod in (("hwpx-core", "hwpx_core"), ("hwpx-skeleton", "hwpx_skeleton")):
        src = os.path.join(REPO, "packages", pkg, "src", mod)
        shutil.copytree(src, os.path.join(VENDOR, mod),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"[1/3] vendor <- packages/ ({', '.join(os.listdir(VENDOR))})")


# ★260928 — V4 도구의 재는 기계를 스킬로. **복제하지 않고 뽑는다** — V4 도구 파일에서
#   뿌리 함수와 그것이 부르는 최상위 함수·상수를 **소스 그대로** 떼어 vendor 에 둔다.
#   V4 에서 고치면 다음 빌드에 저절로 따라온다(두 벌이 벌어지는 병을 처음부터 막는다).
#   걷는 것은 `@mcp.tool()` 데코레이터뿐이다. 저장소 접점은 layout.py 가 덮는다.
MEASURE_SRC = os.path.join(REPO, "agent", "mcp_tool_v2_report_agent.py")
MEASURE_ROOTS = ("_lint_measure", "check_rules", "_sample_outline", "_table_ratios")
# ★261009 — 공개 리포에는 V4 도구 정본이 없다(mcp/ 의 사본은 주석을 걷은 것이다). 정본에서 뽑을 때
#   vendor 밖에도 한 벌 남겨 export 로 내보내고, V4 도구가 없는 곳에서는 그것을 쓴다.
#   vendor 안에 두면 build_vendor 가 지우고, 공개 리포의 .gitignore 에도 걸린다.
MEASURE_SNAPSHOT = os.path.join(SKILL_DIR, "v4_measure.py")


def build_measure():
    import ast
    dst = os.path.join(VENDOR, "v4_measure.py")
    if not os.path.exists(MEASURE_SRC):
        if not os.path.exists(MEASURE_SNAPSHOT):
            raise SystemExit(f"V4 도구도, 뽑아 둔 사본도 없다: {MEASURE_SNAPSHOT}")
        shutil.copyfile(MEASURE_SNAPSHOT, dst)
        print("[1b/3] vendor/v4_measure.py <- skill/v4_measure.py (V4 도구 없음, 뽑아 둔 사본)")
        return
    with open(MEASURE_SRC, encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    top = {}                                   # 이름 → 최상위 노드
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        top[n.id] = node

    need, todo = set(), list(MEASURE_ROOTS)
    while todo:
        name = todo.pop()
        if name in need or name not in top:
            continue
        need.add(name)
        for n in ast.walk(top[name]):
            if isinstance(n, ast.Name) and n.id in top and n.id not in need:
                todo.append(n.id)
    missing = [r for r in MEASURE_ROOTS if r not in need]
    if missing:
        raise SystemExit(f"V4 도구 파일에 뿌리 함수가 없다: {missing}")

    picked = [n for n in tree.body if n in {top[k] for k in need}]
    out = ['# -*- coding: utf-8 -*-\n',
           '"""V4 재는 기계 — **빌드 산물, 손으로 고치지 않는다.**\n\n',
           f'`build_skill.py` 가 `agent/mcp_tool_v2_report_agent.py` 에서 {len(picked)}개 정의를\n',
           '소스 그대로 떼어 냈다(`@mcp.tool()` 만 걷음). 쓰는 쪽은 `scripts/layout.py`.\n"""\n\n']
    for node in picked:
        start = node.lineno
        if getattr(node, "decorator_list", None):
            deco = [d for d in node.decorator_list if "mcp" not in ast.unparse(d)]
            if deco:
                raise SystemExit(f"{node.name}: mcp 밖의 데코레이터는 모른다")
            start = node.lineno         # def 줄부터 — 데코레이터 줄은 버린다
        # 정의 바로 위 주석 덩어리도 같이 옮긴다(상수의 까닭이 거기 있다)
        s = start - 1
        while s > 0 and lines[s - 1].lstrip().startswith("#"):
            s -= 1
        if getattr(node, "decorator_list", None):
            s = start - 1
        out.append("".join(lines[s:node.end_lineno]) + "\n\n")
    body = "".join(out)
    free = {n.id for n in ast.walk(ast.parse(body))
            if isinstance(n, ast.Name) and n.id in ("mcp", "requests")}
    if free:
        raise SystemExit(f"뽑은 코드가 서버 접점을 문다({free}) — 뿌리 목록을 다시 볼 것")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    with open(MEASURE_SNAPSHOT, "w", encoding="utf-8", newline="\n") as f:
        f.write(_public_copy(body))
    print(f"[1b/3] vendor/v4_measure.py <- V4 도구 ({len(picked)}개 정의 · 뿌리 {len(MEASURE_ROOTS)})")


def _public_copy(body):
    """공개 사본 — 주석과 독스트링을 걷는다(261009). 주석에는 V4 도구를 만들며 남긴 사정
    (판 번호·평가 기록·배포 환경)이 들어 있어 공개 리포에 맞지 않는다. 걷는 것은 설명뿐이라
    코드는 같다 — 뽑은 코드는 `__doc__` 를 읽지 않는다."""
    import ast
    tree = ast.parse(body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ('"""재는 기계 — 빌드 산물(공개 사본: 주석·설명을 걷었다). 쓰는 쪽은 `scripts/layout.py`."""\n\n'
            + ast.unparse(tree) + "\n")


def smoke_test():
    sys.path.insert(0, SCRIPTS)
    from render_report import render, list_templates
    keys = [t["key"] for t in list_templates()]
    out = os.path.join(DIST, "_smoke")
    res = render("plan", {"title": "빌드 검증 문서"},
                 body="\n".join([
                     "1. 추진배경", "□ 스킬 빌드 검증용 렌더 확인",
                     "2. 주요내용", "◦ 확인 항목",
                     "3. 추진방안", "□ 확인 방법",
                     "4. 향후계획", "□ 추진 일정",
                     "◦ ’26.  9.\t: 착수",
                     "◦ ’26. 10.\t: 점검",
                     "◦ ’26. 11.\t: 마무리",
                 ]),
                 output_dir=out)
    assert res["status"] == "success", res
    # 스모크 본문부터 골격 규칙(샘플 4단 · 마지막 단 향후계획)을 지킨다 — 빌드가 경고를 흘리면 규칙이 헐거워진다
    assert not res["warnings"], res["warnings"]
    shutil.rmtree(out)

    # 모드 B(stdlib 폴백)는 vendor/hwpx_core/markers.py 를 직접 적재한다 —
    # 경로가 깨지면 lxml 없는 환경에서만 터지므로 빌드에서 미리 잡는다.
    import hwpx_full
    d = hwpx_full.Doc("t").body("○○부와 협의 완료\n-5% 절감\n※ 출처: 자료")
    texts = []
    for b in d._blocks:
        if b.get("text"):                      # 항목부호·헤딩
            texts.append(b["text"])
        elif b.get("para") is not None:        # 평문 단락(run 누적)
            texts.append("".join(r["text"] for r in b["para"]._runs))
    joined = "\n".join(texts)
    # 본문 실문자가 마커로 먹히지 않았는지 + ※ 이중 마커가 없는지
    assert "○○부와 협의 완료" in joined, texts
    assert "-5% 절감" in joined, texts
    assert "* ※" not in joined, texts
    # 엔진이 못 받는 혼합 서식은 [알림] 으로 알려야 한다 — run 은 char_id 만 갖는데
    # 없는 bold 키를 보던 판정이 늘 거짓이라 조용히 빠졌다(261011).
    import contextlib
    import io
    mix_out = os.path.join(DIST, "_smoke_mix")
    m = hwpx_full.Doc("t")
    m.body("1. 개요\n□ 항목")
    m.para("보통 ").add_run("굵게", bold=True)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m.save(os.path.join(mix_out, "mix.hwpx"))
    assert "혼합 서식" in buf.getvalue(), buf.getvalue()
    shutil.rmtree(mix_out)

    # 모드 C(메모)도 vendor 경로로 돈다 — 앵커를 못 찾으면 조용히 빠지는 대신
    # skipped 에 남는 것까지 여기서 확인한다(돌려준 검토본에 지적이 빠지는 사고 방지).
    import review_memo
    memo_out = os.path.join(DIST, "_smoke_memo")
    res = render("plan", {"title": "메모 검증"},
                 body="1. 추진배경\n□ 수도 운영데이터 확인 필요",
                 output_dir=memo_out)
    got = review_memo.annotate(res["path"],
                               [{"anchor": "수도 운영데이터", "text": "[데이터]\n확인필요"},
                                {"anchor": "없는 말", "text": "붙으면 안 된다"}],
                               author="검토자")
    assert got["added"] == 1 and len(got["skipped"]) == 1, got
    back = review_memo.read_memos(got["path"])
    assert [m["text"] for m in back] == ["[데이터]\n확인필요"], back
    shutil.rmtree(memo_out)
    smoke_v4()
    print(f"[2/3] smoke render ok (templates: {len(keys)}, 모드 B 마커·모드 C 메모 · V4 원고·재는 기계 확인)")


# ★260928 — V4 꼴 원고(가변 단 · `- '26. 8월  …` 일정 줄 · 굵은 말머리 · 각주 · 표)가
#   스킬 경로에서 **경고 0** 으로 찍히고, 재는 기계 셋이 돌며, 쪽지가 V4 도구와 **글자까지 같은지**.
V4_MD = """## 1. 추진배경

- **(필요성) 정수장 운영 인력 감소에 따른 자동화 요구**
  - 최근 3년간 정수장 운영 인력이 12% 줄어 야간 수질 감시에 공백이 생겨 AI* 기반 감시 체계 도입 검토를 착수
  - 새솔정수장 시범 운영에서 약품 투입량을 월 8% 절감해 확대 적용 효과를 확인했고 다른 정수장의 적용 요구가 증가 추세

> AI: 운영 데이터를 학습해 수질 변화를 예측하는 모델

## 2. 현황

- **(운영현황) 시범 정수장 한 곳에서 6개월간 시범 운영**
  - 새솔정수장에서 '26. 1월부터 6개월간 탁도·잔류염소 예측 모델을 운영해 예측 오차 5% 이내 유지로 안정성 확인

| 구분 | 시범 전 | 시범 후 |
|---|---|---|
| 약품 투입량(톤/월) | 120 | 110 |
| 야간 감시 인원(명) | 4 | 2 |

## 3. 향후계획

- '26. 8월  대상 정수장 확정
- '26. 10월  확대 적용 착수
"""


def smoke_v4():
    import json
    from render_report import render_md
    import layout
    out = os.path.join(DIST, "_smoke_v4")
    tdir = os.path.join(SKILL_DIR, "hwpx-template", "templates")     # 양식 스킬에 든 첫 양식
    tpl = os.path.join(tdir, sorted(f for f in os.listdir(tdir) if f.endswith(".hwpx"))[0])
    res = render_md(V4_MD, template_path=tpl, fields={"title": "V4 원고 검증"},
                    intent="정수장 AI 운영 확대를 위해 대상 선정과 단계별 적용 계획을 수립하여 운영 인력 공백을 해소하는 방안을 마련",
                    output_dir=out)
    assert res["status"] == "success", res
    # 이번에 바꾼 규칙(가변 단 · 일정 줄 · 자수 띠 · 종결)은 경고 0 이어야 한다.
    # 낱말 쪼개짐·끝줄 채움은 폭 셈이라 원고마다 다르다 — 여기서 묻지 않는다.
    bad = [w for w in res["warnings"]
           if w.startswith(("[골격]", "[종결]")) or "자다 —" in w]
    assert not bad, bad
    shutil.rmtree(out)
    note = layout.view_layout(V4_MD, target_pages=1)
    assert note.startswith("[기계 검사]"), note
    assert "규칙으로 잡힌 것 없음" in layout.check_rules(V4_MD), layout.check_rules(V4_MD)
    assert "향후계획" in layout.sample_outline(2)
    # V4 도구와 같은 쪽지 — 뽑은 코드가 원본과 한 글자도 안 다르게 도는지
    if not os.path.exists(MEASURE_SRC):
        print("      (V4 도구 대조 건너뜀: 도구 파일이 없다)")
        return
    ns = {"__name__": "v4_tool_probe"}
    src = open(MEASURE_SRC, encoding="utf-8").read()

    class _Mcp:
        def tool(self, *a, **k):
            return lambda f: f
    ns["mcp"] = _Mcp()
    try:
        exec(compile(src, MEASURE_SRC, "exec"), ns)
    except Exception as e:                   # 도구 파일이 서버 없이 안 서면 대조만 건너뛴다
        print(f"      (V4 도구 대조 건너뜀: {type(e).__name__}: {e})")
        return
    want = json.loads(ns["_lint_measure"](draft=V4_MD, target_pages="1", scope="받은 글"))["note"]
    assert note == want, (note, want)


def skill_rev() -> int:
    """SKILL.md 의 `<!-- skill-rev: N -->` — 판 번호의 단일 출처.

    업로드한 스킬이 어느 판인지 파일명으로 알 수 있게 zip 이름에 넣는다.
    표기가 없으면 실패한다 — 무음으로 번호 없는 zip 이 나가면 헷갈리는 걸
    막으려던 목적 자체가 사라진다.
    """
    md = os.path.join(HWPX, "SKILL.md")
    with open(md, encoding="utf-8") as f:
        m = re.search(r"<!--\s*skill-rev:\s*(\d+)\s*-->", f.read())
    if not m:
        raise SystemExit(f"SKILL.md 에 '<!-- skill-rev: N -->' 표기가 없다: {md}")
    return int(m.group(1))


def package():
    os.makedirs(DIST, exist_ok=True)
    rev = skill_rev()
    # 판 번호가 없던 시절의 zip 하나만 치운다. **번호 붙은 판은 남긴다** —
    # 어느 판을 올렸는지 되짚거나 옛 판으로 되돌릴 때 필요하다(같은 rev 를 다시
    # 빌드하면 그 파일만 덮어쓴다). 종전 조건이 hwpx-skill*.zip 전부를 지워
    # rev5 를 빌드 한 번에 잃었다(08-16).
    legacy = os.path.join(DIST, "hwpx-skill.zip")
    if os.path.exists(legacy):
        os.remove(legacy)
    zip_path = os.path.join(DIST, f"hwpx-skill-rev{rev}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(HWPX):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.join("hwpx", os.path.relpath(full, HWPX))
                z.write(full, rel.replace(os.sep, "/"))
    n = len(zipfile.ZipFile(zip_path).namelist())
    print(f"[3/3] {os.path.relpath(zip_path, REPO)} ({n} entries)")


if __name__ == "__main__":
    build_vendor()
    build_measure()
    smoke_test()
    package()
    print("done - claude.ai 설정 > 기능(Capabilities) > 스킬에서 zip 업로드")
