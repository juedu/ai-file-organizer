#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║       AI File Organizer v2.1             ║"
echo "  ║       Starting up...                     ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── 1. Python 확인 ──
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$($cmd --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  [ERROR] Python 3.10 이상이 필요합니다!"
    echo ""
    echo "  설치 방법:"
    echo "    Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "    macOS:         brew install python3"
    echo "    기타:          https://www.python.org/downloads/"
    echo ""
    exit 1
fi

echo "  [OK] $($PYTHON --version) 감지됨"

# ── 2. 가상환경 확인/생성 ──
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "  [..] 가상환경 생성 중... (최초 1회)"
    $PYTHON -m venv "$SCRIPT_DIR/venv"
    echo "  [OK] 가상환경 생성 완료"
fi

# ── 3. 가상환경 활성화 ──
source "$SCRIPT_DIR/venv/bin/activate"
echo "  [OK] 가상환경 활성화됨"

# ── 4. 의존성 설치 확인 ──
if ! python -c "import fastapi" 2>/dev/null; then
    echo "  [..] 필요한 패키지 설치 중... (최초 1회)"
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
    echo "  [OK] 패키지 설치 완료"
else
    echo "  [OK] 패키지 확인됨"
fi

# ── 5. 모드 확인 및 Ollama 상태 확인 ──
MODE="local"
if [ -f "$SCRIPT_DIR/config/config.yaml" ]; then
    if grep -q "mode: remote" "$SCRIPT_DIR/config/config.yaml" 2>/dev/null; then
        MODE="remote"
    fi
fi

if [ "$MODE" = "remote" ]; then
    echo "  [OK] 원격 모드 - Ollama 불필요, 외부 서버에 연결합니다"
else
    if ! curl -s http://127.0.0.1:11434/api/tags &>/dev/null; then
        echo ""
        echo "  [경고] Ollama가 실행되고 있지 않습니다!"
        echo "  AI 분류 기능을 사용하려면 Ollama를 먼저 실행하세요."
        echo "  Ollama 다운로드: https://ollama.ai"
        echo ""
        echo "  원격 모드로 사용하려면 설정 페이지에서 모드를 변경하세요."
        echo ""
    fi
fi

# ── 6. 서버 시작 ──
echo ""
echo "  ══════════════════════════════════════════"
echo "   서버 시작 중..."
echo "   브라우저에서 http://localhost:5001 접속하세요"
echo "   종료하려면 Ctrl+C를 누르세요"
echo "  ══════════════════════════════════════════"
echo ""

# 브라우저 자동 오픈 (2초 뒤)
(sleep 2 && (xdg-open http://localhost:5001 2>/dev/null || open http://localhost:5001 2>/dev/null || true)) &

python run.py
