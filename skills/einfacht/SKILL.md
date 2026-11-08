---
name: einfacht
description: >
  Set up and use Einfacht, a fact system against hallucination for agent-driven
  repos: every "this is how things are" claim must be backed by a re-runnable
  command. Use when the user wants to install Einfacht into a repo, wire its
  gates into git hooks, write a measure() for their project, interpret gate
  output (ran/off/failed, OFF:/FATAL:), add or settle facts, manage the
  retraction ledger, or diagnose why a gate is red.
---

# Einfacht

Make every factual claim **provable by a command**. A sentence in a doc must be
one of three things: backed by a re-runnable producer, marked as an inference
with a settling command, or moved to the retraction ledger. None of the three
⇒ a gate turns red.

## Install into a repo

```bash
cp -r <suite>/zreflect <suite>/reflect-hooks <suite>/ruff.toml <repo>/
cd <repo>
python3 zreflect/facts.py --init          # bootstraps skeleton docs; never overwrites
python3 zreflect/facts.py                 # first measurement
python3 zreflect/facts.py --render-doc    # machine block into the state doc
python3 reflect-hooks/install.py --chain  # chain into existing git hooks (never hooksPath)
```

Then **source the env carrier** before any hand-run (hooks source it themselves):

```bash
set -a; . ./Einfacht.env; set +a   # or reflect-hooks/Einfacht.env if that one exists
```

`--init` creates STATE.md / PRINCIPLES.md / AGENTS.md / README.md /
retractions.json / questions/ (one sample) / Einfacht.env trimmed to the docs
it actually made. If anything exists it is left alone — read the
`already exists, left alone` lines.

## Daily commands

| Command | What it does |
|---|---|
| `python3 zreflect/harness.py` | every gate proves it can go red + full self-proof (run before committing) |
| `python3 zreflect/registry.py --run commit` | the live execution face: aggregates `ran / off / failed / fatal` |
| `python3 zreflect/facts.py --check` | docs' machine blocks match the ledger byte-for-byte |
| `python3 zreflect/facts.py --render-doc [DOC]` | re-render machine block(s) after code changes |
| `python3 zreflect/facts.py --accept-changes[=k1,k2]` | accept measured changes (per-key); `--allow-drop` for removed keys |
| `python3 zreflect/doctor.py` | start-of-work liveness pre-flight (http/docker/port probes) |
| `python3 zreflect/knobs.py --list` | every knob and its meaning |

## Reading gate output

- rc **0** = green. rc **1** = a criterion failed (fix the thing it flagged).
  rc **2** = `FATAL:` the environment/config is broken (fix the setup, not the code).
- `OFF: <gate> (reason)` = declared off — a distinct state, **never** counted as pass.
- `=== N PASS / M FAIL ===` is a selftest summary line; selftests prove gates
  can go red, the live run (`--run commit`) proves they are green right now.
- `py_lines`-style mismatch after editing code ⇒ re-run measure + `--render-doc`,
  then `--accept-changes`. Never hand-edit `FACTS.json`.

## Make it measure your project

By default the suite measures itself. Point it at your code:

```bash
echo "export REFLECT_MEASURE_MODULE=my_measure" >> Einfacht.env
```

`my_measure.measure()` returns `{"key": {"value": <int>, "cmd": "<command>"}}`.
The command's stdout, stripped, must **equal** `value` (bare-value contract) —
print the value alone, never a human sentence. Expensive facts may set
`"replay": false` and attach a cheap `witness` + `witness_expect` instead.

All knobs live in `zreflect/knobs.py` and are configured by name in
`Einfacht.env` (`REFLECT_DOCS`, `REFLECT_READMES`, `REFLECT_QUESTIONS`,
`REFLECT_MEASURE_MODULE`, `REFLECT_LANG`, …) — never in code.

## When a gate goes red on purpose

- Claim overturned? Put the old assertion in `retractions.json` (fields: id,
  text, why, evidence, fixed_in) — reappearance in living docs is detected.
- Question to settle later? Drop a file in `questions/` with `**Status:**` and
  a `**Settling:**` command; resolve by setting `resolved` (never delete).
- Host-specific notes belong in `questions/`, not vendored code.

## Rules that bite (they are gates, not advice)

- Docs may cite `[[key]]` but never hand-copy measured numbers.
- Every gate has three-tier self-proof (normal silent / must-report / empty-loud)
  and a machine summary line; `harness.py` discovers them from declarations.
- The trilingual README trio moves as one batch (pre-push enforces it).
- Retired: `--legacy` hook install (`core.hooksPath`) — it silently kills
  husky/lefthook/pre-commit. Use `--chain`.
