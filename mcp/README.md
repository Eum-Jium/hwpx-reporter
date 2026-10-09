# MCP 타입 — 회사에 넣은 보고서 에이전트

한국수자원공사 사내 챗봇에 넣어 쓰는 보고서 에이전트다. GenOS(Flowise 기반 에이전트 플랫폼)의
Agentflow 하나와 MCP 도구 11종으로 되어 있다. 큰 모델 하나가 도구를 골라 부르며 골격 → 본문 →
검토 → `.hwpx` 파일까지 사용자와 대화로 만든다.

엔진은 이 리포의 `packages/`(hwpx-core · hwpx-skeleton)다 — 스킬 타입과 같은 엔진이라 같은 원고면
같은 문서가 나온다. hwpx-reader 는 첨부 원본을 직접 파싱하는 갈래용이다(지금은 꺼 두고 전처리기 청크를 읽는다).

> 이 폴더는 비공개 원본에서 기계로 뽑은 공개 사본이다. 도구 파일은 주석과 내부 함수 설명을
> 걷었고 코드는 같다(도구 11종의 설명은 플랫폼 화면에 뜨므로 그대로 둔다).

## 들어 있는 것

| 파일 | 무엇 | 넣는 곳 |
|---|---|---|
| `mcp_tool_v2_report_agent.py` | MCP 도구 11종 | 플랫폼 「MCP 도구」 자산의 코드칸에 통째로 |
| `workflow/agentflow_v4.json` | Agentflow 4노드 — `1_Start` · `2_Download refs` · `3_Load state` · `4A_Agent`. 프롬프트 · 전처리 코드 · Memory 설정이 안에 들어 있다 | 플랫폼에서 임포트 |
| `prompt/agent_k.txt` | `4A_Agent` 의 시스템 프롬프트 | 워크플로 안에 이미 있다 — 눈으로 대조할 때 |
| `prompt/ref_extract_v2.js` | `2_Download refs` 의 전처리 코드(첨부 파일의 청크를 모아 `[참고자료 N]` 블록으로) | 워크플로 안에 이미 있다 |

전처리 코드는 GenOS 가 넣어 주는 변수 둘을 읽는다 — `$vars.genosUploaded`(첨부 파일의 청크)와
`$vars.genosUserInfo`(요청자 이름 → `[환경]` 블록). 다른 Flowise 에서는 이 둘을 같은 꼴로 채워 주지 않으면
첨부가 「(첨부 없음)」으로 읽힌다.

## 설치 순서

1. **엔진 휠**을 플랫폼이 받는 패키지 저장소에 올린다.

   ```bash
   pip wheel --no-deps packages/hwpx-core packages/hwpx-skeleton packages/hwpx-reader -w dist/
   ```

2. **도구 자산**을 만든다 — 패키지 칸에 `hwpx-core` · `hwpx-skeleton` · `hwpx-reader` · `lxml` 을 고르고
   (`requests` 는 컨테이너에 기본으로 있다) 코드칸에 `mcp_tool_v2_report_agent.py` 를 통째로 붙여 넣는다.
   전역 `mcp`(FastMCP)는 플랫폼이 넣어 준다.
3. **워크플로**를 임포트한다(`workflow/agentflow_v4.json`).
4. 임포트가 담지 못하는 자리를 **손으로 채운다** — 하나라도 빠지면 그 일을 조용히 못 한다.

   | 노드 | 채울 것 |
   |---|---|
   | `3_Load state` (Tool 노드) | 도구 드롭다운에서 `build_state` — 고른 뒤 인자 셋(`refs`=`{{$flow.state.refs_raw}}` · `key`=`{{$flow.chatId}}` · `part`=`agent`)이 그대로인지 본다. `part` 가 비면 [검토]·[목록]·[샘플 골격]이 빠진다 |
   | `4A_Agent` (Agent 노드) | Tools 칸에 여덟 — `load_refs` · `load_draft` · `view_layout` · `check_rules` · `save_outline` · `save_draft` · `save_state` · `generate_hwpx_report` |
   | `4A_Agent` | temperature `0.5` · 모델 이름(비어 있다 — 플랫폼에서 고른다) |

   `4A_Agent` 의 Memory 켜짐 · Window 10 은 JSON 에 담겨 있다 — 임포트 뒤 그대로인지 본다.
5. 모델은 **큰 모델**로 고른다. 작은 모델은 첫 저장이 튕겼을 때 다시 부르지 못했다.

## 환경변수

| 변수 | 기본 | 뜻 |
|---|---|---|
| `HWPX_PUBLIC_HOST` | (없음) | 초안·결과 파일의 공개 주소(`https://<플랫폼 주소>:<포트>`). 업로드할 때 함께 보내고, `load_draft` 가 URL 을 받을 때 이 주소와 플랫폼 CDN 주소만 허용한다 — **꼭 지정한다** |
| `LLMOPS_CDN_API_SERVICE_SERVICE_HOST` · `…_PORT` | `llmops-cdn-api-service` · `8080` | 플랫폼 CDN(파일 업로드) 서비스. `http://<host>:<port>/minio/upload/temp` 로 올리고 presigned URL 을 받는다 |
| `HWPX_DRAFT_DIR` | `/tmp/hwpx-drafts` | 초안 로컬 사본. 컨테이너가 다시 뜨면 비워지고, 그때는 URL 로 회수한다 |
| `HWPX_OUT_DIR` | `/tmp/hwpx-out` | `generate_hwpx_report` 가 업로드 전에 `.hwpx` 를 만드는 자리 |

다른 MCP 서버에 얹을 때는 파일 앞에 `from mcp.server.fastmcp import FastMCP` · `mcp = FastMCP("hwpx-report-agent")`
를, 끝에 `mcp.run()` 을 두고 띄운다(`pip install mcp requests` 와 엔진 패키지). 다만 파일 저장은 위 업로드
API(presigned URL)를 전제로 한다.

## 도구 11종

| 도구 | 하는 일 | 붙는 곳 |
|---|---|---|
| `build_state` | 이번 턴에 읽을 재료(자료 목차 · 저장본 · 제목·목적·분량 · 검토 · 샘플 골격)를 한 덩어리로 | `3_Load state` |
| `load_refs` | 참고자료 본문을 꺼내 읽는다(번호·파일명·낱말로) | `4A_Agent` |
| `load_draft` | 직전 초안을 회수한다(통째 · 골격 · 한 단) | `4A_Agent` |
| `view_layout` | 쓴 글이 쪽에 어떻게 앉나 — 자수·줄 수·장수·표가 쪽 금에 걸리는 곳 | `4A_Agent` |
| `check_rules` | 문장 규칙 검토 — 서술형 종결 · 경어체 · 한자 · 긴 날짜 꼴 · 자료에 없는 수치 | `4A_Agent` |
| `save_outline` | 골격 원고를 저장한다 | `4A_Agent` |
| `save_draft` | 쓴 단을 저장본에 갈아 끼운다(안 온 단은 그대로) | `4A_Agent` |
| `save_state` | 제목·목적·분량과 검토 목록을 저장한다 | `4A_Agent` |
| `generate_hwpx_report` | 저장본을 표준서식 `.hwpx` 로 만들고 다운로드 링크를 낸다 | `4A_Agent` |
| `save_refs` · `probe_refs` | 옛 배선 호환 · 첨부 원본 경로 진단(배선은 안 문다) | — |

작성 규칙(샘플 골격 · □ 30~38자 · ◦ 66~70자 · 향후계획은 일정 줄 다섯 줄까지 · 체언 종결)은 스킬 타입과 같다.
