# -*- coding: utf-8 -*-
"""재 보기 — 쓴 원고(마크다운)가 쪽에 어떻게 앉나 · 규칙에 걸리는 줄 · 샘플 골격.

보고서 에이전트(`mcp/`, 4판 — 코드 주석의 「V4」)가 쓰는 **같은 기계**다. 몸통은
`vendor/v4_measure.py`(빌드 산물 — 에이전트 도구에서 재는 부분만 소스 그대로 떼어 낸 것)이고,
이 파일은 저장소 접점만 덮는다.

    import sys, os
    sys.path.insert(0, os.path.join("<스킬 폴더>", "scripts"))
    from layout import view_layout, check_rules, sample_outline

    print(sample_outline(2))                 # 장수에 맞춘 샘플 골격(단 이름과 역할)
    print(view_layout(md, target_pages=2))   # 쪽 자리 · 표 밀림/접힘 · 자수 안 맞는 줄
    print(check_rules(md, refs=참고자료글))   # 종결·경어체·한자·마침표·날짜 꼴·자료에 없는 수치

재는 것은 `render_md` 가 받는 그 마크다운이다(`## N. 단명` · `- ` □ · 두 칸 `- ` ◦ · `> ` 참고 · 표).
렌더를 부르지 않는 어림셈이라 한/글 실물과 한두 줄 어긋날 수 있다.
⚠️도해(`grid` 표)는 재지 않는다 — md 표만 센다.
"""
import asyncio
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(_HERE, "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

import v4_measure as _M                                                     # noqa: E402

_KEY = "skilllayout"          # 열쇠는 8자 이상이라야 저장소 경로가 선다(_safe_key)


def _text(x):
    return x if isinstance(x, str) else ("" if x is None else "%s" % x)


def view_layout(md, target_pages=None):
    """원고가 쪽에 어떻게 앉나 — 분량·쪽 수·단별 쪽 자리·표 밀림/접힘·자수 안 맞는 줄.

    target_pages: 목표 장수. 주면 목표 대비 차이도 말한다.
    반환: 에이전트 도구 `view_layout` 과 같은 쪽지 문자열. 첫 줄이 무엇을 쟀는지 말한다.
    """
    import json
    md = _text(md)
    if not md.strip():
        return "LINT_FAIL: 잴 글이 없다"
    tp = "" if target_pages in (None, "") else _text(target_pages)
    try:
        j = json.loads(_M._lint_measure(draft=md, target_pages=tp, scope="받은 글"))
    except Exception as e:                                  # 재는 쪽 결함은 숨기지 않는다
        return "LINT_FAIL: 잴 수 없었다 — %s: %s" % (type(e).__name__, e)
    if j.get("lint_unavailable"):
        return "LINT_FAIL: 잴 수 없었다 — %s" % (j.get("error") or "원인 모름")
    return j.get("note") or ""


def check_rules(md, refs=""):
    """[문장 규칙]에 걸리는 줄 — 서술형 종결·경어체·한자·줄 끝 마침표·긴 날짜 꼴,
    그리고 refs(참고자료 글)를 주면 거기 없는 수치에 (확인필요)가 없는 곳.

    흐름·정합성(단끼리 겹침 · 표와 본문 수치)은 안 본다 — 읽어서 짚는다.
    """
    md, refs = _text(md), _text(refs)
    if not md.strip():
        return "REVIEW_FAIL: 볼 글이 없다"
    d = tempfile.mkdtemp(prefix="hwpx-layout-")
    old = os.environ.get("HWPX_DRAFT_DIR")
    os.environ["HWPX_DRAFT_DIR"] = d
    try:
        key = ""
        if refs.strip():
            key = _KEY
            with open(_M._refs_path(key), "w", encoding="utf-8") as f:
                f.write(refs)
        return asyncio.run(_M.check_rules(key=key, draft=md))
    finally:
        if old is None:
            os.environ.pop("HWPX_DRAFT_DIR", None)
        else:
            os.environ["HWPX_DRAFT_DIR"] = old
        shutil.rmtree(d, ignore_errors=True)


def sample_outline(pages=2):
    """장수에 맞춘 샘플 골격 — 단 이름과 역할, 표가 서는 단엔 「· 표 하나」.

    시작점이다. 소재에 맞춰 단을 바꾸고 채울 말이 없는 단은 뺀다. 마지막 단은 향후계획.
    """
    return _M._sample_outline(pages)


def table_ratios(table):
    """표 하나의 열 폭을 내용에 맞춘다(HWPUNIT 목록). 안 넓혀도 다 들면 None.

    `render_md` 가 표마다 알아서 부른다 — 손으로 부를 일은 드물다.
    """
    return _M._table_ratios(table)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(sample_outline(2))
