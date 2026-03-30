---
description: "Exo 分布式 LLM 推理：多台 Mac 联合基准测试，端口 52415，集群配置和性能。"
---

# Exo

Exo 通过在本地网络中汇集多台 Apple Silicon Mac 的 VRAM 实现分布式 LLM 推理，服务端口 52415。它可以运行单机无法容纳的 70B+ 参数模型，支持自动节点发现和 OpenAI 兼容 API。

[Exo](https://github.com/exo-explore/exo) 支持跨多个 Apple Silicon 设备的分布式推理。通过汇集多台 Mac 的 VRAM 运行大模型（70B+）。

## 配置

```bash
pip install exo-inference
exo
```

或从源码安装：

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## 详情

| 属性 | 值 |
|------|---|
| 默认端口 | 52415 |
| API 类型 | OpenAI 兼容 |
| VRAM 报告 | 是（跨集群节点聚合） |
| 模型格式 | GGUF / MLX |
| 检测方式 | 通过 DEFAULT_URLS 自动检测 |

## 基准测试

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo 的基准测试方式与其他引擎相同。asiai 在端口 52415 自动检测它。

## 说明

- Exo 在本地网络上自动发现对等节点。
- asiai 中显示的 VRAM 反映所有集群节点的总聚合内存。
- 单机无法容纳的大模型可以在集群中无缝运行。
- 运行基准测试前，需在集群中每台 Mac 上启动 `exo`。

## 另见

使用 `asiai bench --engines exo` 比较引擎 --- [了解方法](../benchmark-llm-mac.md)
