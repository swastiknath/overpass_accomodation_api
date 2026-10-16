#!/usr/bin/env python3
"""Unified Cross-Platform Runner for India Travel Safety Platform.

Works seamlessly on macOS, Linux, and Windows.
Automatically prepares the environment, installs missing prerequisites,
and runs both backend and frontend servers with a single command.
"""

from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
VENV_DIR = ROOT_DIR / ".venv"

IS_WINDOWS = platform.system() == "Windows"
PYTHON_EXE = sys.executable


def print_banner(msg: str) -> None:
    sep = "=" * 62
    print(f"\n{sep}\n  {msg}\n{sep}")


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        print(f"Error: Python 3.10 or higher is required. Detected: {sys.version}")
        sys.exit(1)


def ensure_node_installed() -> str:
    """Ensure Node.js and npm are installed on the host system."""
    npm_cmd = shutil.which("npm")
    node_cmd = shutil.which("node")

    if npm_cmd and node_cmd:
        try:
            node_ver = subprocess.check_output([node_cmd, "--version"], text=True).strip()
            print(f"✓ Detected Node.js ({node_ver}) and npm ({npm_cmd})")
            return npm_cmd
        except Exception:
            pass

    print("! Node.js / npm not found on PATH. Attempting automatic installation...")
    system = platform.system().lower()

    if system == "darwin":
        if shutil.which("brew"):
            print("Installing Node.js via Homebrew...")
            subprocess.run(["brew", "install", "node"], check=True)
        else:
            print("Error: Homebrew is required to auto-install Node.js on macOS.")
            print("Please install Node.js from https://nodejs.org/ and re-run.")
            sys.exit(1)
    elif system == "linux":
        if shutil.which("apt-get"):
            print("Installing Node.js via apt-get...")
            subprocess.run(["sudo", "apt-get", "update"], check=False)
            subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs", "npm"], check=True)
        elif shutil.which("dnf"):
            print("Installing Node.js via dnf...")
            subprocess.run(["sudo", "dnf", "install", "-y", "nodejs", "npm"], check=True)
        elif shutil.which("pacman"):
            print("Installing Node.js via pacman...")
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"], check=True)
        else:
            print("Error: Unsupported Linux package manager. Please install Node.js 18+ manually.")
            sys.exit(1)
    elif system == "windows":
        if shutil.which("winget"):
            print("Installing Node.js via Windows Package Manager (winget)...")
            subprocess.run(
                ["winget", "install", "OpenJS.NodeJS.LTS", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
                check=True,
            )
        else:
            print("Error: winget not found. Please install Node.js from https://nodejs.org/ and re-run.")
            sys.exit(1)

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print("Error: npm still not detected after installation attempt. Please restart your terminal.")
        sys.exit(1)

    return npm_cmd


def get_venv_python() -> Path:
    """Return the Python executable path inside the active virtualenv."""
    candidates = []
    if IS_WINDOWS:
        candidates.append(ROOT_DIR / ".venv" / "Scripts" / "python.exe")
        candidates.append(ROOT_DIR / "india-travel-safety" / ".venv" / "Scripts" / "python.exe")
    else:
        candidates.append(ROOT_DIR / ".venv" / "bin" / "python3")
        candidates.append(ROOT_DIR / ".venv" / "bin" / "python")
        candidates.append(ROOT_DIR / "india-travel-safety" / ".venv" / "bin" / "python3")
        candidates.append(ROOT_DIR / "india-travel-safety" / ".venv" / "bin" / "python")

    for cand in candidates:
        if cand.exists():
            return cand

    return candidates[0]


def setup_python_venv() -> Path:
    """Prepare virtual environment and install backend dependencies."""
    venv_py = get_venv_python()

    if not venv_py.exists():
        print(f"Creating Python virtual environment in {VENV_DIR}...")
        subprocess.run([PYTHON_EXE, "-m", "venv", str(VENV_DIR)], check=True)
        venv_py = get_venv_python()

    print("Checking backend Python dependencies...")
    req_file = ROOT_DIR / "requirements.txt"

    # Verify that critical packages can be imported without errors
    test_proc = subprocess.run(
        [str(venv_py), "-c", "import rasterio, geopandas, fastapi, uvicorn, shapely, feedparser, pyyaml"],
        capture_output=True,
        text=True,
    )

    if test_proc.returncode != 0 and req_file.exists():
        print("Missing required backend libraries in venv. Installing from requirements.txt...")
        subprocess.run(
            [str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            check=False,
        )
        res = subprocess.run(
            [str(venv_py), "-m", "pip", "install", "-r", str(req_file)],
            check=False,
        )
        if res.returncode != 0:
            print("Retrying pip install...")
            subprocess.run([str(venv_py), "-m", "pip", "install", "-r", str(req_file)], check=True)

    print("✓ Backend Python environment ready.")
    return venv_py


def setup_env_files() -> None:
    """Ensure .env and frontend/.env.local exist with valid defaults."""
    root_env = ROOT_DIR / ".env"
    root_env_example = ROOT_DIR / ".env.example"
    if not root_env.exists():
        if root_env_example.exists():
            shutil.copy(root_env_example, root_env)
            print("✓ Created .env from .env.example")
        else:
            root_env.write_text(
                "CARTO_API_KEY=cb1_4mnl_1_bec5e5affba90bd94917f6fa\n"
                "PORT=8000\n"
                "HOST=0.0.0.0\n",
                encoding="utf-8",
            )
            print("✓ Generated default .env file")

    frontend_env = FRONTEND_DIR / ".env.local"
    if not frontend_env.exists():
        frontend_env.write_text(
            "NEXT_PUBLIC_API_URL=http://localhost:8000\n"
            "NEXT_PUBLIC_CARTO_API_KEY=cb1_4mnl_1_bec5e5affba90bd94917f6fa\n",
            encoding="utf-8",
        )
        print("✓ Created frontend/.env.local configuration")


def setup_frontend_dependencies(npm_cmd: str) -> None:
    """Ensure frontend dependencies are installed."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing frontend npm dependencies (this may take a minute on first run)...")
        subprocess.run([npm_cmd, "install"], cwd=str(FRONTEND_DIR), check=True, shell=IS_WINDOWS)
        print("✓ Frontend dependencies installed.")
    else:
        print("✓ Frontend dependencies already installed.")


def wait_for_backend(url: str = "http://localhost:8000/v1/health", max_retries: int = 40) -> bool:
    """Poll backend health check until it responds."""
    print("Waiting for backend API to initialize on http://localhost:8000...")
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    print("✓ Backend is up and healthy!")
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    print_banner("Travel Safety Platform — Unified Launcher")
    check_python_version()

    # Step 1: Pre-requisite checks & installation
    npm_cmd = ensure_node_installed()
    setup_env_files()
    venv_py = setup_python_venv()
    setup_frontend_dependencies(npm_cmd)

    # Step 2: Launch Backend
    print_banner("Starting Backend & Frontend Servers")
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(BACKEND_DIR) + (
        os.pathsep + backend_env.get("PYTHONPATH", "") if backend_env.get("PYTHONPATH") else ""
    )

    backend_cmd = [
        str(venv_py),
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]
    print(f"Launching Backend API on http://localhost:8000...")
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
        env=backend_env,
        shell=False,
    )

    # Step 3: Wait for Backend Health
    backend_ready = wait_for_backend()
    if not backend_ready:
        print("Warning: Backend health check timed out. Proceeding to launch frontend anyway...")

    # Step 4: Launch Frontend
    print("Launching Frontend Portal on http://localhost:3000...")
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        shell=IS_WINDOWS,
    )

    # Step 5: Automatically open web browser
    time.sleep(2)
    try:
        webbrowser.open("http://localhost:3000")
    except Exception:
        pass

    print_banner("Application Running Successfully!\n  • Web Portal: http://localhost:3000\n  • Backend API: http://localhost:8000\n  • API Docs:    http://localhost:8000/docs\n\n  Press Ctrl+C to shut down both servers.")

    # Step 6: Handle graceful shutdown
    def shutdown(signum=None, frame=None):
        print("\nStopping all servers cleanly...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
            frontend_proc.wait(timeout=5)
            backend_proc.wait(timeout=5)
        except Exception:
            try:
                frontend_proc.kill()
                backend_proc.kill()
            except Exception:
                pass
        print("Servers stopped. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep main process alive
    try:
        while True:
            if backend_proc.poll() is not None:
                print("Backend process terminated unexpectedly.")
                shutdown()
            if frontend_proc.poll() is not None:
                print("Frontend process terminated unexpectedly.")
                shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
