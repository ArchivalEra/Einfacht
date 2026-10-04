# Einfacht

**Das Gedächtnis eines Agenten sollte keine Prosa sein — es sollte eine überprüfbare Aussage sein.**

**Sprachen:** [English](README.md) (Standard) · [简体中文](README.zh.md) · **Deutsch** (diese Datei)

> ehemals `zcode-reflect`

Ein **Antihalluzinations-Faktsystem** für agent-getriebene Repos. Es trainiert keine Modelle,
macht kein Retrieval, speichert keine Embeddings — es tut genau eines: Es macht jedes
„so ist es gerade" **durch einen Befehl beweisbar**, und es **erwischt den Moment automatisch**,
in dem die Aussage widerlegt wird.

```
ein Satz, der sich als Fakt ausgibt  ──▶  entweder einen Produzenten-Befehl daranhängen (re-laufbar)
                                          oder als Inferenz markieren (und das Experiment benennen, das sie klärt)
                                          oder ins Retraktionsledger stellen (mit Wiederauftauch-Erkennung)
                                          keiner der drei Fälle ⇒ ein Gate wird rot
```

## Warum es das braucht

Modelle erzeugen **sicher aussehende Fehler**. „Bitte sei sorgfältiger" repariert das nicht,
denn die Fehlerform ist nicht Unsinn — sie ist **altes Abschreiben**:

- eine Zahl, sechsmal per Hand in Docs kopiert; man korrigiert eine Stelle, fünf behaupten
  weiter den alten Wert;
- eine Aussage, die **durch Messung widerlegt** war, steht nach der Korrektur **immer noch im
  selben File** (und hat irgendwo eine Kopie);
- eine Kostenschätzung („in einer Viertelstunde zu finden"), die nie gegen die Artefakte
  abgeglichen wurde — der erste echte Schritt war ein 29-MB-Rebuild;
- ein Guard gegen stilles Überschreiben von Fakten **hat nie einmal gegriffen**, wegen einer
  einzigen undefinierten Variable.

Das sind keine Wissensfehler — das ist **Wissen ohne Lebenszyklus-Behausung**. Einfacht gibt jeder
Art von Aussage ein Zuhause, und jedem Zuhause eine Prüfung, **die rot werden kann**.

## Vier Disziplinen

1. **Zahlen und Verhalten kommen nur aus Messung**, und der erneute Ausführungsbefehl steht neben
   der Aussage. Ein Satz ohne Ausführungsbefehl ist Geschichte zu lesen — niemals als „jetzt so".
2. **Zahlen werden genau einmal produziert.** Docs zitieren Schlüsselnamen; Hand-Kopie von Ziffern ist verboten.
3. **Kompiliert ≠ funktioniert.** Laufzeit-Aussagen müssen in der echten Umgebung getestet werden;
   ein grüner Build ist keine Abnahme.
4. **Aussagen müssen falsifizierbar sein**: jeder neue Vertrag bringt mindestens eine **Umkehr-**
   assertion mit (was fehlschlagen muss, muss fehlschlagen).

Die fünfte Disziplin verhindert, dass die ersten vier zu Parolen verkommen: **jede Aussage hat
einen Lebenszyklus** — gemessen / inferiert / revoziert. Living-State-Docs enthalten nur Messungen;
Inferenzen gehen in Notizen mit dem Zusatz „welches Experiment klärt das"; Widerlegtes ins
Retraktionsledger.

## Sieben Bausteine + die zweite Gruppe aus Octave

| Baustein | Datei | Was es verhindert |
|---|---|---|
| **Gate-Plattform** | `zreflect/gate.py` | still grün werdende Prüfer (Zero-Value-Guard + dreistufiger Selftest) |
| **Fakten-Ledger** | `zreflect/ledger.py` + `facts.py` | hand-kopierte oder still überschriebene Zahlen |
| **Fakten-Gate** | `zreflect/check_facts.py` | Doc-Block ungleich Ledger, nackte Zahlen im Text, Zitate nicht existierender Schlüssel |
| **Replay-Gate** | `zreflect/check_facts_replay.py` | „re-laufbar" war eine Aussage **ohne Vollstrecker** (issue #2 ①): jetzt wird jedes `cmd` im Ledger wörtlich ausgeführt (stdout muss dem Wert gleichen; kaputtes Kommando / Timeout / fehlendes cmd werden gemeldet; Einträge, die Build-Artefakte brauchen, steigen mit `replay: false` explizit aus — und können trotzdem eine billige **Zeugenschaft** tragen, `witness` + `witness_expect`, issue #5: die Herkunft wird bei jedem Commit gefahren; oder eine **Kalibrierungsprobe**, `calibrate` + `calibrate_expect`, issue #6 ①: das Instrument läuft bei jedem Commit gegen eine bekannt-positive Probe) |
| **Instrumenten-Lebenszyklus** (einsteckbar) | `zreflect/check_instruments.py` | das Replay-Gate fängt *tote* Kommandos (rc≠0), aber nicht **stille Instrumentenverfälschung**: ein Kommando, das erfolgreich ist, einen stabilen Wert liefert und ewig besteht, während es das Falsche mißt (`grep -c X` erfolgreich mit 0, wenn das Tool die Mnemonic X nicht kennt). Einsteckbar: beide Knäufe ungesetzt ⇒ sagt laut, dass es aus ist, exit 0. `REFLECT_INSTRUMENT_DAYS=N` schaltet die Konstanten-Erkennung (`first_seen` älter als N Tage ⇒ „mißt dieses cmd wirklich, oder liefert es immer dieselbe Zahl?"); `REFLECT_INSTRUMENTS=instruments.json` registriert widerlegte **Meßmethoden** (`{"methods": [{text, why, fixed_in}]}`) — jedes Ledger-`cmd` mit einem solchen Fragment wird gemeldet |
| **Deklarative Invarianten** (einsteckbar) | `zreflect/check_invariants.py` | „Datei X muß/ darf Fragment Y nicht enthalten" als **Daten**, nicht Code (`REFLECT_INVARIANTS=invariants.json`, Schema `{"checks": [{path, must_contain?, must_not_contain?, why}]}`) — generische, nur-lesende Engine, kein Build/Netz ⇒ pre-commit-tauglich; `why` ist Pflicht (eine Prüfung, die keiner zu löschen wagt, wird zum Zombie). Einsteckbar: ungesetzt ⇒ sagt laut, dass es aus ist, exit 0. **Grep-Stufe**: ein Fragment im Kommentar zählt auch als „vorhanden" — es beweist „dieser Text ist noch da", nicht „der Code benutzt es wirklich"; die Stärke einer deklarativen Prüfung ist durch die Textform begrenzt, die sie matcht. Stärkere Garantien sind `calibrate` (am Artefakt) oder `witness` (an der Quelle) — orthogonal, nicht mischen: `calibrate` hütet das *Meßinstrument*, Invarianten die **Repository-Dateien selbst** |
| **Retraktions-Ledger** | `zreflect/check_retractions.py` | revozierte Aussagen tauchen **in den via `REFLECT_DOCS` erklärten Living-State-Docs** wieder auf |
| **Fragen-Ledger** | `zreflect/check_questions.py` | offene Fragen, die nur in Prosa leben und keinen ausführbaren Begleicher haben |
| **Trilingual-README-Gate** | `zreflect/check_readme_sync.py` | eine Sprachversion des README ändern und die anderen driften lassen: das Trio muss existieren, einander verlinken — und **mit jedem Push gemeinsam aktualisiert werden** |

### Die zweite Gruppe, migriert aus Octave-Full-Wasm (2026-09-30)

Die erste Gruppe stammt aus jenem Projekt (siehe „Herkunft"); diese zweite Gruppe migriert,
was in dessen `.githooks/` **noch übrig** war — Mechanismen, dort Monate im echten Betrieb.
Behalten wurden nur die Mechanismen; alle Projektdaten wurden abgestreift:

| Baustein | Datei | Was es verhindert |
|---|---|---|
| **Living-State-Extraktion** | `zreflect/living.py` | Gates, die „jetzt so" nicht von „damals so" unterscheiden. Drei Auswege — deklarierte Geschichtsabschnitte, inline Geschichtsmarker, Einträge mit **expliziter Quelle** — plus „strict by default" (auch unnummerierte Abschnitte sind Living State), alles in einer Datei, von allen Prüfern geteilt; die Wortliste wird genau einmal produziert |
| **Stale-Assertion-Gate** | `zreflect/check_stale.py` | sha-Aussagen **ohne Quelle** im Living State; zurückgeschlichene Namen pensionierter Komponenten — dort gemessen: der Build wechselte, der Header zeigte weiter den alten sha, niemandem aufgefallen |
| **Collector-Vertrag** | `zreflect/collect.py` | `measure()` mit **selbständernden Eingängen** (Wanduhr / HEAD-sha ⇒ `--check` konvergiert nie), erfundenen 0en bei fehlendem Lesetritt, teuren Messungen ohne Cache — vier Prinzipien + Helfer zum Wiederverwerten des Maschinenblocks |
| **git hooks** | `reflect-hooks/` | im Repo liegende, **nie ausgeführte** Gates: pre-commit rechnet den Maschinenblock und fährt alle Gates; pre-push weist blöde frische Blöcke ab (**es editiert keine Files und schreibt keine Historie um**). Beide sourcen zuerst ein repo-lokales `reflect.env` (Issue #8) — git exportiert keine Custom-Env an Hooks, die `REFLECT_*`-Knöpfe erreichen sie über diese Datei (Form: `reflect.env.example`) |

Neue Knöpfe: `REFLECT_HISTORY_SECS` (welche nummerierten Abschnitte append-only Geschichte sind,
z. B. `5,9,10`) · `REFLECT_RETIRED` (pensionierte Komponentennamen; leer = diese Regel **sagt laut,
dass sie aus ist**, statt Geprüft-vortäuschen). Seitdem scannt das Retraktions-Gate nur Living
State — alte Werte in Geschichtsabschnitten sind natürlicherweise „damals"; sie freizustellen ist
keine Nachsicht, sondern Schutz vor vernichteten Aufzeichnungen.

Dort gibt es zudem `check-wants.py` (Falsifizierbarkeit von Abnahme-Assertions: ein
Einzelzahlen-Want muss an Zahlengrenzen matchen; gematcht wird mit voller Ausgabe, Kürzung gehört
ausschließlich in die Anzeige) und `check-consistency.py` (dasselbe Wissen an mehreren Stellen
driftet auseinander). Beides gute Vorlagen, **eigene Gates zu schreiben** — beide sind aber an die
Dateiformen jenes Repos geschweißt, also stehen sie hier nur als Regeln, statt als leere Hüllen
mitgereist zu sein.

### 1. Gate-Plattform: Ein Prüfer muss erst beweisen, dass er rot werden kann

Das Gefährliche ist nicht „keine Prüfung". Es ist **eine Prüfung, die still grün wird, wenn ihre
Eingänge verschwinden**:

- drei Sites ohne `VERSION`, und das Konsistenz-Gate meldet „vollständig konsistent";
- eine leere deklarierte Menge, und das Auslieferungs-Audit antwortet `verdict: "ok"`;
- ein Selbsttest-Skript, das `0/0` als „alles bestanden" verbucht.

Darum liefert `gate.py` zwei Dinge:

- `require_nonempty(name, seq)` — der **Zero-Value-Guard**. Wenn die Sammlung nichts einsammelt,
  ist das ein Fehler, niemals „clean".
- `selftest(name, cases)` — jeder `--selftest` muss drei Fallklassen abdecken:
  **normal bleibt still / was feuern muss, feuert / leere Eingabe feuert**. Die mittlere Klasse
  ist entscheidend: Sie beweist, dass der Prüfer **keine Dekoration** ist.

### 2. Fakten-Ledger: zwei Schreib-Guards

Jeder Eintrag in `FACTS.json` ist ein **gemessener Wert** + Ausführungsbefehl + Herkunft. Er wird
in den Maschinenblock des Living-State-Docs gerendert; Prosa darf nur **Schlüsselnamen** zitieren.

Das Neumessen (`facts.py`) hat zwei stille Fehlerformen, je einer Guard:

| Fehlerform | Symptom | Guard |
|---|---|---|
| **drop** | Eingang weg ⇒ Fakten **verschwinden still** | `dropped_keys()` + `--allow-drop` |
| **rephrase** | Eingang geändert (oder falsch gemessen) ⇒ Fakten **werden still eine andere Zahl** | `changed_keys()` + `--accept-changes` |

Die zweite ist tückischer: Wenn Gates nur ein paar shas gegen die Platte abgleichen, ist jeder
andere überschriebene Wert **unwiederbringlich — niemand kann je sehen, dass er sich änderte**.
Darum verweigert `facts.py` das Schreiben per Default, druckt `alt → neu` und wartet darauf, dass
ein Mensch jede Änderung als gemessen bestätigt.

⚠️ Der Werte-Guard vergleicht **nur `value`**, nie `cmd`/`source`/`note` — die beschreiben das
*Wie der Wiederausführung*, und sie zu bearbeiten ist normale Doc-Pflege. Würde man auch für sie
explizites Akzeptieren verlangen, würde der Guard zu Rauschen — pauschal `--accept-changes`ed, und
der Guard wäre tot.

⚠️ **Welche Wertänderungen erwartet sind** (issue #2 ③): jeder Eintrag, der **den lebenden Baum
zählt** (Dateien / Zeilen / Tests), ändert sich mit ganz normaler Entwicklung — eine Datei dazu,
ein Test dazu, fertig. Das ist die häufigste und vorhersagbarste Klasse, und Erstbegegnungen
lesen sie fälschlich als „der Guard heult Wolf — hat er falsch gemessen?" Copy-Paste-Antwort:
jede Änderung als echten Entwicklungszuwachs bestätigen, dann
`python3 zreflect/facts.py --accept-changes`. Den Guard nie schwächen, um den Schritt zu sparen —
kein „Auto-Akzept für Zähler": `--accept-changes` ist das einzige Siegel für „nachgesehen", und
„cmd-Änderungen warnen nicht" ist **die eine begründete Ausnahme** — keine zweite öffnen.

**Selektives Akzeptieren** (issue #3 ①): Wenn ein Re-Mess-Lauf legitim N Werte ändert,
können Sie nur die geprüften übernehmen — `--accept-changes=k1,k2` akzeptiert genau
diese Schlüssel und verweigert weiterhin jede andere Wertänderung. Ein Pauschal-Akzept
einer Batch, die eine tatsächlich kaputte Messung enthält, wäscht sie weiß; die
per-Key-Form hält den Guard scharf, wenn nur ein Teil der Änderung verstanden ist.

Jeder Eintrag trägt außerdem `measured_at` — den Zeitstempel des **Sammelzeitpunkts**
(issue #3 ②). `facts.py` druckt das Alter in Menschenworten („vor 3 Tagen gemessen")
und der Maschinenblock rendert eine „gemessen am"-Spalte mit dem **Rohzeitstempel**
(deterministisch — ein aus der Wanduhr berechnetes Alter würde unter `--check` nie
konvergieren). `check_stale` kann ab konfigurierten Tagen warnen: `REFLECT_STALE_DAYS`
(leer = diese Regel **sagt laut, dass sie aus ist**). Der Stempel zeichnet das *Wann*
auf und ist nie ein Mess-Eingang — ihn als solchen zu füttern, ist genau das, was
`--check` nie konvergieren ließe.

**Die dritte Stufe: Zeugenschaft** (issue #5): `replay: false` hieß
bisher *nie wieder geprüft* — dabei sind teure Fakten die, die eine
billige Nachprüfung am meisten brauchen. Ein 5-Minuten-Benchmark passt
nicht in den pre-commit, aber seine **Herkunft** kann Zeuge sein:
`fact(Wert, cmd, Quelle, replay=False, witness="<billiger, nur-lesender cmd>", witness_expect="<erwarteter stdout>")`.
Der Zeuge wird **bei jedem Commit gefahren** (orthogonal zu `replay`),
mit demselben Bare-Wert-Urteil (`stdout.strip() == witness_expect`);
das Paar muss zusammen gegeben werden — ein halber Zeuge ist eine
kaputte Behauptung, und `ledger.fact()` verweigert sie an Ort und
Stelle. Der Unfall dahinter: ein Artefakt, gebaut von einem
gedrifteten Werkzeug (`-flto` als Rest in einem Build-Skript), passierte
alle billigen Gates und explodierte erst in der Browser-Regression —
ein Zeuge, der die `tool.script_sha256` des Artefakts mit dem sha
des lebenden Skripts vergleicht, hätte es beim Commit gefasst.

**Die vierte Stufe: Instrumenten-Kalibrierung** (issue #6 ①): das
Replay-Gate fängt *tote* Kommandos (rc≠0), aber nicht **stille
Instrumentenverfälschung** — ein Kommando, das erfolgreich ist,
einen stabilen Wert liefert und ewig besteht, während es das Falsche
mißt (`grep -c X` erfolgreich mit 0, wenn das Tool die Mnemonic X
nicht kennt). Jedes `cmd`, das behauptet „das Artefakt enthält X",
sollte eine **bekannt-positive Probe** tragen: `calibrate` (ein
billiges Kommando gegen die Probe) + `calibrate_expect` (der
bekannte Output der Probe). Wie der Zeuge: orthogonal zu `replay`,
wird **bei jedem Commit gefahren**, mit demselben Bare-Wert-Urteil;
das Paar muss zusammen gegeben werden.

**Der Instrumenten-Lebenszyklus ist einsteckbar**
(`check_instruments.py`): Konstanten-Erkennung (`first_seen` —
beim Sammeln gestempelt, von `measure()` unverändert fortgeführt)
schlägt ab `REFLECT_INSTRUMENT_DAYS`: „mißt dieses cmd wirklich,
oder liefert es immer dieselbe Zahl?". Widerlegte
**Meßmethoden** bekommen ein Register wie `retractions.json`
(`REFLECT_INSTRUMENTS=instruments.json`, Schema
`{"methods": [{text, why, fixed_in}]}`): ein Ledger-`cmd` mit
einer widerlegten Methode wird gemeldet — schlechte Meßmethoden
bleiben nicht im Ledger. Beide Knäufe ungesetzt ⇒ das Gate sagt
laut, dass es aus ist, und exit 0; Repos, die es nicht brauchen,
zahlen nichts.

**Auch deklarative Invarianten sind einsteckbar**
(`check_invariants.py`, issue #7): „diese Repo-Datei muß /
darf dieses Fragment nicht enthalten" als **Daten** — ein
JSON-Schema, kein Code: `REFLECT_INVARIANTS=invariants.json`
(`{"checks": [{path, must_contain?, must_not_contain?, why}]}`).
Die Engine ist generisch und nur lesend; `why` ist Pflicht
(eine Prüfung ohne Grund ist ein Zombie, den keiner zu löschen
wagt). Das ist die prüfbare Instanz des `collect.py`-Prinzips 5:
die Invarianten-Datei *ist* die Eingabe-Aufzeichnung, das Gate
*ist* ihre billige Quellen-Invariante. Orthogonal zu `calibrate`,
nicht mischen: `calibrate` hütet das *Meßinstrument*, Invarianten
die **Repository-Dateien selbst**. Grenze, laut gesagt: es ist
**Grep-Stufe** — ein Fragment im Kommentar besteht auch, also
beweist es „dieser Text ist noch da", nicht „der Code benutzt es
wirklich". Die Stärke einer deklarativen Prüfung ist durch die
Textform begrenzt, die sie matcht; alles Stärkere ist `calibrate`
(am Artefakt) oder `witness` (an der Quelle).

### 3. Retraktions-Ledger: Widerlegung hinterlässt eine Spur

`retractions.json` speichert **widerlegte** Aussagen: ein charakteristisches Fragment `text`,
warum sie falsch war (`why`), wie man sie nachprüft (`evidence`), wo die Wahrheit jetzt steht
(`fixed_in`). Das Gate scannt Living-State-Docs: Jede Zeile mit `text` **muss einen
Korrekturmarker tragen** (siehe `HIST_MARK` in `zreflect/living.py` — z. B. retracted /
superseded / deprecated / 已翻案), sonst meldet das Gate.

Ein Zweck: **Eine revozierte Aussage darf nicht still als Gegenwart zurückkehren.**

**Die Scanfläche ist begrenzt** (issue #2 ②): Das Gate scannt exakt die via `REFLECT_DOCS`
erklärten Living-State-Docs. Derselbe Satz taucht in **Quellkommentaren, Configs oder nicht
gelisteten Files** wieder auf ⇒ **unsichtbar**. Das ist eine **dokumentierte Lücke**, kein
„Geprüft". Eine Erweiterung braucht falsch-Positive-Kalibrierung zuerst: Quellkommentare kennen
keinen Begriff „Geschichtsabschnitt", Geschichte in einem Kommentar zu diskutieren ist legitim —
und ein Gate, das Wolf heult, wird pauschal `--accept`ed, was schlimmer ist als kein Gate.

⚠️ Grenze der Inline-Korrekturmarker (in derselben Runde gemessen): Marker existieren dafür,
**einen alten Wert zu zitieren und dabei zu sagen, dass er alt ist** — nicht für die Aussage selbst.
Selbstverneinung in derselben Zeile (z. B. `ZCODE_REFLECT_TYPO — diese Aussage ist retracted.`)
stellt genau diese Zeile frei. Diese Form zu benutzen, um eine *aktuelle* Aussage zu impfen, heißt,
das Gate selbst zu umgehen.

### 4. Fragen-Ledger: Eine ungeklärte Frage ist eine ungefragte Frage

Eine Frage pro Datei in `questions/NN-slug.md`. Im Kopf muss stehen:

```
Settling: <ein ausführbarer Pfad oder Befehl> —— rc=0 ⇒ Schluss A; rc=7 ⇒ Schluss B
```

Regeln:

- `Settling:` muss **ein repo-relativer Pfad** oder ein direkt lauffähiger Befehl sein —
  „siehe irgendeine Notiz" ist kein Begleicher.
- Die zwei Ausgänge müssen **unterschiedliche Exit-Codes / unterscheidbare Ausgabe** liefern,
  sonst falsifiziert der Begleicher nichts.
- **Eine Frage ohne existierenden Begleicher ist legitim** — dann ist das erste Deliverable des
  Tickets, ihn zu bauen. Man schreibt `Settling: none — this ticket's first deliverable`.
  **Nie einen Pfad erfinden.** Ehrliches „none" trägt Information; ein erfundener Pfad macht das
  Gate grün und lügnerisch.
- Nach der Klärung die Schlussfolgerung in die Notizen schreiben, `Status: resolved` setzen.
  **Datei nicht löschen** — Geschichte bleibt.

`check_questions.py` prüft: gültiges `Status:`, vorhandenes `Settling:`, die Existenz der
dateiverweisenden Datei — und **meldet, wenn es nicht eine einzige Frage einsammelte**
(Zero-Value-Guard).

⚠️ **Bekannte Grenze (als Grenze lesen, nicht als Garantie)**: Pfadexistenz wird nur für das
**erste Token** von `Settling:` geprüft (wenn es wie ein Pfad aussieht). Formulierungen wie
`irgendwann scripts/missing.sh laufen lassen` verstecken den Pfad vor der Prüfung. Härte braucht
vorher eine False-Positive-Kalibrierung (Platzhalter wie `<site>/…`, `.sh` in Argumenten — alles
treffergefährdet). Bis ein Fixture kalibriert: lieber eine **dokumentierte Lücke** als ein strenge
Prüfung, die Wolf heult — ein Wolf-geheul-Gate wird pauschal `--accept`ed, und das ist schlimmer
als nichts.

### 5. Gate-Register: entdeckt, nicht gelistet

`gates-selftest.sh` **akzeptiert keine handgeschriebene Liste**. Es scannt `zreflect/check_*.py`,
verlangt von jedem File das `--selftest`-Bekenntnis, und wird rot, wenn eins fehlt.

Die Realität handgeschriebener Register: sie driften immer. Ein Prüfer, beim Hinzufügen nicht
registriert, wird zu „einem Prüfer, den niemand beobachtet" — während das Register selbst grün
bleibt und Alles-okay meldet. Darum läuft es hier umgekehrt: **Registrierung wird entdeckt,
nicht erinnert.**

Jedes `--selftest` endet mit einer maschinenlesbaren Zusammenfassungszeile,
`=== N PASS / M FAIL ===` (neben der Menschenzeile, issue #3 ③) — Runner und CI
greifen ein festes Format, unabhängig vom Namen des Prüfers; `gates-selftest.sh`
wird rot, wenn eine Selbstprüfung sie fehlt.

### 6. Trilinguales README: das Trio bewegt als Ganzes — sonst wird der Push abgewiesen

Das Gesicht dieses Repos existiert in drei Sprachen: `README.md` (Englisch, Standard),
`README.zh.md`, `README.de.md`. Die drei Files sind **eine Aussage in drei Kopien** — eine
ändern und die anderen driften lassen, und „derselbe Satz" ist leise zu zwei einander
widersprechenden Aussagen geworden. Die Disziplin ist bewusst brutal: **Jeder Push muss alle
drei gemeinsam aktualisieren.**

- `reflect-hooks/pre-push` parselt den **Push-Bereich** aus dem git-stdin-Protokoll und weist den
  Push ab, wenn die Änderungsdatei-Menge eines gepushten Ref eine einzige Kopie des Trios vermisst.
- `check_readme_sync.py` (vom Entdeckungsregister automatisch eingesammelt) prüft zusätzlich bei
  jedem Commit und jedem Selftest die **Struktur**: alle Dateien existieren, sind nicht leer, und
  jede enthält alle Namen des Trios — ein kaputter Sprachumschalter ist ein kaputter Eingang.
- CI (`.github/workflows/readme-sync.yml`) fährt **dieselbe Prüfung** — weil ein lokaler Hook
  `git push --no-verify` nicht aufhalten kann. Ein Versprechen, das nur bindet, wenn es bequem
  ist, ist genau das „nie ausgeführte Gate", dessenwegen dieses Repo existiert.
- Andere Sprachen, andere Namen: `REFLECT_READMES=a.md,b.md,c.md` — Hook, Gate und CI lesen
  denselben Knopf.
- Einzelneintrag-Liste: `REFLECT_READMES=maintaince.md` (eine Disziplin-Datei, kein Trio) ⇒
  die **Querverlinkungs-Regel der Strukturaudit ist vakant** — „der Sprachumschalter muss
  jede Sprache verlinken" gilt automatisch, wenn es nur eine Sprache gibt; das Gate **sagt
  laut, dass es nicht anwendbar ist** (derselbe Stil wie jedes andere Gate, das seinen
  Aus-Zustand ankündigt), während Existenz- / Nichtleer-Prüfung in Kraft bleiben. Das
  Push-Kriterium ist **nicht** vakant: „jeder Push muss es aktualisieren" bleibt ein
  echtes Urteil (Issue #8).

## Benutzung

```bash
cp -r zreflect reflect-hooks gates-selftest.sh /path/to/your-repo/
# 1. Dein measure() schreiben: FACTS.json mit gemessenen Fakten füllen (siehe measure_example in facts.py)
#    ⚠️ die vier Collector-Prinzipien stehen in zreflect/collect.py — nur persistentes Disk,
#    keine selbständernden Eingänge, „unavailable" laut sagen, das Teure cachen.
python3 zreflect/facts.py                        # einmal messen
python3 zreflect/facts.py --render-doc STATE.md  # den Maschinenblock ins Doc schreiben
python3 zreflect/facts.py --get py_lines          # Bare-Wert eines Fakts (für Skripte / andere Sprachen)
# 2. pre-commit / pre-push einhängen (Block neu rechnen + alle Gates;
#    pre-push weist außerdem Pushes ab, die das README-Trio nicht gemeinsam aktualisieren)
sh reflect-hooks/install.sh
# 2b. (optional) den Hooks einen dauerhaften Knopf-Träger geben (Issue #8):
#     cp reflect-hooks/reflect.env.example reflect-hooks/reflect.env
#     — git exportiert keine Custom-Env an Hooks, REFLECT_* -Werte,
#     die die Hooks lesen, wohnen in dieser Datei (fehlt sie ⇒ alle
#     Knöpfe fallen auf ihre Defaults zurück)
# 3. manuelle Nachprüfung (dieselben Befehle, die die Hooks fahren)
sh gates-selftest.sh                             # jedes Gate muss erst beweisen, dass es rot kann
for g in zreflect/check_*.py; do python3 "$g" || exit 1; done   # Entdeckungsregister — keine handgeschriebenen Listen, nicht mal hier
```

`measure_example()` in `facts.py` ist ein **Platzhalter** (er zählt die eigenen Repo-Dateien) —
ersetzen. Das System liefert den Mechanismus; nur du weißt, wie *deine* Eingänge zu messen sind.

Konsumenten (CI-Jobs, Tests in anderen Sprachen) lesen das Ledger über
`--get KEY` — **nie `FACTS.json` selbst parsen**: das klassische Scheitern
eines handgeschriebenen Parsers ist Substring-Matching auf `"value"` und
damit der **fremde** Wert eines anderen Schlüssels (issue #4 ④).

CI fährt dieselbe Prüfung bei jedem Push (`.github/workflows/gates.yml`):
`facts.py --check` plus jedes entdeckte Gate — `check_facts_replay`
eingeschlossen, also wird jeder `cmd` in CI wirklich ausgeführt. Lokale
Hooks binden nur Maschinen, die `install.sh` liefen; CI ist die Frontlinie
des Versprechens (issue #4 ②).

(Repo-interne Docs: `STATE.md` ist das Living-State-Beispiel, `AGENTS.md` enthält die
Agent-Regeln — beide auf Chinesisch gepflegt; die Trilingual-Regel gilt für das README-Trio.)

### Hook-Verkabelung für ZCode-Sessions

`.zcode/config.json` liefert eine fertige Konfiguration — **in genau dieser Form**
(die eigene Verkabelung dieses Repos war einmal eine kaputte Kopie dieses Beispiels,
issue #4 ①): Living State beim Sessionstart injizieren, beim Stopp den
Maschinenblock auffrischen.

```json
{
  "hooks": {
    "enabled": true,
    "events": {
      "SessionStart": [{ "matcher": "startup|resume|clear|compact",
        "hooks": [{ "type": "command", "command": "python3 \"${ZCODE_PROJECT_DIR}/.zcode/inject-state.py\"" }] }],
      "Stop": [{ "hooks": [{ "type": "command", "command": "python3 \"${ZCODE_PROJECT_DIR}/.zcode/stop-refresh.py\"" }] }]
    }
  }
}
```

Drei Formen sind tragend:

- **`enabled: true` ist Teil der Form** — Config-File-Hooks sind standardmäßig
  deaktiviert. Einträge sind `{ matcher?, hooks: [{ type, command }] }` unter
  `hooks.events.<Event>`; die flache `hooks.<Event>`-Form sieht ZCode nie.
- **Hook-stdout wird als striktes JSON geparst**: `inject-state.py` sendet im
  Hook-Kontext (non-tty) den `{"hookSpecificOutput": {…}}`-Umschlag und nur
  im Terminal von Hand plain text. Plain text im Hook-Kontext wird still
  verworfen — das Log behält eine failed-Zeile, die wie ein Kavaliersdelikt aussieht.
- **Stop-Hooks müssen immer mit 0 enden**. Zcodes Exit-Codes: `0` pass /
  `2` block / sonst error — und `facts.py --render-doc` endet mit 2 bei
  fehlendem Ledger. Direkt verdrahtet nimmt ein fehlendes Ledger die ganze
  Session als Geisel. `.zcode/stop-refresh.py` ist der immer-0-Wrapper:
  Fehler degradieren zu einer stderr-Zeile.

## Was es nicht ist

- **Kein Retrieval.** Es kümmert sich nicht darum, dass „der Korpus nicht in den Kontext passt" —
  das ist RAGs Problem. Dieses System hat das Problem **unüberprüfbarer Aussagen**.
- **Kein Gedächtnis.** Es fängt kein „der Nutzer hat mich korrigiert" in Prosa. Prosa ist das,
  was es zerstören will.
- **Nicht modellabhängig.** Alles ist nacktes Python und Exit-Codes. Keine API-Keys, kein Netz,
  keine Dienste.
- **Kein Schiedsrichter darüber, was ein Fakt ist.** Es verlangt nur, dass jede Aussage, die du
  triffst, ein Zuhause bekommt.

## Konfiguration (**kein Name ist hartverdrahtet**)

Umgebungsvariablen trennen „wie die Dinge heißen" von „wie der Mechanismus arbeitet" — die
Defaults sind einfach die Namen, die dieses Repo für sich selbst benutzt; Portierung auf andere
Repos passiert über Variablen, niemals über Code-Edits:

Diese Variablen erreichen die **Hooks** über eine repo-lokale Env-Datei
(Issue #8): `reflect-hooks/pre-commit` und `reflect-hooks/pre-push`
sourcen `reflect-hooks/reflect.env` — mit Rückfall auf ein
Repo-Wurzel-`reflect.env` — vor allem anderen, denn git reicht die
Custom-Umgebung des Aufrufers nicht an Hooks weiter; ein Knopf, der nur
per `export` in irgendeiner Shell gesetzt ist, ist ein Knopf, den die
Hooks nie sehen. Keine Datei ⇒ jeder Knopf fällt auf sein Default zurück
(der Wächter: eine fehlende Datei ist kein Fehler). Die `export`s der
Datei überschreiben gleichnamige Umgebungsvariablen — für einen Hook
ist die Datei die reproduzierbare Quelle. Form:
`reflect-hooks/reflect.env.example`.

| Variable | Default | Wirkung |
|---|---|---|
| `REFLECT_FACTS` | `FACTS.json` | Name des Ledger-Files |
| `REFLECT_DOC` | `STATE.md` | Living-State-Doc (darein wird der Maschinenblock gerendert) |
| `REFLECT_DOCS` | `STATE.md,AGENTS.md,README.md,README.zh.md,README.de.md` | von Retraktions-/Stale-Gates gescannte Living-State-Docs (Komma-getrennt; Geschichte-Docs gehören **nicht** hinein) |
| `REFLECT_HISTORY_SECS` | leer | welche **nummerierten** Abschnitte append-only Geschichte sind (z. B. `5,9,10`) — ihr „damals so" ist freigestellt |
| `REFLECT_RETIRED` | leer | pensionierte Komponentennamen (Komma-getrennt); leer = R2 des Stale-Gates **sagt laut, dass es aus ist** |
| `REFLECT_NAKED_MIN` | `100` | Schwellenwert für nackte Zahlen im Fakten-Gate: Ganzzahlen darunter werden ignoriert (1/2/3 sind überall — sie zu prüfen ist Rauschen); eingerahmte Code-Blöcke und Inline-Code sind freigestellt (Replay-Befehle enthalten naturgemäß Zahlen) |
| `REFLECT_STALE_DAYS` | leer | warnen, wenn `measured_at` eines Fakts älter als diese Tage ist; leer = die Staleness-Regel **sagt laut, dass sie aus ist** |
| `REFLECT_REPLAY` | leer (an) | `off` ⇒ das Replay-Gate **sagt laut, dass es aus ist**. Einzelne Einträge, die Build-Artefakte brauchen, steigen per Ledger-Feld `"replay": false` einzeln aus (ein komplett freigestelltes Ledger macht das Replay-Gate selbst rot) — nicht gleich das ganze Gate abschalten |
| `REFLECT_REPLAY_TIMEOUT` | `10` | Sekunden pro wiederausgeführtem `cmd`; Timeout ⇒ gemeldet (eine Messung, die nie fertig wird, gehört in `replay: false`, nicht in die Daten) |
| `REFLECT_READMES` | `README.md,README.zh.md,README.de.md` | das README-Trio: Eingang für die Strukturaudit **und** für „jeder Push muss alle im Änderungssatz haben"; Hook, Gate und CI lesen denselben Knopf |

`GATE_REPO` (`zreflect/gate.py`) zeigt auf **die Wurzel des geprüften Repos** — Selftests laufen
über es gegen Fixture-Bäume und fassen das echte Repo nie an.

**Cross-Repo-Selftest** (wiederholbar): Der letzte Abschnitt von `gates-selftest.sh` baut ein
**wegwerfbares Fixture-Repo**, benennt **alle** diese Namen um (`LEDGER.json` / `NOTES.md` /
`RETRACT.json` / `cases/` / das README-Trio unter anderen Namen) und verlangt von allen Gates
Grün — und fährt dasselbe Fixture unter den **Default-Namen**, wo jedes namenabhängige Gate rot
sein muss. Das ist das falsifizierbare Kriterium für „keine hartverdrahteten Namen": Wenn sich ein
Name nicht ändern lässt, wird dieser Abschnitt rot.

## Herkunft

Dieses System ist aus einem echten Langzeitprojekt herausgewachsen (ein großes C/Fortran-
Scientific-Stack als wasm in den Browser kompilieren: jeder Artefakt-sha, jede Performance-Zahl,
jede gemessene/inferierte/revozierte Aussage unter einem Gate). Beim Herauslösen wurden alle Pfade
und Daten jenes Projekts entfernt und nur die Mechanismen behalten — die Konfigurationstabelle
oben ist die Landestelle des „Entfernens".

Die wertvollste Lektion aus dieser Praxis: **ein Guard hat wegen einer undefinierten Variable vom
Tag seiner Auslieferung an nie gegriffen** — und er scheiterte in der Form „er crasht nur, wenn er
wirklich etwas zu melden hatte". Genau darum muss in jedem Gate hier die Klassen-„was feuern muss,
feuert" im `--selftest` stehen.

**2026-09-30, zweite Migration**: die restlichen praxiserprobten Mechanismen aus dem `.githooks/`
jenes Repos (Living-State-Extraktion, Stale-Assertion-Gate, Collector-Vertrag, git hooks) kamen
komplett herüber — siehe „Die zweite Gruppe" oben. Die Migration folgte derselben Disziplin:
**alle Projektdaten abstreifen, nur Mechanik behalten**; jede ersparte Narbenregel steht am Kopf
des Files, das sie regiert, und darf nirgendwo sonst nacherzählt werden (Nacherzählung driftet).

**2026-10-01, umbenannt und dreisprachig**: das Projekt heißt jetzt **Einfacht** (vormals
`zcode-reflect`). Das README existiert in drei Sprachen (Englisch Standard / 简体中文 / Deutsch)
als eine Aussage in drei Kopien — siehe „Das trilinguale README" für Gate, Hook und CI, die es
durchsetzen.

## Lizenz

MIT
