# -*- coding: utf-8 -*-
"""HWPX(zip) 입출력 원시함수. reader·skeleton·빌더가 공유."""
from __future__ import annotations
import os
import zipfile
from typing import Dict, List

# 자주 쓰는 멤버 경로
SECTION0 = "Contents/section0.xml"
HEADER = "Contents/header.xml"


class HwpxError(Exception):
    """HWPX 처리 실패(파일 없음/형식 오류 등)."""


def validate_hwpx(path: str) -> None:
    """읽기 가능한 .hwpx 인지 검증. 실패 시 HwpxError."""
    if not path or not isinstance(path, str):
        raise HwpxError("경로가 비어 있습니다.")
    if not os.path.exists(path):
        raise HwpxError(f"파일을 찾을 수 없습니다: {path}")
    if not os.path.isfile(path):
        raise HwpxError(f"파일이 아닙니다(폴더?): {path}")
    if os.path.splitext(path)[1].lower() == ".hwp":
        raise HwpxError(
            ".hwp(구형 바이너리)는 지원하지 않습니다. .hwpx 로 저장 후 이용하세요.")
    if not zipfile.is_zipfile(path):
        raise HwpxError("HWPX(zip) 형식이 아닙니다. 파일이 손상되었을 수 있습니다.")


def read_members(path: str, names_filter=None) -> Dict[str, bytes]:
    """HWPX(zip) 멤버를 {이름: bytes} 로 읽는다.

    names_filter: 멤버명 → bool 콜러블. 텍스트 추출처럼 XML 만 필요한 호출이
    임베드 이미지(BinData/, 수백 MB 가능)까지 통째로 적재하지 않도록 선별
    로드에 쓴다. None 이면 전체(쓰기 경로처럼 재저장할 때 필수)."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if names_filter is not None:
            names = [n for n in names if names_filter(n)]
        return {n: z.read(n) for n in names}


def write_hwpx(path: str, members: Dict[str, bytes]) -> str:
    """{이름: bytes} 를 HWPX(zip)로 저장. mimetype 은 STORED 로 첫 항목(HWPX 규칙).

    저장 경로를 반환한다.
    """
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        if "mimetype" in members:
            z.writestr(zipfile.ZipInfo("mimetype"), members["mimetype"],
                       compress_type=zipfile.ZIP_STORED)
        for name, data in members.items():
            if name == "mimetype":
                continue
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return path


def section_names(members: Dict[str, bytes]) -> List[str]:
    """Contents/sectionN.xml 멤버들을 N 순서로 정렬해 반환."""
    names = [n for n in members
             if n.startswith("Contents/section") and n.endswith(".xml")]

    def _idx(n: str) -> int:
        base = os.path.basename(n)[len("section"):-len(".xml")]
        return int(base) if base.isdigit() else 0

    return sorted(names, key=_idx)
