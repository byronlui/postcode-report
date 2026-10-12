#!/bin/sh
# Install into this folder; preserve existing settings and public data.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MODE=${1:-start}
case "$MODE" in start|--install-only) ;; *) echo 'Usage: sh install.sh [--install-only]'; exit 2 ;; esac
fail() { printf '\n%s\n' "$1" >&2; exit 1; }
trap 'echo "Installation stopped. Read the message above, fix the problem and run this file again." >&2' EXIT
printf '\n免費仔 free rider — automatic installation\n'
PYTHON=''
for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
        PYTHON=$candidate
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo 'Python 3.11 or newer is required. Install Python from https://www.python.org/downloads/ then double-click Install-and-Start.command again.'
    if [ "$(uname -s)" = Darwin ]; then open 'https://www.python.org/downloads/macos/' || true; fi
    fail 'Linux / WSL: install python3 and python3-venv using your system package manager.'
fi
"$PYTHON" -c 'import sys; print("Using Python", sys.version.split()[0])'
if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv || fail 'Could not create .venv. On Ubuntu install python3-venv, then retry.'
fi
[ -x .venv/bin/python ] || fail 'The existing .venv is unusable. Rename that folder and retry; do not copy virtual environments between computers.'
.venv/bin/python -c 'import sys; assert sys.version_info >= (3,11)' || fail 'The existing .venv uses an older Python. Rename it and retry.'
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
mkdir -p data
.venv/bin/python -c 'import fastapi,uvicorn,httpx,dotenv,pyproj,shapely; import app.main; print("Installation verified.")'
trap - EXIT
if [ "$MODE" = --install-only ]; then
    echo 'Ready. Run: sh launch.sh'
    exit 0
fi
exec sh launch.sh
