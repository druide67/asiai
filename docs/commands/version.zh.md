---
description: "一条命令查看 asiai 版本、Python 环境和 Agent 注册状态。"
---

# asiai version

显示版本和系统信息。

## 用法

```bash
asiai version
asiai --version
```

## 输出

`version` 子命令显示丰富的系统上下文：

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

`--version` 参数仅显示版本字符串：

```
asiai 1.0.1
```

## 使用场景

- Issue 和 Bug 报告中的快速系统检查
- Agent 上下文收集（芯片、RAM、可用引擎）
- 脚本：`VERSION=$(asiai version | head -1)`
