---
description: "Inferencia LLM distribuida con Exo: benchmark de múltiples Macs juntos, puerto 52415, configuración de clúster y rendimiento."
---

# Exo

Exo permite la inferencia LLM distribuida agrupando la VRAM de múltiples Macs con Apple Silicon en tu red local, sirviendo en el puerto 52415. Te permite ejecutar modelos de 70B+ parámetros que no cabrían en una sola máquina, con descubrimiento automático de pares y una API compatible con OpenAI.

[Exo](https://github.com/exo-explore/exo) permite la inferencia distribuida entre múltiples dispositivos Apple Silicon. Ejecuta modelos grandes (70B+) agrupando la VRAM de varios Macs.

## Instalación

```bash
pip install exo-inference
exo
```

O instalar desde el código fuente:

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 52415 |
| Tipo de API | Compatible con OpenAI |
| Reporte de VRAM | Sí (agregado entre nodos del clúster) |
| Formato de modelo | GGUF / MLX |
| Detección | Automática vía DEFAULT_URLS |

## Benchmarking

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo se evalúa como cualquier otro motor. asiai lo detecta automáticamente en el puerto 52415.

## Notas

- Exo descubre nodos pares automáticamente en la red local.
- La VRAM mostrada en asiai refleja la memoria total agregada de todos los nodos del clúster.
- Los modelos grandes que no caben en un solo Mac pueden ejecutarse sin problemas en el clúster.
- Inicia `exo` en cada Mac del clúster antes de ejecutar benchmarks.

## Ver también

Compara motores con `asiai bench --engines exo` --- [aprende cómo](../benchmark-llm-mac.md)
