# -*- coding: utf-8 -*-
"""표 서식 — 열 너비 비율과 셀별 정렬·볼드.

표 커스터마이징 스펙은 종전에 writer(cell_styles)와 모드 B(CellFmt) 두 군데에
있었지만, 정작 문서를 내는 엔진(skeleton)에는 없어 **둘 다 렌더에서 버려졌다**.
여기서 그 스펙이 실제 XML 까지 닿는지 본다.

잘못된 값은 문서를 막지 않는다는 계약도 함께 못박는다 — 표 하나 때문에 보고서가
통째로 안 나오는 쪽이 더 나쁘다. 대신 사유는 반드시 경고로 남아야 한다.
"""
import re
import zipfile

from hwpx_core import tablespec as TS
from hwpx_skeleton import renderer


BODY = "\n".join(["1. 개요", "□ 앞 문단", "[표1]"])


def _render(tmp_path, tables):
    res = renderer.render(template_key="planning", fields={"title": "표 서식"},
                          output_dir=str(tmp_path), body=BODY, tables=tables)
    assert res["status"] == "success", res
    return res


def _warns(res):
    """표 경고만 골라 본다 — 견본 본문이 골격 규칙(마지막 단 향후계획)을 따르지 않아 골격 경고가 섞인다."""
    all_w = res["warnings"] + (res.get("body_result") or {}).get("warnings", [])
    return [w for w in all_w if w.startswith("[표]")]


def _our_table(path: str) -> str:
    """양식 자체 표(제목 박스 등)를 지나 우리가 넣은 표 XML 을 고른다."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("Contents/section0.xml").decode("utf-8")
    for m in re.finditer(r"<hp:tbl.*?</hp:tbl>", xml, re.S):
        if "앞 문단" in xml[:m.start()] and "구분" in m.group(0):
            return m.group(0)
    raise AssertionError("삽입한 표를 찾지 못했다")


def _widths(tbl: str):
    """열 폭. 병합된 행은 칸이 모자라므로 **병합 없는 행**에서 읽는다."""
    n = int(re.search(r'colCnt="(\d+)"', tbl).group(1))
    for tr in re.findall(r"<hp:tr>.*?</hp:tr>", tbl, re.S):
        cells = re.findall(r"<hp:tc[ >].*?</hp:tc>", tr, re.S)
        if len(cells) != n or any('colSpan="1" rowSpan="1"' not in c for c in cells):
            continue
        return [int(re.search(r'<hp:cellSz width="(\d+)"', c).group(1)) for c in cells]
    raise AssertionError("병합 없는 행이 없다 — 폭을 읽을 수 없다")


BASE = {"headers": ["구분", "내용", "비고"], "rows": [["가", "본문", "주석"]]}


def test_열_비율이_실제_폭에_반영된다(tmp_path):
    res = _render(tmp_path, [dict(BASE, col_ratios=[1, 4, 2])])
    w = _widths(_our_table(res["path"]))
    assert sum(w) == TS.TOTAL_W
    assert abs(w[1] / w[0] - 4) < 0.01 and abs(w[2] / w[0] - 2) < 0.01
    assert not _warns(res)


def test_비율을_안_주면_종전_배분_그대로(tmp_path):
    res = _render(tmp_path, [dict(BASE)])
    assert _widths(_our_table(res["path"]))[0] == TS.FIRST_W


def test_못_쓰는_비율은_기본배분으로_떨어지고_경고를_남긴다(tmp_path):
    res = _render(tmp_path, [dict(BASE, col_ratios=[1, 1])])      # 열 수 불일치
    assert _widths(_our_table(res["path"]))[0] == TS.FIRST_W      # 표는 그대로 나온다
    assert any("열 비율" in w for w in _warns(res))


def test_셀_정렬은_그_셀에만_붙는다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 1, "align": "LEFT"}])])
    ids = re.findall(r'paraPrIDRef="(\d+)"', _our_table(res["path"]))
    assert len(ids) == 6                                   # 2행 × 3열
    assert len(set(ids)) == 2, ids                         # 기본판 + 왼쪽정렬판
    assert ids[4] not in (ids[0], ids[3]), ids             # 바뀐 것은 (1,1) 뿐


def test_같은_정렬은_paraPr_를_한_벌만_만든다(tmp_path):
    """캐시가 없으면 셀마다 새 paraPr 가 쌓여 header 가 부푼다."""
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 0, "align": "LEFT"},
                                               {"r": 1, "c": 1, "align": "LEFT"},
                                               {"r": 1, "c": 2, "align": "LEFT"}])])
    ids = re.findall(r'paraPrIDRef="(\d+)"', _our_table(res["path"]))
    assert len(set(ids[3:])) == 1, ids


def test_행_인덱스는_헤더행_포함_0부터(tmp_path):
    """r=0 이 헤더행이다 — 여기가 어긋나면 서식이 한 행씩 밀린다."""
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 0, "c": 2, "align": "RIGHT"}])])
    ids = re.findall(r'paraPrIDRef="(\d+)"', _our_table(res["path"]))
    assert ids[2] != ids[0] and ids[3:] == [ids[0]] * 3, ids


def test_볼드는_기본이_헤더행뿐이고_셀로_덮을_수_있다(tmp_path):
    plain = re.findall(r'charPrIDRef="(\d+)"', _our_table(
        _render(tmp_path, [dict(BASE)])["path"]))
    assert len(set(plain[:3])) == 1 and len(set(plain[3:])) == 1
    assert plain[0] != plain[3], plain                     # 헤더만 볼드

    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 2, "bold": True}])])
    ids = re.findall(r'charPrIDRef="(\d+)"', _our_table(res["path"]))
    assert ids[5] == ids[0], ids                           # 그 셀만 헤더와 같은 볼드
    assert ids[3] == ids[4] != ids[0], ids


def test_헤더행_볼드도_끌_수_있다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 0, "c": 0, "bold": False}])])
    ids = re.findall(r'charPrIDRef="(\d+)"', _our_table(res["path"]))
    assert ids[0] == ids[3], ids


def test_row_col_로_와도_받는다(tmp_path):
    """Agent 가 흔히 내는 형태 — 조용히 버리면 서식이 안 먹은 줄 모른다."""
    res = _render(tmp_path, [dict(BASE, cells=[{"row": 1, "col": 1, "align": "LEFT"}])])
    ids = re.findall(r'paraPrIDRef="(\d+)"', _our_table(res["path"]))
    assert len(set(ids)) == 2, ids
    assert not _warns(res)


def test_범위_밖_셀과_모르는_정렬값은_경고만_남기고_문서는_나온다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 9, "c": 0, "align": "LEFT"},
                                               {"r": 1, "c": 1, "align": "MIDDLE"},
                                               {"r": "1", "c": 1, "bold": True}])])
    w = _warns(res)
    assert any("범위" in x for x in w), w
    assert any("MIDDLE" in x for x in w), w
    assert any("정수" in x for x in w), w
    ids = re.findall(r'paraPrIDRef="(\d+)"', _our_table(res["path"]))
    assert len(set(ids)) == 1, ids                         # 아무것도 안 먹었다


def test_서식을_줘도_전체_폭은_고정이다(tmp_path):
    """같은 문서 안 표들의 좌우가 어긋나지 않아야 한다 — 표 폭을 고정한 이유."""
    res = _render(tmp_path, [dict(BASE, col_ratios=[2, 3, 5],
                                  cells=[{"r": 1, "c": 0, "align": "LEFT"}])])
    assert sum(_widths(_our_table(res["path"]))) == TS.TOTAL_W


# ── 셀 병합 ──────────────────────────────────────────────────────────────
# 병합은 덮인 칸을 XML 에서 **지우는** 작업이다. 하나라도 잘못 남거나 잘못 지우면
# 한/글이 표를 손상으로 보고 수리한다 — 그 판정 기준(행 커버리지 = 열 수)을
# writer 의 validate_hwpx 와 같은 잣대로 여기서도 건다.

def _rows(tbl: str):
    """[(colAddr, rowAddr, colSpan, rowSpan, width, borderFillIDRef), …] 를 행별로."""
    out = []
    for tr in re.findall(r"<hp:tr>.*?</hp:tr>", tbl, re.S):
        cells = []
        for tc in re.findall(r"<hp:tc[ >].*?</hp:tc>", tr, re.S):
            sp = re.search(r'<hp:cellSpan colSpan="(\d+)" rowSpan="(\d+)"', tc)
            ad = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"', tc)
            sz = re.search(r'<hp:cellSz width="(\d+)" height="(\d+)"', tc)
            bf = re.search(r'borderFillIDRef="(\d+)"', tc)
            cells.append((int(ad.group(1)), int(ad.group(2)),
                          int(sp.group(1)), int(sp.group(2)),
                          int(sz.group(1)), int(sz.group(2)), bf.group(1)))
        out.append(cells)
    return out


def _assert_intact(tbl: str):
    """한/글이 수리하지 않을 표인지 — 행마다 커버리지가 열 수와 맞는지 본다."""
    cols = int(re.search(r'colCnt="(\d+)"', tbl).group(1))
    pending = []
    for ri, cells in enumerate(_rows(tbl)):
        total = sum(cs for _, cs in pending)
        nxt = [[k - 1, cs] for k, cs in pending if k - 1 > 0]
        for _, _, cs, rs, _, _, _ in cells:
            total += cs
            if rs > 1:
                nxt.append([rs - 1, cs])
        pending = nxt
        assert total == cols, f"{ri}행 커버리지 {total} != 열 수 {cols}"


MERGE_BASE = {"headers": ["구분", "1단계", ""],
              "rows": [["가", "설계", "착수"],
                       ["", "시공", "완료"],
                       ["나", "운영", "예정"]]}


def test_가로_병합은_덮인_칸을_지우고_폭을_합친다(tmp_path):
    res = _render(tmp_path, [dict(MERGE_BASE,
                                  merges=[{"r1": 0, "c1": 1, "r2": 0, "c2": 2}])])
    tbl = _our_table(res["path"])
    _assert_intact(tbl)
    head = _rows(tbl)[0]
    assert len(head) == 2, head                       # 3칸이 2칸으로
    assert head[1][2] == 2 and head[1][3] == 1        # colSpan 2
    assert head[1][4] == sum(_widths(tbl)[1:]), head  # 폭은 덮은 칸들의 합


def test_세로_병합은_아랫줄에서_칸이_빠지고_높이가_는다(tmp_path):
    res = _render(tmp_path, [dict(MERGE_BASE,
                                  merges=[{"r1": 1, "c1": 0, "r2": 2, "c2": 0}])])
    tbl = _our_table(res["path"])
    _assert_intact(tbl)
    rows = _rows(tbl)
    assert rows[1][0][3] == 2                          # rowSpan 2
    assert rows[1][0][5] == 2 * rows[0][0][5]          # 높이 두 배
    assert len(rows[2]) == 2, rows[2]                  # 그 행은 칸이 하나 빈다
    assert rows[2][0][0] == 1, rows[2]                 # 남은 첫 칸의 colAddr 은 1


def test_가로세로_병합이_한_표에_같이_있어도_성립한다(tmp_path):
    res = _render(tmp_path, [dict(MERGE_BASE,
                                  merges=[{"r1": 0, "c1": 1, "r2": 0, "c2": 2},
                                          {"r1": 1, "c1": 0, "r2": 2, "c2": 0}])])
    _assert_intact(_our_table(res["path"]))
    assert not _warns(res)


def test_전체_폭_병합은_테두리를_새로_합성한다(tmp_path):
    """시작 칸 테두리만 쓰면 오른쪽에 안쪽 선이 남아 표 밖으로 삐져나온다."""
    plain = _our_table(_render(tmp_path, [dict(BASE)])["path"])
    last_bf = _rows(plain)[0][-1][6]                   # 끝 열의 borderFill
    res = _render(tmp_path, [dict(BASE, merges=[{"r1": 0, "c1": 0, "r2": 0, "c2": 2}])])
    tbl = _our_table(res["path"])
    _assert_intact(tbl)
    head = _rows(tbl)[0]
    assert len(head) == 1 and head[0][2] == 3
    assert head[0][4] == TS.TOTAL_W                    # 전체 폭
    assert head[0][6] not in (_rows(plain)[0][0][6], last_bf)   # 합성된 새 판


def test_같은_모양_병합은_borderFill_을_한_벌만_만든다(tmp_path):
    """행 위치가 같은(둘 다 '내부 행') 병합은 테두리 판을 나눠 쓴다.
    캐시가 없으면 병합마다 새 borderFill 이 쌓여 header 가 부푼다."""
    res = _render(tmp_path, [dict(BASE, rows=[["가", "", ""], ["나", "", ""],
                                              ["다", "", ""], ["라", "", ""]],
                                  merges=[{"r1": 2, "c1": 1, "r2": 2, "c2": 2},
                                          {"r1": 3, "c1": 1, "r2": 3, "c2": 2}])])
    rows = _rows(_our_table(res["path"]))
    assert rows[2][1][6] == rows[3][1][6], rows        # 같은 자리·같은 폭 → 같은 판


def test_뒤집힌_좌표도_바로잡아_받는다(tmp_path):
    res = _render(tmp_path, [dict(BASE, headers=["구분", "", ""],
                                  merges=[{"r1": 0, "c1": 2, "r2": 0, "c2": 0}])])
    _assert_intact(_our_table(res["path"]))
    assert not _warns(res)


def test_겹치는_병합은_뒤엣것을_버리고_경고한다(tmp_path):
    """겹친 채로 두면 앵커가 이미 지워진 칸이 되어 손상 파일이 된다."""
    res = _render(tmp_path, [dict(BASE, merges=[{"r1": 0, "c1": 0, "r2": 0, "c2": 1},
                                                {"r1": 0, "c1": 1, "r2": 1, "c2": 2}])])
    _assert_intact(_our_table(res["path"]))
    assert any("겹친다" in w for w in _warns(res)), _warns(res)


def test_범위_밖_한_칸짜리_망가진_병합은_무시하고_경고한다(tmp_path):
    res = _render(tmp_path, [dict(BASE, merges=[{"r1": 0, "c1": 0, "r2": 9, "c2": 1},
                                                {"r1": 1, "c1": 1, "r2": 1, "c2": 1},
                                                {"r1": 0, "c1": 0}])])
    tbl = _our_table(res["path"])
    _assert_intact(tbl)
    assert len(_rows(tbl)[0]) == 3                     # 아무것도 안 먹었다
    w = _warns(res)
    assert any("범위" in x for x in w) and any("한 칸뿐" in x for x in w), w
    assert any("온전하지" in x for x in w), w


def test_덮인_칸의_글자를_버리면_알린다(tmp_path):
    """조용히 버리면 표에서 글자가 사라진 것을 아무도 모른다."""
    res = _render(tmp_path, [dict(BASE, merges=[{"r1": 0, "c1": 0, "r2": 0, "c2": 1}])])
    assert any("덮인 칸" in w and "내용" in w for w in _warns(res)), _warns(res)


def test_병합과_열비율_셀서식을_같이_줘도_어긋나지_않는다(tmp_path):
    res = _render(tmp_path, [dict(BASE, col_ratios=[1, 3, 2],
                                  cells=[{"r": 1, "c": 1, "align": "LEFT"}],
                                  merges=[{"r1": 0, "c1": 0, "r2": 0, "c2": 2}])])
    tbl = _our_table(res["path"])
    _assert_intact(tbl)
    assert _rows(tbl)[0][0][4] == TS.TOTAL_W
    assert sum(_widths(tbl)) == TS.TOTAL_W


# ── 칸 테두리·배경 ───────────────────────────────────────────────────────
# 도해(모눈 표)의 원시기능이다 — 정본 체계도는 한쪽 변만 켠 칸을 선으로 써서
# 상자·연결선·점선 묶음틀을 그린다. 종류·굵기·색은 지어내면 한/글이 조용히
# 무시하므로, 실측으로 확인된 넷만 받는지도 함께 본다.

def _fills(path: str) -> dict:
    """{borderFill id: ((좌,우,상,하), 배경색)}"""
    with zipfile.ZipFile(path) as z:
        hdr = z.read("Contents/header.xml").decode("utf-8")
    out = {}
    for m in re.finditer(r'<hh:borderFill id="(\d+)".*?</hh:borderFill>', hdr, re.S):
        b = m.group(0)
        e = []
        for side in ("left", "right", "top", "bottom"):
            x = re.search(
                r'<hh:%sBorder type="(\w+)" width="([^"]+)" color="(#\w+)"' % side, b)
            e.append(x.groups() if x else None)
        f = re.search(r'faceColor="(#\w+)"', b)
        out[m.group(1)] = (tuple(e), f.group(1) if f else None)
    return out


def _cell_fill(res, r, c):
    tbl = _our_table(res["path"])
    for tr in re.findall(r"<hp:tr>.*?</hp:tr>", tbl, re.S):
        for tc in re.findall(r"<hp:tc[ >].*?</hp:tc>", tr, re.S):
            ad = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"', tc)
            if (int(ad.group(2)), int(ad.group(1))) == (r, c):
                bf = re.search(r'borderFillIDRef="(\d+)"', tc).group(1)
                return _fills(res["path"])[bf]
    raise AssertionError(f"({r},{c}) 칸이 없다")


def test_한쪽_변만_켜면_그_변만_바뀐다(tmp_path):
    """도해의 가로선 — all 로 네 변을 끄고 위만 켠다."""
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"all": "NONE", "top": "SOLID 0.3"}}])])
    (left, right, top, bottom), _ = _cell_fill(res, 1, 0)
    assert top == ("SOLID", "0.3 mm", "#000000"), top
    assert left[0] == right[0] == bottom[0] == "NONE", (left, right, bottom)
    assert not _warns(res)


def test_all_뒤에_개별_변이_덮는다_순서가_뒤집혀도(tmp_path):
    """dict 순서에 기대면 안 된다 — all 을 먼저 깔고 개별 변을 올린다."""
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"bottom": "DASH 0.3", "all": "NONE"}}])])
    (_, _, top, bottom), _ = _cell_fill(res, 1, 0)
    assert bottom == ("DASH", "0.3 mm", "#000000"), bottom
    assert top[0] == "NONE", top


def test_굵기와_색을_같이_준다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"all": "SOLID 0.5 #FF0000"}}])])
    edges, _ = _cell_fill(res, 1, 0)
    assert all(e == ("SOLID", "0.5 mm", "#FF0000") for e in edges), edges


def test_토큰_순서는_상관없다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"top": "#808080 0.7 DASH"}}])])
    (_, _, top, _), _ = _cell_fill(res, 1, 0)
    assert top == ("DASH", "0.7 mm", "#808080"), top


def test_사전_꼴로도_받는다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0,
         "borders": {"top": {"type": "SOLID", "width": 0.25, "color": "#1E7452"}}}])])
    (_, _, top, _), _ = _cell_fill(res, 1, 0)
    assert top == ("SOLID", "0.25 mm", "#1E7452"), top


def test_배경색을_넣고_지운다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 0, "bg": "#E1EAF6"}])])
    assert _cell_fill(res, 1, 0)[1] == "#E1EAF6"
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 0, "c": 0, "bg": ""}])])
    assert _cell_fill(res, 0, 0)[1] is None       # 양식 헤더는 회색인데 지웠다


def test_테두리와_배경을_같이_줘도_한_판에_담긴다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"all": "SOLID 0.7 #808080"}, "bg": "#F2F2F2"}])])
    edges, bg = _cell_fill(res, 1, 0)
    assert bg == "#F2F2F2" and edges[0] == ("SOLID", "0.7 mm", "#808080")


def test_같은_서식은_borderFill_을_한_벌만_만든다(tmp_path):
    before = len(_fills(_render(tmp_path, [dict(BASE)])["path"]))
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"all": "NONE"}},
        {"r": 1, "c": 1, "borders": {"all": "NONE"}},
        {"r": 1, "c": 2, "borders": {"all": "NONE"}}])])
    # 세 칸의 바탕 판이 서로 달라 새 판이 셋까지는 생길 수 있으나,
    # 같은 바탕+같은 지정이 거듭될 때 판이 늘지 않는 것이 요점이다.
    once = len(_fills(res["path"]))
    res2 = _render(tmp_path, [dict(BASE, rows=[["가", "나", "다"], ["라", "마", "바"]],
                                   cells=[{"r": 1, "c": 0, "borders": {"all": "NONE"}},
                                          {"r": 1, "c": 1, "borders": {"all": "NONE"}},
                                          {"r": 1, "c": 2, "borders": {"all": "NONE"}},
                                          {"r": 2, "c": 0, "borders": {"all": "NONE"}}])])
    assert len(_fills(res2["path"])) <= once + 1, (before, once, len(_fills(res2["path"])))


def test_모르는_종류_색_변은_경고만_남기고_문서는_나온다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[
        {"r": 1, "c": 0, "borders": {"top": "WAVY"}},
        {"r": 1, "c": 1, "borders": {"top": "SOLID 0.3 파랑"}},
        {"r": 1, "c": 2, "borders": {"diag": "SOLID"}}])])
    w = _warns(res)
    assert any("WAVY" in x for x in w), w
    assert any("파랑" in x and "#RRGGBB" in x for x in w), w
    assert any("diag" in x for x in w), w
    assert res["status"] == "success"


def test_borders_가_사전이_아니면_경고하고_넘어간다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 0, "borders": "SOLID"}])])
    assert any("꼴이어야" in x for x in _warns(res)), _warns(res)
    assert res["status"] == "success"


def test_잘못된_배경색은_무시하고_경고한다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 0, "bg": "파랑"}])])
    assert _cell_fill(res, 1, 0)[1] is None
    assert any("배경색" in x for x in _warns(res)), _warns(res)


def test_병합_셀에도_테두리_배경이_얹힌다(tmp_path):
    """병합으로 합성한 테두리 위에 다시 얹는다 — 순서가 어긋나면 하나가 지워진다."""
    res = _render(tmp_path, [dict(BASE,
                                  merges=[{"r1": 1, "c1": 0, "r2": 1, "c2": 2}],
                                  cells=[{"r": 1, "c": 0, "bg": "#E1EAF6",
                                          "borders": {"all": "SOLID 0.5 #FF0000"}}])])
    edges, bg = _cell_fill(res, 1, 0)
    assert bg == "#E1EAF6"
    assert all(e == ("SOLID", "0.5 mm", "#FF0000") for e in edges), edges
    _assert_intact(_our_table(res["path"]))


# ── 도해(모눈) 모드 ──────────────────────────────────────────────────────
# 내용표와 다른 점은 셋이다: 크기를 grid 가 선언하고, 칸이 기본으로 비어 있고
# (테두리·배경 없음), 글자가 cells 에서 온다. 정본 체계도가 42×81 에 글자 든
# 칸이 12개뿐이라 rows 로는 적을 수 없기 때문이다.

GRID = {"grid": {"rows": 3, "cols": 6}}


def _cells_of(res):
    tbl = _our_table_any(res["path"])
    out = {}
    for tr in re.findall(r"<hp:tr>.*?</hp:tr>", tbl, re.S):
        for tc in re.findall(r"<hp:tc[ >].*?</hp:tc>", tr, re.S):
            ad = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"', tc)
            out[(int(ad.group(2)), int(ad.group(1)))] = tc
    return out, tbl


def _our_table_any(path: str) -> str:
    """도해 표는 헤더 글자가 없어 _our_table 의 기준으로는 못 찾는다."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("Contents/section0.xml").decode("utf-8")
    for m in re.finditer(r"<hp:tbl.*?</hp:tbl>", xml, re.S):
        if "앞 문단" in xml[:m.start()] and m.group(0).startswith("<hp:tbl id=\"2000000"):
            return m.group(0)
    raise AssertionError("삽입한 표를 찾지 못했다")


def test_도해는_grid_가_크기를_정한다(tmp_path):
    res = _render(tmp_path, [dict(GRID)])
    cells, tbl = _cells_of(res)
    assert int(re.search(r'colCnt="(\d+)"', tbl).group(1)) == 6
    assert len(cells) == 18, len(cells)
    assert not _warns(res)


def test_도해_칸은_기본이_빈_칸이다(tmp_path):
    """테두리도 배경도 없어야 한다 — 안 그러면 선을 그은 자리가 구분되지 않는다."""
    res = _render(tmp_path, [dict(GRID)])
    for (r, c) in ((0, 0), (0, 5), (2, 3)):
        edges, bg = _cell_fill_at(res, r, c)
        assert all(e[0] == "NONE" for e in edges), (r, c, edges)
        assert bg is None, (r, c, bg)


def _cell_fill_at(res, r, c):
    cells, _ = _cells_of(res)
    bf = re.search(r'borderFillIDRef="(\d+)"', cells[(r, c)]).group(1)
    return _fills(res["path"])[bf]


def test_글자는_cells_의_text_로_넣는다(tmp_path):
    res = _render(tmp_path, [dict(GRID, cells=[{"r": 1, "c": 2, "text": "기본법"}])])
    cells, _ = _cells_of(res)
    assert "기본법" in cells[(1, 2)]
    assert "기본법" not in cells[(0, 0)]


def test_도해에는_헤더행_볼드가_없다(tmp_path):
    res = _render(tmp_path, [dict(GRID, cells=[{"r": 0, "c": 0, "text": "가"},
                                               {"r": 1, "c": 0, "text": "나"}])])
    cells, _ = _cells_of(res)
    ids = [re.search(r'charPrIDRef="(\d+)"', cells[(r, 0)]).group(1) for r in (0, 1)]
    assert ids[0] == ids[1], ids


def test_행_높이를_mm_로_정한다(tmp_path):
    res = _render(tmp_path, [dict(GRID, row_heights=[7, 4, 8])])
    cells, tbl = _cells_of(res)
    got = [int(re.search(r'<hp:cellSz width="\d+" height="(\d+)"',
                         cells[(r, 0)]).group(1)) for r in range(3)]
    assert got == [TS.mm(7), TS.mm(4), TS.mm(8)], got
    # 표 전체 높이도 합과 맞아야 한다 — 안 맞으면 다음 문단이 표를 파고든다
    assert int(re.search(r'<hp:sz width="\d+"[^>]*height="(\d+)"',
                         tbl).group(1)) == sum(got)


def test_연결선_행은_얇게_유지된다(tmp_path):
    """도해의 요점 — 선만 있는 행이 본문 한 줄만큼 두꺼우면 그림이 헐렁해진다."""
    res = _render(tmp_path, [dict(GRID, row_heights=[7, 2, 7])])
    cells, _ = _cells_of(res)
    thin = int(re.search(r'height="(\d+)"', cells[(1, 0)]).group(1))
    assert thin < TS.ROW_H, (thin, TS.ROW_H)


def test_열이_많아도_모눈은_균등하게_나뉜다(tmp_path):
    """내용표 최소폭(글자 한 자)을 그대로 걸면 모눈이 통째로 거부된다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 40}}])
    _, tbl = _cells_of(res)
    w = [int(x) for x in re.findall(r'<hp:cellSz width="(\d+)"', tbl)][:40]
    assert sum(w) == _page_w(res["path"])
    assert max(w) - min(w) <= 1, (min(w), max(w))
    assert not _warns(res)


def _page_w(path: str) -> int:
    """그 문서의 판면 폭 — 도해가 쓰는 폭."""
    with zipfile.ZipFile(path) as z:
        sec = renderer.C.xmlcompat.parse(z.read("Contents/section0.xml"))
    return renderer.printable_width(sec)


def test_도해는_본문_표보다_넓은_판면_폭을_쓴다(tmp_path):
    """정본 체계도가 그렇다 — 본문 표 폭(162.5mm)에 맞추면 지면이 남는다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 10}}])
    _, tbl = _cells_of(res)
    got = int(re.search(r'<hp:sz width="(\d+)"', tbl).group(1))
    page = _page_w(res["path"])
    assert got == page > TS.TOTAL_W, (got, page, TS.TOTAL_W)


def test_도해에는_표_앞_들여쓰기를_붙이지_않는다(tmp_path):
    """판면 폭을 꽉 쓰므로 들여쓰기가 붙으면 그만큼 판면 밖으로 나간다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 10}}])
    with zipfile.ZipFile(res["path"]) as z:
        xml = z.read("Contents/section0.xml").decode("utf-8")
    tbl = _our_table_any(res["path"])
    head = xml[xml.index(tbl) - 400:xml.index(tbl)]
    assert " " * TS.LEAD_SPACES not in head, head[-120:]

    # 내용표는 종전대로 들여쓴다
    res2 = _render(tmp_path, [dict(BASE)])
    with zipfile.ZipFile(res2["path"]) as z:
        xml2 = z.read("Contents/section0.xml").decode("utf-8")
    t2 = _our_table(res2["path"])
    assert " " * TS.LEAD_SPACES in xml2[xml2.index(t2) - 400:xml2.index(t2)]


def test_모눈에도_병합과_테두리가_그대로_먹는다(tmp_path):
    res = _render(tmp_path, [dict(GRID,
                                  merges=[{"r1": 0, "c1": 1, "r2": 0, "c2": 4}],
                                  row_heights=[7, 2, 7],
                                  cells=[{"r": 0, "c": 1, "text": "상자",
                                          "borders": {"all": "SOLID 0.12"}},
                                         {"r": 1, "c": 3,
                                          "borders": {"left": "SOLID 0.12"}}])])
    _assert_intact(_our_table_any(res["path"]))
    edges, _ = _cell_fill_at(res, 0, 1)
    assert all(e[0] == "SOLID" for e in edges), edges
    # 세로 연결선 — 왼쪽만 켜지고 나머지는 꺼진 채여야 한다
    left, right, top, bottom = _cell_fill_at(res, 1, 3)[0]
    assert left[0] == "SOLID" and right[0] == top[0] == bottom[0] == "NONE"


def test_행_높이_개수가_안_맞거나_너무_낮으면_경고하고_기본으로(tmp_path):
    res = _render(tmp_path, [dict(GRID, row_heights=[7, 4])])
    assert any("행 높이 개수" in w for w in _warns(res)), _warns(res)
    cells, _ = _cells_of(res)
    assert int(re.search(r'height="(\d+)"', cells[(0, 0)]).group(1)) == TS.ROW_H

    res = _render(tmp_path, [dict(GRID, row_heights=[7, 0.1, 7])])
    assert any("너무 낮다" in w for w in _warns(res)), _warns(res)

    res = _render(tmp_path, [dict(GRID, row_heights=[7, "넷", 7])])
    assert any("숫자(mm)" in w for w in _warns(res)), _warns(res)


def test_grid_에_크기가_없으면_알리고_넘어간다(tmp_path):
    res = _render(tmp_path, [{"grid": True, "headers": ["가", "나"],
                              "rows": [["다", "라"]]}])
    assert any("rows·cols 가 없어" in w for w in _warns(res)), _warns(res)
    assert res["status"] == "success"


def test_내용표에서도_text_로_칸을_덮는다(tmp_path):
    res = _render(tmp_path, [dict(BASE, cells=[{"r": 1, "c": 1, "text": "덮어쓴 값"}])])
    tbl = _our_table(res["path"])
    assert "덮어쓴 값" in tbl and "본문" not in tbl


# ── 모눈이 지면에 들어가기 위한 두 조건 ──────────────────────────────────
# 아래 둘이 없으면 44열 표가 162.5mm 로 안 들어가 지면 밖(228mm)까지 늘어난다.
# XML 은 멀쩡하고 한/글도 열기 때문에 **파일만 봐서는 안 보이는** 결함이라
# 여기서 못박는다(08-18, PDF 좌표 실측으로 원인을 찾았다).

def test_모눈의_빈_칸은_아주_작은_글꼴을_받는다(tmp_path):
    """한/글은 칸마다 그 칸 글꼴 한 자 자리를 최소 너비로 잡는다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 30}}])
    cells, _ = _cells_of(res)
    with zipfile.ZipFile(res["path"]) as z:
        hdr = z.read("Contents/header.xml").decode("utf-8")
    height = {m.group(1): int(m.group(2)) for m in
              re.finditer(r'<hh:charPr id="(\d+)" height="(\d+)"', hdr)}
    cid = re.search(r'charPrIDRef="(\d+)"', cells[(0, 0)]).group(1)
    assert height[cid] == int(TS.GRID_EMPTY_PT * 100), height[cid]


def test_글자가_든_칸은_원래_크기를_지킨다(tmp_path):
    """빈 칸만 낮춰야 한다 — 글자 칸까지 1pt 로 만들면 글씨가 사라진다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 30},
                              "cells": [{"r": 0, "c": 0, "text": "가"}]}])
    cells, _ = _cells_of(res)
    with zipfile.ZipFile(res["path"]) as z:
        hdr = z.read("Contents/header.xml").decode("utf-8")
    height = {m.group(1): int(m.group(2)) for m in
              re.finditer(r'<hh:charPr id="(\d+)" height="(\d+)"', hdr)}
    cid = re.search(r'charPrIDRef="(\d+)"', cells[(0, 0)]).group(1)
    assert height[cid] > int(TS.GRID_EMPTY_PT * 100), height[cid]


def test_모눈은_칸_안여백을_명시한다(tmp_path):
    """기본값(-1)이면 한/글이 자기 기본 여백을 써서 열마다 최소 폭이 잡힌다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 30}}])
    cells, _ = _cells_of(res)
    tc = cells[(0, 0)]
    assert 'hasMargin="1"' in tc, tc[:160]
    mg = re.search(r'<hp:cellMargin left="(\d+)" right="(\d+)" '
                   r'top="(\d+)" bottom="(\d+)"', tc)
    assert mg and set(mg.groups()) == {str(TS.GRID_CELL_MARGIN)}, tc[-200:]


def test_내용표는_칸_안여백을_건드리지_않는다(tmp_path):
    """도해만의 조치다 — 내용표까지 바꾸면 정본 표 모양이 달라진다."""
    res = _render(tmp_path, [dict(BASE)])
    tbl = _our_table(res["path"])
    tc = re.findall(r"<hp:tc[ >].*?</hp:tc>", tbl, re.S)[0]
    assert 'hasMargin="1"' not in tc
    assert "4294967295" in tc


# ── 첫 열은 항목명에 맞춰 넓어진다 ───────────────────────────────────────
# 규격이 tablespec 에 있어도 렌더가 헤더·행을 안 넘기면 문서에는 안 닿는다.
# 08-18 실물에서 `야간 순찰(회/월)` 이 두 줄로 접혀 행이 두 배로 높아졌다.

def test_긴_항목명이_들면_첫_열이_넓어진다(tmp_path):
    res = _render(tmp_path, [{"headers": ["구분", "목표", "실적"],
                              "rows": [["야간 순찰(회/월)", "12", "11"],
                                       ["주간 점검", "4", "4"]]}])
    w = _widths(_our_table(res["path"]))
    assert w[0] > TS.FIRST_W, w
    assert w[0] == TS.first_col_w(["구분", "야간 순찰(회/월)", "주간 점검"],
                                  TS.TOTAL_W, TS.MIN_COL_W, 3), w
    assert sum(w) == TS.TOTAL_W, w
    assert not _warns(res)


def test_짧은_항목명만_있으면_정본_폭_그대로다(tmp_path):
    """정본 표 모양이 문서마다 흔들리면 안 된다 — 넓히는 건 필요할 때만."""
    res = _render(tmp_path, [dict(BASE)])
    assert _widths(_our_table(res["path"]))[0] == TS.FIRST_W


def test_도해는_첫_열_자동폭을_쓰지_않는다(tmp_path):
    """모눈은 균등 분할이 곧 격자다 — 첫 칸만 넓어지면 그림이 어긋난다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 20},
                              "cells": [{"r": 0, "c": 0, "text": "야간 순찰(회/월)"}]}])
    _, tbl = _cells_of(res)
    w = [int(x) for x in re.findall(r'<hp:cellSz width="(\d+)"', tbl)][:20]
    assert max(w) - min(w) <= 1, (min(w), max(w))


# ── 자간·장평 ────────────────────────────────────────────────────────────
# 긴 줄은 **글자 크기를 줄이지 말고** 자간을 좁혀 넣는다 — 정본 도해가 그렇다
# (장평은 전부 100 이고 자간만 -6/-9/-12/-16). 크기를 줄이면 한 도해 안에서
# 글자가 널뛰어 위계가 무너진다. 실무 한도는 자간 -10 · 장평 95%.

def _charpr(res, key):
    """그 글줄이 쓰는 charPr 의 (pt, 자간, 장평)."""
    tbl = _our_table_any(res["path"])
    with zipfile.ZipFile(res["path"]) as z:
        hdr = z.read("Contents/header.xml").decode("utf-8")
    cp = {}
    for m in re.finditer(r'<hh:charPr id="(\d+)" height="(\d+)".*?</hh:charPr>',
                         hdr, re.S):
        b = m.group(0)
        sp = re.search(r'<hh:spacing hangul="(-?\d+)"', b)
        rt = re.search(r'<hh:ratio hangul="(\d+)"', b)
        cp[m.group(1)] = (int(m.group(2)) / 100, int(sp.group(1)) if sp else 0,
                          int(rt.group(1)) if rt else 100)
    for pa in re.findall(r"<hp:p[ >].*?</hp:p>", tbl, re.S):
        txt = "".join(re.findall(r"<hp:t>(.*?)</hp:t>", pa, re.S))
        if key in txt:
            cid = re.search(r'charPrIDRef="(\d+)"', pa).group(1)
            return cp[cid]
    raise AssertionError(f"{key!r} 글줄을 못 찾았다")


def test_자간을_칸_서식으로_준다(tmp_path):
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 20},
                              "cells": [{"r": 0, "c": 0, "text": "좁힌 줄",
                                         "size": 10, "spacing": -12}]}])
    pt, spac, ratio = _charpr(res, "좁힌 줄")
    assert (pt, spac, ratio) == (10.0, -12, 100), (pt, spac, ratio)
    assert not _warns(res)


def test_장평도_칸_서식으로_준다(tmp_path):
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 20},
                              "cells": [{"r": 0, "c": 0, "text": "누른 줄",
                                         "size": 10, "ratio": 95}]}])
    assert _charpr(res, "누른 줄") == (10.0, 0, 95)


def test_자간과_장평을_같이_준다(tmp_path):
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 20},
                              "cells": [{"r": 0, "c": 0, "text": "둘 다",
                                         "size": 9, "spacing": -8, "ratio": 97}]}])
    assert _charpr(res, "둘 다") == (9.0, -8, 97)


def test_줄마다_자간을_따로_준다(tmp_path):
    """상자는 한 칸에 문단 여러 개다 — 긴 줄만 좁힐 수 있어야 한다."""
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 20},
                              "cells": [{"r": 0, "c": 0, "size": 10, "lines": [
                                  {"text": "제목 줄"},
                                  {"text": "긴 줄", "spacing": -10}]}]}])
    assert _charpr(res, "제목 줄")[1] == 0
    assert _charpr(res, "긴 줄")[1] == -10


def test_범위_밖_자간_장평은_무시하고_경고한다(tmp_path):
    res = _render(tmp_path, [{"grid": {"rows": 2, "cols": 20},
                              "cells": [{"r": 0, "c": 0, "text": "값 이상",
                                         "size": 10, "spacing": -80, "ratio": 400}]}])
    w = _warns(res)
    assert any("자간" in x for x in w) and any("장평" in x for x in w), w
    assert _charpr(res, "값 이상") == (10.0, 0, 100)
    assert res["status"] == "success"
