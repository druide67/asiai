# Qwen-AgentWorld-35B auf Apple Silicon: verdient es einen Platz in deiner Agent-Loop?

> Ein Evaluations-Brief für Leute, die lokale Modelle betreiben und autonome Agenten bauen.
> **Was es ist**: ein *Sprach-Weltmodell* — es sagt vorher, was ein Terminal
> nach einer Aktion ausgeben würde, es handelt nicht. **Was läuft**: MLX, oder llama.cpp/Metal
> mit einem einzeiligen Metadaten-Override (ein einfaches GGUF lädt ohne ihn nicht); keine
> offizielle MLX-Build. **Sein einziges von uns gemessenes Alleinstellungsmerkmal**:
> es hält die Simulator-Rolle über mehrschrittige Sequenzen hinweg, wo ein Generalist abdriftet.
> **Seine Kosten**: starkes Over-Reasoning — deckelbar. Die Zahlen sind small-N und richtungsweisend,
> jede mit ihrer Stichprobengröße versehen; die Benchmark-Werte der Autoren sind als Behauptungen gekennzeichnet.
>
> Gemessen mit `asiai` auf einem M5 Max, MLX 4-bit, jeweils eine Engine zur Zeit, 2026-06.
> Korrekturen willkommen über [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

!!! tip "Wann einsetzen / wann nicht"
    **Setze es ein als** Umgebungssimulator für günstige Agent-Rollouts, als Mock für
    Tool-/Terminal-Ausgaben, oder als Trajektorien-Verifizierer anstelle eines LLM-as-judge
    (*der Verifizierer-Anwendungsfall ist hier ungetestet — siehe §6*). Es hält sich auch als
    einfacher 35B-Generalist, wenn du es als Assistent promptest.

    **Setze es nicht ein als** deinen täglichen Assistenten: die Autoren liefern keinen
    Chat-/Code-Nutzungspfad, und es trägt eine steile Over-Reasoning-Steuer (deckelbar, siehe §5). Und warte
    nicht auf die 397B-Variante, die "GPT-5.4 schlägt" — sie ist **nicht herunterladbar**
    (HF liefert 401 trotz der Apache-2.0-Ankündigung).

## 1. Lauffähigkeit & Reproduktion (lies das zuerst)

Wenn es auf deiner Maschine nicht läuft, ist alles andere egal. Verdikt, unverblümt:

- **Zwei Pfade funktionieren heute; keiner ist schlüsselfertig.** Es gibt **keine offizielle MLX-Build** —
  wir haben eine Community-MLX-Konvertierung verwendet, und das ist der Pfad, auf dem wir gemessen haben. Das GGUF
  **lädt ebenfalls** auf llama.cpp / Metal, aber nicht out of the box: so wie es ist, scheitert es mit
  `missing tensor 'blk.40.attn_norm.weight'` (Build 9780, erneut bestätigt 2026-06-25).
  Die Ursache ist ein Off-by-one des Konverters, **keine fehlenden Gewichte** — das GGUF deklariert
  `block_count=41` (eine zusätzliche MTP-Schicht an Index 40), liefert aber nur die 40 realen
  Schichten 0–39 aus, sodass llama.cpp nach einer Schicht fragt, die nie existieren sollte. Überschreibe
  die Metadaten beim Laden und es lädt *und generiert*:
  `--override-kv qwen35moe.block_count=int:40 --override-kv qwen35moe.nextn_predict_layers=int:0`.
  Ollama und LM Studio umhüllen llama.cpp, geben aber `--override-kv` nicht zuverlässig frei, also
  behandle diese beiden als ungetestet. Offizielle Server-Bereitstellung ist vLLM / SGLang / Transformers.
- **Ein Quant, das lädt, ist kein Beweis, dass es eine korrekte lange Chain-of-Thought ausgibt** —
  validiere die Generierung, nicht nur das Laden.

Reproduktions-Setup:

| | Repo (Hugging Face) | Größe |
|---|---|---|
| AgentWorld (Spezialist) | `jedisct1/Qwen-AgentWorld-35B-A3B-oQ4-MLX` | ~20 GB |
| Qwen3.6 (Generalist-Baseline) | `mlx-community/Qwen3.6-35B-A3B-4bit` | ~19 GB |

`mlx-lm` 0.31.3 · M5 Max 128 GB · Sampling temp 0.6 / top-p 0.95 / top-k 20 · jeweils ein Modell geladen.

!!! warning "Das Token-Budget ist eine erstklassige Setup-Variable"
    AgentWorld emittiert einen sehr langen Reasoning-Trace. Bei `max_tokens=4096` wird seine Ausgabe
    **vor der Antwort abgeschnitten** und als Fehlschlag gewertet — ein falscher Fehlschlag. Es braucht
    **8192–12288** Reasoning-Tokens, um bei manchen trivialen Fällen fertigzuwerden. Wer
    bei niedrigem Budget erneut läuft, bekommt schlechter aussehende Zahlen für AgentWorld, die
    Harness-Artefakte sind, keine Modellfehler.

**RAM- / Kontext-Passung**: Gewichte ~20 GB; Spitze ~27 GB bei 64K Kontext auf einem 128-GB-Mac;
der KV-Cache wächst von 4K bis 64K nur um ~5 GB (eine Eigenschaft der geteilten hybriden
Architektur). Ein 64-GB-Mac führt es bei reduziertem Kontext bequem aus; 36–48 GB ist
knapp, aber bei 4K–32K machbar.

## 2. Was es ist, und wie die Autoren es positionieren

Ein **Sprach-Weltmodell**: gegeben einen Zustand und eine Aktion (ein typisierter Befehl),
sagt es die nächste Beobachtung vorher (was das Terminal zurückgibt) über eine lange
Chain-of-Thought. Sieben digitale Domänen (MCP, Search, Terminal, SWE, Android, Web,
OS). Es ist darauf trainiert, *die Umgebung zu sein*, nicht in ihr zu handeln.

Die Autoren liefern es **als Weltmodell, nicht als Assistenten**: die System-Prompts sind
Simulations-Prompts, und es gibt keinen dokumentierten Chat-/Code-Nutzungspfad. Eine faire
Sorge ist also, dass es, als Assistent verwendet, eine Konsolen-Ausgabe simulieren würde, statt zu
antworten. Unser Test nuanciert das (§4): mit einem Standard-Assistenten-Prompt codet und
schließt es auf Augenhöhe mit dem Generalisten. **Das Verhalten wird durch den Prompt entschieden,
nicht durch eine verlorene Fähigkeit.**

!!! note "Zum Wort *world-model*"
    Der häufigste Community-Einwand ist terminologisch: dies ist ein
    autoregressives LLM, das Next-Text-State-Vorhersage betreibt, kein nicht-autoregressives /
    energiebasiertes Weltmodell im Sinne von LeCun. Gut zu wissen, bevor der Name eine
    Erwartung setzt, die zu erfüllen das Modell nicht beansprucht.

Verifizierte Spezifikationen (HF Model Card, im Klartext):

| | |
|---|---|
| Parameter | **34.66 B** gesamt · ~3 B aktiv (MoE) |
| Architektur | `qwen3_5_moe`, hybrid **Attention + Gated-DeltaNet** |
| Experten | 256 (8 geroutet + 1 geteilt) |
| Kontext | bis zu **256K** Tokens |
| Lizenz | **Apache-2.0** (~65 GB in BF16) |

## 3. Das Alleinstellungsmerkmal: mehrschrittige Rollentreue

Dies ist das eine neue, verteidigbare Ergebnis — und genau das, was der eigene Benchmark der Autoren
nie misst (er ist ausschließlich einschrittig). Der Test: verkette Befehle, die
Zustand aufbauen (ein Verzeichnis erstellen, hineingehen, eine Datei schreiben, sie zurücklesen) und lasse
das Modell bei jedem Schritt die exakte Terminal-Ausgabe vorhersagen.

Fasse es als **Zuverlässigkeits**-Eigenschaft auf — Format-/Rollendisziplin — **nicht** als
Verständnisvorteil. Qwen3.6 versteht das Terminal vollkommen gut (es verfolgt das
Arbeitsverzeichnis, zählt die richtige Zeilenanzahl); der Unterschied ist, dass es manchmal
*aus der Rolle fällt*.

| Test | AgentWorld | Qwen3.6 | Anmerkung |
|---|---|---|---|
| Plausible Ausgabe (`ls`, `git`, `ps`) — N=3 | 9/9 | 9/9 | Gleichstand |
| Sequenz A — 6 Schritte, verankert (4 Läufe) | 0 Rollenbrüche / 24 Schritte | intermittierend | Rollenhaltung |
| Sequenz B — 8 Schritte, verankert (3 Läufe) | 0 Rollenbrüche / 24 Schritte | intermittierend | Rollenhaltung |
| Closed-Loop (speist sich selbst) — N=2 | 6/6 ×2 | intermittierend | Rollenhaltung |

**Ehrliche Lesart**: AgentWorld brach die Rolle in **0 von 48 beobachteten Schritten** über zwei
Sequenzen und vier Läufe. Qwen3.6 bricht die Rolle intermittierend — seine verankerten Läufe
schwankten über Wiederholungen hinweg von 0/6 → 6/6 (N=2), das ist also **richtungsweisend, keine Rate**. Wenn
es scheitert, **gibt es das Aktions-JSON wieder**, statt die Ausgabe zu simulieren:

```text
$ cat log.txt              # log.txt was just deleted → env must return an error

AgentWorld (in role):
  root@host:/home/user# cat log.txt
  cat: log.txt: No such file or directory
  root@host:/home/user#

Qwen3.6 (out of role, ~1 run in 2 here):
  [{"keystrokes": "cat log.txt\n", "duration": 0.1}]    # echoes the input command
                                                        # instead of the output
```

Die korrekte Antwort ist in Qwen3.6s Ausgabe oft vorhanden — es ist ein **Format-/Rollen**-Fehler,
kein Missverständnis. Für eine Loop, in der jeder Schritt vom nächsten maschinenlesbar sein muss,
vergiftet ein einziger Rollenbruch die Kette, was AgentWorld vermeidet.

!!! note "Mess-Vorbehalte (offengelegt)"
    Die byte-genaue Bewertung auf der Befehls-Echo-Zeile ist streng, und unsere Sequenz-D-vs-
    Sequenz-E-Fixtures waren inkonsistent darüber, ob eine `cd`-Beobachtung das
    Echo enthält — die Rollentreue-Metrik hat also eine bekannte Falte. Die Richtung ist
    über vier Dateien hinweg robust; die genaue Lücke nicht.

## 4. Generalisten-Fähigkeit: die Basis ist nicht degradiert

Die Frage des Eigentümers (hat das Weltmodell-Fine-Tuning das Basis-LLM kaputtgemacht?) bekommt einen
nüchternen Abschnitt, nicht die Schlagzeile. Kurze Antwort: nein — N=3, richtungsweisend.

| Aufgabe | AgentWorld | Qwen3.6 | |
|---|---|---|---|
| Reasoning (5 verifizierbare Rätsel inkl. der Strawberry-'r'-Falle) | 15/15 | 15/15 | Gleichstand |
| Code-Generierung (4 Funktionen, **gegen Unit-Tests ausgeführt**) | 12/12 | 12/12 | Gleichstand |

Mit einem Assistenten-Prompt (nicht dem Simulator-Prompt) ausgeführt, schreibt AgentWorld korrekten
Code und schließt korrekt, auf Augenhöhe mit dem Generalisten. Es "entgleist" nicht — es
ist ein kompetenter Generalist, der zufällig over-reasoned.

## 5. Die Kosten: eine Over-Reasoning-Steuer — und das Heilmittel

Stufe das von einer Fußnote zu einem Adoptions-Gate hoch, denn für einen Per-Step-Verifizierer ist es
die entscheidende Zahl — aber es hat einen Fix.

Gemessen an deterministischen Terminal-Fällen (N=2 pro Fall):

| Modus | AgentWorld | Qwen3.6 |
|---|---|---|
| Reasoning **an** (Standard-Simulator-Modus) | Median **1140 tok/pred**, max 2558 · ~14 s · 8/8 exakt | 504 tok · ~4.5 s · 8/8 |
| Reasoning **aus** (`enable_thinking=false`) | **45 tok/pred · ~0.5 s · 8/8 exakt** | 45 tok · ~0.4 s · 8/8 |

AgentWorld emittiert ~2.3× mehr Tokens als der Generalist, und bei einem trivialen `cd ; pwd`
lief sein Reasoning **in 2 von 3 Läufen über 8192 Tokens hinaus**. Die finale Antwort ist korrekt —
das ist eine Latenz-/Compute-Steuer pro Schritt, kein Korrektheitsdefekt.

!!! tip "Das Heilmittel: deckle es"
    Reasoning für die Simulator-Rolle **auszuschalten** senkt die Tokens um ~25× und die Latenz
    um ~28× **ohne Verlust an byte-genauer Treue** in deterministischen Fällen (weiterhin 8/8).
    Für einen Per-Step-Verifizierer oder Mock führe es mit `enable_thinking=false` und einer
    `max_tokens`-Obergrenze aus. **Vorbehalt**: dies ist nur in deterministischen Fällen getestet —
    bei Ausgaben, wo das Reasoning tatsächlich hilft (mehrdeutiger Zustand, komplexer
    Inhalt), kann Reasoning-aus Treue kosten. Hier ungetestet.

## 6. Performance (Einzellauf, indikativ ★)

Gleiche Familie, gleiche Architektur, also liegen die Profile nahe beieinander. Lies diese als Trends.

| Maß | AgentWorld | Qwen3.6 | Lesart |
|---|---|---|---|
| Time to first token ★ | ~360 ms | ~510 ms | AW vorn |
| Decode-Durchsatz ★ | ~110 t/s | ~117 t/s | ~7% langsamer |
| Decode bei 64K Kontext | ~132 t/s | ~160 t/s | ~73% gehalten |
| Speicher 4K → 64K | +5 GB | +5 GB | hybride Arch, nicht AW-spezifisch |
| Kontext-Cache (13K-Token-Präfix-Wiederverwendung) | ~×21 | ~×23 | **MLX-Eigenschaft**, nicht das Modell |

Die ~7%-Decode-Lücke liegt höchstwahrscheinlich am 4-bit-Rezept (AgentWorld schützt seine
Linear-Attention-Projektion in 6-bit; Qwen3.6 schützt das MoE-Gate in 8-bit), bei
ungleichen Ausgabelängen — ein Confounder, kein Modellnachteil. Prompt-Caching ist ein
mlx-lm-Feature, identisch auf beiden Modellen; sein ~20×-Gewinn skaliert mit der Länge des
gecachten Präfixes, es ist keine Eigenschaft von AgentWorld.

**Ungetestet, aber von hohem Wert (der #2-Anwendungsfall der Community)**: die Next-State-
Vorhersage als *Trajektorien-Verifizierer* zu nutzen — wenn die reale Umgebung von der
Vorhersage abweicht, signalisiert das einen vom Pfad abgekommenen Agenten. Wir haben sein False-Positive- /
False-Negative-Verhalten nicht gemessen. Offene Frage.

## 7. Was die Autoren behaupten

!!! quote "Autoren-Benchmark — eine Behauptung, keine Messung"
    Auf ihrem eigenen Benchmark (AgentWorldBench) erzielt AgentWorld-35B **56.4**, gleichauf
    mit Claude Sonnet 4.6 (56.0). Die Gewinne schreiben sie der Spezialisierung zu, per
    Ablation gegen die **Basis Qwen3.5** (selbstberichtet, kein Head-to-Head gegen
    Qwen3.6): **+21.9** Tool-Use (MCP), **+18.1** Software Engineering, **+10.2**
    Terminal. These: *Weltmodell-Spezialisierung schlägt generationellen Fortschritt* —
    der Generalist Qwen3.6 erzielt **unterhalb** der Basis (42.9 vs 47.7) bei der Simulations-
    treue, weil er darauf abgestimmt ist, zu *handeln*, nicht den Zustand zu *vorherzusagen*.

    Diese Werte stammen aus einem Single-Source-, hauseigenen Benchmark, der von einem LLM-
    Judge bewertet wurde, an einem bei Veröffentlichung weniger als 48 h alten Modell — **keine Drittpartei-
    Replikation**. Die Spitze ihrer Tabelle liegt unter einem Judge innerhalb von ~2 Punkten, also
    ist die Nahe-an-der-Spitze-Reihenfolge innerhalb des Rauschens; die 397B-"schlägt-GPT-5.4"-Marge ist +0.46
    (Rauschen), und diese Variante ist nicht öffentlich (HF 401) trotz der Apache-2.0-
    Ankündigung.

Unser Mehrschritt-Ergebnis (§3) liegt auf einer *anderen, nicht replizierten Metrik* als ihr
Einschritt-Bench; es weist in dieselbe Richtung (Qwen3.6 schwächer bei der Simulation), aber
das ist Thesen-Konvergenz, keine Bestätigung.

## 8. Wie ich es einbinden würde

- **Prompt**: verwende den offiziellen Terminal-**Simulations**-System-Prompt, um es als
  Umgebung zu betreiben; verwende einen einfachen Assistenten-Prompt nur, wenn du Generalisten-Ausgabe
  willst. Die zwei Modi sind verschiedene Jobs.
- **Kostenkontrolle**: `enable_thinking=false` + eine `max_tokens`-Obergrenze für die
  Simulator-Rolle (§5). Mit eingeschaltetem Reasoning budgetiere ~1000–2500 Tokens/Schritt.
- **Closed Loop**: speise die eigenen Vorhersagen des Modells zurück, aber verankere an der realen
  Umgebung, wann immer du sie hast; erwarte, dass Format-Strenge wichtig ist (die Echo-Zeile).
- **Footprint**: ~20 GB Gewichte, ~27 GB Spitze bei 64K.
- **Die Build-vs-Adopt-Frage**: ist "verlässt nie die Rolle" dem Weltmodell-
  Training inhärent, oder könnte ein Generalist + grammatikbeschränktes Decoding den
  Großteil der Lücke schließen? Wir haben die Constrained-Generalist-Alternative nicht getestet — wäge sie
  ab, bevor du ein dediziertes Modell adoptierst.

## Grenzen dieses Benchs

- **Kleine Stichproben** (N=1–5, keine Standardabweichung). Jede numerische Lücke ist ein Trend,
  kein statistisches Ergebnis.
- **Eine Domäne** für die zwei Schlüsselergebnisse (Terminal-Sequenzen). Rollenhaltung "in einer Loop"
  bleibt anderswo zu bestätigen.
- **Quantisierung nicht isoliert**: die beiden 4-bit-Rezepte unterscheiden sich leicht; die Decode-
  Lücke ist wahrscheinlich daran gebunden, aber das ist hier nicht bewiesen.
- **Noch nicht getestet**: zufällige/komplexe Szenarien, eine zweite Domäne, ein Dreiweg-Vergleich gegen
  die Basis Qwen3.5, um den genauen Effekt des Fine-Tunings zu isolieren, und der Trajektorien-Verifizierer-
  Anwendungsfall.
- **Nur das 35B ist öffentlich.** Die 397B-Variante ist nicht herunterladbar.

---

*Quellen: arXiv 2606.24597 · [Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) (Apache-2.0). Ergebnisse vor Veröffentlichung intern auf Bias gegengeprüft. ★ = einzelne, indikative Messung.*
