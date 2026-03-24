#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
node src/ha_ws_listener.js
