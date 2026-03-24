#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p config data logs

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    echo "created: $dst"
  else
    echo "exists:  $dst"
  fi
}

copy_if_missing config/cache_rules.example.json config/cache_rules.json
copy_if_missing config/focus_entities.example.json config/focus_entities.json
copy_if_missing config/entity_aliases.example.json config/entity_aliases.json
copy_if_missing config/ws_noise_rules.example.json config/ws_noise_rules.json
copy_if_missing config/ha.example.json config/ha.json

echo
python3 --version || true
node --version || true

echo
echo "Bootstrap complete."
echo "Next steps:"
echo "1. Edit config/ha.json"
echo "2. Edit config/focus_entities.json and config/entity_aliases.json"
echo "3. Run ./scripts/run_once.sh"
echo "4. Optionally run ./scripts/run_ws_listener.sh"
