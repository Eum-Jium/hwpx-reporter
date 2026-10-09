# -*- coding: utf-8 -*-
"""견본 렌더 산출물이 떨어질 자리 — 리포 루트 `output/<날짜>/`.

파일 이름에 이미 `_YYYYMMDD_HHMMSS` 가 붙어 한 줄이 길다. 날짜를 폴더로 올리면
목록에서 그날 것만 골라 볼 수 있어 이름 길이에 눈이 시달리지 않는다.
이름 규칙 자체는 건드리지 않는다 — 렌더러가 정하고, 한 날 안에서 판을 가른다.
"""
import datetime
import os


def out_dir(when=None):
    """`<리포>/output/YYYY-MM-DD` 를 만들고 그 경로를 돌려준다 (기본: 오늘)."""
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(repo, "output", (when or datetime.date.today()).isoformat())
    os.makedirs(path, exist_ok=True)
    return path
