#!/usr/bin/env bash
# Phase 5 E2E for the D5 recording booth: launch the record server +
# headless Chrome with a fake microphone, run tools/e2e_booth.py, then
# tear everything down by PID (never pkill by pattern — it self-matches).
set -u
cd "$(dirname "$0")/.."

SD_CDP_PORT="${SD_CDP_PORT:-9334}"
SD_BASE="${SD_BASE:-http://127.0.0.1:8030}"
PROFILE="$(mktemp -d)"

.venv/bin/python -m samskrita_dhvani.record --port 8030 &
SD_SERVER_PID=$!
trap '[ -n "${SD_SERVER_PID:-}" ] && kill "$SD_SERVER_PID" 2>/dev/null; rm -rf "$PROFILE"' EXIT

for i in $(seq 1 50); do
  curl -sf "$SD_BASE/api/record/words" >/dev/null 2>&1 && break
  sleep 0.2
done

google-chrome --headless=new --disable-gpu --no-first-run --user-data-dir="$PROFILE" \
  --remote-debugging-port="$SD_CDP_PORT" \
  --use-fake-device-for-media-stream --use-fake-ui-for-media-stream \
  about:blank &
CHROME_PID=$!

for i in $(seq 1 50); do
  curl -sf "http://127.0.0.1:$SD_CDP_PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.2
done

SD_CDP_PORT="$SD_CDP_PORT" SD_BASE="$SD_BASE" .venv/bin/python tools/e2e_booth.py
RC=$?

kill "$CHROME_PID" 2>/dev/null
exit $RC
