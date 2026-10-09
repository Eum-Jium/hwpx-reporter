# -*- coding: utf-8 -*-
"""유형별 세부 작성지침(guidelines/*.md) 접근 — 엔진에 동봉된 정적 자산."""
from __future__ import annotations
import logging
import os

from hwpx_core import outline as _outline
from typing import Optional

logger = logging.getLogger("hwpx_skeleton.guides")

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
GUIDELINES_DIR = os.path.join(_ASSETS, "guidelines")


def _scan_guided_types() -> frozenset:
    """지침 md 가 실제로 있는 유형 집합.

    손으로 나열하지 않고 파일에서 파생한다 — 나열이 파일과 어긋나면 지침이
    있는데도 None 을 주거나(신규 유형 누락) 정책의 빈 본문 게이트가 조용히 꺼진다.
    옛 유형 키는 별칭으로 풀어서 찾는다(basic → review).

    자산이 통째로 빠진 배포(package-data 누락 등)에서도 **import 는 성공해야
    한다** — 지침 없이도 렌더 자체는 동작하므로 경고만 남기고 빈 집합을 준다.
    """
    try:
        names = os.listdir(GUIDELINES_DIR)
    except OSError as e:
        logger.warning("작성지침 자산을 읽지 못했다(%s) — 지침 없이 진행한다: %s",
                       GUIDELINES_DIR, e)
        return frozenset()
    return frozenset(f[:-3] for f in names if f.endswith(".md"))


GUIDED_TYPES = _scan_guided_types()


def get_writing_guide(template_key: str) -> Optional[str]:
    """유형별 세부지침 md 원문을 반환. 없으면 None.

    옛 유형 키(planning·training_plan …)로 물어도 새 두 종의 지침을 준다 —
    분류는 hwpx_core.outline 단일 기준.
    """
    key = _outline.resolve((template_key or "").strip())
    path = os.path.join(GUIDELINES_DIR, f"{key}.md")
    if key not in GUIDED_TYPES or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()
