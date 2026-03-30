---
description: 浏览器中的实时 LLM 监控仪表板。GPU 指标、引擎健康、性能历史。无需额外配置。
---

# asiai web

启动 Web 仪表板进行可视化监控和基准测试。

## 用法

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## 选项

| 选项 | 默认值 | 描述 |
|------|--------|------|
| `--port` | `8899` | HTTP 监听端口 |
| `--host` | `127.0.0.1` | 绑定地址 |
| `--no-open` | | 不自动打开浏览器 |
| `--db` | `~/.local/share/asiai/asiai.db` | SQLite 数据库路径 |

## 要求

Web 仪表板需要额外依赖：

```bash
pip install asiai[web]
# 或安装全部：
pip install asiai[all]
```

## 页面

### 仪表板（`/`）

系统概览，含引擎状态、已加载模型、内存使用和最近的基准测试结果。

### 基准测试（`/bench`）

直接在浏览器中运行跨引擎基准测试：

- **Quick Bench** 按钮——1 个提示词，1 次运行，约 15 秒
- 高级选项：引擎、提示词、运行次数、context-size（4K/16K/32K/64K）、功耗
- SSE 实时进度
- 结果表格（含冠军高亮）
- 吞吐量和 TTFT 图表
- **可分享卡片** — 基准测试后自动生成（PNG 通过 API，SVG 兜底）
- **分享区域** — 复制链接、下载 PNG/SVG、分享到 X/Reddit、导出 JSON

### 历史（`/history`）

可视化基准测试和系统指标的时间趋势：

- 系统图表：CPU 负载、内存 %、GPU 利用率（含 renderer/tiler 分解）
- 引擎活动：TCP 连接、正在处理的请求、KV cache 使用率 %
- 基准测试图表：每引擎的吞吐量（tok/s）和 TTFT
- 进程指标：基准测试运行期间的引擎 CPU % 和 RSS 内存
- 按时间范围筛选（1h / 24h / 7d / 30d / 90d）或自定义日期范围
- 含 context-size 标注的数据表（如 "code (64K ctx)"）

### 监控（`/monitor`）

5 秒刷新的实时系统监控：

- CPU 负载 sparkline
- 内存仪表
- 温控状态
- 已加载模型列表

### 诊断（`/doctor`）

系统、引擎和数据库的交互式健康检查。与 `asiai doctor` 相同的检查项，配备可视化界面。

## API 端点

Web 仪表板暴露 REST API 端点供编程访问。

### `GET /api/status`

轻量健康检查。缓存 10 秒，响应 < 500ms。

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

状态值：`ok`（所有引擎可达）、`degraded`（部分下线）、`error`（全部下线）。

### `GET /api/snapshot`

完整系统 + 引擎快照。缓存 5 秒。包含 CPU 负载、内存、温控状态和每引擎状态及已加载模型。

### `GET /api/benchmarks`

带筛选的基准测试结果。返回每次运行数据，含 tok/s、TTFT、功耗、context_size、engine_version。

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `hours` | `168` | 时间范围（小时，0 = 全部） |
| `model` | | 按模型名筛选 |
| `engine` | | 按引擎名筛选 |
| `since` / `until` | | Unix 时间戳范围（覆盖 hours） |

### `GET /api/engine-history`

引擎状态历史（可达性、TCP 连接、KV cache、预测 token 数）。

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `hours` | `168` | 时间范围（小时） |
| `engine` | | 按引擎名筛选 |

### `GET /api/benchmark-process`

基准测试运行的进程级 CPU 和内存指标（保留 7 天）。

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `hours` | `168` | 时间范围（小时） |
| `engine` | | 按引擎名筛选 |

### `GET /api/metrics`

Prometheus exposition 格式。Gauge 覆盖系统、引擎、模型和基准测试指标。

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

指标包含：

| 指标 | 类型 | 描述 |
|------|------|------|
| `asiai_cpu_load_1m` | gauge | CPU 平均负载（1 分钟） |
| `asiai_memory_used_bytes` | gauge | 已用内存 |
| `asiai_thermal_speed_limit_pct` | gauge | CPU 速度限制 % |
| `asiai_engine_reachable{engine}` | gauge | 引擎可达性（0/1） |
| `asiai_engine_models_loaded{engine}` | gauge | 已加载模型数 |
| `asiai_engine_tcp_connections{engine}` | gauge | 已建立的 TCP 连接 |
| `asiai_engine_requests_processing{engine}` | gauge | 正在处理的请求 |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | KV cache 填充率（0-1） |
| `asiai_engine_tokens_predicted_total{engine}` | counter | 累计预测 token 数 |
| `asiai_model_vram_bytes{engine,model}` | gauge | 每模型 VRAM |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | 最近基准测试 tok/s |

## 说明

- 仪表板默认绑定 `127.0.0.1`（仅本地）
- 使用 `--host 0.0.0.0` 暴露到网络（如远程监控）
- 端口 `8899` 是为了避免与推理引擎端口冲突
