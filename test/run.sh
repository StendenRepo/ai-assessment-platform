#!/usr/bin/env bash
# Run all tests from the repository root: ./test/run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_API=1
RUN_LIVE=1

for arg in "$@"; do
  case "$arg" in
    --api-only) RUN_LIVE=0 ;;
    --live-only) RUN_API=0 ;;
    --no-live) RUN_LIVE=0 ;;
    -h|--help)
      echo "Usage: ./test/run.sh [--api-only | --live-only | --no-live]"
      exit 0
      ;;
  esac
done

stack_up() {
  curl -sf "${API_BASE:-http://localhost:8000}/health" >/dev/null 2>&1
}

run_api() {
  echo "=== API tests (pytest) ==="
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx backend; then
    docker compose exec -T backend rm -rf /app/test/backend
    docker compose exec -T backend mkdir -p /app/test/backend
    docker compose cp test/backend/. backend:/app/test/backend/ >/dev/null
    docker compose exec -T backend env PYTHONPATH=/app pytest /app/test/backend -v --tb=short "$@"
  else
    PYTHONPATH="$ROOT/backend" pytest -c "$ROOT/test/pytest.ini" "$ROOT/test/backend" "$@"
  fi
}

run_live() {
  if ! stack_up; then
    echo "Skip live tests: start stack with 'docker compose up -d' first." >&2
    return 1
  fi
  echo "=== Integration smoke ==="
  "$ROOT/test/integration/smoke.sh"
  echo "=== Frontend smoke ==="
  "$ROOT/test/frontend/smoke.sh"
}

if [ "$RUN_API" -eq 1 ]; then
  run_api
fi

if [ "$RUN_LIVE" -eq 1 ]; then
  run_live
fi

echo ""
echo "All requested test suites finished."
