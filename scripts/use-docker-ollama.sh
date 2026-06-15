#!/usr/bin/env bash
# Revert to Docker Ollama container (slower CPU inference).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ Stopping native Ollama on your Mac..."
pkill -x ollama 2>/dev/null || true
sleep 2

if grep -q '^OLLAMA_BASE_URL=' .env 2>/dev/null; then
  sed -i '' 's|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://ollama:11434|' .env
fi

echo "→ Starting Docker Ollama..."
docker start ollama 2>/dev/null || docker compose -f docker-compose.yml up -d ollama

echo "→ Restarting backend..."
docker restart backend >/dev/null

echo "✓ Backend uses Docker Ollama again (http://ollama:11434)"
