"""
validation.py — 생성된 HWPX 파일의 구조 무결성 검사.

"한글에서 수리 없이 열림"의 대리 검사:
  - ZIP 유효 + mimetype 첫 항목(비압축)
  - 참조된 borderFillIDRef / charPrIDRef / paraPrIDRef 가 header에 존재(댕글링 없음)
  - 병합 셀: colSpan>1 인 앵커의 피병합 셀이 XML에서 제거됨(잔존 시 한글 손상)
  - secCnt 와 실제 섹션 수 일치
"""
from __future__ import annotations

import re
import zipfile
from lxml import etree

HH = "http://www.hancom.co.kr/hwpml/2011/head"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def validate_hwpx(path: str) -> list:
    """문제 목록 반환 (빈 리스트 = 정상)."""
    problems = []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        return [f"ZIP 열기 실패: {e}"]

    names = z.namelist()
    if not names or names[0] != "mimetype":
        problems.append("mimetype 이 첫 항목이 아님")
    else:
        info = z.getinfo("mimetype")
        if info.compress_type != zipfile.ZIP_STORED:
            problems.append("mimetype 이 비압축(STORED)이 아님")

    # header에서 정의된 ID 수집
    try:
        header = etree.fromstring(z.read("Contents/header.xml"))
    except Exception as e:
        return problems + [f"header.xml 파싱 실패: {e}"]

    def ids(tag):
        return {e.get("id") for e in header.iter(f"{{{HH}}}{tag}")}

    bf_ids = ids("borderFill")
    cp_ids = ids("charPr")
    pp_ids = ids("paraPr")

    sec_files = sorted([n for n in names if re.match(r"Contents/section\d+\.xml$", n)],
                       key=lambda x: int(re.search(r"\d+", x).group()))
    sec_cnt_attr = header.get("secCnt")
    if sec_cnt_attr is not None and int(sec_cnt_attr) != len(sec_files):
        problems.append(f"secCnt({sec_cnt_attr}) != 섹션 파일 수({len(sec_files)})")

    for sf in sec_files:
        try:
            sec = etree.fromstring(z.read(sf))
        except Exception as e:
            problems.append(f"{sf} 파싱 실패: {e}")
            continue
        # 댕글링 참조 검사
        for el in sec.iter():
            ref = el.get("borderFillIDRef")
            if ref is not None and ref not in bf_ids:
                problems.append(f"{sf}: borderFillIDRef={ref} 미정의")
            ref = el.get("charPrIDRef")
            if ref is not None and ref not in cp_ids:
                problems.append(f"{sf}: charPrIDRef={ref} 미정의")
            ref = el.get("paraPrIDRef")
            if ref is not None and ref not in pp_ids:
                problems.append(f"{sf}: paraPrIDRef={ref} 미정의")
        # 표 병합 무결성: 행별 colSpan 합 + 위 행 rowSpan 이월분 == 열 수
        # (세로 병합 시 피병합 셀이 제거되므로 이월분을 더해야 정확)
        for tbl in sec.iter(f"{{{HP}}}tbl"):
            col_cnt = int(tbl.get("colCnt", 0))
            pending = []   # [남은 이월 행 수, colSpan]
            for tr in tbl.findall(f"{{{HP}}}tr"):
                total = sum(cs for _, cs in pending)
                nxt = [[r - 1, cs] for r, cs in pending if r - 1 > 0]
                for tc in tr.findall(f"{{{HP}}}tc"):
                    span = tc.find(f"{{{HP}}}cellSpan")
                    cs = int(span.get("colSpan", 1)) if span is not None else 1
                    rs = int(span.get("rowSpan", 1)) if span is not None else 1
                    total += cs
                    if rs > 1:
                        nxt.append([rs - 1, cs])
                pending = nxt
                if col_cnt and total != col_cnt:
                    problems.append(
                        f"{sf}: 표 행 커버리지({total}) != colCnt({col_cnt}) "
                        f"— 병합 시 피병합 셀 잔존/과삭제 의심")
    return problems
