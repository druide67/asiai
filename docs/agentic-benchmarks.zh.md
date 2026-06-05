---
description: Apple Silicon 上的 agentic 模式基准测试结果 —— Qwen3.6 与 Qwopus3.6（27B 稠密模型 vs 35B-A3B MoE），在 llama.cpp 与 MLX 引擎家族上、分别启用和不启用 MTP 投机解码。涵盖 decode、TTFT、能耗、内存、有效率。持续更新的结果页。
---

# Agentic 基准测试结果

本页报告 Apple Silicon 上真实的 `asiai bench --agentic-mode` 结果。agentic
协议运行一段 8 阶段、感知 prefix-cache 的对话（`--runs 5` 用于评估方差），
它模拟了 agent 实际使用模型的方式 —— 多轮对话、长系统前缀、50K-token 长上下文
阶段 —— 而非单次的一次性生成。

**为什么要用 agentic 模式 —— 它适合谁？** agent 框架驱动模型的方式与
chatbot 不同：它们在许多轮对话之间复用一段庞大的系统前缀、发出工具调用，
并携带长上下文。单次的吞吐数字会遗漏所有这些 —— 排名甚至可能因此翻转
（一个原始 decode 很出色、但 TTFT 高达数秒或 prefix cache 失效的引擎，
对 agent 而言根本不可用）。agentic 模式按照模型被 **agent 编排器与编码助手**
实际驱动的方式来测量它 —— 例如
[Hermes Agent](https://github.com/nousresearch/hermes-agent)、
[OpenClaw](https://github.com/openclaw/openclaw)、
[opencode](https://github.com/sst/opencode)、Aider、Cline 或 Continue ——
因此结果反映的是真实的 agent 工作负载，而非基准测试的假象。

> **持续更新文档。** 随着引擎版本、模型修订和检测仪表化的改进（例如峰值内存
> 采集），这些数字会被刷新。每一行都标注了确切的引擎版本和模型文件，因此结果
> 始终可复现。

**2026-06-03 测试活动。** 模型：Qwen3.6 与 Qwopus3.6 微调版，两种架构 ——
**27B 稠密模型**与 **35B-A3B MoE**（Mixture-of-Experts，每 token 约 ~3B 激活
参数）。引擎：llama.cpp (b9430) 与 MLX 家族（mlx-lm、mlx_vlm、omlx、rapid-mlx、
vllm-mlx）。MTP = 模型内置的 Multi-Token Prediction 头，用于投机解码
（`--spec-type draft-mtp`）。硬件：**MacBook Pro M5 Max (128 GB)** 和
**Mac mini M4 Pro (64 GB)**，两者均处于 High Power Mode。

## 如何阅读表格

结论优先。各行按确定性的门控结果分组，而不只是排序：

- **★** 该区块内经验证的最佳吞吐 · **✓** 可用 · **⚠** 备选
  （通过硬门控但延迟平庸）· **✗** 淘汰（未通过某项门控）。
- 门控：`valid ≥ 80%` · `TTFT ≤ 1500 ms`（> 3000 为硬性失败）· `prefix-cache reuse > 0`。
- **dec** = 持续热态 decode（tok/s）· **50K** = 50K 上下文下的 decode ·
  **TTFT** = time-to-first-token（ms）· **t/s/W** = 每瓦 SoC 功耗的每秒 token 数
  （能效，越高越好）· **RAMpk** = 引擎峰值 RSS（GB，决定内存适配性的指标）·
  `—` = 未测量（绝不为 0）。
- ★ *仅按吞吐*排名。为实际工作挑选模型还需权衡输出质量
  （见 dev/code 评估），而吞吐无法体现这一点。

> M4 Pro 与 M5 Max 在此**不能**做绝对数值比较 —— 量化方式不同
> （Q5_K_XL vs Q4_K_S）。请在同一机器区块内比较。

## MacBook Pro M5 Max 128 GB · Q4

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ 第 1 档 —— 冠军 + 快速** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ 第 2 档 —— 可用（较慢）** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ 第 3 档 —— 备选（延迟差）** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ 第 4 档 —— 淘汰** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

淘汰原因：mlx_vlm+MTP 未通过有效率（75%）且破坏了长上下文；两次 mlx_vlm
运行与 vllm-mlx 的 TTFT 约 9.6 s（按 agent 每轮计无法使用）。

## Mac mini M4 Pro 64 GB · Q5

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ 第 1 档** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ 第 2 档** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

## 关键发现

- **35B-A3B MoE 在两台机器上的每一项吞吐指标上都胜过 27B 稠密模型** ——
  它每 token 仅激活 ~3B 参数，因此 decode 速度比稠密 27B 快约 ~4×，能效高约
  ~3.5×（1.5 vs ~0.4 tok/s/W）。但吞吐不等于质量 —— 见下方注意事项。
- **MTP 增益取决于架构 × 硬件。** 实测 decode 提升：
  MoE +38%（M5）/ +23%（M4）；稠密模型 +16%（M5）但 **−7%（M4）** —— 在较慢的
  M4 GPU 上，稠密模型的草稿开销无法被摊销。因此 MTP 是逐模型、逐机器的测量，
  而非普遍的收益。
- **MLX 服务器家族在此仅胜在吞吐**：mlx-lm 拥有最佳的 MLX decode，但有 600 ms
  的 TTFT 下限；mlx_vlm、vllm-mlx 和 omlx 因 TTFT（2–11 s）和/或损坏的
  prefix-cache 而出局。llama.cpp 在首 token 延迟上占据主导（~60–120 ms）。
- **峰值内存 vs 稳态内存。** mlx-lm 的 RSS 稳态约 ~14.5 GB，但**峰值达
  26.4 GB**（KV 惰性分配 + 紧凑的 MLX-4bit 权重）；llama.cpp 会预先分配完整的
  上下文 KV（~29 GB 持平）。在峰值时两者相当 —— 做内存适配决策时请使用
  **RAMpk**，而非稳态值。

## 方法与注意事项

- `asiai bench --agentic-mode --runs 5`，关闭 thinking
  （`chat_template_kwargs.enable_thinking=false`），服务器上下文 ≥ 65536。
- 同一时刻仅常驻一个引擎（SOLO）；在共享同一文件的 GGUF 运行之间清空页缓存。
- **量化方式因机器而异**（M5 Q4_K_S/Q4_K_XL，M4 Q5_K_XL）→ 绝对数值
  不能跨机器比较，仅能在同一区块内比较。
- M5 笔记本上**需要 High Power Mode**（否则持续 GPU 会被限速约 ~40%）；
  M4 mini 台式机对此大致中性。
- **已知的检测仪表化缺口**（正在修复中）：部分手动启动的 llama.cpp 服务器
  缺失峰值内存（`—`）；引擎版本尚未逐次运行打标（此处取自版本映射表）；
  prefix-cache `reuse` 是一个粗略的比例，待补充真正的命中率。

另见：[基准测试方法](methodology.md) · [指标规范](metrics-spec.md)
· [社区排行榜](leaderboard.md)。
