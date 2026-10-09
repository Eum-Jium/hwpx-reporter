# -*- coding: utf-8 -*-
"""4차 코드리뷰(도구 중심) 수정 회귀 — writer."""
import zipfile

import hwpx_mcp.server as srv


def fn(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


_PNG_1PX = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


# ── m4: create_document sections key 중복 거부 ────────────
def test_create_document_duplicate_section_keys_rejected():
    r = fn("create_document")(title="x", sections=[
        {"key": "a", "heading": "가"}, {"key": "a", "heading": "나"}])
    assert r["status"] == "error" and "중복" in r["message"]


# ── m3: add_section 자동 키 충돌 시 다음 번호로 전진 ──────
def test_add_section_auto_key_skips_taken_numbers():
    did = fn("create_document")(title="x", sections=[
        {"key": "sec_2", "heading": "사용자 지정"}])["document_id"]
    r = fn("add_section")(document_id=did, heading="자동 키")
    assert r["status"] == "success"
    assert r["section_key"] == "sec_3"   # sec_2 선점 → 다음 번호


# ── m6: add_bullet 선두 기호 제거 + marker 검증 ───────────
def test_add_bullet_strips_leading_marker():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    assert fn("add_bullet")(document_id=did, section_key=sk,
                            text="□ 확대 필요", level=1)["status"] == "success"
    blocks = fn("get_document")(document_id=did)["sections"][0]["blocks"]
    assert blocks[-1]["text"] == "확대 필요"   # 렌더가 □ 를 붙이므로 중복 방지


def test_add_bullet_keeps_negative_number():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_bullet")(document_id=did, section_key=sk, text="-5% 절감", level=3)
    blocks = fn("get_document")(document_id=did)["sections"][0]["blocks"]
    assert blocks[-1]["text"] == "-5% 절감"   # 공백 없는 '-' 는 음수로 취급


def test_add_bullet_marker_validation():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    r = fn("add_bullet")(document_id=did, section_key=sk, text="y", marker="a b c")
    assert r["status"] == "error" and "marker" in r["message"]


# ── m7: 표 셀 스칼라 검증 + None 빈 셀 렌더 ───────────────
def test_add_table_rejects_object_cells():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    r = fn("add_table")(document_id=did, section_key=sk,
                        headers=["a", "b"], rows=[[{"k": 1}, "x"]])
    assert r["status"] == "error" and "객체/배열" in r["message"]


def test_none_cell_renders_empty_not_none():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    assert fn("add_table")(document_id=did, section_key=sk,
                           headers=["a", "b"], rows=[["값", None]])["status"] == "success"
    rh = fn("render_hwpx")(document_id=did)
    assert rh["status"] == "success"
    with zipfile.ZipFile(rh["file_path"]) as z:
        xml = z.read("Contents/section0.xml").decode("utf-8")
    assert ">None<" not in xml


# ── m9: add_image 소스 정확히 하나 + width_mm 범위 ────────
def test_add_image_both_sources_rejected():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    r = fn("add_image")(document_id=did, section_key=sk,
                        image_path="C:/no/such.png", image_b64=_PNG_1PX)
    assert r["status"] == "error" and "동시" in r["message"]


def test_add_image_width_bounds():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    r = fn("add_image")(document_id=did, section_key=sk,
                        image_b64=_PNG_1PX, width_mm=5)
    assert r["status"] == "error" and "width_mm" in r["message"]
    ok = fn("add_image")(document_id=did, section_key=sk,
                         image_b64=_PNG_1PX, width_mm=120)
    assert ok["status"] == "success"


# ── m10: add_toc enabled=false 로 해제 가능 ───────────────
def test_add_toc_toggle_off():
    did = fn("create_document")(title="x")["document_id"]
    assert fn("add_toc")(document_id=did)["include_toc"] is True
    r = fn("add_toc")(document_id=did, enabled=False)
    assert r["status"] == "success" and r["include_toc"] is False
    assert fn("get_document")(document_id=did)["meta"]["include_toc"] is False


# ── 항목부호 줄맞춤 = 스켈레톤 규칙 (사용자 실파일 평가 피드백) ──
# 왼쪽여백 0 + 앞칸은 '공백 문자'(□1·◦2칸) + 내어쓰기 intent 만 음수(실측치).
# 문단 들여쓰기(left)로 계단을 만들면 표준서식과 어긋난다.
def test_bullet_alignment_matches_skeleton_convention():
    from lxml import etree
    import zipfile

    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("set_section_body")(document_id=did, section_key=sk,
                           text="□ 상위 항목\n◦ 하위 항목")
    rh = fn("render_hwpx")(document_id=did)
    with zipfile.ZipFile(rh["file_path"]) as z:
        hdr = etree.fromstring(z.read("Contents/header.xml"))
        sec = etree.fromstring(z.read("Contents/section0.xml"))

    def margins(root):
        out = {}
        for p in root.iter():
            if etree.QName(p.tag).localname != "paraPr":
                continue
            left = intent = None
            for el in p.iter():
                ln = etree.QName(el.tag).localname
                if ln == "intent" and intent is None:
                    intent = el.get("value")
                if ln == "left" and left is None:
                    left = el.get("value")
            out[p.get("id")] = (left, intent)
        return out

    pp = margins(hdr)
    found = {}
    for p in sec.iter():
        if etree.QName(p.tag).localname != "p":
            continue
        text = "".join(t.text or "" for t in p.iter()
                       if etree.QName(t.tag).localname == "t")
        for mk, lead, hang in (("□", " □ ", "-6140"), ("◦", "  ◦ ", "-7720")):
            if mk in text and "항목" in text:
                assert text.startswith(lead), f"{mk} 앞칸 공백 불일치: {text!r}"
                assert pp[p.get("paraPrIDRef")] == ("0", hang), (
                    f"{mk} 여백/내어쓰기 불일치: {pp[p.get('paraPrIDRef')]}")
                found[mk] = True
    assert found == {"□": True, "◦": True}


# ── ☐(U+2610, 표준서식 원본) 입력도 □(U+25A1) 로 정규화 ──────────
# render._detect_line 이 ☐ 를 □ 로 매핑 → 내어쓰기·앞칸이 □ 와 동일하게 걸리고
# 본문에 ☐ 가 중복으로 남지 않아야 한다(hwpx_core.markers 와 경로 일관).
def test_ballot_box_u2610_normalized_to_white_square():
    from lxml import etree
    import zipfile

    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("set_section_body")(document_id=did, section_key=sk, text="☐ 표준서식 항목")
    rh = fn("render_hwpx")(document_id=did)
    with zipfile.ZipFile(rh["file_path"]) as z:
        hdr = etree.fromstring(z.read("Contents/header.xml"))
        sec = etree.fromstring(z.read("Contents/section0.xml"))

    pp = {}
    for p in hdr.iter():
        if etree.QName(p.tag).localname != "paraPr":
            continue
        left = intent = None
        for el in p.iter():
            ln = etree.QName(el.tag).localname
            if ln == "intent" and intent is None:
                intent = el.get("value")
            if ln == "left" and left is None:
                left = el.get("value")
        pp[p.get("id")] = (left, intent)

    hit = False
    for p in sec.iter():
        if etree.QName(p.tag).localname != "p":
            continue
        text = "".join(t.text or "" for t in p.iter()
                       if etree.QName(t.tag).localname == "t")
        if "표준서식 항목" in text:
            assert "☐" not in text, f"U+2610 미정규화: {text!r}"
            assert text.startswith(" □ "), f"□ 정규화/앞칸 불일치: {text!r}"
            assert pp[p.get("paraPrIDRef")] == ("0", "-6140")
            hit = True
    assert hit
