"""MCP 툴: 정상 플로우 + 입력 검증(구조화 에러)."""
import pytest
import hwpx_mcp.server as srv


def fn(name):
    obj = getattr(srv, name)
    return getattr(obj, "fn", obj)


def test_full_flow(tmp_path, monkeypatch):
    cd = fn("create_document")(title="테스트 보고서", report_type="기획", department="○○처")
    assert cd["status"] == "success"
    did = cd["document_id"]
    sk = cd["sections"][0]["key"]

    assert fn("set_section_body")(document_id=did, section_key=sk,
                                  text="□ 항목\n◦ 하위")["status"] == "success"
    at = fn("add_table")(document_id=did, section_key=sk,
                         headers=["a", "b"], rows=[["1", "2"]])
    assert at["status"] == "success" and at["table_index"] == 0
    assert fn("merge_cells")(document_id=did, section_key=sk, table_index=0,
                             r1=0, c1=0, r2=0, c2=1)["status"] == "success"
    assert fn("update_table")(document_id=did, section_key=sk, table_index=0,
                              cell={"row": 1, "col": 0, "bg": "#FFEE00"})["status"] == "success"
    rh = fn("render_hwpx")(document_id=did)
    assert rh["status"] == "success" and rh["size_bytes"] > 0


def test_invalid_report_type():
    r = fn("create_document")(title="x", report_type="없는유형")
    assert r["status"] == "error" and r["stage"] == "create_document"


def test_ragged_table_rejected():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    r = fn("add_table")(document_id=did, section_key=sk,
                        headers=["a", "b", "c"], rows=[["1", "2"]])   # 열 수 불일치
    assert r["status"] == "error" and "직사각형" in r["message"]


def test_bad_hex_rejected():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_table")(document_id=did, section_key=sk, headers=["a"], rows=[["1"]])
    r = fn("update_table")(document_id=did, section_key=sk, table_index=0,
                           cell={"row": 0, "col": 0, "bg": "red"})
    assert r["status"] == "error"


def test_merge_out_of_range_rejected():
    did = fn("create_document")(title="x")["document_id"]
    sk = fn("get_document")(document_id=did)["sections"][0]["key"]
    fn("add_table")(document_id=did, section_key=sk, headers=["a", "b"], rows=[["1", "2"]])
    r = fn("merge_cells")(document_id=did, section_key=sk, table_index=0,
                          r1=0, c1=0, r2=9, c2=9)
    assert r["status"] == "error"


def test_missing_section_rejected():
    did = fn("create_document")(title="x")["document_id"]
    r = fn("set_section_body")(document_id=did, section_key="없는키", text="y")
    assert r["status"] == "error" and "없음" in r["message"]


def test_unknown_document_rejected():
    r = fn("get_document")(document_id="doc_nonexistent")
    assert r["status"] == "error"
