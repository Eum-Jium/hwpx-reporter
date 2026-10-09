# -*- coding: utf-8 -*-
"""5차 코드리뷰 수정 회귀 — skeleton 지침 레지스트리.

GUIDED_TYPES 는 guidelines/*.md 파생(plan·result·review) — 옛 키는 별칭으로 찾는다.
"""
import os

from hwpx_skeleton import guides


def test_guided_types_derived_from_files():
    stems = {f[:-3] for f in os.listdir(guides.GUIDELINES_DIR) if f.endswith(".md")}
    assert guides.GUIDED_TYPES == stems


def test_every_type_is_guided():
    assert guides.GUIDED_TYPES == frozenset({"plan", "result", "review"})
    assert "검토의견" in guides.get_writing_guide("review")
    assert "추진방안" in guides.get_writing_guide("plan")
    assert "추진결과" in guides.get_writing_guide("result")
    # 옛 유형 키로 물어도 지금 키의 지침을 준다
    assert guides.get_writing_guide("sample") == guides.get_writing_guide("plan")
    assert guides.get_writing_guide("training_result") == guides.get_writing_guide("result")


def test_unknown_type_still_none():
    assert guides.get_writing_guide("no_such_type") is None
    assert guides.get_writing_guide("") is None
