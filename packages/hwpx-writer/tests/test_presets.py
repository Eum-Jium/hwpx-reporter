"""프리셋: 4개 보고서 유형 모두 기본 섹션으로 유효한 HWPX 생성."""
import json
from pathlib import Path

import pytest

from hwpx_mcp.store import DEFAULT_SECTIONS_BY_TYPE, DocumentStore, doc_to_blocks_json
from hwpx_mcp.engine.render import render_from_blocks
from hwpx_mcp.validation import validate_hwpx

REGISTRY = Path(__file__).resolve().parent.parent / "presets" / "registry.json"


def test_registry_matches_store():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for rt, spec in reg["report_types"].items():
        headings = [s["heading"] for s in DEFAULT_SECTIONS_BY_TYPE[rt]]
        assert headings == spec["sections"], f"{rt} 섹션 불일치"


@pytest.mark.parametrize("report_type", ["기획", "현황", "회의", "행사"])
def test_report_type_renders_valid(report_type, tmp_path, monkeypatch):
    store = DocumentStore()
    doc = store.create_report(title=f"{report_type} 테스트", report_type=report_type,
                              department="○○처")
    # 각 섹션에 간단 본문
    for s in doc.sections:
        s.blocks = [{"type": "paragraph", "text": f"□ {s.heading} 관련 핵심 내용\n◦ 세부 사항"}]
    store.save(doc)
    blocks = doc_to_blocks_json(doc)
    out = str(tmp_path / f"{report_type}.hwpx")
    render_from_blocks(blocks, out)
    assert validate_hwpx(out) == []
