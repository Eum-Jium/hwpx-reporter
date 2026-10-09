# hwpx-report-policy

공공기관 보고서 생성용 **LLM 출력 품질 보정 미들웨어**. 약한 모델(로컬 qwen2.5:7b)의
흔한 실패를 엔진 앞단에서 보정한다. 엔진(`hwpx-skeleton`)과 오케스트레이터(호출하는 앱) 사이의
**교체 가능한 정책 계층**이다.

## 무엇을 보정하나

| 정책 | 하는 일 |
|---|---|
| `reject_hanja` | fields/body/intent 에 한자 있으면 거부(순수 한글 요구) |
| `enforce_guide_read` | 지침 안 읽고 본문 쓰면 지침 동봉해 재작성 요구(지침 파일이 없으면 생략) |
| `enforce_nonempty_body` | body 누락 시(복구 실패하면) 거부. 끄면 빈 양식 렌더 허용 |
| `recover_body` | 모델이 body 인자 대신 답변에 본문을 쓴 경우 대화에서 복구 |
| `autofix_length` | □/◦ 줄 분량 규격 위반 시 LLM 으로 줄 단위 재작성 |
| `rescue_render` | 렌더 성공 없이 끝나면 답변에서 본문 뽑아 직접 렌더 |
| `sanitize_reply` | 응답에 한자 섞이면 도구결과 기반 한국어 요약으로 대체 |
| `template_key_fallback` | template_key 누락 시 직전 지침 유형으로 보완 |
| `language_guard` | '순수 한국어' 지시 자동 첨부 — `system_guard()`(시스템 프롬프트 1회, 권장) |

## 순수 계층 — 결합은 주입으로

외부 의존이 없다(엔진·LLM 을 몰라도 됨). 세 콜백만 주입한다:

```python
from hwpx_report_policy import ReportPolicy, WEAK_7B, QWEN_STRONG
import hwpx_skeleton as SKEL

policy = ReportPolicy(
    WEAK_7B,                          # 프리셋: 전부 켬
    llm_chat=my_async_llm_chat,       # async (messages, options) -> str  (분량 재작성용)
    guide_text=SKEL.get_writing_guide,
    guided_types=SKEL.GUIDED_TYPES,
    template_specs=SKEL.TEMPLATE_SPECS,
)
```

**`llm_chat` options 계약(백엔드 중립):** 정책이 넘기는 options 에는
`{"temperature": float}` 만 들어온다. 컨텍스트 길이·토큰 상한 등 백엔드 고유
파라미터는 콜백(어댑터) 쪽에서 결정한다. 콜백이 예외를 던지면 해당 줄의
분량 보정만 조용히 포기하고 문서 생성은 계속된다.

## 모델 교체 = 프리셋 한 줄

| 프리셋 | 용도 | 성격 |
|---|---|---|
| `WEAK_7B` | 로컬 7B (기본) | 전부 켬 |
| `FAST` | 로컬 7B, 속도 우선 | 느린 분량 자동보정만 끔 |
| `QWEN_STRONG` | **강한 Qwen 계열(권장)** | 한자 게이트만 유지, 나머지 끔 |
| `STRONG` | 강한 비-Qwen 모델 | 전부 끔 (엔진 서식만 신뢰) |
| `OFF` | 정책 완전 비활성 | `STRONG` 과 동일(별칭) |

```python
policy = ReportPolicy(QWEN_STRONG, ...)  # 한자 혼입은 Qwen 공통 습성이라 크기 무관 → 게이트 유지
# 또는 개별 토글: PolicyConfig(reject_hanja=False, autofix_length=True, ...)
```

`STRONG`/`OFF` 는 어떤 게이트도 걸지 않는다 — 빈 body 도 거부하지 않고
빈 양식으로 렌더된다(엔진 원형 동작).

환경변수로 고를 때는 `resolve_preset()` 을 쓴다 — 공백·대소문자에 관대하고,
미인식 값은 경고 문자열과 함께 기본값으로 폴백한다(무음 폴백 방지):

```python
from hwpx_report_policy import resolve_preset
cfg, name, warn = resolve_preset(os.environ.get("HWPX_POLICY"))  # "weak"/"fast"/"strong-qwen"/"strong"/"off"
if warn: log.warning(warn)
log.info("정책 프리셋 %s: %s", name, cfg.summary())
```

## API

- `ReportPolicy.system_guard() -> str` — 시스템 프롬프트에 1회 덧붙일 언어 지시(권장, 꺼져 있으면 "")
- `ReportPolicy.user_guard() -> str` — 사용자 메시지에 붙이는 구방식(하위호환)
- `await ReportPolicy.prepare_render_args(args, *, guides_read, last_guide_key, conversation)`
  → `(reject|None, effective_body, notes)`. reject 면 그대로 반환, 아니면 effective_body 로 렌더.
- `ReportPolicy.sanitize_reply(reply, events) -> str` — 이벤트에 `result_obj`(원본 dict)가
  있으면 그것을 우선 사용(2000자 절단된 `result` 문자열 파싱 실패 대비).
- `await ReportPolicy.rescue_render(last_render_args, *, conversation, last_guide_key, render_fn)`

테스트: `pytest`  (50개 — 순수함수 + 게이트 + 토글 + 2·3·5차 리뷰 회귀).
