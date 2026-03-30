---
description: 自动检测 Mac 上运行的 LLM 推理引擎。3 层级联——配置、端口扫描、进程检测。
---

# asiai detect

使用 3 层级联自动检测推理引擎。

## 用法

```bash
asiai detect                      # 自动检测（3 层级联）
asiai detect --url http://host:port  # 仅扫描指定 URL
```

## 输出

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

## 工作原理：3 层检测

asiai 使用三层检测级联，从最快到最彻底：

### 第 1 层：配置（最快，~100ms）

读取 `~/.config/asiai/engines.json`——之前运行中发现的引擎。无需重新扫描即可找到非标准端口的引擎（如 oMLX 在 8800）。

### 第 2 层：端口扫描（~200ms）

扫描默认端口加扩展范围：

| 端口 | 引擎 |
|------|------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm 或 llama.cpp |
| 8000-8009 | oMLX 或 vllm-mlx |
| 52415 | Exo |

### 第 3 层：进程检测（兜底）

使用 `ps` 和 `lsof` 查找监听任意端口的引擎进程。能发现运行在完全意外端口上的引擎。

### 自动持久化

第 2 层或第 3 层发现的引擎自动保存到配置文件（第 1 层），加快下次检测。自动发现的条目在 7 天不活跃后清理。

多个引擎共享端口时（如 mlx-lm 和 llama.cpp 共用 8080），asiai 使用 API 端点探测来识别正确的引擎。

## 显式 URL

使用 `--url` 时仅扫描指定 URL。不读写配置——适用于一次性检查。

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## 另见

- [config](config.md) — 管理持久化引擎配置
