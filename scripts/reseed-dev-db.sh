#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MSYS_NO_PATHCONV=1 docker compose exec -T -e PYTHONPATH=/app backend python /app/scripts/reseed_dev_db.py
