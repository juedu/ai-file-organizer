"""REST API 라우트 + WebSocket 정의"""

import asyncio
import base64
import io
import logging
import secrets
import string
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.config import get_config, save_config, AppConfig, OllamaConfig, ProcessingConfig
from backend.models import (
    FileItem, ClassificationResult, ProgressUpdate,
)
from backend.services.profile_manager import ProfileManager
from backend.services.scanner import FileScanner
from backend.services.content_extractor import ContentExtractor
from backend.services.ai_client import OllamaVLClient, RemoteAIClient
from backend.services.classifier import FileClassifier
from backend.services.organizer import FileOrganizer

logger = logging.getLogger(__name__)

router = APIRouter()
ws_router = APIRouter()

# ------------------------------------------------------------------
# WebSocket 연결 관리
# ------------------------------------------------------------------

_ws_clients: list[WebSocket] = []


async def _broadcast(data: dict):
    """모든 WebSocket 클라이언트에 메시지 브로드캐스트"""
    for ws in list(_ws_clients):
        try:
            await ws.send_json(data)
        except Exception:
            _ws_clients.remove(ws)


@ws_router.websocket("/ws/progress")
async def websocket_progress(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ------------------------------------------------------------------
# 공통 응답 유틸리티
# ------------------------------------------------------------------

def _ok(data=None):
    return {"success": True, "data": data, "error": None}


def _err(message: str, status: int = 400):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status,
        content={"success": False, "data": None, "error": message},
    )


# ------------------------------------------------------------------
# 1. 시스템 API
# ------------------------------------------------------------------

@router.get("/health")
async def health():
    return _ok({"status": "ok", "version": "2.1.0"})


@router.get("/thumbnail")
async def get_thumbnail(path: str, size: int = 120):
    """이미지 파일의 썸네일 반환 (lazy, 캐시 없음 - 브라우저 캐시 활용)"""
    from PIL import Image

    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return _err("파일을 찾을 수 없습니다", 404)

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico"}
    if file_path.suffix.lower() not in IMAGE_EXTS:
        return _err("이미지 파일이 아닙니다", 400)

    size = min(max(size, 32), 300)  # 32~300px 제한

    try:
        with Image.open(file_path) as img:
            img.thumbnail((size, size), Image.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
                fmt, mime = "PNG", "image/png"
            else:
                img = img.convert("RGB")
                fmt, mime = "JPEG", "image/jpeg"

            buf = io.BytesIO()
            img.save(buf, format=fmt, quality=75, optimize=True)
            buf.seek(0)

        return Response(
            content=buf.getvalue(),
            media_type=mime,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as e:
        logger.warning("썸네일 생성 실패 %s: %s", path, e)
        return _err("썸네일 생성 실패", 500)


@router.get("/ollama/status")
async def ollama_status():
    config = get_config()

    if config.mode == "remote" and config.remote.url:
        # 리모트 모드: 원격 서버 연결 확인
        remote_client = RemoteAIClient(config.remote.url, config.remote.api_key)
        result = await remote_client.test_connection()
        data = {
            "connected": result["connected"],
            "url": config.remote.url,
            "current_model": "원격 서버",
            "models": [],
            "error": result["error"],
            "mode": "remote",
        }
        if not result["connected"]:
            return JSONResponse(status_code=503, content={"success": False, "data": data, "error": result["error"]})
        return _ok(data)

    # 로컬 모드: Ollama 직접 연결
    client = OllamaVLClient(config.ollama.url, config.ollama.model, config.ollama.timeout)
    result = await client.test_connection()
    data = {
        "connected": result["connected"],
        "url": config.ollama.url,
        "current_model": config.ollama.model,
        "models": result["models"],
        "error": result["error"],
        "mode": "local",
    }
    if not result["connected"]:
        return JSONResponse(status_code=503, content={"success": False, "data": data, "error": result["error"]})
    return _ok(data)


# ------------------------------------------------------------------
# 2. 프로파일 API
# ------------------------------------------------------------------

@router.get("/profiles")
async def list_profiles():
    pm = ProfileManager()
    profiles = pm.list_profiles()
    return _ok([p.model_dump() for p in profiles])


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    pm = ProfileManager()
    profile = pm.get_profile(profile_id)
    if not profile:
        return _err(f"프로파일을 찾을 수 없습니다: {profile_id}", 404)
    return _ok(profile.model_dump())


class ProfileCreateRequest(BaseModel):
    name: str
    description: str = ""
    folders: list[dict]
    prompt: str
    rename_pattern: str = "{description}"
    enable_rename: bool = True


@router.post("/profiles")
async def create_profile(req: ProfileCreateRequest):
    if len(req.folders) < 2:
        return _err("폴더는 최소 2개 이상 필요합니다.")
    pm = ProfileManager()
    profile = pm.create_profile(req.model_dump())
    return _ok(profile.model_dump())


@router.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, req: dict):
    pm = ProfileManager()
    profile = pm.update_profile(profile_id, req)
    if not profile:
        return _err(f"프로파일을 찾을 수 없습니다: {profile_id}", 404)
    return _ok(profile.model_dump())


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    pm = ProfileManager()
    try:
        deleted = pm.delete_profile(profile_id)
        if not deleted:
            return _err(f"프로파일을 찾을 수 없습니다: {profile_id}", 404)
        return _ok({"message": "프로파일이 삭제되었습니다."})
    except ValueError as e:
        return _err(str(e), 400)


@router.post("/profiles/{profile_id}/duplicate")
async def duplicate_profile(profile_id: str):
    pm = ProfileManager()
    dup = pm.duplicate_profile(profile_id)
    if not dup:
        return _err(f"프로파일을 찾을 수 없습니다: {profile_id}", 404)
    return _ok(dup.model_dump())


# ------------------------------------------------------------------
# 3. 파일 시스템 API
# ------------------------------------------------------------------

@router.get("/browse")
async def browse(path: str | None = None):
    if not path:
        # Windows: 드라이브 목록 반환
        drives = []
        for letter in string.ascii_uppercase:
            dp = Path(f"{letter}:\\")
            if dp.exists():
                drives.append({"name": f"{letter}:", "path": f"{letter}:\\"})
        return _ok({
            "current_path": "",
            "parent_path": None,
            "folders": drives,
            "is_root": True,
        })

    base = Path(path).resolve()
    if not base.exists() or not base.is_dir():
        return _err(f"경로를 찾을 수 없습니다: {path}", 400)

    folders = []
    try:
        for item in sorted(base.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                folders.append({"name": item.name, "path": str(item)})
    except PermissionError:
        pass

    parent = str(base.parent) if base.parent != base else None
    return _ok({
        "current_path": str(base),
        "parent_path": parent,
        "folders": folders,
        "is_root": False,
    })


class ScanRequest(BaseModel):
    path: str
    recursive: bool = False


@router.post("/scan")
async def scan_directory(req: ScanRequest):
    config = get_config()
    scanner = FileScanner(config)
    try:
        result = scanner.scan_directory(req.path, req.recursive)
        return _ok(result.model_dump())
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e), 400)


# ------------------------------------------------------------------
# 4. 분류 API
# ------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    base_path: str
    files: list[FileItem]
    profile_id: str


@router.post("/classify")
async def classify_files(req: ClassifyRequest):
    config = get_config()

    # 프로파일 로드
    pm = ProfileManager()
    profile = pm.get_profile(req.profile_id)
    if not profile:
        return _err(f"프로파일을 찾을 수 없습니다: {req.profile_id}", 404)

    # 서비스 초기화 - 모드에 따라 AI 클라이언트 선택
    if config.mode == "remote" and config.remote.url:
        ai_client = RemoteAIClient(config.remote.url, config.remote.api_key, config.ollama.timeout)
    else:
        ai_client = OllamaVLClient(config.ollama.url, config.ollama.model, config.ollama.timeout)
    extractor = ContentExtractor()
    classifier = FileClassifier(ai_client, extractor, config)

    # WebSocket 진행 콜백
    async def on_progress(current: int, total: int, filename: str, result: ClassificationResult):
        update = ProgressUpdate(
            stage="classifying",
            current=current,
            total=total,
            current_file=filename,
            message=f"분류 중: {filename}",
            result=result,
        )
        await _broadcast(update.model_dump())

    # 분류 실행
    plan = await classifier.classify_all(req.files, profile, on_progress)

    # 완료 알림
    await _broadcast(ProgressUpdate(
        stage="complete",
        current=plan.total_files,
        total=plan.total_files,
        current_file="",
        message="분류 완료",
    ).model_dump())

    return _ok(plan.model_dump())


# ------------------------------------------------------------------
# 5. 실행 API
# ------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    base_path: str
    results: list[ClassificationResult]
    operation_mode: str = "copy"


@router.post("/execute")
async def execute_plan(req: ExecuteRequest):
    config = get_config()
    organizer = FileOrganizer(config)

    start_time = time.time()

    # WebSocket 진행 콜백
    async def on_progress(current: int, total: int, filename: str):
        update = ProgressUpdate(
            stage="executing",
            current=current,
            total=total,
            current_file=filename,
            message=f"파일 {'이동' if req.operation_mode == 'move' else '복사'} 중...",
        )
        await _broadcast(update.model_dump())

    result = await organizer.execute(
        req.results, req.base_path, req.operation_mode, on_progress
    )

    duration = round(time.time() - start_time, 2)

    # 완료 알림
    await _broadcast(ProgressUpdate(
        stage="complete",
        current=result.total,
        total=result.total,
        current_file="",
        message="실행 완료",
    ).model_dump())

    data = result.model_dump()
    data["duration"] = duration
    return _ok(data)


class UndoRequest(BaseModel):
    manifest_id: str


@router.post("/undo")
async def undo_execution(req: UndoRequest):
    config = get_config()
    organizer = FileOrganizer(config)

    start_time = time.time()
    result = organizer.undo(req.manifest_id)
    duration = round(time.time() - start_time, 2)

    data = result.model_dump()
    data["duration"] = duration
    return _ok(data)


@router.get("/manifests")
async def list_manifests():
    config = get_config()
    organizer = FileOrganizer(config)
    manifests = organizer.list_manifests()
    return _ok(manifests)


# ------------------------------------------------------------------
# 6. 설정 API
# ------------------------------------------------------------------

@router.get("/config")
async def get_configuration():
    config = get_config()
    return _ok(asdict(config))


@router.put("/config")
async def update_configuration(req: dict):
    config = get_config()

    if "ollama" in req:
        o = req["ollama"]
        if "url" in o:
            config.ollama.url = o["url"]
        if "model" in o:
            config.ollama.model = o["model"]
        if "timeout" in o:
            config.ollama.timeout = o["timeout"]

    if "processing" in req:
        p = req["processing"]
        if "operation_mode" in p:
            config.processing.operation_mode = p["operation_mode"]
        if "scan_recursive" in p:
            config.processing.scan_recursive = p["scan_recursive"]
        if "skip_hidden" in p:
            config.processing.skip_hidden = p["skip_hidden"]
        if "skip_system" in p:
            config.processing.skip_system = p["skip_system"]

    if "language" in req:
        config.language = req["language"]

    if "mode" in req:
        config.mode = req["mode"]
    if "api_key" in req:
        config.api_key = req["api_key"]
    if "remote" in req:
        r = req["remote"]
        if "url" in r:
            config.remote.url = r["url"]
        if "api_key" in r:
            config.remote.api_key = r["api_key"]

    save_config(config)
    return _ok({"message": "설정이 저장되었습니다."})


# ------------------------------------------------------------------
# 7. API 키 생성
# ------------------------------------------------------------------

@router.post("/generate-api-key")
async def generate_api_key():
    """새 API 키를 생성하고 설정에 저장"""
    config = get_config()
    new_key = "afo_" + secrets.token_urlsafe(32)
    config.api_key = new_key
    save_config(config)
    return _ok({"api_key": new_key})


# ------------------------------------------------------------------
# 8. 원격 분류 API (서버 모드: 클라이언트가 파일을 업로드하면 AI 분류)
# ------------------------------------------------------------------

def _verify_api_key(x_api_key: str | None) -> bool:
    """서버의 api_key와 일치하는지 확인"""
    config = get_config()
    if not config.api_key:
        return False  # 서버에 API 키 미설정 → 거부
    return x_api_key == config.api_key


@router.post("/remote/classify")
async def remote_classify(
    file: UploadFile = File(...),
    filename: str = Form(...),
    profile_id: str = Form(...),
    x_api_key: str = Header(None),
):
    """원격 클라이언트가 파일을 업로드 → 서버의 Ollama로 분류 → 결과 반환"""
    # API 키 검증
    if not _verify_api_key(x_api_key):
        return _err("유효하지 않은 API 키입니다.", 401)

    config = get_config()

    # 프로파일 로드
    pm = ProfileManager()
    profile = pm.get_profile(profile_id)
    if not profile:
        return _err(f"프로파일을 찾을 수 없습니다: {profile_id}", 404)

    # 파일 내용 읽기
    file_bytes = await file.read()

    # AI 클라이언트로 분류
    ai_client = OllamaVLClient(config.ollama.url, config.ollama.model, config.ollama.timeout)
    extractor = ContentExtractor()

    # 이미지인지 확인
    ext = Path(filename).suffix.lower()
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
    is_image = ext in IMAGE_EXTS

    images = None
    content = None

    if is_image:
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        images = [encoded]
    else:
        # 문서 내용 추출 시도
        try:
            content = file_bytes.decode("utf-8", errors="ignore")[:1000]
        except Exception:
            content = None

    # 프롬프트 구성 및 AI 호출
    folders_desc = "\n".join(
        f"- {f.name}: {f.description}" for f in profile.folders
    )
    new_name_instr = (
        "'내용 기반 새 파일명 (확장자 제외)'"
        if profile.enable_rename
        else "null"
    )

    system = (
        "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요."
        if config.language == "ko"
        else "You are a file classifier AI. Reply ONLY with JSON."
    )

    if is_image:
        prompt = (
            f"{profile.prompt}\n\n"
            f"현재 파일명: {filename}\n"
            f"사용 가능한 폴더와 설명:\n{folders_desc}\n\n"
            f'반드시 아래 JSON 형식으로만 답하세요:\n'
            f'{{"folder": "가장 적합한 폴더명", "new_name": {new_name_instr}, '
            f'"description": "한줄 설명"}}\n\n'
            f'폴더명은 반드시 위 목록에서 선택하세요. 매칭되는 것이 없으면 "미분류"로 답하세요.'
        )
    else:
        content_section = ""
        if content:
            content_section = f"\n문서 내용 (처음 1000자):\n{content}"

        prompt = (
            f"{profile.prompt}\n\n"
            f"현재 파일명: {filename}{content_section}\n\n"
            f"사용 가능한 폴더와 설명:\n{folders_desc}\n\n"
            f'반드시 아래 JSON 형식으로만 답하세요:\n'
            f'{{"folder": "가장 적합한 폴더명", "new_name": {new_name_instr}, '
            f'"description": "한줄 설명"}}\n\n'
            f'폴더명은 반드시 위 목록에서 선택하세요. 매칭되는 것이 없으면 "미분류"로 답하세요.'
        )

    try:
        response_text = await ai_client.generate(prompt, system, images)
        result = ai_client._parse_response(response_text, profile)
        return _ok(result)
    except Exception as e:
        logger.error("원격 분류 실패 %s: %s", filename, e)
        return _ok({"folder": "미분류", "new_name": None, "description": f"에러: {e}"})
