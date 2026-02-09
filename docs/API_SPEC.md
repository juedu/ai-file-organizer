# API Specification: AI File Organizer

## Base URL
```
http://localhost:5000/api
또는
http://close-ai.iptime.org:5000/api
```

## 공통 응답 형식
```json
{
    "success": true,
    "data": { ... },
    "error": null
}
```
실패 시:
```json
{
    "success": false,
    "data": null,
    "error": "에러 메시지"
}
```

---

## 1. 시스템 API

### `GET /api/health`
서버 상태 확인

**응답 200:**
```json
{
    "success": true,
    "data": {
        "status": "ok",
        "version": "2.0.0"
    }
}
```

---

### `GET /api/ollama/status`
Ollama 서버 연결 상태 확인

**응답 200:**
```json
{
    "success": true,
    "data": {
        "connected": true,
        "url": "http://localhost:11434",
        "current_model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
        "models": [
            "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
            "llama3.1:8b"
        ],
        "error": null
    }
}
```

**응답 503 (연결 실패):**
```json
{
    "success": false,
    "data": {
        "connected": false,
        "url": "http://localhost:11434",
        "current_model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
        "models": [],
        "error": "Connection refused"
    }
}
```

---

## 2. 프로파일 API

### `GET /api/profiles`
분류 프로파일 목록 조회

**응답 200:**
```json
{
    "success": true,
    "data": [
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "name": "기본 파일 정리",
            "description": "파일 종류별 기본 분류",
            "folders": [
                {"name": "사진", "description": "실제 촬영 사진"},
                {"name": "그림", "description": "디지털 아트, 일러스트, 팬아트"},
                {"name": "문서", "description": "PDF, Word, 텍스트 문서"},
                {"name": "기타", "description": "위에 해당하지 않는 파일"}
            ],
            "prompt": "이 파일의 종류와 내용을 분석하여 가장 적합한 폴더를 선택하세요.",
            "rename_pattern": "{description}",
            "enable_rename": true,
            "is_default": true,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00"
        },
        {
            "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "name": "그림 품질 분류",
            "description": "그림의 퀄리티 기준으로 분류",
            "folders": [
                {"name": "명작", "description": "전문가급 퀄리티, 구도와 색감이 뛰어남"},
                {"name": "양호", "description": "평균 이상, 괜찮은 수준"},
                {"name": "스케치", "description": "러프 스케치, 낙서, 미완성"},
                {"name": "미분류", "description": "판단 불가"}
            ],
            "prompt": "이 이미지의 그림 퀄리티를 평가하세요.",
            "rename_pattern": "{folder}_{description}",
            "enable_rename": true,
            "is_default": true,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00"
        }
    ]
}
```

---

### `GET /api/profiles/{id}`
프로파일 상세 조회

**응답 200:**
```json
{
    "success": true,
    "data": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "그림 품질 분류",
        "description": "그림의 퀄리티 기준으로 분류",
        "folders": [
            {"name": "명작", "description": "전문가급 퀄리티, 구도와 색감이 뛰어남"},
            {"name": "양호", "description": "평균 이상, 괜찮은 수준"},
            {"name": "보통", "description": "평범한 수준"},
            {"name": "스케치", "description": "러프 스케치, 낙서, 미완성"}
        ],
        "prompt": "이 이미지의 그림 퀄리티를 평가하세요.\n전문가급이면 \"명작\", 괜찮으면 \"양호\", 평범하면 \"보통\", 러프하면 \"스케치\"로 분류하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": true,
        "is_default": true,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00"
    }
}
```

**응답 404:**
```json
{
    "success": false,
    "error": "프로파일을 찾을 수 없습니다: invalid-id"
}
```

---

### `POST /api/profiles`
프로파일 생성

**요청:**
```json
{
    "name": "애니 캐릭터 분류",
    "description": "애니메이션 캐릭터 이미지를 작품별로 분류",
    "folders": [
        {"name": "원피스", "description": "원피스 캐릭터 이미지"},
        {"name": "나루토", "description": "나루토 캐릭터 이미지"},
        {"name": "귀멸의칼날", "description": "귀멸의 칼날 캐릭터 이미지"},
        {"name": "기타애니", "description": "위에 해당하지 않는 애니 캐릭터"}
    ],
    "prompt": "이 이미지가 어떤 애니메이션 작품의 캐릭터인지 판단하세요.",
    "rename_pattern": "{folder}_{description}",
    "enable_rename": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| name | string | Y | 프로파일 이름 |
| description | string | N | 프로파일 설명 |
| folders | ProfileFolder[] | Y | 분류 폴더 목록 (최소 2개) |
| prompt | string | Y | AI 분류 프롬프트 |
| rename_pattern | string | N | 리네이밍 패턴 (기본: "{description}") |
| enable_rename | boolean | N | 리네이밍 활성화 (기본: true) |

**응답 200:**
```json
{
    "success": true,
    "data": {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "name": "애니 캐릭터 분류",
        "description": "애니메이션 캐릭터 이미지를 작품별로 분류",
        "folders": [...],
        "prompt": "이 이미지가 어떤 애니메이션 작품의 캐릭터인지 판단하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": true,
        "is_default": false,
        "created_at": "2025-06-15T10:30:00",
        "updated_at": "2025-06-15T10:30:00"
    }
}
```

---

### `PUT /api/profiles/{id}`
프로파일 수정

**요청:**
```json
{
    "name": "애니 캐릭터 분류 v2",
    "folders": [
        {"name": "원피스", "description": "원피스 캐릭터 이미지"},
        {"name": "나루토", "description": "나루토 캐릭터 이미지"},
        {"name": "귀멸의칼날", "description": "귀멸의 칼날 캐릭터 이미지"},
        {"name": "주술회전", "description": "주술회전 캐릭터 이미지"},
        {"name": "기타애니", "description": "위에 해당하지 않는 애니 캐릭터"}
    ]
}
```

부분 업데이트 지원: 변경할 필드만 전송하면 나머지는 유지됩니다.

**응답 200:**
```json
{
    "success": true,
    "data": { ... }
}
```

---

### `DELETE /api/profiles/{id}`
프로파일 삭제

**응답 200:**
```json
{
    "success": true,
    "data": {
        "message": "프로파일이 삭제되었습니다."
    }
}
```

**응답 400 (기본 프로파일 삭제 시도):**
```json
{
    "success": false,
    "error": "기본 프로파일은 삭제할 수 없습니다."
}
```

---

### `POST /api/profiles/{id}/duplicate`
프로파일 복제

**응답 200:**
```json
{
    "success": true,
    "data": {
        "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
        "name": "애니 캐릭터 분류 (사본)",
        "is_default": false,
        ...
    }
}
```

---

## 3. 파일 시스템 API

### `GET /api/browse`
서버 파일시스템 폴더 탐색 (폴더 선택 UI용)

**쿼리 파라미터:**
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| path | string | N | 탐색할 경로 (미지정 시 드라이브 목록) |

**요청 예시:**
```
GET /api/browse?path=D:\Photos
```

**응답 200:**
```json
{
    "success": true,
    "data": {
        "current_path": "D:\\Photos",
        "parent_path": "D:\\",
        "folders": [
            {"name": "2024", "path": "D:\\Photos\\2024"},
            {"name": "가족", "path": "D:\\Photos\\가족"},
            {"name": "여행", "path": "D:\\Photos\\여행"}
        ],
        "is_root": false
    }
}
```

**드라이브 목록 (path 미지정 시, Windows):**
```json
{
    "success": true,
    "data": {
        "current_path": "",
        "parent_path": null,
        "folders": [
            {"name": "C:", "path": "C:\\"},
            {"name": "D:", "path": "D:\\"}
        ],
        "is_root": true
    }
}
```

---

### `POST /api/scan`
지정 폴더 스캔

**요청:**
```json
{
    "path": "D:\\Photos",
    "recursive": false
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| path | string | Y | - | 스캔할 폴더 절대 경로 |
| recursive | boolean | N | false | 재귀 스캔 여부 |

**응답 200:**
```json
{
    "success": true,
    "data": {
        "base_path": "D:\\Photos",
        "files": [
            {
                "path": "D:\\Photos\\IMG_1234.jpg",
                "filename": "IMG_1234.jpg",
                "extension": ".jpg",
                "size": 2548736,
                "size_display": "2.4 MB",
                "modified": "2024-03-15T10:30:00",
                "mime_type": "image/jpeg",
                "category": "image"
            },
            {
                "path": "D:\\Photos\\보고서.pdf",
                "filename": "보고서.pdf",
                "extension": ".pdf",
                "size": 1048576,
                "size_display": "1.0 MB",
                "modified": "2024-06-20T14:00:00",
                "mime_type": "application/pdf",
                "category": "document"
            }
        ],
        "subfolders": [
            {"name": "여행", "path": "D:\\Photos\\여행", "file_count": 45},
            {"name": "가족", "path": "D:\\Photos\\가족", "file_count": 23}
        ],
        "total_files": 2,
        "total_size": 3597312,
        "total_size_display": "3.4 MB",
        "type_distribution": {
            ".jpg": 1,
            ".pdf": 1
        }
    }
}
```

**응답 400 (경로 오류):**
```json
{
    "success": false,
    "error": "Path does not exist: D:\\Invalid"
}
```

---

## 4. 분류 API

### `POST /api/classify`
AI 파일 분류 시작 (프로파일 기반, 비동기, WebSocket으로 진행 상황 전송)

**요청:**
```json
{
    "base_path": "D:\\Photos",
    "files": [
        {
            "path": "D:\\Photos\\IMG_1234.jpg",
            "filename": "IMG_1234.jpg",
            "extension": ".jpg",
            "size": 2548736,
            "size_display": "2.4 MB",
            "modified": "2024-03-15T10:30:00",
            "mime_type": "image/jpeg",
            "category": "image"
        }
    ],
    "profile_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| base_path | string | Y | - | 대상 폴더 경로 |
| files | FileItem[] | Y | - | 분류할 파일 목록 |
| profile_id | string | Y | - | 분류에 사용할 프로파일 ID |

**응답 200 (분류 완료):**
```json
{
    "success": true,
    "data": {
        "profile_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "results": [
            {
                "file_path": "D:\\Photos\\IMG_1234.jpg",
                "filename": "IMG_1234.jpg",
                "target_folder": "명작",
                "new_name": "명작_용을_그린_판타지_일러스트.jpg",
                "description": "드래곤을 묘사한 고퀄리티 판타지 일러스트",
                "confidence": 0.85,
                "status": "success"
            },
            {
                "file_path": "D:\\Photos\\보고서.pdf",
                "filename": "보고서.pdf",
                "target_folder": "양호",
                "new_name": null,
                "description": "일반적인 문서 파일",
                "confidence": 0.9,
                "status": "success"
            }
        ],
        "total_files": 2,
        "classified": 2,
        "errors": 0,
        "folder_summary": {
            "명작": 1,
            "양호": 1
        }
    }
}
```

---

## 5. 실행 API

### `POST /api/execute`
분류 계획 실행 (파일 이동/복사/리네이밍)

**요청:**
```json
{
    "base_path": "D:\\Photos",
    "results": [
        {
            "file_path": "D:\\Photos\\IMG_1234.jpg",
            "filename": "IMG_1234.jpg",
            "target_folder": "명작",
            "new_name": "명작_용을_그린_판타지_일러스트.jpg",
            "description": "드래곤을 묘사한 고퀄리티 판타지 일러스트",
            "confidence": 0.85,
            "status": "success"
        }
    ],
    "operation_mode": "copy"
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| base_path | string | Y | - | 대상 폴더 경로 |
| results | ClassificationResult[] | Y | - | 실행할 분류 결과 |
| operation_mode | string | N | "copy" | copy / move |

**응답 200:**
```json
{
    "success": true,
    "data": {
        "total": 1,
        "success": 1,
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "manifest_id": "20240315_103000",
        "duration": 0.5
    }
}
```

---

### `POST /api/undo`
작업 되돌리기

**요청:**
```json
{
    "manifest_id": "20240315_103000"
}
```

**응답 200:**
```json
{
    "success": true,
    "data": {
        "total": 1,
        "success": 1,
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "manifest_id": "undo_20240315_103000",
        "duration": 0.3
    }
}
```

---

### `GET /api/manifests`
작업 이력 목록

**응답 200:**
```json
{
    "success": true,
    "data": [
        {
            "manifest_id": "20240315_103000",
            "timestamp": "2024-03-15T10:30:00",
            "operation_mode": "copy",
            "total_files": 15,
            "success_files": 15,
            "base_path": "D:\\Photos",
            "profile_name": "그림 품질 분류"
        }
    ]
}
```

---

## 6. 설정 API

### `GET /api/config`
현재 설정 조회

**응답 200:**
```json
{
    "success": true,
    "data": {
        "ollama": {
            "url": "http://localhost:11434",
            "model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
            "timeout": 120
        },
        "processing": {
            "operation_mode": "copy",
            "scan_recursive": false,
            "skip_hidden": true,
            "skip_system": true
        },
        "server": {
            "host": "0.0.0.0",
            "port": 5000
        },
        "language": "ko"
    }
}
```

---

### `PUT /api/config`
설정 변경

**요청:**
```json
{
    "ollama": {
        "url": "http://close-ai.iptime.org:11434",
        "model": "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct",
        "timeout": 180
    },
    "processing": {
        "operation_mode": "move"
    },
    "language": "en"
}
```

부분 업데이트 지원: 변경할 필드만 전송.

**응답 200:**
```json
{
    "success": true,
    "data": {
        "message": "설정이 저장되었습니다."
    }
}
```

---

## 7. WebSocket API

### `WS /ws/progress`
실시간 진행 상황 업데이트

**연결:**
```javascript
const ws = new WebSocket("ws://localhost:5000/ws/progress");
// 또는
const ws = new WebSocket("ws://close-ai.iptime.org:5000/ws/progress");
```

**수신 메시지 (분류 진행):**
```json
{
    "stage": "classifying",
    "current": 3,
    "total": 50,
    "current_file": "IMG_5678.jpg",
    "message": "분류 중: IMG_5678.jpg",
    "result": {
        "file_path": "D:\\Photos\\IMG_5678.jpg",
        "filename": "IMG_5678.jpg",
        "target_folder": "명작",
        "new_name": "명작_아기_첫걸음.jpg",
        "description": "아기가 첫 걸음을 떼는 순간의 사진",
        "confidence": 0.92,
        "status": "success"
    }
}
```

**수신 메시지 (실행 진행):**
```json
{
    "stage": "executing",
    "current": 5,
    "total": 50,
    "current_file": "보고서.pdf",
    "message": "파일 복사 중...",
    "result": null
}
```

**수신 메시지 (완료):**
```json
{
    "stage": "complete",
    "current": 50,
    "total": 50,
    "current_file": "",
    "message": "완료",
    "result": null
}
```

**수신 메시지 (에러):**
```json
{
    "stage": "error",
    "current": 0,
    "total": 0,
    "current_file": "",
    "message": "Ollama 서버 연결에 실패했습니다.",
    "result": null
}
```

---

## 8. 에러 응답 상세

### 400 Bad Request
```json
{
    "success": false,
    "error": "path 필드는 필수입니다."
}
```

### 404 Not Found
```json
{
    "success": false,
    "error": "프로파일을 찾을 수 없습니다: invalid-id"
}
```

### 500 Internal Server Error
```json
{
    "success": false,
    "error": "내부 서버 오류가 발생했습니다."
}
```

### 503 Service Unavailable
```json
{
    "success": false,
    "error": "Ollama 서버에 연결할 수 없습니다. URL을 확인해 주세요."
}
```
