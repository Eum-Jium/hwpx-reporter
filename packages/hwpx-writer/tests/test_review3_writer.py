"""3차 코드리뷰(소형 Qwen 전제) 수정 회귀 — writer."""
import pytest
import hwpx_mcp.server as srv


def fn(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


def _new_doc():
    cd = fn("create_document")(title="리뷰3 테스트", report_type="기획")
    return cd["document_id"], cd["sections"][0]["key"]


# ── M13: set_section_body 기본 교체가 표·이미지를 보존 ─────
def test_set_section_body_preserves_tables():
    did, sk = _new_doc()
    fn("set_section_body")(document_id=did, section_key=sk, text="□ 첫 본문")
    fn("add_table")(document_id=did, section_key=sk,
                    headers=["a", "b"], rows=[["1", "2"]])
    r = fn("set_section_body")(document_id=did, section_key=sk, text="□ 다듬은 본문")
    assert r["status"] == "success" and r["preserved_blocks"] == 1
    doc = fn("get_document")(document_id=did)
    types = [b["type"] for b in doc["sections"][0]["blocks"]]
    assert "table" in types                       # 표 생존
    assert types.count("paragraph") == 1          # 문단은 교체(1개)
    assert types.index("paragraph") < types.index("table")   # 원래 위치 유지


def test_set_section_body_append_still_appends():
    did, sk = _new_doc()
    fn("set_section_body")(document_id=did, section_key=sk, text="□ 본문1")
    r = fn("set_section_body")(document_id=did, section_key=sk,
                               text="□ 본문2", append=True)
    assert r["status"] == "success" and r["block_count"] == 2


# ── m12: document_id 형식 검증(경로 이탈·환각 id 차단) ─────
@pytest.mark.parametrize("bad", ["../json/doc_deadbeef", "doc_XYZ12345",
                                 "output/doc_1", "doc:1", "doc_12345678a", ""])
def test_document_id_format_rejected(bad):
    r = fn("get_document")(document_id=bad)
    assert r["status"] == "error" and "document_id" in r["message"]


# ── m19: list_documents — id 유실 시 복구 경로 ─────────────
def test_list_documents_finds_created():
    did, _ = _new_doc()
    r = fn("list_documents")(limit=100)
    assert r["status"] == "success" and r["count"] >= 1
    assert any(d["document_id"] == did for d in r["documents"])


# ── m11: sections 문자열 배열은 명확한 메시지로 거부 ───────
def test_sections_string_array_rejected():
    r = fn("create_document")(title="x", sections=["추진배경", "현황"])
    assert r["status"] == "error" and "객체 배열" in r["message"]
