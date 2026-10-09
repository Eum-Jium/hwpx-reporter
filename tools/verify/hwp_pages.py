# -*- coding: utf-8 -*-
"""한/글 COM 으로 hwpx 를 열어 실제 쪽수를 세고 PDF 로 저장한다."""
import os
import sys

import win32com.client as win32

if len(sys.argv) < 2:
    print("사용법: python tools/verify/hwp_pages.py <열어 볼.hwpx>")
    sys.exit(2)
src = os.path.abspath(sys.argv[1])
pdf = os.path.splitext(src)[0] + ".pdf"

hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
try:
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
except Exception:
    pass
# 보안 모듈이 미등록이면 Open 에서 파일 접근 승인 대화상자가 뜬다(승인은 약 1시간
# 유지). 창을 숨긴 채로 두면 대화상자도 안 보여 무한 대기하므로 반드시 창을 띄운다.
try:
    hwp.XHwpWindows.Item(0).Visible = True
except Exception:
    pass
hwp.Open(src, "HWPX", "forceopen:true")

# 문서 끝으로 이동해 현재 쪽 번호 = 총 쪽수
hwp.Run("MoveDocEnd")
pages = hwp.KeyIndicator()[3]
print("총 쪽수:", pages)

act = hwp.CreateAction("FileSaveAsPdf")
pset = act.CreateSet()
act.GetDefault(pset)
pset.SetItem("FileName", pdf)
pset.SetItem("Format", "PDF")
act.Execute(pset)
hwp.Quit()
print("PDF:", pdf, os.path.exists(pdf))
