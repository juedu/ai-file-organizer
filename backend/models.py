"""Pydantic 데이터 모델 정의"""

from __future__ import annotations
from pydantic import BaseModel


class FileItem(BaseModel):
    """스캔된 파일 정보"""
    path: str
    filename: str
    extension: str
    size: int
    size_display: str
    modified: str
    mime_type: str
    category: str  # image / document / video / audio / archive / code / other


class FolderInfo(BaseModel):
    """폴더 정보"""
    name: str
    path: str
    file_count: int


class ScanResult(BaseModel):
    """스캔 결과"""
    base_path: str
    files: list[FileItem]
    subfolders: list[FolderInfo]
    total_files: int
    total_size: int
    total_size_display: str
    type_distribution: dict[str, int]


class ProfileFolder(BaseModel):
    """프로파일 폴더 정의"""
    name: str
    description: str


class ClassificationProfile(BaseModel):
    """분류 프로파일"""
    id: str
    name: str
    description: str
    folders: list[ProfileFolder]
    prompt: str
    rename_pattern: str = "{description}"
    enable_rename: bool = True
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""


class ClassificationResult(BaseModel):
    """단일 파일 분류 결과"""
    file_path: str
    filename: str
    target_folder: str
    new_name: str | None = None
    description: str = ""
    confidence: float = 0.0
    status: str = "success"  # success / error / timeout / skipped


class ClassificationPlan(BaseModel):
    """전체 분류 계획 (미리보기용)"""
    profile_id: str
    results: list[ClassificationResult]
    total_files: int
    classified: int
    errors: int
    folder_summary: dict[str, int]


class ExecutionResult(BaseModel):
    """실행 결과"""
    total: int
    success: int
    failed: int
    skipped: int
    errors: list[str]
    manifest_id: str
    duration: float = 0.0


class ProgressUpdate(BaseModel):
    """WebSocket 진행 상황 업데이트"""
    stage: str  # scanning / classifying / executing / complete / error
    current: int
    total: int
    current_file: str
    message: str
    result: ClassificationResult | None = None


class OllamaStatus(BaseModel):
    """Ollama 서버 상태"""
    connected: bool
    url: str
    models: list[str]
    current_model: str
    error: str | None = None
