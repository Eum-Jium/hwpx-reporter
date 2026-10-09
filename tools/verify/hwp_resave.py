# -*- coding: utf-8 -*-
"""한/글이 우리 파일을 **어떻게 이해했는지** 되묻는다 — 열어서 다시 저장시킨 뒤 대조.

파일이 열린다는 것은 XML 이 문법적으로 멀쩡하다는 뜻일 뿐이다. 한/글이 그 구조를
자기 모델로 **인식했는지**는 알 수 없다 — 인식 못 한 조각은 조용히 무시되고,
화면을 보지 않는 이상 티가 안 난다. 그래서 한 번 더 저장시킨다:

    우리 hwpx → 한/글이 연다 → 한/글이 다시 hwpx 로 저장 → 우리 리더로 읽어 대조

재저장본에 남아 있다 = 한/글이 파싱해 자기 모델에 넣었다가 다시 써냈다 = 이해했다.
사라졌거나 값이 바뀌었으면 우리가 쓴 XML 을 한/글이 다르게 읽었다는 뜻이다.

이 절차로 잡은 실제 버그: 메모의 `Command` 파라미터에 든 숫자 두 자리를 난수로
보고 아무 값이나 넣었더니, 한/글이 그것을 FILETIME 으로 읽어 작성시각을 **2785년**
으로 고쳐 저장했다(파일은 멀쩡히 열리고 메모도 떴다).

사용법:
    python tools/verify/hwp_resave.py <검사할.hwpx> [저장할.hwpx]

저장 경로를 안 주면 원본 옆에 `<이름>_재저장.hwpx` 로 낸다. 원본은 안 건드린다.
종료코드: 차이가 없으면 0, 있으면 1(자동 검사에 걸어 쓸 수 있게).

⚠️ 한/글 창을 띄운 채로 돈다 — 보안 모듈이 미등록이라 접근 승인 대화상자가 뜰 수
있고(승인은 약 1시간 유지), 창을 숨기면 그 대화상자도 안 보여 무한 대기한다.
`hwp_pages.py` 와 같은 이유다.
"""
import os
import sys

import _repo_path            # noqa: F401  — 설치본 그림자 차단
import hwpx_core as C

# 보고문에 '—' 가 들어간다 — cp949 콘솔에서 그대로 두면 출력하다 죽는다.
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):        # noqa — 리다이렉트된 경우
    pass


def resave(src: str, dst: str) -> str:
    """한/글로 열어 dst 로 다시 저장시킨다. 저장 경로 반환."""
    import win32com.client as win32
    hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:                       # noqa — 미등록이면 대화상자로 받는다
        pass
    try:
        hwp.XHwpWindows.Item(0).Visible = True
    except Exception:                       # noqa
        pass
    hwp.Open(src, "HWPX", "forceopen:true")
    hwp.SaveAs(dst, "HWPX", "")
    hwp.Quit()
    return dst


def _lines(path):
    from hwpx_reader import core
    return core.core_read_text(path, dedupe=False).split("\n")


def _diff_text(before, after):
    """본문이 통째로 사라진 곳만 본다 — 한/글은 빈 문단 정리 등 사소한 손질을 한다."""
    lost = [ln for ln in before if ln.strip() and ln not in after]
    gained = [ln for ln in after if ln.strip() and ln not in before]
    return lost, gained


def _diff_memos(before, after):
    """메모는 값까지 대조한다 — 개수만 세면 2785년 같은 값 변조를 놓친다."""
    keys = ("number", "author", "created", "text", "anchor")
    out = []
    if len(before) != len(after):
        out.append(f"개수 {len(before)} → {len(after)}")
    for i, (b, a) in enumerate(zip(before, after), start=1):
        for k in keys:
            if b.get(k) != a.get(k):
                out.append(f"{i}번 메모 {k}: {b.get(k)!r} → {a.get(k)!r}")
    return out


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0])
        print("사용법: python tools/verify/hwp_resave.py <검사할.hwpx> [저장할.hwpx]")
        return 2
    src = os.path.abspath(argv[1])
    C.validate_hwpx(src)
    if len(argv) > 2:
        dst = os.path.abspath(argv[2])
    else:
        stem, ext = os.path.splitext(src)
        dst = stem + "_재저장" + ext

    before_text, before_memos = _lines(src), C.read_memos_from(src)
    print(f"원본   : {os.path.basename(src)} — 본문 {len(before_text)}줄 · "
          f"메모 {len(before_memos)}건")

    resave(src, dst)
    after_text, after_memos = _lines(dst), C.read_memos_from(dst)
    print(f"재저장 : {os.path.basename(dst)} — 본문 {len(after_text)}줄 · "
          f"메모 {len(after_memos)}건")

    lost, gained = _diff_text(before_text, after_text)
    memo_diff = _diff_memos(before_memos, after_memos)

    if not lost and not gained and not memo_diff:
        print("\n차이 없음 — 한/글이 우리가 쓴 대로 읽고 그대로 다시 썼다.")
        return 0

    print("\n한/글이 다르게 읽은 곳:")
    for ln in lost:
        print(f"  - 사라짐 : {ln[:60]}")
    for ln in gained:
        print(f"  + 생김   : {ln[:60]}")
    for d in memo_diff:
        print(f"  ! 메모   : {d}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
