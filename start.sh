#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Create the virtual environment first; see README.md.'
  exit 1
fi
exec .venv/bin/python -m uvicorn app.main:app --no-access-log --host 127.0.0.1 --port "${PORT:-8765}"
