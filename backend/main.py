"""FastAPI 앱 진입점"""

import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router, ws_router
from backend.config import load_config, get_config, save_config
from backend.services.profile_manager import ProfileManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── SERVER_MODE 결정 ──────────────────────────────────────────
# "remote" = Docker/외부 공개: 랜딩 페이지 + /api/remote/classify만 허용
# "local"  = 로컬 개발/관리: 모든 엔드포인트 + 관리 UI 허용
SERVER_MODE = os.environ.get("SERVER_MODE", "local").lower()

app = FastAPI(title="AI File Organizer", version="2.0.0")

# CORS - 원격 클라이언트도 접속 가능하게
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 보안 미들웨어: SERVER_MODE=remote 일 때 허용 경로만 통과 ──
# 허용 목록 (allowlist) 방식 — 목록에 없으면 전부 차단
_REMOTE_ALLOWED_PREFIXES = (
    "/api/health",
    "/api/remote/classify",
    "/api/profiles",          # GET만 — 클라이언트가 프로파일 목록 필요
    "/api/ollama/status",     # 서버 상태 확인 (읽기 전용)
)

_REMOTE_BLOCKED_METHODS = {
    # profiles는 GET(읽기)만 허용, 수정/삭제 차단
    "/api/profiles": {"POST", "PUT", "DELETE"},
}


@app.middleware("http")
async def server_mode_guard(request: Request, call_next):
    """SERVER_MODE=remote 일 때 파일시스템 접근 엔드포인트를 차단한다."""
    if SERVER_MODE != "remote":
        return await call_next(request)

    path = request.url.path

    # 정적 파일(랜딩 페이지) 요청은 통과
    if not path.startswith("/api/"):
        return await call_next(request)

    # 허용 목록 검사
    allowed = False
    for prefix in _REMOTE_ALLOWED_PREFIXES:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            allowed = True
            # 메서드 제한 검사
            blocked_methods = _REMOTE_BLOCKED_METHODS.get(prefix)
            if blocked_methods and request.method in blocked_methods:
                allowed = False
            break

    if not allowed:
        logger.warning(
            "SERVER_MODE=remote: 차단됨 %s %s (from %s)",
            request.method, path, request.client.host if request.client else "unknown",
        )
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "data": None,
                "error": "이 서버는 원격 분류 전용입니다. 파일 관리 기능은 로컬 클라이언트를 사용하세요.",
            },
        )

    return await call_next(request)


# API 라우트
app.include_router(router, prefix="/api")

# WebSocket (루트 레벨 - /ws/progress)
app.include_router(ws_router)

# ── 프론트엔드: SERVER_MODE에 따라 다른 페이지 제공 ──
if SERVER_MODE == "remote":
    # 외부 공개: 랜딩 페이지 (site/) 제공
    site_path = Path(__file__).parent.parent / "site"
    if site_path.exists():
        app.mount("/", StaticFiles(directory=str(site_path), html=True), name="landing")
        logger.info("SERVER_MODE=remote: 랜딩 페이지 (site/) 제공")
    else:
        logger.warning("SERVER_MODE=remote: site/ 디렉토리가 없습니다!")
else:
    # 로컬: 관리 UI (frontend/) 제공
    frontend_path = Path(__file__).parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


@app.on_event("startup")
async def startup():
    load_config()
    pm = ProfileManager()
    pm.initialize_defaults()

    # SERVER_MODE=remote 시 API 키 자동 생성
    if SERVER_MODE == "remote":
        config = get_config()
        if not config.api_key:
            new_key = "afo_" + secrets.token_urlsafe(32)
            config.api_key = new_key
            save_config(config)
            logger.info("=" * 60)
            logger.info("API 키가 자동 생성되었습니다: %s", new_key)
            logger.info("=" * 60)
        else:
            logger.info("기존 API 키 사용: %s...%s", config.api_key[:8], config.api_key[-4:])

        logger.info("AI File Organizer v2.0 시작됨 [SERVER_MODE=remote]")
        logger.info("허용 엔드포인트: /api/health, /api/remote/classify, /api/profiles(GET)")
        logger.info("관리 UI: 비활성 (랜딩 페이지만 제공)")
    else:
        logger.info("AI File Organizer v2.0 시작됨 [SERVER_MODE=local]")
