# hwpx-skeleton

공공기관 표준서식 HWPX **스켈레톤 렌더 엔진** — 독립 MCP 서버이자 파이썬 라이브러리.

미리 만들어 둔 표준서식 스켈레톤(`assets/templates/*.hwpx`)에 필드·본문을 채워
완성 `.hwpx` 를 생성한다. 제목 파란 박스·표·폰트 등 원본 서식은 그대로 유지되고,
본문의 간격·계층·내어쓰기는 코드가 자동 적용한다. 골격·종결·줄 길이 규격에 어긋난 줄은
`warnings` 로 알린다(고치지는 않는다).

**결정론적 엔진만 담는다.** 한자 차단·분량 자동보정·본문 복구 같은 LLM(소형모델)
방어로직은 포함하지 않는다 — 그건 상위 오케스트레이터/정책 계층(`hwpx-report-policy`)의 몫.

## 설치

```bash
pip install -e packages/hwpx-core -e packages/hwpx-skeleton      # 개발(core 와 함께)
# 또는 빌드해서 배포
```

## MCP 서버로 실행

```jsonc
// mcpServers 아래 (command·args·env 형식)
"hwpx-skeleton": {
  "command": "hwpx-skeleton-mcp",                   // 콘솔 스크립트(설치 시)
  "env": { "HWPX_SKELETON_STORAGE": "<출력 폴더>" }
}
```

설치 없이 소스로 직접 띄우려면:

```jsonc
"command": "<python>", "args": ["-m", "hwpx_skeleton.server"],
"env": {
  "PYTHONPATH": "<...>/packages/hwpx-skeleton/src",
  "HWPX_SKELETON_STORAGE": "<출력 폴더>"
}
```

### 도구 (3)

| 도구 | 역할 |
|---|---|
| `list_templates` | 스켈레톤 목록 + 유형별 입력 필드 |
| `get_writing_guide` | 유형별 세부 작성지침(md) 반환 — 계획·결과·검토(plain 은 지침 없음) |
| `render_from_skeleton` | 필드·본문 채워 `.hwpx` 생성 |

## 라이브러리로 사용

```python
import hwpx_skeleton as HS

HS.render(
    template_key="plan",
    fields={"title": "AI 기반 업무 자동화 방안"},
    body="1. 추진배경\n□ ...\n◦ ...",
    intent="AI 운영 전환 방안 보고",
    output_dir="./output",
)
```

## 자산 재생성

양식을 바꾸려면 `assets/templates/` 의 hwpx 를 한/글로 고친다. 고친 뒤에는 미리보기 그림
(`Preview/PrvImage.png`)을 빈 그림으로 둔다 — 결과물마다 그대로 실린다(`test_template_preview`).
