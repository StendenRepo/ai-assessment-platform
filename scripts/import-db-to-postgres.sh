#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MSYS_NO_PATHCONV=1 docker compose -f docker-compose.dev.yml exec -T -e PYTHONPATH=/app backend python /app/scripts/import_seed_to_postgres.py
