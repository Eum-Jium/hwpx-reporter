# -*- coding: utf-8 -*-
"""
hwpx_full.py v2 — 블록 조립 API (외부 의존성 없음, stdlib only)

Doc 스타일로 쌓은 블록을 모드 A 와 같은 엔진(vendor/hwpx_skeleton)으로 렌더한다:
제목상자·【주관】 블록·자동번호 헤딩·간격 리듬·정본 표 테두리·이미지자리까지 같다.

사용법 (권장 — body 한 방):
    from hwpx_full import Doc

    doc = Doc("보고서 제목")
    doc.body("1. 추진 배경\\n□ 항목\\n◦ 세부\\n- 상세\\n* 참고")
    tbl = doc.table(3, 3)          # 필요 시
    doc.image_placeholder(["캡션"])  # 필요 시
    doc.save("output/보고서.hwpx")

세부 제어가 필요하면 heading()/bullet()/note()/para() 개별 호출도 가능
(간격은 자동 삽입됨).
"""

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 서식 상수 (정본 양식 기준 — run 서식 판정·항목부호 표에 쓴다)
# ═══════════════════════════════════════════════════════════════════════════════

# charPr IDs
_CHAR_BODY    = "7"     # 휴먼명조 15pt (본문)
_CHAR_BOLD    = "31"    # 휴먼명조 15pt bold
_CHAR_BLUE    = "32"    # 휴먼명조 15pt bold #0000FF
_CHAR_REF     = "10"    # 한양중고딕 13pt (참고 '*')

# paraPr IDs
_PARA_BODY    = "0"     # JUSTIFY, 160%, 여백 0

# 항목부호: 마커 → (앞칸 수, 내어쓰기 paraPr) — 정본 실측 intent
_MARKERS   = {1: "☐", 2: "◦", 3: "-", 4: "·", 5: "*"}
_LEAD      = {"☐": 1, "◦": 2, "-": 3, "·": 4, "*": 4}
_PARA_HANG = {"☐": "28", "◦": "29", "-": "30", "·": "30", "*": "31"}

# 마커 판정·간격 규칙은 hwpx_core 단일 기준을 그대로 쓴다 — 표가 모드 A(양식
# 렌더)와 갈라지면 같은 본문이 다른 간격으로 렌더되고, 마커 경계가 없으면
# "-5% 절감"·"○○부와 협의" 의 첫 글자가 마커로 먹혀 사라진다.
# 필요한 모듈 파일만 직접 적재한다 — 패키지 전체를 import 하지 않아도 마커 판정이 선다.
def _load_core_module(name: str):
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "vendor", "hwpx_core", f"{name}.py")
    if not os.path.exists(path):
        raise ImportError(
            f"기준 모듈을 찾지 못했다: {path} — 리포에서 "
            "'python skill/build_skill.py' 로 vendor/ 를 생성하라")
    spec = importlib.util.spec_from_file_location(f"_hwpx_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MARKERS_MOD = _load_core_module("markers")
# 정식 기호(□)와 이 스크립트의 내부 글리프(☐=정본 원본 문자) 사이 변환.
_TO_LOCAL = {"□": "☐"}



# ═══════════════════════════════════════════════════════════════════════════════
# 데이터클래스 / 단위
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CellFmt:
    """표 셀 서식. 정본 규칙: 헤더행 13pt 중고딕 bold / 데이터행 13pt 일반,
    모두 가운데. bold=True 로 데이터 셀 볼드 강제, align="LEFT" 로 정렬 변경.

    borders·bg 는 도해(모눈 표)용이다 — 네 변을 끄고 한쪽만 켜면 그 칸이 선이 된다.
        CellFmt(borders={"all": "NONE", "top": "SOLID 0.3"})   # 가로 실선
        CellFmt(borders={"all": "SOLID 0.5 #FF0000"}, bg="#E1EAF6")
    변 이름은 left·right·top·bottom·all, 종류는 NONE·SOLID·DASH·DOUBLE_SLIM.
    """
    bold: bool = False
    align: Optional[str] = None    # None(=CENTER) / LEFT
    borders: Optional[dict] = None
    bg: Optional[str] = None


def mm(value: float) -> int:
    """밀리미터 → HWPUNIT (1mm ≈ 283.5)"""
    return int(value * 283.5)


# ═══════════════════════════════════════════════════════════════════════════════
# Para / Table
# ═══════════════════════════════════════════════════════════════════════════════

class Para:
    """단락 — run 누적으로 혼합 서식."""

    def __init__(self):
        self._runs: List[dict] = []

    def add_run(self, text: str, bold: bool = False,
                ref: bool = False, blue: bool = False) -> "Para":
        if blue:
            cid = _CHAR_BLUE
        elif ref:
            cid = _CHAR_REF
        elif bold:
            cid = _CHAR_BOLD
        else:
            cid = _CHAR_BODY
        self._runs.append({"text": text, "char_id": cid})
        return self


class Table:
    """표 — 셀 누적 후 save() 시 정본 테두리로 생성."""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self._cells: dict = {}
        self._ratios = None
        self._grid = None
        self._heights = None
        self._pics = []

    def col_ratios(self, ratios) -> "Table":
        """열 너비 비율(열 수만큼). 전체 폭은 고정이고 그 안에서만 나뉜다.
        안 주면 정본 배분(첫 열 고정 + 나머지 균등)."""
        self._ratios = list(ratios)
        return self

    def as_grid(self) -> "Table":
        """도해(모눈) 모드 — 헤더행 개념이 없고 칸이 기본으로 빈 칸이 된다.
        글자는 cell(r, c, "글자") 로 넣고, 선은 CellFmt(borders=…) 로 긋는다."""
        self._grid = {"rows": self.rows, "cols": self.cols}
        return self

    def row_heights(self, heights) -> "Table":
        """행 높이(mm, 행 수만큼). 연결선만 있는 행을 얇게 두는 데 쓴다."""
        self._heights = list(heights)
        return self

    def pic(self, path=None, x_mm=0, y_mm=0, height_mm=None, width_mm=None,
            b64=None) -> "Table":
        """표 **위에 얹는** 그림 — 정본이 상자마다 기관 표장을 두는 방식.

        x_mm 은 판면 왼쪽, y_mm 은 표 윗변 기준이다. 칸 안에 넣는 것이 아니라
        띄우는 것이라 상자 안 글자를 밀지 않는다.
        """
        spec = {"x_mm": x_mm, "y_mm": y_mm}
        for k, v in (("path", path), ("b64", b64),
                     ("height_mm", height_mm), ("width_mm", width_mm)):
            if v is not None:
                spec[k] = v
        self._pics.append(spec)
        return self

    def _get_cell_styles(self, with_text: bool = False) -> list:
        """엔진이 받는 셀 서식 목록. bold=False 는 '지정 안 함'으로 본다 —
        CellFmt 의 기본값이라, 그대로 넘기면 헤더행 볼드까지 벗겨진다.

        with_text=True 면 글자도 **같은 항목에** 담는다(도해 모드). 글자와 서식을
        따로 내보내면 엔진이 칸 하나에 둘을 받아 나중 것이 앞엣것을 덮는다.
        """
        out = []
        for (r, c), cell in sorted(self._cells.items()):
            st = {}
            fmt = cell.get("fmt")
            if fmt is not None:
                if fmt.bold:
                    st["bold"] = True
                if fmt.align:
                    st["align"] = fmt.align
                if fmt.borders:
                    st["borders"] = fmt.borders
                if fmt.bg is not None:
                    st["bg"] = fmt.bg
            if with_text and str(cell.get("text", "")).strip():
                st["text"] = cell["text"]
            if st:
                out.append(dict(st, r=r, c=c))
        return out

    def cell(self, row: int, col: int, text: str = "",
             fmt: Optional[CellFmt] = None, **kwargs) -> "Table":
        if fmt is None:
            fmt = CellFmt(**{k: v for k, v in kwargs.items()
                             if k in ("bold", "align", "borders", "bg")})
        self._cells[(row, col)] = {"text": str(text), "fmt": fmt}
        return self

    def _get_headers(self) -> list:
        return [self._cells.get((0, c), {}).get("text", "")
                for c in range(self.cols)]

    def _get_rows(self) -> list:
        return [[self._cells.get((r, c), {}).get("text", "")
                 for c in range(self.cols)] for r in range(1, self.rows)]


_HEAD_NUM = re.compile(r"^\s*\d+\.\s*")
_ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅰⅱⅲⅳⅴ"


class Doc:
    """정본 골격 템플릿 기반 문서 빌더 (stdlib only).

    제목상자·【주관】 블록·페이지 설정은 템플릿에 내장 — 본문만 만들면 된다.
    블록 사이 간격(8/5/3pt 빈 문단)은 저장 시 자동 삽입된다.
    """

    def __init__(self, title: str = "제목없음"):
        self._title = title
        self._blocks: List[dict] = []
        self._tbl_counter = 2000

    # ── 조립 API ────────────────────────────────────────────

    def heading(self, text: str, level: int = 2) -> "Doc":
        """섹션 헤딩 (16pt, 자동번호 '1.' '2.' …).
        입력 앞의 수동 번호('1. ', 'Ⅰ. ')는 제거된다."""
        t = _HEAD_NUM.sub("", text.strip())
        if t[:1] in _ROMAN:
            t = re.sub(r"^[" + _ROMAN + r"]\.?\s*", "", t)
        self._blocks.append({"kind": "heading", "text": t})
        return self

    def bullet(self, text: str, level: int = 1,
               marker: Optional[str] = None) -> "Doc":
        """항목부호 단락. ☐1칸 ◦2칸 -3칸 ·4칸 *4칸 + 내어쓰기 자동."""
        m = marker or _MARKERS.get(level, "☐")
        canon = _MARKERS_MOD.CANON.get(m, m)   # 별칭(□·○·※ …) → 정식 기호
        m = _TO_LOCAL.get(canon, canon)        # 정식 → 이 스크립트 내부 글리프(☐)
        lead = _LEAD.get(m, 1)
        cid = _CHAR_REF if m == "*" else _CHAR_BODY
        self._blocks.append({"kind": m,
                             "text": f"{' ' * lead}{m} {text}",
                             "char_id": cid,
                             "para_id": _PARA_HANG.get(m, _PARA_BODY)})
        return self

    def note(self, text: str) -> "Doc":
        """참고('*') 단락 — 13pt 한양중고딕, 정규화.

        선두 기호는 별칭(※ 포함)까지 벗긴 뒤 '*' 를 다시 붙인다 — 직접 호출과
        body() 경유 호출이 같은 결과를 내야 한다."""
        return self.bullet(_MARKERS_MOD.strip_marker(text), marker="*")

    def para(self, text: str = "", bold: bool = False,
             blue: bool = False) -> Para:
        """일반 본문 단락(15pt). Para 반환 — add_run 체이닝."""
        p = Para()
        if text:
            p.add_run(text, bold=bold, blue=blue)
        self._blocks.append({"kind": "para", "para": p})
        return p

    def blank(self, pt: int = 5) -> "Doc":
        """수동 빈 줄(간격). 자동 간격 대신 직접 지정할 때."""
        self._blocks.append({"kind": "gap", "pt": pt})
        return self

    def table(self, rows: int, cols: int) -> Table:
        """정본 스타일 표(13pt 중고딕 bold·가운데, 헤더 하단 이중선)."""
        tbl = Table(rows, cols)
        self._blocks.append({"kind": "table", "table": tbl})
        return tbl

    def diagram(self, rows: int, cols: int) -> Table:
        """도해용 모눈 표. table(rows, cols).as_grid() 와 같다."""
        return self.table(rows, cols).as_grid()

    def image_placeholder(self, captions=None, **kw) -> "Doc":
        """이미지자리 + 캡션 (1~3칸).

        `path=` 나 `b64=`(칸이 여럿이면 `sources=[…]`)를 주면 **실물 그림**이
        들어간다. 안 주면 종전대로 `<이미지 삽입>` 자리표만 그린다.
        `height_mm`·`width_mm` 로 표시 크기 상한을 정한다(비율 유지).
        """
        if isinstance(captions, str):
            captions = [captions]
        blk = {"kind": "image", "captions": captions or [""]}
        for k in ("path", "b64", "sources", "height_mm", "width_mm", "count"):
            if kw.get(k) is not None:
                blk[k] = kw[k]
        self._blocks.append(blk)
        return self

    # 실물 그림을 넣을 때 쓰는 이름 — 자리표만 놓을 때와 뜻이 달라 별칭을 둔다
    image = image_placeholder

    def body(self, text: str) -> "Doc":
        """본문 통째 입력 — 줄 첫 기호로 단위 판정 (모드 A 와 동일 규칙).
        '1. 헤딩' / '□ 항목' / '◦ 세부' / '- 상세' / '· 미세' / '* 참고'"""
        for raw in (text or "").split("\n"):
            line = raw.strip()
            if not line:
                continue
            c = _MARKERS_MOD.canon_marker(line)
            if _HEAD_NUM.match(line) or line[0] in _ROMAN:
                self.heading(line)
            elif c:
                content = _MARKERS_MOD.strip_marker(line)
                m = _TO_LOCAL.get(c, c)
                if m == "*":
                    self.note(content)      # 마커는 note 가 다시 붙인다
                else:
                    self.bullet(content, marker=m)
            else:
                self.para(line)
        return self


    def save(self, path: str) -> str:
        """조립한 블록을 **모드 A 와 같은 엔진**(vendor/hwpx_skeleton)으로 렌더한다.

        종전에는 여기서 XML 을 직접 문자열로 조립했다 — 같은 일을 두 벌로 갖고
        있으니 한쪽만 고치면 어긋났다(모아찍기·표 규격을 매번 양쪽에 고쳤다).
        엔진이 파서 중립이 된 뒤로는 lxml 없이도 그 엔진이 돌아, 이
        모듈은 **Doc 스타일 API 를 엔진 입력으로 옮겨 주는 얇은 어댑터**다.

        엔진이 지원하지 않는 것은 조용히 버리지 않고 알린다:
          · para(bold=·blue=) 혼합 서식 → 글자는 살리고 서식은 빠진다
          · blank(pt=) 수동 간격      → 엔진이 8/5/3pt 규칙으로 자동 삽입한다
        (CellFmt 의 bold·align 과 Table.col_ratios 는 엔진이 받는다 — 종전에는
        여기서 버려졌다.)
        """
        import sys as _sys
        vendor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
        if vendor not in _sys.path:
            _sys.path.insert(0, vendor)
        import hwpx_skeleton as _HS

        lines, tables, images, dropped = [], [], [], []
        for b in self._blocks:
            kind = b.get("kind")
            if kind == "table":
                t = b["table"]
                if t._grid:
                    # 도해는 빈 칸이 기본이라 headers/rows 를 넘기지 않는다 —
                    # 글자는 칸마다 cells 로 간다.
                    tb = {"grid": t._grid}
                else:
                    tb = {"headers": t._get_headers(), "rows": t._get_rows()}
                styles = t._get_cell_styles(with_text=bool(t._grid))
                if styles:
                    tb["cells"] = styles
                if t._ratios:
                    tb["col_ratios"] = t._ratios
                if t._heights:
                    tb["row_heights"] = t._heights
                if t._pics:
                    tb["pics"] = t._pics
                tables.append(tb)
                lines.append(f"[표{len(tables)}]")
            elif kind == "image":
                im = {"captions": b.get("captions") or [""]}
                for k in ("path", "b64", "sources", "height_mm", "width_mm",
                          "count"):
                    if b.get(k) is not None:
                        im[k] = b[k]
                images.append(im)
                lines.append(f"[이미지{len(images)}]")
            elif kind == "gap":
                dropped.append("수동 간격(blank)")
            elif kind == "para":
                txt = "".join(r["text"] for r in b["para"]._runs).strip()
                if txt:
                    lines.append(txt)
                # run 은 char_id 만 갖는다 — 본문 15pt 가 아닌 run 이 서식이 빠지는 run 이다
                if any(r["char_id"] != _CHAR_BODY for r in b["para"]._runs):
                    dropped.append("혼합 서식(para bold·blue·ref)")
            elif kind == "heading":
                # 번호는 엔진이 자동으로 매긴다 — 헤딩으로 판정되게 형식만 맞춘다
                lines.append(f"1. {b['text']}")
            elif b.get("text"):
                lines.append(b["text"].strip())

        abs_path = os.path.abspath(path)
        out_dir = os.path.dirname(abs_path) or "."
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(abs_path))[0]

        res = _HS.render("sample", fields={"title": self._title},
                         body=chr(10).join(lines), tables=tables or None,
                         images=images or None, output_dir=out_dir, filename=stem)
        if res.get("status") != "success":
            raise RuntimeError(f"렌더 실패: {res.get('message')}")

        made = os.path.abspath(res["path"])
        if made != abs_path:                     # 확장자·경로 표기 차이 흡수
            if os.path.exists(abs_path):
                os.remove(abs_path)
            os.replace(made, abs_path)
        if dropped:
            print("[알림] 엔진이 지원하지 않아 빠진 요소:", ", ".join(sorted(set(dropped))))
        # 골격 경고는 모드 A 의 결과 dict 로 오지만 이 경로는 경로를 반환하므로
        # 삼켜진다 — 같은 [알림] 창구로 내보낸다(두 진입점이 같은 것을 알린다).
        # 본문을 채우며 난 경고(표 마커·그림·붙임 분량)는 body_result 쪽에 따로 온다.
        br = res.get("body_result") if isinstance(res.get("body_result"), dict) else {}
        seen = []
        for w in list(res.get("warnings") or []) + list(br.get("warnings") or []):
            if w not in seen:
                seen.append(w)
                print("[알림]", w)
        print(f"저장 완료: {abs_path} ({os.path.getsize(abs_path):,} bytes)")
        return abs_path


# ═══════════════════════════════════════════════════════════════════════════════
# 스모크
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    doc = Doc("모드 B v2 스모크")
    doc.body("\n".join([
        "1. 추진 배경",
        "□ (근거) 첫째 항목",
        "◦ (현황) 둘째 수준",
        "- 셋째 수준",
        "* 참고: 넷째",
        "2. 추진 방안",
        "□ (도구) 다시 첫째",
    ]))
    t = doc.table(3, 3)
    t.cell(0, 0, "단계").cell(0, 1, "내용").cell(0, 2, "일정")
    t.cell(1, 0, "1").cell(1, 1, "시범").cell(1, 2, "'26.상")
    t.cell(2, 0, "2").cell(2, 1, "확산").cell(2, 2, "'26.하")
    doc.image_placeholder(["체계 구성도"])
    os.makedirs("output", exist_ok=True)
    doc.save("output/모드B_v2_스모크.hwpx")
