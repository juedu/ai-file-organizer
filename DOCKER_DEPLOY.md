# AI File Organizer - Docker 배포 가이드

## 개요

이 문서는 AI File Organizer를 Docker로 빌드/배포하는 표준 절차다.
코드 변경 후 매번 이 절차를 따라 컨테이너를 갱신한다.

## 전제 조건

- Docker Desktop 설치 완료
- Ollama가 호스트 PC에서 실행 중 (포트 11434)
- 방화벽에서 포트 5000 오픈 완료

## 보안 아키텍처 (중요!)

Docker 컨테이너는 외부에 공개되므로 **SERVER_MODE=remote** 보안 모드로 작동한다.

### SERVER_MODE 개념

| 모드 | 용도 | 접근 범위 |
|------|------|-----------|
| `local` (기본) | 로컬 PC에서 직접 사용 | 모든 기능 (파일 탐색, 분류, 이동, 설정 등) |
| `remote` | Docker/외부 공개 | **원격 분류 API만** 허용, 나머지 전부 차단 |

### remote 모드 허용 엔드포인트

| 엔드포인트 | 메서드 | 인증 | 설명 |
|------------|--------|------|------|
| `/` | GET | 없음 | 랜딩 페이지 (site/index.html) |
| `/api/health` | GET | 없음 | 헬스체크 |
| `/api/remote/classify` | POST | API 키 필수 | 파일 업로드 → AI 분류 → 결과 반환 |
| `/api/profiles` | GET | 없음 | 프로파일 목록 조회 (읽기 전용) |
| `/api/ollama/status` | GET | 없음 | 서버 상태 확인 |

### remote 모드 차단 엔드포인트 (403 Forbidden)

- `/api/browse` — 서버 파일시스템 탐색
- `/api/scan` — 디렉토리 스캔
- `/api/classify` — 로컬 파일 분류
- `/api/execute` — 파일 이동/복사 실행
- `/api/undo` — 되돌리기
- `/api/manifests` — 작업 이력
- `/api/thumbnail` — 서버 이미지 접근
- `/api/config` — 서버 설정 읽기/변경
- `/api/generate-api-key` — API 키 재생성
- `/api/profiles` (POST/PUT/DELETE) — 프로파일 수정/삭제

### 보안 구현 위치

- `backend/main.py` — `SERVER_MODE` 환경변수 읽기, HTTP 미들웨어로 allowlist 검사
- `docker-compose.yml` — `SERVER_MODE=remote` 환경변수 설정
- API 키는 `config/config.yaml`에 저장, 최초 기동 시 자동 생성 후 로그 출력

### API 키 관리

- 최초 기동: `config.yaml`에 `api_key`가 비어있으면 자동 생성 (`afo_` 접두사)
- 로그에서 확인: `docker logs ai-file-organizer | findstr "API"`
- 클라이언트는 `x-api-key` 헤더에 이 키를 넣어 `/api/remote/classify` 호출

## 파일 구조

```
FileCleanup/
├── Dockerfile          # 컨테이너 이미지 정의
├── docker-compose.yml  # 서비스 구성 (포트, 볼륨, 호스트 연결, SERVER_MODE)
├── .dockerignore       # 빌드 시 제외 파일 목록
├── config/             # 볼륨 마운트 → 설정 유지
│   └── config.yaml
├── data/               # 볼륨 마운트 → 프로파일/매니페스트 유지
│   ├── profiles/
│   └── manifests/
├── backend/            # Python 백엔드 (컨테이너에 복사됨)
├── frontend/           # 관리 UI (local 모드에서만 사용)
├── site/               # 랜딩 페이지 (remote 모드에서 / 에 제공)
└── run.py              # 진입점
```

## 핵심 설정

### Ollama 연결

Docker 컨테이너에서 호스트의 Ollama에 접근하려면 `127.0.0.1`이 아닌 `host.docker.internal`을 사용해야 한다.

`config/config.yaml`:
```yaml
ollama:
  url: http://host.docker.internal:11434    # 반드시 이 주소 사용
  model: huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct
  timeout: 120
```

`docker-compose.yml`에 `extra_hosts` 설정이 이미 포함되어 있다:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### 볼륨 마운트

`config/`와 `data/`는 호스트에서 마운트된다. 컨테이너를 재빌드해도 설정과 프로파일이 유지된다.

## 배포 절차 (매 빌드 시)

### 1. 빌드 및 재시작 (한 줄)

```bash
cd D:\Vibe\FileCleanup
docker compose up -d --build
```

이 명령 하나로:
- 이미지 재빌드 (변경된 레이어만 빌드, 캐시 활용)
- 기존 컨테이너 중지 및 제거
- 새 컨테이너 시작

### 2. 확인

```bash
# 컨테이너 상태
docker ps | findstr ai-file-organizer

# 헬스체크
curl http://localhost:5000/api/health

# Ollama 연결 확인
curl http://localhost:5000/api/ollama/status

# 로그 확인
docker logs ai-file-organizer --tail 20
```

### 3. 문제 발생 시

```bash
# 컨테이너 중지
docker compose down

# 캐시 없이 완전 재빌드
docker compose build --no-cache

# 재시작
docker compose up -d

# 컨테이너 내부 진입 (디버깅)
docker exec -it ai-file-organizer bash
```

## 자주 하는 실수

| 증상 | 원인 | 해결 |
|------|------|------|
| Ollama 연결 실패 | config.yaml에 `127.0.0.1` 사용 | `host.docker.internal`로 변경 |
| 설정이 초기화됨 | config/ 볼륨 미마운트 | docker-compose.yml 확인 |
| 포트 충돌 | 5000 포트 사용 중 | `docker compose down` 후 재시작 또는 포트 변경 |
| 이미지 변경 미반영 | 빌드 없이 `up`만 실행 | `--build` 플래그 추가 |
| 관리 UI가 보임 | `SERVER_MODE=remote` 누락 | docker-compose.yml의 environment 확인 |
| API 엔드포인트 전부 차단 | 로컬에서 `SERVER_MODE=remote`로 실행 | `SERVER_MODE=local`로 변경 또는 환경변수 제거 |
| API 키를 모름 | 로그 확인 안 함 | `docker logs ai-file-organizer \| findstr API` |

## 요약: 코드 변경 후 배포

```bash
# 이것만 실행하면 된다:
cd D:\Vibe\FileCleanup && docker compose up -d --build
```

끝.
