---
description: Detección automática de motores de inferencia LLM en tu Mac. Cascada de 3 capas — configuración, escaneo de puertos, detección de procesos.
---

# asiai detect

Detección automática de motores de inferencia usando una cascada de 3 capas.

## Uso

```bash
asiai detect                      # Detección automática (cascada de 3 capas)
asiai detect --url http://host:port  # Escanear solo URL(s) específicas
```

## Salida

```
Detected engines:

  ● ollama 0.17.4
    URL: http://localhost:11434

  ● lmstudio 0.4.5
    URL: http://localhost:1234
    Running: 1 model(s)
      - qwen3.5-35b-a3b  MLX

  ● omlx 0.9.2
    URL: http://localhost:8800
```

## Cómo funciona: detección de 3 capas

asiai utiliza una cascada de tres capas de detección, de la más rápida a la más exhaustiva:

### Capa 1: Configuración (más rápida, ~100ms)

Lee `~/.config/asiai/engines.json` — motores descubiertos en ejecuciones anteriores. Esto detecta motores en puertos no estándar (ej. oMLX en 8800) sin necesidad de reescanear.

### Capa 2: Escaneo de puertos (~200ms)

Escanea puertos por defecto más un rango extendido:

| Puerto | Motor |
|------|--------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm o llama.cpp |
| 8000-8009 | oMLX o vllm-mlx |
| 52415 | Exo |

### Capa 3: Detección de procesos (respaldo)

Usa `ps` y `lsof` para encontrar procesos de motores escuchando en cualquier puerto. Detecta motores ejecutándose en puertos completamente inesperados.

### Persistencia automática

Cualquier motor descubierto en la Capa 2 o 3 se guarda automáticamente en el archivo de configuración (Capa 1) para una detección más rápida la próxima vez. Las entradas autodescubiertas se eliminan después de 7 días de inactividad.

Cuando múltiples motores comparten un puerto (ej. mlx-lm y llama.cpp en 8080), asiai usa sondeo de endpoints API para identificar el motor correcto.

## URLs explícitas

Al usar `--url`, solo se escanean las URLs especificadas. No se lee ni escribe configuración — útil para verificaciones puntuales.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## Ver también

- [config](config.md) — Gestionar configuración persistente de motores
