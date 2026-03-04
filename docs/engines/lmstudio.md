# LM Studio

[LM Studio](https://lmstudio.ai) provides an OpenAI-compatible API with a GUI for model management.

## Setup

```bash
brew install --cask lm-studio
```

Start the local server from the LM Studio app, then load a model.

## Details

| Property | Value |
|----------|-------|
| Default port | 1234 |
| API type | OpenAI-compatible |
| VRAM reporting | No (not exposed via API) |
| Model format | GGUF, MLX |
| Detection | `/lms/version` endpoint or app bundle plist |

## Notes

- LM Studio supports both GGUF and MLX model formats.
- Version detection uses the `/lms/version` API endpoint, with a fallback to the app bundle plist on disk.
- Model names typically use the HuggingFace format (e.g., `gemma-2-9b-it`).
