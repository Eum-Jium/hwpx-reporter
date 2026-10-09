# -*- coding: utf-8 -*-
"""파서 중립 헬퍼 — lxml 전용 API(nsmap·getparent) 없이 트리를 다룬다.

목표는 **엔진 한 벌**이다. 종전에는 같은 일(간격·마커·표·본문 조립)을 모드 A
(lxml, renderer.py)와 모드 B(stdlib, hwpx_full.py)가 두 벌로 갖고 있어, 한쪽만
고치면 다른 쪽이 어긋났다(08-15~16 에 모아찍기·표 규격을 매번 양쪽에 고쳤다).
lxml 의존이 실제로는 nsmap·getparent 뿐이라(XPath 는 아예 안 쓴다) 이 둘만
걷어내면 표준 라이브러리 ElementTree 로도 같은 코드가 돈다.

**stdlib 만 쓴다** — gaps.py·markers.py·tablespec.py 와 같은 이유.
"""

# HWPX 기본 네임스페이스(폴백용). 문서마다 접두사가 달라질 수 있으므로 값은
# 되도록 실물 트리에서 뽑고, 못 찾을 때만 이 값을 쓴다.
HP_DEFAULT = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH_DEFAULT = "http://www.hancom.co.kr/hwpml/2011/head"
HC_DEFAULT = "http://www.hancom.co.kr/hwpml/2011/core"


def uri_of(el) -> str:
    """요소의 태그에 박힌 네임스페이스 URI. 네임스페이스가 없으면 빈 문자열."""
    tag = getattr(el, "tag", "")
    if isinstance(tag, str) and tag.startswith("{"):
        return tag[1:tag.index("}")]
    return ""


def local_name(el) -> str:
    """접두사를 뗀 태그 이름(lxml 의 QName(...).localname 대체)."""
    tag = getattr(el, "tag", "")
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def ns_by_local(root, name: str, default: str = "") -> str:
    """트리에서 localname 이 name 인 첫 요소의 네임스페이스 URI.

    section0.xml 은 루트가 `{section}sec` 이라 루트 태그만 봐서는 본문(hp)
    네임스페이스를 알 수 없다 — 안쪽 `hp:p` 를 찾아 뽑는다.
    """
    if local_name(root) == name:
        return uri_of(root)
    for el in root.iter():
        if local_name(el) == name:
            return uri_of(el)
    return default


def hp_uri(sec, default: str = HP_DEFAULT) -> str:
    """본문(paragraph) 네임스페이스 — sec 트리 안의 p 에서 뽑는다."""
    return ns_by_local(sec, "p", default) or default


def hh_uri(hdr, default: str = HH_DEFAULT) -> str:
    """머리(head) 네임스페이스 — header.xml 은 루트가 곧 hh:head 다."""
    return uri_of(hdr) or default


def hc_uri(hdr, default: str = HC_DEFAULT) -> str:
    """핵심(core) 네임스페이스 — 셀 배경(fillBrush)·변환행렬이 이 이름공간이다.

    header.xml 루트는 hh:head 라 루트 태그로는 알 수 없다. 안쪽 fillBrush 에서
    뽑고, 배경이 하나도 없는 문서면 기본값으로 떨어진다.
    """
    return ns_by_local(hdr, "fillBrush", "") or default


def parent_map(root) -> dict:
    """{자식: 부모} 사전. ElementTree 에 getparent 가 없어 대신 쓴다.

    ⚠️ 트리를 고치면(요소 삽입·삭제) 무효가 된다 — 수정 전에 만들어 쓰거나
    수정 후 다시 만든다. 문서 한 편은 수천 노드라 만드는 비용은 무시해도 된다.
    """
    return {child: parent for parent in root.iter() for child in parent}


# ── 파서 어댑터 ────────────────────────────────────────────
# 엔진을 한 벌로 두기 위해 표준 라이브러리 ElementTree 를 쓴다. lxml 과 다른 점은
# 세 가지뿐이라 여기서 흡수한다:
#   · 접두사 보존 — ET 는 등록해 두지 않으면 ns0: 로 직렬화해 한/글이 못 읽는다
#   · XML 선언 — ET 의 tostring 에는 standalone 인자가 없다
#   · 미사용 네임스페이스 선언 — ET 는 실제로 쓰인 접두사만 다시 써낸다(아래)
import re as _re
import xml.etree.ElementTree as ET       # noqa: E402  (어댑터 아래에서만 쓴다)

_XMLNS_RE = _re.compile(rb'xmlns:([\w.-]+)="([^"]+)"')
# 한/글이 쓰는 형태 그대로 — `?>` 앞에 공백이 있고 뒤에 줄바꿈이 없다.
_DECL = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
_DECL_RE = _re.compile(rb'<\?xml[^>]*\?>')
# 루트 여는 태그: 이름 + 속성들 + 닫기. 속성값에 `"` 는 못 들어간다(ET 가 이스케이프).
_ROOT_RE = _re.compile(rb'(<[\w:.-]+)((?:\s+[\w:.-]+="[^"]*")*)(\s*/?>)')


def register_prefixes(data: bytes) -> None:
    """원본에 선언된 네임스페이스 접두사를 ET 전역 표에 등록한다."""
    for prefix, uri in _XMLNS_RE.findall(data[:8192]):
        ET.register_namespace(prefix.decode(), uri.decode())


def parse(data: bytes):
    """HWPX 조각(bytes)을 트리로. 접두사를 먼저 등록해 직렬화 때 보존되게 한다."""
    register_prefixes(data)
    return ET.fromstring(data)


def _root_decls(data: bytes):
    """조각의 루트 여는 태그에 선언된 xmlns 목록 [(접두사, 선언문), …]."""
    body = _DECL_RE.sub(b"", data[:8192], count=1).lstrip()
    m = _ROOT_RE.match(body)
    if not m:
        return []
    return [(p, b'xmlns:%s="%s"' % (p, u))
            for p, u in _XMLNS_RE.findall(m.group(2))]


def _restore_xmlns(body: bytes, like: bytes) -> bytes:
    """`like` 의 루트에 있던 xmlns 선언을 되살린다.

    ET 는 **실제로 쓰인 접두사만** 다시 써낸다. XML 로는 흠이 없지만, 한/글은
    조각마다 늘 같은 선언 묶음(16개)을 적어 두고 구버전은 그것이 줄어든 파일을
    아예 안 연다 — 실측으로 확인했다(선언만 복원하면 열린다). 그래서 원본이
    선언해 둔 것은 안 쓰이더라도 그대로 돌려놓는다.
    """
    src = _root_decls(like)
    if not src:
        return body
    m = _ROOT_RE.search(body)
    if not m:
        return body
    out = _root_decls(body)
    out_map = dict(out)
    # 같은 접두사를 다른 URI 로 매고 있으면 출력 쪽이 옳다 — 원본 것을 버린다.
    merged = [d for p, d in src if out_map.get(p, d) == d]
    merged += [d for p, d in out if p not in dict(src)]
    others = _re.sub(rb'\s+xmlns:[\w.-]+="[^"]*"', b"", m.group(2))
    root = m.group(1) + b"".join(b" " + d for d in merged) + others + m.group(3)
    return body[:m.start()] + root + body[m.end():]


def serialize(el, like: bytes = b"") -> bytes:
    """트리를 HWPX 가 기대하는 형태(UTF-8·standalone 선언)로 직렬화.

    like: 이 트리를 떠온 **원본 조각의 바이트**. 주면 XML 선언과 루트의 xmlns
    선언 묶음을 원본 그대로 돌려놓는다 — 안 주면 한/글 기본형으로 적는다.
    기존 문서를 고쳐 쓰는 경로(memo·renderer)는 **반드시 준다**.

    빈 태그는 lxml 과 같은 `<tag/>` 로 맞춘다 — ET 기본은 `<tag />`(공백)이라
    기존 문서와 무의미한 diff 가 생기고, 문자열로 대조하는 검증이 어긋난다.
    """
    body = ET.tostring(el, encoding="UTF-8", xml_declaration=False)
    body = _restore_xmlns(body.replace(b" />", b"/>"), like)
    decl = _DECL_RE.match(like.lstrip()) if like else None
    return (decl.group() if decl else _DECL) + body
