# AI File Organizer

Ollama 로컬 AI를 활용하여 파일을 자동으로 분류하고 정리하는 웹 기반 도구입니다.  
파일 내용(텍스트, 이미지, PDF, 문서)을 AI가 분석하여 적절한 폴더로 분류해 줍니다.

## 주요 기능

- **AI 기반 파일 분류** — Ollama LLM이 파일 내용을 분석하여 카테고리 자동 판별
- **다양한 파일 형식 지원** — 이미지(Pillow), PDF(PyPDF2), Word(python-docx), Excel(openpyxl), 텍스트
- **프로파일 시스템** — 분류 규칙을 프로파일로 저장/관리, 프리셋 기본 제공
- **웹 관리 UI** — 브라우저에서 파일 탐색, 스캔, 분류, 이동을 한 번에 처리
- **실시간 진행률** — WebSocket으로 분류 진행 상황 실시간 표시
- **되돌리기** — 파일 이동 작업 이력(매니페스트) 관리 및 실행 취소
- **Docker 배포** — 원격 분류 API 서버로 배포 가능 (보안 모드 내장)

## 아키텍처

```
┌───────────────────────────────────────────────┐
│  Frontend (HTML/CSS/JS)  │  Landing (site/)   │
│  로컬 관리 UI             │  원격 공개 페이지     │
├───────────────────────────────────────────────┤
│              FastAPI Backend                   │
│  ┌──────────┬────────────┬──────────────────┐ │
│  │ Scanner  │ Classifier │ Content Extractor│ │
│  │ 파일 스캔 │ AI 분류     │ 내용 추출         │ │
│  ├──────────┼────────────┼──────────────────┤ │
│  │ Organizer│ AI Client  │ Profile Manager  │ │
│  │ 파일 이동 │ Ollama 통신 │ 분류 규칙 관리     │ │
│  └──────────┴────────────┴──────────────────┘ │
├───────────────────────────────────────────────┤
│           Ollama (로컬 LLM 서버)                │
└───────────────────────────────────────────────┘
```

## 요구 사항

- Python 3.12+
- [Ollama](https://ollama.ai/) 설치 및 실행 (포트 11434)
- 사용할 LLM 모델 다운로드 (예: `ollama pull qwen3`)

## 설치 및 실행

### 로컬 실행

```bash
# 저장소 클론
git clone https://github.com/juedu/ai-file-organizer.git
cd ai-file-organizer

# 의존성 설치
pip install -r requirements.txt

# 실행
python run.py
```

브라우저에서 `http://localhost:5001` 접속

### Docker 배포

```bash
# 빌드 및 실행 (한 줄)
docker compose up -d --build

# 상태 확인
curl http://localhost:5000/api/health
```

> Docker 배포 시 `SERVER_MODE=remote`로 동작하여 원격 분류 API만 허용됩니다.  
> 자세한 배포 가이드는 [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md)를 참고하세요.

### Windows 빠른 실행

```bash
start.bat
```

## 보안 모드

| 모드 | 용도 | 허용 범위 |
|------|------|-----------|
| `local` (기본) | 로컬 PC에서 직접 사용 | 모든 기능 (파일 탐색, 분류, 이동, 설정) |
| `remote` | Docker/외부 공개 | 원격 분류 API만 허용, 파일시스템 접근 차단 |

`remote` 모드에서는 API 키 인증이 필요하며, 최초 기동 시 자동 생성됩니다.

## 프로젝트 구조

```
ai-file-organizer/
├── run.py                  # 진입점
├── backend/
│   ├── main.py             # FastAPI 앱 (CORS, 보안 미들웨어)
│   ├── config.py           # YAML 설정 로더
│   ├── models.py           # Pydantic 데이터 모델
│   ├── api/                # REST API 라우트 + WebSocket
│   └── services/
│       ├── ai_client.py    # Ollama HTTP 클라이언트
│       ├── classifier.py   # AI 분류 로직
│       ├── content_extractor.py  # 파일 내용 추출
│       ├── scanner.py      # 디렉토리 스캔
│       ├── organizer.py    # 파일 이동/복사 실행
│       └── profile_manager.py   # 분류 프로파일 관리
├── frontend/               # 관리 UI (HTML/CSS/JS)
├── site/                   # 원격 모드 랜딩 페이지
├── config/                 # 설정 파일 (config.yaml)
├── Dockerfile
└── docker-compose.yml
```

## 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| Backend | FastAPI, Uvicorn, Pydantic |
| AI | Ollama (로컬 LLM) |
| Frontend | Vanilla HTML/CSS/JS |
| 파일 처리 | Pillow, PyPDF2, python-docx, openpyxl |
| 통신 | httpx (async), WebSocket |
| 배포 | Docker, Docker Compose |

## 라이선스

MIT License
