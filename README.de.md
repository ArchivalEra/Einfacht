# Einfacht

[![gates](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml)
[![readme-sync](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![checked by mypy](https://img.shields.io/badge/checked_by-mypy-2A6DB2)](https://mypy-lang.org/)
![python](https://img.shields.io/badge/python-3.13+-3776AB)
![license](https://img.shields.io/github/license/ArchivalEra/Einfacht)

Jedes „so ist es jetzt" muss wiederholbar sein. Einfacht ist die Vorrichtung, die
das in einem Repo wahr macht, in dem ein Agent arbeitet: fünf Träger halten, was
die nächste Sitzung nicht raten soll, und ein Gate meldet jede Aussage, die sich
von dem entfernt hat, was sie beweist.

**Sprachen:** [English](README.md) · [简体中文](README.zh.md) · **Deutsch** (diese Datei)

## Was es hält

Der Kontext eines Agenten stirbt mit der Sitzung. Die nächste beginnt kalt, und
was überlebt, ist das Aufgeschriebene. Einfacht macht diesen Teil **prüfbar** und
legt fest, wo jede Art von Aussage wohnen darf:

| Träger | Hält | Was es beweist |
|---|---|---|
| `STATE.md` | was gerade wahr ist: gemessene Zahlen | aus dem Register gerendert; `facts.py --check` vergleicht Byte für Byte |
| `PRINCIPLES.md` | die Regeln | jede Zeile trägt einen Befehl, der wirklich läuft (`check_facts_replay`) |
| `questions/` | was noch offen ist | jede offene Frage braucht einen Settler mit zwei unterscheidbaren Ausgängen |
| `HISTORY.md` | warum eine Regel existiert | muss existieren und auf keiner Scanfläche liegen (`check_history`) |
| `AGENTS.md` | wo man nachsieht und was man läuft | absichtlich Prosa; es leitet, es behauptet nicht |

Vier davon werden beurteilt; das fünfte ist die Karte hinein. Eine Aussage, die in
keinen passt, ist genau der Fehlerfall, für den es diese Suite gibt.

Tragend ist die **letzte Spalte**. Ein Träger ohne Bedingung ist ein Ordner;
`STATE.md` ist nicht deshalb verlässlich, weil Zahlen dort stehen, sondern weil ein
frisches Rendern Byte für Byte mit ihm übereinstimmen muss und jede Zahl einen
Befehl mitbringt, der sie erneut ausgibt. Dieselbe Form gilt für die anderen drei:
eine Regel ist eine Tabellenzeile, deren Befehl bei jedem Commit läuft; eine offene
Frage ist ein Settler, dessen zwei Ausgänge verschiedene Exit-Codes tragen; und
`HISTORY.md` wird von der **Gegenseite** bewacht — die Bedingung beweist, dass es
**ungescannt bleibt**, weil eine „so war es damals"-Zeile, als aktueller Zustand
beurteilt, für immer rot wäre.

## Benutzung

```bash
cp -r <suite>/zreflect <suite>/reflect-hooks <suite>/ruff.toml <dein-repo>/
cd <dein-repo>
python3 zreflect/facts.py --init                  # Skelett-Dokumente, überschreibt nie
python3 zreflect/facts.py                         # erste Messung
python3 zreflect/facts.py --render-doc            # Statusdokument rendern
python3 reflect-hooks/hook.py --chain             # in vorhandene Git-Hooks einketten
```

`--init` schreibt die Skelett-Dokumente (`STATE.md`, `PRINCIPLES.md`, `AGENTS.md`,
`README.md`), `retractions.json` und `questions/`. Die Register-Standardwerte
passen direkt zu diesem Einzel-README-Skelett; Repos mit eigenen Knöpfen können
eine optionale `knobs.json` in die Repo-Wurzel legen (von Hooks, CLI und CI
identisch gelesen):

```json
{
  "REFLECT_MEASURE_MODULE": "my_measure"
}
```

Die Suite braucht keinen eigenen Installationsschritt: sie besteht aus Skripten und
einer Konfigurationsdatei, und `hook.py --chain` hängt ihre Zeilen an die Hooks,
die das Repo schon hat, statt sie zu ersetzen. Nichts wird außerhalb des Repos
geschrieben.

Die Nutzung danach — Knöpfe, Ausgabe, was jeder Exit-Code bedeutet — steht in
[skills/einfacht/SKILL.md](skills/einfacht/SKILL.md), dem einzigen Einstiegspunkt.

## Was wann läuft

```
vor der Arbeit   facts.py --check           Dokumente stimmen mit dem Register
                 doctor.py                  Lebendigkeit: laufen die Dienste noch
beim Commit      registry.py --run commit   alle Commit-Gates, aggregiert
                                            (ran / off / failed / fatal getrennt;
                                             off ist kein Bestehen)
beim Push        dieselbe Vorschrift, dazu die dreisprachigen READMEs im selben Zug
```

Jedes Gate deklariert seine Phase in einer `GATE = meta(...)`-Zeile; die Liste wird
aus diesen Deklarationen entdeckt, nie geglobbt. Ein Gate, das sich abschalten kann,
muss begründen, warum; seine `OFF:`-Zeile wird gemeldet, statt als grün zu zählen.

Die drei Phasen unterscheiden sich in der **Frequenz**, nicht in der Strenge, und die
Frequenz ist ein Deklarationsfeld statt einer Namenskonvention. `doctor.py` prüft
Dinge, die sterben können — eine neu gestartete Maschine, ein verschwundener
Container, ein Port, den etwas anderes genommen hat —, also ist es bei
Commit-Frequenz falsch und vor der Arbeit richtig. Alles andere ist billig genug für
jeden Commit, und das ist der einzige Grund, ihm zu trauen: eine Bedingung, die läuft,
wenn jemand daran denkt, berichtet den Stand von jemandes Gedächtnis.

## Was ein Gate überleben muss, bevor man ihm traut

Jedes Gate bringt `--selftest` mit. Es zu laufen zeigt, dass die Bedingungen darin
noch rot werden können; eine Bedingung, die nur bestehen kann, gilt als Dekoration,
nicht als Beweis. `harness.py` läuft alle, dann läuft es die Suite erneut mit jedem
namensartigen Knopf auf einen anderen Namen umgestellt — eine Bedingung, die von
den Dateinamen dieses Repos abhängt, ist in deinem keine.

Daraus folgen zwei Konsequenzen, beide teuer bezahlt. Erstens muss eine Bedingung
sagen können, **was** sie abgelehnt hat: ein Gate, das „Probleme gefunden" ohne Datei
und Zeile meldet, lässt den Leser raten, und Raten ist genau das, wogegen diese Suite
steht. Zweitens ist der Selbsttest für ein Gate, das „offensichtlich funktioniert",
nicht optional — die offensichtlich funktionierenden sind genau die, deren
Bedingungen sich still in immer-wahre Vergleiche verwandeln, weshalb `harness.py` ein
Gate ablehnt, dessen eigener Beweis nicht fehlschlagen kann.

## Out-of-Band-Freigabe & Schlüsselwechsel

`zreflect/approval.py` enthält standardmäßig einen `PINNED_APPROVER_PUB` für diesen Host. Externe Nutzer müssen ihn auf ihr eigenes Ed25519-Schlüsselpaar umstellen: den öffentlichen Schlüssel als PEM unter `/etc/einfacht-approver/signing_pub.pem` ablegen (nur lesbar für normale Agenten) oder `PINNED_APPROVER_PUB` ersetzen und `python3 zreflect/registry.py --reseal=ALL --force` ausführen. In jedem Ziel-Repo `python3 zreflect/approval.py --init-anchors` für `ANCHORS.json` sowie `python3 zreflect/approval.py --request --wait` gegen `EINFACHT_APPROVER_URL` nutzen.

## Warum Prosa eingesperrt ist

Prosa verrottet: ein Satz, der als wahr geschrieben wurde, sieht weiter wahr aus,
wenn der Code sich bewegt, und nichts vergleicht ihn mit irgendetwas. Deshalb hat
Erzählung genau ein Zuhause, und ihre Herkunft ist in [HISTORY.md](HISTORY.md)
festgehalten.

## Dokumentkarte

Die Hauptdokumente sind `STATE.md` (Zahlen), `PRINCIPLES.md` (Regeln),
`HISTORY.md` (Herkunft), `questions/` (Offenes) und `AGENTS.md` (Wegführung).
Lauffähige Beispiele liegen in [examples/README.md](examples/README.md); die
Sprachpakete sind in [docs/LANG-PACK-GLOSSARY.md](docs/LANG-PACK-GLOSSARY.md)
beschrieben. Agentenanweisungen sind [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md).

Diese Datei README.de.md ist das deutsche Mitglied des Trios — [README.md](README.md) ·
[README.zh.md](README.zh.md) — und alle drei werden als eine Aussage geprüft.

## Lizenz

MPL-2.0
