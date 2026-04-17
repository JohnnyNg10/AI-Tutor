@echo off
chcp 65001 >nul
echo ===========================================
echo AI Tutor Server Startup
echo ===========================================

cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate

REM Set encoding
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Change to backend directory
cd backend

echo.
echo Starting AI Tutor Server...
echo API Docs will be available at: http://localhost:8000/docs
echo.

REM Start the server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
