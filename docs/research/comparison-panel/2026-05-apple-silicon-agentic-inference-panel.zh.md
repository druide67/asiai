# Apple Silicon 智能体推理对比面板

> 跨推理引擎的对比基准面板（llama.cpp、mlx-lm、
> LM Studio、Rapid-MLX、vLLM-MLX、oMLX、vMLX、Ollama），在 Apple Silicon
> M 系列上运行 Qwen 3.6 系列模型，使用
> `asiai bench --agentic-mode` 和 `asiai bench --burst-mode` 测量。
>
> **工作负载目标**：智能体编排器级别——每轮约 60-80 次工具调用，
> 相同的系统提示词约 7 KB，用户消息每次调用都变化。这是
> 朴素前缀缓存的最坏情况：需要真正的跨 USER 缓存复用，
> 而不仅仅是在相同提示词上的缓存命中。
>
> **如何阅读吞吐量数字**：第 1 节的解码速率使用 Qwen3
> 默认聊天模板（thinking ON），因此它们包含推理 token——
> 在 thinking 模型上的有效智能体吞吐量更低。Thinking 是
> 按任务权衡的（caveat 1），而非全局开关。
>
> 发布于 2026-06 · 欢迎通过
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues) 提交贡献与修正。

## ⚠️ 继续阅读前已知的注意事项

1. **Thinking 模式是按任务的权衡。** 使用 Qwen3 默认模板
   （thinking ON）时，Qwen 3.6 / Qwopus 会多输出约 6-7× 的 token，因此第 1 节的
   解码数字**包含推理 token**，有效智能体吞吐量更低。Thinking ON 对于书面的
   多章节交付物是**必需**的（thinking-OFF 模型会跳过交付物），但**代价**是
   原子工具调用的整洁度（asiai 测得 thinking OFF 下约 100% 整洁工具调用，而
   thinking ON + `preserve_thinking` ON 下约 77.8%，跨多次运行具确定性；
   `enable_thinking=on` + `preserve_thinking=off` 不可用——一旦推理在上下文中
   累积，就会出现确定性的 HTTP 500）。请**按任务维度**设置 thinking，
   而非作为单一全局开关。
2. **Rapid-MLX 和 vLLM-MLX 共享同一引擎。** Rapid-MLX 是
   `waybarrios/vllm-mlx` 的社区分支；它们在下方作为独立行出现，是因为它们在
   版本和功能上已经分叉，但前缀缓存快照机制是同一脉络。
3. **MTP：Qwen 3.6 有真实的头；后端很关键。** Qwen 3.6 的官方
   `config.json` 携带 `mtp_num_hidden_layers=1`（Qwen 命名——**不是** DeepSeek 的
   `num_nextn_predict_layers` 键，因此只检查 `nextn` 会错误地
   得出“无头”结论）。某些重新量化的 GGUF/MLX 工件会丢弃 MTP
   张量但保留 config 标志——请在权重索引中验证张量本身，
   而不仅仅是标志。llama.cpp 原生 MTP（`--spec-type draft-mtp`）
   **需要一个嵌入了头的 `-MTP-GGUF`**；普通 GGUF 无法 draft。
   已发布的 mlx-lm 不会将该头作为原生投机解码运行（PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) 添加了
   它）。LM Studio 通过其源自 llama.cpp 的后端路由 GGUF，通过
   `mlx-engine` 路由 MLX。
4. **单次测量，无方差报告**——第 1 / 2 节的
   数字是单次观测。方差报告（N 次运行的中位数 + 最小值 + 最大值）
   自 `--burst-runs N` 起已支持，但重新基准测试
   仍待进行。

| 章节 | 主题 | 状态 |
|---------|-------|--------|
| 1 | Single-call performance | 🟡 8 cells, thinking-mode ON (decode includes reasoning tokens) |
| 2 | Concurrent burst (30/60/80 parallel calls) | 🟡 smoke cell + 2 partial concurrent points; no normalized 30/60/80 panel |
| 3 | Caches & optimizations | ✅ 8 engines covered |
| 4 | Memory & resources | ✅ idle + under-load swap (+0) + footprint measured |
| 5 | Model quality (public leaderboards) | 🟡 vendor/self-reported figures (llm-stats) |
| — | **asiai direct measurements** | ✅ dev-quality, thinking ablation, MTP, instruction-following |
| 6 | Operational (license, endpoints, maintenance) | ✅ 8 engines covered |
| 7 | Quality benchmark weighting | 🟡 default weighting, override via `--weights` planned |
| 8 | Custom long-horizon eval (proposal) | 🟡 scoped, not yet built |

---

## Section 1 — Single-call performance

> 🟠 **2026 年 5 月快照——仅供参考，并非基准参考数字。** 此表
> 采集于 5 月（thinking-mode ON、单次），其源 fixture 尚未
> 重新验证。如需**当前、可复现的解码吞吐量**，请使用下方的 *asiai
> direct measurements* 章节（6 月，llama.cpp b9430，确定性）。此表
> 可靠之处在于**相对 TTFT / 前缀缓存**的结论
>（跨 USER 复用），而非绝对 t/s。尤其要注意第 5 行的 123.9 t/s
>（LM Studio GGUF+MTP）紧邻 6 月的 **llama.cpp Qwopus+MTP
> 123.3 t/s**——LM Studio 的 GGUF 路径是源自 llama.cpp 的后端，因此两者
> 本质上测量的是同一引擎。

> ⚠️ **请结合上方 caveat 1 阅读**：此表中的每个数字都包含
> Qwen3 默认 thinking-mode 的 token（reasoning_content）。有效
> 智能体吞吐量需要使用
> `chat_template_kwargs={"enable_thinking": false}` 重新运行。该列标注为
> “decode (t/s)”而非“effective throughput”。
>
> “lower-bound estimate”列为 `60 × (TTFT + max_tokens/decode)`，
> 假设顺序派发（Rapid-MLX 单槽位强制如此）。这
> **不是**生产 tick 预测——参见 [Section 7](#section-7) 中的
> 方法论注意事项。
>
> 📌 **测试版本（2026 年 5 月）**：Rapid-MLX 0.6.66、LM Studio 0.4.14、
> llama.cpp b9270。Apple Silicon 上的引擎版本每周变动——请将每个
> 数字视为有日期标记，而非当前。（asiai-measurements 章节使用 llama.cpp
> b9430。）

| # | Engine | Model | Format | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test median (ms) | TTFT cold (ms) | Lower-bound estimate (60 calls × single-call, optimistic) | Source fixture |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Thinking-mode 注意事项**：数字采集自默认聊天模板
（thinking ON）。在工具调用工作负载上的真实有效吞吐量
通常在 Qwopus/Qwen3.6 微调模型上为 4-12 t/s，因为推理 token
将输出膨胀了 6-7×。要复现这些解码数字，请在请求载荷中传入
`chat_template_kwargs={"enable_thinking": false}`。

² **LM Studio 后端**：第 5-6 行使用 GGUF 文件，它通过
LM Studio 源自 llama.cpp 的后端路由（**而非** MLX 运行时 `mlx-engine`）。
第 5 行的 MTP 声明反映的是该后端的实现，而非
mlx-engine 投机解码。已发布的 mlx-lm 不会将 MTP 头
作为原生投机解码运行（其 `sanitize()` 在转换过程中历来会丢弃 MTP
权重；原生支持在 PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) 中），
因此假设的 MLX 格式 MTP 模型在已发布的
mlx-engine 上同样不会受益。

### Key observations

- 在真实的智能体模式（相同系统 + 变化的用户提示词）下，
  **Rapid-MLX + Qwopus 35B-A3B-v1** 的前缀测试 TTFT 中位数为 131 ms，
  而 LM Studio GGUF 后端为 5965 ms（**快约 44×**）。该优势
  来自 vllm-mlx 前缀缓存快照机制（源代码消歧见 Section 3）。
- 在纯解码吞吐量（warm 路径）上，**带 Unsloth MTP 的 LM Studio GGUF
  后端**记录 123.9 t/s，而 Rapid-MLX 为 109.1 t/s（+13.5%）。该差异
  反映的是 LM Studio 源自 llama.cpp 的后端在携带 MTP 头的
  GGUF 上的投机解码，而非 Apple-MLX 的增益（已发布的 mlx-engine
  不运行该头——见脚注 2）。在原生 llama.cpp 路径上，MTP 在
  MoE 35B-A3B 上为净正收益——见 Section 3。
- 所有 `Qwen 3.6 family` 配置（混合 DeltaNet + 全注意力）都无法实现
  跨 USER 前缀缓存，**唯独 Rapid-MLX 例外**，它保留了 RNN 状态
  快照。在 llama.cpp / LM Studio GGUF 上 `llama_memory_can_shift=false`；在
  mlx-lm / oMLX 上，recurrent/SSM 状态无法在任意 token
  边界处切分。针对此架构的上游 llama.cpp 修复未被合并
  （[#23121](https://github.com/ggml-org/llama.cpp/pull/23121) 已关闭；
  `preserve_thinking` 无法解决它，
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)）。
- **已确认单槽位串行化**：smoke burst 测试（Section 2）
  显示 Rapid-MLX 0.6.66 以 FIFO 串行处理并发调用（burst=5 时 p50 ≈ p95 ≈ max）。
  对于每轮 60-80 次调用，在此引擎上总墙钟时间随 burst
  规模线性增长。多槽位引擎（例如 llama.cpp
  `--parallel N`）会有不同表现，但在 Qwen3.6
  混合架构上 `--parallel N` 会禁用每槽位的前缀缓存（架构限制）。

---

## Section 2 — Concurrent burst (30/60/80 parallel calls)

> 模式：在约 200 ms 窗口内发起 30 到 80 次并发 `POST /v1/chat/completions` 调用。
> 模拟智能体循环并行派发多个 MCP/工具调用。通过
> `asiai bench --burst-mode` 原生测量。
>
> 🟡 **状态**：已测量 1 个 smoke cell（Rapid-MLX burst-5）。完整面板待进行。

### Smoke cell (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latency (ms) | p95 latency (ms) | max latency (ms) | agg throughput (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Smoke 发现**：`p50 ≈ p95 ≈ max` 表明这 5 次调用在**服务端被串行化**
（单槽位引擎）。Rapid-MLX 0.6.66 似乎**不**支持
并发请求调度——调用在内部以 FIFO 排队。需在 60/80
调用规模下验证。

### Full concurrent panel — not yet measured

尚未运行规范化的 30/60/80 并发面板（此处的测量是
顺序 agentic-mode，而非并发 burst）。其他地方存在的两个部分并发
数据点：

- **TurboQuant**（K=`q8_0` V=`turbo2`，Qwen3-4B，M4 Pro）：**4 并发下聚合 +9%**
  （68.5 → 74.7 t/s），尽管单流为 −8%——KV
  压缩换回了并行余量。
- **oMLX** 连续批处理（mlx-lm `BatchGenerator`）：**burst-8 下聚合 ×1.8**
  （12.8 → 22.9 t/s），但一旦 27B-dense 把 RAM 占满进入 swap，它在 burst-30 下
  **崩溃**（17.3 t/s）——0 次崩溃。

跨所有引擎的专用 burst-mode 面板暂缓进行。

---

## Section 3 — Caches & optimizations

| # | Couple | Cache reuse cross-USER | Snapshot persists cross-restart | MTP support | MTP accept rate | TurboQuant compat | KV cache native types | Native parallel slots |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Rapid-MLX 前缀缓存**：缓存存储混合注意力 KV slab +
RNN 状态快照，以 `<repo>--<sys_prompt_hash>` 为键，并持久化于
`~/.cache/vllm-mlx/`。观测到的约 131 ms 前缀测试 TTFT 是一次 RAM 内 KV slab
重新挂载加上变化用户的前向传递，而非从磁盘重新加载。

**oMLX 大上下文缓存。** oMLX 的 2 层分页 SSD KV 缓存在相同提示词缓存命中时，
将一次 55K-token 的 prefill 从约 115 s 降至约 **3.5 s** TTFT（×33；55,296 /
55,837 个 token 已缓存）。在小提示词（约 7.5K）上没有优势（约 2-5 s，=
mlx-lm），且解码约 19 t/s（无原始速度增益）。这是相同提示词复用，而非
跨 USER 复用（oMLX 不支持后者）；跨重启持久化已有文档记录，但
尚未进行 A/B 测试。

**TurboQuant KV 压缩**（llama.cpp）。K=`q8_0` V=`turbo2` 将 KV RAM 削减约 **28%**
（4B 模型上 22.9 → 16.4 GB，M4 Pro），工具调用有效性不变（10/10），
并在 **4 并发下获得 +9% 聚合**，尽管单流为 −8%。对称的
K=`turbo3` V=`turbo3` 达到约 −56% RAM，但会降低质量（提前停止、
重复）——非对称的 `q8_0`/`turbo2` 才是可用配置。

---

## Section 4 — Memory & resources (Apple Silicon M5 Max 128 GB)

| # | Couple | Working-set RAM (GB) | Disk footprint (GB) | Swap Δ idle | Swap Δ under load | SOLO required? | Cohabitation safe? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **“Under load”** = 包含一次 50K-token prefill 的 8 阶段 agentic 基准测试（已测量的
> 最重的*顺序*内存压力），M5 Max 128 GB，SOLO：**每个引擎的 swap delta
> 均为 0 MB / 0 swapouts**——模型 + KV 装入空闲/非活动内存，
> 留有 >100 GB 余量。这是顺序负载内存，**不是** 60 并发
> 内存（见 Section 2）。Working-set RAM 是估算值；测得的 RSS 包含
> mmap 的 GGUF / wired MLX 页面，因此真实的增量占用更低（
> MTP 头增加约 +3 GB）。

### Observations

- **Rapid-MLX 在 GPU 上需要 SOLO 运行**：与另一个
  正在解码的引擎共处会触发 5.4 → 14.2 GB 的 swap delta 以及解码
  崩溃至 0.4 t/s。不要在同一 Apple Silicon
  GPU 上启动第二个引擎。
- **LM Studio MTP** 磁盘占用相比无 MTP 头的 Q4_K_S 为 +13%，原因是
  MTP 权重块。相对于 +17% 解码增益，成本可忽略。
- 在 M5 Max 128 GB 统一内存上：测试的每个 35B-A3B 配置在加载后都留有
  超过 100 GB 余量——RAM 不是限制因素。
- 在 M4 Pro 64 GB 上：`Q5_K_XL` 与辅助模型并存时**装不下**（生产中观测到 swap
  抖动）。`Q4_K_S` 能装下。

---

## Section 5 — Model quality

> 此处的公开基准数字为**厂商 / 自报**，并由
> 排行榜（llm-stats）聚合，未经独立验证。在依赖它们之前，请在
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) 上交叉验证。asiai 自己在 Apple Silicon
> 上的直接测量见下一节。
>
> 仅作者声明（Jackrong/Qwopus、Unsloth 自评）被单独标记，
> 并排除在公开排行榜列之外。
>
> 🔴 **关键发现**：多个社区模型卡片引用的“Hessling agentic”基准
> **无法独立复现**——16 个提示词、单一策展人、无中立排行榜
> 集成。三位顾问均
> 建议仅将其视为冒烟测试。

### Open-weight Qwen 3.6 base models

> 公开排行榜数字（llm-stats），自报。27B-dense 在 SWE-bench 上
> 优于 35B-A3B MoE——这与下方 asiai 自己的开发质量发现一致
>（MoE base 正是会触发工具调用空对象 bug 的那个）。MTP
> 头是解码速度特性，不会改变模型的质量分数。

| Model | Architecture | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** 远难于旧版 Terminal-Bench v1（社区
> 卡片对 v1 上的 35B-A3B 引用约 51.5%）；此处的 24.6% 是 2.0 这一代。

### Qwopus 3.6 family — author-reported only, **not independently verified**

Jackrong 在 HuggingFace 上发布的 Qwopus 3.6 微调模型声称
相比 Qwen base 有显著提升。截至 2026 年 5 月，这些声明
**尚未在中立排行榜上被独立复现**。在第三方进行
BFCL / SWE-bench 重跑之前，请将其视为实验性。

| Model (author claims) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ Jackrong 模型卡片上引用的“Hessling agentic”基准
似乎是一个 16 提示词的策展人特定评估，无中立
排行榜集成。所查询的三方顾问（Grok-4、GPT-5、
Gemini Advanced）均建议仅将其视为冒烟测试。

### Frontier anchors (mid-2026)

> 所有数字均为**厂商 / 自报**，由 llm-stats 聚合——没有一个
> 在那里经过独立验证。**Terminal-Bench 2.0** 是例外（
> tbench 团队会重跑提交；各行为最佳的智能体×模型分数）。GPQA 是
> 厂商“Diamond”数字，且该集合接近饱和——请视为近似。

| Model | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Source |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 没有公开的 SWE-bench *Verified* 分数（OpenAI 报告 SWE-bench Pro
Public 58.6%）；流传的“88.7% SWE-bench”数字不在任何主要
来源上。注意：**Qwen 3.6 没有 235B-A22B**——开放系列是 27B-dense
和 35B-A3B（见下）；235B-A22B 是上一代 Qwen3。

### Same-class open-weights baselines

| Model | MMLU-Pro | SWE-bench Verified | Notes |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### Quality benchmarks deprecated for this decision

- **HumanEval / HumanEval+** —— 2026 年已饱和，所有前沿模型均高于 90%，已无信号。
- **GSM8K** —— 已饱和，对编码智能体无信号。
- **MMLU (original)** —— 已被 MMLU-Pro 取代。
- **作者自报的“Hessling agentic”16 提示词** —— 不可复现，仅视为冒烟测试。

### Open quality questions (research gaps)

1. **每 GB RAM 质量基准**：尚无标准。建议的代理公式：
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`。
2. **长程稳定性（60+ 工具调用）**：现有最接近的基准是
   τ-bench、PencilPuzzleBench（>1000 轮）、MultiAgentBench、TRAIL。它们
   都没有专门测量“60-80 次顺序工具调用中的 schema 正确性与战略一致性”——
   这一基准空白得到三位顾问的一致承认。
3. **量化感知评估（MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL）**：尚无
   标准化排行榜。社区报告存在分歧——有些声称 MLX-4bit
   在保持工具调用稳定性上不如 GGUF Q5_K_M，另一些则相反。**实用建议**：
   在投入生产前，针对每种量化运行你自己的
   生产工作负载。
4. **Qwopus 3.6 系列质量验证**：需要第三方 BFCL +
   SWE-bench 重跑。作者声明不应驱动生产决策。

---

## asiai direct measurements — Apple Silicon, mid-2026

> 上述公开排行榜未展示的内容：asiai 直接在 Apple Silicon
>（M5 Max 128 GB，High Power Mode；M4 Pro 64 GB）上运行的测量，llama.cpp
> b9430，确定性（temp 0），在公开的 Qwen 3.6 系列和
> Opus 蒸馏的 **Qwopus** 微调模型上。注意事项：M5 笔记本上的跨会话
> 绝对吞吐量为 ±15%（热/负载）；只有**会话内 ±MTP 背靠背的
> 差值**是收紧的，且 M5↔M4 的绝对值不可比（不同量化）。

### Dev-quality / tool-call (`asiai bench --code`)

- **base Qwen 3.6-35B-A3B (MoE)** 在深上下文轮次中将 `edit_file.edits`
  坍缩为空对象——**3/3 运行，在 Q4_K_S 和 Q5_K_XL 上均如此**，相同
  聊天模板。工具调用整洁 **87.5%**，编辑轮整洁 **66.7%**。这是
  MoE base 的工具调用生成行为，与量化无关，也与模板无关。
- **dense 27B**（Q5_K_XL）和 **Qwopus-35B-A3B**（Q4_K_S）均取得 **100%
  整洁 / 0 bug**——Qwopus 在 MoE 约 4× 的解码速率下达到了 dense-27B 的工具调用
  可靠性。
- 在更难的工具调用压力套件下，Qwopus 保持 **100% / 0**，而 dense
  27B 降至 **88.9% / 3 bug**（同样的空对象失败）。但在
  一个表达式求值陷阱（`**` 与一元负号的优先级）上，**dense 27B
  正确而 Qwopus 错误**——它们分道扬镳。（恢复率对权重敏感
  且有噪声——非头条结论。）

### Thinking ablation (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 deterministic runs)

| Config | Tool-call clean | Note |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### MTP throughput (`--spec-type draft-mtp`, warm decode, intra-session ±MTP)

| Model / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

MTP 增益随 **(MoE > dense) × (M5 > M4)** 缩放——在 MoE 上强烈为正，
在慢速 dense 路径上从边际到负值（draft 开销未被摊销）。Qwopus 微调版的 MTP 头也比 base 更弱（Qwopus 27B +3% / 35B +17%，对比 base 27B-dense +18% / 35B-A3B +38%）——微调会侵蚀 draft 头。
MLX 侧的 MTP（mlx_vlm）被取消资格：它破坏长上下文（空输出、
75% 有效）。头条：35B-A3B MoE + MTP 在 llama.cpp 上于 M5 Max 上维持 **~118 t/s**
解码（M4 Pro 上 ~44 t/s），约为 27B-dense 的 4×，约 1.5 tok/s/W，TTFT
~62 ms，100% 输出有效性。

### Instruction-following (`asiai bench --instruct`, research-brief)

thinking 权衡在多步交付物上有实际影响：使用
`enable_thinking=false` 时，Qwopus-35B 完成了工具工作，但交付所请求的
多章节简报的比例为 **0%**（它在次要步骤处停止）；开启 thinking 时，
base 模型交付率为 **100%**（5/5 章节）。这与上方的工具调用结果方向
相反——thinking-off 对原子工具调用最整洁，但会抑制书面交付物——
这正是 asiai **按任务维度**设置 thinking 而非作为单一全局开关的原因。

### Perfectionist research loop (`asiai bench --instruct loop-search`)

单轮 IFEval 和 research-brief 在这些模型上都饱和到 100%，因此两者都暴露
不出*完美主义研究循环*：一个不肯接受含糊、无法确认的搜索结果的模型，
会反复发出语义等价的查询，直到一个无进展护栏将其叫停，始终不交付。一次
`loop-search` 横扫（9 个配置，M5，b9430，thinking 开/关，两种含糊模式）
将其隔离出来：

- **35B-A3B MoE 会循环到上限** —— **基座版和 Qwopus 微调版皆然，在 Q4 和
  Q8 下亦然**。更高的量化也救不了它，所以这个循环是 **A3B MoE 的架构性
  问题**，而非量化所致。
- **稠密 27B 从不循环**（Q4 / Q5 / Q8）：它接受这个含糊的结果并撰写简报。

因此吞吐冠军（MoE，~118-123 t/s）和 agentic 适配度冠军（稠密 27B，
~25 t/s）是*不同的模型*。对于 NousResearch 的 Hermes Agent 这类框架，
抗循环性可以胜过原始 decode —— 最快的模型并不总是合适的 agent。（这与
工具调用结果相反，在那里 MoE 微调版才是更稳健的 agent：**适配度是逐失败
模式而定的，所以要测多个。**）

---

## Section 6 — Operational

> 📌 能力快照（mid-2026）。Apple Silicon 上的引擎版本每周变动——
> 这些单元格是时间点状态，并非锁定版本的保证。

| # | Engine | License | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Persisted prefix cache | Maintainer activity |
|---|--------|---------|---|---|---|---|---|---|---|---|
| 1 | Rapid-MLX 0.6.66 | Apache-2.0 | ✅ | ✅ | ✅ (HTML page) | ❌ (logs only) | ✅ | ✅ HF Hub auto-DL on serve | ✅ `~/.cache/vllm-mlx/prefix_cache/` | community (raullenchai) |
| 2 | LM Studio 0.4.14 | proprietary | ✅ | ✅ | partial (websocket) | ❌ | ✅ | ✅ via `lms get` CLI | ❌ | Element Labs |
| 3 | llama.cpp b9270 | MIT | ✅ | ✅ | ✅ | ✅ `--metrics` | ✅ | manual (GGUF on disk) | ❌ (`--cache-reuse N` arch-disabled on hybrid) | ggerganov very active |
| 4 | mlx-lm | MIT | ✅ | ✅ | ✅ | ❌ | partial | ✅ HF auto | ❌ | Apple ml-explore active |
| 5 | oMLX | MIT | ✅ | ✅ | ✅ | ❌ | ✅ (caveat: post-cache-hit bug) | ✅ | partial (tiered SSD) | jundot active |
| 6 | vLLM-MLX | Apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ paged-attention | vllm-project active |
| 7 | vMLX (Mamba/SSM) | Apache-2.0 | ✅ | ✅ | ✅ | partial | untested | partial | untested | community |
| 8 | Ollama | MIT | ✅ | partial | ✅ `/api/version` | ❌ | partial | ✅ `ollama pull` | ❌ | Ollama Inc. very active |

---

## Section 7 — Quality benchmark weighting for agentic-coding workloads

> 这是面向编排器级工作负载的 **asiai 默认权重**
>（每轮 60-80 次顺序工具调用、schema 校验输出、长上下文
> 系统提示词）。它参考了三份前沿 LLM 顾问意见
>（Grok-4、GPT-5、Gemini Advanced，于 2026 年 5 月查询），但**不是社区
> 共识**——请视为起点，而非权威。可通过
> 未来的 `--weights` 标志覆盖（已规划）。

| Benchmark | What it measures | Why it matters here | Consensus weight |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### Benchmarks consciously dropped from the weighting

- MMLU-Pro、GPQA Diamond、HumanEval+ —— 作为通用能力信号有用，
  但根据 2026 年的证据，与智能体循环可靠性**弱相关**。
  前沿实验室的确认表明，单次推理分数已不再以足够的
  粒度预测自主智能体的成功。
- 无第三方重跑的作者自报聚合（Jackrong Hessling、
  Unsloth 自评、GLM-4.6-Coder 厂商声明）。

---

## Section 8 — Custom "endurance" benchmark proposal (research opportunity)

三位顾问在同一空白上达成共识：**最能刻画
编排器工作负载的基准目前尚无公开版本**。构建
一个是获得缺失信号的唯一途径。

### Proposed scope

- 每条轨迹 **80 次顺序工具调用**
- **每轮 schema 校验**（严格 JSON / 结构化输出）
- **累积上下文增长**（沿轨迹 10K → 50K token）
- **中断 / 恢复测试**（轨迹中途取消 + 恢复）
- **畸形 XML/JSON 恢复**（智能体能否自我纠正？）
- **仓库编辑持久性**（第 N 轮做出的编辑在第 60 轮是否仍然成立？）

这在 asiai 路线图上（burst-mode 之后的长程耐力模式）。
若构建完成，它将是这一特定细分领域的首个公开基准。

---

## Methodology

- **Hardware**：MacBook Pro M5 Max 128 GB 统一内存，macOS 26.4.1。
- **Workload**：编排器级——系统提示词 ~7 KB，用户提示词 ~150-200
  token，每轮 60-80 次调用。
- **测量的阶段**（single-call，agentic-mode v1.6.0）：
  - `cold`：全新启动后的首次调用
  - `warm`：与 cold 完全相同的提示词（warm 缓存）
  - `prefix-test-1/2/3`：相同系统、用户变化——测量跨 USER 缓存复用
  - `cold-prefix`：相同系统、重启后——测量持久缓存
- **前缀缓存复用判定**：若 `median(prefix-test) / cold < 0.2` 则为 `YES`，
  否则为 `NO`。
- **反偏置措施**：SOLO 模式（无共处引擎）、热空闲
  基线、mmap 预热阶段。
- **质量门**（由 asiai bench 自动跟踪）：
  - `early_stop`：至少 2 次运行的完成量 `<0.5×` 中位数
  - `memory_pressure`：swap delta `>500 MB` 或 swapouts delta `>1000`
  - `duplicate_processes`：基准测试期间检测到多个引擎进程

完整协议即 `asiai bench --agentic-mode` / `--burst-mode`
仪表化（power/thermal、引擎占用、KV 占用率、前缀缓存
阶段）——见 asiai CLI 文档。

---

## Open questions

1. **vLLM-MLX/Rapid-MLX 上的 MTP —— 已（部分）回答。** vLLM-MLX 在
   prerelease **0.4.0rc1**（2026-05-21）中添加了 MTP；一旦
   Rapid-MLX 分支跟进 0.4.x，理论组合“MLX + 配备 MTP 的 Qwopus 35B-A3B +
   跨 USER 快照”有望在解码和 TTFT 上双双取胜。跟踪 Rapid-MLX 何时采纳 MTP 路径。
2. **MLX 运行时上的 MTP —— 当前状态。** 已发布的 mlx-lm 不会将
   MTP 头作为原生投机解码运行（`sanitize()` 在转换过程中丢弃 MTP 权重；
   原生支持在未合并的 PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) 中）。
   LM Studio 的 `mlx-engine` 封装了 mlx-lm，因此继承了这一点——Section 1 第 5 行的
   +13.5% 解码增益来自 LM Studio 的 **源自 llama.cpp 的
   后端**（文件是 GGUF），而非 mlx-engine 投机解码。
3. **Rapid-MLX/vllm-mlx 在 60-80 调用规模下的 burst 行为**：smoke
   测试确认 burst=5 下为单槽位 FIFO。完整面板待进行（Section
   2）。相关的上游问题是 vllm-mlx 是否计划为混合架构模型实现
   连续批处理 / 多槽位调度。
4. **Qwen 3.6 混合架构上的 `llama_memory_can_shift=false`** —— 在上游仍然
   未修复。[#18497](https://github.com/ggml-org/llama.cpp/issues/18497)
   已关闭（记录了完整重新处理）；[#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   是一个 *issue*（closed-as-completed），**不是**已合并的修复；实际的修复 PR
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) 被 **关闭
   未合并**（补丁仅存在于分支上）。“只需启用 `preserve_thinking`”的
   绕过方法被开放 issue
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) 驳斥（0.67× 加速 =
   缓存保持惰性）。混合 DeltaNet 层在构造上不暴露可移位的缓存
   状态。
5. **Qwopus 3.6 质量独立复现**：需要第三方
   BFCL / SWE-bench 重跑。在交叉验证之前，作者发布的数字不应驱动
   生产决策。
6. **vllm-mlx vs Rapid-MLX 脉络 —— 已回答。** Rapid-MLX 是
   `waybarrios/vllm-mlx` 的社区**硬分支**，而非薄封装：它把
   引擎在仓库内 vendor（包仍名为 `vllm_mlx`），不 pip 依赖
   上游包，且已大幅分叉（Rapid-MLX 0.6.74 vs 上游
   0.3.0）。共享的 `vllm_mlx` 包名和 `~/.cache/vllm-mlx/` 目录是
   归属混淆的常见来源（见 Section 3，caveat 2）。

---

*本面板是一份持续更新的文档。欢迎通过
[github.com/druide67/asiai](https://github.com/druide67/asiai/issues) 提交贡献、修正与额外的
bench cell。*
