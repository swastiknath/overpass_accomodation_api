@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

title India Travel Safety Platform - Unified Launcher

echo =================================================================
echo   Preparing ^& Launching India Travel Safety Platform (Windows)   
echo =================================================================
echo.

cd /d "%~dp0"

:: Ensure Windows system directories and standard tools are always on PATH
if defined SystemRoot (
    set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;!PATH!"
) else (
    set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;!PATH!"
)

:: Augment PATH with common Windows install locations for Python & Node.js
if exist "%ProgramFiles%\nodejs" set "PATH=%ProgramFiles%\nodejs;!PATH!"
if defined ProgramFiles(x86) (
    if exist "%ProgramFiles(x86)%\nodejs" set "PATH=%ProgramFiles(x86)%\nodejs;!PATH!"
)
if exist "%LOCALAPPDATA%\Programs\nodejs" set "PATH=%LOCALAPPDATA%\Programs\nodejs;!PATH!"
if exist "%APPDATA%\npm" set "PATH=%APPDATA%\npm;!PATH!"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    set "PATH=%%~fD;%%~fD\Scripts;!PATH!"
)

:: ====================================================================
:: 1. Check Python
:: ====================================================================
set "PY_CMD="

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and 'WindowsApps' not in sys.executable else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :python_found
)

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and 'WindowsApps' not in sys.executable else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3"
    goto :python_found
)

echo [!] Python 3.10+ was not found on your system PATH.
echo Please install Python manually:
echo  1. Download Python 3.12: https://www.python.org/downloads/
echo  2. IMPORTANT: Check the box "Add python.exe to PATH" during setup.
echo.
pause
exit /b 1

:python_found
echo [OK] Using Python:
!PY_CMD! --version

:: ====================================================================
:: 2. Check Node.js & npm
:: ====================================================================
where node.exe >nul 2>&1
if !errorlevel! equ 0 goto :node_found

echo.
echo [!] Node.js and npm were not found on your system PATH.
echo Downloading official Node.js installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi' -OutFile '%TEMP%\node_installer.msi'"

if not exist "%TEMP%\node_installer.msi" goto :node_download_failed

echo Launching Node.js installer...
echo Please complete the setup wizard to install Node.js.
start /wait msiexec /i "%TEMP%\node_installer.msi"
del "%TEMP%\node_installer.msi" 2>nul

if exist "%ProgramFiles%\nodejs" set "PATH=%ProgramFiles%\nodejs;!PATH!"
if defined ProgramFiles(x86) (
    if exist "%ProgramFiles(x86)%\nodejs" set "PATH=%ProgramFiles(x86)%\nodejs;!PATH!"
)

where node.exe >nul 2>&1
if !errorlevel! equ 0 goto :node_found

:node_download_failed
echo.
echo [ERROR] Node.js is required for the frontend portal.
echo Please install Node.js LTS manually:
echo  1. Download from: https://nodejs.org/
echo  2. Run the installer and finish setup
echo  3. Restart your terminal or VS Code and re-run run.bat
echo.
pause
exit /b 1

:node_found
echo [OK] Using Node.js:
node --version

:: ====================================================================
:: 3. Run the unified Python launcher
:: ====================================================================
echo.
echo Launching unified cross-platform runner...
!PY_CMD! "%~dp0run.py" %*

set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo =================================================================
echo   Launcher finished with exit code %EXIT_CODE%.
echo =================================================================
pause
exit /b %EXIT_CODE%
