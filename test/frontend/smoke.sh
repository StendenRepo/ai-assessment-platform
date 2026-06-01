#!/usr/bin/env bash
# Frontend HTTP smoke — requires frontend on :3000 (docker compose).
set -euo pipefail

BASE="${FRONTEND_BASE:-http://localhost:3000}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK  $*"; }

for path in / /dashboard /projects; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$path")
  if [ "$code" != "200" ]; then
    fail "$path returned HTTP $code"
  fi
  ok "$path → $code"
done

echo ""
echo "Frontend smoke passed."
