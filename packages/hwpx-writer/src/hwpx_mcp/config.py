"""
config.py — 스토리지 경로, 로깅(stderr), 폰트 체크, python-hwpx 버전 가드, 전송/인증 설정.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# ── 스토리지 경로 (환경변수로 오버라이드 가능) ────────────
def _default_base_dir() -> Path:
    """소스 체크아웃이면 패키지 루트, 휠 설치본이면 사용자 데이터 디렉토리.
    (site-packages 기준 상대경로를 쓰면 파이썬 설치 디렉토리를 오염시키고,
    쓰기금지 경로면 서버 기동 자체가 불가)"""
    src_root = Path(__file__).resolve().parent.parent.parent
    if (src_root / "pyproject.toml").exists():
        return src_root
    if os.name == "nt":
        return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "hwpx-mcp"
    return Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "hwpx-mcp"


BASE_DIR = Path(os.getenv("HWPX_MCP_HOME") or _default_base_dir())
STORAGE_DIR = Path(os.getenv("HWPX_MCP_STORAGE") or (BASE_DIR / "storage"))
JSON_DIR = STORAGE_DIR / "json"
HWPX_DIR = STORAGE_DIR / "hwpx"


def ensure_storage_dirs() -> None:
    """스토리지 디렉토리 생성 — import 시점이 아닌 실제 사용 시점에 호출."""
    for _d in (STORAGE_DIR, JSON_DIR, HWPX_DIR):
        _d.mkdir(parents=True, exist_ok=True)

# ── 전송/인증 ────────────────────────────────────────────
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()   # stdio | http
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")             # HTTP bearer 토큰 (설정 시 인증 요구)

# ── python-hwpx 버전 핀 (private API 결합) ────────────────
PINNED_HWPX_VERSION = "2.18.0"


def configure_logging():
    """
    모든 로그를 stderr로. [stdio MCP는 stdout이 JSON-RPC 채널이므로 오염 금지]
    python-hwpx 자체 로거의 잡음은 낮춘다.
    """
    root = logging.getLogger()
    if not root.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(h)
    root.setLevel(os.getenv("HWPX_MCP_LOGLEVEL", "INFO").upper())
    # python-hwpx 내부 경고(masterPage/history fallback 등) 잡음 억제
    for noisy in ("hwpx", "hwpx.package", "hwpx.opc"):
        logging.getLogger(noisy).setLevel(logging.ERROR)


def check_hwpx_version(strict: bool = False):
    """python-hwpx 버전 확인 — 핀과 다르면 경고(또는 strict 시 예외)."""
    try:
        import hwpx
        ver = getattr(hwpx, "__version__", None)
    except Exception as e:
        raise RuntimeError(f"python-hwpx import 실패: {e}")
    log = logging.getLogger("hwpx_mcp.config")
    if ver and ver != PINNED_HWPX_VERSION:
        msg = (f"python-hwpx 버전 불일치: 설치={ver}, 핀={PINNED_HWPX_VERSION}. "
               f"private API 접점(tc.cell / _root._headers) 회귀 가능 — 테스트 권장.")
        if strict:
            raise RuntimeError(msg)
        log.warning(msg)
    return ver


def check_fonts():
    """필수 표준서식 폰트 설치 여부 확인(Windows). 없으면 경고 리스트 반환."""
    from .engine.constants import REQUIRED_FONTS
    log = logging.getLogger("hwpx_mcp.config")
    missing = []
    # 시스템 폰트 + 사용자별 설치 폰트(Win10 1809+) 모두 확인
    font_dirs = [
        Path(os.getenv("SystemRoot", "C:/Windows")) / "Fonts",
        Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
    ]
    installed = set()
    for d in font_dirs:
        try:
            if d.exists():
                installed |= {p.name.lower() for p in d.glob("*")}
        except Exception:
            pass
    # 파일명 매핑(대략) — 정확 매칭이 어려우므로 존재 힌트만
    hint = {
        "HY헤드라인M": "h2hdrm.ttf",
        "휴먼명조": "hmkmm.ttf",
        "한양중고딕": "h2gtrm.ttf",
        "맑은 고딕": "malgun.ttf",
    }
    for f in REQUIRED_FONTS:
        fn = hint.get(f, "").lower()
        if fn and installed and fn not in installed:
            missing.append(f)
    if missing:
        log.warning("필수 폰트 미확인(대상 PC 서식 붕괴 가능): %s", ", ".join(missing))
    return missing
