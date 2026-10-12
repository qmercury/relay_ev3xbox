#!/bin/bash
# Double-click this file in macOS Finder, or run: bash ./Start-Relay.command
cd "$(dirname "$0")" || exit 1

PY_RUN=""
for candidate in python3.12 python3.11 python3.13 python3.10 python3.9 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] <= (3,13) else 1)' >/dev/null 2>&1; then
        PY_RUN="$candidate"
        break
    fi
done

if [ -z "$PY_RUN" ]; then
    echo "[Relay] Python 3.9-3.13 was not found."
    echo "[Relay] Install Python 3.12 from https://www.python.org/downloads/macos/"
    echo "[Relay] Then run this launcher again."
    if [ -t 0 ]; then read -r -p "Press Return to close..." _; fi
    exit 1
fi

echo "[Relay] Using $PY_RUN"
"$PY_RUN" tools/start_relay.py "$@"
RESULT=$?

if [ "$RESULT" -ne 0 ] && [ -t 0 ]; then
    read -r -p "Press Return to close..." _
fi
exit "$RESULT"
