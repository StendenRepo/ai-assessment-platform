#!/usr/bin/env bash
# Start Ollama on macOS (Metal/GPU) and ensure llama3.2:1b is available.
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-llama3.2:1b}"

ollama_bin() {
  if command -v ollama >/dev/null 2>&1; then
    command ollama
    return
  fi
  if [[ -x /Applications/Ollama.app/Contents/Resources/ollama ]]; then
    /Applications/Ollama.app/Contents/Resources/ollama
    return
  fi
  return 1
}

brew_cmd() {
  if command -v brew >/dev/null 2>&1; then
    command brew
  elif [[ -x /opt/homebrew/bin/brew ]]; then
    /opt/homebrew/bin/brew
  elif [[ -x /usr/local/bin/brew ]]; then
    /usr/local/bin/brew
  else
    return 1
  fi
}

install_ollama() {
  echo "==> Installing Ollama (Apple Silicon GPU / Metal)..."
  if brew_cmd >/dev/null 2>&1; then
    brew_cmd install --cask ollama || true
    return
  fi
  echo "==> Homebrew not found — using Ollama install script..."
  curl -fsSL https://ollama.com/install.sh | sh || true
  if [[ ! -d /Applications/Ollama.app ]]; then
    echo "ERROR: Ollama install failed. Download from https://ollama.com/download"
    exit 1
  fi
  echo "==> Ollama.app installed (CLI may be at /Applications/Ollama.app/Contents/Resources/ollama)"
}

api_ready() {
  curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1
}

start_ollama() {
  echo "==> Starting Ollama on your Mac..."
  if [[ -d /Applications/Ollama.app ]]; then
    open -a Ollama || true
  fi
  if ! api_ready; then
    local bin
    bin="$(ollama_bin)" || { echo "ERROR: ollama CLI not found after install"; exit 1; }
    nohup "$bin" serve >>/tmp/ollama-serve.log 2>&1 &
    disown 2>/dev/null || true
  fi
}

wait_for_api() {
  local i=0
  while ! api_ready; do
    i=$((i + 1))
    if [[ $i -gt 60 ]]; then
      echo "ERROR: Ollama did not respond at ${OLLAMA_HOST} (see /tmp/ollama-serve.log)"
      exit 1
    fi
    sleep 2
  done
  echo "==> Ollama API ready (${OLLAMA_HOST})"
}

ensure_model() {
  local bin
  bin="$(ollama_bin)"
  if "$bin" list 2>/dev/null | grep -qE '(^|/)llama3\.2:1b'; then
    echo "==> Model ${MODEL} already present"
    return
  fi
  echo "==> Pulling ${MODEL} (first time only, ~1.3GB)..."
  "$bin" pull "${MODEL}"
}

main() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "ensure-ollama-mac.sh is for macOS only; use Docker profile bundled-ollama on Linux."
    exit 0
  fi

  if [[ ! -d /Applications/Ollama.app ]] && ! ollama_bin >/dev/null 2>&1; then
    install_ollama
    sleep 3
  fi

  if ! api_ready; then
    start_ollama
  fi

  wait_for_api
  ensure_model
}

main "$@"
