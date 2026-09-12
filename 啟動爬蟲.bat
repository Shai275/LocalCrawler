@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set "CRAWLER_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%CRAWLER_PY%" set "CRAWLER_PY=python"
if exist ".venv\Scripts\python.exe" set "CRAWLER_PY=.venv\Scripts\python.exe"
"%CRAWLER_PY%" app.py
if errorlevel 1 (
  echo.
  echo 啟動失敗，請查看上方錯誤及 README.md。
  pause
)
