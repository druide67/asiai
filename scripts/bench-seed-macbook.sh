#!/bin/bash
# bench-seed-macbook.sh — Seed leaderboard depuis MacBook Pro M4 Max 64 GB
# ATTENTION : petits modèles seulement (RAM limitée, beaucoup de choses tournent)
# Durée estimée : ~45 min
# Usage : nohup bash ~/bench-seed-macbook.sh &

set -euo pipefail
ASIAI=asiai
LOG=~/bench-seed.log

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
  log "START $engine / $model"
  if $ASIAI bench -e "$engine" -m "$model" --share $extra 2>&1 | tee -a "$LOG"; then
    log "OK    $engine / $model"
  else
    log "FAIL  $engine / $model"
  fi
}

echo "" > "$LOG"
log "=== BENCH SEED MacBook M4 Max — START ==="

# === Ollama — petits modèles (≤14 GB) ===
log "--- Ollama petits modèles ---"
bench ollama "gemma2:2b"
bench ollama "gemma2:9b"
bench ollama "llama3.1:8b"
bench ollama "mistral:7b"
bench ollama "qwen2.5-coder:7b-instruct"
bench ollama "qwen2.5-coder:14b"

# === Cross-engine : gemma2 9b (Ollama vs LM Studio) ===
log "--- Cross-engine gemma2 9b ---"
bench lmstudio "gemma-2-9b" "--card"

# === Cross-engine : gemma2 2b (Ollama vs mlx-lm) ===
log "--- Cross-engine gemma2 2b ---"
bench mlxlm "gemma-2-2b" "--card"

log "=== BENCH SEED MacBook — DONE ==="
echo ""
log "Résultats : $ASIAI bench --history 24h"
