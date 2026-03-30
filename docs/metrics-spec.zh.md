---
description: "asiai 基准测试指标详细定义：tok/s、TTFT、功耗、能效、VRAM、稳定性、温控状态。"
---

# 基准测试指标规范

> **版本**: 0.4.0
> **状态**: 已实现
> **范围**: `asiai bench` — 所有引擎

## 动机

基准测试结果必须**跨引擎可比较**。每个指标有唯一定义，所有引擎实现都必须遵守。实现方式可以不同（服务端 API vs 客户端测量），但语义必须一致。

## 指标

### M1. `tok_per_sec` — 生成速度

**定义**：每秒**仅生成时间**产生的 token 数，不含 prompt 处理（TTFT）。

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| 引擎 | `generation_s` 来源 |
|------|-------------------|
| Ollama | `eval_duration / 1e9`（服务端 API — 直接） |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)`（客户端） |

**理由**：大上下文（如 64k token）时 TTFT 可能占据总时长。将其计入 tok/s 使快速生成器看起来很慢（如 3.2 tok/s 而非 42 tok/s）。

### M2. `ttft_ms` — 首 Token 延迟

**定义**：从发送请求到收到第一个输出 token 的时间，单位 ms。

| 引擎 | 来源 |
|------|------|
| Ollama | `prompt_eval_duration / 1e6`（服务端 API） |
| OpenAI-compat | `(time.monotonic() at 1st content chunk - t0) * 1000`（客户端） |

注意：语义略有差异（服务端 vs 客户端测量），但在 localhost 上差距约 1ms——可接受。

### M3. `total_duration_ms` — 总时长

**定义**：请求的 wall-clock 总时间（prompt 处理 + 生成），单位 ms。

**不变量**：`total_duration_ms >= ttft_ms` — 始终成立。

| 引擎 | 来源 |
|------|------|
| Ollama | `total_duration / 1e6`（服务端 API） |
| OpenAI-compat | `elapsed_s * 1000`（客户端 wall-clock） |

### M4. `tokens_generated` — Token 计数

**定义**：模型产生的输出 token 数。

**来源（按优先级）**：
1. 服务器计数器：Ollama `eval_count`，OpenAI-compat `usage.completion_tokens`
2. 文本长度估算：`max(1, len(text) // 4)`（启发式：约 4 字符/token）
3. **绝不**使用 `len(text_parts)`（SSE chunk != token）

### M5. `generation_duration_ms` — 生成时长

**定义**：仅生成时间（不含 TTFT），单位 ms。使 `total = ttft + generation` 的分解显式化且可审计。

| 引擎 | 来源 |
|------|------|
| Ollama | `eval_duration / 1e6`（服务端 API — 直接） |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000`（计算得出） |

### M6. `power_watts` — GPU 功耗

**定义**：**该特定引擎**执行期间的平均 GPU 功耗，单位瓦特。

**范围**：每引擎一个 `PowerMonitor`。在第一个 prompt 前启动，在最后一次运行后停止。每个引擎有自己的测量——无全局会话平均。

来源：`sudo powermetrics`（macOS）。

### M7. `tok_per_sec_per_watt` — 能效

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

使用修正后的 tok/s（M1）和按引擎功耗（M6）。

### M8. `std_dev_tok_s` — 方差（Pooled）

**定义**：Pooled 提示词内标准差——捕获运行间噪声**不**混入提示词间方差。

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**稳定性分类**（不变）：
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

其中 CV = `(std_dev_tok_s / avg_tok_s) * 100`。

## 实现映射

| 指标 | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | field | server API | client (excl. TTFT) | passthrough | avg |
| M2 ttft_ms | field | server API | client streaming | passthrough | avg |
| M3 total_duration_ms | field | server API | client wall-clock | passthrough | avg |
| M4 tokens_generated | field | server API | server or `len//4` | passthrough | avg |
| M5 generation_duration_ms | field | server API | computed | stored in dict | — |
| M6 power_watts | — | — | — | per-engine monitor | passthrough |
| M7 tok/s/W | — | — | — | computed | passthrough |
| M8 std_dev | — | — | — | — | pooled intra-prompt |

## 基准测试协议

1. **预热**：每引擎 1 次不计时生成（`"Hello"`，max_tokens=1）预热缓存。
2. **计时运行**：默认每提示词每引擎 3 次运行（可通过 `--runs` 配置）。
3. **采样**：所有引擎 `temperature=0`（贪心）确保确定性输出。
4. **报告**：中位数 tok/s 作为主要指标（SPEC 标准），均值 +/- 标准差作为次要指标。
5. **降频**：任何运行期间 `thermal_speed_limit < 100%` 时发出警告。
6. **元数据**：engine_version、model_format、model_quantization、hw_chip、os_version 按结果存储以确保可重现性。

详见 [benchmark-best-practices.md](benchmark-best-practices.md) 的完整方法论审计。
