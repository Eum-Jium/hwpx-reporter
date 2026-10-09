# -*- coding: utf-8 -*-
"""
review_memo.py — 검토 의견을 문서에 **메모로** 달아 돌려주는 진입점 (모드 C)

한/글의 메모(F4 로 여는 그 메모)를 코드로 달고 읽는다. 지적을 채팅에만 남기면
받는 사람이 문서에서 그 대목을 다시 찾아야 한다 — 메모는 지적을 지적당한
자리에 붙여 놓는다. 실무에서 돌아다니는 검토본이 정확히 이 모양이다.

의존성: 없음 (stdlib)

사용법:
    import sys, os
    sys.path.insert(0, os.path.join("<스킬 폴더>", "scripts"))
    from review_memo import annotate, read_memos

    # 받은 검토본에서 남이 단 지적을 회수
    for m in read_memos(r"C:\\...\\사업계획서_검토본.hwpx"):
        print(m["number"], m["author"], m["anchor"], "→", m["text"])

    # 내 검토 의견을 달아 돌려주기 (원본은 그대로, 새 파일로 나온다)
    res = annotate(
        r"C:\\...\\사업계획서.hwpx",
        [{"anchor": "운영 기록, 설비 사진 등",
          "text": "[데이터]\\n어느 데이터를 쓰는지 확인필요"},
         {"anchor": "공용 인프라", "text": "[인프라]\\n협조 여부 확인필요"}],
        author="검토자")
    # res = {"status": "success", "added": 2, "skipped": [...], "path": "...메모.hwpx"}

**anchor 는 본문에 실제로 있는 글자 그대로여야 한다.** 못 찾으면 조용히 넘어가지
않고 skipped 에 사유가 남으므로, 돌려주기 전에 `res["skipped"]` 가 비었는지 본다.
앵커는 짧게 잡는 편이 안전하다 — 탭·각주로 쪼개진 줄은 한 조각 안에서만 찾는다.
"""
import os
import sys

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from hwpx_core.memo import annotate, add_memos, read_memos_from as read_memos  # noqa: E402

__all__ = ["annotate", "add_memos", "read_memos"]


if __name__ == "__main__":
    # 스모크: 주어진 파일의 메모를 훑는다
    if len(sys.argv) > 1:
        for m in read_memos(sys.argv[1]):
            print(f"[{m['number']}] {m['author']} — {m['anchor']}\n    "
                  + m["text"].replace("\n", "\n    "))
