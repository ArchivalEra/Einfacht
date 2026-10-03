# Einfacht

**An agent's memory should not be prose — it should be an assertion you can re-run.**

**Languages:** **English** (this file, default) · [简体中文](README.zh.md) · [Deutsch](README.de.md)

> Formerly `zcode-reflect`.

A **fact system against hallucination**, built for agent-driven repos. It does not train models,
does not do retrieval, does not store embeddings — it does exactly one thing: it makes every
"this is how things are" **provable by a command**, and it **catches automatically** the moment
that claim is overturned.

```
a sentence claiming to be fact  ──▶  attach a producer command (re-runnable)
                                     or mark it as inference (and name the experiment that settles it)
                                     or move it into the retraction ledger (with reappearance detection)
                                     none of the three ⇒ a gate turns red
```

## Why this exists

Models produce **confident-looking errors**. No amount of "please be careful" fixes this, because
the failure mode is not nonsense — it is **copying stale text**:

- one number hand-copied into six docs; you fix one, the other five keep asserting the old value;
- an assertion **already refuted by measurement** still sitting in the same file after the
  correction (with a copy in another file);
- a "findable in fifteen minutes" cost estimate that was never reconciled against the artifacts —
  the real first step was a 29 MB relink;
- a guard meant to stop facts from being silently overwritten **never fired once**, because of a
  single undefined variable.

None of these are knowledge errors. They are **knowledge lifecycles without a home**. Einfacht
gives every kind of claim a home — and every home a check **that can turn red**.

## Four disciplines

1. **Numbers and behaviors come from measurement only**, with the re-run command written next to
   the claim. A sentence without a re-run command may be read as history — never as "current state".
2. **Numbers are produced exactly once.** Docs cite key names; they never hand-copy digits.
3. **Compiles ≠ works.** Runtime claims must be tested in the real environment; a green build is
   not functional acceptance.
4. **Assertions must be falsifiable**: every new contract ships with at least one **reverse**
   assertion (what must fail, must fail).

The fifth discipline is what keeps the first four from becoming slogans: **every assertion has a
lifecycle** — measured / inferred / retracted. Living-state docs hold only measurements; inferences
go into notes with "which experiment settles this" written down; refuted claims go into the
retraction ledger.

## Seven components + the second group from Octave

| Component | File | What it stops |
|---|---|---|
| **Gate platform** | `zreflect/gate.py` | checkers silently turning green (zero-value guards + three-tier selftest) |
| **Fact ledger** | `zreflect/ledger.py` + `facts.py` | numbers hand-copied or silently overwritten |
| **Fact gate** | `zreflect/check_facts.py` | doc block out of sync with the ledger, bare numbers in prose, citations of keys that don't exist |
| **Replay gate** | `zreflect/check_facts_replay.py` | "re-runnable" used to be an assertion **with no executor** (issue #2 ①): now every ledger `cmd` is executed verbatim (stdout must equal the value; broken command / timeout / missing cmd all reported; entries that need build artifacts opt out with `replay: false` — and can still carry a cheap **witness**, `witness` + `witness_expect`, issue #5: its provenance runs every commit) |
| **Retraction ledger** | `zreflect/check_retractions.py` | retracted claims **reappearing inside the living-state docs declared by `REFLECT_DOCS`** |
| **Question ledger** | `zreflect/check_questions.py` | open questions living only in prose, with no executable settler |
| **Trilingual README gate** | `zreflect/check_readme_sync.py` | editing one language README while the others drift: the trio must exist, cross-link each other, and **move together in every push** |

### The second group, migrated from Octave-Full-Wasm (2026-09-30)

The first group was extracted from that project (see "Origins"); this second group migrates
**everything that was left** in its `.githooks/` — mechanisms that ran in anger for months.
Only the mechanisms were kept; all project data was stripped:

| Component | File | What it stops |
|---|---|---|
| **Living-state extraction** | `zreflect/living.py` | gates failing to tell "how things are" from "how things were". Three exits — declared history sections, inline history marks, records with an **explicit source** — plus "strict by default" (unnumbered sections are living state too), all in one file shared by every checker; the word list is produced exactly once |
| **Stale-assertion gate** | `zreflect/check_stale.py` | sha claims **without a source** in living state; retired component names sneaking back — measured over there: the build changed and the header still showed the old sha, unnoticed |
| **Collector contract** | `zreflect/collect.py` | `measure()` reading inputs **that change by themselves** (wall-clock / HEAD sha ⇒ `--check` never converges), inventing a 0 when a read fails, expensive measurements without caching — four principles + a block-recycling helper |
| **git hooks** | `reflect-hooks/` | gates lying in the repo **never executed**: pre-commit recomputes the machine block and runs every gate; pre-push refuses stale blocks (**it never edits files or rewrites history**) |

New knobs: `REFLECT_HISTORY_SECS` (which numbered sections are append-only history, e.g. `5,9,10`) ·
`REFLECT_RETIRED` (retired-component names; unset = that rule **says out loud that it is off**
instead of pretending to have checked). Since then the retraction gate scans living state only —
old values in history sections are naturally "as of then"; exempting them is not mercy, it is
refusing to make people destroy records.

Over there there are also `check-wants.py` (falsifiability of acceptance assertions: a single-number
want must match on numeric boundaries, and matching uses full output — truncation belongs on
display only) and `check-consistency.py` (the same piece of knowledge written in several places
will drift apart). They are two good models for **writing your own gates** — but both are welded to
that repo's file shapes, so they are recorded here as rules rather than shipped as empty shells.

### 1. Gate platform: a checker must first prove it can turn red

The dangerous thing is not "no check". It is **a check silently turning green when its inputs
disappear**:

- three sites simultaneously missing `VERSION`, and the consistency gate reports "fully consistent";
- an empty declared set, and the shipping audit returns `verdict: "ok"`;
- a self-check script reporting `0/0` as "all passed".

So `gate.py` provides two things:

- `require_nonempty(name, seq)` — the **zero-value guard**. If collection gathered nothing, that is
  an error, never "clean".
- `selftest(name, cases)` — every checker's `--selftest` must cover three case classes:
  **normal stays quiet / what must fire, fires / empty input fires**. The middle class is the key:
  it proves the checker **is not decoration**.

### 2. Fact ledger: two write guards

Each entry in `FACTS.json` is one **measured value** + re-run command + provenance. It renders into
the machine block of the living-state doc; prose may cite **key names** only.

Re-measuring (`facts.py`) has two silent failure modes, each with a guard:

| Failure mode | Symptom | Guard |
|---|---|---|
| **dropped entries** | input gone ⇒ facts **vanish silently** | `dropped_keys()` + `--allow-drop` |
| **changed values** | input changed (or was mis-measured) ⇒ facts **silently become a different number** | `changed_keys()` + `--accept-changes` |

The second is nastier: if gates only cross-check a few shas against disk, every other overwritten
value is **unrecoverable — nobody can ever see that it changed**. So `facts.py` refuses to write by
default and prints `old → new`, waiting for a human to confirm each change was measured.

⚠️ The value guard compares **`value` only**, never `cmd`/`source`/`note` — those describe *how to
re-run*, and editing them is normal doc maintenance. Making humans explicitly accept those too
turns the guard into noise, which gets blanket-`--accept-changes`ed, which kills the guard.

⚠️ **Which value changes are expected** (issue #2 ③): every entry that **counts the live tree**
(files / lines / tests) changes with ordinary development — one file added, one test added, done.
This is the most frequent and most predictable class, and first-timers misread it as "the guard is
crying wolf — did it mis-measure?" Copy-paste answer: confirm each change really is the accumulation
of development, then run `python3 zreflect/facts.py --accept-changes`. Never weaken the guard to
skip this step — no "auto-accept for counters": `--accept-changes` is the single mark of "I checked",
and "cmd changes don't warn" is already **the one justified exception** — don't open a second.

**Selective acceptance** (issue #3 ①): when one re-measure legitimately changes N values,
accept only the ones you verified — `--accept-changes=k1,k2` accepts exactly those keys and
still refuses every other changed value. Blanket-accepting a batch that contains a genuinely
broken measurement would launder it; the per-key form keeps the guard sharp when only part
of a change is understood.

Every entry also carries `measured_at` — the **collection-time** stamp (issue #3 ②).
`facts.py` prints the age in human words ("measured 3 days ago"), and the machine block
renders a "measured at" column with the **raw timestamp** (deterministic — an age computed
from the wall clock would never converge under `--check`). `check_stale` can warn past a
configured age: `REFLECT_STALE_DAYS` (unset = that rule **says out loud it is off**).
The stamp records *when*, and is never a measurement input — feeding it back as one is
exactly what would make `--check` never converge.

**The third tier: witnesses** (issue #5): `replay: false` used to mean
*never re-checked* — but expensive facts are the ones that most need a
cheap re-check. A 5-minute benchmark can't enter pre-commit, but its
**provenance** can still be witnessed:
`fact(value, cmd, source, replay=False, witness="<cheap read-only cmd>", witness_expect="<expected stdout>")`.
The witness runs **every commit** (orthogonal to `replay`), judged by the
same bare-value contract (`stdout.strip() == witness_expect`). The pair
must be given together — a half-given witness is a broken assertion, and
`ledger.fact()` refuses it on the spot. The incident behind this: an
artifact built by a drifted tool (`-flto` left in a build script) passed
every cheap gate and only blew up in the browser regression — a witness
comparing the artifact's recorded `tool.script_sha256` against the live
script would have caught it at commit time.

### 3. Retraction ledger: overturning leaves a trace

`retractions.json` stores **refuted** claims: a distinctive fragment `text`, why it was wrong `why`,
how to re-verify `evidence`, where the truth now lives `fixed_in`. The gate scans living-state
docs: any line containing `text` **must carry a correction marker** (see `HIST_MARK` in
`zreflect/living.py` — e.g. retracted / superseded / deprecated / 已翻案), or the gate reports.

One purpose: **a sentence that was retracted must not sneak back as current state.**

**The scan surface is bounded** (issue #2 ②): the gate scans exactly the living-state docs declared
by `REFLECT_DOCS`. The same sentence reappearing in **source comments, config, or any unlisted
file** ⇒ **invisible**. That is a **documented gap**, not "checked". Widening the surface requires
calibrating false positives first: source comments have no notion of "history sections", and
discussing history inside a comment is legitimate — a gate that cries wolf gets blanket-`--accept`ed,
which is worse than no gate.

⚠️ Boundary of inline correction markers (measured in the same round): markers exist for **citing
an old value while stating that it is old** — not for the assertion itself. Self-negation inside the
same line (e.g. `ZCODE_REFLECT_TYPO — this sentence is retracted.`) exempts that line. Using this
shape to immunize a *current* claim is bypassing the gate yourself.

### 4. Question ledger: an unsettled question is as good as unasked

One question per file in `questions/NN-slug.md`. Its header must carry:

```
Settling: <an executable path or command> —— rc=0 ⇒ conclusion A; rc=7 ⇒ conclusion B
```

Rules:

- `Settling:` must name **a repo-relative path** or a directly runnable command — "see some note"
  is not a settler.
- The two outcomes must produce **distinct exit codes / distinguishable output**, or the settler
  falsifies nothing.
- **A question whose settler does not exist yet is legitimate** — then the ticket's first deliverable
  is to build it. Write `Settling: none — this ticket's first deliverable`. **Never invent a path.**
  Saying "none" honestly carries information; a fake path makes the gate green and lying.
- When settled, write the conclusion into notes and set `Status: resolved`. **Do not delete the
  file** — history stays.

`check_questions.py` verifies: valid `Status:`, `Settling:` present, the file it points to exists,
and **reports when it collected not a single question** (zero-value guard).

⚠️ **Known limitation (read it as a limit, not a guarantee)**: path existence is checked for the
**first token** of `Settling:` only (when it looks like a path). A phrasing like
`just run scripts/missing.sh sometime` hides the path from the check. Tightening it first needs
false-positive calibration (placeholders like `<site>/…`, `.sh` inside arguments, all get hit).
Until a fixture calibrates that, better a **documented gap** than a strict check that cries wolf —
a wolf-crying gate gets blanket-`--accept`ed, and that is worse than nothing.

### 5. Gate registry: discovered, not listed

`gates-selftest.sh` **takes no hand-written list**. It scans `zreflect/check_*.py`, requires every
file to advertise `--selftest`, and turns red if one is missing.

The reality of hand-written registries: they always drift. Add a checker, forget to register it,
and that checker becomes "a checker nobody watches" — while the registry itself stays green,
reporting all-is-well. So it works the other way here: **registration is discovered, not remembered.**

Every `--selftest` ends with a machine-readable summary line, `=== N PASS / M FAIL ===`
(kept alongside the human line, issue #3 ③) — runners and CI grep one fixed format
regardless of the checker's name, and `gates-selftest.sh` turns red when a selftest
lacks it.

### 6. Trilingual README: the trio moves as one — or the push is refused

This repo's face exists in three languages: `README.md` (English, default), `README.zh.md`,
`README.de.md`. The three files are **one claim in three copies** — edit one and let the others
drift, and "the same sentence" has quietly become two contradicting assertions. The rule is
deliberately brutal: **every push must update all three together.**

- `reflect-hooks/pre-push` parses the **push range** from git's stdin protocol and refuses the push
  if the changed-file set of any pushed ref is missing a single copy of the trio.
- `check_readme_sync.py` (picked up automatically by the discovery registry) additionally checks
  structure on every commit and every selftest: all files exist, are non-empty, and each one
  contains all names of the trio — a broken language switcher is a broken entry point.
- CI (`.github/workflows/readme-sync.yml`) runs the **same judgment** — because a local hook cannot
  stop `git push --no-verify`. A promise that binds only when convenient is exactly the
  "gate that never executed" this repo exists to kill.
- Different languages, different file names: `REFLECT_READMES=a.md,b.md,c.md` — the hook, the gate
  and CI all read the same knob.

## Usage

```bash
cp -r zreflect reflect-hooks gates-selftest.sh /path/to/your-repo/
# 1. Write your measure(): fill FACTS.json with measured facts (see measure_example in facts.py)
#    ⚠️ the collector's four principles live in zreflect/collect.py — persistent disk only,
#    no inputs that change by themselves, say "unavailable" out loud, cache the expensive ones.
python3 zreflect/facts.py                       # measure once
python3 zreflect/facts.py --render-doc STATE.md # write the machine block into the doc
python3 zreflect/facts.py --get py_lines         # bare value of one fact (for scripts / other languages)
# 2. Install pre-commit / pre-push (recompute block + run all gates;
#    pre-push additionally refuses pushes that don't update the README trio together)
sh reflect-hooks/install.sh
# 3. Manual re-verification (the same commands the hooks run)
sh gates-selftest.sh                            # every gate must first prove it can turn red
for g in zreflect/check_*.py; do python3 "$g" || exit 1; done   # discovered registry — no hand-written lists, not even here
```

`measure_example()` in `facts.py` is a **placeholder** (it counts this repo's own files) — replace
it. The system ships the mechanism; only you know how to measure *your* inputs.

Consumers (CI jobs, tests in other languages) read the ledger through `--get KEY` —
**never parse `FACTS.json` yourselves**: a hand-rolled parser's classic failure is
substring-matching `"value"` and grabbing **another key's** value (issue #4 ④).

CI runs the same judgment on every push (`.github/workflows/gates.yml`):
`facts.py --check` plus every discovered checker — `check_facts_replay` included,
so every `cmd` is really executed in CI too. Local hooks only bind machines that ran
`install.sh`; CI is the promise's front line (issue #4 ②).

(Repo-local docs: `STATE.md` is the living-state example and `AGENTS.md` holds the agent rules —
both are kept in Chinese; the trilingual rule applies to the README trio.)

### Hook wiring for ZCode sessions

`.zcode/config.json` ships a ready-made config — **in this exact shape** (this repo's own
wiring was once a broken copy of this example, issue #4 ①): inject living state at session
start, refresh the machine block on stop.

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

Three shapes are load-bearing:

- **`enabled: true` is part of the shape** — config-file hooks ship disabled. Entries are
  `{ matcher?, hooks: [{ type, command }] }` under `hooks.events.<Event>`; the flat
  `hooks.<Event>` form is one ZCode never sees.
- **hook stdout is parsed as strict JSON**: `inject-state.py` emits the
  `{"hookSpecificOutput": {…}}` envelope when the hook runs it (non-tty) and plain text
  only when run by hand in a terminal. Plain text in hook context is silently dropped —
  the log keeps one failed line that looks minor.
- **Stop hooks must always exit 0**. ZCode's exit codes are `0` pass / `2` block /
  other = error, and `facts.py --render-doc` exits 2 on a missing ledger — wiring it
  directly takes the session hostage on one missing file. `.zcode/stop-refresh.py` is the
  always-0 wrapper: failures degrade to one stderr line.

## What this is not

- **Not retrieval.** It does not care that "the corpus does not fit in context" — that is RAG's
  problem. This system's problem is **unverifiable assertions**.
- **Not memory.** It does not capture "the user corrected me" into prose. Prose is what it exists
  to destroy.
- **Not model-dependent.** Everything is plain Python scripts and exit codes. No API keys, no
  network, no services.
- **Not an arbiter of what counts as fact.** It only demands that every claim you make gets a home.

## Configuration (**no name is hardcoded**)

Environment variables separate "what things are called" from "how the mechanism works" — the
defaults are simply the names this repo uses for itself; port to another repo by setting
variables, never by editing code:

| Variable | Default | What it does |
|---|---|---|
| `REFLECT_FACTS` | `FACTS.json` | ledger file name |
| `REFLECT_DOC` | `STATE.md` | living-state doc (the machine block renders into it) |
| `REFLECT_DOCS` | `STATE.md,AGENTS.md,README.md,README.zh.md,README.de.md` | living-state docs scanned by the retraction / stale gates (comma-separated; do **not** put history docs in here) |
| `REFLECT_HISTORY_SECS` | empty | which **numbered** sections are append-only history (e.g. `5,9,10`) — their "as of then" is exempt |
| `REFLECT_RETIRED` | empty | retired component names (comma-separated); unset = the stale gate's R2 **says out loud it is off** |
| `REFLECT_NAKED_MIN` | `100` | bare-number threshold of the fact gate: integers below it are ignored (1/2/3 are everywhere — checking them is noise); fenced code blocks and inline code are exempt (re-run commands naturally contain numbers) |
| `REFLECT_STALE_DAYS` | empty | warn when a fact's `measured_at` is older than this many days; unset = the staleness rule **says out loud it is off** |
| `REFLECT_REPLAY` | empty (on) | `off` ⇒ the replay gate **says out loud it is off**. Individual entries that need build artifacts should opt out one by one with the ledger field `"replay": false` (a fully-exempt ledger turns the replay gate red itself) — don't switch the whole gate off |
| `REFLECT_REPLAY_TIMEOUT` | `10` | seconds allowed per replayed `cmd`; timeout ⇒ reported (a measurement that never finishes belongs in `replay: false`, not in the data) |
| `REFLECT_READMES` | `README.md,README.zh.md,README.de.md` | the README trio: input to the structure check **and** to "every push must update all of them"; the hook, the gate and CI all read this knob |

`GATE_REPO` (`zreflect/gate.py`) points at **the repo being checked** — selftests run against
fixture trees through it and never touch the real repo.

**Cross-repo selftest** (re-runnable): the last section of `gates-selftest.sh` builds a **throwaway
fixture repo**, renames **all of these** (`LEDGER.json` / `NOTES.md` / `RETRACT.json` / `cases/` /
the README trio under different names) and requires every gate green — then runs the same fixture
under the **default** names and requires every name-dependent gate red. That is the falsifiable
criterion for "no hardcoded names": if a name cannot be changed, that section turns red.

## Origins

This system grew out of one real long-running project (compiling a large C/Fortran scientific
stack to wasm for the browser: every artifact sha, every performance number, every
measured/inferred/retracted claim under a gate). Extracting it removed every path and every piece
of data from that project and kept only the mechanisms — the configuration table above is where
"removed" landed.

The single most valuable lesson from that practice: **a guard, because of one undefined variable,
never fired from the day it shipped** — and it failed in the shape of "it only crashes when it
actually had something to report". Which is exactly why every gate here must include "what must
fire, fires" in its `--selftest`.

**2026-09-30, second migration**: the remaining field-tested mechanisms from that repo's
`.githooks/` (living-state extraction, stale-assertion gate, collector contract, git hooks) were
migrated in full — see "The second group" above. The migration followed the same discipline:
**strip all project data, keep only mechanism**; every scar-rule is written at the top of the file
it governs, and must not be restated elsewhere (restated things drift).

**2026-10-01, renamed and trilingual**: the project is now called **Einfacht** (formerly
`zcode-reflect`). The README exists in three languages (English default / 简体中文 / Deutsch)
as one claim in three copies — see "The trilingual README" section for the gate and the hook that
enforce it.

## License

MIT
