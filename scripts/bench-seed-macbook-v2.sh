#!/bin/bash
# bench-seed-macbook-v2.sh — Compléter le seed MacBook
# Sleep 10s entre chaque pour éviter le rate limit 429

set -euo pipefail
ASIAI=asiai
LOG=~/bench-seed-v2.log

log() { echo "$(date '+%H:%M:%S') — $*" | tee -a "$LOG"; }

unload_all() {
  for m in $(curl -s http://localhost:11434/api/ps | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null); do
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null 2>&1
  done
  sleep 3
}

bench() {
  local engine="$1" model="$2" extra="${3:-}"
  unload_all
  log "START $engine / $model $extra"
  if $ASIAI bench -e "$engine" -m "$model" --share $extra 2>&1 | tee -a "$LOG"; then
    log "OK    $engine / $model $extra"
  else
    log "FAIL  $engine / $model $extra"
  fi
  sleep 10
}

echo "" > "$LOG"
log "=== BENCH SEED v2 MacBook — START ==="

# === Context-size 64K (4 entrées) ===
log "--- Context 64K ---"
bench ollama "gemma2:9b" "--context-size 64k"
bench ollama "llama3.1:8b" "--context-size 64k"
bench ollama "qwen2.5-coder:14b" "--context-size 64k"
bench ollama "mistral:7b" "--context-size 64k"

# === Context-size 4K (4 entrées) ===
log "--- Context 4K ---"
bench ollama "gemma2:2b" "--context-size 4096"
bench ollama "gemma2:9b" "--context-size 4096"
bench ollama "llama3.1:8b" "--context-size 4096"
bench ollama "qwen2.5-coder:7b-instruct" "--context-size 4096"

# === Quick bench (5 entrées) ===
log "--- Quick bench ---"
bench ollama "gemma2:9b" "--quick"
bench ollama "qwen2.5-coder:14b" "--quick"
bench ollama "mistral:7b" "--quick"
bench lmstudio "gemma-2-9b" "--quick"
bench mlxlm "gemma-2-2b" "--quick"

# === llama.cpp — démarrer, bencher, arrêter (3 entrées) ===
log "--- llama.cpp ---"
GEMMA_GGUF="$HOME/.ollama/models/blobs/sha256-ff1d1fc78170d787ee1201778e2dd65ea211654ca5fb7d69b5a2e7b123a50373"
llama-server -m "$GEMMA_GGUF" --alias gemma2-9b --port 8085 --host 127.0.0.1 -ngl 99 &
LLAMA_PID=$!
sleep 10  # temps de chargement
bench llamacpp "gemma2-9b" "--url http://localhost:8085"
bench llamacpp "gemma2-9b" "--url http://localhost:8085 --quick"
bench llamacpp "gemma2-9b" "--url http://localhost:8085 --context-size 4096"
kill $LLAMA_PID 2>/dev/null; wait $LLAMA_PID 2>/dev/null

log "=== BENCH SEED v2 MacBook — DONE (16 entrées) ==="
