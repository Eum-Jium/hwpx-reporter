# -*- coding: utf-8 -*-
"""마크다운 → 개조식 변환 — 세 트랙의 단일 기준(260831 신설).

**변환기는 번역기다.** md 표기를 개조식 표기로 옮길 뿐 내용을 선별하지 않는다.
분량을 줄이거나 꼬리를 자르는 일은 여기서 하지 않는다.

왜 여기 있나 — 같은 변환이 세 곳에 따로 적혀 있었다:
    에이전트 도구   `_convert_rows`
    MCP 서버        그 복제본
    스킬            **없었다** — 그래서 스킬은 개조식으로만 body 를 받았다
셋이 갈라지면 같은 초안이 경로마다 다른 문서로 나온다. 이 모듈이 그 원천이다.

⚠️ 에이전트 도구(`mcp/`)는 아직 자기 복제본 `_convert_rows` 를 쓴다 — 갈아탈 때까지
   둘을 함께 고친다. 지금 복제본은 ○·ㅁ·ㅇ 별칭을 마커로 보지 않는다(여기는 본다).

규칙 요약
    | 표          → `[표N]` 마커 + 표 데이터를 따로 뽑는다
    ## N. 제목    → `N. 제목` (번호가 없으면 순번을 매긴다)
    - 항목        → 들여쓰기 0 = `□` · 2 = `◦` · 4 이상 = `-`
    > 참고        → `* 참고`  (각주·비고·그림 캡션이 다 이 줄이다)
    [이미지N]     → 순번을 다시 매긴다(단마다 1 로 겹쳐 오는 일이 있다)
    일정 줄       → 날짜와 내용 사이에 탭. 한 자리 월 패딩은 **렌더러**가 한다
                    (`schedule.pad_tab_date` — renderer.py 가 부른다)

stdlib 만 쓴다. 다만 markers·schedule 과 달리 **파일째 적재를 상정하지 않는다** —
패키지 안에서 정상 import 로 쓴다.
"""
import re

try:                                  # 패키지 안에서 정상 import
    from .markers import CANON, AMBIGUOUS
except ImportError:                   # 파일째 적재된 경우(블록 조립 계열)
    from markers import CANON, AMBIGUOUS   # type: ignore

__all__ = ["clean_md", "tabify", "convert_rows", "convert_md"]


_SEP_CELL = re.compile("^:?-+:?$")
_RULE = re.compile("^(?:-{3,}|={3,})$")
_HEAD = re.compile("^#{1,6}\\s*(.+)$")
_NUMBERED = re.compile("^(\\d+)\\.\\s")
_QUOTE = re.compile("^>\\s*(.*)$")
_BULLET = re.compile("^(\\s*)[-*+]\\s+(.*)$")
_MARKER_ONLY = re.compile("^\\[(표|이미지)\\d+\\]$")
# `- [이미지1] 현황도` 처럼 **항목 줄 안에** 마커를 쓴 경우(관대 처리)
_INLINE_MARKER = re.compile("^[-*+□☐◦]\\s*\\[(이미지|표)(\\d+)\\]\\s*(.*)$")

# 일정 줄 — 날짜부와 내용 사이를 탭으로.
# ⚠️범위 표기(`10~12월`)에서 끊기지 않게 `~` 를 날짜부에 포함시킨다. 끊기면
#   `'26.<탭>10~12월<탭>내용` 이 되는데 `'26. 9월` 은 멀쩡해 늦게 드러난다.
_SCHED = re.compile(
    "^(['’]?\\d{2}\\s*[.년]\\s*(?:\\d{1,2}\\.\\s*)*"
    "(?:\\d{1,2}\\s*(?:[~–-]\\s*\\d{1,2}\\s*)?월?|[상하]반기|\\d분기|말|초)?)\\s+(\\S.*)$")


def clean_md(s):
    """마크다운 장식을 걷어낸다 — **볼드**·__밑줄__·`코드`·[글자](주소)."""
    s = s.replace("**", "").replace("__", "").replace("`", "")
    s = re.sub("\\[([^\\]]+)\\]\\(([^)]*)\\)", "\\1", s)
    return s.strip()


def tabify(s):
    """일정 줄이면 날짜부와 내용 사이에 탭을 넣는다. 아니면 그대로."""
    m = _SCHED.match(s)
    return (m.group(1).rstrip() + "\t" + m.group(2)) if m else s


def _is_marker(head, rest):
    """줄 선두 글자가 항목부호인가. 헷갈리는 별칭은 뒤에 공백이 와야 마커다.

    판정 기준은 `markers` 한 곳이다 — 여기서 따로 목록을 들면 갈라진다.
    `*` 경계(`**핵심 수치**` 를 마커로 안 보는 것)도 260831 부터 거기 있다.
    """
    if head not in CANON:
        return False
    return not (head in AMBIGUOUS and not rest[:1].isspace())


def convert_rows(raw, table_offset=0):
    """마크다운을 개조식 줄로 옮기되 **원문 md 줄을 함께 나른다.**

    반환: `(rows, tables)` — `rows = [(개조식 줄, 원문 md 줄)]`

    원문 줄을 나르는 이유: 규격 검사의 행 번호는 변환된 본문 기준이라 md 의 행과
    어긋난다(빈 줄·표 구분행이 사라져 표가 많을수록 크게 밀린다). 교정은
    `찾을 줄 → 바꿀 줄` 쌍으로 원문에서 치환하므로 **열쇠는 행 번호가 아니라
    원문 줄 자체**다. 표만 쓰는 쪽은 `convert_md` 를 부르면 된다.

    Args:
        raw: 마크다운(또는 이미 개조식인) 본문.
        table_offset: 이미 앞에서 쓴 표 개수 — `[표N]` 번호를 이어 붙일 때.
    """
    text = raw if isinstance(raw, str) else ("%s" % (raw or ""))
    text = text.replace("\\n", "\n")

    rows, tables = [], []
    table_no = table_offset
    in_table, cur = False, None
    head_no = 0
    img_no = 0          # 이미지 순번 재부여 — 단마다 [이미지1] 로 겹쳐 오는 일이 있다

    for ln in text.splitlines():
        t = ln.rstrip()
        s = t.lstrip()

        if _RULE.match(s) or not s:
            in_table, cur = False, None
            continue

        # ── 표 ────────────────────────────────────────────
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            if not in_table:
                in_table = True
                table_no += 1
                rows.append(("[표%d]" % table_no, t))
                cur = {"headers": [clean_md(c) for c in cells], "rows": []}
                tables.append(cur)
            elif all(_SEP_CELL.match(c or "-") for c in cells):
                continue                     # |---|:--:| 구분행
            elif cur is not None:
                cur["rows"].append([clean_md(c) for c in cells])
            continue
        in_table, cur = False, None

        # ── 항목 줄 안에 쓴 `[이미지N] 캡션` (관대 처리) ──
        m = _INLINE_MARKER.match(s)
        if m:
            kind, num, cap = m.group(1), m.group(2), clean_md(m.group(3)).strip()
            if kind == "이미지":
                img_no += 1
                num = img_no
            rows.append(("[%s%s]" % (kind, num), t))
            if cap:
                rows.append(("* " + cap, t))
            continue

        if _MARKER_ONLY.match(s):
            if s.startswith("[이미지"):
                img_no += 1
                s = "[이미지%d]" % img_no
            rows.append((s, t))
            continue

        # ── 대제목 ───────────────────────────────────────
        m = _HEAD.match(s)
        if m:
            h = clean_md(m.group(1))
            n = _NUMBERED.match(h)
            if n:
                head_no = int(n.group(1))
            else:
                head_no += 1
                h = "%d. %s" % (head_no, h)
            rows.append((h, t))
            continue

        # ── 참고(각주·비고·캡션) ─────────────────────────
        m = _QUOTE.match(s)
        if m:
            rows.append(("* " + clean_md(m.group(1)), t))
            continue

        # ── 목록 — 들여쓰기가 계층을 정한다 ──────────────
        m = _BULLET.match(t)
        if m:
            indent = len(m.group(1).replace("\t", "  "))
            mark = "- " if indent >= 4 else ("◦ " if indent >= 2 else "□ ")
            rows.append((mark + tabify(clean_md(m.group(2))), t))
            continue

        # ── 이미 개조식이거나 평문 ───────────────────────
        if _is_marker(s[:1], s[1:]):
            rows.append((s[:1] + " " + tabify(clean_md(s[1:])), t))
        else:
            rows.append((clean_md(s) if _NUMBERED.match(s)
                         else "□ " + clean_md(s), t))

    return rows, tables


def convert_md(raw, table_offset=0):
    """마크다운을 개조식 본문으로 옮긴다.

    반환: `(개조식 본문 문자열, 표 목록)` — 표는 `[{"headers": [...],
    "rows": [[...]]}]` 꼴로, 본문에는 `[표N]` 마커만 남는다. 그대로
    `render(body=…, tables=…)` 에 넘기면 된다.
    """
    rows, tables = convert_rows(raw, table_offset)
    return "\n".join(c for c, _ in rows), tables
