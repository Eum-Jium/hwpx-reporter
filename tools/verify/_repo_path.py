# -*- coding: utf-8 -*-
"""리포 안의 packages/ 를 **설치본보다 앞세운다**. 임포트하는 것만으로 동작한다.

같은 이름(`hwpx_core`·`hwpx_skeleton` …)의 다른 판이 파이썬에 설치돼 있으면 그쪽을
가로채 쓴다. 그대로 두면 검증 도구가 **옛 코드를 검증하고도 통과했다고 보고한다** —
도구가 거짓말을 하는 것이 도구가 없는 것보다 나쁘다.

그래서 이 리포의 도구가 스스로 자기 소스를 앞에 둔다. pytest 쪽은 `pytest.ini` 의
`pythonpath` 가 같은 일을 한다.

    import _repo_path          # noqa: F401  — 다른 임포트보다 **먼저**
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC = [os.path.join(_REPO, "packages", name, "src") for name in (
    "hwpx-core", "hwpx-skeleton", "hwpx-reader", "hwpx-report-policy", "hwpx-writer")]

for _p in reversed(_SRC):
    if os.path.isdir(_p) and _p not in sys.path[:len(_SRC)]:
        sys.path.insert(0, _p)
