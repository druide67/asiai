#!/bin/bash
# bench-seed-mini-v2.sh — Compléter le seed (objectif 50+)
# Ajoute des variantes context-size + ratés du v1
# Sleep 10s entre chaque pour éviter le rate limit 429

set -euo pipefail
ASIAI=~/.local/bin/asiai
LOG=~/bench-seed-v2.log

log() { echo "$(date '+%H:%M:%S') — $*" | tee -a "$LOG"; }

unload_all() {
  for m in $(curl -s http://localhost:11434/api/ps | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null); do
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null 2>&1
  done
  lms unload --all 2>/dev/null || true
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
log "=== BENCH SEED v2 Mac Mini — START ==="

# === Ratés du v1 (2 entrées) ===
log "--- Ratés v1 ---"
bench omlx "qwen3.5" "--card"
bench omlx "qwen3-coder" "--card"

# === Context-size 64K — gros modèles Ollama (5 entrées) ===
log "--- Context 64K ---"
bench ollama "qwen3.5:35b-a3b" "--context-size 64k"
bench ollama "qwen3-coder:30b" "--context-size 64k"
bench ollama "qwen2.5-coder:32b" "--context-size 64k"
bench ollama "glm-4.7-flash:latest" "--context-size 64k"
bench ollama "gpt-oss:20b" "--context-size 64k"

# === Context-size 64K — cross-engine (4 entrées) ===
log "--- Context 64K cross-engine ---"
bench lmstudio "qwen3.5" "--context-size 64k"
bench omlx "qwen3.5" "--context-size 64k"
bench lmstudio "qwen3-coder" "--context-size 64k"
bench omlx "qwen3-coder" "--context-size 64k"

# === Context-size 4K — petits modèles rapides (4 entrées) ===
log "--- Context 4K ---"
bench ollama "qwen2.5-coder:7b-instruct" "--context-size 4096"
bench ollama "qwen2.5-coder:14b" "--context-size 4096"
bench ollama "gpt-oss:20b" "--context-size 4096"
bench ollama "glm-4.7-flash:latest" "--context-size 4096"

# === Quick bench variantes (5 entrées) ===
log "--- Quick bench ---"
bench ollama "qwen3.5:35b-a3b" "--quick"
bench ollama "qwen2.5:32b-instruct" "--quick"
bench lmstudio "qwen3.5" "--quick"
bench omlx "qwen3.5" "--quick"
bench ollama "qwen3-coder:30b" "--quick"

# === llama.cpp — déjà running sur port 8085 (3 entrées) ===
log "--- llama.cpp (port 8085) ---"
bench llamacpp "qwen2.5-coder-7b" "--url http://localhost:8085"
bench llamacpp "qwen2.5-coder-7b" "--url http://localhost:8085 --quick"
bench llamacpp "qwen2.5-coder-7b" "--url http://localhost:8085 --context-size 4096"

# === vllm-mlx — démarrer, bencher, arrêter (4 entrées) ===
log "--- vllm-mlx ---"
# Démarrer vllm-mlx avec Qwen3-Coder (chemin local LM Studio)
~/.local/bin/vllm-mlx serve ~/.lmstudio/models/lmstudio-community/Qwen3-Coder-30B-A3B-Instruct-MLX-4bit --port 8090 &
VLLM_PID=$!
sleep 15  # temps de chargement modèle MLX
bench vllm_mlx "Qwen3-Coder-30B-A3B-Instruct-MLX-4bit" "--url http://localhost:8090"
bench vllm_mlx "Qwen3-Coder-30B-A3B-Instruct-MLX-4bit" "--url http://localhost:8090 --quick"
kill $VLLM_PID 2>/dev/null; wait $VLLM_PID 2>/dev/null
sleep 5

# Démarrer vllm-mlx avec Qwen3.5 (chemin local LM Studio)
~/.local/bin/vllm-mlx serve ~/.lmstudio/models/nightmedia/Qwen3.5-35B-A3B-Text-qx64-hi-mlx --port 8090 &
VLLM_PID=$!
sleep 15
bench vllm_mlx "Qwen3.5-35B-A3B-Text-qx64-hi-mlx" "--url http://localhost:8090"
bench vllm_mlx "Qwen3.5-35B-A3B-Text-qx64-hi-mlx" "--url http://localhost:8090 --quick"
kill $VLLM_PID 2>/dev/null; wait $VLLM_PID 2>/dev/null

log "=== BENCH SEED v2 Mac Mini — DONE (27 entrées) ==="
