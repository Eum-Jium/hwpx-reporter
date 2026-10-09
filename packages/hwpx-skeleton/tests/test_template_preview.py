# -*- coding: utf-8 -*-
"""양식의 미리보기 그림(Preview/PrvImage.png)은 빈 그림이어야 한다.

렌더러는 양식 zip 을 통째로 이어받으므로 이 그림이 **모든 결과 문서에 그대로 실린다**
— 탐색기 썸네일로 보이는 그림이다. 양식을 한/글로 고쳐 저장하면 그 화면이 다시 찍히므로,
견본 글자를 바꿔도 그림은 따로 비워야 한다. 글자 검사는 그림 속 글자를 못 본다.

그림 속 글자를 읽을 수는 없으니 크기로 잰다 — 흰 724×1024 는 3.6KB, 글자가 찍힌
미리보기는 19KB 를 넘었다.
"""
import glob
import os
import zipfile

import pytest

from hwpx_skeleton import renderer as R

TEMPLATES = sorted(glob.glob(os.path.join(R.TEMPLATE_DIR, "*.hwpx")))
LIMIT = 5000


def test_templates_found():
    assert TEMPLATES, R.TEMPLATE_DIR


@pytest.mark.parametrize("path", TEMPLATES, ids=os.path.basename)
def test_preview_image_is_blank(path):
    with zipfile.ZipFile(path) as z:
        if "Preview/PrvImage.png" not in z.namelist():
            return
        size = len(z.read("Preview/PrvImage.png"))
    assert size <= LIMIT, (
        f"{os.path.basename(path)}: 미리보기 그림 {size}B — 원본 문서가 찍혀 있을 수 있다. "
        "빈 그림으로 바꿀 것")
