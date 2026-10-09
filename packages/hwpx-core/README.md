# hwpx-core

HWPX(한글 워드프로세서 XML) 문서를 다루는 **공용 저수준 툴킷**.
`hwpx-reader`(읽기 MCP)·`hwpx-writer`(쓰기 MCP)·`hwpx-skeleton`(표준서식 렌더 MCP)이
공유하는 원시 함수를 담는다 — 자체 MCP 서버는 없다.

## 제공 기능

- **zipio** — HWPX(zip) 멤버 읽기/쓰기(`read_members`/`write_hwpx`, mimetype STORED 규칙,
  `names_filter` 로 BinData 제외 선별 로드), 섹션 정렬(`section_names`), `validate_hwpx`
- **XML 헬퍼** — 네임스페이스(HP), 문단 텍스트 추출(`para_text`), 본문 문단 순회,
  표 추출(`extract_tables`)
- **charmap / HWPUNIT** — 글자 크기 매핑 파싱(`parse_charmap`, `para_charsize`) 등
  한글 고유 단위 처리
- **memo** — 메모(검토 의견) 읽기/쓰기(`read_memos`·`add_memos`·`annotate`).
  메모 구조를 아는 곳을 한 군데로 둔다 — 읽기와 쓰기가 갈리면 우리가 단 메모를
  우리가 못 읽는다

## 설치

```
pip install -e packages/hwpx-core   # 리포 안에서(로컬 경로)
```

PyPI 에는 올리지 않았다 — `pip install hwpx-core` 로 받으면 같은 이름의 남의 패키지가
들어올 수 있다.

소비 패키지(reader/writer/skeleton)는 이 패키지를 pyproject 에 적지 않고, 임포트 시점에
`require_version()` 으로 판을 확인한다. API 를 바꾸면 세 소비자를 함께 올린다.
