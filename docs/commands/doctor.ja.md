---
description: "MacでのLLM推論問題を診断：asiai doctor がエンジンヘルス、ポート競合、モデルロード、GPUステータスをチェック。"
---

# asiai doctor

インストール、エンジン、システムヘルス、データベースを診断します。

## 使用方法

```bash
asiai doctor
```

## 出力

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

## チェック項目

- **System**: Apple Silicon検出、RAM、メモリプレッシャー、サーマル状態
- **Engine**: 7つの対応エンジンの到達性とバージョン；Ollamaランタイムパラメータ（host、num_parallel、max_loaded_models、keep_alive、flash_attention）
- **Database**: SQLiteスキーマバージョン、サイズ、最終エントリのタイムスタンプ
- **Daemon**: monitorおよびwebサービスのLaunchAgentステータス
- **Alerting**: Webhook URL設定と接続性
