@echo off
REM Run the SwasthGati web application and open the browser
chcp 65001 >nul
set PYTHONUTF8=1
start "SwasthGati Web" cmd /k "cd /d %~dp0 && .\.venv\Scripts\python.exe web_app.py"
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5000
pause
