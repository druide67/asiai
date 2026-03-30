---
description: Recomendações de modelos baseadas em hardware considerando RAM, GPU cores e margem térmica do seu Mac.
---

# asiai recommend

Obtenha recomendações de motores para seu hardware e caso de uso.

## Uso

```bash
asiai recommend [options]
```

## Opções

| Opção | Descrição |
|-------|-----------|
| `--model MODEL` | Modelo para obter recomendações |
| `--use-case USE_CASE` | Otimizar para: `throughput`, `latency` ou `efficiency` |
| `--community` | Incluir dados de benchmark da comunidade nas recomendações |
| `--db PATH` | Caminho para o banco de dados local de benchmark |

## Fontes de dados

As recomendações são construídas a partir dos melhores dados disponíveis, em ordem de prioridade:

1. **Benchmarks locais** — suas próprias execuções no seu hardware
2. **Dados da comunidade** — resultados agregados de chips similares (com `--community`)
3. **Heurísticas** — regras integradas quando não há dados de benchmark disponíveis

## Níveis de confiança

| Nível | Critério |
|-------|----------|
| Alto | 5 ou mais execuções locais de benchmark |
| Médio | 1 a 4 execuções locais, ou dados da comunidade disponíveis |
| Baixo | Baseado em heurísticas, sem dados de benchmark |

## Exemplo

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## Notas

- Execute `asiai bench` primeiro para recomendações mais precisas.
- Use `--community` para preencher lacunas quando você não fez benchmark de um motor específico localmente.
- O caso de uso `efficiency` considera o consumo de energia (requer dados `--power` de benchmarks anteriores).
