#!/usr/bin/env bash
# Build seed SQLite DB, import into Postgres, then simulate evidence/overlap/G2 drafts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_in_backend() {
  if docker ps --format '{{.Names}}' | grep -qx backend; then
    docker exec -e PYTHONPATH=/app backend "$@"
  else
    MSYS_NO_PATHCONV=1 docker compose -f docker-compose.dev.yml exec -T -e PYTHONPATH=/app backend "$@"
  fi
}

echo "==> 1/4 Alembic migrations"
run_in_backend alembic upgrade head

echo "==> 2/4 Reseed SQLite database"
run_in_backend python /app/scripts/reseed_dev_db.py

echo "==> 3/4 Import seed into Postgres"
run_in_backend python /app/scripts/import_seed_to_postgres.py

echo "==> 4/4 Simulate evidence, overlap, and assessment drafts"
run_in_backend python /app/scripts/simulate_demo_environment.py

echo ""
echo "Done. Open http://localhost:3000 and log in with admin@admin.com / admin"
