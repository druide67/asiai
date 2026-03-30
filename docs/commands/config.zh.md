---
description: "如何配置 asiai：管理引擎 URL、端口和 Mac 上 LLM 基准测试的持久化设置。"
---

# asiai config

管理持久化引擎配置。`asiai detect` 发现的引擎会自动保存到 `~/.config/asiai/engines.json`，加快后续检测。

## 用法

```bash
asiai config show              # 显示已知引擎
asiai config add <engine> <url> [--label NAME]  # 手动添加引擎
asiai config remove <url>      # 删除引擎
asiai config reset             # 清除所有配置
```

## 子命令

### show

显示所有已知引擎及其 URL、版本、来源（auto/manual）和最后发现时间戳。

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

手动注册非标准端口的引擎。手动引擎永不被自动清理。

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

按 URL 删除引擎条目。

```bash
asiai config remove http://localhost:8800
```

### reset

删除整个配置文件。下次 `asiai detect` 将从头发现引擎。

## 工作原理

配置文件存储检测过程中发现的引擎：

- **自动条目**（`source: auto`）：`asiai detect` 发现新引擎时自动创建。7 天不活跃后清理。
- **手动条目**（`source: manual`）：通过 `asiai config add` 创建。永不自动清理。

`asiai detect` 的 3 层检测级联使用此配置作为第 1 层（最快），然后是端口扫描（第 2 层）和进程检测（第 3 层）。详见 [detect](detect.md)。

## 配置文件位置

```
~/.config/asiai/engines.json
```
