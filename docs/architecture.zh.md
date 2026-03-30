---
description: asiai 如何检测引擎、通过 IOReport 采集 GPU 指标并存储时间序列数据。技术深入解析。
---

# 架构

数据如何在 asiai 中流动——从硬件传感器到终端、浏览器和 AI Agent。

## 概览

![asiai architecture overview](assets/architecture.svg)

## 关键文件

| 层 | 文件 | 职责 |
|---|------|------|
| **引擎** | `src/asiai/engines/` | ABC `InferenceEngine` + 7 个适配器（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo）。`OpenAICompatEngine` 是 OpenAI 兼容引擎的基类。 |
| **采集器** | `src/asiai/collectors/` | 系统指标：`gpu.py`（ioreg）、`system.py`（CPU、内存、温控）、`processes.py`（通过 lsof 检测推理活动）。 |
| **基准测试** | `src/asiai/benchmark/` | `runner.py`（预热 + N 次运行、中位数、标准差、CI95）、`prompts.py`（测试提示词）、`card.py`（SVG 卡片生成）。 |
| **存储** | `src/asiai/storage/` | `db.py`（SQLite WAL，所有 CRUD）、`schema.py`（表 + 迁移）。 |
| **CLI** | `src/asiai/cli.py` | Argparse 入口，全部 12 个命令。 |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + ApexCharts 仪表板。路由在 `routes/`。 |
| **MCP** | `src/asiai/mcp/` | FastMCP 服务器，11 个工具 + 3 个资源。传输方式：stdio、SSE、streamable-http。 |
| **顾问** | `src/asiai/advisor/` | 基于硬件的推荐（模型选型、引擎选择）。 |
| **显示** | `src/asiai/display/` | ANSI 格式化器（`formatters.py`）、CLI 渲染器（`cli_renderer.py`）、TUI（`tui.py`）。 |

## 数据流

### 监控（守护进程模式）

```
每 60 秒：
  采集器 → 快照字典 → store_snapshot(db) → models 表
                                          → metrics 表
  引擎    → 引擎状态 → store_engine_status(db)
```

### 基准测试

```
CLI --bench → 检测引擎 → 选择模型 → 预热 → N 次运行
           → 计算中位数/标准差/CI95 → store_benchmark(db)
           → 渲染表格（ANSI 或 JSON）
           → 可选：--share → POST 到社区 API
           → 可选：--card  → 生成 SVG 卡片
```

### Web 仪表板

```
浏览器 → FastAPI → Jinja2 模板（初始渲染）
       → htmx SSE → /api/v1/stream → 实时更新
       → ApexCharts → /api/v1/metrics?hours=N → 历史图表
```

### MCP 服务器

```
AI Agent → stdio/SSE/HTTP → FastMCP → 工具调用
        → 在线程池中运行采集器/基准测试（asyncio.to_thread）
        → 返回结构化 JSON
```

## 设计原则

1. **核心零依赖** — CLI、采集器、引擎、存储仅使用 Python 标准库。可选扩展（`[web]`、`[tui]`、`[mcp]`）按需添加依赖。
2. **共享数据层** — 同一个 SQLite 数据库服务于 CLI、Web、MCP 和 Prometheus。无独立数据存储。
3. **适配器模式** — 全部 7 个引擎实现 `InferenceEngine` ABC。添加新引擎 = 1 个文件 + 在 `detect.py` 中注册。
4. **延迟导入** — 每个 CLI 命令在本地导入其依赖，保持启动速度快。
5. **macOS 原生** — `ioreg` 用于 GPU、`launchd` 用于守护进程、`lsof` 用于推理活动。无 Linux 抽象层。
