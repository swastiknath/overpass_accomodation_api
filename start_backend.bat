@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%~dp0"
set "PYTHONPATH=%~dp0backend"

if exist "%~dp0.venv-win\Scripts\python.exe" (
    set "PY_BIN=%~dp0.venv-win\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0india-travel-safety\.venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0india-travel-safety\.venv\Scripts\python.exe"
) else (
    set "PY_BIN=python"
)

echo Starting Travel Safety Backend on http://localhost:8000...
"%PY_BIN%" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "%~dp0backend"
