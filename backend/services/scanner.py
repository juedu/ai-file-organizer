"""파일/폴더 스캔 서비스"""

import mimetypes
import logging
from pathlib import Path
from datetime import datetime

from backend.models import FileItem, FolderInfo, ScanResult
from backend.config import AppConfig

logger = logging.getLogger(__name__)

# 확장자 → 카테고리 매핑
CATEGORY_MAP: dict[str, str] = {}

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".ico"}
_DOC_EXTS = {".txt", ".md", ".csv", ".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".rtf", ".hwp"}
_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}
_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".opus"}
_ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tar.gz"}
_CODE_EXTS = {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".cs", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sh", ".bat", ".ps1"}

for _ext in _IMAGE_EXTS:
    CATEGORY_MAP[_ext] = "image"
for _ext in _DOC_EXTS:
    CATEGORY_MAP[_ext] = "document"
for _ext in _VIDEO_EXTS:
    CATEGORY_MAP[_ext] = "video"
for _ext in _AUDIO_EXTS:
    CATEGORY_MAP[_ext] = "audio"
for _ext in _ARCHIVE_EXTS:
    CATEGORY_MAP[_ext] = "archive"
for _ext in _CODE_EXTS:
    CATEGORY_MAP[_ext] = "code"

# Windows 시스템 파일
SYSTEM_FILES = {"desktop.ini", "thumbs.db", "ntuser.dat", "$recycle.bin"}


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class FileScanner:
    def __init__(self, config: AppConfig):
        self.config = config

    def scan_directory(self, path: str, recursive: bool = False) -> ScanResult:
        base = Path(path).resolve()
        if not base.exists():
            raise FileNotFoundError(f"경로를 찾을 수 없습니다: {path}")
        if not base.is_dir():
            raise ValueError(f"디렉토리가 아닙니다: {path}")

        files: list[FileItem] = []
        type_dist: dict[str, int] = {}
        total_size = 0

        iterator = base.rglob("*") if recursive else base.iterdir()

        for item in iterator:
            if not item.is_file():
                continue
            if self.config.processing.skip_hidden and item.name.startswith("."):
                continue
            if self.config.processing.skip_system and item.name.lower() in SYSTEM_FILES:
                continue

            try:
                stat = item.stat()
                ext = item.suffix.lower()
                category = CATEGORY_MAP.get(ext, "other")
                mime = mimetypes.guess_type(item.name)[0] or "application/octet-stream"
                mod_time = datetime.fromtimestamp(stat.st_mtime).isoformat()

                fi = FileItem(
                    path=str(item),
                    filename=item.name,
                    extension=ext,
                    size=stat.st_size,
                    size_display=format_size(stat.st_size),
                    modified=mod_time,
                    mime_type=mime,
                    category=category,
                )
                files.append(fi)
                total_size += stat.st_size
                type_dist[ext] = type_dist.get(ext, 0) + 1
            except (PermissionError, OSError) as e:
                logger.warning("파일 스캔 실패 %s: %s", item, e)

        # 하위 폴더 목록
        subfolders = self._scan_subfolders(base)

        return ScanResult(
            base_path=str(base),
            files=files,
            subfolders=subfolders,
            total_files=len(files),
            total_size=total_size,
            total_size_display=format_size(total_size),
            type_distribution=type_dist,
        )

    def _scan_subfolders(self, base: Path) -> list[FolderInfo]:
        folders = []
        try:
            for item in sorted(base.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    count = sum(1 for f in item.iterdir() if f.is_file())
                    folders.append(FolderInfo(
                        name=item.name,
                        path=str(item),
                        file_count=count,
                    ))
        except PermissionError:
            logger.warning("하위 폴더 접근 실패: %s", base)
        return folders
