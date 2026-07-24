@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    py -3 -m venv ".venv" >nul 2>&1
    if errorlevel 1 python -m venv ".venv"
    if errorlevel 1 (
        echo Python 3.11 or newer is required.
        echo Please install Python and try again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages. This may take a few minutes...
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 (
        echo Failed to install required packages.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0run.py"
exit /b 0
