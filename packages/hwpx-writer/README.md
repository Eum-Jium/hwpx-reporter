# hwpx-mcp — 공공기관 표준서식 HWPX 보고서 생성 MCP 서버

자연어로 지시하면 공공기관 표준서식(개조식 문체, □◦-* 항목부호, 정부문서 표 테두리)에 맞는
한글 문서(`.hwpx`)를 생성하는 **MCP 서버**. MCP 호스트가 stdio 또는 HTTP로 연결해
보고서 작성 도구로 사용한다. LLM은 호스트가 담당하므로 이 서버 자체에는 OpenAI 등 외부 LLM 키가 필요 없다.

## 특징

- **동적 서식 엔진** — 폰트·색·정렬·줄간격·테두리를 런타임 생성(고정 템플릿 의존 없음)
- **셀 병합 + 셀별 스타일** — 제목행 가로 병합, 특정 셀 배경색/강조 (한글 호환 XML 병합)
- **16-상태 정부문서 표 테두리** — 헤더 이중 밑줄, 외곽 굵은선, 내부 얇은 격자
- **공공기관 표준서식 기본값** — 휴먼명조 15pt 본문 / HY헤드라인M 제목 / 여백 15·23mm
- **입력 검증 + 구조화 에러** — 잘못된 입력이 엔진을 죽이지 않고 `{status:"error"}` 반환
- **무결성 검증** — 생성물의 댕글링 참조/병합 잔존/mimetype 검사(한글 수리 방지)

## 설치

```bash
pip install -e packages/hwpx-core -e packages/hwpx-writer   # core 와 함께(로컬 경로)
```

core 를 의존성으로 선언하지 않으므로(루트 README 설치 절 참조) **둘을 함께** 설치한다.

의존성은 `pyproject.toml`에 핀 고정(`python-hwpx==2.18.0` 등). python-hwpx는 private API에
결합되어 있어 **정확 버전 핀 필수**(업그레이드 시 `pytest`로 접점 회귀 확인).

## 실행

### stdio (로컬 호스트)
```bash
hwpx-mcp
# 또는
python -m hwpx_mcp.server
```

### HTTP (원격 호스트)
```bash
MCP_TRANSPORT=http MCP_HOST=0.0.0.0 MCP_PORT=8001 MCP_AUTH_TOKEN=<발급토큰> hwpx-mcp
```

### 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MCP_TRANSPORT` | `stdio` | `stdio` \| `http` |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8001` | HTTP 바인딩 |
| `MCP_AUTH_TOKEN` | (없음) | 설정 시 HTTP bearer 인증 요구. **부착 실패 시 기동 거부(fail-closed)** |
| `HWPX_MCP_HOME` | 소스=패키지 루트 / 휠=`%LOCALAPPDATA%\hwpx-mcp` | 기본 베이스 디렉토리 |
| `HWPX_MCP_STORAGE` | `<HOME>/storage` | 문서 JSON/HWPX 저장 경로 |
| `HWPX_MCP_IMAGE_ROOT` | (없음) | `add_image` 허용 루트. **미설정 = 모든 경로 허용(경고 로그)** — 상시 서버 배포 시 지정 권장 |
| `HWPX_MCP_IMAGE_MAX_BYTES` | `20971520` (20MB) | 이미지 크기 상한(정수) |
| `HWPX_MCP_LOGLEVEL` | `INFO` | 로그 레벨(전부 stderr) |

### 호스트 연결 예 (stdio)
```json
{
  "mcpServers": {
    "hwpx-writer": { "command": "hwpx-mcp" }
  }
}
```

## MCP 툴

| 툴 | 설명 |
|----|------|
| `create_document(title, report_type, author, department, doc_date, sections)` | 문서 생성 (report_type: 기획/현황/회의/행사) |
| `add_section(document_id, heading, key, after_section_key)` | 섹션 추가 |
| `set_section_body(document_id, section_key, text, append)` | 본문 입력 (□◦-* 항목부호, **볼드** 자동 · 교체 시 표/이미지 블록은 보존) |
| `add_bullet(document_id, section_key, text, level, marker)` | 항목부호 단락 (level 1~5) |
| `add_table(document_id, section_key, headers, rows, col_ratios, style)` | 표 (style=gov/plain) |
| `merge_cells(document_id, section_key, table_index, r1, c1, r2, c2)` | ★ 셀 병합 |
| `update_table(document_id, section_key, table_index, headers, rows, cell)` | ★ 표/셀 수정 (cell=셀별 스타일) |
| `add_image(document_id, section_key, image_path\|image_b64, caption, width_mm)` | 이미지 임베드 |
| `add_image_placeholder(document_id, section_key, captions)` | 빈 그림칸 표 |
| `add_toc(document_id, enabled)` | 목차 (`enabled=false` 로 해제) |
| `get_document(document_id)` | 문서 조회 |
| `list_documents(limit)` | 최근 수정순 문서 목록 (id 유실 시 복구 경로) |
| `render_hwpx(document_id)` | HWPX 파일 생성 → 경로 반환 |

MCP 프롬프트 `gov_report_guide` 는 공공기관 작성 규칙/작업 흐름을 제공(호스트 시스템 프롬프트로 사용).

## 필수 폰트 (대상 PC)

문서는 폰트를 **참조만** 하고 임베드하지 않으므로, **한글로 여는 PC에 아래 폰트가 설치**되어야
표준 서식이 정확히 재현된다(미설치 시 대체 폰트로 열려 열너비/줄바꿈이 어긋남).

- HY헤드라인M, 휴먼명조, 한양중고딕, 맑은 고딕

서버 시작 시 폰트 존재를 점검해 경고 로그를 남긴다. 배포 대상(호스트 실행 PC 또는 최종 열람 PC)에
폰트를 사전 설치하거나, 폰트 임베딩(추후 옵션)을 고려한다.

## 테스트

```bash
pytest
```
- 골든 렌더 구조, "한글 무수리 열림" 스모크, 셀 병합, 열너비, **python-hwpx private API 버전 가드**.

## 알려진 제약

- **이미지**: 바이너리는 BinData 에 임베드되고 본문에 `<hp:pic>` 으로 들어간다(`engine/images.py`
  의 `EMBED_PIC` 기본 켬). 실패하면 캡션 박스 자리표로 떨어진다.
- **폰트 임베딩 미적용** — 위 "필수 폰트" 참조.
- **python-hwpx 버전 결합** — 내부 API(`tc.cell`, `_root._headers[0]`, 헤더 dirty) 사용.
  업그레이드 시 반드시 `pytest tests/test_version_guard.py` 로 회귀 확인.

## 아키텍처

```
서버(FastMCP) ─ 툴 ─ DocumentStore(JSON+filelock) ─ 블록 JSON
                                                    └→ 렌더 엔진(python-hwpx 동적 빌더)
                                                         ├ 16-상태 표 테두리
                                                         ├ 셀 병합(XML 직접)
                                                         └ 무결성 검증
```

LLM(호스트) = 의미/구성 담당, 엔진 = 서식/표준 보장.

서버 골격·문서 저장소(DocumentStore)·작성 프롬프트와 표 테두리·열 너비 규칙은
이승준([@tmdwnsdl](https://github.com/tmdwnsdl))과 함께 만든 [kor_hwpx_generator](https://github.com/tmdwnsdl/kor_hwpx_generator)에서
가져왔다. 렌더링은 고정 템플릿 대신 동적 엔진으로 바꿨다(셀 병합 추가).
