#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ok() { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
info() { echo "[INFO] $*"; }

show_file_age() {
  local path="$1"
  local label="$2"
  if [ -f "$path" ]; then
    local mtime now age
    mtime=$(stat -c %Y "$path" 2>/dev/null || echo 0)
    now=$(date +%s)
    age=$((now - mtime))
    info "$label age_seconds: $age"
  fi
}

[ -f config/ha.json ] && ok "config/ha.json exists" || warn "config/ha.json missing"
[ -f data/answer_brief.json ] && ok "answer_brief.json exists" || warn "answer_brief.json missing"
[ -f data/summary.json ] && ok "summary.json exists" || warn "summary.json missing"
[ -f data/answer_card.md ] && ok "answer_card.md exists" || warn "answer_card.md missing"

show_file_age data/answer_brief.json "answer_brief.json"
show_file_age data/summary.json "summary.json"
show_file_age data/answer_card.md "answer_card.md"
show_file_age logs/ws_listener.log "ws_listener.log"
show_file_age data/recent_events.jsonl "recent_events.jsonl"

if [ -f data/summary.json ]; then
  python3 - <<'PY'
import json
from pathlib import Path
p = Path('data/summary.json')
try:
    data = json.loads(p.read_text(encoding='utf-8'))
    print(f"[INFO] summary generated_at: {data.get('generated_at')}")
    c = data.get('counts', {})
    print(f"[INFO] tracked lights_on={c.get('lights_on')} climates_active={c.get('climates_active')} unavailable={c.get('unavailable')} focus_alerts={c.get('focus_alerts')}")
except Exception as e:
    print(f"[WARN] failed to parse summary.json: {e}")
PY
fi

if [ -f data/answer_brief.json ]; then
  python3 - <<'PY'
import json
from pathlib import Path
p = Path('data/answer_brief.json')
try:
    data = json.loads(p.read_text(encoding='utf-8'))
    print(f"[INFO] brief headline: {data.get('headline')}")
except Exception as e:
    print(f"[WARN] failed to parse answer_brief.json: {e}")
PY
fi

if systemctl --user is-active --quiet openclaw-ha-ws.service; then
  ok "openclaw-ha-ws.service is active"
else
  warn "openclaw-ha-ws.service is not active"
fi

if systemctl --user is-enabled --quiet openclaw-ha-ws.service; then
  ok "openclaw-ha-ws.service is enabled"
else
  warn "openclaw-ha-ws.service is not enabled"
fi

if [ -f logs/ws_listener.log ]; then
  info "recent ws listener log:"
  tail -n 8 logs/ws_listener.log || true

  sync_count=$(grep -c 'sync triggered:' logs/ws_listener.log 2>/dev/null || true)
  ignored_count=$(grep -c 'event ignored by noise rules:' logs/ws_listener.log 2>/dev/null || true)
  accepted_count=$(grep -c 'event accepted:' logs/ws_listener.log 2>/dev/null || true)
  info "ws stats sync_triggered=$sync_count accepted_events=$accepted_count ignored_events=$ignored_count"
else
  warn "logs/ws_listener.log missing"
fi

if [ -f data/recent_events.jsonl ]; then
  event_lines=$(wc -l < data/recent_events.jsonl)
  info "recent_events lines: $event_lines"
else
  warn "data/recent_events.jsonl missing"
fi
