---
description: MCP 服务器提供 11 个工具，供 AI Agent 监控推理引擎、运行基准测试和获取基于硬件的推荐。
---

# asiai mcp

启动 MCP（Model Context Protocol）服务器，让 AI Agent 能够监控和测试你的推理基础设施。

## 用法

```bash
asiai mcp                          # stdio 传输（Claude Code）
asiai mcp --transport sse          # SSE 传输（网络 Agent）
asiai mcp --transport sse --port 9000
```

## 选项

| 选项 | 描述 |
|------|------|
| `--transport` | 传输协议：`stdio`（默认）、`sse`、`streamable-http` |
| `--host` | 绑定地址（默认：`127.0.0.1`） |
| `--port` | SSE/HTTP 传输端口（默认：`8900`） |
| `--register` | Opt-in 注册到 asiai Agent 网络（匿名） |

## 工具（11 个）

| 工具 | 描述 | 只读 |
|------|------|------|
| `check_inference_health` | 快速健康检查：引擎在线/离线、内存压力、温控、GPU | 是 |
| `get_inference_snapshot` | 完整系统快照（含所有指标） | 是 |
| `list_models` | 列出所有引擎上已加载的模型 | 是 |
| `detect_engines` | 重新扫描推理引擎 | 是 |
| `run_benchmark` | 运行基准测试或跨模型比较（限速 1 次/分钟） | 否 |
| `get_recommendations` | 基于硬件的引擎/模型推荐 | 是 |
| `diagnose` | 运行诊断检查（同 `asiai doctor`） | 是 |
| `get_metrics_history` | 查询历史指标（1-168 小时） | 是 |
| `get_benchmark_history` | 带筛选条件查询历史基准测试结果 | 是 |
| `compare_engines` | 对模型进行引擎性能排名比较和结论；支持从历史进行多模型比较 | 是 |
| `refresh_engines` | 无需重启服务器即可重新检测引擎 | 是 |

## 资源（3 个）

| 资源 | URI | 描述 |
|------|-----|------|
| 系统状态 | `asiai://status` | 当前系统健康（内存、温控、GPU） |
| 模型 | `asiai://models` | 所有引擎上已加载的模型 |
| 系统信息 | `asiai://system` | 硬件信息（芯片、RAM、核心数、OS、运行时间） |

## Claude Code 集成

添加到 Claude Code MCP 配置（`~/.claude/claude_desktop_config.json`）：

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

然后问 Claude：*"检查我的推理健康状况"*或*"比较 Ollama vs LM Studio 跑 qwen3.5"*。

## 基准测试卡片

`run_benchmark` 工具通过 `card` 参数支持卡片生成。`card=true` 时生成 1200x630 SVG 基准测试卡片，响应中返回 `card_path`。

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

跨模型比较（与 `model` 互斥，最多 8 个槽位）：

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

CLI 等效命令（获取 PNG + 分享）：

```bash
asiai bench --quick --card --share    # 快速测试 + 卡片 + 分享（~15秒）
```

详见[基准测试卡片](../benchmark-card.md)页面。

## Agent 注册

加入 asiai Agent 网络获取社区功能（排行榜、比较、百分位统计）：

```bash
asiai mcp --register                  # 首次运行时注册，后续发送心跳
asiai unregister                      # 删除本地凭证
```

注册是**opt-in 且匿名的**——仅发送硬件信息（芯片、RAM）和引擎名。不存储 IP、主机名或个人数据。凭证保存在 `~/.local/share/asiai/agent.json`（chmod 600）。

后续 `asiai mcp --register` 调用会发送心跳而非重新注册。API 不可达时 MCP 服务器正常启动，不注册。

通过 `asiai version` 查看注册状态。

## 网络 Agent

用于其他机器上的 Agent（如监控无头 Mac Mini）：

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

详见 [Agent 集成指南](../agent.md)。
