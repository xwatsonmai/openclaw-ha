#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ok() { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
crit() { echo "[CRIT] $*"; }
info() { echo "[INFO] $*"; }

FRESH_SECONDS="${HEALTHCHECK_FRESH_SECONDS:-60}"
STALE_SECONDS="${HEALTHCHECK_STALE_SECONDS:-300}"
OVERALL="OK"

mark_warn() {
  [ "$OVERALL" = "OK" ] && OVERALL="WARN"
}

mark_crit() {
  OVERALL="CRIT"
}

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

cache_status_line() {
  local age="$1"
  local label="$2"
  if [ "$age" -le "$FRESH_SECONDS" ]; then
    ok "$label freshness=green age_seconds=$age"
  elif [ "$age" -le "$STALE_SECONDS" ]; then
    warn "$label freshness=yellow age_seconds=$age"
    mark_warn
  else
    crit "$label freshness=red age_seconds=$age"
    mark_crit
  fi
}

[ -f config/ha.json ] && ok "config/ha.json exists" || { warn "config/ha.json missing"; mark_warn; }
[ -f data/answer_brief.json ] && ok "answer_brief.json exists" || { warn "answer_brief.json missing"; mark_warn; }
[ -f data/summary.json ] && ok "summary.json exists" || { warn "summary.json missing"; mark_warn; }
[ -f data/answer_card.md ] && ok "answer_card.md exists" || { warn "answer_card.md missing"; mark_warn; }

show_file_age data/answer_brief.json "answer_brief.json"
show_file_age data/summary.json "summary.json"
show_file_age data/answer_card.md "answer_card.md"
show_file_age logs/ws_listener.log "ws_listener.log"
show_file_age data/recent_events.jsonl "recent_events.jsonl"

if [ -f data/summary.json ]; then
  python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone
p = Path('data/summary.json')
try:
    data = json.loads(p.read_text(encoding='utf-8'))
    generated_at = data.get('generated_at')
    print(f"[INFO] summary generated_at: {generated_at}")
    c = data.get('counts', {})
    print(f"[INFO] tracked lights_on={c.get('lights_on')} climates_active={c.get('climates_active')} unavailable={c.get('unavailable')} focus_alerts={c.get('focus_alerts')}")
    print(f"[INFO] refresh_mode={data.get('refresh_mode')} changed_entity_ids={len(data.get('changed_entity_ids', []))}")
    if generated_at:
        age = int((datetime.now(timezone.utc) - datetime.fromisoformat(generated_at.replace('Z', '+00:00'))).total_seconds())
        print(f"[CACHE_AGE] {age}")
except Exception as e:
    print(f"[WARN] failed to parse summary.json: {e}")
PY
fi

SUMMARY_AGE=$(python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone
p = Path('data/summary.json')
if not p.exists():
    print('')
else:
    data = json.loads(p.read_text(encoding='utf-8'))
    ts = data.get('generated_at')
    if not ts:
        print('')
    else:
        age = int((datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace('Z', '+00:00'))).total_seconds())
        print(age)
PY
)

if [ -n "$SUMMARY_AGE" ]; then
  cache_status_line "$SUMMARY_AGE" "summary_cache"
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
  crit "openclaw-ha-ws.service is not active"
  mark_crit
fi

if systemctl --user is-enabled --quiet openclaw-ha-ws.service; then
  ok "openclaw-ha-ws.service is enabled"
else
  warn "openclaw-ha-ws.service is not enabled"
  mark_warn
fi

if [ -f logs/ws_listener.log ]; then
  info "recent ws listener log:"
  tail -n 8 logs/ws_listener.log || true

  sync_count=$(grep -c 'sync triggered:' logs/ws_listener.log 2>/dev/null || true)
  ignored_count=$(grep -c 'event ignored by noise rules:' logs/ws_listener.log 2>/dev/null || true)
  accepted_count=$(grep -c 'event accepted:' logs/ws_listener.log 2>/dev/null || true)
  partial_count=$(grep -c 'refresh_mode": "partial"' logs/ws_listener.log 2>/dev/null || true)
  info "ws stats sync_triggered=$sync_count accepted_events=$accepted_count ignored_events=$ignored_count partial_syncs=$partial_count"
else
  warn "logs/ws_listener.log missing"
  mark_warn
fi

if [ -f data/recent_events.jsonl ]; then
  event_lines=$(wc -l < data/recent_events.jsonl)
  info "recent_events lines: $event_lines"
else
  warn "data/recent_events.jsonl missing"
  mark_warn
fi

info "overall_status=$OVERALL"
