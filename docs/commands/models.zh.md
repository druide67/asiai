---
description: "列出所有引擎上已加载的 LLM 模型：查看 VRAM 占用、量化、上下文长度和每个模型的格式。"
---

# asiai models

列出所有已检测引擎上的已加载模型。

## 用法

```bash
asiai models
```

## 输出

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

显示引擎版本、模型名、VRAM 占用（可用时）、格式和每个引擎的量化级别。

VRAM 由 Ollama 和 LM Studio 原生报告。其他引擎通过 `ri_phys_footprint`（macOS 物理占用，与活动监视器相同）估算内存。估算值标记为"(est.)"。
