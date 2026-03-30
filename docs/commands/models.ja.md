---
description: "全エンジンのロード済みLLMモデル一覧：各モデルのVRAM使用量、量子化、コンテキスト長、フォーマットを表示。"
---

# asiai models

検出されたすべてのエンジンのロード済みモデルを一覧表示します。

## 使用方法

```bash
asiai models
```

## 出力

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

各エンジンのバージョン、モデル名、VRAM使用量（利用可能な場合）、フォーマット、量子化レベルを表示します。

VRAMはOllamaとLM Studioでネイティブに報告されます。他のエンジンでは、asiai は `ri_phys_footprint`（Activity Monitorと同じmacOSの物理フットプリント）によりメモリ使用量を推定します。推定値は「(est.)」とラベル付けされます。
