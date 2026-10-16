#!/usr/bin/env bash
# ==============================================================================
# Unified Self-Bootstrapping Runner for macOS and Linux
# Automatically installs Python and Node.js prerequisites if missing,
# prepares virtual environments, dependencies, and runs both Backend & Frontend.
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "  Preparing & Launching India Travel Safety Platform (Unix)      "
echo "================================================================="

# ------------------------------------------------------------------------------
# 1. Check and Auto-Install Python 3
# ------------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "! Python 3 not found on system. Attempting automatic installation..."
  OS="$(uname -s)"
  if [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      echo "Installing Python via Homebrew..."
      brew install python@3.11
    else
      echo "Installing Homebrew and Python..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null || true)"
      brew install python@3.11
    fi
  elif [ "$OS" = "Linux" ]; then
    if command -v apt-get >/dev/null 2>&1; then
      echo "Installing Python via apt-get..."
      sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
    elif command -v dnf >/dev/null 2>&1; then
      echo "Installing Python via dnf..."
      sudo dnf install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
      echo "Installing Python via pacman..."
      sudo pacman -S --noconfirm python python-pip
    elif command -v apk >/dev/null 2>&1; then
      echo "Installing Python via apk..."
      sudo apk add --no-cache python3 py3-pip
    else
      echo "Error: Could not automatically detect a supported package manager to install Python."
      echo "Please install Python 3.10+ manually and re-run."
      exit 1
    fi
  fi
fi

# ------------------------------------------------------------------------------
# 2. Check and Auto-Install Node.js & npm
# ------------------------------------------------------------------------------
if ! command -v npm >/dev/null 2>&1 || ! command -v node >/dev/null 2>&1; then
  echo "! Node.js / npm not found on system. Attempting automatic installation..."
  OS="$(uname -s)"
  if [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      echo "Installing Node.js via Homebrew..."
      brew install node
    fi
  elif [ "$OS" = "Linux" ]; then
    if command -v apt-get >/dev/null 2>&1; then
      echo "Installing Node.js via apt-get..."
      sudo apt-get update && sudo apt-get install -y nodejs npm
    elif command -v dnf >/dev/null 2>&1; then
      echo "Installing Node.js via dnf..."
      sudo dnf install -y nodejs npm
    elif command -v pacman >/dev/null 2>&1; then
      echo "Installing Node.js via pacman..."
      sudo pacman -S --noconfirm nodejs npm
    fi
  fi
fi

# Ensure python3 has venv module
if ! python3 -c "import venv" >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing python3-venv..."
    sudo apt-get install -y python3-venv
  fi
fi

# ------------------------------------------------------------------------------
# 3. Hand over execution to the unified cross-platform runner
# ------------------------------------------------------------------------------
chmod +x "$SCRIPT_DIR/run.py" 2>/dev/null || true
exec python3 "$SCRIPT_DIR/run.py" "$@"
