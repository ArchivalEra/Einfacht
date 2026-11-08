# Einfacht

[![gates](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml)
[![readme-sync](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![checked by mypy](https://img.shields.io/badge/checked_by-mypy-2A6DB2)](https://mypy-lang.org/)
![python](https://img.shields.io/badge/python-3.13+-3776AB)
![license](https://img.shields.io/github/license/ArchivalEra/Einfacht)

**Das Gedächtnis eines Agenten sollte keine Prosa sein — es sollte eine überprüfbare Aussage sein.**

Ein Faktensystem gegen Halluzination für agentengetriebene Repos: Jede Aussage
„so ist es jetzt" muss an einem wiederholbaren Befehl hängen, als Inferenz mit
Settling-Befehl markiert sein oder im Widerrufsledger stehen. Keines von dreien
⇒ ein Gate wird rot.

**Sprachen:** [English](README.md) (Standard) · [简体中文](README.zh.md) · **Deutsch** (diese Datei)

## Benutzen

**Für KI-Agenten:** Lies [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md) —
dort stehen Installation, Anbindung, Knobs und wie man Gate-Ausgaben liest.
Diese Datei ist der einzige Einstiegspunkt; dieses README wiederholt sie nicht.

Die 30-Sekunden-Version für Menschen:

```bash
cp -r <suite>/zreflect <suite>/reflect-hooks <suite>/ruff.toml <dein-repo>/
cd <dein-repo>
python3 zreflect/facts.py --init                  # Skelett-Dokumente, überschreibt nie
python3 zreflect/facts.py                         # erste Messung
python3 zreflect/facts.py --render-doc            # Maschinenblock ins Statusdokument
python3 reflect-hooks/install.py --chain          # in vorhandene Git-Hooks einketten
set -a; . ./Einfacht.env; set +a                  # Knob-Träger sourcen
python3 zreflect/registry.py --run commit         # die einzige Ausführungsfläche
```

Was du bekommst: Messwerte werden einmal in `FACTS.json` produziert (Dokumente
zitieren `[[key]]`, niemals handkopiert), eine entdeckungsbasierte Gate-Liste
läuft bei Commit/Push echt, jedes Gate hat drei Selbstbeweis-Stufen
(`harness.py`), ein Widerrufsledger mit Wiedererkennung, und einen Doctor für
Live-Checks vor der Arbeit.

## Dokumentkarte

| Willst du | Geh zu |
|---|---|
| Einem Agenten die Nutzung beibringen | [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md) |
| Diese Datei (Deutsch) | README.de.md — Trio: [README.md](README.md) · [README.zh.md](README.zh.md) |
| Harte Regeln für Agenten | [AGENTS.md](AGENTS.md) |
| Stand & Richtung | [maintaince.md](maintaince.md) |
| Gemessene Fakten (Maschinenblock) | [STATE.md](STATE.md) |
| Sprachpaket-Glossar | [docs/LANG-PACK-GLOSSARY.md](docs/LANG-PACK-GLOSSARY.md) |

Das lange README (Designbegründung, Komponententabellen, Entscheidungsaufzeichnungen)
liegt in der Git-Historie — `git log -- README.md`.

## Lizenz

MIT
