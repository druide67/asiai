---
description: "Execute o asiai como daemon em segundo plano no Mac: monitoramento auto-start, dashboard web e métricas Prometheus no boot."
---

# asiai daemon

Gerencie serviços em segundo plano via LaunchAgents do macOS launchd.

## Serviços

| Serviço | Descrição | Modelo |
|---------|-----------|--------|
| `monitor` | Coleta métricas de sistema + inferência em intervalos regulares | Periódico (`StartInterval`) |
| `web` | Executa o dashboard web como serviço persistente | Longa duração (`KeepAlive`) |

## Uso

```bash
# Daemon de monitoramento (padrão)
asiai daemon start                     # Iniciar monitoramento (a cada 60s)
asiai daemon start --interval 30       # Intervalo customizado
asiai daemon start --alert-webhook URL # Habilitar alertas via webhook

# Serviço de dashboard web
asiai daemon start web                 # Iniciar web em 127.0.0.1:8899
asiai daemon start web --port 9000     # Porta customizada
asiai daemon start web --host 0.0.0.0  # Expor na rede (sem autenticação!)

# Status (mostra todos os serviços)
asiai daemon status

# Parar
asiai daemon stop                      # Parar monitor
asiai daemon stop web                  # Parar web
asiai daemon stop --all                # Parar todos os serviços

# Logs
asiai daemon logs                      # Logs do monitor
asiai daemon logs web                  # Logs do web
asiai daemon logs web -n 100           # Últimas 100 linhas
```

## Como funciona

Cada serviço instala um plist LaunchAgent separado em `~/Library/LaunchAgents/`:

- **Monitor**: executa `asiai monitor --quiet` no intervalo configurado (padrão: 60s). Dados são armazenados em SQLite. Se `--alert-webhook` for fornecido, alertas são enviados via POST em transições de estado (pressão de memória, térmico, motor down).
- **Web**: executa `asiai web --no-open` como processo persistente. Reinicia automaticamente se crashar (`KeepAlive: true`, `ThrottleInterval: 10s`).

Ambos os serviços iniciam automaticamente no login (`RunAtLoad: true`).

## Segurança

- Serviços rodam no **nível do usuário** (sem root necessário)
- O dashboard web faz bind em `127.0.0.1` por padrão (apenas localhost)
- Um aviso é exibido ao usar `--host 0.0.0.0` — nenhuma autenticação está configurada
- Logs são armazenados em `~/.local/share/asiai/`
