# Einfacht

[![gates](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml)
[![readme-sync](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![checked by mypy](https://img.shields.io/badge/checked_by-mypy-2A6DB2)](https://mypy-lang.org/)
![python](https://img.shields.io/badge/python-3.13+-3776AB)
![license](https://img.shields.io/github/license/ArchivalEra/Einfacht)

**An agent's memory should not be prose — it should be an assertion you can re-run.**

A fact system against hallucination for agent-driven repos: every "this is how
things are" must be backed by a re-runnable command, marked as an inference
with a settling command, or moved to the retraction ledger. None of the three
⇒ a gate turns red.

**Languages:** **English** (this file, default) · [简体中文](README.zh.md) · [Deutsch](README.de.md)

## Use it

**For AI agents:** read [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md) —
it teaches install, wiring, knobs, and how to read gate output. That file is
the single entry point; this README does not repeat it.

Humans, the 30-second version:

```bash
cp -r <suite>/zreflect <suite>/reflect-hooks <suite>/ruff.toml <your-repo>/
cd <your-repo>
python3 zreflect/facts.py --init                  # skeleton docs, never overwrites
python3 zreflect/facts.py                         # first measurement
python3 zreflect/facts.py --render-doc            # machine block into the state doc
python3 reflect-hooks/install.py --chain          # chain into your git hooks
set -a; . ./Einfacht.env; set +a                  # source the knob carrier
python3 zreflect/registry.py --run commit         # the live execution face
```

What you get: measured numbers produced once in `FACTS.json` (docs cite `[[key]]`,
never hand-copy), a discovery-registered gate roster that runs at commit/push,
three-tier self-proof per gate (`harness.py`), a retraction ledger with
reappearance detection, and a doctor for start-of-work liveness.

## Documentation map

| Want | Go to |
|---|---|
| Teach an agent to use it | [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md) |
| This file (English) | README.md — trio: [README.zh.md](README.zh.md) · [README.de.md](README.de.md) |
| Hard rules for agents | [AGENTS.md](AGENTS.md) |
| Status & direction | [maintaince.md](maintaince.md) |
| Measured facts (machine block) | [STATE.md](STATE.md) |
| Language-pack glossary | [docs/LANG-PACK-GLOSSARY.md](docs/LANG-PACK-GLOSSARY.md) |

The long-form README (design rationale, component tables, decision records)
lives in git history — `git log -- README.md`.

## License

MIT
