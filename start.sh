#!/usr/bin/env bash
# Set up the Ubuntu/Debian dependencies and launch the application.
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$PROJECT_DIR"

trap 'printf "\nSetup or startup failed. See the error above, then rerun ./start.sh.\n" >&2' ERR

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

as_root() {
    if (( EUID == 0 )); then
        "$@"
    else
        command -v sudo >/dev/null 2>&1 || fail "Install sudo or ask your administrator to install the required Ubuntu packages."
        sudo "$@"
    fi
}

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    fail "Open a terminal in your graphical desktop session and run ./start.sh there."
fi

packages=()
if ! command -v python3 >/dev/null 2>&1; then
    packages=(python3 python3-tk python3-venv)
else
    if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
        packages+=(python3-tk)
    fi
    if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
        packages+=(python3-venv)
    fi
fi

if (( ${#packages[@]} > 0 )); then
    command -v apt-get >/dev/null 2>&1 || fail "Automatic setup requires Ubuntu or Debian with apt-get."
    printf 'Installing missing Ubuntu packages...\n'
    printf 'Ubuntu may ask for your administrator password.\n'
    as_root apt-get update
    as_root apt-get install -y "${packages[@]}"
fi

# The former downloaded browser no longer needs a private AppArmor profile.
if [[ -f /etc/apparmor.d/fitgirl-ff-link-extractor-browser ]]; then
    printf 'Removing the obsolete app browser profile...\n'
    as_root sh "$PROJECT_DIR/packaging/postinst" configure
fi

if ! python3 -c 'import tkinter, venv, ensurepip'; then
    fail "Python still cannot load Tkinter or venv. Use the Ubuntu system python3 and rerun ./start.sh."
fi

VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
    printf 'Creating the local Python environment...\n'
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# Repair environments created without pip, including an interrupted setup.
if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
    "$VENV_PYTHON" -m ensurepip --upgrade
fi

printf 'Checking Python dependencies...\n'
"$VENV_PYTHON" -m pip install --disable-pip-version-check -r "$PROJECT_DIR/requirements.txt"

"$VENV_PYTHON" - <<'PY'
import setuptools  # Register the distutils fallback before importing the driver.
import tkinter
import requests
import bs4
import undetected_chromedriver
import selenium
import websocket
PY

printf 'Starting FitGirl FF Link Extractor...\n'
exec "$VENV_PYTHON" "$PROJECT_DIR/ff_grabber.py"
