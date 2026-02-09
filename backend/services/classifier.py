"""프로파일 기반 파일 분류 서비스"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Callable, Awaitable

from backend.models import (
    FileItem, ClassificationResult, ClassificationPlan,
    ClassificationProfile,
)
from backend.services.ai_client import OllamaVLClient
from backend.services.content_extractor import ContentExtractor
from backend.config import AppConfig

logger = logging.getLogger(__name__)

MEANINGLESS_PATTERNS = [
    "IMG_", "img_", "DSC_", "dsc_", "DCIM", "DSCN",
    "Photo_", "photo_", "Screenshot_", "screenshot_",
    "Screen Shot", "image", "Image",
    "Document", "document", "문서", "사진",
    "새 ", "New ", "Untitled", "제목 없",
    "KakaoTalk_", "received_",
]

ProgressCallback = Callable[[int, int, str, ClassificationResult], Awaitable[None]]


class FileClassifier:
    def __init__(self, ai_client: OllamaVLClient,
                 extractor: ContentExtractor,
                 config: AppConfig):
        self.ai = ai_client
        self.extractor = extractor
        self.config = config

    # ------------------------------------------------------------------
    # 분류
    # ------------------------------------------------------------------

    async def classify_file(self, file: FileItem,
                            profile: ClassificationProfile) -> ClassificationResult:
        try:
            file_path = Path(file.path)

            content = None
            if file.category == "document":
                content = self.extractor.extract(file_path)

            result = await self.ai.classify_file(
                file_path=file_path,
                profile=profile,
                content=content,
                language=self.config.language,
            )

            new_name = self._compute_new_name(result, profile, file)

            return ClassificationResult(
                file_path=file.path,
                filename=file.filename,
                target_folder=result.get("folder", "미분류"),
                new_name=new_name,
                description=result.get("description", ""),
                confidence=0.8,
                status="success",
            )

        except Exception as e:
            logger.error("분류 실패 %s: %s", file.filename, e)
            return ClassificationResult(
                file_path=file.path,
                filename=file.filename,
                target_folder="미분류",
                new_name=None,
                description=f"에러: {e}",
                confidence=0.0,
                status="error",
            )

    async def classify_all(
        self,
        files: list[FileItem],
        profile: ClassificationProfile,
        progress_callback: ProgressCallback | None = None,
    ) -> ClassificationPlan:
        results: list[ClassificationResult] = []
        errors = 0

        for i, file in enumerate(files):
            result = await self.classify_file(file, profile)
            results.append(result)

            if result.status == "error":
                errors += 1

            if progress_callback:
                await progress_callback(i + 1, len(files), file.filename, result)

        folder_summary: dict[str, int] = {}
        for r in results:
            folder_summary[r.target_folder] = folder_summary.get(r.target_folder, 0) + 1

        return ClassificationPlan(
            profile_id=profile.id,
            results=results,
            total_files=len(files),
            classified=len(files) - errors,
            errors=errors,
            folder_summary=folder_summary,
        )

    # ------------------------------------------------------------------
    # 리네이밍
    # ------------------------------------------------------------------

    def _compute_new_name(self, ai_result: dict,
                          profile: ClassificationProfile,
                          file: FileItem) -> str | None:
        if not profile.enable_rename:
            return None
        if not ai_result.get("new_name"):
            return None
        if not self.is_meaningless_filename(file.filename):
            return None

        if profile.rename_pattern:
            renamed = self.apply_rename_pattern(
                profile.rename_pattern,
                ai_result.get("folder", "미분류"),
                ai_result.get("description", ""),
                file,
            )
            if renamed:
                return renamed + file.extension

        clean = ai_result["new_name"]
        return clean + file.extension if clean else None

    @staticmethod
    def is_meaningless_filename(filename: str) -> bool:
        stem = Path(filename).stem
        for pattern in MEANINGLESS_PATTERNS:
            if stem.startswith(pattern):
                return True
        if stem.replace("_", "").replace("-", "").isdigit():
            return True
        return False

    @staticmethod
    def apply_rename_pattern(pattern: str, folder: str,
                             description: str, file: FileItem) -> str | None:
        safe_desc = description.replace(" ", "_")
        for ch in '<>:"/\\|?*':
            safe_desc = safe_desc.replace(ch, "")
        safe_desc = safe_desc[:60]

        try:
            dt = datetime.fromisoformat(file.modified)
            date_str = dt.strftime("%Y%m%d")
        except (ValueError, TypeError):
            date_str = "unknown"

        original = Path(file.filename).stem

        result = pattern.replace("{folder}", folder)
        result = result.replace("{description}", safe_desc)
        result = result.replace("{date}", date_str)
        result = result.replace("{original}", original)

        return result[:80] if result else None
