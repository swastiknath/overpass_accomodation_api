@echo off
setlocal enabledelayedexpansion

title India Travel Safety Platform - Unified Launcher

echo =================================================================
echo   Preparing ^& Launching India Travel Safety Platform (Windows)   
echo =================================================================

cd /d "%~dp0"

:: 1. Check if Python is installed
set "PY_CMD="
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
) else (
    py -3 --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [!] Python was not found on your system.
    echo Attempting automatic installation via winget...
    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        timeout /t 5 >nul
        set "PY_CMD=python"
    ) else (
        echo [!] winget not available. Downloading official Python 3.11 installer...
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%TEMP%\python_installer.exe')"
        echo Installing Python silently...
        start /wait "" "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
        del "%TEMP%\python_installer.exe" 2>nul
        set "PY_CMD=python"
    )
)

:: 2. Check if Node.js & npm are installed
npm --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [!] Node.js and npm were not found on your system.
    echo Attempting automatic installation via winget...
    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        echo Refreshing environment variables...
        timeout /t 5 >nul
    ) else (
        echo [!] Downloading official Node.js installer...
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi', '%TEMP%\node_installer.msi')"
        echo Installing Node.js silently...
        msiexec /i "%TEMP%\node_installer.msi" /quiet /qn
        del "%TEMP%\node_installer.msi" 2>nul
    )
)

:: 3. Run the unified Python launcher
echo Launching unified cross-platform runner...
%PY_CMD% run.py %*

if !errorlevel! neq 0 (
    echo.
    echo [!] Launcher exited with error code !errorlevel!.
    pause
)
