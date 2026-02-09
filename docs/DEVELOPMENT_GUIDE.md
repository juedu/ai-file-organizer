# Development Guide: AI File Organizer

이 문서는 개발 AI가 프로젝트를 구현할 때 참조해야 할 상세 구현 가이드입니다.

---

## 1. 구현 순서 (권장)

### Phase 1: 기반 구축
```
1. 프로젝트 구조 생성 (디렉토리, __init__.py)
2. requirements.txt 확인 및 의존성 설치
3. config.yaml 및 config.py 구현
4. models.py (Pydantic 데이터 모델 - 프로파일 모델 포함) 구현
5. run.py (앱 실행 스크립트) 구현
6. main.py (FastAPI 앱 기본 골격) 구현
```

### Phase 2: 프로파일 시스템
```
7. profile_manager.py - 프로파일 CRUD + 기본 프로파일 초기화
8. 프로파일 API 엔드포인트 (routes.py에 추가)
```

### Phase 3: 백엔드 서비스
```
9. scanner.py - 파일/폴더 스캔 서비스
10. content_extractor.py - 문서 텍스트 추출
11. ai_client.py - Ollama VL 클라이언트 (프로파일 기반 프롬프트)
12. classifier.py - 파일 분류 로직 (프로파일 기반)
13. organizer.py - 파일 이동/복사/리네이밍
```

### Phase 4: API 레이어
```
14. routes.py - REST API 엔드포인트 (스캔, 분류, 실행, 설정)
15. WebSocket 진행 상황 엔드포인트
```

### Phase 5: 프론트엔드
```
16. index.html - SPA 구조
17. style.css - 스타일시트
18. app.js - 프론트엔드 로직 (프로파일 선택/편집 UI 포함)
```

### Phase 6: 통합 및 테스트
```
19. 전체 흐름 통합 테스트
20. 에러 처리 검증
21. 설정 저장/로드 검증
22. 프로파일 CRUD 검증
```

---

## 2. 핵심 구현 가이드

### 2.1 FastAPI 앱 구조 (`backend/main.py`)

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from backend.api.routes import router
from backend.config import load_config, get_config
from backend.services.profile_manager import ProfileManager

app = FastAPI(title="AI File Organizer", version="2.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://close-ai.iptime.org:5000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우트 등록
app.include_router(router, prefix="/api")

# 프론트엔드 정적 파일 서빙
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

@app.on_event("startup")
async def startup():
    load_config()
    # 기본 프로파일 초기화
    profile_manager = ProfileManager()
    profile_manager.initialize_defaults()
```

### 2.2 설정 관리 (`backend/config.py`)

```python
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"

@dataclass
class OllamaConfig:
    url: str = "http://localhost:11434"
    model: str = "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct"
    timeout: int = 120

@dataclass
class ProcessingConfig:
    operation_mode: str = "copy"
    scan_recursive: bool = False
    skip_hidden: bool = True
    skip_system: bool = True

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000

@dataclass
class AppConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    language: str = "ko"

# 전역 설정 인스턴스
_config: AppConfig = AppConfig()

def load_config() -> AppConfig:
    global _config
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # YAML 데이터를 AppConfig에 매핑
        ollama_data = data.get("ollama", {})
        processing_data = data.get("processing", {})
        server_data = data.get("server", {})
        _config = AppConfig(
            ollama=OllamaConfig(**{k: v for k, v in ollama_data.items() if k in OllamaConfig.__dataclass_fields__}),
            processing=ProcessingConfig(**{k: v for k, v in processing_data.items() if k in ProcessingConfig.__dataclass_fields__}),
            server=ServerConfig(**{k: v for k, v in server_data.items() if k in ServerConfig.__dataclass_fields__}),
            language=data.get("language", "ko"),
        )
    return _config

def get_config() -> AppConfig:
    return _config

def save_config(config: AppConfig):
    global _config
    _config = config
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(asdict(config), f, allow_unicode=True, default_flow_style=False)
```

### 2.3 프로파일 관리 (`backend/services/profile_manager.py`)

```python
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime

from backend.models import ClassificationProfile, ProfileFolder

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent.parent.parent / "data" / "profiles"

# 기본 프로파일 정의
DEFAULT_PROFILES = [
    {
        "name": "기본 파일 정리",
        "description": "파일 종류별 기본 분류",
        "folders": [
            {"name": "사진", "description": "실제 카메라로 촬영한 사진"},
            {"name": "그림", "description": "디지털 아트, 일러스트, 팬아트"},
            {"name": "문서", "description": "PDF, Word, 텍스트 문서"},
            {"name": "스크린샷", "description": "화면 캡처"},
            {"name": "동영상", "description": "비디오 파일"},
            {"name": "음악", "description": "오디오, 음악 파일"},
            {"name": "압축", "description": "압축 파일"},
            {"name": "기타", "description": "위에 해당하지 않는 파일"},
        ],
        "prompt": "이 파일의 종류와 내용을 분석하여 가장 적합한 폴더를 선택하세요.",
        "rename_pattern": "{description}",
        "enable_rename": True,
    },
    {
        "name": "그림 품질 분류",
        "description": "그림의 퀄리티 기준으로 분류",
        "folders": [
            {"name": "명작", "description": "전문가급 퀄리티, 구도와 색감이 뛰어남"},
            {"name": "양호", "description": "평균 이상, 괜찮은 수준"},
            {"name": "보통", "description": "평범한 수준"},
            {"name": "스케치", "description": "러프 스케치, 낙서, 미완성"},
        ],
        "prompt": "이 이미지의 그림 퀄리티를 평가하세요.\n전문가급이면 \"명작\", 괜찮으면 \"양호\", 평범하면 \"보통\", 러프하면 \"스케치\"로 분류하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
    {
        "name": "이미지 출처 분류",
        "description": "이미지의 출처/용도별 분류",
        "folders": [
            {"name": "직접그린", "description": "본인이 직접 그린 그림, 디지털 아트"},
            {"name": "팬아트", "description": "애니/게임/영화 등의 팬아트"},
            {"name": "짤_밈", "description": "인터넷에서 가져온 재미있는 짤, 밈 이미지"},
            {"name": "스크린샷", "description": "화면 캡처, UI 스크린샷"},
            {"name": "사진", "description": "실제 카메라로 촬영한 사진"},
            {"name": "AI생성", "description": "AI로 생성된 이미지"},
        ],
        "prompt": "이 이미지가 어디서 온 것인지, 어떤 용도인지 판단하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
    {
        "name": "컨텐츠 수위 분류",
        "description": "이미지의 수위/노출 정도별 분류",
        "folders": [
            {"name": "전체이용가", "description": "누구나 볼 수 있는 안전한 이미지"},
            {"name": "약간노출", "description": "약간의 노출이 있지만 심하지 않음"},
            {"name": "성인", "description": "성인 컨텐츠, 노출이 심함"},
        ],
        "prompt": "이 이미지의 수위/노출 정도를 판단하세요.",
        "rename_pattern": "{description}",
        "enable_rename": False,
    },
    {
        "name": "문서 주제 분류",
        "description": "문서의 주제/용도별 분류",
        "folders": [
            {"name": "업무", "description": "회사 업무 관련 문서, 보고서, 회의록"},
            {"name": "학습", "description": "강의자료, 교재, 학습 노트"},
            {"name": "개인", "description": "개인 메모, 일기, 편지"},
            {"name": "금융", "description": "영수증, 세금, 은행 관련"},
            {"name": "법률계약", "description": "계약서, 법률 문서"},
        ],
        "prompt": "이 문서의 주제와 용도를 분석하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
]


class ProfileManager:
    def __init__(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[ClassificationProfile]:
        """모든 프로파일 목록 반환"""
        profiles = []
        for path in sorted(PROFILES_DIR.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(ClassificationProfile(**data))
            except Exception as e:
                logger.error(f"프로파일 로드 실패 {path}: {e}")
        return profiles

    def get_profile(self, profile_id: str) -> ClassificationProfile | None:
        """ID로 프로파일 조회"""
        path = PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ClassificationProfile(**data)
        except Exception as e:
            logger.error(f"프로파일 로드 실패 {profile_id}: {e}")
            return None

    def create_profile(self, data: dict) -> ClassificationProfile:
        """새 프로파일 생성"""
        now = datetime.now().isoformat()
        profile = ClassificationProfile(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data.get("description", ""),
            folders=[ProfileFolder(**f) for f in data["folders"]],
            prompt=data["prompt"],
            rename_pattern=data.get("rename_pattern", "{description}"),
            enable_rename=data.get("enable_rename", True),
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        self._save_profile(profile)
        return profile

    def update_profile(self, profile_id: str, data: dict) -> ClassificationProfile | None:
        """프로파일 수정 (부분 업데이트)"""
        profile = self.get_profile(profile_id)
        if not profile:
            return None

        # 부분 업데이트 적용
        if "name" in data:
            profile.name = data["name"]
        if "description" in data:
            profile.description = data["description"]
        if "folders" in data:
            profile.folders = [ProfileFolder(**f) for f in data["folders"]]
        if "prompt" in data:
            profile.prompt = data["prompt"]
        if "rename_pattern" in data:
            profile.rename_pattern = data["rename_pattern"]
        if "enable_rename" in data:
            profile.enable_rename = data["enable_rename"]

        profile.updated_at = datetime.now().isoformat()
        self._save_profile(profile)
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        """프로파일 삭제 (기본 프로파일은 삭제 불가)"""
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        if profile.is_default:
            raise ValueError("기본 프로파일은 삭제할 수 없습니다.")

        path = PROFILES_DIR / f"{profile_id}.json"
        path.unlink()
        return True

    def duplicate_profile(self, profile_id: str) -> ClassificationProfile | None:
        """프로파일 복제"""
        original = self.get_profile(profile_id)
        if not original:
            return None

        now = datetime.now().isoformat()
        duplicate = ClassificationProfile(
            id=str(uuid.uuid4()),
            name=f"{original.name} (사본)",
            description=original.description,
            folders=original.folders.copy(),
            prompt=original.prompt,
            rename_pattern=original.rename_pattern,
            enable_rename=original.enable_rename,
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        self._save_profile(duplicate)
        return duplicate

    def initialize_defaults(self):
        """기본 프로파일 초기화 (프로파일이 하나도 없을 때만)"""
        existing = list(PROFILES_DIR.glob("*.json"))
        if existing:
            return  # 이미 프로파일이 있으면 건너뜀

        now = datetime.now().isoformat()
        for default_data in DEFAULT_PROFILES:
            profile = ClassificationProfile(
                id=str(uuid.uuid4()),
                name=default_data["name"],
                description=default_data["description"],
                folders=[ProfileFolder(**f) for f in default_data["folders"]],
                prompt=default_data["prompt"],
                rename_pattern=default_data["rename_pattern"],
                enable_rename=default_data["enable_rename"],
                is_default=True,
                created_at=now,
                updated_at=now,
            )
            self._save_profile(profile)

        logger.info(f"기본 프로파일 {len(DEFAULT_PROFILES)}개 생성 완료")

    def _save_profile(self, profile: ClassificationProfile):
        """프로파일을 JSON 파일로 저장"""
        path = PROFILES_DIR / f"{profile.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.dict(), f, ensure_ascii=False, indent=2)
```

### 2.4 AI 클라이언트 (`backend/services/ai_client.py`)

**핵심 구현 포인트:**

```python
import httpx
import base64
import json
import logging
from pathlib import Path

from backend.models import ClassificationProfile

logger = logging.getLogger(__name__)

class OllamaVLClient:
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def test_connection(self) -> dict:
        """Ollama 서버 연결 테스트"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return {"connected": True, "models": models, "error": None}
        except Exception as e:
            return {"connected": False, "models": [], "error": str(e)}

    def _encode_image(self, image_path: Path) -> str | None:
        """이미지를 base64로 인코딩"""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"이미지 인코딩 실패 {image_path}: {e}")
            return None

    async def generate(self, prompt: str, system: str = "",
                       images: list[str] | None = None) -> str:
        """Ollama generate API 호출"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 512
            }
        }
        if images:
            payload["images"] = images

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    async def classify_file(self, file_path: Path,
                            profile: ClassificationProfile,
                            content: str | None = None,
                            language: str = "ko") -> dict:
        """
        프로파일 기반으로 파일을 분류합니다.

        Returns:
            {"folder": str, "new_name": str|None, "description": str}
        """
        filename = file_path.name
        is_image = file_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
        images = None

        # 시스템 프롬프트
        if language == "ko":
            system = "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요."
        else:
            system = "You are a file classifier AI. Reply ONLY with JSON."

        # 폴더 목록 + 설명 문자열 생성
        folders_desc = "\n".join(
            f"- {f.name}: {f.description}" for f in profile.folders
        )

        # 이미지 파일: Vision 기능 사용
        if is_image:
            encoded = self._encode_image(file_path)
            if encoded:
                images = [encoded]

            prompt = f"""{profile.prompt}

현재 파일명: {filename}
사용 가능한 폴더와 설명:
{folders_desc}

반드시 아래 JSON 형식으로만 답하세요:
{{"folder": "가장 적합한 폴더명", "new_name": {"'내용 기반 새 파일명 (확장자 제외)'" if profile.enable_rename else "null"}, "description": "한줄 설명"}}

폴더명은 반드시 위 목록에서 선택하세요. 매칭되는 것이 없으면 "미분류"로 답하세요."""

        # 문서/기타 파일: Language 기능 사용
        else:
            content_section = ""
            if content:
                content_section = f"\n문서 내용 (처음 1000자):\n{content[:1000]}"

            prompt = f"""{profile.prompt}

현재 파일명: {filename}{content_section}

사용 가능한 폴더와 설명:
{folders_desc}

반드시 아래 JSON 형식으로만 답하세요:
{{"folder": "가장 적합한 폴더명", "new_name": {"'내용 기반 새 파일명 (확장자 제외)'" if profile.enable_rename else "null"}, "description": "한줄 설명"}}

폴더명은 반드시 위 목록에서 선택하세요. 매칭되는 것이 없으면 "미분류"로 답하세요."""

        try:
            response_text = await self.generate(prompt, system, images)
            return self._parse_response(response_text, profile)
        except Exception as e:
            logger.error(f"AI 분류 실패 {filename}: {e}")
            return {"folder": "미분류", "new_name": None, "description": f"에러: {str(e)}"}

    def _parse_response(self, response_text: str, profile: ClassificationProfile) -> dict:
        """AI 응답을 파싱합니다. 여러 단계의 fallback 적용."""
        folder_names = [f.name for f in profile.folders]
        default = {"folder": "미분류", "new_name": None, "description": ""}

        # 1단계: 직접 JSON 파싱
        try:
            result = json.loads(response_text)
            return self._validate_result(result, folder_names)
        except json.JSONDecodeError:
            pass

        # 2단계: ```json 코드블록에서 추출
        if "```json" in response_text:
            try:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                result = json.loads(response_text[start:end].strip())
                return self._validate_result(result, folder_names)
            except (ValueError, json.JSONDecodeError):
                pass

        # 3단계: { } 사이에서 JSON 추출
        if "{" in response_text and "}" in response_text:
            try:
                start = response_text.index("{")
                end = response_text.rindex("}") + 1
                result = json.loads(response_text[start:end])
                return self._validate_result(result, folder_names)
            except (ValueError, json.JSONDecodeError):
                pass

        # 4단계: 텍스트에서 프로파일 폴더명 매칭
        response_lower = response_text.lower()
        for folder_name in folder_names:
            if folder_name.lower() in response_lower:
                return {"folder": folder_name, "new_name": None,
                        "description": response_text[:100]}

        # 5단계: fallback
        logger.warning(f"AI 응답 파싱 실패: {response_text[:200]}")
        return default

    def _validate_result(self, result: dict, folder_names: list[str]) -> dict:
        """파싱된 결과의 폴더명을 검증하고 정규화합니다."""
        folder = result.get("folder", "미분류")
        new_name = result.get("new_name")
        description = result.get("description", "")

        # 폴더명 매칭
        matched = self._match_folder(folder, folder_names)
        if matched:
            folder = matched

        # new_name 정리 (확장자 제거, 특수문자 정리)
        if new_name:
            new_name = self._clean_filename(new_name)

        return {"folder": folder, "new_name": new_name, "description": description}

    def _match_folder(self, ai_folder: str, folder_names: list[str]) -> str | None:
        """AI가 반환한 폴더명을 프로파일 폴더 목록에서 매칭"""
        # 정확한 매칭
        if ai_folder in folder_names:
            return ai_folder

        # 대소문자 무시 매칭
        for f in folder_names:
            if f.lower() == ai_folder.lower():
                return f

        # 부분 매칭
        for f in folder_names:
            if ai_folder.lower() in f.lower() or f.lower() in ai_folder.lower():
                return f

        return None

    def _clean_filename(self, name: str) -> str:
        """파일명 정리: 확장자 제거, 위험 문자 제거"""
        from pathlib import PurePath
        name = PurePath(name).stem

        # 위험 문자 제거
        invalid_chars = '<>:"/\\|?*'
        for ch in invalid_chars:
            name = name.replace(ch, "")

        # 공백을 언더스코어로
        name = name.strip().replace(" ", "_")

        # 길이 제한
        return name[:80] if name else None
```

### 2.5 분류 서비스 (`backend/services/classifier.py`)

```python
import logging
from pathlib import Path
from datetime import datetime

from backend.models import (
    FileItem, ClassificationResult, ClassificationPlan,
    ClassificationProfile
)
from backend.services.ai_client import OllamaVLClient
from backend.services.content_extractor import ContentExtractor
from backend.config import AppConfig

logger = logging.getLogger(__name__)

# 무의미한 파일명 패턴
MEANINGLESS_PATTERNS = [
    "IMG_", "img_", "DSC_", "dsc_", "DCIM", "DSCN",
    "Photo_", "photo_", "Screenshot_", "screenshot_",
    "Screen Shot", "image", "Image",
    "Document", "document", "문서", "사진",
    "새 ", "New ", "Untitled", "제목 없",
    "KakaoTalk_", "received_",
]

class FileClassifier:
    def __init__(self, ai_client: OllamaVLClient,
                 extractor: ContentExtractor,
                 config: AppConfig):
        self.ai_client = ai_client
        self.extractor = extractor
        self.config = config

    def is_meaningless_filename(self, filename: str) -> bool:
        """무의미한 파일명인지 판단"""
        stem = Path(filename).stem
        for pattern in MEANINGLESS_PATTERNS:
            if stem.startswith(pattern):
                return True
        if stem.replace("_", "").replace("-", "").isdigit():
            return True
        return False

    def apply_rename_pattern(self, pattern: str, folder: str,
                             description: str, file: FileItem) -> str:
        """리네이밍 패턴 적용"""
        # 설명을 파일명에 안전한 형태로 변환
        safe_desc = description.replace(" ", "_")
        invalid_chars = '<>:"/\\|?*'
        for ch in invalid_chars:
            safe_desc = safe_desc.replace(ch, "")
        safe_desc = safe_desc[:60]  # 설명 길이 제한

        # 파일 수정일
        try:
            modified_dt = datetime.fromisoformat(file.modified)
            date_str = modified_dt.strftime("%Y%m%d")
        except (ValueError, TypeError):
            date_str = "unknown"

        # 원본 파일명 (확장자 제외)
        original = Path(file.filename).stem

        # 패턴 변수 치환
        result = pattern.replace("{folder}", folder)
        result = result.replace("{description}", safe_desc)
        result = result.replace("{date}", date_str)
        result = result.replace("{original}", original)

        return result[:80] if result else None

    async def classify_file(self, file: FileItem,
                            profile: ClassificationProfile) -> ClassificationResult:
        """프로파일 기반으로 단일 파일 분류"""
        try:
            file_path = Path(file.path)

            # 문서인 경우 텍스트 추출
            content = None
            if file.category == "document":
                content = self.extractor.extract(file_path)

            # AI 분류 (프로파일 기반)
            result = await self.ai_client.classify_file(
                file_path=file_path,
                profile=profile,
                content=content,
                language=self.config.language
            )

            # 리네이밍 처리
            new_name = None
            if profile.enable_rename and result.get("new_name"):
                # 패턴이 있으면 패턴 적용, 없으면 AI 제안 이름 사용
                if profile.rename_pattern:
                    renamed = self.apply_rename_pattern(
                        profile.rename_pattern,
                        result.get("folder", "미분류"),
                        result.get("description", ""),
                        file
                    )
                    if renamed:
                        new_name = renamed + file.extension
                else:
                    new_name = result["new_name"] + file.extension

            # 파일명이 의미있으면 리네이밍 안함
            if new_name and not self.is_meaningless_filename(file.filename):
                new_name = None

            return ClassificationResult(
                file_path=file.path,
                filename=file.filename,
                target_folder=result.get("folder", "미분류"),
                new_name=new_name,
                description=result.get("description", ""),
                confidence=0.8,
                status="success"
            )

        except Exception as e:
            logger.error(f"분류 실패 {file.filename}: {e}")
            return ClassificationResult(
                file_path=file.path,
                filename=file.filename,
                target_folder="미분류",
                new_name=None,
                description=f"에러: {str(e)}",
                confidence=0.0,
                status="error"
            )

    async def classify_all(self, files: list[FileItem],
                           profile: ClassificationProfile,
                           progress_callback=None) -> ClassificationPlan:
        """프로파일 기반으로 모든 파일 분류"""
        results = []
        errors = 0

        for i, file in enumerate(files):
            result = await self.classify_file(file, profile)
            results.append(result)

            if result.status == "error":
                errors += 1

            if progress_callback:
                await progress_callback(i + 1, len(files), file.filename, result)

        # 폴더별 요약
        folder_summary = {}
        for r in results:
            folder_summary[r.target_folder] = folder_summary.get(r.target_folder, 0) + 1

        return ClassificationPlan(
            profile_id=profile.id,
            results=results,
            total_files=len(files),
            classified=len(files) - errors,
            errors=errors,
            folder_summary=folder_summary
        )
```

### 2.6 파일 정리 실행기 (`backend/services/organizer.py`)

```python
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

from backend.models import ClassificationResult, ExecutionResult
from backend.config import AppConfig

logger = logging.getLogger(__name__)

MANIFESTS_DIR = Path(__file__).parent.parent.parent / "data" / "manifests"

class FileOrganizer:
    def __init__(self, config: AppConfig):
        self.config = config
        MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    async def execute(self, results: list[ClassificationResult],
                      base_path: str,
                      operation_mode: str = "copy",
                      progress_callback=None) -> ExecutionResult:
        """분류 결과에 따라 파일을 이동/복사합니다."""
        base = Path(base_path)
        operations = []
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        for i, result in enumerate(results):
            if result.status != "success":
                skipped_count += 1
                continue

            try:
                source = Path(result.file_path)
                target_dir = base / result.target_folder
                target_dir.mkdir(parents=True, exist_ok=True)

                # 대상 파일명 결정
                target_name = result.new_name if result.new_name else result.filename
                target_path = self._resolve_collision(target_dir / target_name)

                # 파일 복사 또는 이동
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
                errors.append(f"{result.filename}: {str(e)}")
                failed_count += 1

            if progress_callback:
                await progress_callback(i + 1, len(results), result.filename)

        # 매니페스트 생성
        manifest_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_manifest(manifest_id, operations, base_path, operation_mode)

        return ExecutionResult(
            total=len(results),
            success=success_count,
            failed=failed_count,
            skipped=skipped_count,
            errors=errors,
            manifest_id=manifest_id,
            duration=0  # 호출자가 측정
        )

    def undo(self, manifest_id: str) -> ExecutionResult:
        """매니페스트 기반으로 작업을 되돌립니다."""
        manifest_path = MANIFESTS_DIR / f"{manifest_id}.json"
        if not manifest_path.exists():
            return ExecutionResult(
                total=0, success=0, failed=0, skipped=0,
                errors=[f"매니페스트를 찾을 수 없습니다: {manifest_id}"],
                manifest_id="", duration=0
            )

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        operations = manifest.get("operations", [])
        success_count = 0
        errors = []

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
                errors.append(f"되돌리기 실패: {op.get('target', '?')}: {str(e)}")

        return ExecutionResult(
            total=len(operations),
            success=success_count,
            failed=len(errors),
            skipped=0,
            errors=errors,
            manifest_id=f"undo_{manifest_id}",
            duration=0
        )

    def _resolve_collision(self, target_path: Path) -> Path:
        """파일명 충돌 해결"""
        if not target_path.exists():
            return target_path

        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        counter = 1

        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
            if counter > 9999:
                raise ValueError(f"충돌 해결 실패: {target_path}")

    def _save_manifest(self, manifest_id: str, operations: list,
                       base_path: str, operation_mode: str):
        """매니페스트 저장"""
        manifest = {
            "manifest_id": manifest_id,
            "timestamp": datetime.now().isoformat(),
            "base_path": base_path,
            "operation_mode": operation_mode,
            "total_files": len(operations),
            "operations": operations
        }
        path = MANIFESTS_DIR / f"{manifest_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def list_manifests(self) -> list[dict]:
        """매니페스트 목록 반환"""
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
```

### 2.7 API 라우트 (`backend/api/routes.py`)

```python
import asyncio
import time
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from backend.config import get_config, save_config, AppConfig
from backend.services.scanner import FileScanner
from backend.services.ai_client import OllamaVLClient
from backend.services.content_extractor import ContentExtractor
from backend.services.classifier import FileClassifier
from backend.services.organizer import FileOrganizer
from backend.services.profile_manager import ProfileManager
from backend.models import FileItem, ClassificationResult

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket 연결 관리
active_websockets: list[WebSocket] = []

async def broadcast_progress(data: dict):
    """모든 WebSocket 클라이언트에 진행 상황 전송"""
    for ws in active_websockets[:]:
        try:
            await ws.send_json(data)
        except Exception:
            active_websockets.remove(ws)


# === WebSocket 엔드포인트 ===

@router.websocket("/ws/progress")  # 실제 경로: /api/ws/progress
async def websocket_progress(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


# === 프로파일 API ===

@router.get("/profiles")
async def list_profiles():
    pm = ProfileManager()
    profiles = pm.list_profiles()
    return {"success": True, "data": [p.dict() for p in profiles]}

@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    pm = ProfileManager()
    profile = pm.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"프로파일을 찾을 수 없습니다: {profile_id}")
    return {"success": True, "data": profile.dict()}

@router.post("/profiles")
async def create_profile(req: dict):
    pm = ProfileManager()
    profile = pm.create_profile(req)
    return {"success": True, "data": profile.dict()}

@router.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, req: dict):
    pm = ProfileManager()
    profile = pm.update_profile(profile_id, req)
    if not profile:
        raise HTTPException(status_code=404, detail=f"프로파일을 찾을 수 없습니다: {profile_id}")
    return {"success": True, "data": profile.dict()}

@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    pm = ProfileManager()
    try:
        pm.delete_profile(profile_id)
        return {"success": True, "data": {"message": "프로파일이 삭제되었습니다."}}
    except ValueError as e:
        return {"success": False, "error": str(e)}

@router.post("/profiles/{profile_id}/duplicate")
async def duplicate_profile(profile_id: str):
    pm = ProfileManager()
    profile = pm.duplicate_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"프로파일을 찾을 수 없습니다: {profile_id}")
    return {"success": True, "data": profile.dict()}


# === REST 엔드포인트 ===

@router.get("/health")
async def health():
    return {"success": True, "data": {"status": "ok", "version": "2.0.0"}}


@router.get("/ollama/status")
async def ollama_status():
    config = get_config()
    client = OllamaVLClient(config.ollama.url, config.ollama.model, config.ollama.timeout)
    result = await client.test_connection()
    return {
        "success": result["connected"],
        "data": {
            "connected": result["connected"],
            "url": config.ollama.url,
            "current_model": config.ollama.model,
            "models": result["models"],
            "error": result["error"]
        }
    }


# POST /api/scan
class ScanRequest(BaseModel):
    path: str
    recursive: bool = False

@router.post("/scan")
async def scan_directory(req: ScanRequest):
    config = get_config()
    scanner = FileScanner(config)
    try:
        result = scanner.scan_directory(req.path, req.recursive)
        return {"success": True, "data": result}
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# POST /api/classify (프로파일 기반)
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
        return {"success": False, "error": f"프로파일을 찾을 수 없습니다: {req.profile_id}"}

    client = OllamaVLClient(config.ollama.url, config.ollama.model, config.ollama.timeout)
    extractor = ContentExtractor()
    classifier = FileClassifier(client, extractor, config)

    async def progress_callback(current, total, filename, result):
        await broadcast_progress({
            "stage": "classifying",
            "current": current,
            "total": total,
            "current_file": filename,
            "message": f"분류 중: {filename}",
            "result": result.dict() if result else None
        })

    plan = await classifier.classify_all(req.files, profile, progress_callback)

    await broadcast_progress({
        "stage": "complete",
        "current": plan.total_files,
        "total": plan.total_files,
        "current_file": "",
        "message": "분류 완료",
        "result": None
    })

    return {"success": True, "data": plan.dict()}


# POST /api/execute
class ExecuteRequest(BaseModel):
    base_path: str
    results: list[ClassificationResult]
    operation_mode: str = "copy"

@router.post("/execute")
async def execute_plan(req: ExecuteRequest):
    config = get_config()
    organizer = FileOrganizer(config)

    start_time = time.time()

    async def progress_callback(current, total, filename):
        await broadcast_progress({
            "stage": "executing",
            "current": current,
            "total": total,
            "current_file": filename,
            "message": f"{'이동' if req.operation_mode == 'move' else '복사'} 중: {filename}",
            "result": None
        })

    result = await organizer.execute(
        req.results, req.base_path, req.operation_mode, progress_callback
    )
    result.duration = time.time() - start_time

    await broadcast_progress({
        "stage": "complete",
        "current": result.total,
        "total": result.total,
        "current_file": "",
        "message": "실행 완료",
        "result": None
    })

    return {"success": True, "data": result.dict()}


# POST /api/undo
class UndoRequest(BaseModel):
    manifest_id: str

@router.post("/undo")
async def undo_operation(req: UndoRequest):
    config = get_config()
    organizer = FileOrganizer(config)
    result = organizer.undo(req.manifest_id)
    return {"success": True, "data": result.dict()}


# GET /api/manifests
@router.get("/manifests")
async def list_manifests():
    config = get_config()
    organizer = FileOrganizer(config)
    return {"success": True, "data": organizer.list_manifests()}


# GET /api/config
@router.get("/config")
async def get_config_endpoint():
    from dataclasses import asdict
    config = get_config()
    return {"success": True, "data": asdict(config)}


# PUT /api/config
@router.put("/config")
async def update_config(req: dict):
    config = get_config()
    if "ollama" in req:
        for k, v in req["ollama"].items():
            if hasattr(config.ollama, k):
                setattr(config.ollama, k, v)
    if "processing" in req:
        for k, v in req["processing"].items():
            if hasattr(config.processing, k):
                setattr(config.processing, k, v)
    if "language" in req:
        config.language = req["language"]

    save_config(config)
    return {"success": True, "data": {"message": "설정이 저장되었습니다."}}


# GET /api/browse
@router.get("/browse")
async def browse_folders(path: str = ""):
    """서버 파일시스템 폴더 탐색"""
    import platform

    if not path:
        if platform.system() == "Windows":
            import string
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if Path(drive).exists():
                    drives.append({"name": f"{letter}:", "path": drive})
            return {"success": True, "data": {
                "current_path": "",
                "parent_path": None,
                "folders": drives,
                "is_root": True
            }}
        else:
            path = "/"

    p = Path(path)
    if not p.exists() or not p.is_dir():
        return {"success": False, "error": f"경로를 찾을 수 없습니다: {path}"}

    folders = []
    try:
        for item in sorted(p.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                folders.append({"name": item.name, "path": str(item)})
    except PermissionError:
        return {"success": False, "error": f"접근 권한이 없습니다: {path}"}

    parent = str(p.parent) if p.parent != p else None

    return {"success": True, "data": {
        "current_path": str(p),
        "parent_path": parent,
        "folders": folders,
        "is_root": parent is None
    }}
```

---

## 3. 프론트엔드 구현 가이드

### 3.1 index.html 구조

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI File Organizer</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <header id="app-header">
        <h1>AI File Organizer</h1>
        <nav>
            <button onclick="App.navigate('profiles')">프로파일 관리</button>
            <button onclick="App.navigate('settings')">설정</button>
        </nav>
        <div id="connection-status"></div>
    </header>

    <main id="app-content">
        <!-- 화면별 컨텐츠가 여기에 렌더링됨 -->
    </main>

    <footer id="app-footer">
        <span id="status-text">준비됨</span>
    </footer>

    <script src="/js/app.js"></script>
</body>
</html>
```

### 3.2 app.js 핵심 구조

```javascript
const App = {
    // 상태
    state: {
        currentScreen: 'home',
        scanResult: null,
        selectedProfile: null,
        classificationPlan: null,
        profiles: [],
        ws: null,
    },

    // 초기화
    async init() {
        await this.loadProfiles();
        this.checkOllama();
        this.navigate('home');
    },

    // 프로파일 로드
    async loadProfiles() {
        const result = await this.api('GET', '/profiles');
        if (result.success) {
            this.state.profiles = result.data;
        }
    },

    // 화면 전환
    navigate(screen, params) {
        this.state.currentScreen = screen;
        const content = document.getElementById('app-content');
        content.innerHTML = this.screens[screen].render(params);
        this.screens[screen].bind(params);
    },

    // API 호출
    async api(method, path, body = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(`/api${path}`, options);
        return await response.json();
    },

    // WebSocket 연결
    connectWS(onMessage) {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${location.host}/api/ws/progress`);
        ws.onmessage = (e) => onMessage(JSON.parse(e.data));
        ws.onerror = (e) => console.error('WS error:', e);
        this.state.ws = ws;
        return ws;
    },

    // Ollama 상태 확인
    async checkOllama() {
        const result = await this.api('GET', '/ollama/status');
        const el = document.getElementById('connection-status');
        if (result.data?.connected) {
            el.textContent = '● 연결됨';
            el.className = 'connected';
        } else {
            el.textContent = '○ 연결 안됨';
            el.className = 'disconnected';
        }
    },

    // 화면 정의
    screens: {
        home: {
            render() { /* 홈 화면 HTML 반환 - 폴더 경로 입력 */ },
            bind() { /* 스캔 버튼 이벤트 */ }
        },
        scan: {
            render() { /* 스캔 결과 + 프로파일 선택 드롭다운 */ },
            bind() { /* 프로파일 선택, AI 분석 시작 버튼 */ }
        },
        profile: {
            render(params) { /* 프로파일 편집/생성 폼 */ },
            bind(params) { /* 폴더 추가/삭제, 저장 버튼 */ }
        },
        profiles: {
            render() { /* 프로파일 목록 카드 그리드 */ },
            bind() { /* 수정/삭제/복제/새로만들기 버튼 */ }
        },
        classify: {
            render() { /* 분류 진행 화면 - 프로그레스 바 */ },
            bind() { /* WebSocket 연결, 실시간 결과 표시 */ }
        },
        preview: {
            render() { /* 미리보기 - 폴더별 그룹핑, 체크박스, 수동 수정 */ },
            bind() { /* 체크박스, 드롭다운, 실행 버튼 */ }
        },
        execute: {
            render() { /* 실행 진행 화면 */ },
            bind() { /* WebSocket 연결 */ }
        },
        result: {
            render() { /* 결과 화면 - 성공/실패 통계 */ },
            bind() { /* 되돌리기, 홈으로 버튼 */ }
        },
        settings: {
            render() { /* 설정 화면 - Ollama URL, 모델, 언어 등 */ },
            bind() { /* 저장, 연결 테스트 버튼 */ }
        },
    }
};

// 앱 시작
document.addEventListener('DOMContentLoaded', () => App.init());
```

### 3.3 프로파일 편집 화면 구현 포인트

```javascript
// 프로파일 편집 화면의 핵심 기능:

// 1. 폴더 목록 동적 추가/삭제
function addFolder() {
    // 폴더명 + 설명 입력 필드 쌍을 추가
}
function removeFolder(index) {
    // 해당 인덱스의 폴더 제거
}

// 2. 프롬프트 편집 (textarea)
// - 여러 줄 입력 가능
// - 프로파일 저장 시 prompt 필드에 저장

// 3. 리네이밍 패턴 편집
// - 패턴 입력 필드 + 미리보기
// - 변수 버튼: {folder}, {description}, {date}, {original}
// - 클릭하면 패턴 입력 필드에 삽입

// 4. 프롬프트 미리보기
// - 실제 AI에게 전달되는 전체 프롬프트를 미리 보여줌
// - system 프롬프트 + user 프롬프트 (예시 파일 기준)
```

### 3.4 스타일 가이드

- **색상**: 깔끔한 모던 다크/라이트 테마
- **폰트**: 시스템 폰트 (Noto Sans KR fallback)
- **레이아웃**: 중앙 정렬, 최대 너비 1200px
- **반응형**: 기본 반응형 (데스크톱 중심)
- **아이콘**: 이모지 사용 (외부 라이브러리 없이)
- **프로파일 카드**: 그리드 레이아웃, 호버 효과, 이름/설명/폴더수 표시

---

## 4. 주의사항

### 4.1 비동기 처리
- Ollama API 호출은 반드시 `async/await` 사용 (httpx.AsyncClient)
- FastAPI의 background task나 asyncio.create_task로 분류/실행 처리
- WebSocket으로 진행 상황 실시간 전송

### 4.2 파일 경로 처리
- Windows 경로 호환 (`\` vs `/`)
- 항상 `pathlib.Path` 사용
- 사용자 입력 경로는 `resolve()`로 정규화
- 심볼릭 링크 주의

### 4.3 인코딩
- 한글 파일명 지원 (UTF-8)
- YAML/JSON 파일: `encoding='utf-8'`
- 텍스트 파일 추출: 다중 인코딩 시도 (utf-8, cp949, euc-kr)

### 4.4 에러 복원력
- AI 응답 파싱 실패 → 다단계 fallback
- 파일 작업 실패 → 해당 파일만 건너뛰고 계속
- Ollama 연결 끊김 → 재연결 시도
- 전체 프로세스 실패 → 완료된 부분 유지, 매니페스트 기록

### 4.5 기존 코드 재사용 불가
- 기존 `src/`, `app.py` 코드는 **전부 폐기**합니다
- 새로운 `backend/` 구조로 처음부터 작성합니다
- 기존 코드의 로직(텍스트 추출, 파일 스캔 등)은 참고하되, 새 구조에 맞게 재작성합니다

### 4.6 Flet 제거
- 기존 Flet GUI 프레임워크는 **사용하지 않습니다**
- FastAPI + 바닐라 HTML/JS로 대체합니다
- `flet` 의존성을 `requirements.txt`에서 제거합니다

### 4.7 프로파일 시스템 핵심 원칙
- **프로파일이 분류의 중심**: 모든 분류는 프로파일을 선택해야 시작됨
- **프로파일의 prompt가 AI 프롬프트의 핵심**: 사용자 커스텀 지시가 가장 중요
- **폴더 설명**: 각 폴더에 AI용 설명을 붙여 AI의 분류 정확도 향상
- **기본 프로파일 보호**: 기본 5개 프로파일은 수정은 가능하나 삭제 불가
- **JSON 저장**: 프로파일은 `data/profiles/{uuid}.json`에 개별 파일로 저장

---

## 5. 테스트 체크리스트

### 5.1 프로파일 시스템 테스트
- [ ] 기본 프로파일 5개 자동 생성 (최초 실행 시)
- [ ] 프로파일 생성 (이름, 폴더, 프롬프트, 패턴)
- [ ] 프로파일 수정 (부분 업데이트)
- [ ] 프로파일 삭제 (기본 프로파일 삭제 차단 확인)
- [ ] 프로파일 복제
- [ ] 프로파일 목록 조회
- [ ] 프로파일 JSON 파일 저장/로드

### 5.2 백엔드 테스트
- [ ] Ollama 연결 테스트 (로컬/도메인)
- [ ] 폴더 스캔 (빈 폴더, 많은 파일, 숨김 파일)
- [ ] 텍스트 추출 (PDF, DOCX, TXT, 다양한 인코딩)
- [ ] 프로파일 기반 AI 분류 (이미지, 문서, 기타)
- [ ] 리네이밍 패턴 적용 ({folder}, {description}, {date}, {original})
- [ ] JSON 파싱 (정상, 코드블록, 비정상 응답)
- [ ] 파일 복사/이동 (이름 충돌, 권한 오류)
- [ ] 매니페스트 생성/로드
- [ ] Undo 동작

### 5.3 프론트엔드 테스트
- [ ] 폴더 브라우저 동작
- [ ] 스캔 결과 표시
- [ ] 프로파일 선택 드롭다운
- [ ] 프로파일 편집 화면 (폴더 동적 추가/삭제, 프롬프트, 패턴)
- [ ] 분류 진행 (WebSocket 실시간 업데이트)
- [ ] 미리보기 (체크박스, 수동 수정, 제외 기능)
- [ ] 실행 진행
- [ ] 결과 표시
- [ ] 설정 저장/로드
- [ ] 에러 메시지 표시

### 5.4 통합 테스트
- [ ] 전체 워크플로우: 스캔 → 프로파일 선택 → 분류 → 미리보기 → 실행
- [ ] 다른 프로파일로 동일 폴더 재분류
- [ ] Undo 전체 워크플로우
- [ ] 대량 파일 (100+) 처리
- [ ] 다양한 파일 유형 혼합
- [ ] 외부 접속 (close-ai.iptime.org:5000) 테스트
