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

:: Ensure Windows system directories and standard tools (ping, where, powershell) are always on PATH
if defined SystemRoot (
    set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;!PATH!"
) else (
    set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;!PATH!"
)

:: Augment PATH with common Windows install locations for Python & Node.js
if exist "%ProgramFiles%\nodejs" set "PATH=%ProgramFiles%\nodejs;!PATH!"
if exist "%ProgramFiles(x86)%\nodejs" set "PATH=%ProgramFiles(x86)%\nodejs;!PATH!"
if exist "%LOCALAPPDATA%\Programs\nodejs" set "PATH=%LOCALAPPDATA%\Programs\nodejs;!PATH!"
if exist "%APPDATA%\npm" set "PATH=%APPDATA%\npm;!PATH!"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    set "PATH=%%~fD;%%~fD\Scripts;!PATH!"
)

:: 1. Check if a real Python 3.10+ is installed (avoiding Windows Store stub)
set "PY_CMD="

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and 'WindowsApps' not in sys.executable else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
) else (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and 'WindowsApps' not in sys.executable else 1)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=py -3"
    )
)

if "!PY_CMD!"=="" (
    echo [!] Python 3.10+ was not found on your system PATH.
    echo Attempting automatic installation via winget...
    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        ping 127.0.0.1 -n 5 >nul 2>&1
        for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
            set "PATH=%%~fD;%%~fD\Scripts;!PATH!"
        )
        set "PY_CMD=python"
    ) else (
        echo [!] winget not available. Downloading official Python 3.12 installer...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
        if exist "%TEMP%\python_installer.exe" (
            echo Running Python installer...
            start /wait "" "%TEMP%\python_installer.exe" InstallAllUsers=0 PrependPath=1 Include_test=0
            del "%TEMP%\python_installer.exe" 2>nul
            for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
                set "PATH=%%~fD;%%~fD\Scripts;!PATH!"
            )
            set "PY_CMD=python"
        )
    )
)

:: Verify Python is truly executable
!PY_CMD! --version >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Python 3.10 or higher is required but could not be found or executed.
    echo.
    echo Please install Python manually:
    echo  1. Download Python 3.12: https://www.python.org/downloads/
    echo  2. IMPORTANT: Check the box "Add python.exe to PATH" in the installer.
    echo  3. Disable Windows App Execution Aliases if needed:
    echo     Settings -^> Apps -^> Advanced app settings -^> App execution aliases
    echo     Turn OFF "App Installer (python.exe)" and "App Installer (python3.exe)".
    echo.
    pause
    exit /b 1
)

echo [OK] Using Python:
!PY_CMD! --version

:: 2. Check if Node.js & npm are installed
where node.exe >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo [!] Node.js and npm were not found on your system PATH.
    echo Downloading official Node.js installer...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi' -OutFile '%TEMP%\node_installer.msi'"
    if exist "%TEMP%\node_installer.msi" (
        echo Launching Node.js installer with administrative prompt (UAC)...
        echo Please click "Yes" / "Next" on the installer window to complete setup.
        start /wait msiexec /i "%TEMP%\node_installer.msi"
        del "%TEMP%\node_installer.msi" 2>nul
        if exist "%ProgramFiles%\nodejs" set "PATH=%ProgramFiles%\nodejs;!PATH!"
        if exist "%ProgramFiles(x86)%\nodejs" set "PATH=%ProgramFiles(x86)%\nodejs;!PATH!"
    )
)

where node.exe >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Node.js is required for the frontend portal.
    echo The silent winget/msi installer failed (code 1603 requires Administrator permissions).
    echo.
    echo Please install Node.js manually:
    echo  1. Go to: https://nodejs.org/
    echo  2. Download and run the recommended LTS installer (.msi)
    echo  3. Click "Next" through the setup and finish
    echo  4. Restart VS Code or your terminal window and re-run run.bat
    echo.
    pause
    exit /b 1
)

echo [OK] Using Node.js:
node --version

:: 3. Run the unified Python launcher
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
