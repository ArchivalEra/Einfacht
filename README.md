# Einfacht

[![gates](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/gates.yml)
[![readme-sync](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml/badge.svg)](https://github.com/ArchivalEra/Einfacht/actions/workflows/readme-sync.yml)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![checked by mypy](https://img.shields.io/badge/checked_by-mypy-2A6DB2)](https://mypy-lang.org/)
![python](https://img.shields.io/badge/python-3.13+-3776AB)
![license](https://img.shields.io/github/license/ArchivalEra/Einfacht)

Every "this is how things are" must be re-runnable. Einfacht is the apparatus
that makes that true for a repo an agent works in: five carriers hold what the
next session must not have to guess, and a gate reports any claim that drifted
away from the thing that proves it.

**Languages:** **English** (this file, default) · [简体中文](README.zh.md) · [Deutsch](README.de.md)

## What it holds

An agent's context dies with the session. The next one starts cold, and what
survives is whatever was written down. Einfacht makes that written-down part
**checkable**, and fixes where each kind of statement may live:

| Carrier | Holds | What proves it |
|---|---|---|
| `STATE.md` | what is true right now: measured numbers | rendered from the ledger; `facts.py --check` compares byte for byte |
| `PRINCIPLES.md` | the rules | each row carries a command that really runs (`check_facts_replay`) |
| `questions/` | what is still unresolved | every open question must carry a settler that yields two distinguishable outcomes |
| `HISTORY.md` | why a rule exists | must exist and must stay off every scan surface (`check_history`) |
| `AGENTS.md` | where to look and what to run | prose by design; it routes, it does not assert |

Four of those are judged; the fifth is the map into them. A statement that fits
none of them is the failure mode this suite exists to report.

The load-bearing part is the **last column**. A carrier without a criterion is a
folder; what makes `STATE.md` reliable is not that numbers were written there but
that a fresh render must match it byte for byte, and that every number carries a
command which reprints it. The same shape holds for the other three: a rule is a
row whose command runs at every commit, a question is a settler whose two
outcomes carry different exit codes, and `HISTORY.md` is guarded from the
opposite side — the criterion proves it **stays unscanned**, because an "as it
was then" line judged as current state would go red forever.

## Use it

```bash
cp -r <suite>/zreflect <suite>/reflect-local <suite>/ruff.toml <your-repo>/
cd <your-repo>
python3 zreflect/facts.py --init                  # skeleton docs, never overwrites
python3 zreflect/facts.py                         # first measurement
python3 zreflect/facts.py --render-doc            # render the state document
python3 reflect-local/hook.py --chain             # chain into your git hooks
```

`--init` writes the skeleton documents (`STATE.md`, `PRINCIPLES.md`, `AGENTS.md`,
`README.md`), `retractions.json`, and `questions/`. Registry defaults match that
single-README skeleton out of the box; repos that customize knobs can place an
optional `knobs.json` in the repo root (read identically by hooks, CLI, and CI):

```json
{
  "REFLECT_MEASURE_MODULE": "my_measure"
}
```

The suite needs no install step of its own: it is scripts plus a config file, and
`hook.py --chain` adds its lines to the hooks the repo already has instead of
replacing them. Nothing is written outside the repo.

Usage after that — knobs, output, what each exit code means — lives in
[skills/einfacht/SKILL.md](skills/einfacht/SKILL.md), the single entry point.

## What runs, and when

```
start-of-work   facts.py --check           documents agree with the ledger
                doctor.py                  liveness: are the services still up
commit          registry.py --run commit   every commit-phase gate, aggregated
                (ran / off / failed / fatal are reported separately -- off is
                 not a pass)
push            the same criterion, plus the trilingual READMEs in one batch
```

Every gate declares its own phase in a `GATE = meta(...)` line; the roster is
discovered from those declarations, never globbed. A gate that can switch
itself off must declare why, and its `OFF:` line is reported rather than being
counted as green.

The three phases differ in **frequency**, not in strictness, and the frequency is
a declaration field rather than a naming convention. `doctor.py` checks things
that can die — a rebooted machine, a container that vanished, a port taken by
something else — so it is wrong at commit frequency and right before work
starts. Everything else is cheap enough to run on every commit, which is the only
reason it can be trusted: a criterion that runs when someone remembers is a
criterion that reports the state of someone's memory.

## What a gate must survive before you trust it

Each gate ships `--selftest`. Running one proves the criteria it contains can
still go red; a criterion that can only pass is treated as decoration, not
evidence. `harness.py` runs all of them, then re-runs the suite with every
name-type knob swapped for a different name — a criterion that depends on this
repo's file names is a criterion that will not work in yours.

Two consequences follow, and both were paid for. First, a criterion must be able
to name **which** thing it rejected: a gate that reports "problems found" without
the file and line leaves the reader to guess, and guessing is what this suite is
against. Second, the self-test is not optional for a gate that "obviously works" —
the ones that obviously work are exactly the ones whose criteria quietly turn
into always-true comparisons, which is why `harness.py` refuses a gate whose own
proof cannot fail.

## Out-of-band approval & key rotation

`zreflect/trust.py` ships with a default `PINNED_APPROVER_PUB` for this host. External adopters or other devices must rotate it to their own Ed25519 keypair: place the public key PEM at `/etc/einfacht-approver/signing_pub.pem` (read-only by non-root agents), export `EINFACHT_APPROVER_PUB` (PEM or file path), or replace `PINNED_APPROVER_PUB` and re-run `python3 zreflect/registry.py --reseal=ALL --force`. In each downstream repo, run `python3 zreflect/trust.py --init` to bind `ANCHORS.json`; gates verify read-only locally, `python3 zreflect/trust.py --submit` / `--pull` / `--release` interact with `EINFACHT_APPROVER_URL`, and `python3 zreflect/trust.py --sync` updates `ANCHORS.json` locally once receipts pass.

## Why prose is confined

Prose rots: a sentence written as true keeps looking true after the code moves,
and nothing compares it to anything. So narration has exactly one home, and its
provenance is recorded in `HISTORY.md`. See [HISTORY.md](HISTORY.md).

## Documentation map

The primary documents are `STATE.md` (numbers), `PRINCIPLES.md` (rules),
`HISTORY.md` (provenance), `questions/` (open items) and `AGENTS.md` (routing).
Runnable examples live in [examples/README.md](examples/README.md); the language
packs are described in [docs/LANG-PACK-GLOSSARY.md](docs/LANG-PACK-GLOSSARY.md).
Agent-facing instructions are [skills/einfacht/SKILL.md](skills/einfacht/SKILL.md).

This file is the English member of the trio — [README.zh.md](README.zh.md) ·
[README.de.md](README.de.md) — and all three are checked as one assertion.

## License

MPL-2.0
