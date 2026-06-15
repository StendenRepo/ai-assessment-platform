#!/usr/bin/env bash
# Switch overlap/assessment AI to native Mac Ollama (Metal GPU — much faster than Docker CPU).
# Revert with: ./scripts/use-docker-ollama.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ Stopping Docker Ollama..."
docker stop ollama ollama-init 2>/dev/null || true

echo "→ Stopping Ollama app / old serve processes (frees port 11434)..."
osascript -e 'quit app "Ollama"' 2>/dev/null || true
pkill -x ollama 2>/dev/null || true
sleep 2

if lsof -nP -iTCP:11434 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: Port 11434 still in use. Quit Ollama from the menu bar and re-run."
  lsof -nP -iTCP:11434 -sTCP:LISTEN
  exit 1
fi

MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
echo "→ Starting native Ollama on 0.0.0.0:11434 (Metal, reachable from Docker)..."
OLLAMA_HOST=0.0.0.0:11434 nohup ollama serve >>/tmp/ollama-host.log 2>&1 &
sleep 4

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "ERROR: Native Ollama did not start. See /tmp/ollama-host.log"
  tail -20 /tmp/ollama-host.log || true
  exit 1
fi

if ! curl -sf "http://127.0.0.1:11434/api/tags" | grep -q "$MODEL"; then
  echo "→ Pulling $MODEL on host..."
  ollama pull "$MODEL"
fi

if grep -q '^OLLAMA_BASE_URL=' .env 2>/dev/null; then
  sed -i '' 's|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://host.docker.internal:11434|' .env
else
  echo 'OLLAMA_BASE_URL=http://host.docker.internal:11434' >>.env
fi

echo "→ Restarting backend..."
docker restart backend >/dev/null
sleep 3

echo ""
echo "✓ Backend → native Ollama (host.docker.internal:11434, model: $MODEL)"
docker exec backend printenv OLLAMA_BASE_URL OLLAMA_MODEL 2>/dev/null || true
curl -sf http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; print('Host models:', [m['name'] for m in json.load(sys.stdin).get('models',[])])" 2>/dev/null || true
docker exec backend python -c "
import httpx, time
from app.config import settings
t=time.time()
r=httpx.post(f\"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate\", json={'model':settings.OLLAMA_MODEL,'prompt':'OK','stream':False}, timeout=60)
print(f'Smoke test: {round(time.time()-t,1)}s —', (r.json().get('response') or '')[:50].strip())
" 2>/dev/null || echo "(smoke test skipped — check backend logs)"
