---
name: hwpx
description: Create, edit, and review HWPX (한글 워드프로세서) documents. Use this skill whenever the user wants to create, write, generate, edit, or review(검토·첨삭·레드팀) a 한글 document, HWP/HWPX file, 공문서, 보고서, 제안서, 기획서, or any Korean word processor document — even if they just say "한글로 작성해줘", "hwp 파일 만들어", "보고서 써줘", "보고서 검토해줘" without explicitly mentioning HWPX. Always use this skill for Korean document creation or report review requests.
---

# HWPX Document Creator Skill

<!-- skill-rev: 29 -->
**rev 29** — 판을 올릴 때는 위 표기만 고친다(빌드가 읽는다).
· rev 28 → 29: 표·그림·붙임 경고도 `warnings` 한 곳으로 모은다 · 블록 조립의 혼합 서식 안내를
  지금 동작(빠지고 [알림])대로 · 양식 유형을 `template_key` 로 함께 주는 법.
· rev 27 → 28: hwpx_full 의 혼합 서식 [알림] · 옛 XML 조립·템플릿 폴백 걷음 · 참고 문서 바로잡음.
· rev 25 → 27: 예시 값 정리 · 양식 미리보기 그림을 빈 그림으로. 규칙은 그대로.
· rev 24 → 25: 엔진 core 0.1.6 · skeleton 0.3.3 — 경고 값을 지금 규격으로(□ 한 줄 38 ·
  ◦ 66~70 · 골격은 마지막 단=향후계획만) · **재 보기**(`layout.py`) 신설 · 표 열 폭 자동 · 괄호 위첨자 뗌.

한글(HWPX) 문서를 **읽고 쓰는 엔진**이다. 여기 있는 것은 *hwpx 를 어떻게 다루는가*
뿐이고, ***보고서를 어떻게 쓰는가*(문체·분량·골격)와 양식 파일은 `hwpx-template`
스킬**이 들고 있다 — 그건 조직마다 다르기 때문이다.

의존성은 없다(표준 라이브러리만). 서식 값(간격·표 규격·마커)은 `hwpx_core` 의
`gaps`·`tablespec`·`markers` 가 단일 기준이라 **어느 경로로 들어와도 같은 문서**가
나온다.

## 읽기

```python
import sys, os
SKILL_DIR = "<이 SKILL.md 가 있는 폴더>"
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "vendor"))

from hwpx_core import read_members, SECTION0, iter_body_paragraphs, para_text, extract_tables
from hwpx_core.xmlcompat import parse

sec    = parse(read_members("문서.hwpx")[SECTION0])
lines  = [t for t in (para_text(p) for p in iter_body_paragraphs(sec)) if t.strip()]
tables = extract_tables(sec)          # [[[셀,…],…],…] — 표마다 행·열
```

| 하려는 일 | 부를 것 |
|---|---|
| 본문 줄을 순서대로 뽑는다 | `iter_body_paragraphs` + `para_text` |
| 표를 행·열로 뽑는다 | `extract_tables` |
| 남이 단 **메모**를 회수한다 | `review_memo.read_memos(경로)` |
| 이 파일을 **양식으로 쓸 수 있나** 진단한다 | `render_report.inspect_template(경로)` |

### 양식 선택 규칙

1. **양식 파일이 주어지면 그 양식**을 쓴다 — 먼저 `inspect_template(path)` 로
   진단하고 `render(template_path=…)`. 사용자가 준 파일이 곧 그 조직의 서식이다.
2. **"우리 양식으로"·"이 문서처럼" 인데 파일이 없으면 → 파일을 달라고 요청한다.**
   임의로 다른 양식을 골라 진행하지 않는다 — 서식이 조금만 달라도 결재에서
   되돌아오고, 사용자는 자기 서식으로 나온 줄 알고 올린다.
3. **진단이 `usable: False` 면** `missing` 을 그대로 알리고 다른 양식으로 갈지
   **묻는다**. **조용히 다른 양식으로 바꿔 찍지 않는다.**
4. **아무 말이 없으면 `plain` 이다** — 제목 + 본문뿐인 기본 양식.
   【주관】 블록도 취지 상자도 없고 **목차를 강제하지 않는다.** 계획표·안내문·
   개인 문서처럼 공문서 골격이 어울리지 않는 글이 여기로 나온다.
   `plain` 에는 **공문서 관행 검사(체언 종결·자수 규격)도 걸지 않는다** —
   그건 hwpx 의 기능이 아니라 보고서 관행이라서다.
5. **공문서를 쓸 때만** `plan`·`result`·`review` 를 고른다 — 골격 검사(마지막 단 =
   향후계획)와 문체·분량 규격이 함께 걸린다. 샘플 골격과 쓰는 법은 **`hwpx-template`
   스킬**에 있다(그 조직이 보고서를 나누는 방식이라서다).
   양식 파일(`template_path`)을 줄 때도 **유형은 `template_key` 로 함께 준다** — 안 주면
   계획 골격으로 보고, 검토보고에 「마지막 단은 향후계획」 경고가 뜬다.

서식 실측값(판면·글자·간격·표 치수)은 `references/format_spec.md` — 엔진의
`gaps`·`tablespec` 이 그 값을 코드로 들고 있다.

## 쓰기

세 갈래이고, **양식이 필요한 것과 아닌 것**이 갈린다.

| 무엇 | 부를 것 | 양식 | 자세히 |
|---|---|---|---|
| **양식을 복제해 채운다** | `render_report.render` · `render_md` | 내장(`plain` · 공문서 기본 `standard`)<br>조직 양식은 `template_path` | 위 '양식 선택 규칙' |
| **블록으로 조립한다** | `hwpx_full` — 섹션·항목·표·이미지를 코드로 쌓는다 | 없어도 된다 | `references/block_api.md` |
| **남의 문서에 메모를 단다** | `review_memo.annotate(경로, [{anchor, text}], author=)` | 없어도 된다 | `references/review.md` |

참고 문서는 이 셋을 위에서부터 **모드 A · B · C** 라 부른다.

⚠️**공문서는 `hwpx-template` 스킬과 함께 쓴다** — 거기에 조직 양식과 보고서 관행
(문체·분량·골격)이 있다. 이 스킬만으로도 `plain` 문서·블록 조립·검토는 되고, 내장
양식으로 공문서 유형을 찍을 수도 있지만 **쓰는 법은 양식 스킬에 있다.**

메모는 지적을 **지적당한 자리에 붙인다** — 채팅에만 남기면 받는 사람이 그 대목을
문서에서 다시 찾아야 한다. `anchor` 는 본문에 실제로 있는 글자 그대로여야 하고,
못 찾으면 `skipped` 에 사유가 남으니 **돌려주기 전에 그게 비었는지 본다.**
검토를 어떻게 하느냐(방법론)는 `references/review_methodology.md`.

### 줄 맨 앞 기호가 계층을 정한다

```
1. 헤딩         → 16pt HY헤드라인M, 자동 번호
□ 항목          → ☐ 정식 기호로 자동 교정, 앞칸 1
◦ 세부          → 앞칸 2
* 참고          → 한양중고딕 13pt, 앞칸 4 (각주 설명)
```

앞칸·간격·내어쓰기·글꼴은 **전부 자동**이다. 기호 앞에 공백을 넣지 말 것(자동
부여된다). `ㅁ`/`ㅇ` 같은 자모를 써도 교정된다.

- **`-` `·` 는 새로 쓰지 않는다** — 엔진은 기존 문서 호환을 위해 계속 렌더하지만
  (앞칸 3·4) 새 문서의 계층은 □→◦ 까지다.
- **각주**: 새 용어에 `단어*` 처럼 별표를 붙이면 별표만 위첨자로 올라가고,
  같은 블록 하단에 `* 단어: 설명` 참고행으로 받는다. 위첨자는 이 별표뿐이다.
- **괄호**: 줄 맨 앞 `(현황)` 은 말머리(굵게), 공백·숫자가 든 `(월 0.8억원)` 은 부연
  (2pt 작게). 그 밖의 괄호는 글자 그대로 나간다.
- `**볼드**` 는 `render()` 가 해석하지 않는다 — 아래 마크다운 경로는 걷어낸다.

### 마크다운도 받는다 — `convert_md`

마크다운을 개조식으로 옮기는 것은 **엔진 기능**이다. 규칙은 `hwpx_core.mdconv` 한
곳이 정한다 — **번역기지 편집기가 아니다**(내용을 고르거나 줄이지 않는다).

```python
from render_report import convert_md
body, tables = convert_md(md)      # (개조식 본문, 표 목록)
```

옮기는 대응표(제목·들여쓰기·인용·표·이미지·일정 줄)는 `references/markdown.md`.

양식과 함께 한 번에 찍으려면 `render_md(md, …)` — 쓰는 법은 `hwpx-template` 스킬.
`render_md` 는 md 표의 **열 폭을 내용에 맞춰** 넓힌다(`col_ratios` 를 준 표·도해는 그대로).

### 찍기 전에 재 본다 — `layout.py`

모델은 마크다운 글자만 보지 조판된 쪽을 못 본다. 그 눈을 기계가 대신한다 — `mcp/` 의
보고서 에이전트가 쓰는 **같은 기계**다(`scripts/vendor/v4_measure.py` — 에이전트 도구에서
재는 부분만 떼어 온 사본).

```python
from layout import view_layout, check_rules, sample_outline
print(view_layout(md, target_pages=2))  # 분량·쪽 자리·표 밀림/접힘·자수 안 맞는 줄(`2단 ◦ 44/70`)
print(check_rules(md, refs=자료글))      # 종결·경어체·한자·마침표·날짜 꼴·자료에 없는 수치
print(sample_outline(2))                # 장수에 맞춘 샘플 골격
```

- `view_layout` 은 렌더를 부르지 않는 어림셈이다(한/글 실물과 한두 줄 어긋날 수 있다).
  md 표는 재지만 **도해(`grid` 표)는 안 잰다.**
- 흐름·정합성(단끼리 겹침 · 표와 본문 수치)은 안 본다 — 읽어서 짚는다.

### 한글이 가진 것 — 무엇을 꺼내 쓸 수 있나

엔진의 일은 **한글의 표현력을 다 꺼내 쓸 수 있게 하는 것**이다. *어떻게 쓸지*(문체·
분량·골격)는 `hwpx-template` 스킬이 정하고, 여기는 *무엇이 가능한지*를 안다.

| 한글 기능 | 어떻게 꺼내나 | 자세히 |
|---|---|---|
| 제목 상자 · 【주관】 작성자 블록 | 양식이 들고 있다 — `fields={"title": …}` | 양식 스킬 |
| **취지 상자**(󰂐) | `intent="…"` — 비우면 상자가 통째로 사라진다 | 문구 규격은 양식 스킬 |
| 표 | `tables=[{"headers": …, "rows": …}]` | `tables_images.md` |
| ↳ 열 비율 · 셀 병합 · 셀 서식 · 행 높이 | 같은 인자에 얹는다 | `tables_images.md` |
| **그림 자리**(빈 칸 + 캡션) | `images=[{"captions": [...]}]` — 그림은 사람이 붙인다 | `tables_images.md` |
| **실제 그림 넣기** | `images=[{"path": …}]` 또는 `b64` | `tables_images.md` |
| **도해**(체계도·흐름도·단계 흐름) | 그림이 아니라 **표**로 그린다 — 굵기=중요도, 점선=묶음, 색=갈래 | `diagrams.md` |
| 각주 | 본문에 `단어*`, 아래에 `* 단어: 풀이` | 위 '기호가 계층을 정한다' |
| **붙임 별지** | `attachments=[…]` — 쪽을 새로 열고 표제로 시작 | `attachments.md` |
| **메모**(한글의 F4 메모) | `annotate(경로, [{anchor, text}], author=)` | `review.md` |
| 일정 줄 **탭 정렬** | 날짜와 내용 사이에 탭 · 한 자리 월은 앞에 공백 한 칸 | 렌더러가 보정 |
| 쪽 경계 보호 | 헤딩·표 앞·각주가 쪽에서 갈라지지 않게 **자동** | — |

### 반환값과 경고

```python
{"status": "success", "path": "출력경로.hwpx", "template": "plan",
 "applied": {...}, "skipped": [...], "body_result": {...},
 "warnings": [...골격과 어긋난 지점...], "outline": {"expected": [...], "found": [...]}}
# status != "success" 면 message 를 읽고 수정 후 재시도
# status == "success" 여도 **warnings 가 비어 있는지 본다** — 어긋난 문서도 그대로
#   나가지만 결재에서 되돌아온다. 경고를 고쳐 다시 찍을 것.
```

⚠️**`warnings` 는 비었는지 반드시 본다** — 어긋난 문서도 그대로 나가지만 결재에서
되돌아온다. 엔진은 표·그림·붙임 경고를 `body_result["warnings"]` 에 따로 싣지만
`render_report.render`·`render_md` 가 `warnings` 로 모아 준다. 무엇을 무는지:

| 표시 | 무엇을 보나 | 단일 기준 |
|------|------------|-----------|
| `[골격]` | 계획·결과의 마지막 단 = 향후계획 · 거기엔 날짜 일정 줄만(다섯 줄 상한) | `hwpx_core/outline.py` |
| `[종결]` | 체언 종결(`~다`·`~함/됨/임` 금지) · 같은 종결어 잇달아 | `hwpx_core/endings.py` |
| `[분량]` | □ 38자 이내(한 줄) · ◦ 두 줄 66~70자 · 낱말이 줄 사이에서 쪼개짐 · 끝줄 85% 미만 | `hwpx_core/linebreak.py` |
| (붙임) | 붙임이 한 쪽을 못 채움 | `hwpx_core/volume.py` |
| (표·이미지) | 마커에 해당하는 표/이미지 없음 · 마커 중복 | — |

`[골격]`·`[종결]`·자수는 고쳐 다시 찍는다. 낱말 쪼개짐·끝줄은 폭 셈이라 어절 하나로
맞출 수 있으면 맞추고, 못 맞춘 줄은 사용자에게 알린다 — 판정 원칙은 `references/warnings.md`.

## 언제 무엇을 읽나 — `references/`

**이 파일은 스킬이 발동되면 통째로 실린다.** 그래서 얇게 두고 세부는 필요할 때만
읽는다.

| 하려는 일 | 읽을 것 |
|---|---|
| 표·이미지자리를 넣는다 | `tables_images.md` |
| **체계도·흐름도를 그린다** | `diagrams.md` |
| 표·명단·법령을 붙임으로 뺀다 | `attachments.md` |
| 본문을 코드로 한 블록씩 쌓는다 | `block_api.md` |
| 남이 쓴 보고서를 검토·첨삭한다 | `review.md` · `review_methodology.md` |
| 양식 유형의 옛 키 별칭을 푼다 | `templates.md` |
| 서식 실측값(판면·글자·간격·표)을 본다 | `format_spec.md` |
| 경고가 떴다 — 무엇을 보는 건지 | `warnings.md` |
| 마크다운이 어떻게 옮겨지는지 본다 | `markdown.md` |
| 쓴 원고가 쪽에 어떻게 앉나 잰다 | 위 '찍기 전에 재 본다' (`scripts/layout.py`) |
| 샌드박스 import 가 안 된다 | `environment.md` |

**보고서를 쓰는 법과 양식은 여기 없다** — `hwpx-template` 스킬을 본다.
소재별 세부 지침은 `get_writing_guide(template_key)` 가 그때 돌려준다.
