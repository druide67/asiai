---
description: asiai 如何测量 tok/s、TTFT 和功耗。预热、统计方法论以及结果可重现的原因。
---

# 基准测试方法论

asiai 遵循既定的基准测试标准（[MLPerf](https://mlcommons.org/benchmarks/inference-server/)、[SPEC CPU 2017](https://www.spec.org/cpu2017/)、[NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)）来产出可靠、可重现、可比较的结果。

## 协议

1. **预检门控**：如果内存压力为严重或系统严重降频（<80%）则拒绝启动
2. **预热**：每引擎 1 次不计时的生成，用于预热 JIT 编译器和缓存
3. **计时运行**：默认每提示词每引擎 3 次运行（可通过 `--runs` 配置）
4. **采样**：`temperature=0`（贪心）确保确定性输出
5. **模型卸载**：每个引擎基准测试后卸载模型释放统一内存，然后再开始下一个引擎。防止比较多引擎大模型时的内存累积和交换
6. **自适应冷却**：卸载后等待 macOS 内存压力恢复"正常"（最长 30 秒），再加最短 5 秒温控冷却
7. **健全性检查**：tok/s <= 0 的结果被丢弃。TTFT > 60s 或 tok/s > 500 触发警告（可能是交换或测量错误）
8. **报告**：中位数 tok/s 作为主要指标（SPEC 标准），均值 +/- 标准差作为次要指标
9. **降频**：任何运行期间 `thermal_speed_limit < 100%` 时发出警告。温控漂移（运行间 tok/s 单调下降，>= 5% 下降）被检测和报告
10. **元数据**：引擎版本、模型格式、量化、硬件芯片、macOS 版本按结果存储

## 指标

### tok/s — 生成速度

每秒**仅生成时间**产生的 token 数，不含 prompt 处理（TTFT）。

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s
```

大上下文（如 64k token）时 TTFT 可能占据总时长。将其从 tok/s 中排除可防止快速生成器看起来很慢。

### TTFT — 首 Token 延迟

从发送请求到收到第一个输出 token 的时间，单位毫秒。Ollama 在服务端测量，OpenAI 兼容引擎在客户端第一个 SSE 内容 chunk 处测量。

### Power — GPU 功耗

每个特定引擎执行期间的平均 GPU 功耗，通过 `sudo powermetrics` 测量。每引擎一个 `PowerMonitor`——无整个会话的平均。

### tok/s/W — 能效

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### 方差 — Pooled 标准差

Pooled 提示词内标准差捕获运行间噪声，**不**混入提示词间方差。

稳定性分类：

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

其中 CV = `(std_dev / mean) * 100`。

## 合规性

| 实践 | 状态 |
|------|------|
| 预检门控（内存压力 + 温控） | 已实现 |
| TTFT 与 tok/s 分离 | 已实现 |
| 确定性采样（temperature=0） | 已实现 |
| Token 计数来自服务器 API（非 SSE chunk） | 已实现 |
| 按引擎功耗监控（IOReport，无 sudo） | 已实现 |
| 每引擎 1 次预热生成 | 已实现 |
| 默认 3 次运行（SPEC 最低要求） | 已实现 |
| 中位数作为主要指标（SPEC 标准） | 已实现 |
| Pooled 提示词内标准差 | 已实现 |
| 引擎间模型卸载 | 已实现 |
| 自适应冷却（感知内存压力） | 已实现 |
| 健全性检查（tok/s、TTFT 边界） | 已实现 |
| 温控降频检测 + 警告 | 已实现 |
| 温控漂移检测（单调下降） | 已实现 |
| 引擎版本 + 模型元数据存储 | 已实现 |
| 通用 VRAM（ri_phys_footprint） | 已实现 |
| 历史回归检测 | 已实现 |

## Apple Silicon 注意事项

### 统一内存

Apple Silicon 在 CPU 和 GPU 间共享内存。asiai **顺序**运行引擎并在**引擎间卸载模型**以避免内存争用和交换。VRAM 由 Ollama 和 LM Studio 原生报告；其他引擎通过 `ri_phys_footprint`（macOS 物理占用指标，与活动监视器相同）估算。估算值在 UI 中标记为"(est.)"。

### 温控降频

- **MacBook Air**（无风扇）：持续负载下严重降频
- **MacBook Pro**（有风扇）：轻度降频
- **Mac Mini/Studio/Pro**：主动散热，极少降频

asiai 按结果记录 `thermal_speed_limit`，检测到降频时发出警告。

### KV Cache

大上下文（32k+）可能在预分配 KV cache 的引擎上导致不稳定。将引擎上下文长度设为实际测试大小以获得公平结果。

## 功耗测量

asiai 通过 Apple IOReport Energy Model 框架测量 GPU、CPU、ANE 和 DRAM 功耗——**无需 sudo**。功耗在每次基准测试和每次监控快照中自动测量。

IOReport 读取与 `sudo powermetrics` 相同的硬件能量计数器，但通过用户态 API（`libIOReport.dylib` via ctypes）。无需配置免密 sudo。

### 验证

我们在 M4 Pro 64GB 上 LLM 推理负载下将 IOReport 与 `sudo powermetrics` 交叉验证，每引擎 10 个配对样本，2 秒间隔：

| 引擎 | IOReport 平均 | powermetrics 平均 | 平均差异 | 最大差异 |
|------|-------------|-----------------|---------|---------|
| LM Studio (MLX) | 12.6 W | 12.6 W | 0.9% | 2.1% |
| Ollama (llama.cpp) | 15.6 W | 15.4 W | 1.3% | 4.1% |

两个引擎确认平均差异 <1.5%，10/10 配对样本。ANE 功耗在全部 20 个样本中为 0.000W，确认目前没有 LLM 引擎使用 Neural Engine。

`--power` 参数启用额外交叉验证，同时运行 IOReport 和 `sudo powermetrics`，存储两组读数用于比较。

### 能效

能效（tok/s per watt）按 `tok_per_sec / gpu_watts` 计算。该指标支持跨引擎和硬件的推理成本比较。

## 元数据

每个基准测试结果存储：engine、engine_version、model、model_format、model_quantization、hw_chip、os_version、thermal_level、thermal_speed_limit、power_watts、power_source、metrics_version。支持公平的回归比较和跨机器基准测试。
