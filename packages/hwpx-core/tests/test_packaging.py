# -*- coding: utf-8 -*-
"""내부 패키지 이름이 의존성으로 새어 나가지 않는지 지킨다.

이 이름들(hwpx-core·hwpx-skeleton·…)은 어떤 인덱스에도 없다. pyproject 에 적으면
pip 이 해결하려고 **공개 PyPI** 를 뒤지므로, 누가 그 이름을 선점해 두면 엉뚱한
패키지가 들어온다(dependency confusion). 적어도 얻는 것은 없다 — 어차피 로컬
경로로 함께 설치해야 하기 때문이다. 그래서 선언을 금지하고 판 확인은 임포트
시점에 한다. 이 테스트는 그 선언이 다시 기어들어오는 것을 막는다.
"""
import os
import re

import pytest

import hwpx_core as C

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PKGS = os.path.join(_REPO, "packages")
# 폴더 이름이 아니라 **배포 이름**으로 적는다 — writer 폴더의 배포명은 hwpx-mcp 다.
_INTERNAL = ("hwpx-core", "hwpx-reader", "hwpx-skeleton", "hwpx-mcp",
             "hwpx-writer", "hwpx-report-policy")


def _dependency_lines(pyproject_text):
    """dependencies = [...] 블록 안에서 주석을 뺀 실제 항목만."""
    m = re.search(r"^dependencies = \[(.*?)^\]", pyproject_text, re.S | re.M)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def test_no_internal_package_declared_as_dependency():
    seen = 0
    for name in sorted(os.listdir(_PKGS)):
        path = os.path.join(_PKGS, name, "pyproject.toml")
        if not os.path.exists(path):
            continue
        seen += 1
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for dep in _dependency_lines(text):
            for internal in _INTERNAL:
                assert internal not in dep, (
                    f"{name}/pyproject.toml 이 내부 패키지 {internal} 를 의존성으로 "
                    f"선언했다 — 공개 PyPI 해석 여지가 생긴다: {dep}")
    assert seen == 5, f"패키지 5개를 기대했는데 {seen}개를 봤다"


def test_readme_documents_bundled_install():
    with open(os.path.join(_REPO, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert "pip install -e packages/hwpx-core" in readme
    assert "require_version" in readme, "판 확인 방식이 README 에 없다"


def test_require_version_accepts_current_series():
    C.require_version("테스트", "0.1")          # 예외 없이 지나가야 한다


def test_require_version_rejects_other_series():
    with pytest.raises(ImportError) as e:
        C.require_version("테스트", "9.9")
    assert "hwpx-core 9.9.x" in str(e.value)
    assert "pip install -e packages/hwpx-core" in str(e.value)   # 할 일을 알려 준다
