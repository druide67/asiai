---
description: 在 Apple Silicon 上运行 LLM 并排基准测试。比较引擎，测量 tok/s、TTFT 和能效。分享结果。
---

# asiai bench

使用标准化提示词进行跨引擎基准测试。

## 用法

```bash
asiai bench [options]
```

## 选项

| 选项 | 描述 |
|------|------|
| `-m, --model MODEL` | 基准测试的模型（默认：自动检测） |
| `-e, --engines LIST` | 筛选引擎（如 `ollama,lmstudio,mlxlm`） |
| `-p, --prompts LIST` | 提示词类型：`code`、`tool_call`、`reasoning`、`long_gen` |
| `-r, --runs N` | 每提示词运行次数（默认：3，用于中位数 + 标准差） |
| `--power` | 使用 sudo powermetrics 交叉验证功耗（IOReport 始终开启） |
| `--context-size SIZE` | 上下文填充提示词：`4k`、`16k`、`32k`、`64k` |
| `--export FILE` | 导出结果到 JSON 文件 |
| `-H, --history PERIOD` | 显示历史基准测试（如 `7d`、`24h`） |
| `-Q, --quick` | 快速基准测试：1 个提示词（code），1 次运行（约 15 秒） |
| `--compare MODEL [MODEL...]` | 跨模型比较（2-8 个模型，与 `-m` 互斥） |
| `--card` | 生成可分享的基准测试卡片（本地 SVG，配合 `--share` 生成 PNG） |
| `--share` | 将结果分享到社区基准测试数据库 |

## 示例

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## 提示词

四种标准化提示词测试不同的生成模式：

| 名称 | Token 数 | 测试内容 |
|------|---------|---------|
| `code` | 512 | 结构化代码生成（Python BST） |
| `tool_call` | 256 | JSON 函数调用 / 指令跟随 |
| `reasoning` | 384 | 多步数学问题 |
| `long_gen` | 1024 | 持续吞吐量（bash 脚本） |

使用 `--context-size` 测试大上下文填充提示词。

## 跨引擎模型匹配

运行器自动跨引擎解析模型名——`gemma2:9b`（Ollama）和 `gemma-2-9b`（LM Studio）被识别为同一模型。

## JSON 导出

导出结果用于分享或分析：

```bash
asiai bench -m qwen3.5 --export bench.json
```

JSON 包含机器元数据、按引擎统计（中位数、95% 置信区间、P50/P90/P99）、原始每次运行数据和 schema 版本。

## 回归检测

每次基准测试后，asiai 将结果与过去 7 天的历史比较，对性能回归发出警告（如引擎更新或 macOS 升级后）。

## 快速基准测试

运行单提示词单次运行的快速基准测试（约 15 秒）：

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

适用于演示、GIF 和快速检查。默认使用 `code` 提示词，可用 `--prompts` 覆盖。

## 跨模型比较

使用 `--compare` 在单次会话中比较多个模型：

```bash
# 自动扩展到所有可用引擎
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# 筛选特定引擎
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# 用 @ 将模型绑定到引擎
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

`@` 在字符串的**最后一个** `@` 处分割，因此包含 `@` 的模型名能正确处理。

### 规则

- `--compare` 和 `--model` **互斥**——只能用一个。
- 接受 2 到 8 个模型槽位。
- 不带 `@` 时，每个模型扩展到所有可用引擎。

### 会话类型

会话类型根据槽位列表自动检测：

| 类型 | 条件 | 示例 |
|------|------|------|
| **engine** | 同模型，不同引擎 | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | 不同模型，同引擎 | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | 混合模型和引擎 | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### 与其他参数组合

`--compare` 可与所有输出和运行参数配合：

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## 基准测试卡片

生成可分享的基准测试卡片：

```bash
asiai bench --card                    # SVG 本地保存
asiai bench --card --share            # SVG + PNG（通过社区 API）
asiai bench --quick --card --share    # 快速测试 + 卡片 + 分享
```

卡片是 1200x630 暗色主题图片，包含模型名和硬件芯片徽章、规格横幅、tok/s 柱状图、冠军高亮、指标标签和 asiai 品牌。

SVG 保存到 `~/.local/share/asiai/cards/`。配合 `--share` 还会从 API 下载 PNG。

## 社区分享

匿名分享你的结果：

```bash
asiai bench --share
```

通过 `asiai leaderboard` 查看社区排行榜。

## 温控漂移检测

运行 3 次以上时，asiai 检测连续运行间 tok/s 的单调下降。如果 tok/s 持续下降（>5%），发出可能温控降频累积的警告。
