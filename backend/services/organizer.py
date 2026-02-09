"""파일 이동/복사/리네이밍 실행 서비스"""

import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Callable, Awaitable

from backend.models import ClassificationResult, ExecutionResult
from backend.config import AppConfig

logger = logging.getLogger(__name__)

MANIFESTS_DIR = Path(__file__).parent.parent.parent / "data" / "manifests"

ExecProgressCallback = Callable[[int, int, str], Awaitable[None]]


class FileOrganizer:
    def __init__(self, config: AppConfig):
        self.config = config
        MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        results: list[ClassificationResult],
        base_path: str,
        operation_mode: str = "copy",
        progress_callback: ExecProgressCallback | None = None,
    ) -> ExecutionResult:
        base = Path(base_path)
        operations: list[dict] = []
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors: list[str] = []

        for i, result in enumerate(results):
            if result.status != "success":
                skipped_count += 1
                continue

            try:
                source = Path(result.file_path)
                target_dir = base / result.target_folder
                target_dir.mkdir(parents=True, exist_ok=True)

                target_name = result.new_name or result.filename
                target_path = self._resolve_collision(target_dir / target_name)

                if operation_mode == "move":
                    shutil.move(str(source), str(target_path))
                else:
                    shutil.copy2(str(source), str(target_path))

                operations.append({
                    "source": str(source),
                    "target": str(target_path),
                    "operation": operation_mode,
                    "original_name": result.filename,
                    "new_name": target_name,
                })
                success_count += 1

            except Exception as e:
                errors.append(f"{result.filename}: {e}")
                failed_count += 1

            if progress_callback:
                await progress_callback(i + 1, len(results), result.filename)

        manifest_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_manifest(manifest_id, operations, base_path, operation_mode)

        return ExecutionResult(
            total=len(results),
            success=success_count,
            failed=failed_count,
            skipped=skipped_count,
            errors=errors,
            manifest_id=manifest_id,
        )

    def undo(self, manifest_id: str) -> ExecutionResult:
        manifest_path = MANIFESTS_DIR / f"{manifest_id}.json"
        if not manifest_path.exists():
            return ExecutionResult(
                total=0, success=0, failed=0, skipped=0,
                errors=[f"매니페스트를 찾을 수 없습니다: {manifest_id}"],
                manifest_id="",
            )

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        operations = manifest.get("operations", [])
        success_count = 0
        errors: list[str] = []

        for op in reversed(operations):
            try:
                target = Path(op["target"])
                source = Path(op["source"])

                if op["operation"] == "move":
                    source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(target), str(source))
                else:
                    if target.exists():
                        target.unlink()

                success_count += 1
            except Exception as e:
                errors.append(f"되돌리기 실패: {op.get('target', '?')}: {e}")

        return ExecutionResult(
            total=len(operations),
            success=success_count,
            failed=len(errors),
            skipped=0,
            errors=errors,
            manifest_id=f"undo_{manifest_id}",
        )

    def list_manifests(self) -> list[dict]:
        manifests = []
        for path in sorted(MANIFESTS_DIR.glob("*.json"), reverse=True):
            if path.name.startswith("undo_"):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifests.append({
                    "manifest_id": data["manifest_id"],
                    "timestamp": data["timestamp"],
                    "operation_mode": data["operation_mode"],
                    "total_files": data["total_files"],
                    "base_path": data["base_path"],
                })
            except Exception:
                continue
        return manifests

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_collision(target_path: Path) -> Path:
        if not target_path.exists():
            return target_path
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        for counter in range(1, 10000):
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
        raise ValueError(f"충돌 해결 실패: {target_path}")

    @staticmethod
    def _save_manifest(manifest_id: str, operations: list,
                       base_path: str, operation_mode: str):
        manifest = {
            "manifest_id": manifest_id,
            "timestamp": datetime.now().isoformat(),
            "base_path": base_path,
            "operation_mode": operation_mode,
            "total_files": len(operations),
            "operations": operations,
        }
        path = MANIFESTS_DIR / f"{manifest_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
