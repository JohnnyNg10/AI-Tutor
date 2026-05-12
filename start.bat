@echo off
chcp 65001 >nul
title AI Tutor - Start

set PROJECT_ROOT=D:\Project\AI Tutor
set VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe

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

echo Starting backend...
start "AI Tutor Backend" cmd /k "cd /d %PROJECT_ROOT%\backend && title AI Tutor Backend && %VENV_PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting frontend...
start "AI Tutor Frontend" cmd /k "cd /d %PROJECT_ROOT%\frontend && title AI Tutor Frontend && npm run dev"

echo.
echo Both servers launched in separate windows.
echo.
pause
