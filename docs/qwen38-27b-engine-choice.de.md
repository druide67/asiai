---
title: "Welche Engine für Qwen3.8-27B auf Apple Silicon"
description: "Acht Inferenz-Engines auf einem M5 Max mit demselben Modell gemessen. Zwei Engines, die dieselbe Gewichtsdatei lesen, unterscheiden sich um 50%, und das Flag, das 20% bringt, ist in fast allen davon standardmäßig aus."
type: article
date: 2026-08-16
updated: 2026-08-16
---

<!-- STALE: rewritten 2026-08-16 after adversarial audit; retranslate from the English before publishing -->

# Welche Engine für Qwen3.8-27B auf Apple Silicon

Die Modellfrage ist geklärt: Qwen3.8-27B läuft auf einem Laptop und fasst 262.144 Token
Kontext. Die Engine-Frage ist es nicht, und sie kostet mehr, als man denkt.

Wir haben acht Engines auf einem M5 Max gemessen. Die beiden interessantesten Ergebnisse
betreffen überhaupt nicht die Geschwindigkeit — sie betreffen zwei Engines, die
*dieselbe Datei* lesen und um 50% auseinanderliegen, und ein Flag, das niemand
einschaltet.

## Bedingungen, vor den Zahlen

M5 Max 128 GB, Netzbetrieb, High Power Mode, immer nur eine Engine resident. Reasoning auf
jeder Engine deaktiviert, damit sie untereinander vergleichbar sind. Thermisches Throttling
auf 50% innerhalb von 1-2 Minuten in jeder Zelle — **das sind Untergrenzen, keine Maxima**.
Ausgabevalidität 100% in jeder Zeile. Prompt-Größen 7.530 Token (kurze Phasen) und 55.839
(lang), Ausgabe auf 400 bzw. 200 Token begrenzt.

**Wir behaupten nicht, dass dies die Geschwindigkeiten sind, die Sie erreichen werden.**
Wir behaupten, dass es die Abstände zwischen den Engines unter einem Protokoll sind.

## Die Tabelle

| Engine | Gewichte | n | Warm | Bei 56k | Erstes Token | Speicher | Deklarierter ctx |
|---|---|---|---|---|---|---|---|
| **MTPLX** Bare-Speed | MTPLX 4-bit g64 | 3 | **56,0** | **46,5** | 101 ms | 22,0 GB | Engine-Default |
| **MTPLX** Optimized-Speed | MTPLX 4-bit g32 | **5** | **44,4** | 37,5 | 99 ms | 27,0 GB | Engine-Default |
| **mlx-vlm** + MTP-Drafter | MLX 4-bit ⁽¹⁾ | 3 | **43,3** | 28,9 | **9.982 ms** | 15,5 GB | Engine-Default |
| **MTPLX** Optimized-Quality | MTPLX 8-bit g64 | 3 | 40,8 | 30,3 | 118 ms | 32,9 GB | Engine-Default |
| Ollama 0.32.13 | GGUF (nicht deklariert) | 3 | 32,8 | 21,7 | 240 ms | 30,3 GB | 65.536 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31,8 | 22,7 | **125 ms** | 36,8 GB | 131.072 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30,2 | 24,7 | **33.195 ms** | 15,0 GB | Engine-Default |
| oMLX 0.6.0-dev | oQ4e-mtp (Drittanbieter) | 3 | 29,8 | 24,6 | 1.968 ms | 16,7 GB | Engine-Default |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28,8 | 24,0 | 432 ms | **14,6 GB** | Engine-Default |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27,8 | 23,4 | 419 ms | 36,3 GB | 65.536 |
| LM Studio 0.4.21 Standardwerte | GGUF Q5_K_XL ⁽²⁾ | 3 | 23,1 | 18,7 | 359 ms | 35,2 GB | 65.536 |

⁽¹⁾ und ⁽²⁾ kennzeichnen Zeilen, die sich eine **byte-identische Gewichtsdatei** teilen.
Jede Zeile ist eine Zelle, ein Export — keine Werte zwischen Läufen vermischt.

⚠️ **Speicher ist zwischen Familien nicht vergleichbar.** llama.cpp und Ollama mappen ihr
GGUF per mmap: Ihr Resident Set ist dateigestützt und auslagerbar (llama.cpp: 36,8 GB RSS,
aber 19,8 GB physischer Footprint). MLX-Engines allozieren. Lesen Sie die Spalte innerhalb
einer Familie, nicht familienübergreifend.

⚠️ **Der deklarierte Kontext unterscheidet sich.** Drei Engines bekamen ein explizites
Fenster; die anderen liefen mit ihrem Default. Das allein verbietet es, die Speicherspalte
global zu ranken.

## Zwei Engines, eine Datei, 50% auseinander ⁽¹⁾

mlx-vlm, mlx-lm und rapid-mlx bedienten alle `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
Snapshot `6067b15c` — dieselbe Datei auf der Platte.

| Engine | Warm | Erstes Token | Speicher |
|---|---|---|---|
| mlx-vlm + MTP-Drafter | **43,3** | 9.982 ms | 15,5 GB |
| rapid-mlx | 30,2 | 33.195 ms | 15,0 GB |
| mlx-lm | 28,8 | **432 ms** | 14,6 GB |

**+50% von mlx-lm zu mlx-vlm, ohne dass sich etwas außer dem Server geändert hätte.** Das
ist der sauberste Vergleich der Kampagne: kein Quantisierungsunterschied, über den man
streiten könnte.

Und es kehrt sich sofort um: Der 50%-Vorsprung von mlx-vlm kostet eine **23× schlechtere
Zeit bis zum ersten Token**, weil es überhaupt keinen Prefix-Cache hat. Für eine einmalige
Generierung gewinnt es. Für einen Agenten ist es unbrauchbar — und der Grund steht im
nächsten Abschnitt.

## Das Flag, das 20% bringt, und warum es aus ist ⁽²⁾

Qwen3.8 liefert einen **Multi-Token-Prediction-Head in den Gewichten** mit. Das Modell
schlägt mehrere Token im Voraus vor, die Engine verifiziert sie in einem einzigen
Forward-Pass. Engines, die die Akzeptanzregel über das Wahrscheinlichkeitsverhältnis
implementieren, erhalten die Ausgabeverteilung exakt; wir haben diese Eigenschaft nicht
selbst verifiziert, und Sie sollten sie einem Benchmark nicht auf Treu und Glauben
abnehmen — lesen Sie die Implementierung Ihrer Engine.

Fast jede Engine liefert es **ausgeschaltet** aus.

| Engine | Flag | Standardmäßig an? |
|---|---|---|
| vmlx | `--native-mtp-depth` | **ja** |
| MTPLX | `--mtp --depth 3` | ja |
| vllm-mlx | `--enable-mtp` | nein |
| llama.cpp | `--spec-type draft-mtp` | nein |
| LM Studio | `--speculative-draft-mtp` | nein |
| mlx-vlm | `--draft-kind mtp` + separates Drafter-Repository | nein |
| oMLX | hat bei Qwen3.8 in unseren Läufen nicht gegriffen | — |
| Ollama · mlx-lm · rapid-mlx | keine Unterstützung | — |

Wir haben die Kosten des Nichtwissens gemessen, auf derselben Gewichtsdatei, demselben
Kontext von 65.536, allem gleich außer zwei Flags: **LM Studio geht von 23,1 auf
27,8 tok/s, +20%.** Keine GUI zeigt es an.

Effekt zweiter Ordnung, und er wiegt schwerer: **Zwei Engines in ihren
Standardeinstellungen zu vergleichen, vergleicht zwei verschiedene Regime.** vmlx draftet,
llama.cpp nicht.

## Das erste Token spannt 350×. Prefill erklärt das nicht.

Von 99 ms bis 33.195 ms über die Tabelle hinweg. Entscheidend ist die **Granularität des
Prefix-Cache** — wie viel eines wiederholten Prompts zwischen den Turns überlebt. Gemessen
in derselben Phase (dem warmen Turn, in dem die Latenz bis zum ersten Token genommen wird):

| Engine | Wiederverwendet | Pro Turn neu prefillt | Erstes Token |
|---|---|---|---|
| llama.cpp | 7.526 / 7.530 — **Token-Ebene** | 4 Token | 125 ms |
| oMLX | 6.144 / 7.530 — **1024-Token-Blöcke** | 1.386 Token | 1.944 ms |
| mlx-vlm | 0 / 7.530 | 7.530 Token | 9.982 ms |

6.144 ist sechs mal 1.024. oMLX verwendet ganze Blöcke wieder und prefillt alles neu, was
keinen vollen Block füllt — 1.386 Token, in jedem Turn, für immer. Das ist die gesamte
Lücke zwischen 125 ms und 2 Sekunden.

⚠️ **Vergleichen Sie keine über die Session aggregierten Wiederverwendungsraten zwischen
Engines.** Sie haben je nachdem, wie viel des Test-Prompts cachefähig ist,
unterschiedliche Obergrenzen, und ihr Vergleich erzeugt Paradoxien, die verschwinden,
sobald man dieselbe Phase vergleicht. Wir haben diesen Fehler in einem früheren Entwurf
dieser Seite gemacht.

Wir veröffentlichen **keine** Spalte für den Prefill-Durchsatz. Unsere stammte aus einer
einzigen, nicht wiederholten Kaltanfrage, die bei Engines mit Lazy Loading das Lesen von
20 GB von der Platte einschließt — LM Studio maß 216 tok/s bei dieser Anfrage und 938 bei
der unmittelbar nächsten. Es wäre eine erfundene Zahl gewesen.

## Token pro Sekunde ist keine Geschwindigkeit

Über Quantisierungen desselben Modells hinweg misst tok/s teilweise, wie lang die Ausgaben
sind, nicht wie schnell sie ankommen:

| Build | tok/s | chars/s |
|---|---|---|
| Bare-Speed | 56,0 | 200,8 |
| Optimized-Speed | 44,4 | **203,1** |
| Optimized-Quality | 40,8 | 165,7 |

Bare-Speed führt mit 26% bei Token pro Sekunde und liegt bei Zeichen pro Sekunde
**zurück**. Derselbe Tokenizer bei allen dreien — was sich unterscheidet, ist das, was die
Quantisierungen zu schreiben gewählt haben. Veröffentlichen Sie die Definition zusammen
mit der Zahl.

## Was wir empfehlen

**Für einen lokalen autonomen Agenten: MTPLX mit `Qwen3.8-27B-MTPLX-Optimized-Speed`,
MTP-Tiefe 3.** Schnell, 99 ms bis zum ersten Token, Prefix-Wiederverwendung auf
Token-Ebene, 27 GB.

Nicht Bare-Speed, obwohl es auf dem Papier führt. Die drei Builds unterscheiden sich in
ihrer Divergenz gegenüber bf16, veröffentlicht vom Autor der Quantisierungen: **0,00105**
für Optimized-Quality, **0,0220** für Optimized-Speed, **0,0376** für Bare-Speed. Seine
Messung, nicht unsere, nicht reproduziert — aber es ist die einzige Genauigkeitszahl, die
überhaupt jemand hat, und Bare-Speed liegt eine Größenordnung von Quality entfernt.

Auch nicht Optimized-Quality: es kostet **8,3 GB mehr** für einen Vorsprung, den niemand an
einer Aufgabe nachgewiesen hat.

**Betreiben Sie es mit aktiviertem Reasoning.** Qwen empfiehlt die Effort-Stufe `xhigh` für
agentische Arbeit und stellt fest, dass ein geringerer Aufwand bei mehrstufigen agentischen
Aufgaben *„zu unzureichender Analyse, mehr Fehlschlägen und wiederholten Neuversuchen
führen kann, was die Gesamtlatenz erhöhen kann"*. MTPLX 2.7.1 führt deaktiviertes Reasoning
separat als bekanntes Problem bei Qwen3.8 auf. Beachten Sie: `high` existiert bei diesem
Modell nicht — Qwen bietet nur `low`, `medium` und `xhigh`, und `xhigh` ist der Standard.

## Was wir nicht messen konnten

**vmlx und vllm-mlx wurden versucht und fehlen.** Beide unterstützen natives MTP — bei
vmlx ist es standardmäßig an —, ihr Fehlen ist also eine echte Lücke in diesem Vergleich,
kein Rundungsfehler. vllm-mlx starb beim Start an einem Quoting-Fehler in der
Kommandozeile; vmlx lief noch, als dies hier herausging.

**Reasoning war durchgehend deaktiviert, um die Engines vergleichbar zu machen.** Das ist
eine Mess- und keine Deployment-Entscheidung — siehe die Empfehlung oben. Wir haben keine
Zahl dazu anzubieten, was Reasoning mit diesen Engines macht, und wir werden auch keine
extrapolieren.

**Vorbehalte zu den Versionen.** Die MTPLX-Zeilen liefen auf **2.6.0**, bevor die Engine
eine Modellfamilie `qwen3_8` auslieferte — sie bediente Qwen3.8 unter den Defaults von
Qwen3.6, einschließlich eines anderen Sampling-Vertrags. Das betrifft nicht den Durchsatz;
es betrifft alles, was das Verhalten angeht. Die oMLX-Zeile lief aus einem temporären
Entwicklungs-Build, dessen Versionsstring der Export nicht erfasst hat, diese Zeile ist
also so, wie sie veröffentlicht ist, nicht reproduzierbar. Und unser mlx-vlm-Export
identifiziert sich selbst als `mlxlm 0.31.3_2` — nur das Startlog beweist, dass
`mlx_vlm.server` der Server war.

**Die Rangfolge des ersten Tokens zwischen den drei MTPLX-Builds liegt innerhalb ihres
eigenen Rauschens** — Variationskoeffizienten von 0,33 bis 0,66 bei dieser Metrik. 99, 101
und 118 ms sind nicht trennbar. Die Durchsatzspalte ist weit stabiler (CV 0,01-0,04).

**Die Test-Retest-Streuung bei identischen Wiederholungen desselben Befehls erreichte
7,5%** (37,97 / 40,82 / 39,35 tok/s über drei Läufe von Optimized-Quality), und der
Speicher bewegte sich zwischen den Wiederholungen um 5 GB. Behandeln Sie jeden Abstand
unter 8% als nichts.

**Das Tuning war nicht symmetrisch.** llama.cpp bekam explizite Cache-Flags
(`--cache-reuse 256 --slot-prompt-similarity 0.5`, Flash Attention, 131k KV), die die
MLX-Engines nicht bekamen. MTPLX lief mit `--profile turbo`, nicht mit seinem Default. Das
ist ein Vergleich von Konfigurationen, die wir ausrollen würden, nicht von
Werkseinstellungen.

## Das hier reproduzieren

Jede Zahl stammt aus einer zertifizierten Karte, erzeugt von [asiai](https://asiai.dev),
über einen einzigen skriptgesteuerten Pfad mit Solitude-Gates, Identitätsnachweisen des
bedienten Modells und thermischer Abtastung. Rohexporte verfügbar.

Wenn Sie eine Sache mitnehmen: **Prüfen Sie, ob Ihre Engine Multi-Token-Prediction hat und
ob sie eingeschaltet ist.**
