#!/usr/bin/env python3
"""Unified Cross-Platform Runner for Travel Safety & Hotel Intelligence Platform.

Works seamlessly on Windows, macOS, and Linux.
Automatically prepares the environment, resolves cross-OS virtualenvs and native
node_modules binaries (e.g. when moved from macOS to Windows), installs missing
prerequisites, and launches both Backend and Frontend servers with a single command.
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

# Force UTF-8 encoding across Windows / Unix consoles to prevent charmap crashes
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

IS_WINDOWS = platform.system().lower() == "windows"
IS_MAC = platform.system().lower() == "darwin"
PYTHON_EXE = sys.executable

CORE_PYTHON_PACKAGES = [
    "fastapi>=0.110.0",
    "uvicorn>=0.28.0",
    "requests>=2.31.0",
    "httpx>=0.27.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.0",
    "feedparser>=6.0.0",
    "shapely>=2.0.0",
    "numpy>=1.26.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]

OPTIONAL_GIS_PACKAGES = [
    "h3>=3.7.6",
    "pandas>=2.2.0",
    "geopandas>=1.0.0",
    "rasterio>=1.3.0",
    "owslib>=0.31.0",
    "aiohttp>=3.9.0",
    "rapidfuzz>=3.6.0",
]


def print_banner(msg: str) -> None:
    sep = "=" * 64
    print(f"\n{sep}\n  {msg}\n{sep}", flush=True)


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        print(f"[ERROR] Python 3.10 or higher is required. Detected: {sys.version}")
        sys.exit(1)


def _augment_windows_path() -> None:
    """Add common Windows installation directories for Node.js and Python to PATH."""
    if not IS_WINDOWS:
        return

    extra_dirs: list[Path] = []
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app = os.environ.get("LOCALAPPDATA", "")
    roaming_app = os.environ.get("APPDATA", "")

    extra_dirs.append(Path(prog_files) / "nodejs")
    extra_dirs.append(Path(prog_files_x86) / "nodejs")
    if local_app:
        extra_dirs.append(Path(local_app) / "Programs" / "nodejs")
        extra_dirs.append(Path(local_app) / "Microsoft" / "WinGet" / "Links")
        py_base = Path(local_app) / "Programs" / "Python"
        if py_base.exists():
            for p in sorted(py_base.glob("Python3*"), reverse=True):
                extra_dirs.append(p)
                extra_dirs.append(p / "Scripts")
    if roaming_app:
        extra_dirs.append(Path(roaming_app) / "npm")
        nvm_dir = Path(roaming_app) / "nvm"
        if nvm_dir.exists():
            for v in sorted(nvm_dir.glob("v*"), reverse=True):
                extra_dirs.append(v)

    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep)
    added = []
    for d in extra_dirs:
        if d.exists() and str(d) not in path_parts:
            added.append(str(d))
    if added:
        os.environ["PATH"] = os.pathsep.join(added + path_parts)


def ensure_node_installed() -> tuple[str, str]:
    """Ensure Node.js and npm are installed on the host system and return (node_cmd, npm_cmd)."""
    _augment_windows_path()

    npm_cmd = shutil.which("npm.cmd") if IS_WINDOWS else shutil.which("npm")
    if not npm_cmd:
        npm_cmd = shutil.which("npm")
    node_cmd = shutil.which("node.exe") if IS_WINDOWS else shutil.which("node")
    if not node_cmd:
        node_cmd = shutil.which("node")

    if npm_cmd and node_cmd:
        try:
            node_ver = subprocess.check_output([node_cmd, "--version"], text=True).strip()
            print(f"[OK] Detected Node.js ({node_ver}) and npm ({npm_cmd})")
            return node_cmd, npm_cmd
        except Exception:
            pass

    print("[!] Node.js / npm not found on PATH. Attempting automatic installation...")
    system = platform.system().lower()

    if system == "darwin":
        if shutil.which("brew"):
            print("Installing Node.js via Homebrew...")
            subprocess.run(["brew", "install", "node"], check=True)
        else:
            print("[ERROR] Homebrew is required to auto-install Node.js on macOS.")
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
            print("[ERROR] Unsupported Linux package manager. Please install Node.js 20+ manually.")
            sys.exit(1)
    elif system == "windows":
        if shutil.which("winget"):
            print("Installing Node.js LTS via Windows Package Manager (winget)...")
            subprocess.run(
                [
                    "winget",
                    "install",
                    "OpenJS.NodeJS.LTS",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                check=False,
            )
        else:
            print("[ERROR] winget not found. Please install Node.js from https://nodejs.org/ and re-run.")
            sys.exit(1)

    _augment_windows_path()
    npm_cmd = (shutil.which("npm.cmd") if IS_WINDOWS else None) or shutil.which("npm")
    node_cmd = (shutil.which("node.exe") if IS_WINDOWS else None) or shutil.which("node")
    if not npm_cmd or not node_cmd:
        print("[ERROR] Node.js / npm still not detected after installation attempt. Please restart your terminal.")
        sys.exit(1)

    return node_cmd, npm_cmd


def get_venv_dir() -> Path:
    """Return the platform-appropriate virtual environment directory.

    If `.venv` was created on macOS/Linux (contains `bin/python` instead of `Scripts/python.exe`)
    and the project is now running on Windows, use `.venv-win` so there is zero conflict
    with POSIX symlinks or `pyvenv.cfg`.
    """
    default_venv = ROOT_DIR / ".venv"
    if IS_WINDOWS:
        if (default_venv / "Scripts" / "python.exe").exists():
            return default_venv
        if (ROOT_DIR / "india-travel-safety" / ".venv" / "Scripts" / "python.exe").exists():
            return ROOT_DIR / "india-travel-safety" / ".venv"
        if (default_venv / "bin").exists():
            return ROOT_DIR / ".venv-win"
        return default_venv
    else:
        if (default_venv / "bin" / "python3").exists() or (default_venv / "bin" / "python").exists():
            return default_venv
        if (ROOT_DIR / "india-travel-safety" / ".venv" / "bin" / "python3").exists():
            return ROOT_DIR / "india-travel-safety" / ".venv"
        if (default_venv / "Scripts").exists():
            return ROOT_DIR / ".venv-unix"
        return default_venv


def get_venv_python(venv_dir: Path) -> Path:
    """Return the Python executable path inside the active virtualenv."""
    if IS_WINDOWS:
        return venv_dir / "Scripts" / "python.exe"
    for name in ("python3", "python"):
        cand = venv_dir / "bin" / name
        if cand.exists():
            return cand
    return venv_dir / "bin" / "python3"


def setup_python_venv() -> Path:
    """Prepare virtual environment and install backend dependencies."""
    venv_dir = get_venv_dir()
    venv_py = get_venv_python(venv_dir)

    if not venv_py.exists():
        print(f"Creating Python virtual environment in {venv_dir}...")
        subprocess.run([PYTHON_EXE, "-m", "venv", "--clear", str(venv_dir)], check=True)
        venv_py = get_venv_python(venv_dir)

    print("Checking backend Python dependencies...")

    # 1. Verify core packages required to run the FastAPI server
    test_core = subprocess.run(
        [
            str(venv_py),
            "-c",
            "import fastapi, uvicorn, httpx, requests, pydantic, pydantic_settings, shapely, feedparser, yaml, numpy",
        ],
        capture_output=True,
        text=True,
    )

    if test_core.returncode != 0:
        print("Installing core backend Python dependencies...")
        subprocess.run(
            [str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade", "pip", "setuptools", "wheel"],
            check=False,
        )
        subprocess.run(
            [str(venv_py), "-m", "pip", "install", *CORE_PYTHON_PACKAGES],
            check=True,
        )

    # 2. Verify optional GIS / H3 packages (installed best-effort so missing C++ / GDAL DLLs on Windows never block startup)
    test_gis = subprocess.run(
        [str(venv_py), "-c", "import h3"],
        capture_output=True,
        text=True,
    )
    if test_gis.returncode != 0:
        print("Installing spatial & GIS indexing packages...")
        subprocess.run(
            [str(venv_py), "-m", "pip", "install", "--quiet", *OPTIONAL_GIS_PACKAGES],
            check=False,
        )

    print("[OK] Backend Python environment ready.")
    return venv_py


def setup_env_files() -> None:
    """Ensure .env and frontend/.env.local exist with valid defaults."""
    root_env = ROOT_DIR / ".env"
    root_env_example = ROOT_DIR / ".env.example"
    if not root_env.exists():
        if root_env_example.exists():
            shutil.copy(root_env_example, root_env)
            print("[OK] Created .env from .env.example")
        else:
            root_env.write_text(
                "CARTO_API_KEY=cb1_4mnl_1_bec5e5affba90bd94917f6fa\n"
                "PORT=8000\n"
                "HOST=0.0.0.0\n",
                encoding="utf-8",
            )
            print("[OK] Generated default .env file")

    frontend_env = FRONTEND_DIR / ".env.local"
    if not frontend_env.exists():
        frontend_env.write_text(
            "NEXT_PUBLIC_API_URL=http://localhost:8000\n"
            "NEXT_PUBLIC_CARTO_API_KEY=cb1_4mnl_1_bec5e5affba90bd94917f6fa\n",
            encoding="utf-8",
        )
        print("[OK] Created frontend/.env.local configuration")


def _is_frontend_node_modules_valid_for_os() -> bool:
    """Check if frontend/node_modules exists and has native binaries for the current OS."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        return False

    next_bin_js = node_modules / "next" / "dist" / "bin" / "next"
    if not next_bin_js.exists():
        return False

    next_scope = node_modules / "@next"
    tailwind_scope = node_modules / "@tailwindcss"

    if IS_WINDOWS:
        has_win_swc = next_scope.exists() and any(next_scope.glob("swc-win32-*"))
        has_win_oxide = tailwind_scope.exists() and any(tailwind_scope.glob("oxide-win32-*"))
        has_win_shim = (node_modules / ".bin" / "next.cmd").exists()
        return has_win_swc and has_win_oxide and has_win_shim
    elif IS_MAC:
        has_mac_swc = next_scope.exists() and any(next_scope.glob("swc-darwin-*"))
        return has_mac_swc
    else:
        has_linux_swc = next_scope.exists() and any(next_scope.glob("swc-linux-*"))
        return has_linux_swc


def _clean_stale_next_cache_if_needed() -> None:
    """Remove frontend/.next if it contains build cache paths from a different operating system."""
    next_cache = FRONTEND_DIR / ".next"
    if not next_cache.exists():
        return

    try:
        # Check if .next cache was created on macOS (/Users/...) while running on Windows, or vice versa
        for sample_file in list(next_cache.glob("**/*.json"))[:10]:
            content = sample_file.read_text(encoding="utf-8", errors="ignore")
            if IS_WINDOWS and "/Users/" in content:
                print("Cleaning macOS .next build cache for Windows compatibility...")
                shutil.rmtree(next_cache, ignore_errors=True)
                return
            if not IS_WINDOWS and ":\\\\" in content:
                print("Cleaning Windows .next build cache for Unix compatibility...")
                shutil.rmtree(next_cache, ignore_errors=True)
                return
    except Exception:
        pass


def setup_frontend_dependencies(npm_cmd: str) -> None:
    """Ensure frontend dependencies and OS-native SWC/Tailwind binaries are installed."""
    _clean_stale_next_cache_if_needed()

    if not _is_frontend_node_modules_valid_for_os():
        node_modules = FRONTEND_DIR / "node_modules"
        if node_modules.exists():
            print(
                f"Detected frontend/node_modules from a different OS. "
                f"Rebuilding native packages for {platform.system()} ({platform.machine()})..."
            )
            # Clean .next cache when switching OS
            shutil.rmtree(FRONTEND_DIR / ".next", ignore_errors=True)
            # Remove stale lock/modules if needed so npm installs win32 optional dependencies
            try:
                shutil.rmtree(node_modules / ".bin", ignore_errors=True)
            except Exception:
                pass
            res = subprocess.run(
                [npm_cmd, "install", "--force", "--include=optional", "--no-audit", "--no-fund"],
                cwd=str(FRONTEND_DIR),
                shell=IS_WINDOWS,
                check=False,
            )
            if res.returncode != 0:
                print("Performing clean node_modules installation...")
                shutil.rmtree(node_modules, ignore_errors=True)
                subprocess.run(
                    [npm_cmd, "install", "--no-audit", "--no-fund", "--legacy-peer-deps"],
                    cwd=str(FRONTEND_DIR),
                    shell=IS_WINDOWS,
                    check=True,
                )
        else:
            print("Installing frontend npm dependencies (this may take a minute on first run)...")
            subprocess.run(
                [npm_cmd, "install", "--no-audit", "--no-fund"],
                cwd=str(FRONTEND_DIR),
                shell=IS_WINDOWS,
                check=True,
            )
        print("[OK] Frontend dependencies installed.")
    else:
        print("[OK] Frontend dependencies already installed.")


def wait_for_backend(url: str = "http://127.0.0.1:8000/v1/health", max_retries: int = 50) -> bool:
    """Poll backend health check over IPv4 127.0.0.1 until it responds."""
    print("Waiting for backend API to initialize on http://localhost:8000...")
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    print("[OK] Backend is up and healthy!")
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _kill_process_tree(proc: subprocess.Popen | None) -> None:
    """Cleanly terminate a subprocess and all its children on both Windows and Unix."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    except Exception:
        pass


def main() -> None:
    print_banner("Travel Safety Platform - Unified Cross-Platform Launcher")
    check_python_version()

    # Step 1: Pre-requisite checks & installation
    node_cmd, npm_cmd = ensure_node_installed()
    setup_env_files()
    venv_py = setup_python_venv()
    setup_frontend_dependencies(npm_cmd)

    # Step 2: Launch Backend
    print_banner("Starting Backend & Frontend Servers")
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(BACKEND_DIR) + (
        os.pathsep + backend_env.get("PYTHONPATH", "") if backend_env.get("PYTHONPATH") else ""
    )
    backend_env["PYTHONUTF8"] = "1"

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
        "--reload-dir",
        str(BACKEND_DIR),
    ]
    print("Launching Backend API on http://localhost:8000...")
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
        env=backend_env,
        shell=False,
    )

    # Step 3: Wait for Backend Health
    backend_ready = wait_for_backend()
    if not backend_ready:
        print("[WARN] Backend health check timed out. Proceeding to launch frontend anyway...")

    # Step 4: Launch Frontend directly via Node.js (avoids Windows .cmd space-quoting issues)
    print("Launching Frontend Portal on http://localhost:3000...")
    next_cli = FRONTEND_DIR / "node_modules" / "next" / "dist" / "bin" / "next"
    if next_cli.exists():
        frontend_cmd = [node_cmd, str(next_cli), "dev"]
    else:
        frontend_cmd = [npm_cmd, "run", "dev"]

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        shell=False,
    )

    # Step 5: Automatically open web browser
    time.sleep(2)
    try:
        webbrowser.open("http://localhost:3000")
    except Exception:
        pass

    print_banner(
        "Application Running Successfully!\n"
        "  * Web Portal:  http://localhost:3000\n"
        "  * Backend API: http://localhost:8000\n"
        "  * API Docs:    http://localhost:8000/docs\n\n"
        "  Press Ctrl+C to shut down both servers."
    )

    # Step 6: Handle graceful shutdown
    def shutdown(signum=None, frame=None, exit_code: int = 0):
        print("\nStopping all servers cleanly...")
        _kill_process_tree(frontend_proc)
        _kill_process_tree(backend_proc)
        print("Servers stopped. Goodbye!")
        sys.exit(exit_code)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # Keep main process alive
    try:
        while True:
            if backend_proc.poll() is not None:
                print("Backend process terminated unexpectedly.")
                shutdown(exit_code=1)
            if frontend_proc.poll() is not None:
                print("Frontend process terminated unexpectedly.")
                shutdown(exit_code=1)
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(exit_code=0)


if __name__ == "__main__":
    main()
