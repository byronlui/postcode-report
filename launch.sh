#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
[ -x .venv/bin/python ] || { echo 'First run: sh install.sh'; exit 1; }
# Open the browser only once the server has responded. Never log EPC credentials.
.venv/bin/python - <<'PY' &
import os,time,urllib.request,webbrowser
port=os.environ.get('PORT','8765')
url=f'http://127.0.0.1:{port}/'
for _ in range(60):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status == 200:
                webbrowser.open(url)
                break
    except Exception:
        time.sleep(1)
PY
BROWSER_WAITER=$!
trap 'kill "$BROWSER_WAITER" 2>/dev/null || true' EXIT
printf '\nKeep this window open. Stop the server with Control+C.\nWebsite: http://127.0.0.1:%s/\n' "${PORT:-8765}"
sh start.sh
