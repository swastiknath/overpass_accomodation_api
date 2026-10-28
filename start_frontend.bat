@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

cd /d "%~dp0frontend"

if not exist "node_modules\.bin\next.cmd" (
    echo Installing frontend dependencies for Windows...
    call npm install --force --include=optional --no-audit --no-fund
)

echo Starting Travel Safety Web Portal on http://localhost:3000...
node "node_modules\next\dist\bin\next" dev
