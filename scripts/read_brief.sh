#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 src/read_cache.py brief
