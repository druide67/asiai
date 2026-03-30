---
description: "Como configurar o asiai: gerencie URLs de motores, portas e configurações persistentes para seu setup de benchmark LLM no Mac."
---

# asiai config

Gerencie configuração persistente de motores. Motores descobertos pelo `asiai detect` são automaticamente salvos em `~/.config/asiai/engines.json` para detecção mais rápida nas próximas vezes.

## Uso

```bash
asiai config show              # Mostrar motores conhecidos
asiai config add <engine> <url> [--label NAME]  # Adicionar motor manualmente
asiai config remove <url>      # Remover um motor
asiai config reset             # Limpar toda a configuração
```

## Subcomandos

### show

Exibe todos os motores conhecidos com URL, versão, fonte (auto/manual) e timestamp do último contato.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

Registre manualmente um motor em uma porta não padrão. Motores manuais nunca são removidos automaticamente.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

Remova uma entrada de motor pela URL.

```bash
asiai config remove http://localhost:8800
```

### reset

Apaga todo o arquivo de configuração. O próximo `asiai detect` vai redescobrir motores do zero.

## Como funciona

O arquivo de configuração armazena motores descobertos durante a detecção:

- **Entradas auto** (`source: auto`): criadas automaticamente quando `asiai detect` encontra um novo motor. Removidas após 7 dias de inatividade.
- **Entradas manuais** (`source: manual`): criadas via `asiai config add`. Nunca removidas automaticamente.

A cascata de detecção em 3 camadas do `asiai detect` usa esta configuração como Camada 1 (mais rápida), seguida por varredura de portas (Camada 2) e detecção de processos (Camada 3). Veja [detect](detect.md) para detalhes.

## Localização do arquivo de configuração

```
~/.config/asiai/engines.json
```
