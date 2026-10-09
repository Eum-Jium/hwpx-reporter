# -*- coding: utf-8 -*-
"""HWPML 네임스페이스 상수 + 태그 헬퍼."""

# HWPML 2011 네임스페이스 URI
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"   # 문단(body)
HH = "http://www.hancom.co.kr/hwpml/2011/head"        # 머리(header/charPr 등)


def local(tag) -> str:
    """네임스페이스를 제거한 로컬 태그명. 예: '{...}charPr' → 'charPr'.

    주석·PI 노드는 tag 가 문자열이 아니라 함수라 QName 이 ValueError 를 던진다 —
    이런 노드는 "" 를 반환해 호출부의 이름 비교에서 자연히 걸러지게 한다.
    """
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]
