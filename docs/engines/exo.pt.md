---
description: "Inferência LLM distribuída com Exo: benchmark de vários Macs juntos, porta 52415, configuração de cluster e performance."
---

# Exo

Exo permite inferência LLM distribuída agrupando VRAM de múltiplos Macs com Apple Silicon na sua rede local, servindo na porta 52415. Ele permite rodar modelos de 70B+ parâmetros que não caberiam em uma única máquina, com descoberta automática de peers e API compatível com OpenAI.

[Exo](https://github.com/exo-explore/exo) permite inferência distribuída entre múltiplos dispositivos Apple Silicon. Rode modelos grandes (70B+) agrupando VRAM de vários Macs.

## Configuração

```bash
pip install exo-inference
exo
```

Ou instale a partir do código-fonte:

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 52415 |
| Tipo de API | Compatível com OpenAI |
| Reporte de VRAM | Sim (agregado entre nós do cluster) |
| Formato de modelo | GGUF / MLX |
| Detecção | Auto via DEFAULT_URLS |

## Benchmarking

```bash
asiai bench --engines exo -m llama3.3:70b
```

O Exo é benchmarked como qualquer outro motor. O asiai o auto-detecta na porta 52415.

## Notas

- O Exo descobre nós peers automaticamente na rede local.
- A VRAM exibida no asiai reflete a memória total agregada de todos os nós do cluster.
- Modelos grandes que não cabem em um único Mac podem rodar sem problemas no cluster.
- Inicie o `exo` em cada Mac do cluster antes de executar benchmarks.

## Veja também

Compare motores com `asiai bench --engines exo` --- [saiba como](../benchmark-llm-mac.md)
