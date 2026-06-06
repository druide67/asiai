---
description: Dev-Qualitäts- und Mehrsprachen-Retention-Benchmark-Ergebnisse auf Apple Silicon — Tool-Call-Zuverlässigkeit (der JSON-Argument-Truncation- / Empty-Object-Bug), agentische Fehlerbehebung, Thinking-Disziplin und Sprachretention. Deterministisch, kein LLM-Judge für das Kernsignal nötig. Eine lebende Ergebnisseite.
---

# Dev-Qualitäts- & Sprach-Benchmarks

Throughput ist nicht gleich Qualität. Ein Modell kann schnell dekodieren und trotzdem
für agentisches Coding unbrauchbar sein — es kürzt Tool-Call-Argumente ab, dreht bei
Fehlern in Schleifen, oder sein Finetune hat klammheimlich eine andere Sprache kaputt
gemacht. Diese Seite berichtet über reale `asiai bench --code`- und
`asiai bench --language`-Ergebnisse: **deterministische** Signale (kein LLM-Judge für
den Kern nötig), die messen, ob ein Modell tatsächlich funktioniert — nicht, wie schnell
es Tokens ausspuckt.

> **Lebendes Dokument.** Die Zahlen werden aktualisiert, sobald sich Modellrevisionen,
> Engines und Templates ändern. Jeder Block nennt die exakte Modelldatei und die
> Serving-Konfiguration, sodass ein Ergebnis reproduzierbar ist.

## Was gemessen wird

`asiai bench --code` (deterministisch, kein Judge):

- **tool-call** — eine 8-Turn-agentische Datei-Editing-Session unter sich
  akkumulierendem Kontext. Bewertet Tool-Call-Emission, JSON-Validität,
  Nicht-Truncation, korrektes Tool, Schema-Konformität und den **Empty-Object-Bug**:
  die `|items`-Template-Truncation, die ein `edit_file.edits`-Array auf `{}` / `[]`
  zusammenfallen lässt.
- **tool-call-stress** — dasselbe, härter: tieferer Kontext, 8–10-elementige
  Edit-Arrays, JSON-Escaping-Druck (Zeilenumbrüche, Anführungszeichen, Backslashes,
  Unicode). Wird genutzt, um Modelle zu unterscheiden, die die Baseline mit Bravour
  bestehen.
- **recovery** — ein synthetischer Tool-Fehler wird mitten in der Session injiziert;
  bewertet eine korrigierende Aktion vs. eine festgefahrene Schleife (das erneute
  Absetzen des fehlschlagenden Calls).
- **thinking** — Thinking-Mode-Disziplin: kein `<think>`-Leak in den Content,
  nicht-leerer Output bei knappem Budget und respektiertes `enable_thinking=false`.
- **coding** / **coding-hard** *(optionaler Judge)* — Multi-Turn-Coding-Aufgaben,
  von einem LLM-Judge unter `--judge-url` (beliebiger OpenAI-kompatibler Endpoint) mit
  1–5 bewertet.

`asiai bench --instruct` (deterministisches Instruction-Following):

- **verifiable** — IFEval-artige Single-Turn-Prompts mit programmatisch überprüfbaren
  Anweisungen (Wort-/Satz-/Abschnitts-Zählungen, Keywords, JSON-only, Groß-/Kleinschreibung,
  keine Kommas, Schlussphrase, Titel in `<<>>`, Sprache …). Berichtet als
  strict/loose-Accuracy auf Prompt-Ebene und Instruction-Ebene — das Format des
  öffentlichen Leaderboards. asiai-native Reimplementierung des IFEval-Paradigmas (Zhou
  et al. 2023); es wird kein IFEval-Code und keine -Daten mitgeliefert.
- **research-brief** — eine agentische Aufgabe: mehrere Themen per Tools recherchieren,
  dann ein mehrteiliges Briefing schreiben, dann **zuletzt** eine sekundäre Tool-Aktion
  (Speichern). Produziert das Modell das primäre Briefing, oder erledigt es die Tool-Arbeit
  und liefert nur die Bestätigung des sekundären Schritts zurück? Ein Modell kann die
  Tool-Call-Zuverlässigkeit mit Bravour bestehen und trotzdem das eigentliche
  Deliverable überspringen — deterministisch bewertet durch die Prüfung, ob die geforderten
  Abschnitte nach den Tool-Turns erscheinen. **order-control** vertauscht die Reihenfolge
  (sekundär zuerst) als Diagnostik.
- **loop-search** — eine Mehrdeutigkeits-Suchfalle: ein tiefes Warmup über klare
  Themen, dann eine Zieltatsache, die `web_search` nie bestätigen kann (semantische
  Umformulierungen der Anfrage fallen auf eine Antwort zusammen). Bewertet, ob das
  Modell die Mehrdeutigkeit akzeptiert und liefert (nüchtern) oder äquivalente
  Anfragen erneut absetzt, bis ein No-Progress-Cap es stoppt (perfektionistisch),
  plus ein Signal für den Kollaps der Output-Tokens. Zwei Modi (`short` Resultat
  unter 1 KB / `unconfirmable` plausible-aber-fehlende-Tatsache). Dies ist der
  Fehlermodus, den Single-Turn-IFEval und research-brief nicht zutage fördern.

`asiai bench --language <code>` (deterministisch, 8 Sprachen):

- **adherence** — bleibt das Modell in der Zielsprache? (Verhältnis von Zielsprach- zu
  englischen Funktionswörtern bei lateinischen Schriften; Verhältnis der
  Zielschrift-Zeichen bei ja/ko/zh).
- **diacritics** — Trap-Prompts, deren korrekte Antwort bestimmte akzentuierte Tokens
  enthalten muss (`café`, `préféré`); eine ASCII-bereinigte Antwort fällt durch.

Alle drei Modi sind JSON-only und vergleichen Modelle, indem der Output gediffed wird.

## Durchgerechnetes Beispiel — Qwen3.6-35B-A3B vs. Qwopus3.6-35B-A3B vs. Qwen3.6-27B Dense

Ein Finetune (`Qwopus3.6`, ein Opus-distilliertes Finetune des `Qwen3.6-35B-A3B` MoE)
vs. seine Basis, vs. ein Dense-Modell halber Größe. Dasselbe llama.cpp, **dasselbe
Chat-Template konstant gehalten** (nur die Modelldatei getauscht), Thinking deaktiviert,
3 Wiederholungen. Apple Silicon M5 Max, High Power Mode.

### Tool-Call-Zuverlässigkeit

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **Das Basis-35B-MoE hat einen residualen Tool-Call-Defekt, den der Template-Fix nicht
  vollständig schließt.** Es lässt `edit_file.edits` 3/3 in den Empty-Object-Bug
  zusammenfallen bei einem Turn mit tiefem Kontext — und das bei **beiden** Quants Q4 und Q5
  (es ist also ein Generierungsverhalten, keine Quantisierung). Das Community-Template
  `froggeric`, das den `|items`-Bug bei einfachen Calls behebt, rettet das Basis-MoE
  tief im Kontext nicht.
- **Das Opus-distillierte Finetune repariert ihn vollständig** — 0 Bugs, 100% clean —
  und zwar bei einem *niedrigeren* Quant (Q4 vs. Q5), was den Sieg umso deutlicher macht.
- **Unter Stress ist das Finetune der robustere Agent als das Dense-27B**: das 27B
  bricht ein (3 Empty-Object-Bugs in der härteren Suite), während das Finetune bei 0
  bleibt. Auf der Baseline liegen sie gleichauf; die Stress-Suite trennt sie.

### Code-Korrektheit (LLM-bewertete harte Aufgaben)

Bei zwei kniffligeren Multi-Turn-Coding-Aufgaben **teilen sie sich auf**: bei einem
Sliding-Window-Rate-Limiter behandeln beide die Grenz-/Eviction-Edge-Cases; bei einem
Expression-Evaluator bekommt das **Dense-27B die Operator-Präzedenz richtig hin**
(`-2**2 == -4`, unäres Minus als korrekter Operator), während das **Finetune das nicht
tut** (es faltet das unäre Minus in die Zahl → `4.0`). Tool-Call-Robustheit und
algorithmische Korrektheit sind *verschiedene* Achsen — miss beide.

### Sprachretention

`--language fr` auf dem Finetune und seiner Basis, gleicher Quant:

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**Null Französisch-Regression.** Das Coding-orientierte Finetune hat das Französisch des
Basismodells intakt gehalten (Adherence, Diakritika, kein ASCII-Stripping) — ein
aufgabenspezifisches Finetune hat *nicht* eine andere Sprache gekostet, was zu
verifizieren ist, anstatt es anzunehmen.

### Perfektionistische Recherche-Schleife (loop-search)

`research-brief` sättigt für jedes Modell hier bei 100%, diskriminiert also nicht
die *perfektionistische Schleife*, die reale Agenten zerstört. Das `loop-search`-
Szenario tut es. Über einen Sweep von Dense-27B- und MoE-35B-A3B-Konfigurationen (M5,
llama.cpp b9430, Thinking on/off, beide Mehrdeutigkeitsmodi):

- Das **35B-A3B MoE dreht in Schleifen** — es setzt zu einer nicht bestätigbaren
  Tatsache immer wieder semantisch äquivalente Suchen ab, bis ein
  No-Progress-Guardrail es stoppt, anstatt die Unsicherheit zu akzeptieren und zu
  liefern. Es tut dies in **sowohl Q4 als auch Q8** (architektonisch, kein
  Quant-Artefakt), für die Basis und das Opus-distillierte Finetune gleichermaßen.
- Das **Dense-27B dreht nie in Schleifen** (Q4 / Q5 / Q8): es akzeptiert das
  mehrdeutige Resultat und schreibt das Briefing.

Für ein agentisches Harness wie den Hermes Agent von NousResearch ist dies das
entscheidende Signal: das schleifenresistente Dense-Modell ist die sicherere
Hauptwahl, selbst wenn ein schnelleres MoE existiert — Throughput kauft nichts,
wenn der Agent bei einem mehrdeutigen Schritt in eine Spirale gerät. Es ist auch
die umgekehrte Lektion des Tool-Call-Ergebnisses oben (wo das MoE-Finetune der
*robustere* Agent war): **Eignung ist pro Fehlermodus, also miss mehrere.**

## So liest du das

- **Verdict-first, nicht Speed-first.** Dies sind Korrektheits-/Zuverlässigkeitssignale.
  Für Throughput siehe die [Agentic-Benchmarks](agentic-benchmarks.md).
- **Deterministischer Kern, optionaler Judge.** tool-call / recovery / thinking /
  adherence / diacritics brauchen keinen LLM-Judge — sie sind reproduzierbar. Die
  `coding`/`fluency`-Bewertungen sind LLM-bewertet (subjektiv, optional).
- **Vergleiche innerhalb einer kontrollierten Änderung.** Das Beispiel hält das Template
  konstant und variiert nur das Modell, sodass ein Unterschied der des Modells ist, nicht
  der des Harness.

## Methodik & Vorbehalte

- `asiai bench --code` / `--language`, Thinking deaktiviert
  (`chat_template_kwargs.enable_thinking=false`), eine Engine zur Zeit resident.
- **Der Quant unterscheidet sich über das Beispiel hinweg** (das Finetune Q4 vs. die
  Qwen-Modelle Q5): der headline Empty-Object-Bug ist Template-/Generierungs-getrieben
  und wurde bei **beiden** Quants für die Basis bestätigt, der Quant erklärt die Lücke
  also nicht — und das Finetune gewinnt vom niedrigeren Quant aus.
- **Der Code-Qualitäts-Judge ist hier nicht strikt blind** (ein Frontier-Modell hat die
  Transkripte inhaltlich gelesen); die deterministischen tool-call/stress-Zahlen sind
  objektiv.
- **Recovery ist gewichtsensitiv**, kein sauberes modellübergreifendes Signal — die
  Headline ist die tool-call/empty-object-Zuverlässigkeit, die über Wiederholungen hinweg
  stabil ist.

Siehe auch: [Agentic-Benchmarks](agentic-benchmarks.md) ·
[Benchmark-Methodik](methodology.md) · [Metrik-Spezifikation](metrics-spec.md).
