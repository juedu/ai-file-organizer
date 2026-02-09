"""Ollama Vision-Language 모델 클라이언트"""

import base64
import json
import logging
from pathlib import Path

import httpx

from backend.models import ClassificationProfile

logger = logging.getLogger(__name__)

# 이미지 확장자
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}


class OllamaVLClient:
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # ------------------------------------------------------------------
    # 연결/모델 관리
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return {"connected": True, "models": models, "error": None}
                return {"connected": False, "models": [], "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"connected": False, "models": [], "error": str(e)}

    # ------------------------------------------------------------------
    # 핵심 API
    # ------------------------------------------------------------------

    async def generate(self, prompt: str, system: str = "",
                       images: list[str] | None = None) -> str:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512},
        }
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    # ------------------------------------------------------------------
    # 파일 분류
    # ------------------------------------------------------------------

    async def classify_file(
        self,
        file_path: Path,
        profile: ClassificationProfile,
        content: str | None = None,
        language: str = "ko",
    ) -> dict:
        """프로파일 기반 파일 분류. 반환: {folder, new_name, description}"""
        filename = file_path.name
        is_image = file_path.suffix.lower() in IMAGE_EXTS
        images = None

        system = (
            "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요."
            if language == "ko"
            else "You are a file classifier AI. Reply ONLY with JSON."
        )

        folders_desc = "\n".join(
            f"- {f.name}: {f.description}" for f in profile.folders
        )

        new_name_instr = (
            "'내용 기반 새 파일명 (확장자 제외)'"
            if profile.enable_rename
            else "null"
        )

        if is_image:
            encoded = self._encode_image(file_path)
            if encoded:
                images = [encoded]

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
                content_section = f"\n문서 내용 (처음 1000자):\n{content[:1000]}"

            prompt = (
                f"{profile.prompt}\n\n"
                f"현재 파일명: {filename}{content_section}\n\n"
                f"사용 가능한 폴더와 설명:\n{folders_desc}\n\n"
                f'반드시 아래 JSON 형식으로만 답하세요:\n'
                f'{{"folder": "가장 적합한 폴더명", "new_name": {new_name_instr}, '
                f'"description": "한줄 설명"}}\n\n'
                f'폴더명은 반드시 위 목록에서 선택하세요. 매칭되는 것이 없으면 "미분류"로 답하세요.'
            )

        # 최대 2회 시도
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response_text = await self.generate(prompt, system, images)
                return self._parse_response(response_text, profile)
            except Exception as e:
                last_error = e
                logger.warning("AI 분류 시도 %d 실패 %s: %s", attempt + 1, filename, e)

        logger.error("AI 분류 최종 실패 %s: %s", filename, last_error)
        return {"folder": "미분류", "new_name": None, "description": f"에러: {last_error}"}

    # ------------------------------------------------------------------
    # 응답 파싱
    # ------------------------------------------------------------------

    def _parse_response(self, text: str, profile: ClassificationProfile) -> dict:
        folder_names = [f.name for f in profile.folders]
        default = {"folder": "미분류", "new_name": None, "description": ""}

        # 1) 직접 JSON
        try:
            return self._validate(json.loads(text), folder_names)
        except json.JSONDecodeError:
            pass

        # 2) ```json 코드블록
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return self._validate(json.loads(text[start:end].strip()), folder_names)
            except (ValueError, json.JSONDecodeError):
                pass

        # 3) { } 추출
        if "{" in text and "}" in text:
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                return self._validate(json.loads(text[start:end]), folder_names)
            except (ValueError, json.JSONDecodeError):
                pass

        # 4) 텍스트 매칭
        text_lower = text.lower()
        for name in folder_names:
            if name.lower() in text_lower:
                return {"folder": name, "new_name": None, "description": text[:100]}

        logger.warning("AI 응답 파싱 실패: %s", text[:200])
        return default

    def _validate(self, result: dict, folder_names: list[str]) -> dict:
        folder = result.get("folder", "미분류")
        new_name = result.get("new_name")
        description = result.get("description", "")

        matched = self._match_folder(folder, folder_names)
        if matched:
            folder = matched

        if new_name:
            new_name = self._clean_filename(str(new_name))

        return {"folder": folder, "new_name": new_name, "description": description}

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------

    @staticmethod
    def _match_folder(ai_folder: str, folder_names: list[str]) -> str | None:
        if ai_folder in folder_names:
            return ai_folder
        for f in folder_names:
            if f.lower() == ai_folder.lower():
                return f
        for f in folder_names:
            if ai_folder.lower() in f.lower() or f.lower() in ai_folder.lower():
                return f
        return None

    @staticmethod
    def _encode_image(image_path: Path) -> str | None:
        try:
            return base64.b64encode(image_path.read_bytes()).decode("utf-8")
        except Exception as e:
            logger.error("이미지 인코딩 실패 %s: %s", image_path.name, e)
            return None

    @staticmethod
    def _clean_filename(name: str) -> str | None:
        from pathlib import PurePath
        name = PurePath(name).stem
        for ch in '<>:"/\\|?*':
            name = name.replace(ch, "")
        name = name.strip().replace(" ", "_")
        return name[:80] if name else None


class RemoteAIClient:
    """원격 서버에 파일을 업로드하여 AI 분류를 받는 클라이언트"""

    def __init__(self, server_url: str, api_key: str, timeout: int = 120):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def test_connection(self) -> dict:
        """원격 서버 연결 테스트"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.server_url}/api/health",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"connected": True, "models": [], "error": None}
                return {"connected": False, "models": [], "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"connected": False, "models": [], "error": str(e)}

    async def classify_file(
        self,
        file_path: Path,
        profile: ClassificationProfile,
        content: str | None = None,
        language: str = "ko",
    ) -> dict:
        """파일을 원격 서버에 업로드하여 분류 결과를 받음"""
        filename = file_path.name

        try:
            file_bytes = file_path.read_bytes()
        except Exception as e:
            logger.error("파일 읽기 실패 %s: %s", filename, e)
            return {"folder": "미분류", "new_name": None, "description": f"파일 읽기 에러: {e}"}

        last_error = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.server_url}/api/remote/classify",
                        files={"file": (filename, file_bytes)},
                        data={
                            "filename": filename,
                            "profile_id": profile.id,
                        },
                        headers={"x-api-key": self.api_key},
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    if result.get("success"):
                        return result["data"]
                    else:
                        raise Exception(result.get("error", "원격 분류 실패"))
            except Exception as e:
                last_error = e
                logger.warning("원격 분류 시도 %d 실패 %s: %s", attempt + 1, filename, e)

        logger.error("원격 분류 최종 실패 %s: %s", filename, last_error)
        return {"folder": "미분류", "new_name": None, "description": f"에러: {last_error}"}
