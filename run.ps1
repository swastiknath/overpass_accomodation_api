<#
.SYNOPSIS
    Unified Self-Bootstrapping Runner for Windows (PowerShell)
    Automatically installs Python and Node.js prerequisites if missing,
    prepares virtual environments, dependencies, and runs both Backend & Frontend.
#>

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Preparing & Launching India Travel Safety Platform (Windows)   " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Refresh PATH from Machine and User environment variables
$MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$MachinePath;$UserPath"

# 1. Check real Python 3.10+ (ignoring Windows Store stub)
$PythonExe = $null
foreach ($candidate in @("python.exe", "py.exe")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        & $cmd.Source -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = $cmd.Source
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Host "[!] Python 3.10+ not found on system. Attempting automatic installation..." -ForegroundColor Yellow
    $WingetCmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($WingetCmd) {
        Write-Host "Installing Python 3.12 via winget..." -ForegroundColor Green
        & winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        Start-Sleep -Seconds 5
    } else {
        Write-Host "Downloading official Python 3.12 installer..." -ForegroundColor Green
        $InstallerUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
        $TempInstaller = Join-Path $env:TEMP "python-installer.exe"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $InstallerUrl -OutFile $TempInstaller
        Write-Host "Running silent Python installation..." -ForegroundColor Green
        Start-Process -FilePath $TempInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
        Remove-Item $TempInstaller -ErrorAction SilentlyContinue
    }
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonExe = $PythonCmd.Source
    } else {
        $PythonExe = "python"
    }
}

# 2. Check Node.js / npm
$NodeCmd = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $NodeCmd) {
    Write-Host "[!] Node.js / npm not found on system. Attempting automatic installation..." -ForegroundColor Yellow
    $WingetCmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($WingetCmd) {
        Write-Host "Installing Node.js LTS via winget..." -ForegroundColor Green
        & winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        Start-Sleep -Seconds 5
    } else {
        Write-Host "Downloading official Node.js LTS installer..." -ForegroundColor Green
        $NodeUrl = "https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi"
        $TempNode = Join-Path $env:TEMP "node-installer.msi"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $NodeUrl -OutFile $TempNode
        Write-Host "Running silent Node.js installation..." -ForegroundColor Green
        Start-Process msiexec.exe -ArgumentList "/i `"$TempNode`" /quiet /qn" -Wait
        Remove-Item $TempNode -ErrorAction SilentlyContinue
    }
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# 3. Launch unified runner
Write-Host "Running cross-platform Python launcher..." -ForegroundColor Green
if ($args.Count -gt 0) {
    & $PythonExe "$ScriptDir\run.py" @args
} else {
    & $PythonExe "$ScriptDir\run.py"
}
