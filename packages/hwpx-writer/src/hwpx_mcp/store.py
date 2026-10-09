"""
store.py — 문서 저장소 + 데이터 모델.

kor_hwpx_generator/chat_service.py 의 DocumentStore / ReportDocument / Section 이식.
프로덕션: filelock 로 동시쓰기 보호, 확장 블록(병합·셀스타일·이미지) 지원.
"""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from filelock import FileLock

from .config import JSON_DIR, ensure_storage_dirs

logger = logging.getLogger("hwpx_mcp.store")


# ── 데이터 모델 ──────────────────────────────────────────
@dataclass
class Section:
    key: str
    heading: str
    blocks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportDocument:
    document_id: str
    doc_type: Literal["report"] = "report"
    title: str = "제목 없음"
    report_type: str = "기획"
    meta: Dict[str, Any] = field(default_factory=dict)
    sections: List[Section] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()


# 보고서 유형별 기본 섹션 — create_document 에 sections 를 주지 않았을 때만 쓴다.
# SYSTEM_PROMPT 는 샘플 4단을 먼저 제안해 sections 로 넘기게 한다.
DEFAULT_SECTIONS_BY_TYPE = {
    "기획": [
        {"key": "background", "heading": "추진배경"},
        {"key": "status", "heading": "현황 및 문제점"},
        {"key": "plan", "heading": "추진방향 및 계획"},
        {"key": "detail", "heading": "세부 추진계획"},
        {"key": "effect", "heading": "기대효과"},
        {"key": "schedule", "heading": "향후 일정"},
    ],
    "현황": [
        {"key": "overview", "heading": "개요"},
        {"key": "status", "heading": "현황"},
        {"key": "issue", "heading": "문제점 및 시사점"},
        {"key": "plan", "heading": "향후 계획"},
    ],
    "회의": [
        {"key": "overview", "heading": "회의 개요"},
        {"key": "attendees", "heading": "참석자"},
        {"key": "discussion", "heading": "주요 논의사항"},
        {"key": "decision", "heading": "결정사항"},
        {"key": "action", "heading": "향후 조치"},
    ],
    "행사": [
        {"key": "overview", "heading": "행사 개요"},
        {"key": "progress", "heading": "추진경과"},
        {"key": "content", "heading": "행사 내용"},
        {"key": "result", "heading": "결과 및 성과"},
        {"key": "plan", "heading": "향후 계획"},
    ],
}
DEFAULT_SECTIONS = DEFAULT_SECTIONS_BY_TYPE["기획"]


class DocumentStore:
    """JSON 파일 기반 문서 저장소 (filelock 동시성 보호)."""

    _ID_RE = re.compile(r"^doc_[0-9a-f]{8}$")

    def __init__(self):
        ensure_storage_dirs()
        self._dir = Path(JSON_DIR)
        self._lock = FileLock(str(self._dir / ".store.lock"))

    def _path(self, document_id: str) -> Path:
        # id 가 경로 문자열로 직결되므로 형식을 입구에서 강제 —
        # '../' 류 경로 이탈과 LLM 이 환각한 id("output/doc_1" 등)를 함께 차단.
        if not isinstance(document_id, str) or not self._ID_RE.match(document_id):
            raise ValueError(
                f"document_id 형식 오류: {document_id!r} — create_document 가 "
                "반환한 'doc_xxxxxxxx'(소문자 16진수 8자리)를 그대로 사용하라")
        return self._dir / f"{document_id}.json"

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 수정순 문서 목록 — 오케스트레이터가 document_id 를 유실했을 때의
        유일한 복구 경로(없으면 JSON_DIR 에 파일이 있어도 도구로는 못 찾는다)."""
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 20
        items = []
        with self._lock:
            for p in self._dir.glob("doc_*.json"):
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                items.append({"document_id": raw.get("document_id", p.stem),
                              "title": raw.get("title", ""),
                              "report_type": raw.get("report_type", ""),
                              "updated_at": raw.get("updated_at", "")})
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items[:limit]

    def _to_dict(self, doc: ReportDocument) -> dict:
        return {
            "document_id": doc.document_id,
            "doc_type": doc.doc_type,
            "title": doc.title,
            "report_type": doc.report_type,
            "meta": doc.meta,
            "sections": [asdict(s) for s in doc.sections],
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }

    def _from_dict(self, raw: dict) -> ReportDocument:
        sections = [Section(**s) for s in raw.get("sections", [])]
        data = {k: v for k, v in raw.items() if k != "sections"}
        return ReportDocument(sections=sections, **data)

    def _write(self, doc: ReportDocument) -> None:
        """임시 파일에 쓴 뒤 os.replace — 쓰기 도중 중단돼도 원본이 절단되지 않는다."""
        path = self._path(doc.document_id)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(self._to_dict(doc), ensure_ascii=False, indent=2),
            encoding="utf-8")
        os.replace(tmp, path)

    def _load(self, document_id: str) -> ReportDocument:
        path = self._path(document_id)
        if not path.exists():
            raise ValueError(f"document_id '{document_id}' 없음")
        return self._from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, doc: ReportDocument) -> None:
        doc.touch()
        with self._lock:
            self._write(doc)

    def get(self, document_id: str) -> ReportDocument:
        with self._lock:
            return self._load(document_id)

    @contextmanager
    def modify(self, document_id: str):
        """락을 잡은 채 읽기→수정→쓰기.

        get()/save() 를 따로 부르면 두 도구 호출이 같은 스냅샷을 읽고 나중 저장이
        먼저 것을 덮어써 블록이 무음 소실된다(FastMCP 는 sync 도구를 워커 스레드에서
        병렬 실행). 본문에서 예외가 나면 저장하지 않는다.
        """
        with self._lock:
            doc = self._load(document_id)
            doc.touch()
            yield doc
            self._write(doc)

    def create_report(self, title: str, report_type: str = "기획",
                      author: str = "", department: str = "",
                      doc_date: str = "",
                      sections: Optional[List[Dict[str, str]]] = None) -> ReportDocument:
        document_id = f"doc_{uuid4().hex[:8]}"
        section_defs = sections or DEFAULT_SECTIONS_BY_TYPE.get(report_type, DEFAULT_SECTIONS)
        doc = ReportDocument(
            document_id=document_id,
            title=title,
            report_type=report_type,
            meta={
                "author": author,
                "department": department,
                "date": doc_date or datetime.now().strftime("%Y. %m. %d."),
            },
            sections=[Section(key=s["key"], heading=s["heading"]) for s in section_defs],
        )
        self.save(doc)
        return doc

    def find_section(self, doc: ReportDocument, section_key: str) -> Optional[Section]:
        return next((s for s in doc.sections if s.key == section_key), None)


# ── 문서 → 렌더 블록 JSON 브리지 (확장) ──────────────────
def doc_to_blocks_json(doc: ReportDocument) -> dict:
    """
    DocumentStore 문서 → render_from_blocks 입력 형식.
    확장 표 필드(col_ratios/merges/cell_styles), image/bullet 블록 통과.
    """
    blocks: List[dict] = []
    if doc.meta.get("include_toc"):
        blocks.append({"type": "toc",
                       "entries": [f"{i}. {s.heading}" for i, s in enumerate(doc.sections, 1)]})
    for i, section in enumerate(doc.sections, 1):
        blocks.append({"type": "heading", "text": f"{i}. {section.heading}", "level": 2})
        for block in section.blocks:
            bt = block.get("type")
            if bt == "paragraph":
                blocks.append({"type": "paragraph", "text": block.get("text", "")})
            elif bt == "bullet":
                blocks.append({"type": "bullet", "text": block.get("text", ""),
                               "level": block.get("level", 1), "marker": block.get("marker")})
            elif bt in ("simple_table", "table"):
                tb = {"type": "table",
                      "headers": block.get("headers", []),
                      "rows": block.get("rows", []),
                      "style": block.get("style", "gov")}
                for opt in ("col_ratios", "merges", "cell_styles"):
                    if block.get(opt):
                        tb[opt] = block[opt]
                blocks.append(tb)
            elif bt == "image_table":
                blocks.append({"type": "image_table", "captions": block.get("captions", [])})
            elif bt == "image":
                blocks.append({k: v for k, v in block.items()})
    return {"title": doc.title, "meta": doc.meta, "blocks": blocks}
