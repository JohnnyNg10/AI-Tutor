@echo off
chcp 65001 >nul
title AI Tutor - Start

set "PROJECT_ROOT=D:\Project\AI Tutor"
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

echo.
echo ============================================
echo   AI Tutor - Starting Servers
echo ============================================
echo.
echo   Backend:  http://localhost:8000/docs
echo   Frontend: http://localhost:5177
echo.
echo   Close each window to stop that server.
echo ============================================
echo.

REM Ensure Redis is running
echo Checking Redis...
"C:\Program Files\Redis\redis-cli.exe" ping >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting Redis...
    start "Redis" /MIN "C:\Program Files\Redis\redis-server.exe" --port 6379
    timeout /t 2 >nul
    "C:\Program Files\Redis\redis-cli.exe" ping >nul 2>&1
    if %errorlevel% neq 0 (
        echo WARNING: Redis failed to start. Backend may not work properly.
    ) else (
        echo Redis is ready.
    )
) else (
    echo Redis is already running.
)

REM Generate temp startup scripts to avoid space-in-path issues
set "BACKEND_BAT=%TEMP%\ai_tutor_backend.bat"
set "FRONTEND_BAT=%TEMP%\ai_tutor_frontend.bat"

(
echo @echo off
echo title AI Tutor Backend
echo cd /d "%PROJECT_ROOT%\backend"
echo echo Starting backend on http://localhost:8000/docs
echo "%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
echo pause
) > "%BACKEND_BAT%"

(
echo @echo off
echo title AI Tutor Frontend
echo cd /d "%PROJECT_ROOT%\frontend"
echo echo Starting frontend on http://localhost:5177
echo npm run dev
echo pause
) > "%FRONTEND_BAT%"

echo Starting backend...
start "AI Tutor Backend" "%BACKEND_BAT%"

echo Starting frontend...
start "AI Tutor Frontend" "%FRONTEND_BAT%"

echo.
echo Both servers launched in separate windows.
echo.
pause
