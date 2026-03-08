# Exo

[Exo](https://github.com/exo-explore/exo) enables distributed inference across multiple Apple Silicon devices. Run large models (70B+) by pooling VRAM from several Macs.

## Setup

```bash
pip install exo-inference
exo
```

Or install from source:

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## Details

| Property | Value |
|----------|-------|
| Default port | 52415 |
| API type | OpenAI-compatible |
| VRAM reporting | Yes (aggregated across cluster nodes) |
| Model format | GGUF / MLX |
| Detection | Auto via DEFAULT_URLS |

## Benchmarking

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo is benchmarked like any other engine. asiai auto-detects it on port 52415.

## Notes

- Exo discovers peer nodes automatically on the local network.
- VRAM displayed in asiai reflects the total memory aggregated across all cluster nodes.
- Large models that don't fit on a single Mac can run seamlessly across the cluster.
- Start `exo` on each Mac in the cluster before running benchmarks.
