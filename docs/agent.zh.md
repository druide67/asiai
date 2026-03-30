---
description: 让你的 AI Agent 实时了解 LLM 推理状态。MCP 服务器提供 11 个工具用于自主引擎监控。
type: faq
faq:
  - q: "asiai 需要 root/sudo 权限吗？"
    a: "不需要。GPU 监测使用 ioreg（无需特权）。功耗指标使用 IOReport，同样无需 sudo。可选的 --power 参数用于与 sudo powermetrics 交叉验证。"
  - q: "API 响应时间是多少？"
    a: "/api/status 响应时间低于 500ms（缓存 10 秒）。/api/snapshot 需要 1-3 秒，因为它要从所有引擎收集实时数据。"
  - q: "能在 Linux 上运行 asiai 吗？"
    a: "不能。asiai 仅支持 macOS Apple Silicon。它使用 sysctl、vm_stat、ioreg、IOReport 和 launchd——全部是 macOS 专有 API。"
  - q: "如何监控多台 Mac？"
    a: "在每台 Mac 上运行 asiai daemon start web --host 0.0.0.0。用 Prometheus 抓取 /api/metrics。用 Grafana 可视化。"
  - q: "如果引擎在监控过程中崩溃怎么办？"
    a: "asiai 会自动检测引擎故障。使用 asiai doctor 进行诊断。通过 asiai alert add 设置 webhook 告警实现自动通知。"
---

# Agent 集成指南

> **如果你是 AI Agent**：如果你的框架支持 MCP，使用 [MCP](#mcp-model-context-protocol)；否则使用 [REST API](#rest-api-参考)。配置方法见[快速开始](#快速开始)。

## 概述

asiai 通过两种方式将 Mac 的 LLM 推理基础设施暴露给 AI Agent：

- **MCP 服务器** — 通过 [Model Context Protocol](https://modelcontextprotocol.io) 实现原生工具集成。最适合支持 MCP 的 AI Agent（Claude Code、Cursor、Cline 及其他 MCP 兼容客户端）。
- **REST API** — 标准 HTTP/JSON 端点。最适合 Agent 框架、Swarm 编排器和任何支持 HTTP 的系统（CrewAI、AutoGen、LangGraph、自定义 Agent）。

两者提供相同的能力：

- **监控**系统健康状态（CPU、RAM、GPU、温控、交换区）
- **检测**正在运行的推理引擎和已加载的模型
- **诊断**性能问题（GPU 监测和推理活动信号）
- **基准测试**模型并追踪性能回归
- **获取推荐**——基于硬件的最佳模型/引擎建议

本地访问无需认证。所有接口默认绑定 `127.0.0.1`。

### 该选择哪种集成方式？

| 场景 | MCP | REST API |
|------|-----|----------|
| Agent 支持 MCP | **使用 MCP** | — |
| Swarm / 多 Agent 编排 | — | **使用 REST API** |
| 轮询 / 定时监控 | — | **使用 REST API** |
| Prometheus / Grafana 集成 | — | **使用 REST API** |
| 交互式 AI 助手（Claude Code、Cursor） | **使用 MCP** | — |
| Docker 容器内的 Agent | — | **使用 REST API** |
| 自定义脚本或自动化 | — | **使用 REST API** |

## 快速开始

### 安装 asiai

```bash
# Homebrew（推荐）
brew tap druide67/tap && brew install asiai

# pip（含 MCP 支持）
pip install "asiai[mcp]"

# pip（仅 REST API）
pip install asiai
```

### 方案 A：MCP 服务器（适用于 MCP 兼容 Agent）

```bash
# 启动 MCP 服务器（stdio 传输——Claude Code、Cursor 等使用）
asiai mcp
```

无需手动启动服务器——MCP 客户端会自动启动 `asiai mcp`。详见下方 [MCP 设置](#mcp-model-context-protocol)。

### 方案 B：REST API（适用于基于 HTTP 的 Agent）

```bash
# 前台运行（开发）
asiai web --no-open

# 后台守护进程（生产）
asiai daemon start web
```

API 地址为 `http://127.0.0.1:8899`。端口可通过 `--port` 配置：

```bash
asiai daemon start web --port 8642
```

远程访问（例如其他机器上的 AI Agent 或 Docker 容器内）：

```bash
asiai daemon start web --host 0.0.0.0
```

> **注意：**如果 Agent 运行在 Docker 内，`127.0.0.1` 不可达。使用主机网络 IP（如 `192.168.0.16`）或 Docker Desktop for Mac 的 `host.docker.internal`。

### 验证

```bash
# REST API
curl http://127.0.0.1:8899/api/status

# MCP（列出可用工具）
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP（Model Context Protocol）

asiai 实现了 [MCP 服务器](https://modelcontextprotocol.io)，将推理监控功能暴露为原生工具。任何 MCP 兼容客户端都可以直接连接使用——无需 HTTP 配置，无需管理 URL。

### 设置

#### 本地（同一台机器）

添加到你的 MCP 客户端配置（如 Claude Code 的 `~/.claude/settings.json`）：

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

如果 asiai 安装在虚拟环境中：

```json
{
  "mcpServers": {
    "asiai": {
      "command": "/path/to/.venv/bin/asiai",
      "args": ["mcp"]
    }
  }
}
```

#### 远程（通过 SSH 连接其他机器）

```json
{
  "mcpServers": {
    "asiai": {
      "command": "ssh",
      "args": [
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "your-mac-host",
        "cd /path/to/asiai && .venv/bin/asiai mcp"
      ]
    }
  }
}
```

#### SSE 传输（网络）

适用于偏好 HTTP MCP 传输的环境：

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### MCP 工具参考

所有工具返回 JSON。只读工具响应时间 < 2 秒。`run_benchmark` 是唯一的主动操作。

| 工具 | 描述 | 参数 |
|------|------|------|
| `check_inference_health` | 快速健康检查——引擎在线/离线状态、内存压力、温控、GPU 利用率 | — |
| `get_inference_snapshot` | 完整系统状态快照（存储在 SQLite 中用于历史记录） | — |
| `list_models` | 列出所有引擎上已加载的模型（含 VRAM、量化、上下文长度） | — |
| `detect_engines` | 三层检测：配置、端口扫描、进程检测。自动发现非标准端口上的引擎。 | — |
| `run_benchmark` | 运行基准测试或跨模型比较。限速：每 60 秒 1 次 | `model`（可选），`runs`（1-10，默认 3），`compare`（字符串列表，可选，与 `model` 互斥，最多 8 个） |
| `get_recommendations` | 基于硬件的模型/引擎推荐 | — |
| `diagnose` | 运行诊断检查（系统、引擎、守护进程健康） | — |
| `get_metrics_history` | 查询 SQLite 历史系统指标 | `hours`（1-168，默认 24） |
| `get_benchmark_history` | 查询历史基准测试结果 | `hours`（1-720，默认 24），`model`（可选），`engine`（可选） |
| `compare_engines` | 对给定模型进行引擎排名比较和结论；支持从历史记录进行多模型比较 | `model`（必需） |
| `refresh_engines` | 无需重启 MCP 服务器即可重新检测引擎 | — |

### MCP 资源

静态数据端点，无需调用工具即可获取：

| URI | 描述 |
|-----|------|
| `asiai://status` | 当前健康状态（内存、温控、GPU） |
| `asiai://models` | 所有引擎上已加载的模型 |
| `asiai://system` | 硬件信息（芯片、RAM、核心数、OS、运行时间） |

### MCP 安全性

- **无 sudo**：MCP 模式下禁用功耗指标（强制 `power=False`）
- **限速**：基准测试限制为每 60 秒 1 次
- **输入限幅**：`hours` 限制在 1-168，`runs` 限制在 1-10
- **默认本地**：stdio 传输无网络暴露；SSE 绑定 `127.0.0.1`

### MCP 限制

- **无自动重连**：如果 SSH 连接断开（网络问题、Mac 休眠），MCP 服务器会终止，客户端需要手动重连。对于无人值守监控，REST API 轮询更可靠。
- **单客户端**：stdio 传输一次只能服务一个客户端。如需多客户端并发访问，使用 SSE 传输。

---

## REST API 参考

asiai 的 API 是**只读的**——它只监控和报告，不控制引擎。要加载/卸载模型，请使用引擎原生命令（`ollama pull`、`lms load` 等）。

所有端点返回 JSON，HTTP 200。如果引擎不可达，响应仍返回 200 并标记该引擎 `"running": false`——API 本身不会出错。

| 端点 | 典型响应时间 | 建议超时 |
|------|-------------|---------|
| `GET /api/status` | < 500ms（缓存 10 秒） | 2s |
| `GET /api/snapshot` | 1-3s（实时采集） | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

### `GET /api/status`

快速健康检查。缓存 10 秒。响应时间 < 500ms。

**响应：**

```json
{
  "hostname": "mac-mini",
  "chip": "Apple M4 Pro",
  "ram_gb": 64.0,
  "cpu_percent": 12.3,
  "memory_pressure": "normal",
  "gpu_utilization_percent": 45.2,
  "engines": {
    "ollama": {
      "running": true,
      "models_loaded": 2,
      "port": 11434
    },
    "lmstudio": {
      "running": true,
      "models_loaded": 1,
      "port": 1234
    }
  },
  "asiai_version": "1.0.1",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

完整系统状态。包含 `/api/status` 的所有内容，外加详细模型信息、GPU 指标和温控数据。

**响应：**

```json
{
  "system": {
    "hostname": "mac-mini",
    "chip": "Apple M4 Pro",
    "cores_p": 12,
    "cores_e": 4,
    "gpu_cores": 20,
    "ram_total_gb": 64.0,
    "ram_used_gb": 41.2,
    "ram_percent": 64.4,
    "swap_used_gb": 0.0,
    "memory_pressure": "normal",
    "cpu_percent": 12.3,
    "thermal_state": "nominal",
    "gpu_utilization_percent": 45.2,
    "gpu_renderer_percent": 38.1,
    "gpu_tiler_percent": 12.4,
    "gpu_memory_allocated_bytes": 8589934592
  },
  "engines": [
    {
      "name": "ollama",
      "running": true,
      "port": 11434,
      "models": [
        {
          "name": "qwen3.5:latest",
          "size_params": "35B",
          "size_vram_bytes": 21474836480,
          "quantization": "Q4_K_M",
          "context_length": 32768
        }
      ]
    }
  ],
  "timestamp": "2026-03-09T14:30:00Z"
}
```

### `GET /api/metrics`

Prometheus 兼容指标。可用 Prometheus、Datadog 或任何兼容工具抓取。

**响应（text/plain）：**

```
# HELP asiai_cpu_percent CPU usage percentage
# TYPE asiai_cpu_percent gauge
asiai_cpu_percent 12.3

# HELP asiai_ram_used_gb RAM used in GB
# TYPE asiai_ram_used_gb gauge
asiai_ram_used_gb 41.2

# HELP asiai_gpu_utilization_percent GPU utilization percentage
# TYPE asiai_gpu_utilization_percent gauge
asiai_gpu_utilization_percent 45.2

# HELP asiai_engine_up Engine availability (1=up, 0=down)
# TYPE asiai_engine_up gauge
asiai_engine_up{engine="ollama"} 1
asiai_engine_up{engine="lmstudio"} 1

# HELP asiai_models_loaded Number of models loaded per engine
# TYPE asiai_models_loaded gauge
asiai_models_loaded{engine="ollama"} 2
```

### `GET /api/history?hours=N`

SQLite 历史系统指标。默认：`hours=24`。最大：`hours=2160`（90 天）。

**响应：**

```json
{
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "cpu_percent": 15.2,
      "ram_used_gb": 40.1,
      "ram_percent": 62.7,
      "swap_used_gb": 0.0,
      "memory_pressure": "normal",
      "thermal_state": "nominal",
      "gpu_utilization_percent": 42.0,
      "gpu_renderer_percent": 35.0,
      "gpu_tiler_percent": 10.0,
      "gpu_memory_allocated_bytes": 8589934592
    }
  ],
  "count": 144,
  "hours": 24
}
```

### `GET /api/engine-history?engine=X&hours=N`

引擎级活动历史。用于检测推理模式。

**参数：**

| 参数 | 必需 | 默认值 | 描述 |
|------|------|--------|------|
| `engine` | 是 | — | 引擎名称（ollama、lmstudio 等） |
| `hours` | 否 | 24 | 时间范围 |

**响应：**

```json
{
  "engine": "ollama",
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "running": true,
      "tcp_connections": 3,
      "requests_processing": 1,
      "kv_cache_usage_percent": 45.2
    }
  ],
  "count": 144,
  "hours": 24
}
```

## 指标解读

### 系统健康阈值

| 指标 | 正常 | 警告 | 严重 |
|------|------|------|------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75-90% | > 90% |
| `swap_used_gb` | 0 | 0.1-2.0 | > 2.0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80-95% | > 95% |

### GPU 阈值

| 指标 | 空闲 | 活跃推理 | 过载 |
|------|------|---------|------|
| `gpu_utilization_percent` | 0-5% | 20-80% | > 90% 持续 |
| `gpu_renderer_percent` | 0-5% | 15-70% | > 85% 持续 |
| `gpu_memory_allocated_bytes` | < 1 GB | 2-48 GB | > 90% RAM |

> **重要：**`gpu_utilization_percent = 0` 表示 GPU 空闲，不是故障。值为 `-1.0` 表示指标不可用（如不支持的硬件或采集失败）——不要将其视为"GPU 故障"。

### 推理性能

| 指标 | 优秀 | 良好 | 劣化 |
|------|------|------|------|
| `tok/s`（7B 模型） | > 80 | 40-80 | < 40 |
| `tok/s`（35B 模型） | > 40 | 20-40 | < 20 |
| `tok/s`（70B 模型） | > 15 | 8-15 | < 8 |
| `TTFT` | < 100ms | 100-500ms | > 500ms |

## 诊断决策树

### 生成速度慢（低 tok/s）

```
tok/s 低于预期？
├── 检查 memory_pressure
│   ├── "critical" → 模型换页到磁盘。卸载模型或增加内存。
│   └── "normal" → 继续
├── 检查 thermal_state
│   ├── "serious"/"critical" → 温控降频。降温，检查散热。
│   └── "nominal" → 继续
├── 检查 gpu_utilization_percent
│   ├── < 10% → GPU 未被使用。检查引擎配置（num_gpu layers）。
│   ├── > 90% → GPU 已饱和。减少并发请求。
│   └── 20-80% → 正常。检查模型量化和上下文大小。
└── 检查 swap_used_gb
    ├── > 0 → 模型超出内存。使用更小的量化。
    └── 0 → 检查引擎版本，尝试其他引擎。
```

### 引擎无响应

```
engine.running == false？
├── 检查进程是否存在：lsof -i :<port>
│   ├── 无进程 → 引擎崩溃。重启引擎。
│   └── 进程存在但无响应 → 引擎卡住。
├── 检查 memory_pressure
│   ├── "critical" → OOM 被杀。先卸载其他模型。
│   └── "normal" → 检查引擎日志。
└── 尝试：asiai doctor（全面诊断）
```

### 高内存压力 / VRAM 溢出

```
memory_pressure == "warn" 或 "critical"？
├── 检查 swap_used_gb
│   ├── > 2 GB → VRAM 溢出。模型无法全部装入统一内存。
│   │   ├── 延迟将恶化 5-50 倍（磁盘交换）。
│   │   ├── 卸载模型：ollama rm <model>，lms unload
│   │   └── 或使用更小的量化（Q4_K_M → Q3_K_S）。
│   └── < 2 GB → 可控，但需密切监控。
├── 检查所有引擎上已加载的模型
│   ├── 多个大模型 → 卸载未使用的模型
│   │   ├── Ollama：ollama rm <model> 或等待自动卸载
│   │   └── LM Studio：通过 UI 或 lms unload 卸载
│   └── 单模型 > 80% RAM → 使用更小的量化
└── 检查 gpu_memory_allocated_bytes
    └── 与 ram_total_gb 比较。如果 > 80%，下次模型加载将触发交换。
```

## 推理活动信号

asiai 通过多种信号检测活跃推理：

### GPU 利用率

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%**：无推理运行
- **20-80%**：活跃推理（Apple Silicon 统一内存的正常范围）
- **> 90%**：重度推理或多并发请求

### TCP 连接

```
GET /api/engine-history?engine=ollama&hours=1
```

每个活跃推理请求维持一个 TCP 连接。`tcp_connections` 激增表示正在生成。

### 引擎特定指标

对于暴露 `/metrics` 的引擎（llama.cpp、vllm-mlx）：

- `requests_processing > 0`：活跃推理
- `kv_cache_usage_percent > 0`：模型有活跃上下文

### 关联模式

最可靠的推理检测结合多种信号：

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## 示例代码

### 健康检查（Python，仅标准库）

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker：使用主机 IP 或 host.docker.internal

def check_health():
    """快速健康检查。返回状态字典。"""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """解读健康状态。"""
    issues = []
    if status.get("memory_pressure") != "normal":
        issues.append(f"memory_pressure: {status['memory_pressure']}")
    gpu = status.get("gpu_utilization_percent", 0)
    if gpu > 90:
        issues.append(f"gpu_utilization: {gpu}%")
    engines = status.get("engines", {})
    for name, info in engines.items():
        if not info.get("running"):
            issues.append(f"engine_down: {name}")
    return {"healthy": len(issues) == 0, "issues": issues}

# 使用方法
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Issues detected: {health['issues']}")
```

### 完整系统状态

```python
def get_full_state():
    """获取完整系统快照。"""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """获取历史指标。"""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# 检测性能趋势
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("GPU utilization trending up significantly")
```

## 基准测试卡片（可分享图片）

通过 CLI 生成可分享的基准测试卡片：

```bash
asiai bench --card                    # SVG 本地保存（零依赖）
asiai bench --card --share            # SVG + PNG（通过社区 API）
asiai bench --quick --card --share    # 快速测试 + 卡片 + 分享（~15秒）
```

一张 **1200x630 暗色主题卡片**，包含模型、芯片、引擎对比柱状图、冠军高亮和指标标签。针对 Reddit、X、Discord 和 GitHub README 优化。

卡片保存到 `~/.local/share/asiai/cards/`（SVG 格式）。添加 `--share` 获取 PNG 下载和可分享链接——Reddit、X 和 Discord 发帖需要 PNG 格式。

### 通过 MCP

`run_benchmark` MCP 工具通过 `card` 参数支持卡片生成：

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

响应包含 `card_path`——MCP 服务器文件系统上的 SVG 文件绝对路径。

## Webhook 告警（推送通知）

无需轮询，配置 asiai 在状态变化时推送通知：

```bash
# 添加 webhook（Slack、Discord 或任意 URL）
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# 以下情况触发告警：
# - 引擎下线 / 恢复上线
# - 内存压力变化（normal → warn → critical）
# - 检测到温控降频
```

告警仅在**状态变化时**触发（不是每次检查都触发），并有 5 分钟冷却期防止洪泛。非常适合需要响应基础设施变化而无需持续轮询的 Swarm 编排器。

管理告警：`asiai alert list`、`asiai alert remove <id>`。

## 标识你的 Agent

**建议**在 REST API 请求中包含 `User-Agent` 头来标识你的 Agent：

```
User-Agent: asiai-agent/<framework>/<version>
```

示例：

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

这**不是必需的**——没有 User-Agent 头的请求也能正常工作。但它有助于：

- **调试** — 在日志中区分 Agent 请求和人工浏览器访问
- **Agent 分析** — 查看哪些 Agent 在访问 API、频率和端点
- **多 Agent 环境** — 多个 Agent 共享同一 asiai 实例时识别身份

MCP 客户端的标识是自动的（MCP 协议包含客户端元数据）。

---

## 注册你的 Agent（可选）

注册是**完全可选的**——asiai 不注册也能完全正常工作。无电话回拨，默认无遥测。

如果你选择注册，你就加入了 asiai Agent 网络：一个 API 调用，无需邮箱，无需个人数据——只需你的硬件信息。

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.1"
  }'
```

**响应：**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

将 `agent_id` 和 `agent_token` 安全存储在 `~/.local/share/asiai/agent.json`。社区 API 调用和基准测试提交需要这两个值。

### 注册解锁的功能

| 功能 | 无 agent_id | 有 agent_id |
|------|------------|-------------|
| 本地 bench/monitor/web | 是 | 是 |
| `/api/status`、`/api/snapshot` | 是 | 是 |
| `--share` 基准测试 | 否 | **是** |
| `asiai compare`（社区） | 否 | **是** |
| `asiai recommend --community` | 否 | **是** |
| 百分位统计 | 否 | **是** |
| Agent 目录（查找相同芯片的 peers） | 否 | **是** |
| 性能告警（新引擎超过你的成绩） | 否 | **即将推出** |

### 心跳

通过定期心跳保持注册状态：

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.1",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

### 隐私

- **不存储 IP 地址** — IP 仅用于限速，不会持久化到 Agent 注册表中
- **无个人数据** — 只有硬件信息（芯片、RAM）、引擎名称和框架名称
- **纯 Opt-in** — 除非你主动注册，asiai 绝不会向外发送数据
- **Token 安全** — 你的 `agent_token` 在存储前经过 SHA-256 哈希；明文仅在注册时返回一次
- **限速数据** — 限速表中的 IP 哈希（每日加盐 SHA-256）在 30 天后自动清除

## 常见问题

**问：asiai 需要 root/sudo 吗？**
答：不需要。GPU 监测使用 `ioreg`（无需特权）。功耗指标（基准测试中的 `--power` 参数）需要 `sudo powermetrics`，但这是可选的。

**问：API 响应时间是多少？**
答：`/api/status` 响应时间 < 500ms（缓存 10 秒）。`/api/snapshot` 需要 1-3 秒（从所有引擎收集实时数据）。

**问：能在 Linux 上运行 asiai 吗？**
答：不能。asiai 仅支持 macOS Apple Silicon。它使用 `sysctl`、`vm_stat`、`ioreg` 和 `launchd`——全部是 macOS 专有 API。

**问：如何监控多台 Mac？**
答：在每台 Mac 上运行 `asiai daemon start web --host 0.0.0.0`。用 Prometheus 抓取 `/api/metrics`。用 Grafana 可视化。

**问：如果引擎崩溃怎么办？**
答：asiai 会自动检测引擎故障。使用 `asiai doctor` 进行诊断。通过 `asiai alert add` 设置 webhook 告警实现自动通知。
