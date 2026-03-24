#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
INTERVAL="${REFRESH_INTERVAL:-60}"
LOG_FILE="logs/refresh.log"
mkdir -p logs

echo "[$(date '+%F %T')] refresh loop started, interval=${INTERVAL}s" >> "$LOG_FILE"

while true; do
  {
    echo "[$(date '+%F %T')] refresh begin"
    python3 src/sync_snapshot.py
    echo "[$(date '+%F %T')] refresh done"
  } >> "$LOG_FILE" 2>&1 || {
    echo "[$(date '+%F %T')] refresh failed" >> "$LOG_FILE"
  }
  sleep "$INTERVAL"
done
