---
description: "asiai 终端界面：在终端中使用交互式仪表板实时监控 LLM 推理引擎。"
---

# asiai tui

自动刷新的交互式终端仪表板。

## 用法

```bash
asiai tui
```

## 要求

需要 `tui` 扩展：

```bash
pip install asiai[tui]
```

这将安装 [Textual](https://textual.textualize.io/) 终端 UI 框架。

## 功能

- 实时系统指标（CPU、内存、温控）
- 引擎状态和已加载模型
- 可配置间隔的自动刷新
