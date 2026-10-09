# -*- coding: utf-8 -*-
"""
스켈레톤 기반 렌더러.
assets/templates 의 양식 hwpx 를 열어 지정된 t요소(인덱스)들의 텍스트를 사용자 값으로 교체 후 저장.

원본 서식(제목 파란 박스, 표, 폰트, 취지 박스)은 그대로 유지됨.
"""
from __future__ import annotations
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
# 파서는 표준 라이브러리 ElementTree — 엔진을 한 벌로 두기 위함이다.
# lxml 전용 API(nsmap·getparent·QName)는 hwpx_core.xmlcompat 이 흡수한다.
from hwpx_core.xmlcompat import ET as etree

import hwpx_core as C

from . import style as KW

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "assets", "templates")

KST = timezone(timedelta(hours=9))


def today_kst() -> str:
    """공문 날짜 표기(’26. 8. 5) — 서버 시각(KST) 기준.

    작성일을 호출자(LLM)에게 맡기지 않기 위한 것이다(0.2.4). 맡기면 '오늘'을
    지어내거나 참고자료에 적힌 날짜를 옮겨 적는다 — 문서에 찍히는 날짜는
    사실이어야 하므로 렌더 시각으로 채운다.
    """
    n = datetime.now(KST)
    return "’%02d. %d. %d" % (n.year % 100, n.month, n.day)


def default_output_dir() -> str:
    """출력 폴더 기본값 — CWD 의존 금지(서비스 기동은 CWD 가 임의라
    System32 등에서 즉사하거나 산출물이 흩어진다).
    소스 체크아웃이면 모노레포 루트 output/, 휠 설치본이면 사용자 데이터 디렉토리."""
    pkg_root = Path(__file__).resolve().parent.parent.parent
    if (pkg_root / "pyproject.toml").exists():
        return str(pkg_root.parent.parent / "output")
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_DATA_HOME")
                    or (Path.home() / ".local" / "share"))
    return str(base / "hwpx-skeleton" / "output")


DEFAULT_OUTPUT_DIR = default_output_dir()
SECTION_MEMBER = C.SECTION0
SETTINGS_MEMBER = "settings.xml"

# 인쇄 방식은 **문서 파일에 저장된다**(settings.xml). 정본 양식에 4(2쪽 모아 찍기)가
# 박혀 있어 복제한 문서마다 따라붙었고, 그 문서를 PDF 로 내보내면 A4 가로 한 장에
# 두 쪽씩 붙어 나왔다. 한/글 앱의 인쇄 설정(HPrint.PrintMethod)은 0 이어도 파일 값이
# 이긴다 — 08-15 파일 값을 고쳐 보고 확인했다. 새로 만드는 문서는 0(기본)으로 둔다.
PRINT_METHOD_BASIC = 0
_PRINT_METHOD_RE = re.compile(
    rb'(<config:config-item name="PrintMethod" type="short">)\d+(</config:config-item>)')


def normalize_print_method(members: Dict[str, bytes], value: int = PRINT_METHOD_BASIC):
    """settings.xml 의 PrintMethod 를 value 로 맞춘다. 바꿨으면 이전 값을 반환."""
    data = members.get(SETTINGS_MEMBER)
    if not data:
        return None
    m = _PRINT_METHOD_RE.search(data)
    if not m:
        return None
    old = int(re.search(rb">(\d+)<", m.group(0)).group(1))
    if old == value:
        return None
    members[SETTINGS_MEMBER] = _PRINT_METHOD_RE.sub(
        rb"\g<1>" + str(value).encode() + rb"\g<2>", data)
    return old

# 【주관】 줄 공통 필드 — 유형 템플릿 견본이 전부 같은 구조라(t 인덱스:
# 0=제목, 1=【주관】, 2=담당자 앞부분, 3=담당자 꼬리+날짜) 한 정의를 공유한다.
# 공유하지 않으면 견본 날짜('(’26.7.13)')가 그대로 나간다.
_OWNER_DATE_FIELDS: Dict[str, Dict[str, Any]] = {
    "owner": {"index": 2, "hint": "담당자 (예: '○○처 이몽룡 과장(0002)'). "
                                  "안 주면 견본을 그대로 둔다"},
    "date":  {"index": 3, "hint": "작성일. 비우면 서버 시각(KST)으로 "
                                  "견본의 날짜만 바꾼다"},
}

# 양식은 **한 벌**이다 — 아홉 유형을 뜯어 보니 렌더에 쓰이는 부분(제목상자·
# 【주관】·취지박스·문단 견본 heading/□/◦·표 그리드·필드)이 전부 같았고, 실제로
# 갈린 것은 헤딩 자동번호뿐이었다(planning·sample 만 켜져 있어 나머지 일곱 종은
# '1. 추진배경' 이 글자로 본문에 남았다). 견본 본문은 어차피 body 가 통째로
# 교체하므로, 양식을 나눠 둘 이유가 없다 — 나눠 두면 이런 불일치만 쌓인다.
STANDARD_TEMPLATE = "standard.hwpx"
PLAIN_TEMPLATE = "plain.hwpx"    # 기본 양식 — 공문서 껍데기 없음(260831)

# 공문서 유형은 **셋**(plan·result·review)이고 셋 다 standard.hwpx 를 쓴다. 갈리는 것은
# 골격 샘플뿐이고(hwpx_core.outline),
# 그 밖의 차이(교육이냐 행사냐)는 양식이 아니라 지침 md 의 소재별 절이 맡는다.
TEMPLATE_SPECS: Dict[str, Dict[str, Any]] = {
    # ★기본 양식(260831). 제목만 있고 【주관】·취지 상자가 없다 — 목차도 강제하지
    # 않는다(`hwpx_core.outline.PLAIN`). 계획표·안내문·개인 문서처럼 공문서 골격이
    # 어울리지 않는 글이 이 엔진으로 나오는 자리다. **평소에는 이것을 쓰고**, 공문서
    # 관행(샘플 골격·【주관】·취지 상자)이 필요할 때 plan/result/review 를 고른다.
    "plain": {
        "label": "기본 문서",
        "description": "공문서 골격이 없는 일반 문서 — 제목 + 본문. 목차를 강제하지 "
                       "않고 【주관】·취지 상자도 없다. 양식 지정이 없으면 이것.",
        "file": PLAIN_TEMPLATE,
        "fields": {
            "title": {"index": 0, "hint": "문서 제목 (25자 이내)"},
        },
    },
    "plan": {
        "label": "계획 보고서",
        "description": "무엇을 할 것인가 — 추진계획·방안·대책 및 교육/행사/회의 계획. "
                       "샘플 4단(3번 '추진방안')에서 시작하고 마지막 단은 '향후계획'",
        "file": STANDARD_TEMPLATE,
        "fields": {
            "title":     {"index": 0, "hint": "보고서 제목 (25자 이내)"},
            # 【주관】 줄. ⚠️기본 동작은 **날짜만 바꾸고 담당자는 견본 그대로 두는 것**
            #   — 부서·직급·내선은 자동으로 채울 방법이 없고, 견본이 남아 있어야
            #     사람이 한글에서 자기 것으로 고친다. owner 는 명시할 때만 쓰는 자리.
            **_OWNER_DATE_FIELDS,
        },
    },
    "result": {
        "label": "결과 보고서",
        "description": "무엇을 했는가 — 사업·교육·행사·회의 결과보고. "
                       "샘플 4단(3번 '추진결과')에서 시작하고 마지막 단은 '향후계획'",
        "file": STANDARD_TEMPLATE,
        "fields": {
            "title":     {"index": 0, "hint": "보고서 제목 (25자 이내)"},
            **_OWNER_DATE_FIELDS,
        },
    },
    # 기승전결을 세우지 않는 1~2쪽짜리 검토보고. 서식은 위 둘과 같고 골격만 다르다
    # (개요 · 세부내용 · 검토의견) — 사안을 사실 위주로 설명하고 판단을 붙이는 자리다.
    "review": {
        "label": "검토보고",
        "description": "이 사안을 어떻게 볼 것인가 — 경위 설명·자료 요지·확인 결과에 "
                       "담당자 판단을 붙이는 1~2쪽 보고. "
                       "샘플 3단(개요·세부내용·검토의견), 추진배경·향후계획을 세우지 않는다",
        "file": STANDARD_TEMPLATE,
        "fields": {
            "title":     {"index": 0, "hint": "보고서 제목 (25자 이내)"},
            **_OWNER_DATE_FIELDS,
        },
    },
}

# 옛 유형 키 → 지금 키. 표는 hwpx_core.outline 이 갖는다 — 골격 검사와 같은
# 분류를 써야 별칭으로 부른 문서가 엉뚱한 3번 이름으로 검사받지 않는다.
TEMPLATE_ALIASES: Dict[str, str] = dict(C.outline.ALIASES)

# 없어진 키 → 무엇을 보라고 안내할지. 조용히 다른 양식으로 바꿔 찍지 않는다.
# ('basic' 은 한때 렌더되지 않는 서식 설명 페이지였다 — 그 설명은
#  references/format_spec.md 로 갔고, 그 이름은 지금 review 의 별칭이다.)
TEMPLATE_RETIRED: Dict[str, str] = {}


def resolve_template_key(key: str) -> str:
    """옛 유형 키를 지금 키로 옮긴다. 모르는 키는 그대로 돌려준다(호출부가 오류로 받는다)."""
    return C.outline.resolve(key)


def template_file(key: str) -> str:
    """유형 키의 양식 파일 경로. 공문서 세 유형이 같은 파일을 가리킨다.

    이름이 `template_path` 가 아닌 이유: render() 의 인자에 같은 이름이 있어
    함수가 지역 변수에 가려진다(밖에서 가져온 양식 경로를 받는 자리다).
    """
    spec = TEMPLATE_SPECS.get(key) or {}
    return os.path.join(TEMPLATE_DIR, spec.get("file", f"{key}.hwpx"))


def list_templates() -> List[Dict[str, Any]]:
    """UI 및 LLM 용 템플릿 목록 반환."""
    out = []
    for key, spec in TEMPLATE_SPECS.items():
        path = template_file(key)
        out.append({
            "key": key,
            "label": spec["label"],
            "description": spec["description"],
            "exists": os.path.exists(path),
            "fields": [
                {"name": fname, "hint": f["hint"]}
                for fname, f in spec["fields"].items()
            ],
        })
    return out


# 정식 기호 → 스켈레톤 정본 글자. □(U+25A1) 은 양식 원본이 ☐(U+2610) 를 쓴다.
_TEMPLATE_GLYPH = {"□": "☐"}

# XML 1.0 이 금지하는 제어문자 — 모델이 만든 인자에 섞여 들어오면 lxml 이
# "All strings must be XML compatible" 로 죽는다. 문서 내용과 무관하므로 제거한다.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _xml_safe(s: str) -> str:
    """XML 에 넣을 수 없는 제어문자를 제거한 문자열."""
    return _CTRL_RE.sub("", s)


# 【주관】 줄의 날짜 괄호 — 견본은 `(’26.7.13)` 꼴. 연도 2~4자리·공백·끝 온점을 모두 허용해
# 견본이 개정돼 표기가 조금 달라져도 잡히게 한다(못 잡으면 skipped 로 사실을 남긴다).
_DATE_PAREN_RE = re.compile(
    r"\(\s*[’'`]?\s*\d{2,4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}\s*\.?\s*\)")


def _stamp_date(sec, HP, idx: int, day: str) -> bool:
    """【주관】 줄에서 **날짜 괄호만** 바꾼다 — 담당자·직급·내선은 손대지 않는다.

    통째 치환(_replace_text_at_indices)과 다른 이유: 견본의 그 t 요소에는
    담당자 꼬리('이몽룡 과장(0002)')와 날짜가 함께 들어 있다. 통째로 바꾸면
    사람이 고쳐 쓸 견본이 사라진다(실무 확인).
    """
    ts = [t for t in sec.iter(f"{{{HP}}}t") if (t.text or "").strip()]
    if not (0 <= idx < len(ts)):
        return False
    el = ts[idx]
    # 치환값은 함수로 준다 — 템플릿 문자열로 주면 사용자(모델) 입력 속 역슬래시가
    # 그룹 참조(\1)·이스케이프로 해석돼 값이 조용히 바뀌거나 렌더가 죽는다.
    new, n = _DATE_PAREN_RE.subn(lambda _m: f"({day})", el.text or "")
    if not n:
        return False
    el.text = new
    _clear_lineseg_of_t(el, HP, sec)
    return True


def _detect_fields(sec, HP) -> Dict[str, Dict[str, Any]]:
    """임의 양식에서 제목·【주관】 자리를 찾아 fields 스펙을 만든다.

    인덱스 기준은 _replace_text_at_indices 와 같다(**비어 있지 않은 hp:t 순서**).
    내장 양식은 0=제목·1=【주관】·2=담당자·3=꼬리+날짜로 같지만, 밖에서 가져온
    양식은 제목상자가 없거나 【주관】 줄이 없을 수 있어 실제로 훑어 찾는다.
    """
    ts = [(t.text or "").strip()
          for t in sec.iter(f"{{{HP}}}t") if (t.text or "").strip()]
    fields: Dict[str, Dict[str, Any]] = {}
    if ts:
        fields["title"] = {"index": 0, "hint": "보고서 제목 (25자 이내)"}
    for i, txt in enumerate(ts):
        if "【주관】" not in txt:
            continue
        # 견본 구조: [i]=【주관】…, [i+1]=담당자 앞부분, [i+2]=꼬리+날짜
        if i + 2 < len(ts) and _DATE_PAREN_RE.search(ts[i + 2] or ""):
            fields["owner"] = {"index": i + 1,
                               "hint": "담당자. 안 주면 견본을 그대로 둔다"}
            fields["date"] = {"index": i + 2,
                              "hint": "작성일. 비우면 오늘(KST)로 날짜만 갱신"}
        break
    return fields


def inspect_template(path: str) -> Dict[str, Any]:
    """임의 hwpx 를 양식으로 쓸 수 있는지 진단한다(렌더하지 않는다).

    반환: {"usable": bool, "fields": {...}, "prototypes": [...],
           "missing": [...], "has_table_grid": bool, "body_start": str|None,
           "message": str}
    """
    try:
        members = C.read_members(path)
    except Exception as e:                       # 손상·비hwpx
        return {"usable": False, "message": f"열 수 없음: {e}"}
    if C.SECTION0 not in members or C.HEADER not in members:
        return {"usable": False, "message": "hwpx 구조가 아님(section0/header 없음)"}

    sec = C.xmlcompat.parse(members[C.SECTION0])
    HP = C.xmlcompat.hp_uri(sec, C.HP)
    charmap = _parse_charmap(members[C.HEADER])
    paras = [p for p in sec if C.xmlcompat.local_name(p) == "p"]
    protos = _collect_prototypes(paras, HP, charmap)

    body_start = None
    for p in paras:
        txt = _para_text(p, HP).strip()
        if txt and _para_size(p, HP, charmap) >= 16 and not _has_table(p, HP):
            body_start = txt[:24]
            break

    have = [k for k in ("heading", "□", "◦", "-", "*") if k in protos]
    missing = [k for k in ("heading", "□") if k not in protos]   # 본문 최소 요건
    if body_start is None:
        missing.append("본문 시작(16pt 헤딩)")
    fields = _detect_fields(sec, HP)
    usable = not missing
    msg = ("양식으로 쓸 수 있다" if usable else
           f"부족한 요소: {', '.join(missing)} — 이 양식에 해당 견본 문단이 있어야 "
           f"서식을 복제할 수 있다")
    return {"usable": usable, "fields": fields, "prototypes": have,
            "missing": missing, "blank_sizes": sorted(protos["blank"]),
            "has_table_grid": _find_grid_proto(sec, HP) is not None,
            "body_start": body_start, "message": msg}


def _replace_text_at_indices(sec, HP, replacements: Dict[int, str]) -> set:
    """
    파싱된 section 트리에서 '내용이 있는' hp:t 요소 순서로 인덱스 → 텍스트 치환.
    (TEMPLATE_SPECS 의 인덱스는 빈 t 를 제외하고 센 것 — 빈 t 포함해 세면
     한 칸씩 밀려 엉뚱한 자리에 쓰이므로 반드시 동일 기준 사용)
    반환: 실제 치환된 인덱스 집합 — 범위 밖(템플릿 개정으로 t 수 감소)은
    무음 no-op 이 아니라 호출부가 skipped 로 보고해야 한다.
    """
    ts = [t for t in sec.iter(f"{{{HP}}}t") if (t.text or "").strip()]
    done = set()
    for idx, new_text in replacements.items():
        if 0 <= idx < len(ts):
            ts[idx].text = new_text
            _clear_lineseg_of_t(ts[idx], HP, sec)
            done.add(idx)
    return done


# ── 본문 채우기 (표준 간격 규칙) ──────────────────────
# 저수준 문단 읽기는 hwpx-core 에 위임(중복 제거). HP 인자는 호출부 호환용으로 유지.
def _para_text(p, HP=None) -> str:
    return C.para_text(p)


def _para_size(p, HP, charmap) -> float:
    return C.para_charsize(p, charmap)


def _parse_charmap(hdr_bytes: bytes) -> Dict[str, int]:
    return C.parse_charmap(hdr_bytes)


def _has_secpr(p, HP) -> bool:
    return next(iter(p.iter(f"{{{HP}}}secPr")), None) is not None


def _has_table(p, HP) -> bool:
    return next(iter(p.iter(f"{{{HP}}}tbl")), None) is not None


def _clear_lineseg(p, HP) -> None:
    """
    문단의 줄 배치 캐시(linesegarray) 제거.
    캐시가 이전(짧은) 텍스트 기준이면 한글이 글자를 겹쳐 그림 —
    제거하면 한글이 열 때 새로 계산함 (엔진 생성 파일도 캐시 없이 정상).
    """
    for parent in list(p.iter()):
        for lsa in [c for c in parent if _ln(c.tag) == "linesegarray"]:
            parent.remove(lsa)


def _clear_lineseg_of_t(t, HP, root) -> None:
    """t 요소가 속한 문단의 lineseg 캐시 제거.

    root(보통 sec)를 받는 이유: ElementTree 에는 getparent 가 없어 부모 사전을
    만들어 거슬러 오른다(파서 중립).
    """
    pm = C.xmlcompat.parent_map(root)
    node = pm.get(t)
    while node is not None:
        if C.xmlcompat.local_name(node) == "p":
            _clear_lineseg(node, HP)
            return
        node = pm.get(node)


# 문장 중간의 부연 괄호 — 안에 공백이나 숫자가 있으면 설명이고, 없으면 짧은
# 라벨이다('(북부)', '(추정)'). 설명 괄호만 본문보다 2pt 작게 쓴다(실물 대조).
_PAREN = re.compile(r"\(([^()]*)\)")


# 줄 맨 앞의 말머리 라벨 — '☐ (필요성) …' 처럼 그 항목이 무엇을 말하는지 밝히는
# 짧은 꼬리표. 라벨 글자만 굵게 쓴다(괄호는 굵지 않다, 실물 대조).
_LEAD_LABEL = re.compile(r"^(\s*[□☐◦\-*·※]?\s*)\(([^()]{1,12})\)")


# **괄호 위첨자 규칙은 뗐다.** 예전엔 '1단계(북부)' 처럼 숫자 토큰 바로 뒤의 짧은 괄호를 괄호째 지우고
#   위첨자로 올렸는데, 같은 조건에 '50억원(안)'·'80억원(확인필요)' 도 걸려 뜻이 있는 괄호가 사라졌다.
#   괄호는 이제 말머리(굵게)·부연(작게) 둘만 가르고 나머지는 글자 그대로 둔다. 위첨자는 낱말에 붙은
#   각주 별표(`단어*`)뿐 — 명시 표기만 서식이 된다. 위첨자를 다시 쓸 땐 `^` 같은 명시 표기로 정한다.


# 각주 별표: 낱말에 **붙어 있는** '*' 만 위첨자로 올린다(`렌더링 엔진* 구축`).
# 줄 앞 참고 마커('    * 자료: …')는 앞이 공백이라 걸리지 않는다.
_FOOTNOTE_STAR = re.compile(r"(?<=[^\s(*])\*")


def _split_footnote_stars(segs):
    """평문 조각 안의 각주 별표를 별도 'sup' 조각으로 떼어낸다."""
    out = []
    for seg_text, kind in segs:
        if kind is not None or "*" not in seg_text:
            out.append((seg_text, kind))
            continue
        pos = 0
        for m in _FOOTNOTE_STAR.finditer(seg_text):
            if m.start() > pos:
                out.append((seg_text[pos:m.start()], None))
            out.append(("*", "sup"))
            pos = m.end()
        if pos < len(seg_text):
            out.append((seg_text[pos:], None))
    return out


def _paren_segments(text: str):
    """[(조각, 서식)] 로 나눈다. 서식: None·'small'(부연 괄호)·'bold'(말머리 라벨)·
    'sup'(낱말에 붙은 각주 별표 — 괄호 라벨 위첨자는 09-22 에 뗐다).
    나눌 것이 없으면 통짜 한 조각."""
    text = text or ""
    # 중첩 괄호는 최내곽만 잡혀 바깥 괄호 문자가 유실된다 — 괄호는 손대지 않되
    # 각주 별표는 그대로 처리한다.
    if text.count("(") != text.count(")") or re.search(r"\([^()]*\(", text):
        return _split_footnote_stars([(text, None)])
    segs, pos = [], 0
    lead = _LEAD_LABEL.match(text)
    if lead:
        segs.append((lead.group(1) + "(", None))
        segs.append((lead.group(2), "bold"))
        segs.append((")", None))
        pos = lead.end()
    start = pos
    for m in _PAREN.finditer(text):
        if m.start() < start:
            continue
        inner = m.group(1)
        if not inner:
            continue
        # 안에 공백이나 숫자가 있으면 부연 설명(괄호째 2pt 작게). 그 밖의 괄호는 건드리지 않는다(문자 보존) —
        # 09-22 부터 '1단계(북부)' 식 라벨 위첨자 없음(위 주석).
        if " " in inner or any(c.isdigit() for c in inner):
            kind = "small"
        else:
            kind = None
        if kind is None:
            continue
        if m.start() > pos:
            segs.append((text[pos:m.start()], None))
        segs.append((m.group(0) if kind == "small" else inner, kind))
        pos = m.end()
    if not segs:
        return _split_footnote_stars([(text, None)])
    if pos < len(text):
        segs.append((text[pos:], None))
    return _split_footnote_stars(segs)


def _fill_t(t, HP, text: str) -> None:
    """hp:t 하나에 텍스트를 넣는다. 탭 문자(\\t)는 <hp:tab/> 요소로 변환
    (OWPML 의 t 는 mixed content — tab 의 tail 이 뒤 텍스트). 일정 줄의
    날짜·내용 열 정렬용: '26. 9월<탭>투자심의 상정."""
    for ch in list(t):              # 프로토타입에 남아 있을 하위 요소 제거
        t.remove(ch)
    if "\t" in (text or ""):
        parts = text.split("\t")
        t.text = parts[0]
        for part in parts[1:]:
            tab = etree.SubElement(t, f"{{{HP}}}tab")
            tab.tail = part
    else:
        t.text = text


def _set_para_text(p, HP, text: str, hdr=None, small_cache: dict = None,
                   bold_cache: dict = None, sup_cache: dict = None) -> None:
    """복제된 문단의 텍스트를 통째로 교체 (첫 t 에 전체, 나머지 t 비움).

    hdr 을 주면 부연 괄호는 2pt 작게, 말머리 라벨은 굵게 별도 run 으로 뗀다(0.2.3).
    """
    # 일정 줄 한 자리 월·일은 여기서 폭을 맞춘다 — 괄호 분절 전에 한 번만 손대면
    # 모드 A·B 가 같이 낫는다(모드 B 도 vendor/hwpx_skeleton 으로 이 경로를 탄다).
    text = C.pad_tab_date(text)
    segs = (_paren_segments(text)
            if (hdr is not None and small_cache is not None) else [(text, None)])
    runs = p.findall(f"{{{HP}}}run")
    if len(segs) > 1 and runs:
        proto = runs[0]
        idx = list(p).index(proto)
        for r in runs[1:]:
            p.remove(r)
        base_cid = proto.get("charPrIDRef")
        small_cid = _make_smaller_charpr(hdr, base_cid, small_cache)
        bold_cid = (_make_bold_charpr(hdr, base_cid, bold_cache)
                    if bold_cache is not None else base_cid)
        sup_cid = (_make_supscript_charpr(hdr, base_cid, sup_cache)
                   if sup_cache is not None else base_cid)
        made = []
        for seg_text, kind in segs:
            r = deepcopy(proto)
            if kind == "small":
                r.set("charPrIDRef", small_cid)
            elif kind == "bold":
                r.set("charPrIDRef", bold_cid)
            elif kind == "sup":
                r.set("charPrIDRef", sup_cid)
            ts = list(r.iter(f"{{{HP}}}t"))
            for j, t in enumerate(ts):
                if j == 0:
                    _fill_t(t, HP, seg_text)
                else:
                    par = C.xmlcompat.parent_map(r).get(t, r)
                    r.remove(par if par is not r else t)
            made.append(r)
        p.remove(proto)
        for off, r in enumerate(made):
            p.insert(idx + off, r)
    else:
        ts = list(p.iter(f"{{{HP}}}t"))
        for i, t in enumerate(ts):
            if i == 0:
                _fill_t(t, HP, text)
            else:
                for ch in list(t):
                    t.remove(ch)
                t.text = ""
    _clear_lineseg(p, HP)


def _collect_prototypes(paras, HP, charmap):
    """
    본문용 프로토타입 수집:
      heading(16pt) / item '□'(☐ 시작) / '◦' / '-' / '*' / blank{size_pt: el}
    표·secPr 포함 문단은 프로토타입에서 제외.
    """
    protos = {"blank": {}}
    for p in paras:
        if _has_secpr(p, HP) or _has_table(p, HP):
            continue
        txt = _para_text(p, HP)
        stripped = txt.strip()
        size = _para_size(p, HP, charmap)
        if not stripped:
            key = int(round(size))
            if key not in protos["blank"]:
                protos["blank"][key] = p
            continue
        c = stripped[0]
        if size >= 16 and "heading" not in protos:
            protos["heading"] = p
        elif c in "☐□ㅁ" and "□" not in protos:
            protos["□"] = p
        elif c in "◦○ㅇ" and "◦" not in protos:
            protos["◦"] = p
        elif c == "-" and "-" not in protos:
            protos["-"] = p
        elif c in "*※" and "*" not in protos:
            protos["*"] = p
    return protos


def _proto_for_level(protos, lvl):
    """레벨별 프로토타입. 없으면 근접 레벨로 폴백."""
    fallback = {"heading": ["heading"],
                "□": ["□", "◦"],
                "◦": ["◦", "□"],
                "-": ["-", "◦", "□"],
                "·": ["-", "◦", "□"],
                "*": ["*", "-", "◦", "□"]}
    for k in fallback.get(lvl, ["□"]):
        if k in protos:
            return protos[k]
    return None


def _blank_proto(protos, want_pt):
    """원하는 크기의 빈 줄 프로토타입. 없으면 가장 근접한 크기."""
    blanks = protos["blank"]
    if not blanks:
        return None, None
    if want_pt in blanks:
        return blanks[want_pt], want_pt
    nearest = min(blanks.keys(), key=lambda k: abs(k - want_pt))
    return blanks[nearest], nearest


def fill_intent(sec, HP, intent_text: str) -> bool:
    """
    취지 박스(󰂐 ...)의 안내 문구를 실제 요약 문장으로 치환.
    첫 󰂐 t 요소에 내용을 쓰고, 중복 󰂐/'(본문과 내용중복 시 생략 가능)' 은 비움.
    """
    done = False
    for t in sec.iter(f"{{{HP}}}t"):
        txt = t.text or ""
        s = txt.strip()
        if s.startswith("󰂐"):
            if not done:
                t.text = "󰂐 " + intent_text.strip()
                done = True
            else:
                t.text = ""
            _clear_lineseg_of_t(t, HP, sec)
        elif "내용중복 시 생략" in s:
            t.text = ""
            _clear_lineseg_of_t(t, HP, sec)
    return done


def drop_intent(sec, HP) -> int:
    """취지 상자(󰂐 …) 문단과 그 안내문을 문단째 제거하고 지운 수를 반환(0.2.3).

    취지를 주지 않으면 뼈대의 견본 문구가 그대로 남아 문서에 노출된다.
    한 장짜리 보고서는 취지 상자를 쓰지 않는 것이 관례라 빈 취지 = 삭제로 본다.
    바로 뒤의 간격용 빈 문단 하나까지 같이 걷어야 위쪽 공백이 남지 않는다.
    """
    tops = [ch for ch in sec if C.xmlcompat.local_name(ch) == "p"]
    drop = []
    for i, p in enumerate(tops):
        s = _para_text(p, HP).strip()
        if s.startswith("󰂐") or "내용중복 시 생략" in s:
            drop.append(p)
            nxt = tops[i + 1] if i + 1 < len(tops) else None
            if nxt is not None and not _para_text(nxt, HP).strip() \
                    and not _has_secpr(nxt, HP) and nxt not in drop:
                drop.append(nxt)
    for p in drop:
        sec.remove(p)
    return len(drop)


def _heading_is_autonumbered(hdr, parapr_id: str) -> bool:
    """헤딩 paraPr 에 자동 번호(NUMBER/OUTLINE)가 걸려 있는지."""
    if hdr is None or parapr_id is None:
        return False
    for pp in hdr.iter():
        if C.xmlcompat.local_name(pp) == "paraPr" and pp.get("id") == parapr_id:
            for el in pp:
                if C.xmlcompat.local_name(el) == "heading":
                    return el.get("type") in ("NUMBER", "OUTLINE")
    return False


def _make_unnumbered_parapr(hdr, base_ppid: str, cache: dict) -> str:
    """헤딩 paraPr 를 복제해 **자동 번호만 끈** 새 paraPr id.

    별지(붙임) 안의 절 제목용이다. 본문 헤딩은 자동 번호라 별지까지 번호가
    이어져 5·6·7 로 붙는다. 별지의 '1. 작성요령' 은 그 문서 안의 번호이므로
    글자 그대로 두고, 자동 번호는 꺼서 본문 번호 흐름을 건드리지 않는다.
    """
    if hdr is None or base_ppid is None:
        return base_ppid
    if base_ppid in cache:
        return cache[base_ppid]
    HH = C.xmlcompat.hh_uri(hdr)
    para_props = hdr.find(f".//{{{HH}}}paraProperties")
    if para_props is None:
        return base_ppid
    base = None
    for pp in para_props.findall(f"{{{HH}}}paraPr"):
        if pp.get("id") == base_ppid:
            base = pp
            break
    if base is None:
        cache[base_ppid] = base_ppid
        return base_ppid
    new = deepcopy(base)
    new_id = max((int(e.get("id", "0")) for e in
                  para_props.findall(f"{{{HH}}}paraPr")), default=0) + 1
    new.set("id", str(new_id))
    for el in new:
        if _ln(el.tag) == "heading":
            el.set("type", "NONE")
            el.set("idRef", "0")
            el.set("level", "0")
    para_props.append(new)
    para_props.set("itemCnt", str(len(para_props.findall(f"{{{HH}}}paraPr"))))
    cache[base_ppid] = str(new_id)
    return str(new_id)


def _find_ref13_charpr(hdr, sec, HP, charmap) -> Optional[str]:
    """
    '*' 참고 단위용 13pt 한양중고딕 charPr id 탐색.
    (문서에서 실제 사용 중인 것 우선)
    """
    if hdr is None:
        return None
    # 한양중고딕 폰트 id
    jungodik_id = None
    for ff in hdr.iter():
        if C.xmlcompat.local_name(ff) == "fontface" and ff.get("lang") == "HANGUL":
            for f in ff:
                if "중고딕" in (f.get("face") or ""):
                    jungodik_id = f.get("id")
            break
    if jungodik_id is None:
        return None
    candidates = []
    for cp in hdr.iter():
        if C.xmlcompat.local_name(cp) != "charPr":
            continue
        if int(cp.get("height", "0")) != 1300:
            continue
        for el in cp:
            if C.xmlcompat.local_name(el) == "fontRef":
                if el.get("hangul") == jungodik_id:
                    candidates.append(cp.get("id"))
    if not candidates:
        return None
    # 문서에서 실제 참조 중인 것 우선
    used = {r.get("charPrIDRef") for r in sec.iter(f"{{{HP}}}run")}
    for cid in candidates:
        if cid in used:
            return cid
    return candidates[0]


_NUM_PREFIX = re.compile(r"^\s*(\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])[.)]\s*")

# 본문 내 표/이미지자리 위치 마커: '[표1]' '[이미지2]' '[그림1]' (0.2.2)
# 마커 줄 위치에 해당 tables/images 항목을 삽입한다. 마커 없는 항목은
# 기존처럼 본문 끝에 덧붙인다(하위호환).
_TBL_MARK = re.compile(r"^\[\s*표\s*(\d+)\s*\]$")
_IMG_MARK = re.compile(r"^\[\s*(?:이미지|그림)\s*(\d+)\s*\]$")

# 단위별 내어쓰기 폭(실측 pt) — "내어쓰기" 필드 값만 의미함.
# 여백-왼쪽(left)은 절대 건드리지 않고 프로토타입 문단의 기존 값을 그대로 둔다.
# 척도 변환(1pt=200, 글자크기의 1pt=100 과 다른 함정!)은 hwpx_core.units 가 단일 소스.
# ◦ 는 한글에서 "내어쓰기 38.6pt" 실측 → margin_hwpunit(38.6)=7720.
_HANG_PT = {"□": 30.7, "☐": 30.7, "◦": 38.6, "-": 36.5, "·": 36.5, "*": 33.8}
_HANG_BY_MARKER = {m: C.units.margin_hwpunit(pt) for m, pt in _HANG_PT.items()}
# 말머리('☐ (필요성) …')가 붙은 줄은 접힌 둘째 줄이 **여는 괄호 다음**에 맞도록
# 내어쓰기를 반각 괄호 폭만큼 더 준다 — 실측: 30.7pt → 37.68pt(+6.98pt).
_HANG_LABEL_EXTRA = C.units.margin_hwpunit(6.98)


def _make_keep_parapr(hdr, base_ppid: str, cache: dict) -> str:
    """기존 paraPr 를 복제해 `keepWithNext=1`(다음 문단과 함께)만 켠 새 paraPr 를
    header 에 추가하고 id 반환. base_ppid 단위로 캐시.

    쪽 경계에서 갈라지면 곤란한 자리 — 헤딩(다음 항목이 반드시 따라온다) · 표와
    이미지자리 바로 앞 항목 · 각주 설명(`* …`) 앞 문단 — 에만 켠다. 본문 ◦ 까지
    켜면 쪽 끝마다 큰 공백이 생긴다(08-15).
    """
    if base_ppid in cache:
        return cache[base_ppid]
    HH = C.xmlcompat.hh_uri(hdr)
    para_props = hdr.find(f".//{{{HH}}}paraProperties")
    base = next((pp for pp in para_props.findall(f"{{{HH}}}paraPr")
                 if pp.get("id") == base_ppid), None)
    if base is None:
        cache[base_ppid] = base_ppid
        return base_ppid
    new = deepcopy(base)
    new_id = max((int(e.get("id", "0")) for e in
                  para_props.findall(f"{{{HH}}}paraPr")), default=0) + 1
    new.set("id", str(new_id))
    touched = False
    for el in new.iter():          # switch/case 안의 breakSetting 까지 모두
        if C.xmlcompat.local_name(el) == "breakSetting":
            el.set("keepWithNext", "1")
            touched = True
    if not touched:                # 속성이 없는 양식이면 원본 유지(무음 실패 방지)
        cache[base_ppid] = base_ppid
        return base_ppid
    para_props.append(new)
    para_props.set("itemCnt", str(len(para_props.findall(f"{{{HH}}}paraPr"))))
    cache[base_ppid] = str(new_id)
    return str(new_id)


def _make_hanging_parapr(hdr, base_ppid: str, hang: int, cache: dict) -> str:
    """기존 paraPr 를 복제해 내어쓰기(intent=-hang)만 적용한 새 paraPr 를
    header 에 추가하고 id 반환. 여백-왼쪽(left)은 프로토타입 값 그대로 유지.
    (base_ppid, hang) 단위로 캐시."""
    key = (base_ppid, hang)
    if key in cache:
        return cache[key]
    HH = C.xmlcompat.hh_uri(hdr)
    para_props = hdr.find(f".//{{{HH}}}paraProperties")
    base = None
    for pp in para_props.findall(f"{{{HH}}}paraPr"):
        if pp.get("id") == base_ppid:
            base = pp
            break
    if base is None:
        cache[key] = base_ppid
        return base_ppid
    new = deepcopy(base)
    new_id = max((int(e.get("id", "0")) for e in
                  para_props.findall(f"{{{HH}}}paraPr")), default=0) + 1
    new.set("id", str(new_id))
    # switch/case 와 default 안의 margin 모두 갱신 — intent(내어쓰기)만 수정, left(여백) 유지
    for el in new.iter():
        if C.xmlcompat.local_name(el) == "margin":
            for child in el:
                if C.xmlcompat.local_name(child) == "intent":
                    child.set("value", str(-hang))
    para_props.append(new)
    para_props.set("itemCnt", str(len(para_props.findall(f"{{{HH}}}paraPr"))))
    cache[key] = str(new_id)
    return str(new_id)


def _make_smaller_charpr(hdr, base_cid: str, cache: dict, delta_pt: int = 2) -> str:
    """기존 charPr 를 복제해 글자 크기만 delta_pt 만큼 줄인 charPr 를 header 에
    추가하고 id 반환(글꼴·색·굵기는 그대로). base_cid 단위 캐시.

    문장 중간 부연 괄호를 본문보다 작게 쓰는 공공기관 관례용(실물 대조).
    """
    key = (base_cid, delta_pt)
    if key in cache:
        return cache[key]
    HH = C.xmlcompat.hh_uri(hdr)
    char_props = hdr.find(f".//{{{HH}}}charProperties")
    base = None
    for cp in char_props.findall(f"{{{HH}}}charPr"):
        if cp.get("id") == base_cid:
            base = cp
            break
    try:
        height = int(base.get("height"))
    except (AttributeError, TypeError, ValueError):
        cache[key] = base_cid
        return base_cid
    new = deepcopy(base)
    new.set("height", str(max(height - delta_pt * 100, 700)))
    new_id = max((int(e.get("id", "0")) for e in
                  char_props.findall(f"{{{HH}}}charPr")), default=0) + 1
    new.set("id", str(new_id))
    char_props.append(new)
    char_props.set("itemCnt", str(len(char_props.findall(f"{{{HH}}}charPr"))))
    cache[key] = str(new_id)
    return str(new_id)


def _make_bold_charpr(hdr, base_cid: str, cache: dict) -> str:
    """기존 charPr 를 복제해 <hh:bold/> 만 추가한 charPr id 반환(크기·글꼴 유지).

    각 단 첫 항목의 말머리 라벨('☐ (필요성) …')을 굵게 쓰는 관례용(실물 대조).
    OWPML 자식 순서상 bold 는 offset·italic 뒤, underline·strikeout 앞에 온다.
    """
    if base_cid in cache:
        return cache[base_cid]
    HH = C.xmlcompat.hh_uri(hdr)
    char_props = hdr.find(f".//{{{HH}}}charProperties")
    base = None
    for cp in char_props.findall(f"{{{HH}}}charPr"):
        if cp.get("id") == base_cid:
            base = cp
            break
    if base is None:
        cache[base_cid] = base_cid
        return base_cid
    if base.find(f"{{{HH}}}bold") is not None:
        cache[base_cid] = base_cid
        return base_cid
    new = deepcopy(base)
    before = ("fontRef", "ratio", "spacing", "relSz", "offset")
    pos = 0
    for i, child in enumerate(new):
        if C.xmlcompat.local_name(child) in before:
            pos = i + 1
    new.insert(pos, etree.SubElement(etree.Element("tmp"), f"{{{HH}}}bold"))
    new_id = max((int(e.get("id", "0")) for e in
                  char_props.findall(f"{{{HH}}}charPr")), default=0) + 1
    new.set("id", str(new_id))
    char_props.append(new)
    char_props.set("itemCnt", str(len(char_props.findall(f"{{{HH}}}charPr"))))
    cache[base_cid] = str(new_id)
    return str(new_id)


def _make_supscript_charpr(hdr, base_cid: str, cache: dict) -> str:
    """기존 charPr 를 복제해 <hh:supscript/> 를 더한 charPr id 반환(크기·글꼴 유지).

    낱말에 붙은 각주 별표(`단어*`)를 위첨자로 올린다(괄호 라벨 위첨자는 09-22 에 뗐다).
    자식 순서상 supscript 는 strikeout 뒤에 온다.
    """
    if base_cid in cache:
        return cache[base_cid]
    HH = C.xmlcompat.hh_uri(hdr)
    char_props = hdr.find(f".//{{{HH}}}charProperties")
    base = None
    for cp in char_props.findall(f"{{{HH}}}charPr"):
        if cp.get("id") == base_cid:
            base = cp
            break
    if base is None or base.find(f"{{{HH}}}supscript") is not None:
        cache[base_cid] = base_cid
        return base_cid
    new = deepcopy(base)
    sub = new.find(f"{{{HH}}}subscript")
    if sub is not None:
        new.remove(sub)
    etree.SubElement(new, f"{{{HH}}}supscript")
    new_id = max((int(e.get("id", "0")) for e in
                  char_props.findall(f"{{{HH}}}charPr")), default=0) + 1
    new.set("id", str(new_id))
    char_props.append(new)
    char_props.set("itemCnt", str(len(char_props.findall(f"{{{HH}}}charPr"))))
    cache[base_cid] = str(new_id)
    return str(new_id)


def _make_unbold_charpr(hdr, base_cid: str, cache: dict) -> str:
    """기존 charPr 를 복제해 <hh:bold/> 만 제거한 charPr 를 header 에 추가하고
    id 반환. 볼드가 아니면 원본 id 그대로. base_cid 단위 캐시.
    (표는 헤더행만 볼드 규칙 — 양식 그리드 프로토가 전 행 볼드라 여기서 벗김.)"""
    if base_cid in cache:
        return cache[base_cid]
    HH = C.xmlcompat.hh_uri(hdr)
    char_props = hdr.find(f".//{{{HH}}}charProperties")
    base = None
    for cp in char_props.findall(f"{{{HH}}}charPr"):
        if cp.get("id") == base_cid:
            base = cp
            break
    bold = base.find(f"{{{HH}}}bold") if base is not None else None
    if base is None or bold is None:
        cache[base_cid] = base_cid
        return base_cid
    new = deepcopy(base)
    new.remove(new.find(f"{{{HH}}}bold"))
    new_id = max((int(e.get("id", "0")) for e in
                  char_props.findall(f"{{{HH}}}charPr")), default=0) + 1
    new.set("id", str(new_id))
    char_props.append(new)
    char_props.set("itemCnt", str(len(char_props.findall(f"{{{HH}}}charPr"))))
    cache[base_cid] = str(new_id)
    return str(new_id)


def _make_align_parapr(hdr, base_ppid: str, horizontal, cache: dict,
                       line_spacing=None) -> str:
    """기존 paraPr 를 복제해 가로 정렬·줄 간격만 바꾼 판을 header 에 추가하고 id 반환.
    (base_ppid, horizontal, line_spacing) 단위 캐시.

    표 셀은 양식 프로토가 가운데 정렬이다. 그런데 셀 글자가 긴 열(비고·조치사항)
    은 가운데로 두면 줄마다 들쭉날쭉해 읽기 나쁘다 — 실무에서는 그런 열만 왼쪽으로
    돌린다. 네 값(LEFT·CENTER·RIGHT·JUSTIFY)은 모두 양식 header 에 이미 쓰이고
    있으므로 한/글이 받는 것이 확인된 값이다.
    """
    key = (base_ppid, horizontal, line_spacing)
    if key in cache:
        return cache[key]
    if horizontal is None and line_spacing is None:
        cache[key] = base_ppid
        return base_ppid
    HH = C.xmlcompat.hh_uri(hdr)
    para_props = hdr.find(f".//{{{HH}}}paraProperties")
    base = None
    for pp in para_props.findall(f"{{{HH}}}paraPr"):
        if pp.get("id") == base_ppid:
            base = pp
            break
    if base is None:
        cache[key] = base_ppid
        return base_ppid
    new = deepcopy(base)
    new_id = max((int(e.get("id", "0")) for e in
                  para_props.findall(f"{{{HH}}}paraPr")), default=0) + 1
    new.set("id", str(new_id))
    for el in new.iter():
        name = C.xmlcompat.local_name(el)
        if name == "align" and horizontal:
            el.set("horizontal", horizontal)
        elif name == "lineSpacing" and line_spacing:
            # 도해 칸은 정본이 120% 다 — 양식의 160% 를 그대로 두면 줄이 성겨진다
            el.set("type", "PERCENT")
            el.set("value", str(int(line_spacing)))
    para_props.append(new)
    para_props.set("itemCnt", str(len(para_props.findall(f"{{{HH}}}paraPr"))))
    cache[key] = str(new_id)
    return str(new_id)


def printable_width(sec) -> int:
    """이 문서의 판면 폭(HWPUNIT) — 용지 폭에서 좌우 여백과 제본을 뺀 값.

    도해는 본문 표(TOTAL_W=162.5mm)가 아니라 이 폭을 쓴다. 정본 체계도가 그렇고,
    붙임 표제도 같은 이유로 본문 표보다 넓다. 값을 지어내지 않고 문서에서 읽는다
    — 양식이 바뀌면 따라가야 하기 때문이다(등록 양식·외부 양식 모두 실측 48190).
    양식에서 못 읽으면 본문 표 폭으로 물러선다.
    """
    for el in sec.iter():
        if C.xmlcompat.local_name(el) != "pagePr":
            continue
        try:
            w = int(el.get("width"))
        except (TypeError, ValueError):
            continue
        for ch in el:
            if C.xmlcompat.local_name(ch) != "margin":
                continue
            try:
                w -= (int(ch.get("left", 0)) + int(ch.get("right", 0))
                      + int(ch.get("gutter", 0)))
            except (TypeError, ValueError):
                return C.tablespec.TOTAL_W
            return w if w > 0 else C.tablespec.TOTAL_W
    return C.tablespec.TOTAL_W


def _make_char_variant(hdr, base_cid: str, color, size_pt, cache: dict,
                       ratio_pct=None, spacing_pct=None) -> str:
    """기존 charPr 를 복제해 글자색·크기·장평만 바꾼 판을 만든다.

    도해에 필요해서 붙였다 — 태그(파란 바탕 흰 글자)와 상자 안 잔글씨는 본문
    13pt 검정으로는 정본과 다르게 보인다. 색은 charPr 의 textColor 속성이고
    (양식에 이미 #FFFFFF 가 쓰인다), 크기는 height 로 1pt = 100 HWPUNIT 이다
    (문단 여백과 척도가 다르다 — units.py 의 이중 척도 주석 참조).

    ratio_pct 는 장평(hh:ratio) — 글자 폭만 줄여 한 줄에 넣는 자리에 쓴다
    spacing_pct 는 자간(hh:spacing, 음수면 좁힘) — 글자 모양을 그대로 두고 사이만
    좁힌다. **정본 도해가 긴 줄을 넣는 방식이 이것이다**(장평은 전부 100 이고
    자간을 -6/-9/-12/-16 으로 준다). 글자를 눌러 뭉개지 않아 위계가 안 무너진다.
    단 【주관】 줄의 자간은 건드리지 않는다 — 양식이 -1/-3/-7 로 이미 잡아 둔
    값이라 더 줄이면 글자가 뭉개진다(그 줄은 장평으로 맞춘다).
    """
    key = (base_cid, color, size_pt, ratio_pct, spacing_pct)
    if key in cache:
        return cache[key]
    HH = C.xmlcompat.hh_uri(hdr)
    char_props = hdr.find(f".//{{{HH}}}charProperties")
    base = None
    if char_props is not None:
        for cp in char_props.findall(f"{{{HH}}}charPr"):
            if cp.get("id") == base_cid:
                base = cp
                break
    if base is None:
        cache[key] = base_cid
        return base_cid
    new = deepcopy(base)
    if color:
        new.set("textColor", color)
    if size_pt:
        new.set("height", str(int(round(float(size_pt)
                                       * C.units.HWPUNIT_PER_PT_CHAR))))
    if ratio_pct:
        # hh:ratio 는 글자 종류별 속성(hangul·latin·hanja…)을 다 갖는다 — 한 종류만
        # 줄이면 숫자·괄호가 그대로 남아 줄이 여전히 넘친다. 전부 같은 값으로 준다.
        for el in new:
            if C.xmlcompat.local_name(el) == "ratio":
                for k in list(el.attrib):
                    el.set(k, str(int(ratio_pct)))
    if spacing_pct:
        # ratio 와 같은 이유로 글자 종류별 속성을 전부 같은 값으로 준다
        for el in new:
            if C.xmlcompat.local_name(el) == "spacing":
                for k in list(el.attrib):
                    el.set(k, str(int(spacing_pct)))
    new_id = max((int(e.get("id", "0")) for e in
                  char_props.findall(f"{{{HH}}}charPr")), default=0) + 1
    new.set("id", str(new_id))
    char_props.append(new)
    char_props.set("itemCnt", str(len(char_props.findall(f"{{{HH}}}charPr"))))
    cache[key] = str(new_id)
    return str(new_id)


# 【주관】 줄 장평(%). 견본 담당자가 **셋이면** 줄이 판면(48188)을 넘어 날짜
# 꼬리('18)')가 둘째 줄에 떨어진다(08-18 실물 — 계산상 51089 로 2901 초과).
# 내용은 한 글자도 바꾸지 않는다: 담당자·직급·내선·날짜는 사람이 한/글에서 고치는
# 자리라 줄여서도 잘라서도 안 된다. 95 는 **사용자가 한/글에서 직접 맞춘 값**이다
# — 도구가 매 문서 재서 정하면 문서마다 장평이 흔들려 오히려 서식이 어긋난다.
OWNER_RATIO = 95


def fit_owner_line(sec, HP, hdr) -> bool:
    """【주관】 줄을 **장평 95% · 오른쪽 정렬**로 맞춘다. 손댔으면 True.

    자간은 손대지 않는다(양식이 -1/-3/-7 로 이미 잡아 뒀다). 오른쪽 정렬은
    날짜 꼬리를 판면 오른쪽 끝에 붙이려는 것이다 — 공문서 관례이고, 장평으로
    줄인 뒤 남는 자투리가 왼쪽이 아니라 【주관】 앞에 오게 한다.
    """
    target = None
    for p in sec.iter(f"{{{HP}}}p"):
        txt = "".join(t.text or "" for t in p.iter(f"{{{HP}}}t"))
        if "【주관】" in txt or "[주관]" in txt:
            target = p
            break
    if target is None:
        return False          # 【주관】 줄이 없는 양식 — 조용히 지나간다
    ccache, pcache = {}, {}
    changed = False
    for run in target.iter(f"{{{HP}}}run"):
        cid = run.get("charPrIDRef")
        if cid is None:
            continue
        new = _make_char_variant(hdr, cid, None, None, ccache,
                                 ratio_pct=OWNER_RATIO)
        if new != cid:
            run.set("charPrIDRef", new)
            changed = True
    ppid = target.get("paraPrIDRef")
    if ppid is not None:
        new = _make_align_parapr(hdr, ppid, "RIGHT", pcache)
        if new != ppid:
            target.set("paraPrIDRef", new)
            changed = True
    return changed


# 테두리 종류·굵기·색은 지어내지 않는다 — 정본 견본과 양식 header 에서 실제로
# 쓰이는 것만 받는다(08-18 실측: 두 파일 통틀어 이 넷뿐이다). 모르는 값을 넣으면
# 한/글이 조용히 무시하거나 수리한다.
BORDER_TYPES = ("NONE", "SOLID", "DASH", "DOUBLE_SLIM")
BORDER_SIDES = ("left", "right", "top", "bottom")
_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _parse_border(spec):
    """테두리 한 변의 지정 → (type, width, color). 못 알아들으면 사유 문자열.

    받는 꼴: 'SOLID' · 'DASH 0.3' · 'SOLID 0.12 #808080' · 순서 무관,
    또는 {"type": …, "width": …, "color": …}. 굵기는 mm, 색은 #RRGGBB.
    """
    if isinstance(spec, dict):
        t = str(spec.get("type", "SOLID"))
        w = spec.get("width", "0.12")
        c = str(spec.get("color", "#000000"))
    else:
        t, w, c = None, None, None
        for tok in str(spec).replace(",", " ").split():
            if tok.startswith("#"):
                c = tok
            elif tok.replace(".", "", 1).isdigit():
                w = tok
            elif tok.lower() == "mm":
                continue
            elif t is None:
                t = tok                      # 첫 낱말만 종류로 본다
            else:
                # 둘째 낱말까지 종류로 받으면 색 오타가 '모르는 종류'로 둔갑한다
                return (f"{tok!r} 를 모른다 — 굵기(mm)나 색(#RRGGBB)이어야 한다")
        if t is None:
            return f"종류가 없다({spec!r})"
        w, c = (w or "0.12"), (c or "#000000")
    t = t.strip().upper()
    if t not in BORDER_TYPES:
        return f"종류 {t!r} 를 모른다 — {' · '.join(BORDER_TYPES)} 중 하나"
    if not _COLOR_RE.match(c):
        return f"색 {c!r} 이 #RRGGBB 가 아니다"
    w = str(w).replace("mm", "").strip()
    try:
        w = "%g mm" % float(w)
    except ValueError:
        return f"굵기 {w!r} 가 숫자(mm)가 아니다"
    return (t, w, c)


def _make_styled_borderfill(hdr, base_bf: str, edges: dict, bg, cache: dict) -> str:
    """기존 borderFill 을 복제해 지정한 변의 테두리와 배경색만 바꾼 판을 만든다.

    도해(모눈 표)가 이걸로 선을 긋는다 — 위만 SOLID 면 가로선, 아래만 DASH 면
    점선이다. 정본 체계도가 딱 그 방식으로 그려져 있었다(08-18 견본: 병합 블록
    377개 중 글자가 든 것은 12개뿐이고 나머지는 전부 선과 여백이다).
    """
    key = ("style", base_bf, tuple(sorted(edges.items())), bg)
    if key in cache:
        return cache[key]
    HH = C.xmlcompat.hh_uri(hdr)
    HC = C.xmlcompat.hc_uri(hdr)
    fills = hdr.find(f".//{{{HH}}}borderFills")
    base = None
    if fills is not None:
        for bf in fills.findall(f"{{{HH}}}borderFill"):
            if bf.get("id") == base_bf:
                base = bf
                break
    if base is None:
        cache[key] = base_bf
        return base_bf
    new = deepcopy(base)
    for side, (t, w, c) in edges.items():
        el = new.find(f"{{{HH}}}{side}Border")
        if el is not None:
            el.attrib.update({"type": t, "width": w, "color": c})
    if bg is not None:
        brush = new.find(f"{{{HC}}}fillBrush")
        if bg == "":                      # 배경 지우기
            if brush is not None:
                new.remove(brush)
        else:
            if brush is None:
                # 스키마 순서상 diagonal 뒤가 자리다(정본 실측과 같은 배치)
                brush = etree.SubElement(new, f"{{{HC}}}fillBrush")
            win = brush.find(f"{{{HC}}}winBrush")
            if win is None:
                win = etree.SubElement(brush, f"{{{HC}}}winBrush")
            win.attrib.update({"faceColor": bg, "hatchColor": "#000000",
                               "alpha": "0"})
    new_id = max((int(e.get("id", "0")) for e in
                  fills.findall(f"{{{HH}}}borderFill")), default=0) + 1
    new.set("id", str(new_id))
    fills.append(new)
    fills.set("itemCnt", str(len(fills.findall(f"{{{HH}}}borderFill"))))
    cache[key] = str(new_id)
    return str(new_id)


def _make_merged_borderfill(hdr, base_bf: str, right_bf: str, bottom_bf: str,
                            cache: dict) -> str:
    """병합 셀의 테두리를 합성한 borderFill 을 header 에 추가하고 id 반환.

    양식 그리드는 **자리마다 테두리가 다르다** — 열 위치가 좌·우를, 행 위치가
    상·하를 정한다(첫 열은 왼쪽 NONE, 끝 열은 오른쪽 NONE — 표 바깥선은 표
    자신의 borderFill 이 그리므로 셀은 안쪽만 그린다).

    그래서 여러 칸을 덮는 셀은 **왼쪽·위는 시작 칸, 오른쪽은 끝 열, 아래는 끝 행**
    에서 가져와야 테두리가 닫힌다. 시작 칸 것만 쓰면 전체 폭 병합에서 오른쪽에
    안쪽 선이 남아 표 밖으로 삐져나온 것처럼 보인다.
    """
    key = ("merge", base_bf, right_bf, bottom_bf)
    if key in cache:
        return cache[key]
    if base_bf == right_bf == bottom_bf:
        cache[key] = base_bf
        return base_bf
    HH = C.xmlcompat.hh_uri(hdr)
    fills = hdr.find(f".//{{{HH}}}borderFills")
    if fills is None:
        cache[key] = base_bf
        return base_bf

    def _find(bid):
        for bf in fills.findall(f"{{{HH}}}borderFill"):
            if bf.get("id") == bid:
                return bf
        return None

    base = _find(base_bf)
    if base is None:
        cache[key] = base_bf
        return base_bf
    new = deepcopy(base)
    for tag, src_id in (("rightBorder", right_bf), ("bottomBorder", bottom_bf)):
        src = _find(src_id)
        if src is None:
            continue
        s_el, n_el = src.find(f"{{{HH}}}{tag}"), new.find(f"{{{HH}}}{tag}")
        if s_el is None or n_el is None:
            continue
        n_el.attrib.clear()
        n_el.attrib.update(s_el.attrib)
    new_id = max((int(e.get("id", "0")) for e in
                  fills.findall(f"{{{HH}}}borderFill")), default=0) + 1
    new.set("id", str(new_id))
    fills.append(new)
    fills.set("itemCnt", str(len(fills.findall(f"{{{HH}}}borderFill"))))
    cache[key] = str(new_id)
    return str(new_id)


# ── 동적 표 (양식 자기 그리드 복제 → N열×M행 리사이즈) ──────────────────────
# 문서 간 이식이 아니라 '같은 양식의 기존 4×3 그리드'를 복제하므로
# borderFill/charPr/paraPr ID 가 그대로 유효 → 한글 수리팝업 없음.
# 표 전체 너비 162.5mm 고정(실무 확인) — 본문폭보다 조금 좁게 잡아 좌우 여백을 준다.
# 1mm = 7200/25.4 HWPUNIT → 162.5mm = 46063.
# 표 규격은 hwpx_core.tablespec 이 단일 기준 — 모드 B(hwpx_full)와 같은 값을 써야
# 폴백이 작동하는 순간에도 같은 표가 나온다(08-15 감사에서 46063/47531 로 갈려 있었다).
# 근거·단위는 그 모듈 주석 참조. 아래는 기존 이름 유지를 위한 별칭이다.
TABLE_TOTAL_W = C.tablespec.TOTAL_W
TABLE_LEAD_SPACES = C.tablespec.LEAD_SPACES
TABLE_FIRST_W = C.tablespec.FIRST_W
TABLE_ROW_H = C.tablespec.ROW_H


def _ln(tag: str) -> str:
    """태그 문자열의 localname (파서 중립)."""
    return tag.rsplit("}", 1)[-1]


def _find_grid_proto(sec, HP):
    """섹션에서 2×2 이상 그리드 표를 감싼 <hp:p> 를 찾아 deepcopy 반환(없으면 None)."""
    for p in sec:
        if _ln(p.tag) != "p":
            continue
        tbl = next(iter(p.iter(f"{{{HP}}}tbl")), None)
        if tbl is None:
            continue
        if int(tbl.get("rowCnt", "0")) >= 2 and int(tbl.get("colCnt", "0")) >= 2:
            return deepcopy(p)
    return None


def _cell_set_text(tc, HP, text: str) -> None:
    """칸에 글자를 넣는다. 줄바꿈이 있으면 **문단을 그만큼 만든다**.

    도해의 상자는 정본에서 '병합한 한 칸 안의 여러 문단'이다(실측: 고영향 상자가
    50열×12행 병합 한 칸에 문단 7개). 줄마다 행을 따로 쓰면 줄 간격이 행 높이에
    묶여 원본보다 34% 성겨지고, 그 행을 공유하는 옆 상자까지 벌어진다.
    """
    nl = chr(10)
    if nl in (text or ""):
        _cell_set_lines(tc, HP, str(text).split(nl))
        return
    ts = list(tc.iter(f"{{{HP}}}t"))
    if not ts:
        # 빈 프로토 셀(<hp:t> 없음 — 양식 그리드 '비고'류 열)에 쓰면 유실되던 버그.
        # 기존 run(charPr 유지)에 <hp:t> 를 만들어 넣고, run 도 없으면 생성한다.
        para = next(iter(tc.iter(f"{{{HP}}}p")), None)
        if para is None:
            return
        run = next(iter(para.iter(f"{{{HP}}}run")), None)
        if run is None:
            run = etree.SubElement(para, f"{{{HP}}}run")
            run.set("charPrIDRef", "0")
        etree.SubElement(run, f"{{{HP}}}t").text = text
        return
    for i, t in enumerate(ts):
        t.text = text if i == 0 else ""


def _cell_set_lines(tc, HP, lines) -> None:
    """칸 안에 문단을 여러 개 만든다 — 첫 문단을 복제해 줄마다 하나씩."""
    sub = next((e for e in tc.iter() if _ln(e.tag) == "subList"), None)
    if sub is None:
        return
    paras = [e for e in sub if _ln(e.tag) == "p"]
    if not paras:
        return
    proto = deepcopy(paras[0])
    for extra in paras[1:]:
        sub.remove(extra)
    _cell_set_text(tc, HP, lines[0] if lines else "")
    first = paras[0]
    for i, line in enumerate(lines[1:], 1):
        p = deepcopy(proto)
        # 문단 id 는 문서 안에서 겹쳐도 한/글이 받아 준다(양식 자체가 그렇다).
        _clear_lineseg(p, HP)
        sub.insert(list(sub).index(first) + i, p)
        for t in list(p.iter(f"{{{HP}}}t")):
            t.text = ""
        ts = list(p.iter(f"{{{HP}}}t"))
        if ts:
            ts[0].text = line
        else:
            run = next(iter(p.iter(f"{{{HP}}}run")), None)
            if run is None:
                run = etree.SubElement(p, f"{{{HP}}}run")
                run.set("charPrIDRef", "0")
            etree.SubElement(run, f"{{{HP}}}t").text = line


def _build_table_p(proto_p, headers, rows, HP, uid: int,
                   hdr=None, unbold_cache=None,
                   col_ratios=None, cells=None, merges=None,
                   grid=None, row_heights=None, total_w=None,
                   align_cache=None, bf_cache=None, char_cache=None,
                   warnings=None):
    """proto_p(그리드 표를 감싼 <hp:p>) 를 복제해 N열×M행 표 문단을 만든다.
    전체너비 고정(TABLE_TOTAL_W), 첫 열 고정(TABLE_FIRST_W), 나머지 균등.

    col_ratios: 열 너비 비율(열 수만큼). 주면 첫 열 고정 대신 이 비율로 나눈다.
    cells: 셀별 서식 [{"r":행, "c":열, "align":"LEFT", "bold":True}, …].
        행은 헤더행 포함 0 부터. align 은 LEFT·CENTER·RIGHT·JUSTIFY.
        bold 를 주지 않으면 종전 규칙(헤더행만 볼드)이 그대로 간다.
        "color": "#FFFFFF" · "size": 9 — 글자색과 크기(pt).
        "ratio": 90 — 장평(%) · "spacing": -12 — 자간(%). 긴 줄은 크기를 줄이지
        말고 **자간**을 좁혀 넣는다 — 정본 도해가 그렇게 한다(장평은 전부 100).
        "line_spacing": 120 — 줄 간격(%). 도해는 기본이 정본과 같은 120 이다.
        "borders": {"top": "SOLID", "bottom": "DASH 0.3", "all": "NONE"} —
        변마다 'type [굵기mm] [#색]'. 'all' 은 네 변을 한꺼번에 깔고 개별 변이
        그 위를 덮는다. "bg": "#E1EAF6"(빈 값이면 배경 지우기).
    merges: 셀 병합 [{"r1":0,"c1":0,"r2":0,"c2":1}, …]. (r1,c1)=좌상단,
        (r2,c2)=우하단이고 둘 다 포함이다. 덮인 칸은 XML 에서 지운다 —
        남겨 두면 한/글이 표를 손상으로 보고 수리한다.
    grid: 도해 모드 {"rows": R, "cols": C}. 켜면 헤더행 개념이 없고(볼드 없음),
        칸 테두리가 기본으로 전부 꺼진 **빈 모눈**이 된다 — 거기에 cells 로
        선을 긋는다. 글자도 cells 의 "text" 로 넣는다(모눈은 대부분 빈 칸이라
        rows 로 다 적을 수 없다).
    row_heights: 행 높이 목록(mm, 행 수만큼). 생략하면 종전 고정 높이.
    total_w: 표 전체 너비. 도해는 판면 폭을 받는다(printable_width).
    ※ 표 **위에 얹는** 그림(`pics`)은 이 함수가 아니라 `_build_table_pics_p` 가
      별도 문단으로 만든다 — 같은 문단에 두면 표가 밀린다(그쪽 주석 참조).
    잘못된 값은 문서를 막지 않는다 — 그 항목만 무시하고 warnings 에 사유를 남긴다.
    """
    warn = warnings if warnings is not None else []
    q = lambda n: f"{{{HP}}}{n}"
    p = deepcopy(proto_p)
    tbl = next(iter(p.iter(q("tbl"))))
    trs = [tr for tr in tbl if _ln(tr.tag) == "tr"]
    proto_rows = [[tc for tc in tr if _ln(tc.tag) == "tc"] for tr in trs]
    R, Cc = len(proto_rows), len(proto_rows[0])

    # 프로토타입 4행 = 헤더(하단 이중선) / 첫데이터(상단 이중선) / 내부(얇은선) / 마지막(하단 굵은선)
    # 내부 행은 반드시 '행2'(순수 내부). '행1'(상단 이중선)은 헤더 바로 아래(r==1)만.
    def row_idx(r):
        if r == 0:
            return 0
        if r == M - 1:
            return R - 1
        if r == 1:
            return min(1, R - 1)
        return min(2, R - 1)

    def col_idx(c):
        if c == 0:
            return 0
        if c == N - 1:
            return Cc - 1
        return min(1, Cc - 1)

    def pick(r, c):
        return proto_rows[row_idx(r)][col_idx(c)]

    headers = [str(x) for x in (headers or [])]
    # 행 정규화: LLM 이 행을 배열 대신 문자열/스칼라로 줘도 유실 없이 수용
    data = []
    for row in (rows or []):
        if isinstance(row, (list, tuple)):
            data.append([str(x) for x in row])
        else:
            data.append([str(row)])
    # 열 수 = 헤더/데이터 중 최대 (헤더 생략 시 데이터 열 유실 방지)
    N = max(1, len(headers), *(len(r) for r in data)) if data else max(1, len(headers))
    M = 1 + len(data)

    # 도해 모드 — 크기를 grid 가 선언한다. 모눈은 칸이 수천 개라 rows 로는
    # 못 적는다(정본 체계도는 42×81=3402칸인데 글자가 든 것은 12칸뿐이었다).
    grid_mode = bool(grid)
    if grid_mode:
        g = grid if isinstance(grid, dict) else {}
        try:
            gr, gc = int(g.get("rows", 0) or 0), int(g.get("cols", 0) or 0)
        except (TypeError, ValueError):
            warn.append(f"[표] grid 의 rows·cols 가 정수가 아니다 — 무시({grid!r})")
            gr = gc = 0
        if gr > 0:
            M = gr
        if gc > 0:
            N = gc
        if gr <= 0 or gc <= 0:
            warn.append(f"[표] grid 에 rows·cols 가 없어 헤더·행에서 크기를 잡았다 "
                        f"({M}행 {N}열)")

    # 모드 B 와 같은 계산(단일 기준). 비율이 틀렸으면 기본 배분으로 떨어뜨린다 —
    # 표를 통째로 빼는 것보다 낫고, 사유는 warnings 로 올라간다.
    floor = C.tablespec.GRID_MIN_COL_W if grid_mode else None
    # 도해는 본문 표 폭이 아니라 판면 폭을 쓴다 — 정본 체계도가 그렇다.
    span_w = int(total_w) if (grid_mode and total_w) else None
    if grid_mode and col_ratios is None:
        col_ratios = [1] * N                 # 모눈 기본은 균등 분할
    # 첫 열은 항목명에 맞춰 넓힌다 — 고정 7자면 `야간 순찰(회/월)` 이 두 줄로
    # 접혀 행이 두 배로 높아진다(08-18 실물). 계산은 tablespec 이 한다(단일 기준).
    firsts = None if grid_mode else (
        ([headers[0]] if headers else []) + [r[0] for r in data if r])
    try:
        widths = C.tablespec.col_widths(N, col_ratios, floor, span_w, firsts)
    except ValueError as e:
        warn.append(f"[표] 열 비율을 무시했다 — {e}")
        widths = C.tablespec.col_widths(N, None, None, span_w, firsts)

    # 행 높이 — 주면 그대로, 안 주면 종전 고정 높이.
    heights = [TABLE_ROW_H] * M
    if row_heights is not None:
        vals, bad = [], None
        for v in (row_heights if isinstance(row_heights, (list, tuple)) else []):
            try:
                h = C.tablespec.mm(v)
            except (TypeError, ValueError):
                bad = f"{v!r} 가 숫자(mm)가 아니다"
                break
            if h < C.tablespec.MIN_ROW_H:
                bad = f"{v}mm 는 너무 낮다(최소 {C.tablespec.MIN_ROW_H} HWPUNIT)"
                break
            vals.append(h)
        if bad:
            warn.append(f"[표] 행 높이를 무시했다 — {bad}")
        elif len(vals) != M:
            warn.append(f"[표] 행 높이 개수({len(vals)})가 행 수({M})와 다르다 — 무시")
        else:
            heights = vals

    # 칸 안여백 — 한/글의 최소 열 너비가 `여백×2 + 283` 이라, 모눈이 촘촘하면
    # 정본 값(1mm)을 그대로 쓸 수 없다. 가장 좁은 열이 견디는 만큼으로 낮춘다.
    grid_margin = C.tablespec.GRID_CELL_MARGIN
    if grid_mode and widths:
        room = (min(widths) - C.tablespec.GRID_MIN_CONTENT) // 2
        grid_margin = max(0, min(grid_margin, room))

    # 셀별 서식 색인. r/c 대신 row/col 로 오는 경우도 받는다(Agent 가 흔히 낸다).
    style_at = {}
    for cs in (cells or []):
        if not isinstance(cs, dict):
            continue
        r_, c_ = cs.get("r", cs.get("row")), cs.get("c", cs.get("col"))
        bad_rc = (isinstance(r_, bool) or isinstance(c_, bool)
                  or not isinstance(r_, int) or not isinstance(c_, int))
        if bad_rc:
            warn.append(f"[표] 셀 서식의 행·열이 정수가 아니다 — 무시({cs})")
            continue
        if not (0 <= r_ < M and 0 <= c_ < N):
            warn.append(f"[표] 셀 서식 ({r_},{c_}) 가 표 범위(행 {M}·열 {N}) 밖이다 — 무시")
            continue
        style_at[(r_, c_)] = cs

    # 병합 파싱. 덮인 칸을 지우는 작업이라 검증이 헐거우면 손상 파일이 된다 —
    # 범위·순서·겹침을 모두 본 뒤 통과한 것만 쓴다(겹치면 앵커가 이미 지워진
    # 칸일 수 있다). writer 의 merge_cells 와 같은 잣대다.
    spans, covered = {}, {}
    for mg in (merges or []):
        if not isinstance(mg, dict):
            continue
        try:
            r1, c1 = int(mg["r1"]), int(mg["c1"])
            r2, c2 = int(mg["r2"]), int(mg["c2"])
        except (KeyError, TypeError, ValueError):
            warn.append(f"[표] 병합에 r1·c1·r2·c2 가 온전하지 않다 — 무시({mg})")
            continue
        if r1 > r2 or c1 > c2:
            r1, r2 = min(r1, r2), max(r1, r2)
            c1, c2 = min(c1, c2), max(c1, c2)
        if not (0 <= r1 and r2 < M and 0 <= c1 and c2 < N):
            warn.append(f"[표] 병합 ({r1},{c1})-({r2},{c2}) 가 표 범위"
                        f"(행 {M}·열 {N}) 밖이다 — 무시")
            continue
        if r1 == r2 and c1 == c2:
            warn.append(f"[표] 병합 ({r1},{c1})-({r2},{c2}) 가 한 칸뿐이다 — 무시")
            continue
        taken = list(covered) + list(spans)
        hit = [k for k in taken if r1 <= k[0] <= r2 and c1 <= k[1] <= c2]
        if hit:
            warn.append(f"[표] 병합 ({r1},{c1})-({r2},{c2}) 가 앞선 병합과 겹친다 — 무시")
            continue
        spans[(r1, c1)] = (r2 - r1 + 1, c2 - c1 + 1)
        for rr in range(r1, r2 + 1):
            for cc in range(c1, c2 + 1):
                if (rr, cc) != (r1, c1):
                    covered[(rr, cc)] = (r1, c1)

    for tr in trs:
        tbl.remove(tr)
    for r in range(M):
        tr = etree.SubElement(tbl, q("tr"))
        for c in range(N):
            if (r, c) in covered:
                # 덮인 칸은 아예 쓰지 않는다 — 남겨 두면 한/글이 표를 손상으로
                # 보고 수리한다(행 커버리지가 열 수와 안 맞기 때문).
                st_lost = style_at.get((r, c)) or {}
                if "text" in st_lost:
                    lost = str(st_lost["text"])
                elif grid_mode:
                    lost = ""
                elif r == 0:
                    lost = headers[c] if c < len(headers) else ""
                elif r - 1 < len(data):
                    lost = data[r - 1][c] if c < len(data[r - 1]) else ""
                else:
                    lost = ""
                if lost.strip():
                    a = covered[(r, c)]
                    warn.append(f"[표] 병합에 덮인 칸 ({r},{c}) 의 글자 {lost[:12]!r} "
                                f"를 버렸다 — 앵커 ({a[0]},{a[1]}) 에 적을 것")
                continue
            rs, cs_ = spans.get((r, c), (1, 1))
            tc = deepcopy(pick(r, c))
            next(iter(tc.iter(q("cellAddr")))).attrib.update(
                {"colAddr": str(c), "rowAddr": str(r)})
            next(iter(tc.iter(q("cellSpan")))).attrib.update(
                {"colSpan": str(cs_), "rowSpan": str(rs)})
            # 병합 앵커는 덮은 칸들의 폭·높이를 합쳐 갖는다(정본 실측과 같은 방식).
            next(iter(tc.iter(q("cellSz")))).attrib.update(
                {"width": str(sum(widths[c:c + cs_])),
                 "height": str(sum(heights[r:r + rs]))})
            if grid_mode:
                # 칸 안여백을 명시한다 — 기본값(-1)이면 한/글이 자기 기본 여백을
                # 써서 열마다 최소 폭이 잡히고 모눈이 지면 밖까지 늘어난다.
                mg = str(grid_margin)
                tc.set("hasMargin", "1")
                for cm in tc.iter(q("cellMargin")):
                    cm.attrib.update({"left": mg, "right": mg,
                                      "top": mg, "bottom": mg})
            if (rs, cs_) != (1, 1) and hdr is not None and bf_cache is not None:
                tc.set("borderFillIDRef", _make_merged_borderfill(
                    hdr, tc.get("borderFillIDRef"),
                    pick(r, c + cs_ - 1).get("borderFillIDRef"),
                    pick(r + rs - 1, c).get("borderFillIDRef"), bf_cache))
            st = style_at.get((r, c))
            if grid_mode:
                txt = ""                      # 모눈은 빈 칸이 기본이다
            elif r == 0:
                txt = headers[c] if c < len(headers) else ""
            elif r - 1 < len(data):
                row = data[r - 1]
                txt = row[c] if c < len(row) else ""
            else:
                txt = ""
            # lines 를 주면 **한 칸 안에 문단 여러 개**를 만들고 줄마다 서식을 건다.
            # 정본 도해의 상자가 그 구조다(병합 한 칸 + 문단 7개, 제목 10pt·날짜 8pt).
            line_specs = st.get("lines") if isinstance(st, dict) else None
            if line_specs is not None and not isinstance(line_specs, list):
                warn.append(f"[표] 셀 ({r},{c}) 의 lines 는 목록이어야 한다 — 무시")
                line_specs = None
            if line_specs:
                _cell_set_lines(tc, HP, [str((x or {}).get("text", ""))
                                         for x in line_specs])
                txt = " ".join(str((x or {}).get("text", "")) for x in line_specs)
            else:
                if st is not None and "text" in st:
                    txt = str(st["text"])     # 칸에 직접 적은 글자가 이긴다
                _cell_set_text(tc, HP, txt)
            # 서식 적용 대상 — lines 를 줬으면 문단마다, 아니면 칸 전체에 한 벌.
            base_st = dict(st or {})
            if line_specs:
                sub_el = next((e for e in tc.iter()
                               if _ln(e.tag) == "subList"), None)
                paras = ([e for e in sub_el if _ln(e.tag) == "p"]
                         if sub_el is not None else [])
                targets = []
                for pa, sp in zip(paras, line_specs):
                    merged = dict(base_st)
                    merged.pop("lines", None)
                    merged.update(sp or {})
                    targets.append((pa, merged, str((sp or {}).get("text", ""))))
            else:
                targets = [(tc, base_st, txt)]

            for tgt, tst, ttxt in targets:
                # 표는 헤더행만 볼드 — 데이터행은 벗긴다(프로토가 전 행 볼드).
                # 도해에는 헤더 개념이 없으므로 기본은 볼드 없음이다.
                default_bold = (r == 0) and not grid_mode
                want_bold = tst["bold"] if "bold" in tst else default_bold
                if not want_bold and hdr is not None and unbold_cache is not None:
                    for run in tgt.iter(q("run")):
                        run.set("charPrIDRef",
                                _make_unbold_charpr(hdr, run.get("charPrIDRef"),
                                                    unbold_cache))
                # 도해의 빈 칸은 아주 작은 글꼴로 낮춘다 — 한/글이 칸마다 글꼴 한
                # 자 자리를 최소 너비로 잡아, 13pt 를 물려받으면 모눈이 지면 밖까지
                # 늘어난다(tablespec.GRID_EMPTY_PT 주석 참조).
                if grid_mode and not ttxt.strip() and "size" not in tst:
                    tst["size"] = C.tablespec.GRID_EMPTY_PT
                col = str(tst["color"]).strip() if tst.get("color") else None
                if col is not None and not _COLOR_RE.match(col):
                    warn.append(f"[표] 셀 ({r},{c}) 글자색 {tst['color']!r} 이 "
                                f"#RRGGBB 가 아니다 — 무시")
                    col = None
                pt = tst.get("size")
                if pt is not None:
                    try:
                        pt = float(pt)
                        # 1pt 까지 받는다 — 도해의 빈 칸이 실제로 그 크기를 쓴다.
                        if not (1 <= pt <= 72):
                            raise ValueError
                    except (TypeError, ValueError):
                        warn.append(f"[표] 셀 ({r},{c}) 글자 크기 {tst['size']!r} 이 "
                                    f"1~72pt 가 아니다 — 무시")
                        pt = None
                # 장평 — 긴 줄은 글자 크기를 줄이지 말고 **폭만** 줄여 넣는다.
                # 정본 도해는 장평 대신 자간을 줄인다(아래 spacing). 크기를
                # 줄이면 한 도해 안에서 글자가 널뛰어 위계가 무너진다.
                ratio = tst.get("ratio")
                if ratio is not None:
                    try:
                        ratio = int(ratio)
                        if not (50 <= ratio <= 200):
                            raise ValueError
                    except (TypeError, ValueError):
                        warn.append(f"[표] 셀 ({r},{c}) 장평 {tst['ratio']!r} 이 "
                                    f"50~200(%) 이 아니다 — 무시")
                        ratio = None
                spac = tst.get("spacing")
                if spac is not None:
                    try:
                        spac = int(spac)
                        if not (-50 <= spac <= 50):
                            raise ValueError
                    except (TypeError, ValueError):
                        warn.append(f"[표] 셀 ({r},{c}) 자간 {tst['spacing']!r} 이 "
                                    f"-50~50(%) 이 아니다 — 무시")
                        spac = None
                if (col or pt or ratio or spac) and hdr is not None                         and char_cache is not None:
                    for run in tgt.iter(q("run")):
                        run.set("charPrIDRef", _make_char_variant(
                            hdr, run.get("charPrIDRef"), col, pt, char_cache,
                            ratio_pct=ratio, spacing_pct=spac))
                # 정렬·줄 간격은 문단의 paraPr 를 갈아 끼운다.
                hz = None
                if tst.get("align"):
                    cand = str(tst["align"]).strip().upper()
                    if cand in ("LEFT", "CENTER", "RIGHT", "JUSTIFY"):
                        hz = cand
                    else:
                        warn.append(f"[표] 셀 ({r},{c}) 정렬값 {tst['align']!r} 을 "
                                    f"모른다 — LEFT·CENTER·RIGHT·JUSTIFY 중 하나")
                ls = C.tablespec.GRID_LINE_SPACING if grid_mode else None
                if tst.get("line_spacing") is not None:
                    try:
                        v = int(tst["line_spacing"])
                        if not (50 <= v <= 300):
                            raise ValueError
                        ls = v
                    except (TypeError, ValueError):
                        warn.append(f"[표] 셀 ({r},{c}) 줄 간격 "
                                    f"{tst['line_spacing']!r} 이 50~300(%) 이 "
                                    f"아니다 — 무시")
                if (hz or ls) and hdr is not None and align_cache is not None:
                    if _ln(tgt.tag) == "p":
                        tgt.set("paraPrIDRef",
                                _make_align_parapr(hdr, tgt.get("paraPrIDRef"),
                                                   hz, align_cache, ls))
                    else:
                        for cp in tgt.iter(q("p")):
                            cp.set("paraPrIDRef",
                                   _make_align_parapr(hdr, cp.get("paraPrIDRef"),
                                                      hz, align_cache, ls))
            st = base_st or None
            # 칸 테두리·배경 — 도해(모눈 표)는 이걸로 선을 긋는다.
            st_b = st or {}
            if (grid_mode or st_b.get("borders") is not None or "bg" in st_b)                     and hdr is not None and bf_cache is not None:
                edges, bg = {}, None
                if grid_mode:
                    # 빈 모눈에서 시작한다 — 안 그리면 내용표 테두리가 비쳐
                    # 선을 그은 자리와 안 그은 자리가 구분되지 않는다. 배경도
                    # 함께 지운다(양식 헤더행이 회색이라 첫 줄에 띠가 남았다).
                    edges = {sd: ("NONE", "0.1 mm", "#000000") for sd in BORDER_SIDES}
                    bg = ""
                spec = st_b.get("borders")
                if spec is None:
                    spec = {}
                elif not isinstance(spec, dict):
                    warn.append(f"[표] 셀 ({r},{c}) 의 borders 는 "
                                f"{{'top': 'SOLID', …}} 꼴이어야 한다 — 무시")
                    spec = {}
                # 'all' 은 네 변을 한꺼번에 — 개별 변 지정이 그 위를 덮는다
                keys = sorted(spec, key=lambda k: str(k).lower() != "all")
                for k in keys:
                    side = str(k).strip().lower()
                    if side == "all":
                        sides = BORDER_SIDES
                    elif side in BORDER_SIDES:
                        sides = (side,)
                    else:
                        warn.append(f"[표] 셀 ({r},{c}) 테두리 변 {k!r} 을 모른다 "
                                    f"— {' · '.join(BORDER_SIDES)} · all")
                        continue
                    got = _parse_border(spec[k])
                    if isinstance(got, str):
                        warn.append(f"[표] 셀 ({r},{c}) {side} 테두리 — {got}")
                        continue
                    for sd in sides:
                        edges[sd] = got
                if "bg" in st_b:
                    v = st_b["bg"]
                    text = "" if v is None else str(v).strip()
                    if text.lower() in ("", "none"):
                        bg = ""                       # 배경 지우기
                    elif _COLOR_RE.match(text):
                        bg = text.upper()
                    else:
                        warn.append(f"[표] 셀 ({r},{c}) 배경색 {v!r} 이 "
                                    f"#RRGGBB 가 아니다 — 무시")
                if edges or bg is not None:
                    tc.set("borderFillIDRef", _make_styled_borderfill(
                        hdr, tc.get("borderFillIDRef"), edges, bg, bf_cache))
            # 줄 배치 캐시 제거 — 긴 셀 텍스트가 2줄로 넘어갈 때 이전 캐시 기준
            # 겹침 방지(본문 fill_body 와 동일한 검증된 방식, 한글이 열 때 재계산)
            for cp in tc.iter(q("p")):
                _clear_lineseg(cp, HP)
            tr.append(tc)

    tbl.set("rowCnt", str(M))
    tbl.set("colCnt", str(N))
    tbl.set("id", str(uid))
    # 표 앞 들여쓰기 — 프로토타입은 공백 1칸이라 규정 칸수로 맞춘다(실무 확인).
    # 공백과 표가 같은 run 안에 있으므로 tbl 앞에 오는 t 만 고른다.
    for run in p.findall(q("run")):
        done = False
        for ch in run:
            if _ln(ch.tag) == "tbl":
                done = True
                break
            if _ln(ch.tag) == "t" and (ch.text or "").strip() == "":
                # 도해는 판면 폭을 꽉 쓰므로 앞 들여쓰기를 붙이지 않는다 —
                # 붙이면 그만큼 오른쪽으로 밀려 판면 밖으로 나간다.
                ch.text = "" if grid_mode else " " * TABLE_LEAD_SPACES
        if done:
            break
    total_h = sum(heights)
    for ch in tbl:
        if _ln(ch.tag) == "sz":
            ch.attrib.update({"width": str(sum(widths)),
                              "height": str(total_h)})
            break
    # 문단 자체 lineseg(직속) 높이도 표 높이에 맞춤
    for ch in p:
        if _ln(ch.tag) == "linesegarray":
            for ls in ch:
                ls.attrib.update({"vertsize": str(total_h),
                                  "textheight": str(total_h)})
    return p


# 그림을 매다는 빈 문단이 스스로 차지하는 높이(pt). 이 문단의 위가 그림의 세로
# 원점이고 표는 그보다 한 줄 **아래**에서 시작하므로, 호출부가 준 y_mm(표 윗변
# 기준)에 이만큼을 더해야 자리가 맞는다. 실측: 그림 문단을 넣기 전 표 안 글자
# y=225.5 → 넣은 뒤 246.3(차이 20.8), 같은 렌더에서 y_mm=0 인 그림이 224.9 에
# 앉았다 = 표 윗변보다 20.8pt 위다(2026-08-19).
TBL_PIC_ANCHOR_PT = 20.8


def _build_table_pics_p(p, HP, pics, embed, warn, uid: int):
    """표에 얹을 그림만 든 문단을 만든다 — **표 문단 바로 앞**에 넣을 것.

    ⚠️ 정본은 그림을 표와 **같은 run 안, 표 앞**에 둔다(실측: 한 run 의 자식이
    `pic × 11 · rect × 2 · tbl · t`). 그런데 우리 양식에서 그렇게 하면 그림이
    하나만 있어도 **표가 통째로 (+88.1pt, +20.8pt) 밀린다** — 그림의 위치·크기·
    개수와도, 표 크기와도 무관한 상수다. 재저장시켜 보면 한/글은 우리가 쓴 대로
    읽어 두고(속성이 그대로 돌아온다) 지면에서만 옮긴다.

    바꿔 보고 잰 것(2026-08-19, PDF 좌표):
        zOrder 낮추기 · offset/transMatrix 를 정본처럼 · textWrap BEHIND_TEXT ·
        effects 제거 · 표 폭 줄이기(48188·47000) · 별도 run   → **전부 밀린다**
        표 뒤로 옮기기 · **앞 문단에 매달기**                  → 밀리지 않는다
    표 뒤로 옮기면 세로 원점이 판면 위로 튀어 표를 따라다니지 않는다(그림은 표가
    움직여도 제자리에 남는다). 앞 문단에 매달면 원점이 그 문단의 위라 **표와 함께
    움직인다** — 그래서 이쪽을 쓴다.
    """
    pics = [x for x in (pics or []) if x]
    if not pics:
        return None
    if embed is None:
        warn.append("[표] 얹을 그림을 넣을 수 없다(임베드 경로 없음) — 그림 없이 그린다")
        return None
    anchor = deepcopy(p)
    run = None
    for r in anchor.iter(f"{{{HP}}}run"):
        if any(_ln(ch.tag) == "tbl" for ch in r):
            run = r
            break
    if run is None:
        warn.append("[표] 표를 담은 run 을 못 찾아 그림을 얹지 못했다")
        return None
    # 표와 글자를 걷어내 그림만 남긴다 — 표가 둘이 되면 안 된다
    for ch in list(run):
        run.remove(ch)
    for ch in list(anchor):
        if _ln(ch.tag) not in ("run", "linesegarray"):
            anchor.remove(ch)
    _clear_lineseg(anchor, HP)

    added = 0
    for i, spec in enumerate(pics):
        try:
            data, fmt = C.bindata.load_bytes(spec)
            px_w, px_h = C.bindata.image_size(data)
            item_id = embed(data, fmt)
            w, h = C.bindata.fit_box(
                px_w, px_h,
                C.tablespec.mm(spec["width_mm"]) if spec.get("width_mm") else 0,
                C.tablespec.mm(spec["height_mm"]) if spec.get("height_mm") else 0)
            # y_mm 은 **표 윗변** 기준으로 받는다 — 원점인 이 문단의 위는 표보다
            # 한 줄 높으므로 그만큼 더 내려 준다.
            y = (float(spec.get("y_mm") or 0) / 25.4 * 72 + TBL_PIC_ANCHOR_PT)
            xml = C.bindata.pic_xml(
                item_id, w, h, px_w=px_w, px_h=px_h, treat_as_char=False,
                horz_offset=C.tablespec.mm(spec.get("x_mm") or 0),
                vert_offset=int(round(y / 72 * 7200)),
                obj_id=uid + 1 + i, z_order=100 + i)
        except Exception as e:                       # noqa — 사유를 남기고 넘어간다
            warn.append(f"[표] {i + 1}번째 얹을 그림 실패: {e}")
            continue
        run.append(etree.fromstring(xml))
        added += 1
    return anchor if added else None


# ── 붙임 별지 (본문 뒤에 붙는 상세자료) ──────────────────────────────────
# 실무에서 보고서는 본문 1~3쪽으로 끊고 상세자료는 뒤로 뺀다. 그 별지가 붙임이다.
# 정본(08-18 요청서 견본) 실측 구조:
#   본문 끝  `붙임  1. 제목.` 목록(둘째 줄부터 6칸) + 마지막에 `끝.`
#   별지     쪽을 새로 시작하고 1행 3열 표제([붙임 N] 상자 · 빈칸 · 제목)로 연다
# 그 견본에서 쪽 나눔이 명시된 곳은 넷 중 하나뿐이었다 — 나머지는 앞 내용이 길어
# **우연히** 넘어간 것이라, 본문이 몇 줄만 줄어도 표제가 앞쪽 하단에 남는다.
# 여기서는 표제마다 쪽 나눔을 걸어 우연에 기대지 않는다.
_ATT_MARK = re.compile(r"^\[붙임\s*(\d{1,2})\]$")
_ATTLIST_MARK = re.compile(r"^\[붙임목록\]$")


def _find_attach_proto(sec, HP):
    """양식에서 붙임 표제 견본(첫 칸이 '붙임' 인 1행 3열 표)을 찾아 deepcopy.

    표(grid)와 같은 방식이다 — 폭·테두리·정렬을 코드로 지어내면 정본과 어긋난다
    (실제로 지어내 봤더니 표제가 가운데로 몰렸다). 양식에 견본이 없으면 None 을
    돌려주고 호출부가 사유를 남긴다.
    """
    for p in sec:
        if C.xmlcompat.local_name(p) != "p":
            continue
        tbls = [e for e in p.iter() if C.xmlcompat.local_name(e) == "tbl"]
        if not tbls or tbls[0].get("colCnt") != "3" or tbls[0].get("rowCnt") != "1":
            continue
        cells = [e for e in tbls[0].iter() if C.xmlcompat.local_name(e) == "tc"]
        if not cells:
            continue
        first = "".join(x.text or "" for x in cells[0].iter()
                        if C.xmlcompat.local_name(x) == "t").strip()
        if first.startswith("붙임"):
            return deepcopy(p)
    return None


def attach_list_lines(titles) -> List[str]:
    """본문 끝에 붙는 붙임 목록 줄. 마지막 줄 끝에 '끝.' 을 단다.

    하나면 번호를 매기지 않는다(`붙임  제목 1부.  끝.`) — 실무 관례다.
    """
    titles = [str(t).strip() for t in (titles or []) if str(t).strip()]
    if not titles:
        return []
    pad = " " * C.tablespec.ATTACH_LIST_INDENT
    if len(titles) == 1:
        return [f"붙임  {titles[0]} 1부.  끝."]
    out = []
    for i, t in enumerate(titles, 1):
        head = "붙임  " if i == 1 else pad
        tail = "  끝." if i == len(titles) else ""
        out.append(f"{head}{i}. {t}.{tail}")
    return out


def _build_attach_caption_p(proto_p, HP, uid: int, no: int, title: str):
    """붙임 표제 문단 — 견본을 복제해 두 칸의 글자만 바꾼다."""
    q = lambda t: f"{{{HP}}}{t}"                                   # noqa: E731
    p = deepcopy(proto_p)
    tbls = [e for e in p.iter() if _ln(e.tag) == "tbl"]
    if not tbls:
        return None
    tbls[0].set("id", str(uid))
    cells = [e for e in tbls[0].iter() if _ln(e.tag) == "tc"]
    if len(cells) < 3:
        return None
    for tc, txt in zip(cells, (f"붙임 {no}", "", f" {title}")):
        _cell_set_text(tc, HP, txt)
        for cp in tc.iter(q("p")):
            _clear_lineseg(cp, HP)
    # 별지는 쪽을 새로 연다 — 정본 견본은 넷 중 하나에만 쪽 나눔이 있었고,
    # 나머지는 앞 내용이 길어 **우연히** 넘어간 것이라 본문이 줄면 무너진다.
    p.set("pageBreak", "1")
    return p


# ── 이미지 자리 (insert_image.hwpx 실측 치수, 셀은 양식 자기 그리드에서 복제) ──
IMG_TOTAL_W = TABLE_TOTAL_W   # 이미지자리 너비 = 표 표준(같은 문서에서 좌우가 맞아야 한다)
# **17865 → 13000** (178.65pt → 130pt · 63mm → 46mm). 옛 값은 그림 블록
#   (칸 178 + 캡션 24 = 202pt)이 A4 본문 높이(≈672pt)의 **30%** 였다. 한 쪽에
#   그림이 하나면 지면의 3분의 1을 빈 상자가 먹는다.
#   ⚠️쪽 넘김의 두 번째 원인이기도 했다 — 그림 앞 항목을 안 묶게 고친 뒤에도
#     1쪽에 남은 자리가 176pt 인데 블록이 202pt 라 **26pt 차이로** 못 들어가
#     31% 가 비었다(실측 PDF). 130pt 면 블록이 154pt 라 들어간다.
#   ⚠️`insert_image.hwpx` 실측 치수에서 온 값이라 바꾸면 **그 견본과는 달라진다.**
#     그림을 실제로 넣을 때의 여백(IMG_PAD_*)은 그대로라 안쪽 정렬은 유지된다.
IMG_CELL_H = 13000      # 이미지칸 높이 (130pt · 본문의 약 1/5)
IMG_CAPTION_H = 2385    # 캡션칸 높이
IMG_PLACEHOLDER = "<이미지 삽입>"
# 그림을 실제로 넣을 때 칸 안에서 뺄 여백(HWPUNIT). 양식 칸의 안여백 실측치다 —
# 좌우 1100 은 tablespec.CELL_PAD(첫 열 7자에서 역산한 값)와 같은 기준이고,
# 위아래 566 = 283×2 는 도해에서 쓰던 칸 안여백 몫이다. 이 값으로 넣은 그림이
# 칸 테두리 안에 들어오는 것을 PDF 좌표로 확인했다(아래 IMG_FIT 주석).
IMG_PAD_W = 1100
IMG_PAD_H = 566


def _find_none_borderfill(hdr) -> Optional[str]:
    """header 에서 사방 NONE(무테두리) borderFill id 를 찾는다."""
    if hdr is None:
        return None
    for bf in hdr.iter(f"{{{C.HH}}}borderFill"):
        types = [b.get("type") for b in bf
                 if _ln(b.tag) in ("leftBorder", "rightBorder",
                                   "topBorder", "bottomBorder")]
        if types and all(t == "NONE" for t in types):
            return bf.get("id")
    return None


def _cell_set_pic(tc, HP, pic_xml: str) -> None:
    """칸의 첫 문단을 그림 하나로 바꾼다 — 글자를 지우고 run 안에 hp:pic 을 넣는다.

    자리표('<이미지 삽입>')를 지우지 않고 그림만 얹으면 그림 옆에 그 글자가 남는다.
    """
    para = next(iter(tc.iter(f"{{{HP}}}p")), None)
    if para is None:
        return
    run = next(iter(para.iter(f"{{{HP}}}run")), None)
    if run is None:
        run = etree.SubElement(para, f"{{{HP}}}run")
        run.set("charPrIDRef", "0")
    for child in list(run):
        if _ln(child.tag) == "t":
            run.remove(child)
    run.append(etree.fromstring(pic_xml))


def _build_image_p(proto_p, count: int, captions, HP, uid: int,
                   caption_bf: Optional[str] = None,
                   hdr=None, unbold_cache=None,
                   pics=None, cell_h: Optional[int] = None):
    """양식 자기 그리드의 '내부 셀'(사방 실선)만으로 이미지자리 표(2행×N열)를 조립.
    행0=이미지칸(높이 IMG_CELL_H), 행1=캡션칸(IMG_CAPTION_H, 무테두리). N은 1~3.

    pics: 칸마다 넣을 `hp:pic` XML(없으면 None) — 주면 자리표 글자 대신 실물이
    들어간다. cell_h 를 주면 이미지칸 높이를 그 값으로 낮춘다(그림이 작은데 칸만
    46mm(130pt)로 남아 지면을 먹는 것을 막는다).
    """
    q = lambda n: f"{{{HP}}}{n}"
    p = deepcopy(proto_p)
    tbl = next(iter(p.iter(q("tbl"))))
    trs = [tr for tr in tbl if _ln(tr.tag) == "tr"]
    proto_rows = [[tc for tc in tr if _ln(tc.tag) == "tc"] for tr in trs]
    # 내부 셀(사방 SOLID) = 행2(없으면 마지막행)의 가운데 열(없으면 0)
    r_i = min(2, len(proto_rows) - 1)
    c_i = min(1, len(proto_rows[r_i]) - 1)
    inner = proto_rows[r_i][c_i]

    N = max(1, min(3, int(count or 1)))
    captions = [str(x) for x in (captions or [])]
    base = IMG_TOTAL_W // N
    widths = [base] * N
    widths[-1] += IMG_TOTAL_W - sum(widths)
    heights = [int(cell_h) if cell_h else IMG_CELL_H, IMG_CAPTION_H]
    pics = list(pics or [])

    for tr in trs:
        tbl.remove(tr)
    for r in range(2):
        tr = etree.SubElement(tbl, q("tr"))
        for c in range(N):
            tc = deepcopy(inner)
            next(iter(tc.iter(q("cellAddr")))).attrib.update(
                {"colAddr": str(c), "rowAddr": str(r)})
            next(iter(tc.iter(q("cellSpan")))).attrib.update(
                {"colSpan": "1", "rowSpan": "1"})
            next(iter(tc.iter(q("cellSz")))).attrib.update(
                {"width": str(widths[c]), "height": str(heights[r])})
            pic = pics[c] if (r == 0 and c < len(pics)) else None
            if r == 0:
                txt = IMG_PLACEHOLDER
            else:
                txt = captions[c] if c < len(captions) else ""
                if caption_bf:          # 캡션 행은 무테두리
                    tc.set("borderFillIDRef", caption_bf)
            if pic:
                _cell_set_pic(tc, HP, pic)
            else:
                _cell_set_text(tc, HP, txt)
            # 이미지자리는 표 헤더가 아님 — 전 셀 볼드 제거
            if hdr is not None and unbold_cache is not None:
                for run in tc.iter(q("run")):
                    run.set("charPrIDRef",
                            _make_unbold_charpr(hdr, run.get("charPrIDRef"),
                                                unbold_cache))
            for cp in tc.iter(q("p")):
                _clear_lineseg(cp, HP)
            tr.append(tc)

    tbl.set("rowCnt", "2")
    tbl.set("colCnt", str(N))
    # 표와 같은 들여쓰기(3칸) — 한 문서에 표·이미지자리가 같이 오면 좌측이 맞아야 한다
    for run in p.findall(q("run")):
        done = False
        for ch in run:
            if _ln(ch.tag) == "tbl":
                done = True
                break
            if _ln(ch.tag) == "t" and (ch.text or "").strip() == "":
                ch.text = " " * TABLE_LEAD_SPACES
        if done:
            break
    tbl.set("id", str(uid))
    total_h = sum(heights)
    for ch in tbl:
        if _ln(ch.tag) == "sz":
            ch.attrib.update({"width": str(IMG_TOTAL_W), "height": str(total_h)})
            break
    for ch in p:
        if _ln(ch.tag) == "linesegarray":
            for ls in ch:
                ls.attrib.update({"vertsize": str(total_h),
                                  "textheight": str(total_h)})
    return p


def _image_sources(im: Dict[str, Any]) -> List[Any]:
    """이미지 블록에서 실물 그림 목록을 뽑는다. 없으면 빈 목록 = 지금까지의 자리표.

    한 블록이 칸을 1~3개 갖고, 칸마다 그림이 하나다. 그래서 목록이 기본형이지만
    칸이 하나인 흔한 경우를 위해 `path`/`b64` 를 블록에 바로 적는 것도 받는다.
    """
    srcs = im.get("sources")
    if srcs is None:
        one = {k: im[k] for k in ("path", "b64") if im.get(k)}
        srcs = [one] if one else []
    elif isinstance(srcs, (dict, str)):
        srcs = [srcs]
    return [s for s in srcs if s]


def _image_pics(ii: int, im: Dict[str, Any], srcs, cnt: int, embed, warnings):
    """칸마다 넣을 `hp:pic` XML 목록과, 그중 가장 큰 그림의 높이(HWPUNIT).

    그림을 못 넣은 칸은 None 이라 자리표 글자가 그대로 남는다 — 조용히 빈 칸을
    내지 않고 warnings 에 이유를 적는다(무음 실패는 렌더까지 가야 드러난다).
    """
    pics: List[Optional[str]] = []
    heights: List[int] = []
    if not srcs:
        return pics, 0
    if embed is None:
        warnings.append(f"[이미지{ii + 1}] 그림을 넣을 수 없다(임베드 경로 없음) — 자리표로 둔다")
        return pics, 0
    # 칸 안에 들어갈 상자. 폭은 칸 폭에서 안여백을, 높이는 이미지칸 높이에서 뺀다.
    box_w = IMG_TOTAL_W // cnt - IMG_PAD_W
    box_h = IMG_CELL_H - IMG_PAD_H
    if im.get("height_mm"):
        box_h = C.tablespec.mm(im["height_mm"])
    if im.get("width_mm"):
        box_w = min(box_w, C.tablespec.mm(im["width_mm"]))
    for c in range(cnt):
        if c >= len(srcs):
            pics.append(None)
            continue
        try:
            data, fmt = C.bindata.load_bytes(srcs[c])
            px_w, px_h = C.bindata.image_size(data)
            item_id = embed(data, fmt)
            w, h = C.bindata.fit_box(px_w, px_h, box_w, box_h)
        except Exception as e:                       # noqa — 사유를 남기고 자리표로
            warnings.append(f"[이미지{ii + 1}] {c + 1}번째 그림 실패: {e}")
            pics.append(None)
            continue
        pics.append(C.bindata.pic_xml(
            item_id, w, h, px_w=px_w, px_h=px_h, treat_as_char=True,
            obj_id=2200000001 + ii * 10 + c, z_order=c))
        heights.append(h)
    return pics, (max(heights) if heights else 0)


def fill_body(sec, HP, charmap, body_lines: List[str], hdr=None,
              tables=None, images=None, attachments=None,
              embed=None) -> Dict[str, Any]:
    """
    스켈레톤 본문 영역(첫 헤딩 ~ 붙임/참고 직전)을
    표준 간격 규칙이 적용된 새 문단들로 교체.
    프로토타입 복제 방식이라 charPr/paraPr 참조가 그대로 유지됨.
    tables/images 는 본문 줄의 위치 마커('[표1]' '[이미지1]') 자리에 삽입되고,
    마커로 소비되지 않은 항목은 기존처럼 본문 끝에 덧붙는다(0.2.2, 하위호환).
    attachments 는 본문 뒤 별지다 — 목록을 본문 끝에 붙이고 각 붙임은 쪽을 새로
    시작한다. 붙임의 표는 tables 뒤에 이어 붙여 같은 마커 체계로 삽입한다.
    """
    # 표/이미지자리 삽입용: 본문 제거 전에 양식 자기 그리드를 프로토타입으로 확보(deepcopy)
    # 붙임도 그리드를 쓴다(별지 안의 표) — 조건에서 빠지면 표가 통째로 실패한다
    grid_proto = _find_grid_proto(sec, HP) if (tables or images or attachments) else None
    # 붙임 표제는 전용 견본을 복제한다(표와 같은 방식)
    attach_proto = _find_attach_proto(sec, HP) if attachments else None

    top_paras = [ch for ch in sec
                 if C.xmlcompat.local_name(ch) == "p"]

    # 본문 시작: 취지(󰂐) 문단 이후 첫 16pt 비어있지 않은 문단
    # 본문 끝: '붙임' 또는 '참고' 로 시작하는 문단 직전
    start_idx = end_idx = None
    for i, p in enumerate(top_paras):
        txt = _para_text(p, HP).strip()
        size = _para_size(p, HP, charmap)
        if start_idx is None and txt and size >= 16 and not _has_table(p, HP):
            start_idx = i
            continue
        if start_idx is not None and txt and (
                txt.startswith("붙임") or txt.startswith("참고")):
            end_idx = i
            break
    if start_idx is None:
        return {"filled": False, "reason": "본문 시작(16pt 헤딩)을 찾지 못함"}
    if end_idx is None:
        end_idx = len(top_paras)

    body_paras = top_paras[start_idx:end_idx]
    protos = _collect_prototypes(top_paras, HP, charmap)
    if "heading" not in protos and "□" not in protos:
        return {"filled": False, "reason": "프로토타입 문단 없음"}

    # 헤딩 자동 번호 여부: 자동이면 텍스트의 '1.' 을 떼야 중복 안 됨
    auto_num = False
    if "heading" in protos:
        auto_num = _heading_is_autonumbered(hdr, protos["heading"].get("paraPrIDRef"))
    # '*' 참고 단위용 13pt 중고딕 charPr
    ref13_id = _find_ref13_charpr(hdr, sec, HP, charmap)

    # 붙임: 본문 줄 뒤에 목록·별지 줄을 이어 붙여 **한 흐름**으로 만든다.
    # 간격 규칙(build_flow)과 표 마커 체계를 그대로 쓰기 위해서다 — 별지용
    # 경로를 따로 두면 같은 규칙을 두 벌 갖게 된다(모드 B 에서 겪은 일).
    tables = list(tables or [])
    att_lines, att_warn = [], []
    att_head_lines = set()      # 별지 헤딩 줄(자동 번호를 끄고 번호를 글자로 둔다)
    for ai, att in enumerate(attachments or [], 1):
        if not isinstance(att, dict):
            att_warn.append(f"붙임{ai}: dict 가 아니어서 건너뜀")
            continue
        att_lines.append(f"[붙임{ai}]")
        # 별지 안의 '[표N]' 은 **그 붙임의 N 번째 표**를 가리킨다(전역 번호가
        # 아니다) — 붙임을 따로 쓰는 사람이 전체 표 번호를 셀 이유가 없다.
        att_tbls = [t for t in (att.get("tables") or [])]
        base = len(tables)
        tables.extend(att_tbls)
        used_local = set()
        for raw in str(att.get("body") or "").splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            tm = _TBL_MARK.match(line.strip())
            if tm is not None:
                n = int(tm.group(1))
                if 1 <= n <= len(att_tbls):
                    used_local.add(n)
                    att_lines.append(f"[표{base + n}]")
                else:
                    att_warn.append(f"붙임{ai}: [표{n}] 에 해당하는 표가 없다 "
                                    f"(이 붙임의 표는 {len(att_tbls)}개)")
                continue
            # 별지의 절 제목은 그 문서 안의 번호다 — 글자를 그대로 두고 자동
            # 번호만 끈다(아래 att_head_lines). 본문 번호 흐름을 건드리지 않는다.
            if KW.detect_level(line) == "heading":
                att_head_lines.add(line.strip())
            att_lines.append(line)
        # 본문에서 자리를 안 잡은 표는 그 붙임 끝에 붙인다(본문 규칙과 같다)
        for n in range(1, len(att_tbls) + 1):
            if n not in used_local:
                att_lines.append(f"[표{base + n}]")
        # 별지도 한 쪽을 채운다 — 본문에만 분량 규칙을 걸었더니 견본부터
        # 아래를 3분의 2 비운 채 나왔다(08-18). 판정은 최대 추정치라 거짓 경고가
        # 없다: 여기서 걸리면 아무리 길게 잡아도 한 쪽이 안 찬다는 뜻이다.
        body_only = [ln for ln in str(att.get("body") or "").splitlines() if ln.strip()]
        att_warn.extend(C.check_endings(body_only, f"붙임{ai}"))
        att_warn.extend(C.check_lines(body_only, f"붙임{ai}"))
        if not C.volume.fills_page(body_only, att_tbls, caption=True):
            need = C.volume.shortfall_lines(body_only, att_tbls, caption=True)
            att_warn.append(
                f"붙임{ai}('{str(att.get('title') or '')[:14]}')이 한 쪽을 못 채운다 "
                f"— 본문 줄로 {need}줄쯤 모자라다. 내용을 보태거나 앞 붙임과 합칠 것")
    att_titles = []
    if attachments:
        att_titles = [str((a or {}).get("title") or f"붙임 {i}")
                      for i, a in enumerate(attachments, 1) if isinstance(a, dict)]
        # 목록은 마커로 넘긴다 — 글자로 흘리면 '2. 제목.' 이 헤딩으로 잡혀
        # 자동 번호가 붙고 앞칸 정규화가 6칸 들여쓰기를 지운다(08-18 확인).
        body_lines = list(body_lines) + ["[붙임목록]"]

    # 새 문단 시퀀스 생성
    flow = KW.build_flow(body_lines) + KW.build_flow(att_lines)
    new_els = []
    warnings = []
    hang_cache = {}    # (base_ppid, hang) → 내어쓰기 paraPr id
    unnum_cache = {}   # 헤딩 paraPr id → 자동 번호 끈 판(별지 절 제목용)
    unbold_cache = {}  # charPr id → 볼드 제거판 id (표 데이터행·이미지자리용)
    small_cache = {}   # charPr id → 2pt 축소판 id (본문 부연 괄호용, 0.2.3)
    bold_cache = {}    # charPr id → 볼드판 id (말머리 라벨용, 0.2.3)
    sup_cache = {}     # charPr id → 위첨자판 id (각주 별표용 · 괄호 라벨 위첨자는 09-22 에 뗐다)
    align_cache = {}   # (paraPr id, 가로정렬) → 정렬만 바꾼 paraPr id (표 셀 서식용)
    bf_cache = {}      # (좌·우·하 borderFill) → 합성판 id (병합 셀 테두리용)
    page_w = printable_width(sec)   # 도해가 쓰는 판면 폭(문서에서 실측)
    char_cache = {}    # (charPr id, 글자색, 크기) → 변형판 id (도해 태그·잔글씨용)

    # (0.2.2) 위치 마커 지원 준비 — 마커로 삽입된 항목은 끝 덧붙임에서 제외
    used_tables: set = set()
    used_images: set = set()
    caption_bf = _find_none_borderfill(hdr) if images else None
    tables_added = 0
    images_added = 0
    attachments_added = 0

    def _valid_table(ti):
        return (tables is not None and 0 <= ti < len(tables)
                and isinstance(tables[ti], dict)
                and (tables[ti].get("headers") or tables[ti].get("rows")
                     or tables[ti].get("grid")))   # 도해는 grid 만으로 성립한다

    def _valid_image(ii):
        return (images is not None and 0 <= ii < len(images)
                and isinstance(images[ii], dict))

    def _table_els(ti):
        """표 문단 — 얹을 그림이 있으면 그림 문단이 **앞에** 하나 더 붙는다."""
        p = _table_el(ti)
        pre = _build_table_pics_p(p, HP, tables[ti].get("pics"), embed,
                                  warnings, 2000000001 + ti)
        return [pre, p] if pre is not None else [p]

    def _table_el(ti):
        tb = tables[ti]
        return _build_table_p(grid_proto, tb.get("headers") or [],
                              tb.get("rows") or [], HP,
                              uid=2000000001 + ti,
                              hdr=hdr, unbold_cache=unbold_cache,
                              col_ratios=tb.get("col_ratios"),
                              cells=tb.get("cells"),
                              merges=tb.get("merges"),
                              grid=tb.get("grid"),
                              row_heights=tb.get("row_heights"),
                              total_w=page_w,
                              align_cache=align_cache, bf_cache=bf_cache,
                              char_cache=char_cache, warnings=warnings)

    def _image_el(ii):
        im = images[ii]
        # 단수 'caption' 오입력 승격 (Agent 가 흔히 내는 형태)
        caps = im.get("captions")
        if caps is None and im.get("caption") is not None:
            caps = [im["caption"]]
        elif isinstance(caps, str):
            caps = [caps]
        srcs = _image_sources(im)
        cnt = im.get("count") or max(len(caps or []), len(srcs)) or 1
        cnt = max(1, min(3, int(cnt)))
        pics, pic_h = _image_pics(ii, im, srcs, cnt, embed, warnings)
        # 그림이 하나라도 들어갔으면 칸 높이를 실물에 맞춘다. 안 그러면 7mm 짜리
        # 로고 하나에 46mm 짜리 빈 칸이 따라붙어 지면을 헛되이 먹는다.
        cell_h = (pic_h + IMG_PAD_H) if pic_h else None
        return _build_image_p(grid_proto, cnt, caps, HP,
                              uid=2100000001 + ii,
                              caption_bf=caption_bf,
                              hdr=hdr, unbold_cache=unbold_cache,
                              pics=pics, cell_h=cell_h)

    for item in flow:
        if item.get("blank"):
            proto, got = _blank_proto(protos, item["size"])
            if proto is None:
                continue
            if got != item["size"]:
                warnings.append(f"빈줄 {item['size']}pt 없음 → {got}pt 사용")
            new_els.append(deepcopy(proto))
        else:
            # (0.2.2) 위치 마커 인터셉트 — '[표N]'/'[이미지N]' 줄은 문단 대신
            # 해당 표/이미지자리를 그 자리에 삽입한다
            stripped = item["text"].strip()
            if _ATTLIST_MARK.match(stripped):
                list_proto = _proto_for_level(protos, "□")
                for line in attach_list_lines(att_titles):
                    if list_proto is None:
                        break
                    lel = deepcopy(list_proto)
                    _set_para_text(lel, HP, line)   # 앞칸을 있는 그대로 둔다
                    new_els.append(lel)
                continue
            am = _ATT_MARK.match(stripped)
            if am is not None:
                ai = int(am.group(1)) - 1
                att = (attachments or [])[ai] if 0 <= ai < len(attachments or []) else None
                cap = None
                if isinstance(att, dict) and attach_proto is not None:
                    cap = _build_attach_caption_p(
                        attach_proto, HP, uid=2200000001 + ai, no=ai + 1,
                        title=str(att.get("title") or "").strip())
                if cap is None:
                    warnings.append(
                        f"{stripped} 표제 생성 실패 — 이 양식에 붙임 표제 견본이 없다"
                        "(첫 칸이 '붙임' 인 1행 3열 표)")
                else:
                    new_els.append(cap)
                    attachments_added += 1
                continue
            tm = _TBL_MARK.match(stripped)
            imk = _IMG_MARK.match(stripped) if tm is None else None
            if tm is not None or imk is not None:
                if tm is not None:
                    ti = int(tm.group(1)) - 1
                    if ti in used_tables:
                        warnings.append(f"[표{ti + 1}] 마커 중복 — 첫 위치만 사용")
                    elif _valid_table(ti) and grid_proto is not None:
                        new_els.extend(_table_els(ti))
                        used_tables.add(ti)
                        tables_added += 1
                    else:
                        warnings.append(
                            f"{stripped} 마커에 해당하는 표가 없거나 그리드 없음 — 줄 무시")
                else:
                    ii = int(imk.group(1)) - 1
                    if ii in used_images:
                        warnings.append(f"{stripped} 마커 중복 — 첫 위치만 사용")
                    elif _valid_image(ii) and grid_proto is not None:
                        new_els.append(_image_el(ii))
                        used_images.add(ii)
                        images_added += 1
                    else:
                        warnings.append(
                            f"{stripped} 마커에 해당하는 이미지자리가 없거나 그리드 없음 — 줄 무시")
                continue
            lvl = KW.detect_level(item["text"])
            proto = _proto_for_level(protos, lvl)
            if proto is None:
                continue
            el = deepcopy(proto)
            text = item["text"]
            # 마크다운 볼드(**)는 복제 방식에서 해석 불가 → 별표 노출 방지 위해 제거
            text = text.replace("**", "")
            # 마커 통일: detect_level 이 별칭(ㅁ→□, ㅇ→◦)을 레벨로만 인식하고
            # 텍스트는 안 바꾸므로, 출력도 양식 정식 기호로 교정한다.
            # 판정은 hwpx_core.markers 단일 기준 — 경계 규칙(- ○ ㅁ ㅇ 는 뒤 공백
            # 필수)이 있어야 "○○부와 협의"·"ㅁ자형 구조물" 의 첫 글자를 마커로
            # 먹지 않는다. 정식 기호 중 □ 만 스켈레톤 정본 글자(☐)로 바꾼다.
            lead = C.lead_marker(text)
            if lead:
                glyph = _TEMPLATE_GLYPH.get(C.CANON[lead], C.CANON[lead])
                if glyph != lead:
                    text = text.replace(lead, glyph, 1)
            # 자동 번호 헤딩이면 수동 번호 제거 ('1. 추진배경' → '추진배경')
            att_head = lvl == "heading" and text.strip() in att_head_lines
            if lvl == "heading" and auto_num and not att_head:
                text = _NUM_PREFIX.sub("", text)
            # 본문 줄의 부연 괄호는 2pt 작게(0.2.3) — 헤딩은 그대로 둔다.
            # '*' 참고 줄도 제외한다: 아래에서 run 서식을 ref13 으로 통째 덮으므로
            # 분할해 봐야 서식이 날아가고 괄호만 사라진다(08-04 리뷰 H1).
            _set_para_text(el, HP, text,
                           hdr=hdr if lvl not in ("heading", "*") else None,
                           small_cache=small_cache, bold_cache=bold_cache,
                           sup_cache=sup_cache)
            # '*' 참고 단위는 13pt 한양중고딕으로 서식 교체
            if lvl == "*" and ref13_id is not None:
                for r in el.iter(f"{{{HP}}}run"):
                    r.set("charPrIDRef", ref13_id)
            if att_head and hdr is not None:
                el.set("paraPrIDRef",
                       _make_unnumbered_parapr(hdr, el.get("paraPrIDRef"),
                                               unnum_cache))
            # 항목 단위에 내어쓰기 적용 (두 줄로 넘어갈 때 둘째 줄 정렬)
            hang = _HANG_BY_MARKER.get(lvl)
            if hang and _LEAD_LABEL.match(text):
                hang += _HANG_LABEL_EXTRA
            if hang and hdr is not None:
                el.set("paraPrIDRef",
                       _make_hanging_parapr(hdr, el.get("paraPrIDRef"),
                                            hang, hang_cache))
            new_els.append(el)

    kept = _apply_keep_with_next(new_els, hdr, HP, charmap)

    # (0.2.2) 마커로 소비되지 않은 표/이미지자리는 기존처럼 본문 끝에 덧붙임(하위호환)
    if tables and grid_proto is not None:
        for ti in range(len(tables)):
            if ti in used_tables or not _valid_table(ti):
                continue
            new_els.extend(_table_els(ti))
            tables_added += 1
    elif tables and grid_proto is None:
        warnings.append("표 삽입 실패: 이 양식에 복제할 그리드 표가 없음")

    if images and grid_proto is not None:
        for ii in range(len(images)):
            if ii in used_images or not _valid_image(ii):
                continue
            new_els.append(_image_el(ii))
            images_added += 1
    elif images and grid_proto is None:
        warnings.append("이미지자리 삽입 실패: 이 양식에 복제할 그리드 표가 없음")

    # 교체: 기존 본문 제거 후 새 문단 삽입
    anchor_pos = list(sec).index(body_paras[0])
    for p in body_paras:
        sec.remove(p)
    for offset, el in enumerate(new_els):
        sec.insert(anchor_pos + offset, el)

    # 부록(참고/붙임 예시 블록) 제거: 실제 내용이 채워진 문서에
    # 양식 예시("참고000 0000", "☐ TH 휴먼명조..." 등)가 남지 않도록
    removed_appendix = 0
    direct = {id(x) for x in sec}
    for p in top_paras[end_idx:]:
        if id(p) in direct:
            sec.remove(p)
            removed_appendix += 1

    return {"filled": True, "lines": len([x for x in flow if not x.get("blank")]),
            "appendix_removed": removed_appendix, "tables_added": tables_added,
            "images_added": images_added, "attachments_added": attachments_added,
            "kept_with_next": kept, "warnings": warnings + att_warn}


def _apply_keep_with_next(els, hdr, HP, charmap) -> int:
    """쪽 경계에서 갈라지면 안 되는 문단에 keepWithNext 를 켠다. 켠 개수 반환.

    묶는 자리(08-15 실제로 갈라진 사례에서 뽑았다):
      · 헤딩 → 뒤따르는 첫 항목      (회의계획에서 헤딩만 1쪽 끝에 남았다)
      · **표** 앞 항목               (교육계획에서 시간계획 표가 상위와 갈렸다)
      · 각주 설명(`* …`) **앞** 문단  (각주 마커는 1쪽, 설명은 2쪽으로 갈렸다)
    사이의 간격용 빈 문단에도 함께 켜야 연쇄가 끊기지 않는다.

    ⚠️★**이미지자리는 뺀다**(한/글 PDF 로 원인 확인).
      이미지자리도 표로 만들어져서 「표 앞 항목」 규칙에 같이 걸렸는데, 그 값이 컸다:

          이미지자리     178pt(칸) + 24pt(캡션) = 202pt
          1쪽에 남은 자리                        253pt   ← 그림만이면 들어간다
          앞 ◦ 3줄(65pt)이 같이 묶여             270pt   ← 17pt 초과 → 통째로 넘어감
          결과: 1쪽 아래 253pt(40%)가 빈다

      **그림만 넘어갔으면 들어갈 자리였다.** 원래 사고(08-15)는 **표**였고, 그림은
      캡션이 자기를 설명하므로 앞 항목과 붙어 있을 이유가 약하다. 상자 크기를
      줄이는 쪽은 다른 문서에서 또 어긋나므로 이쪽이 근본이다.
    """
    cache: Dict[str, str] = {}

    def is_blank(el):
        return not _para_text(el, HP).strip() and not _has_table(el, HP)

    def is_img(el):
        """이미지자리인가 — 표이면서 `<이미지 삽입>` 표시를 품고 있다."""
        return _has_table(el, HP) and IMG_PLACEHOLDER in _para_text(el, HP)

    def is_heading(el):
        return (bool(_para_text(el, HP).strip())
                and _para_size(el, HP, charmap) >= 16 and not _has_table(el, HP))

    def is_note(el):
        return _para_text(el, HP).strip().startswith("*")

    def turn_on(el):
        ppid = el.get("paraPrIDRef")
        if ppid is None:
            return False
        new = _make_keep_parapr(hdr, ppid, cache)
        if new == ppid:
            return False
        el.set("paraPrIDRef", new)
        return True

    n = len(els)
    count = 0
    for i, el in enumerate(els):
        if is_blank(el) or _has_table(el, HP):
            continue                      # 빈 문단은 아래에서 연쇄로 처리
        nxt = next((els[j] for j in range(i + 1, n) if not is_blank(els[j])), None)
        if nxt is None:
            continue
        need = (is_heading(el)
                or (_has_table(nxt, HP) and not is_img(nxt))     # ★그림은 안 묶는다
                or is_note(nxt))
        if not need:
            continue
        if turn_on(el):
            count += 1
        for j in range(i + 1, n):         # 사이의 간격용 빈 문단까지 함께
            if not is_blank(els[j]):
                break
            if turn_on(els[j]):
                count += 1
    return count


def fix_first_heading_gap(sec, HP, charmap, want_pt: int = None):
    """첫 헤딩 앞 빈 문단을 섹션 사이와 같은 간격(기본 8pt)으로 맞춘다.

    이 자리는 본문 교체 범위 **밖**(양식 원본의 빈 문단)이라 build_flow 의 간격
    규칙이 닿지 않아 양식마다 1pt·3pt·5pt 로 제각각이었다(08-15 지적).
    ⚠️ **drop_intent 뒤에 호출**해야 한다 — 취지 상자를 걷을 때 그 뒤 빈 문단도
    같이 사라지므로, 먼저 맞춰 두면 방금 맞춘 문단이 제거된다(실제로 겪었다).
    반환: 맞춘 pt (이미 맞거나 못 맞추면 None).
    """
    want = KW.GAP_BEFORE_FIRST_HEADING if want_pt is None else want_pt
    paras = [ch for ch in sec if C.xmlcompat.local_name(ch) == "p"]
    idx = next((i for i, p in enumerate(paras)
                if _para_text(p, HP).strip() and _para_size(p, HP, charmap) >= 16
                and not _has_table(p, HP)), None)
    if not idx:                      # 첫 헤딩이 없거나 문서 맨 앞이면 둘 자리가 없다
        return None
    before = paras[idx - 1]
    if _para_text(before, HP).strip() or _has_table(before, HP):
        return None                  # 빈 문단이 아니면 건드리지 않는다
    if int(round(_para_size(before, HP, charmap))) == want:
        return None                  # 이미 규격
    proto, got = _blank_proto(_collect_prototypes(paras, HP, charmap), want)
    if proto is None or got != want:
        return None                  # 그 크기 빈 문단이 양식에 없으면 원본 유지
    pos = list(sec).index(before)          # ET 에는 replace 가 없다
    sec.remove(before)
    sec.insert(pos, deepcopy(proto))
    return got


def _slugify(s: str) -> str:
    s = re.sub(r"[^\w가-힣]+", "_", s.strip()) or "doc"
    return s[:40]


def render(template_key: str = None,
           fields: Optional[Dict[str, str]] = None,
           output_dir: str = None,
           filename: str = None,
           body: Optional[str] = None,
           intent: Optional[str] = None,
           tables: Optional[List[Dict[str, Any]]] = None,
           images: Optional[List[Dict[str, Any]]] = None,
           attachments: Optional[List[Dict[str, Any]]] = None,
           template_path: Optional[str] = None) -> Dict[str, Any]:
    """
    스켈레톤을 열어 필드 값을 치환하고(선택) 본문을 채운 후 새 hwpx 파일로 저장.

    Args:
        template_key: 'plan'(계획류) · 'result'(결과보고류) · 'review'(검토보고) ·
            'plain'(기본 문서). 옛 유형 키(planning·training_plan·business_result …)는
            별칭으로 받는다
        fields: {필드명: 값} — 필드명은 TEMPLATE_SPECS[key]['fields'] 에 정의된 것
        output_dir: 출력 폴더 (기본: default_output_dir() — 소스 체크아웃이면 리포 루트 output/)
        filename: 파일명(확장자 제외). 미지정 시 자동
        body: 본문 내용(줄바꿈 구분). '1. 헤딩' '□ 항목' '◦ 세부' '- 상세' '* 참고'
            '[표1]'/'[이미지1]' 줄 = 해당 tables/images 항목을 그 위치에 삽입(0.2.2).
            표준 간격 규칙(빈줄 8/5/3pt, 들여쓰기)이 자동 적용된다. None 이면 양식의
            안내 문구를 그대로 둔다.
        images: 이미지자리 목록. [{"captions": [...], ...}, …] — 칸 1~3개.
            **실물 그림**은 `path`(파일 경로) 또는 `b64` 로 준다. 칸이 여럿이면
            `sources`: [{"path": …}, {"b64": …}] 로 칸마다 하나씩. 안 주면
            종전대로 자리표('<이미지 삽입>') 칸만 그린다.
            `height_mm`·`width_mm` 로 표시 크기 상한을 정할 수 있다(비율 유지).
            그림 바이트는 BinData 에 임베드되고 content.hpf 에 등록된다.
        attachments: 본문 뒤 별지 — [{"title": 붙임 제목, "body": 본문 줄,
            "tables": [...]}, ...]. 본문 끝에 붙임 목록이 자동으로 붙고,
            각 붙임은 쪽을 새로 시작해 '[붙임 N] 제목' 표제로 연다.
            별지 안의 헤딩('1. 작성요령')은 자동 번호를 끄고 글자 그대로 둔다 —
            본문 번호가 별지까지 이어지지 않게. 계층은 □·◦ 와 표로 짠다.

    Returns:
        {"status", "path", "template", "applied", "skipped", "body_result",
         "warnings", "outline"}
        warnings: 골격(hwpx_core.outline)·분량·종결 규격에 어긋난 지점. 빈 목록이면 이상 없음.
        outline: 어긋났을 때만 {"expected", "found"} — 무엇을 무엇으로 고칠지.
    """
    # 작은 모델이 흘리는 비정형 인자 방어: 엔진 경계에서 타입 정규화 (크래시 대신 무시/빈값)
    fields = fields if isinstance(fields, dict) else {}
    body = body if isinstance(body, str) else None
    attachments = attachments if isinstance(attachments, list) else None
    intent = intent if isinstance(intent, str) else None
    # 양식 출처: 등록 양식(template_key) 또는 밖에서 가져온 양식(template_path).
    # 서식 복제는 양식 파일에서 문단 프로토타입을 읽어 쓰는 구조라, 등록 여부와
    # 무관하게 같은 엔진으로 처리한다 — 필드 자리만 실물에서 찾아낸다(08-16).
    if template_path:
        src = os.path.abspath(str(template_path))
        if not os.path.exists(src):
            return {"status": "error", "message": f"양식 파일 없음: {src}"}
        probe = inspect_template(src)
        if not probe.get("usable"):
            return {"status": "error",
                    "message": f"이 파일은 양식으로 쓸 수 없다 — {probe.get('message')}",
                    "inspect": probe}
        template_key = template_key or os.path.splitext(os.path.basename(src))[0]
        spec = {"label": f"사용자 양식({os.path.basename(src)})",
                "description": "밖에서 가져온 양식",
                "fields": probe["fields"]}
    else:
        # 옛 유형 키(planning·training_plan…)는 지금 키로 옮겨 받는다.
        requested, template_key = template_key, resolve_template_key(template_key)
        if requested in TEMPLATE_RETIRED:
            return {"status": "error",
                    "message": f"'{requested}' 는 더 이상 양식이 아니다 — "
                               f"{TEMPLATE_RETIRED[requested]}"}
        if template_key not in TEMPLATE_SPECS:
            return {"status": "error",
                    "message": f"unknown template '{requested}'. "
                               f"사용 가능: {list(TEMPLATE_SPECS.keys())}"}
        spec = TEMPLATE_SPECS[template_key]
        src = template_file(template_key)
        if not os.path.exists(src):
            return {"status": "error", "message": f"스켈레톤 없음: {src}"}

    # 【주관】 줄(0.2.4 sample → 0.2.5 유형 템플릿 공통) — 담당자와 작성일이 한 줄을 나눠 쓴다.
    # · **기본은 날짜만 바꾼다**(실무 확인) — 담당자·직급·내선은 견본을 그대로 두어
    #   사람이 한글에서 자기 것으로 고치게 한다. 자동으로 채울 수 있는 건 이름뿐이라
    #   반쪽으로 채우면 오히려 고칠 견본이 사라진다
    # · 날짜는 호출자(LLM)에게 맡기지 않는다 — 비면 서버 시각(KST)으로 채운다
    # · owner 를 명시하면 그때만 담당자 자리를 통째로 교체한다(다른 소비자용 능력)
    stamp_day = None
    if "owner" in spec["fields"] and "date" in spec["fields"]:
        fields = dict(fields)
        # 값은 여기서 한 번만 정리한다 — 문서에 넣는 값과 applied 로 돌려주는 값이
        # 달라지면 호출자가 문서 내용을 오해한다.
        owner = _xml_safe(str(fields.get("owner") or "").strip())
        day = _xml_safe(str(fields.get("date") or "").strip()) or today_kst()
        if owner:
            fields["owner"] = owner
            fields["date"] = f"/({day})"
        else:
            fields.pop("owner", None)
            fields.pop("date", None)
            stamp_day = day

    # 필드 → 인덱스 치환 맵
    idx_map: Dict[int, str] = {}
    applied: Dict[str, str] = {}
    skipped: List[str] = []
    for name, value in (fields or {}).items():
        # 공백만 있는 값은 '없는 것'으로 본다 — 통과시키면 견본 글자가 빈 문자열로
        # 덮여 그 <hp:t> 가 비고, 비어 있지 않은 t 를 세는 날짜 스탬프의 인덱스가
        # 통째로 밀려 조용히 실패한다(제목은 비고 견본 날짜는 남는 문서가 나온다).
        v = _xml_safe(str(value).strip()) if value is not None else ""
        if name in spec["fields"] and v:
            idx = spec["fields"][name]["index"]
            idx_map[idx] = v
            applied[name] = v
        elif name in spec["fields"]:
            skipped.append(f"{name}(값이 비어 있음 — 견본 문구 유지)")
        else:
            skipped.append(name)

    # 원본 압축 로드 (hwpx-core)
    members = C.read_members(src)
    if SECTION_MEMBER not in members:
        return {"status": "error",
                "message": f"손상된 스켈레톤(섹션 없음): {os.path.basename(src)}"}

    # 한 번 파싱해 필드 치환 + 본문 채우기 순서로 처리
    sec = C.xmlcompat.parse(members[SECTION_MEMBER])
    # 접두사가 'hp' 가 아닌(그러나 유효한) 템플릿에서 치환이 무음 no-op 되지 않도록 URI 폴백
    HP = C.xmlcompat.hp_uri(sec, C.HP)
    replaced = _replace_text_at_indices(sec, HP, idx_map)
    # 범위 밖 인덱스(템플릿 개정으로 자리 소실 등)는 applied 성공으로 보고하지 않는다
    for name in list(applied):
        if spec["fields"][name]["index"] not in replaced:
            applied.pop(name)
            skipped.append(f"{name}(치환 실패: 템플릿에 해당 자리 없음)")
    # 견본 유지 경로 — 날짜 괄호만 도장을 찍는다(담당자 꼬리는 그대로).
    # ⚠️위 사후 검사 **뒤에** 온다 — 이건 인덱스 통째 치환이 아니라 부분 치환이라
    #   `replaced` 에 안 들어간다(앞에 두면 방금 찍은 날짜가 실패로 보고된다).
    if stamp_day:
        if _stamp_date(sec, HP, spec["fields"]["date"]["index"], stamp_day):
            applied["date"] = stamp_day
        else:
            # 무음 no-op 금지 — 견본이 개정돼 날짜 자리를 못 찾으면 사실을 남긴다
            skipped.append("date(견본에서 날짜 자리를 찾지 못함)")

    body_result = None
    hdr = None
    hdr_src = members.get(C.HEADER)
    if body and body.strip():
        if hdr_src is None:
            return {"status": "error",
                    "message": f"손상된 스켈레톤(헤더 없음): {os.path.basename(src)}"}
        hdr = C.xmlcompat.parse(hdr_src)
        charmap = _parse_charmap(hdr_src)

        def _embed(data: bytes, fmt: str) -> str:
            """그림 바이트를 이 문서에 적재하고 `binaryItemIDRef` 를 돌려준다.

            등록 자리는 **content.hpf 의 opf:manifest** 다(header.xml 이 아니다).
            같은 바이트를 여러 칸에 써도 멤버는 하나만 생긴다 — bindata 가 판정한다.
            """
            return C.bindata.add_image(members, data, fmt)

        body_result = fill_body(sec, HP, charmap, body.splitlines(), hdr=hdr,
                                tables=tables, images=images,
                                attachments=attachments, embed=_embed)

    # 【주관】 줄 맞춤 — body 유무와 무관하다(견본 담당자 셋은 본문이 없어도 넘친다).
    # 필드 치환·날짜 도장 **뒤에** 온다: 그쪽이 글자를 바꾸고 이쪽은 서식만 바꾼다.
    owner_fitted = False
    if hdr_src is not None:
        if hdr is None:
            hdr = C.xmlcompat.parse(hdr_src)
        owner_fitted = fit_owner_line(sec, HP, hdr)

    if hdr is not None:
        # fill_body 가 내어쓰기 paraPr 를, fit_owner_line 이 장평 charPr 를 header 에
        # 추가했을 수 있으므로 재직렬화. like= 로 원본 바이트를 준다 — 안 주면 안
        # 쓰이는 xmlns 선언이 빠져 구버전 한/글이 파일을 못 연다(xmlcompat._restore_xmlns).
        members[C.HEADER] = C.xmlcompat.serialize(hdr, like=hdr_src)

    # 취지 상자 — body 유무와 무관하게 처리한다. 안 주면 뼈대의 견본 문구('󰂐 …')가
    # 그대로 문서에 남으므로 문단째 걷어낸다(한 장짜리는 취지 상자를 쓰지 않는 관례).
    intent_info = {}
    if intent and str(intent).strip():
        intent_info["intent_filled"] = fill_intent(sec, HP, str(intent))
    else:
        intent_info["intent_dropped"] = drop_intent(sec, HP)
    if isinstance(body_result, dict):
        body_result.update(intent_info)
        # 취지 상자를 걷어낸 **뒤에** 첫 헤딩 앞 간격을 맞춘다(순서 의존 — 함수 주석 참조)
        if body_result.get("filled"):
            body_result["first_gap_pt"] = fix_first_heading_gap(
                sec, HP, _parse_charmap(members[C.HEADER]))

    # 골격 검사 — 골격 규칙(hwpx_core.outline)과 어긋나면 사실을 남긴다.
    # 막지 않고 알리기만 하는 이유는 check_outline 주석 참조(우회가 표준이 되는 것을 막는다).
    # 헤딩 판정은 KW.detect_level 단일 기준을 그대로 쓴다 — 여기서 다시 정규식을
    # 세우면 본문에 들어간 헤딩과 검사가 보는 헤딩이 갈린다.
    warnings: List[str] = []
    heads: List[str] = []
    if body and body.strip():
        rows = body.splitlines()
        heads = [ln for ln in rows if KW.detect_level(ln) == "heading"]
        warnings.extend(C.check_outline(heads, template_key))
        # ★공문서 관행 검사는 **공문서 유형에만** 건다(260831). 체언 종결과 자수
        # 규격은 hwpx 의 기능이 아니라 공공기관 보고서 관행이라, 계획표·안내문
        # 같은 일반 문서(plain)에 걸면 맞지도 않는 잣대로 매번 경고가 뜬다 —
        # 실제로 방학 생활계획표를 찍다 "체언으로 끊을 것"이 무더기로 나왔다.
        if C.outline.resolve(template_key) != C.outline.PLAIN:
            # 개조식 종결은 본문·별지에 똑같이 건다 — 산문에만 두었더니 붙임을
            # 통째로 서술형으로 쓰는 일이 생겼다(08-18).
            warnings.extend(C.check_endings(rows, "본문"))
            warnings.extend(C.check_lines(rows, "본문"))
        # 마지막 단(향후계획) 뒤의 줄들 — 일정 줄만 두는지 본다.
        # ★260928 — 「넷째 헤딩 뒤」에서 「마지막 헤딩 뒤」로(단 수가 가변이 됐다 · core 0.1.6).
        #   마지막 단이 향후계획이 아니면 check_outline 이 이미 알렸으니 여기선 안 본다.
        if (C.outline.resolve(template_key) in C.outline.HAS_FUTURE_PLAN
                and heads and C.outline.normalize_heading(heads[-1]) == C.outline.SECTION_4):
            tail, seen = [], 0
            for ln in rows:
                if KW.detect_level(ln) == "heading":
                    seen += 1
                    continue
                if seen >= len(heads):
                    tail.append(ln)
            warnings.extend(C.check_future_plan(tail))

    members[SECTION_MEMBER] = C.xmlcompat.serialize(
        sec, like=members[SECTION_MEMBER])

    # 양식에 박힌 2쪽 모아 찍기를 기본 인쇄로 되돌린다(함수 주석 참조)
    print_method_was = normalize_print_method(members)

    # 저장 (hwpx-core: mimetype STORED 우선 규칙 포함)
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    if not filename:
        # raw fields 가 아닌 정규화된 applied 사용 (비문자열 title 크래시·None fields 방지)
        base = _slugify(applied.get("title") or applied.get("post_title") or template_key)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{template_key}_{base}_{stamp}"
    out_path = os.path.join(out_dir, filename + ".hwpx")
    C.write_hwpx(out_path, members)

    return {"status": "success",
            "path": out_path,
            "template": template_key,
            "template_label": spec["label"],
            "applied": applied,
            "skipped": skipped,
            "print_method_fixed": print_method_was,
            "owner_line_fitted": owner_fitted,
            "warnings": warnings,
            "outline": {"expected": list(C.outline_for(template_key)),
                        "found": [C.outline.normalize_heading(h) for h in heads]}
                       if warnings else None,
            "body_result": body_result}


if __name__ == "__main__":
    import json
    print(json.dumps(list_templates(), ensure_ascii=False, indent=2))
