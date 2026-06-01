#!/usr/bin/env bash
# Live API smoke — requires: docker compose up, Ollama optional.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="${ROOT}/test/.tmp"
mkdir -p "$TMP"

BASE="${API_BASE:-http://localhost:8000}"
PROJECT_ID="${PROJECT_ID:-proj-1}"
GROUP_ID="${GROUP_ID:-group-1}"
STUDENT_ID="${STUDENT_ID:-student-1}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK  $*"; }

curl -sf "$BASE/health" | grep -q healthy || fail "health"
ok "health"

curl -sf "$BASE/api/v1/llm-status" >"$TMP/llm.json"
python3 -c "import json; d=json.load(open('$TMP/llm.json')); assert 'ready' in d"
ok "llm-status"

TOKEN=$(curl -sf -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@admin.nl","password":"admin"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
test -n "$TOKEN" || fail "login"
ok "auth login"

curl -sf "$BASE/api/v1/auth/me" -H "Authorization: Bearer $TOKEN" >"$TMP/me.json"
ok "auth me"

curl -sf -X POST "$BASE/api/v1/projects/$PROJECT_ID/groups/$GROUP_ID/ensure" >"$TMP/ensure.json"
ok "dev bridge ensure"

CODE=$(curl -s -o "$TMP/start.json" -w '%{http_code}' -X POST \
  "$BASE/api/v1/projects/$PROJECT_ID/groups/$GROUP_ID/analyze")
if [ "$CODE" != "200" ] && [ "$CODE" != "409" ]; then
  cat "$TMP/start.json" >&2
  fail "analyze HTTP $CODE"
fi
ok "analyze started"

DONE=0
for _ in $(seq 1 120); do
  STATUS=$(curl -sf "$BASE/api/v1/projects/$PROJECT_ID/groups/$GROUP_ID/analyze/status")
  STATE=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
  case "$STATE" in
    completed) DONE=1; break ;;
    failed) echo "$STATUS" >&2; fail "analysis failed" ;;
  esac
  sleep 0.5
done
test "$DONE" -eq 1 || fail "analysis timeout"
ok "analyze completed"

INSIGHTS=$(curl -sf \
  "$BASE/api/v1/projects/$PROJECT_ID/groups/$GROUP_ID/students/$STUDENT_ID/ai-insights")
echo "$INSIGHTS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['student_id'] == '$STUDENT_ID'
assert len(d['insights']) >= 1
print(len(d['insights']))
" >"$TMP/insight_count.txt"
ok "insights ($(cat "$TMP/insight_count.txt") findings)"

curl -sf "$BASE/api/v1/modules" >/dev/null
ok "modules list"

echo ""
echo "Integration smoke passed."
