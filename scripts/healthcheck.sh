#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ok() { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
info() { echo "[INFO] $*"; }

[ -f config/ha.json ] && ok "config/ha.json exists" || warn "config/ha.json missing"
[ -f data/answer_brief.json ] && ok "answer_brief.json exists" || warn "answer_brief.json missing"
[ -f data/summary.json ] && ok "summary.json exists" || warn "summary.json missing"
[ -f data/answer_card.md ] && ok "answer_card.md exists" || warn "answer_card.md missing"

if [ -f data/summary.json ]; then
  python3 - <<'PY'
import json
from pathlib import Path
p = Path('data/summary.json')
try:
    data = json.loads(p.read_text(encoding='utf-8'))
    print(f"[INFO] summary generated_at: {data.get('generated_at')}")
    c = data.get('counts', {})
    print(f"[INFO] tracked lights_on={c.get('lights_on')} climates_active={c.get('climates_active')} unavailable={c.get('unavailable')}")
except Exception as e:
    print(f"[WARN] failed to parse summary.json: {e}")
PY
fi

if systemctl --user is-active --quiet openclaw-ha-ws.service; then
  ok "openclaw-ha-ws.service is active"
else
  warn "openclaw-ha-ws.service is not active"
fi

if [ -f logs/ws_listener.log ]; then
  info "recent ws listener log:"
  tail -n 5 logs/ws_listener.log || true
else
  warn "logs/ws_listener.log missing"
fi
