# System Architecture: AI File Organizer

## 1. 시스템 개요

```
+--------------------------------------------------+
|                   Web Browser                     |
|  (localhost:5000 또는 close-ai.iptime.org:5000)   |
+--------------------------------------------------+
          |  HTTP / WebSocket
          v
+--------------------------------------------------+
|              FastAPI Web Server (:5000)            |
|  +--------------------------------------------+  |
|  |  API Layer (routes.py)                     |  |
|  |  - REST endpoints                          |  |
|  |  - WebSocket (실시간 진행 상황)               |  |
|  |  - Static files (프론트엔드)                 |  |
|  +--------------------------------------------+  |
|  |  Service Layer                              |  |
|  |  +----------+ +----------+ +-----------+   |  |
|  |  | Scanner  | | AIClient | | Organizer |   |  |
|  |  +----------+ +----------+ +-----------+   |  |
|  |  +----------+ +----------+ +-----------+   |  |
|  |  |Extractor | |Classifier| |  Config   |   |  |
|  |  +----------+ +----------+ +-----------+   |  |
|  |  +-------------------+                     |  |
|  |  | Profile Manager   |                     |  |
|  |  +-------------------+                     |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
          |  HTTP (REST API)
          v
+--------------------------------------------------+
|              Ollama Server                         |
|  huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct |
|  (localhost:11434 또는 close-ai.iptime.org:11434) |
+--------------------------------------------------+
```

## 2. 디렉토리 구조

```
D:\Vibe\FileCleanup\
├── docs/                              # 기획/설계 문서
│   ├── PRD.md                         # 제품 요구사항 문서
│   ├── ARCHITECTURE.md                # 시스템 아키텍처 (이 문서)
│   ├── API_SPEC.md                    # API 명세서
│   └── DEVELOPMENT_GUIDE.md           # 개발 가이드
│
├── backend/                           # 백엔드 (FastAPI)
│   ├── __init__.py
│   ├── main.py                        # FastAPI 앱 진입점, 서버 설정
│   ├── config.py                      # 설정 관리 (YAML 로드, 기본값)
│   ├── models.py                      # Pydantic 데이터 모델
│   │
│   ├── services/                      # 비즈니스 로직 서비스
│   │   ├── __init__.py
│   │   ├── scanner.py                 # 파일/폴더 스캔 서비스
│   │   ├── ai_client.py              # Ollama VL 모델 클라이언트
│   │   ├── content_extractor.py      # 문서 텍스트 추출
│   │   ├── classifier.py             # 파일 분류 로직 (프로파일 기반)
│   │   ├── organizer.py              # 파일 이동/복사/리네이밍 실행
│   │   └── profile_manager.py        # 분류 프로파일 CRUD 관리
│   │
│   └── api/                           # API 라우트
│       ├── __init__.py
│       └── routes.py                  # REST + WebSocket 엔드포인트
│
├── frontend/                          # 프론트엔드 (정적 파일)
│   ├── index.html                     # SPA 메인 페이지
│   ├── css/
│   │   └── style.css                  # 스타일시트
│   └── js/
│       └── app.js                     # 프론트엔드 로직
│
├── config/
│   └── config.yaml                    # 앱 설정 파일
│
├── data/                              # 런타임 데이터 (gitignore)
│   ├── profiles/                      # 분류 프로파일 JSON 파일
│   └── manifests/                     # 작업 매니페스트 (undo용)
│
├── requirements.txt                   # Python 의존성
├── run.py                             # 앱 실행 스크립트
└── .gitignore
```

## 3. 백엔드 모듈 상세

### 3.1 `backend/main.py` - 앱 진입점

```python
# 역할:
# - FastAPI 앱 인스턴스 생성
# - 라우트 등록
# - 정적 파일 서빙 (frontend/)
# - CORS 설정 (localhost:5000, close-ai.iptime.org:5000)
# - 앱 시작/종료 이벤트 핸들러
# - 기본 프로파일 초기화

# 의존성:
# - fastapi, uvicorn
# - backend.api.routes
# - backend.config
# - backend.services.profile_manager
```

### 3.2 `backend/config.py` - 설정 관리

```python
# 역할:
# - config.yaml 로드
# - 기본값 관리
# - 런타임 설정 변경 지원
# - 설정 유효성 검증

# 설정 구조:
@dataclass
class AppConfig:
    # Ollama 서버
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct"
    ollama_timeout: int = 120  # 초

    # 파일 처리
    operation_mode: str = "copy"  # copy | move
    language: str = "ko"  # ko | en

    # 스캔 설정
    scan_recursive: bool = False  # 기본: 1단계만
    skip_hidden: bool = True
    skip_system: bool = True
    min_file_size: int = 0  # bytes
    max_file_size: int | None = None  # bytes, None = 무제한

    # 서버 설정
    host: str = "0.0.0.0"
    port: int = 5000
```

### 3.3 `backend/models.py` - 데이터 모델

```python
# Pydantic 모델 정의

class FileItem(BaseModel):
    """스캔된 파일 정보"""
    path: str                    # 절대 경로
    filename: str                # 파일명
    extension: str               # 확장자 (.jpg 등)
    size: int                    # 바이트
    size_display: str            # 사람이 읽을 수 있는 크기 (예: "2.5 MB")
    modified: str                # 수정일 ISO 형식
    mime_type: str               # MIME 타입
    category: str                # 파일 카테고리 (image/document/video/audio/archive/code/other)

class FolderInfo(BaseModel):
    """폴더 정보"""
    name: str                    # 폴더명
    path: str                    # 절대 경로
    file_count: int              # 포함 파일 수

class ScanResult(BaseModel):
    """스캔 결과"""
    base_path: str               # 스캔 대상 폴더
    files: list[FileItem]        # 파일 목록
    subfolders: list[FolderInfo] # 하위 폴더 목록
    total_files: int
    total_size: int
    total_size_display: str
    type_distribution: dict[str, int]  # 확장자별 파일 수

class ProfileFolder(BaseModel):
    """프로파일 폴더 정의"""
    name: str                    # 폴더명
    description: str             # AI용 폴더 설명

class ClassificationProfile(BaseModel):
    """분류 프로파일"""
    id: str                      # 고유 ID (UUID)
    name: str                    # 프로파일 이름
    description: str             # 프로파일 설명
    folders: list[ProfileFolder] # 분류 폴더 목록 (이름 + 설명)
    prompt: str                  # AI에게 보낼 커스텀 분류 프롬프트
    rename_pattern: str          # 리네이밍 패턴 ("{folder}_{description}" 등)
    enable_rename: bool          # 리네이밍 활성화 여부
    is_default: bool = False     # 기본 프로파일 여부
    created_at: str              # 생성일 ISO
    updated_at: str              # 수정일 ISO

class ClassificationResult(BaseModel):
    """단일 파일 분류 결과"""
    file_path: str               # 원본 파일 경로
    filename: str                # 현재 파일명
    target_folder: str           # 대상 폴더명
    new_name: str | None         # 새 파일명 (리네이밍 시, null이면 변경 없음)
    description: str             # AI 설명
    confidence: float            # 신뢰도 (0.0-1.0) - JSON 파싱 성공 시 기본 0.8
    status: str                  # success | error | timeout | skipped

class ClassificationPlan(BaseModel):
    """전체 분류 계획 (미리보기용)"""
    profile_id: str              # 사용된 프로파일 ID
    results: list[ClassificationResult]
    total_files: int
    classified: int
    errors: int
    folder_summary: dict[str, int]  # 폴더별 파일 수

class ExecutionResult(BaseModel):
    """실행 결과"""
    total: int
    success: int
    failed: int
    skipped: int
    errors: list[str]
    manifest_id: str             # undo용 매니페스트 ID
    duration: float              # 실행 시간 (초)

class ProgressUpdate(BaseModel):
    """WebSocket 진행 상황 업데이트"""
    stage: str                   # scanning | classifying | executing
    current: int                 # 현재 처리 번호
    total: int                   # 전체 수
    current_file: str            # 현재 처리 중 파일명
    message: str                 # 상태 메시지
    result: ClassificationResult | None  # 분류 결과 (classifying 단계)

class OllamaStatus(BaseModel):
    """Ollama 서버 상태"""
    connected: bool
    url: str
    models: list[str]            # 설치된 모델 목록
    current_model: str
    error: str | None
```

### 3.4 `backend/services/scanner.py` - 파일 스캔 서비스

```python
# 역할:
# - 지정 폴더의 파일 목록 스캔
# - 하위 폴더 목록 감지
# - 파일 메타데이터 수집 (크기, 수정일, MIME)
# - 숨김/시스템 파일 필터링
# - 파일 유형 카테고리 분류 (확장자 기반)

# 핵심 메서드:
class FileScanner:
    def scan_directory(self, path: str, recursive: bool = False) -> ScanResult
    def scan_subfolders(self, path: str) -> list[FolderInfo]
    def get_file_category(self, extension: str) -> str
    def format_size(self, size_bytes: int) -> str
```

### 3.5 `backend/services/ai_client.py` - Ollama VL 클라이언트

```python
# 역할:
# - Ollama REST API 통신 (단일 VL 모델)
# - 이미지 base64 인코딩 + Vision 요청
# - 텍스트 분석 요청
# - 연결 테스트
# - 모델 목록 조회
# - 응답 JSON 파싱 + fallback 처리

# 핵심 메서드:
class OllamaVLClient:
    def __init__(self, base_url: str, model: str, timeout: int)
    async def test_connection(self) -> OllamaStatus
    async def list_models(self) -> list[str]
    async def generate(self, prompt: str, system: str, images: list[str] | None) -> str
    async def classify_file(self, file_path: Path,
                            profile: ClassificationProfile,
                            content: str | None = None) -> dict

# 중요 구현 사항:
# - httpx.AsyncClient 사용 (비동기)
# - 이미지 전송 시 base64 인코딩
# - 프로파일의 prompt와 folders를 AI 프롬프트에 통합
# - JSON 파싱 실패 시 텍스트에서 폴더명 추출 시도
# - 타임아웃 처리
# - 재시도 로직 (최대 2회)
```

### 3.6 `backend/services/content_extractor.py` - 텍스트 추출

```python
# 역할:
# - PDF 텍스트 추출 (PyPDF2)
# - DOCX 텍스트 추출 (python-docx)
# - TXT/MD/CSV 텍스트 읽기 (인코딩 자동 감지)
# - XLSX 텍스트 추출 (openpyxl)
# - 최대 길이 제한 (기본 1000자)

# 핵심 메서드:
class ContentExtractor:
    def extract(self, file_path: Path) -> str | None
    def extract_pdf(self, file_path: Path) -> str | None
    def extract_docx(self, file_path: Path) -> str | None
    def extract_text(self, file_path: Path) -> str | None
    def extract_xlsx(self, file_path: Path) -> str | None
```

### 3.7 `backend/services/classifier.py` - 파일 분류 서비스

```python
# 역할:
# - 선택된 프로파일을 기반으로 AI 분류 수행
# - 파일 유형에 따른 분류 전략 선택
# - 프로파일의 프롬프트 + 폴더 설명을 AI 프롬프트에 통합
# - 리네이밍 패턴 적용 ({folder}, {description}, {date}, {original})
# - 결과 검증 및 정규화
# - 무의미한 파일명 감지

# 핵심 메서드:
class FileClassifier:
    def __init__(self, ai_client: OllamaVLClient,
                 extractor: ContentExtractor,
                 config: AppConfig)

    async def classify_file(self, file: FileItem,
                            profile: ClassificationProfile) -> ClassificationResult

    async def classify_all(self, files: list[FileItem],
                           profile: ClassificationProfile,
                           progress_callback) -> ClassificationPlan

    def build_prompt(self, file: FileItem, profile: ClassificationProfile,
                     content: str | None) -> tuple[str, str]  # (system, user)

    def apply_rename_pattern(self, pattern: str, folder: str,
                             description: str, file: FileItem) -> str

    def parse_ai_response(self, response_text: str,
                          profile: ClassificationProfile) -> dict

    def is_meaningless_filename(self, filename: str) -> bool

    def match_folder(self, ai_folder: str,
                     profile_folders: list[ProfileFolder]) -> str | None

# 분류 전략:
# 1. 이미지 파일: base64 인코딩 → VL 모델 Vision 기능
# 2. 문서 파일: 텍스트 추출 → VL 모델 Language 기능
# 3. 기타 파일: 파일명 + 확장자 → VL 모델 Language 기능 (짧은 프롬프트)

# 프롬프트 구성:
# - system: "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요."
# - user: profile.prompt + 폴더 목록(name: description) + 파일 정보 + JSON 출력 지시
```

### 3.8 `backend/services/organizer.py` - 파일 정리 실행기

```python
# 역할:
# - ClassificationPlan에 따라 파일 이동/복사 실행
# - 리네이밍 패턴 적용 결과로 파일명 변경
# - 폴더 자동 생성
# - 이름 충돌 해결
# - 매니페스트 생성 (undo용)
# - undo 실행

# 핵심 메서드:
class FileOrganizer:
    def __init__(self, config: AppConfig)

    async def execute(self, plan: ClassificationPlan,
                      base_path: str,
                      progress_callback) -> ExecutionResult

    def resolve_collision(self, target_path: Path) -> Path
    def create_manifest(self, operations: list[dict]) -> str
    def undo(self, manifest_id: str) -> ExecutionResult
    def list_manifests(self) -> list[dict]
```

### 3.9 `backend/services/profile_manager.py` - 프로파일 관리

```python
# 역할:
# - 분류 프로파일 CRUD (Create/Read/Update/Delete)
# - data/profiles/ 디렉토리에 JSON 파일로 저장
# - 기본 프로파일 5개 초기화 (앱 첫 실행 시)
# - 프로파일 복제
# - UUID 기반 고유 ID 생성

# 핵심 메서드:
class ProfileManager:
    PROFILES_DIR = Path("data/profiles")

    def __init__(self)
    def list_profiles(self) -> list[ClassificationProfile]
    def get_profile(self, profile_id: str) -> ClassificationProfile | None
    def create_profile(self, data: dict) -> ClassificationProfile
    def update_profile(self, profile_id: str, data: dict) -> ClassificationProfile
    def delete_profile(self, profile_id: str) -> bool
    def duplicate_profile(self, profile_id: str) -> ClassificationProfile
    def initialize_defaults(self)   # 기본 5개 프로파일 생성

# 저장 형식: data/profiles/{uuid}.json
# 각 파일은 ClassificationProfile 모델의 JSON 직렬화

# 기본 프로파일 5개:
# 1. 기본 파일 정리 (사진/그림/문서/스크린샷/동영상/음악/압축/기타)
# 2. 그림 품질 분류 (명작/양호/보통/스케치)
# 3. 이미지 출처 분류 (직접그린/팬아트/짤_밈/스크린샷/사진/AI생성)
# 4. 컨텐츠 수위 분류 (전체이용가/약간노출/성인)
# 5. 문서 주제 분류 (업무/학습/개인/금융/법률계약)
```

### 3.10 `backend/api/routes.py` - API 라우트

```python
# REST API 엔드포인트:
# - GET  /api/health              → 서버 상태
# - GET  /api/ollama/status       → Ollama 연결 상태
# - GET  /api/ollama/models       → 설치된 모델 목록
# - POST /api/scan                → 폴더 스캔
# - POST /api/classify            → AI 분류 시작 (profile_id 기반)
# - POST /api/execute             → 분류 계획 실행
# - POST /api/undo                → 작업 되돌리기
# - GET  /api/config              → 현재 설정
# - PUT  /api/config              → 설정 변경
# - GET  /api/manifests           → 작업 이력 목록
# - GET  /api/browse              → 서버 파일시스템 폴더 탐색
#
# 프로파일 API:
# - GET    /api/profiles           → 프로파일 목록
# - GET    /api/profiles/{id}      → 프로파일 상세
# - POST   /api/profiles           → 프로파일 생성
# - PUT    /api/profiles/{id}      → 프로파일 수정
# - DELETE /api/profiles/{id}      → 프로파일 삭제
# - POST   /api/profiles/{id}/duplicate → 프로파일 복제

# WebSocket 엔드포인트:
# - WS   /ws/progress             → 실시간 진행 상황
```

## 4. 프론트엔드 설계

### 4.1 SPA 구조 (Single Page Application)

```
index.html
├── 헤더 (로고, 설정 버튼, 연결 상태)
├── 메인 컨텐츠 (화면별 전환)
│   ├── #home       → 메인 화면 (폴더 선택)
│   ├── #scan       → 스캔 결과 + 프로파일 선택
│   ├── #profile    → 프로파일 편집
│   ├── #profiles   → 프로파일 관리 (목록)
│   ├── #classify   → 분류 진행/결과
│   ├── #preview    → 미리보기
│   ├── #execute    → 실행 진행
│   ├── #result     → 실행 결과
│   └── #settings   → 설정
└── 푸터 (상태 바)
```

### 4.2 화면 전환 흐름

```
[Home] → 폴더 입력 → [Scan] → 스캔 완료
                              ↓
                     프로파일 선택 (또는 새로 만들기)
                              ↓
                     [Classify] → 분류 완료
                              ↓
                     [Preview] → 사용자 확인/수정
                              ↓
                     [Execute] → 실행 중
                              ↓
                     [Result] → 완료
                              ↓
                     [Home] (되돌아감)

별도 흐름:
[Profiles] → 프로파일 목록 → [Profile] → 프로파일 편집/생성
```

### 4.3 프론트엔드 기술

```javascript
// app.js 구조
const App = {
    state: {
        currentScreen: 'home',
        config: {},
        scanResult: null,
        selectedProfile: null,     // 선택된 프로파일
        classificationPlan: null,
        executionResult: null,
        profiles: [],              // 프로파일 목록
        ws: null,  // WebSocket connection
    },

    // 화면 렌더링
    screens: {
        home: { render(), bind() },
        scan: { render(), bind() },         // 스캔 결과 + 프로파일 선택
        profile: { render(), bind() },      // 프로파일 편집/생성
        profiles: { render(), bind() },     // 프로파일 관리 (목록)
        classify: { render(), bind() },
        preview: { render(), bind() },
        execute: { render(), bind() },
        result: { render(), bind() },
        settings: { render(), bind() },
    },

    // API 통신
    api: {
        scan(path),
        classify(scanResult, profileId),    // 프로파일 ID로 분류
        execute(plan, options),
        undo(manifestId),
        getConfig(),
        updateConfig(config),
        checkOllama(),
        browseFolders(path),
        // 프로파일 API
        listProfiles(),
        getProfile(id),
        createProfile(data),
        updateProfile(id, data),
        deleteProfile(id),
        duplicateProfile(id),
    },

    // WebSocket
    ws: {
        connect(),
        onProgress(callback),
        disconnect(),
    },

    // 유틸리티
    utils: {
        formatSize(bytes),
        formatDate(iso),
        navigate(screen),
    }
};
```

## 5. 데이터 흐름

### 5.1 스캔 흐름
```
사용자: 폴더 경로 입력
    ↓
Frontend: POST /api/scan {path: "D:/Photos"}
    ↓
routes.py: scan_directory 호출
    ↓
scanner.py:
    1. 경로 유효성 확인
    2. 파일 목록 수집 (메타데이터 포함)
    3. 하위 폴더 목록 수집
    4. ScanResult 반환
    ↓
Frontend: 스캔 결과 표시 + 프로파일 선택 UI
```

### 5.2 분류 흐름 (프로파일 기반)
```
사용자: 프로파일 선택 후 "AI 분석 시작" 클릭
    ↓
Frontend: POST /api/classify {scan_result, profile_id}
         + WebSocket 연결 (/ws/progress)
    ↓
routes.py: classify 태스크 시작 (백그라운드)
    ↓
    1. profile_manager.get_profile(profile_id) → 프로파일 로드
    2. 프로파일의 folders와 prompt 추출
    ↓
classifier.py: 각 파일에 대해:
    1. 파일 유형 판별
    2. 이미지면 → ai_client.classify_file(file, profile)
       문서면 → content_extractor.extract() → ai_client.classify_file(file, profile)
       기타면 → ai_client.classify_file(file, profile) (파일명만)
    3. AI 프롬프트 구성:
       system: "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요."
       user: {profile.prompt} + 폴더 목록(name: description) + 파일 정보
    4. AI 응답 파싱 → ClassificationResult
    5. 리네이밍 패턴 적용 (profile.rename_pattern)
    6. progress_callback → WebSocket으로 실시간 전송
    ↓
Frontend: 실시간 진행 표시 → 완료 시 미리보기 화면
```

### 5.3 실행 흐름
```
사용자: 미리보기 확인 후 "실행" 클릭
    ↓
Frontend: POST /api/execute {plan, options}
         + WebSocket 연결
    ↓
organizer.py: 각 파일에 대해:
    1. 대상 폴더 생성 (없는 경우)
    2. 이름 충돌 확인/해결
    3. 파일 복사 또는 이동
    4. 리네이밍 적용
    5. 매니페스트에 기록
    6. progress_callback → WebSocket
    ↓
Frontend: 결과 표시
```

### 5.4 프로파일 관리 흐름
```
사용자: 프로파일 관리 화면 접근
    ↓
Frontend: GET /api/profiles → 프로파일 목록 표시
    ↓
사용자: "새 프로파일" 또는 기존 프로파일 편집
    ↓
Frontend: 프로파일 편집 화면 (폴더 목록, 프롬프트, 패턴)
    ↓
사용자: "저장" 클릭
    ↓
Frontend: POST /api/profiles 또는 PUT /api/profiles/{id}
    ↓
profile_manager.py: JSON 파일로 저장 (data/profiles/{id}.json)
```

## 6. Ollama API 통신 상세

### 6.1 이미지 분석 요청 (프로파일 기반)
```http
POST {ollama_url}/api/generate
Content-Type: application/json

{
    "model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
    "prompt": "{profile.prompt}\n\n현재 파일명: {filename}\n사용 가능한 폴더와 설명:\n- 명작: 전문가급 퀄리티\n- 양호: 괜찮은 수준\n...\n\n반드시 JSON으로만 답하세요: {\"folder\": \"...\", \"new_name\": ..., \"description\": \"...\"}",
    "system": "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요.",
    "images": ["<base64_encoded_image>"],
    "stream": false,
    "options": {
        "temperature": 0.3,
        "num_predict": 512
    }
}
```

### 6.2 텍스트 분석 요청 (프로파일 기반)
```http
POST {ollama_url}/api/generate
Content-Type: application/json

{
    "model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
    "prompt": "{profile.prompt}\n\n현재 파일명: {filename}\n문서 내용 (처음 1000자):\n{content}\n\n사용 가능한 폴더와 설명:\n- 업무: 회사 업무 관련\n...\n\n반드시 JSON으로만 답하세요: {\"folder\": \"...\", \"new_name\": ..., \"description\": \"...\"}",
    "system": "당신은 파일 분류 AI입니다. 반드시 JSON으로만 답하세요.",
    "stream": false,
    "options": {
        "temperature": 0.3,
        "num_predict": 512
    }
}
```

### 6.3 응답 파싱 전략

```python
# 1차: JSON 직접 파싱
try:
    result = json.loads(response_text)
    return result

# 2차: 마크다운 코드블록에서 JSON 추출
except JSONDecodeError:
    if "```json" in response_text:
        json_text = extract_from_codeblock(response_text)
        result = json.loads(json_text)
        return result

# 3차: { } 사이 JSON 추출
    if "{" in response_text:
        json_text = extract_json_object(response_text)
        result = json.loads(json_text)
        return result

# 4차: 텍스트에서 프로파일 폴더명 매칭 시도
    for folder in profile.folders:
        if folder.name.lower() in response_text.lower():
            return {"folder": folder.name, "new_name": None, "description": ""}

# 5차: fallback
    return {"folder": "미분류", "new_name": None, "description": "분류 실패"}
```

## 7. 설정 파일 구조

### config/config.yaml
```yaml
# AI File Organizer v2.0 설정

# Ollama 서버 설정
ollama:
  url: "http://localhost:11434"
  model: "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct"
  timeout: 120

# 파일 처리 설정
processing:
  operation_mode: "copy"         # copy | move
  scan_recursive: false
  skip_hidden: true
  skip_system: true

# 서버 설정
server:
  host: "0.0.0.0"
  port: 5000

# 언어 설정
language: "ko"
```

### data/profiles/{uuid}.json (프로파일 파일 예시)
```json
{
    "id": "a1b2c3d4-...",
    "name": "그림 품질 분류",
    "description": "그림의 퀄리티 기준으로 분류",
    "folders": [
        {"name": "명작", "description": "전문가급 퀄리티, 구도와 색감이 뛰어남"},
        {"name": "양호", "description": "평균 이상, 괜찮은 수준"},
        {"name": "스케치", "description": "러프 스케치, 낙서, 미완성"},
        {"name": "미분류", "description": "판단 불가"}
    ],
    "prompt": "이 이미지의 그림 퀄리티를 평가하세요.\n전문가급이면 \"명작\", 괜찮으면 \"양호\", 러프하면 \"스케치\"로 분류하세요.",
    "rename_pattern": "{folder}_{description}",
    "enable_rename": true,
    "is_default": true,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00"
}
```

## 8. 에러 처리 전략

### 8.1 레이어별 에러 처리

```
Frontend  →  API 응답 코드 기반 에러 표시
              ↓
API Layer →  try/except + HTTPException 반환
              ↓
Service   →  비즈니스 로직 예외 처리 + 로깅
              ↓
Ollama    →  타임아웃/연결실패 → 재시도 → 에러 반환
```

### 8.2 HTTP 에러 코드
| 코드 | 의미 | 사용처 |
|------|------|--------|
| 200 | 성공 | 모든 성공 응답 |
| 400 | 잘못된 요청 | 경로 오류, 잘못된 파라미터 |
| 404 | 없음 | 존재하지 않는 폴더/파일/프로파일 |
| 500 | 서버 오류 | 내부 에러 |
| 503 | 서비스 불가 | Ollama 연결 실패 |

## 9. 보안 설계

### 9.1 경로 접근 제어
```python
# Path traversal 방지
def validate_path(user_path: str) -> Path:
    resolved = Path(user_path).resolve()
    # 심볼릭 링크 확인
    if resolved.is_symlink():
        raise ValueError("Symbolic links not allowed")
    # 존재 확인
    if not resolved.exists():
        raise FileNotFoundError(f"Path not found: {user_path}")
    return resolved
```

### 9.2 CORS 설정
```python
# 로컬 + 외부 도메인 허용
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
```

## 10. 의존성 목록

### requirements.txt
```
# 웹 프레임워크
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# HTTP 클라이언트 (비동기)
httpx>=0.25.0

# 파일 처리
Pillow>=10.1.0
PyPDF2>=3.0.1
python-docx>=1.1.0
openpyxl>=3.1.2

# 설정
pyyaml>=6.0.1
pydantic>=2.5.0

# 유틸리티
python-multipart>=0.0.6
aiofiles>=23.2.1
```

## 11. 실행 방법

### 11.1 개발 모드
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. Ollama 서버 확인
# Ollama가 실행 중이고 모델이 설치되어 있어야 함
# ollama pull huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct

# 3. 앱 실행
python run.py
# 또는
# uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload

# 4. 브라우저 접속
# 로컬: http://localhost:5000
# 외부: http://close-ai.iptime.org:5000
```

### 11.2 run.py
```python
import uvicorn
from backend.config import load_config

if __name__ == "__main__":
    config = load_config()
    uvicorn.run(
        "backend.main:app",
        host=config.host,
        port=config.port,
        reload=False
    )
```
