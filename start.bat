@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title AI File Organizer
color 0A

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       AI File Organizer v2.1             ║
echo  ║       Starting up...                     ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── 1. Python 확인 ──
where python >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  [ERROR] Python이 설치되어 있지 않습니다!
    echo.
    echo  아래 링크에서 Python 3.10 이상을 설치하세요:
    echo  https://www.python.org/downloads/
    echo.
    echo  설치 시 반드시 "Add Python to PATH" 체크하세요!
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

:: Python 버전 확인
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% 감지됨

:: ── 2. 가상환경 확인/생성 ──
if not exist "%~dp0venv" (
    echo  [..] 가상환경 생성 중... (최초 1회)
    python -m venv "%~dp0venv"
    if %errorlevel% neq 0 (
        echo  [ERROR] 가상환경 생성 실패
        pause
        exit /b 1
    )
    echo  [OK] 가상환경 생성 완료
)

:: ── 3. 가상환경 활성화 ──
call "%~dp0venv\Scripts\activate.bat"
echo  [OK] 가상환경 활성화됨

:: ── 4. 의존성 설치 확인 ──
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [..] 필요한 패키지 설치 중... (최초 1회, 1-2분 소요)
    pip install -r "%~dp0requirements.txt" --quiet
    if %errorlevel% neq 0 (
        echo  [ERROR] 패키지 설치 실패
        echo  인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
    echo  [OK] 패키지 설치 완료
) else (
    echo  [OK] 패키지 확인됨
)

:: ── 5. 모드 확인 및 Ollama 상태 확인 ──
:: config.yaml에서 mode 확인
set MODE=local
if exist "%~dp0config\config.yaml" (
    findstr /c:"mode: remote" "%~dp0config\config.yaml" >nul 2>&1
    if !errorlevel! equ 0 set MODE=remote
)

if "%MODE%"=="remote" (
    echo  [OK] 원격 모드 - Ollama 불필요, 외부 서버에 연결합니다
) else (
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:11434/api/tags >nul 2>&1
    if %errorlevel% neq 0 (
        color 0E
        echo.
        echo  [경고] Ollama가 실행되고 있지 않습니다!
        echo  AI 분류 기능을 사용하려면 Ollama를 먼저 실행하세요.
        echo  Ollama 다운로드: https://ollama.ai
        echo.
        echo  Ollama 없이도 서버는 시작됩니다.
        echo  원격 모드로 사용하려면 설정 페이지에서 모드를 변경하세요.
        echo.
        color 0A
    )
)

:: ── 6. 서버 시작 ──
echo.
echo  ══════════════════════════════════════════
echo   서버 시작 중...
echo   브라우저에서 http://localhost:5000 접속하세요
echo   종료하려면 이 창을 닫거나 Ctrl+C를 누르세요
echo  ══════════════════════════════════════════
echo.

:: 브라우저 자동 오픈 (2초 뒤)
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: 서버 실행
cd /d "%~dp0"
python run.py

:: 서버 종료 시
echo.
echo  서버가 종료되었습니다.
pause
