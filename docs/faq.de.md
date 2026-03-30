---
title: "Häufig gestellte Fragen"
description: "Häufige Fragen zu asiai: unterstützte Engines, Apple-Silicon-Anforderungen, LLM-Benchmarking auf dem Mac, RAM-Anforderungen und mehr."
type: faq
faq:
  - q: "Was ist asiai?"
    a: "asiai ist ein Open-Source-CLI-Tool, das LLM-Inferenz-Engines auf Apple-Silicon-Macs benchmarkt und überwacht. Es unterstützt 7 Engines (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) und misst tok/s, TTFT, Stromverbrauch und VRAM-Nutzung."
  - q: "Welche ist die schnellste LLM-Engine auf Apple Silicon?"
    a: "In Benchmarks auf M4 Pro 64 GB mit Qwen3-Coder-30B erreicht LM Studio (MLX-Backend) 102 tok/s gegenüber 70 tok/s von Ollama — 46% schneller bei der Token-Generierung. Allerdings hat Ollama eine niedrigere Time-to-First-Token-Latenz."
  - q: "Funktioniert asiai auf Intel-Macs?"
    a: "Nein. asiai erfordert Apple Silicon (M1, M2, M3 oder M4). Es nutzt macOS-spezifische APIs für GPU-Metriken, IOReport-Leistungsüberwachung und Hardwareerkennung, die nur auf Apple-Silicon-Chips verfügbar sind."
  - q: "Wie viel RAM brauche ich, um LLMs lokal zu betreiben?"
    a: "Für ein Q4-quantisiertes 7B-Modell: mindestens 8 GB. Für 13B: 16 GB. Für 30B: 32-64 GB. MoE-Modelle wie Qwen3.5-35B-A3B nutzen nur etwa 7 GB aktive Parameter, ideal für 16-GB-Macs."
  - q: "Ist Ollama oder LM Studio besser für Mac?"
    a: "Es kommt auf den Anwendungsfall an. LM Studio (MLX) ist schneller beim Durchsatz und energieeffizienter. Ollama (llama.cpp) hat eine niedrigere First-Token-Latenz und handhabt große Kontextfenster (>32K) besser. Siehe den detaillierten Vergleich auf asiai.dev/ollama-vs-lmstudio."
  - q: "Benötigt asiai sudo oder Root-Zugang?"
    a: "Nein. Alle Funktionen einschließlich GPU-Observability (ioreg) und Leistungsüberwachung (IOReport) funktionieren ohne sudo. Das optionale --power-Flag zur Kreuzvalidierung mit powermetrics ist die einzige Funktion, die sudo verwendet."
  - q: "Wie installiere ich asiai?"
    a: "Installieren Sie über pip (pip install asiai) oder Homebrew (brew tap druide67/tap && brew install asiai). Python 3.11+ erforderlich."
  - q: "Können KI-Agenten asiai nutzen?"
    a: "Ja. asiai enthält einen MCP-Server mit 11 Tools und 3 Ressourcen. Installieren Sie mit pip install asiai[mcp] und konfigurieren Sie als asiai mcp in Ihrem MCP-Client (Claude Code, Cursor usw.)."
  - q: "Wie genau sind die Leistungsmessungen?"
    a: "IOReport-Leistungswerte haben weniger als 1,5% Abweichung im Vergleich zu sudo powermetrics, validiert über 20 Proben auf LM Studio (MLX) und Ollama (llama.cpp)."
  - q: "Kann ich mehrere Modelle gleichzeitig benchmarken?"
    a: "Ja. Verwenden Sie asiai bench --compare für modellübergreifende Benchmarks. Unterstützt die model@engine-Syntax für präzise Steuerung, mit bis zu 8 Vergleichsslots."
  - q: "Wie teile ich meine Benchmark-Ergebnisse?"
    a: "Führen Sie asiai bench --share aus, um Ergebnisse anonym an das Community-Leaderboard zu übermitteln. Fügen Sie --card hinzu, um ein teilbares 1200x630 Benchmark-Kartenbild zu generieren."
  - q: "Welche Metriken misst asiai?"
    a: "Sieben Kernmetriken: tok/s (Generierungsgeschwindigkeit), TTFT (Time to First Token), Leistung (GPU+CPU Watt), tok/s/W (Energieeffizienz), VRAM-Nutzung, Stabilität zwischen Durchläufen und thermischer Drosselungszustand."
---

# Häufig gestellte Fragen

## Allgemein

**Was ist asiai?**

asiai ist ein Open-Source-CLI-Tool, das LLM-Inferenz-Engines auf Apple-Silicon-Macs benchmarkt und überwacht. Es unterstützt 7 Engines (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) und misst tok/s, TTFT, Stromverbrauch und VRAM-Nutzung mit null Abhängigkeiten.

**Funktioniert asiai auf Intel-Macs oder Linux?**

Nein. asiai erfordert Apple Silicon (M1, M2, M3 oder M4). Es nutzt macOS-spezifische APIs (`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`), die nur auf Apple-Silicon-Macs verfügbar sind.

**Benötigt asiai sudo oder Root-Zugang?**

Nein. Alle Funktionen einschließlich GPU-Observability (`ioreg`) und Leistungsüberwachung (`IOReport`) funktionieren ohne sudo. Das optionale `--power`-Flag zur Kreuzvalidierung mit `powermetrics` ist die einzige Funktion, die sudo verwendet.

## Engines und Leistung

**Welche ist die schnellste LLM-Engine auf Apple Silicon?**

In unseren Benchmarks auf M4 Pro 64 GB mit Qwen3-Coder-30B (Q4_K_M) erreicht LM Studio (MLX-Backend) **102 tok/s** gegenüber **70 tok/s** von Ollama — 46% schneller bei der Token-Generierung. LM Studio ist außerdem 82% energieeffizienter (8,23 vs 4,53 tok/s/W). Siehe unseren [detaillierten Vergleich](ollama-vs-lmstudio.md).

**Ist Ollama oder LM Studio besser für Mac?**

Es kommt auf den Anwendungsfall an:

- **LM Studio (MLX)**: Am besten für Durchsatz (Code-Generierung, lange Antworten). Schneller, effizienter, weniger VRAM.
- **Ollama (llama.cpp)**: Am besten für Latenz (Chatbots, interaktive Nutzung). Schnellere TTFT. Besser für große Kontextfenster (>32K Tokens).

**Wie viel RAM brauche ich, um LLMs lokal zu betreiben?**

| Modellgröße | Quantisierung | Benötigter RAM |
|-------------|--------------|----------------|
| 7B | Q4_K_M | Mindestens 8 GB |
| 13B | Q4_K_M | Mindestens 16 GB |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE (3B aktiv) | Q4_K_M | 16 GB (nur aktive Parameter geladen) |

## Benchmarking

**Wie starte ich meinen ersten Benchmark?**

Drei Befehle:

```bash
pip install asiai     # Installieren
asiai detect          # Engines finden
asiai bench           # Benchmark starten
```

**Wie lange dauert ein Benchmark?**

Ein Schnellbenchmark (`asiai bench --quick`) dauert etwa 2 Minuten. Ein vollständiger Engine-übergreifender Vergleich mit mehreren Prompts und 3 Durchläufen dauert 10-15 Minuten.

**Wie genau sind die Leistungsmessungen?**

IOReport-Leistungswerte haben weniger als 1,5% Abweichung im Vergleich zu `sudo powermetrics`, validiert über 20 Proben auf LM Studio (MLX) und Ollama (llama.cpp).

**Kann ich meine Ergebnisse mit anderen Mac-Nutzern vergleichen?**

Ja. Führen Sie `asiai bench --share` aus, um Ergebnisse anonym an das [Community-Leaderboard](leaderboard.md) zu übermitteln. Verwenden Sie `asiai compare`, um zu sehen, wie Ihr Mac abschneidet.

## Integration mit KI-Agenten

**Können KI-Agenten asiai nutzen?**

Ja. asiai enthält einen MCP-Server mit 11 Tools und 3 Ressourcen. Installieren Sie mit `pip install "asiai[mcp]"` und konfigurieren Sie als `asiai mcp` in Ihrem MCP-Client (Claude Code, Cursor, Windsurf). Siehe die [Anleitung zur Agentenintegration](agent.md).

**Welche MCP-Tools sind verfügbar?**

11 Tools: `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3 Ressourcen: `asiai://status`, `asiai://models`, `asiai://system`.
