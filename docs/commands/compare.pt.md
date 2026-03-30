---
description: Matriz de benchmark cross-model e cross-engine. Compare até 8 combinações model@engine em uma única execução.
---

# asiai compare

Compare seus benchmarks locais com dados da comunidade.

## Uso

```bash
asiai compare [options]
```

## Opções

| Opção | Descrição |
|-------|-----------|
| `--chip CHIP` | Chip Apple Silicon para comparar (padrão: auto-detecção) |
| `--model MODEL` | Filtrar por nome do modelo |
| `--db PATH` | Caminho para o banco de dados local de benchmark |

## Exemplo

```bash
asiai compare --model qwen3.5
```

```
  Compare: qwen3.5 — M4 Pro

  Engine       Your tok/s   Community median   Delta
  ────────── ──────────── ────────────────── ────────
  lmstudio        72.6           70.1          +3.6%
  ollama          30.4           31.0          -1.9%

  Chip: Apple M4 Pro (auto-detected)
```

## Notas

- Se `--chip` não for especificado, o asiai auto-detecta seu chip Apple Silicon.
- O delta mostra a diferença percentual entre sua mediana local e a mediana da comunidade.
- Deltas positivos significam que sua configuração é mais rápida que a média da comunidade.
- Os resultados locais vêm do seu banco de dados de histórico de benchmark (`~/.local/share/asiai/benchmarks.db` por padrão).
