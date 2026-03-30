---
description: "Exo分散LLM推論：複数のMacを接続してベンチマーク、ポート52415、クラスターセットアップとパフォーマンス。"
---

# Exo

Exoはローカルネットワーク上の複数のApple Silicon MacのVRAMをプールすることで分散LLM推論を可能にし、ポート52415でサービスを提供します。単一マシンに収まらない70B以上のパラメータモデルを、自動ピア検出とOpenAI互換APIで実行できます。

[Exo](https://github.com/exo-explore/exo)は複数のApple Siliconデバイス間での分散推論を可能にします。複数のMacからVRAMをプールして大規模モデル（70B以上）を実行できます。

## セットアップ

```bash
pip install exo-inference
exo
```

またはソースからインストール：

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 52415 |
| APIタイプ | OpenAI互換 |
| VRAMレポーティング | あり（クラスターノード全体の集約） |
| モデルフォーマット | GGUF / MLX |
| 検出 | DEFAULT_URLsによる自動検出 |

## ベンチマーク

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exoは他のエンジンと同様にベンチマークされます。asiai はポート52415で自動検出します。

## 注意事項

- Exoはローカルネットワーク上のピアノードを自動的に検出します。
- asiai で表示されるVRAMは、クラスター全体のノードから集約された総メモリを反映しています。
- 単一Macに収まらない大規模モデルもクラスター全体でシームレスに実行できます。
- ベンチマーク実行前に、クラスター内の各Macで `exo` を起動してください。

## 関連項目

`asiai bench --engines exo` でエンジンを比較 --- [詳しくはこちら](../benchmark-llm-mac.md)
