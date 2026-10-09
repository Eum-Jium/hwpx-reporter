# hwpx-reader (읽기 전용 HWPX MCP)

**HWPX(한글) 문서를 열어 텍스트·표·개요·검색·메타를 추출하는 MCP 서버.**
모노레포 `packages/hwpx-reader` 의 표준 파이썬 패키지다(`src/hwpx_reader/`).
한글(HWP) 프로그램 불필요. 의존성은 `mcp` + `hwpx-core`(+lxml).

> `hwpx-writer`(문서 *생성/편집*)·`hwpx-skeleton`(표준서식 렌더)과 **별개**. 이건 *읽기* 전용.

---

## 설치와 연결

```
pip install -e packages/hwpx-core -e packages/hwpx-reader     # 개발(모노레포)
```

설치하면 콘솔스크립트 `hwpx-reader-mcp` 가 생긴다. MCP 등록(mcphost simplified 형식):

```json
{
  "mcpServers": {
    "hwpx-reader": {
      "type": "local",
      "command": ["hwpx-reader-mcp"],
      "environment": { "HWPX_READER_ROOT": "<읽기 허용 루트 — 지정 권장>" }
    }
  }
}
```

- 콘솔스크립트가 PATH 에 없으면 절대경로(`<파이썬>\Scripts\hwpx-reader-mcp.exe`)로.
- 설치 없이 소스로 실행하려면:
  `"command": ["<python>", "-m", "hwpx_reader.server"]` +
  `"environment": {"PYTHONPATH": "<hwpx-reader/src>;<hwpx-core/src>"}`.
- 호스트가 표준형이면 `"command": "hwpx-reader-mcp", "args": [], "env": {...}` 로 변환.
- 세 서버(쓰기·읽기·스켈레톤)를 함께 등록하는 예는 리포 루트 README 의 「그 밖의 패키지」 절에 있다.

### 환경변수

| 변수 | 기본 | 설명 |
|---|---|---|
| `HWPX_READER_ROOT` | (없음) | 지정 시 그 하위 경로만 읽기 허용. **미설정 = 서버 계정이 읽을 수 있는 모든 절대경로 허용** — 상시 서버에서는 지정 권장 |

---

## 제공 도구 (7개)

| 도구 | 설명 | 인자 |
|------|------|------|
| `read_text` | 전체 텍스트를 문서 순서대로 (60k자 단위, `offset` 으로 이어읽기) | `path`, `dedupe`, `include_tables`, `offset` |
| `read_tables` | 모든 표를 `[표][행][열]` 배열로 | `path` |
| `outline` | 큰 글씨 문단을 제목으로 추정한 개요 | `path`, `min_pt` |
| `read_structure` | 제목 기준 섹션 계층 구조 | `path` |
| `search` | 키워드 포함 줄 찾기(앞뒤 문맥 옵션, 200건 초과 시 `truncated`) | `path`, `keyword`, `context` |
| `info` | 제목·문단수·표수·미리보기 등 메타 | `path` |
| `read_memos` | 문서에 달린 메모(검토 의견) — 내용과 걸린 본문(`anchor`) | `path` |

모든 도구는 `path`(읽을 `.hwpx` **절대경로** — 상대경로는 거부)를 받고, 실패 시
`{"status":"error","message":"..."}` 를 반환. `read_text` 응답이 `truncated: true` 면
`next_offset` 값으로 재호출해 이어 읽는다.

## 사용 예 (LLM 프롬프트)
- "`C:\보고서\7월실적.hwpx` 읽어서 요약해줘" → `read_text`
- "'예산' 들어간 줄 다 찾아줘" → `search(keyword="예산")`
- "표만 뽑아줘" → `read_tables`  ·  "목차 알려줘" → `outline`
- "검토본에 뭐라고 달렸는지 봐줘" → `read_memos`

## 주의
- `.hwpx` 전용. `.hwp`(구형)은 한글에서 `.hwpx` 로 다시 저장 후 사용.
- `info.preview_snippet` 은 캐시된 미리보기라 실제 본문과 다를 수 있음
  (정확한 내용은 `read_text`).
- 임베드 이미지(BinData)는 메모리에 적재하지 않는다(텍스트 추출에 불필요).
