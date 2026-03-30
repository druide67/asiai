---
description: "Navegue e consulte o leaderboard da comunidade asiai: compare resultados de benchmark entre chips Apple Silicon e motores de inferência."
---

# asiai leaderboard

Navegue pelos dados de benchmark da comunidade da rede asiai.

## Uso

```bash
asiai leaderboard [options]
```

## Opções

| Opção | Descrição |
|-------|-----------|
| `--chip CHIP` | Filtrar por chip Apple Silicon (ex: `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | Filtrar por nome do modelo |

## Exemplo

```bash
asiai leaderboard --chip "M4 Pro"
```

```
  Community Leaderboard — M4 Pro

  Model                  Engine      tok/s (median)   Runs   Contributors
  ──────────────────── ────────── ──────────────── ────── ──────────────
  qwen3.5:35b-a3b       ollama          30.4          42         12
  qwen3.5:35b-a3b       lmstudio        72.6          38         11
  llama3.3:70b           exo            18.2          15          4
  gemma2:9b              mlx-lm        105.3          27          9

  Source: api.asiai.dev — 122 results
```

## Notas

- Requer a API da comunidade em `api.asiai.dev`.
- Os resultados são anonimizados. Nenhum dado pessoal ou de identificação da máquina é compartilhado.
- Contribua com seus próprios resultados usando `asiai bench --share`.
