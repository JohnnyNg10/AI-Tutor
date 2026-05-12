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
