#!/bin/bash
# bench-seed-mini.sh — Seed leaderboard depuis Mac Mini M4 Pro 64 GB
# Durée estimée : ~2h
# Usage : nohup bash ~/bench-seed-mini.sh &

set -euo pipefail
ASIAI=~/.local/bin/asiai
LOG=~/bench-seed.log

log() { echo "$(date '+%H:%M:%S') — $*" | tee -a "$LOG"; }

unload_all() {
  # Décharger tous les modèles Ollama
  for m in $(curl -s http://localhost:11434/api/ps | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null); do
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null 2>&1
  done
  # Décharger LM Studio
  lms unload --all 2>/dev/null || true
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
log "=== BENCH SEED Mac Mini M4 Pro — START ==="

# === PHASE 1 : Ollama — tous les modèles ===
log "--- Phase 1 : Ollama (8 modèles) ---"
bench ollama "qwen3.5:35b-a3b"
bench ollama "qwen3-coder:30b"
bench ollama "qwen2.5-coder:32b"
bench ollama "qwen2.5:32b-instruct"
bench ollama "glm-4.7-flash:latest"
bench ollama "gpt-oss:20b"
bench ollama "qwen2.5-coder:14b"
bench ollama "qwen2.5-coder:7b-instruct"

# === PHASE 2 : Cross-engine qwen3.5 35b (Ollama vs LM Studio vs oMLX) ===
log "--- Phase 2 : Cross-engine qwen3.5 35b ---"
bench lmstudio "qwen3.5" "--card"
bench omlx "qwen3.5" "--card"

# === PHASE 3 : Cross-engine qwen3-coder 30b ===
log "--- Phase 3 : Cross-engine qwen3-coder 30b ---"
bench lmstudio "qwen3-coder" "--card"
bench omlx "qwen3-coder" "--card"

log "=== BENCH SEED Mac Mini — DONE ==="
echo ""
log "Résultats : $ASIAI bench --history 24h"
