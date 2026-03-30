---
description: "诊断 Mac 上的 LLM 推理问题：asiai doctor 检查引擎健康、端口冲突、模型加载和 GPU 状态。"
---

# asiai doctor

诊断安装、引擎、系统健康和数据库。

## 用法

```bash
asiai doctor
```

## 输出

```
Doctor

  System
    ✓ Apple Silicon       Mac Mini M4 Pro — Apple M4 Pro
    ✓ RAM                 64 GB total, 42% used
    ✓ Memory pressure     normal
    ✓ Thermal             nominal (100%)

  Engine
    ✓ Ollama              v0.17.5 — 1 model(s): qwen3.5:35b-a3b
    ✓ Ollama config       host=0.0.0.0:11434, num_parallel=1 (default), ...
    ✓ LM Studio           v0.4.6 — 1 model(s): qwen3.5-35b-a3b
    ✗ mlx-lm              not installed
    ✗ llama.cpp           not installed
    ✗ vllm-mlx            not installed

  Database
    ✓ SQLite              2.4 MB, last entry: 1m ago

  Daemon
    ✓ Monitoring daemon   running PID 1234
    ✓ Web dashboard       not installed

  Alerting
    ✓ Webhook URL         https://hooks.slack.com/services/...
    ✓ Webhook reachable   HTTP 200

  9 ok, 0 warning(s), 3 failed
```

## 检查项

- **系统**：Apple Silicon 检测、RAM、内存压力、温控状态
- **引擎**：所有 7 个支持引擎的可达性和版本；Ollama 运行时参数（host、num_parallel、max_loaded_models、keep_alive、flash_attention）
- **数据库**：SQLite schema 版本、大小、最后条目时间戳
- **守护进程**：monitor 和 web 服务的 LaunchAgent 状态
- **告警**：Webhook URL 配置和连通性
