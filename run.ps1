<#
.SYNOPSIS
    Unified Self-Bootstrapping Runner for Windows (PowerShell)
    Automatically installs Python and Node.js prerequisites if missing,
    prepares virtual environments, dependencies, and runs both Backend & Frontend.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Preparing & Launching India Travel Safety Platform (Windows)   " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check Python
$PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py.exe -ErrorAction SilentlyContinue
}

if (-not $PythonCmd) {
    Write-Host "! Python not found on system. Attempting automatic installation..." -ForegroundColor Yellow
    $WingetCmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($WingetCmd) {
        Write-Host "Installing Python via winget..." -ForegroundColor Green
        & winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        Start-Sleep -Seconds 5
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    } else {
        Write-Host "Downloading official Python 3.11 installer..." -ForegroundColor Green
        $InstallerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $TempInstaller = Join-Path $env:TEMP "python-installer.exe"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $InstallerUrl -OutFile $TempInstaller
        Write-Host "Running silent Python installation..." -ForegroundColor Green
        Start-Process -FilePath $TempInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
        Remove-Item $TempInstaller -ErrorAction SilentlyContinue
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    }
}

# 2. Check Node.js / npm
$NpmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $NpmCmd) {
    Write-Host "! Node.js / npm not found on system. Attempting automatic installation..." -ForegroundColor Yellow
    $WingetCmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($WingetCmd) {
        Write-Host "Installing Node.js via winget..." -ForegroundColor Green
        & winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        Start-Sleep -Seconds 5
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } else {
        Write-Host "Downloading official Node.js installer..." -ForegroundColor Green
        $NodeUrl = "https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi"
        $TempNode = Join-Path $env:TEMP "node-installer.msi"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $NodeUrl -OutFile $TempNode
        Write-Host "Running silent Node.js installation..." -ForegroundColor Green
        Start-Process msiexec.exe -ArgumentList "/i `"$TempNode`" /quiet /qn" -Wait
        Remove-Item $TempNode -ErrorAction SilentlyContinue
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
}

# 3. Launch unified runner
Write-Host "Running cross-platform Python launcher..." -ForegroundColor Green
& python "$ScriptDir\run.py" $args
