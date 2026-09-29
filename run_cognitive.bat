@echo off
cd /d "%~dp0"

echo ==========================================
echo Smirthi - Cognitive Companion for Elders
echo ==========================================

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Using system Python.
)

start "" "http://127.0.0.1:5000/cognitive"

python web_app.py

pause