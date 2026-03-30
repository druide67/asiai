---
description: "在 Mac 上将 asiai 作为后台守护进程运行：开机自启监控、Web 仪表板和 Prometheus 指标。"
---

# asiai daemon

通过 macOS launchd LaunchAgent 管理后台服务。

## 服务

| 服务 | 描述 | 模式 |
|------|------|------|
| `monitor` | 定期采集系统 + 推理指标 | 周期性（`StartInterval`） |
| `web` | 作为持久服务运行 Web 仪表板 | 长驻（`KeepAlive`） |

## 用法

```bash
# 监控守护进程（默认）
asiai daemon start                     # 启动监控（每 60 秒）
asiai daemon start --interval 30       # 自定义间隔
asiai daemon start --alert-webhook URL # 启用 webhook 告警

# Web 仪表板服务
asiai daemon start web                 # 在 127.0.0.1:8899 启动 web
asiai daemon start web --port 9000     # 自定义端口
asiai daemon start web --host 0.0.0.0  # 暴露到网络（无认证！）

# 状态（显示所有服务）
asiai daemon status

# 停止
asiai daemon stop                      # 停止监控
asiai daemon stop web                  # 停止 web
asiai daemon stop --all                # 停止所有服务

# 日志
asiai daemon logs                      # 监控日志
asiai daemon logs web                  # Web 日志
asiai daemon logs web -n 100           # 最后 100 行
```

## 工作原理

每个服务在 `~/Library/LaunchAgents/` 安装单独的 launchd LaunchAgent plist：

- **Monitor**：按配置间隔（默认 60 秒）运行 `asiai monitor --quiet`。数据存储在 SQLite 中。如提供 `--alert-webhook`，在状态转换（内存压力、温控、引擎下线）时通过 POST 发送告警。
- **Web**：作为持久进程运行 `asiai web --no-open`。崩溃后自动重启（`KeepAlive: true`，`ThrottleInterval: 10s`）。

两个服务都在登录时自动启动（`RunAtLoad: true`）。

## 安全性

- 服务在**用户级别**运行（无需 root）
- Web 仪表板默认绑定 `127.0.0.1`（仅本地）
- 使用 `--host 0.0.0.0` 时显示警告——未配置认证
- 日志存储在 `~/.local/share/asiai/`
