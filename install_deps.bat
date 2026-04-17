@echo off
chcp 65001 >nul
echo ===========================================
echo AI Tutor Dependency Installation
echo ===========================================

REM Set Python encoding
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org

REM Install dependencies one by one to avoid encoding issues
echo.
echo Installing dependencies...
echo.

pip install fastapi>=0.104.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install uvicorn[standard]>=0.24.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install python-multipart>=0.0.6 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install sqlalchemy[asyncio]>=2.0.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install aiosqlite>=0.19.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install redis>=5.0.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install openai>=1.0.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install chromadb>=0.4.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install pydantic>=2.0.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install pydantic-settings>=2.0.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install python-dotenv>=1.0.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install numpy>=1.24.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install scipy>=1.10.0 --trusted-host pypi.org --trusted-host files.pythonhosted.org

echo.
echo ===========================================
echo Installation Complete!
echo ===========================================
echo.
echo To start the server:
echo   1. Make sure Redis is running (if using Redis)
echo   2. Edit backend\.env and add your API keys
echo   3. Run: start_server.bat
echo.

pause
