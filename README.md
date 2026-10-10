# Einfacht

**An agent's memory should not be prose — it should be an assertion you can re-run.**

**Languages:** **English** (this file, default) · [简体中文](README.zh.md) · [Deutsch](README.de.md)

> Status & direction: [maintaince.md](maintaince.md) — the map only; measured facts live in `STATE.md`'s machine block, usage in this trio.

> **For AI agents:** start from [maintaince.md](maintaince.md) — it names where truth lives and what to run before starting work; hard rules are in [AGENTS.md](AGENTS.md).

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
| **Gate platform** | `zreflect/gate.py` | checkers silently turning green — and the **rc contract's single home**: `off()` (0, prints an `OFF:` machine marker) / `fatal()` (2, config broken ≠ problems found) / `load_spec()` / `finish()` (1 vs 0) own the whole gate lifecycle, so 13 gates don't hand-copy their run-tails (they used to, and three divergent conventions grew: stdout-vs-stderr, header order, exit codes). `selftest()` now **refuses empty case lists** (the 0/0 hole — grep used to accept `0 PASS / 0 FAIL`); `main_selftest_or()` is the universal `__main__` tail; `meta()` is the declaration line the registry parses, and `run_phase()` is the **execution face**: it runs a phase's gates and aggregates `ran / off / failed` — so "all green" never silently includes "never ran" (this repo had 7 of 13 gates off). **off is a distinct state, not a pass** |
| **Bare-value runner** | `zreflect/runner.py` | the verbatim executor (`run_cmd` / `quote` / timeout) as a **public seam** — the replay gate and the world gate are its two adapters (two adapters = a real seam; it used to live in `check_facts_replay`'s private region) |
| **Knob registry** | `zreflect/knobs.py` | the `REFLECT_*` concept having no module: reads scattered across gates, declarations in docstrings, the roster guessed by text-scan (which admitted **phantom knobs** — configured, silently ignored). One roster (name → kind/default/meaning), **declared-or-die**; plus the self-consistency judgments (scan-surface phantoms, README phantoms, declared-knobs ⊆ actually-read, registry ⊆ README tables) — all of which run **regardless of any env-file carrier** (they were once welded behind it and never executed) |
| **Discovery registry** | `zreflect/registry.py` | the gate *set* was discovered but its **narration** was hand-written — and hand-written narration drifts (STATE.md said ten gates when thirteen existed; the red-list named 4 of 6). Gates self-declare (`GATE = gate.meta(…)`, ast-parsed, no import); platform modules too (`MODULE = module_meta(…)`, C5). The registry derives the **execution list** (`runnable(phase)` — the only source; hooks/CI/runner read it instead of globbing `check_*.py`), the narration (**AUTO:GATES** machine block), the red-list, and the selftest roster. `runs_at` (C1) is a declaration field, not a naming accident: `doctor` is a gate whose phase is `start-of-work` |
| **Ledger write guards** | `zreflect/guard.py` | the drop/change guards' **wiring** being untested: the pure functions had selftests, the path that actually refuses had none — this repo once shipped a guard dead from birth. `decide()` separates decision (pure; refuse/write/notes, 16 selftests) from execution (`measure()` runs it) |
| **Bare-value runner** | `zreflect/runner.py` | the verbatim executor (`run_cmd` / `quote` / timeout) as a **public seam** — the replay gate (ledger `cmd`) and the world gate (environment stamps) are its two adapters (two adapters = a real seam; it used to live in `check_facts_replay`'s private region and `check_world` imported the underscore names) |
| **Knob registry** | `zreflect/knobs.py` | the `REFLECT_*` concept having no module: reads scattered across gates, declarations living in docstrings, judgment data in envfile's hand lists, the roster guessed by text-scanning (which admitted **phantom knobs** — `REFLECT_AB` / `REFLECT_PINS` were docstring-only once: configured, silently ignored). One roster: name → (kind, default, one-line meaning); **declared-or-die** — a `REFLECT_*` token in the scan surface that isn't registered reports as phantom/typo, and the READMEs' knob mentions ⊆ registry (reverse assertion) |
| **Discovery registry** | `zreflect/registry.py` | the gate *set* was discovered but its **narration** was hand-written — and hand-written narrations drift: STATE.md's prose gate list said ten gates when thirteen existed; the runner's hand red-list named 4 of the 6 gates that actually go red; plugins and doctor were named by hand. Gates now self-declare (`GATE = gate.meta(…)` in each checker; ast-parsed, no import); `facts.py --render-doc` renders the **AUTO:GATES machine block** into STATE.md (the AUTO:FACTS precedent — narration derived, `--check` guards the drift), and the red-list + plugin roster derive from the same declaration lines |
| **Ledger write guards** | `zreflect/guard.py` | the drop/change guards' **wiring** being untested: the pure functions had selftests, the path that actually refuses had none — this repo once shipped a guard dead from birth via an undefined variable ("fails only when it should fire"). `decide()` separates decision (pure; refuse/write/notes, 16 selftests) from execution (`measure()` runs it); `--accept-changes` parsing lives here too |
| **Fact ledger** | `zreflect/ledger.py` + `facts.py` | numbers hand-copied or silently overwritten |
| **Fact gate** | `zreflect/check_facts.py` | doc block out of sync with the ledger, bare numbers in prose, citations of keys that don't exist |
| **Replay gate** | `zreflect/check_facts_replay.py` | "re-runnable" used to be an assertion **with no executor** (issue #2 ①): now every ledger `cmd` is executed verbatim (stdout must equal the value; broken command / timeout / missing cmd all reported; entries that need build artifacts opt out with `replay: false` — and can still carry a cheap **witness**, `witness` + `witness_expect`, issue #5: its provenance runs every commit; or a **calibration sample**, `calibrate` + `calibrate_expect`, issue #6 ①: the instrument runs against a known-positive sample every commit) |
| **Instrument lifecycle** (pluggable) | `zreflect/check_instruments.py` | the re-run contract catches *dead* commands (rc≠0), not **silent instrument distortion**: a command that succeeds, returns a stable value, and passes replay forever while measuring the wrong thing (`grep -c X` exits 0 successfully when the tool doesn't know mnemonic X). Pluggable: both knobs unset ⇒ says out loud it is off, exit 0. `REFLECT_INSTRUMENT_DAYS=N` enables constant-value detection (`first_seen` older than N days ⇒ "is this cmd really measuring, or always returning the same number?"); `REFLECT_INSTRUMENTS=instruments.json` registers falsified **measurement methods** (`{"methods": [{text, why, fixed_in}]}`) — any ledger `cmd` containing one is reported |
| **Declarative invariants** (pluggable) | `zreflect/check_invariants.py` | "file X must/must not contain fragment Y" as **data**, not code (`REFLECT_INVARIANTS=invariants.json`, spec `{"checks": [{path, must_contain?, must_not_contain?, why}]}`) — generic read-only engine, no build/network ⇒ pre-commit-safe; `why` is mandatory (a check nobody dares delete becomes a zombie). Pluggable: unset ⇒ says out loud it is off, exit 0. **Grep-level**: a fragment inside a comment passes too — it proves "this text is still here", not "the code really uses it"; a declarative check's strength is bounded by the text form it matches. Stronger guarantees are `calibrate`'s (on the artifact) or `witness`'s (on the source) job — orthogonal, don't mix: `calibrate` guards the *measuring tool*, invariants guard the *repo files themselves* |
| **Env-file carrier** (pluggable) | `zreflect/check_envfile.py` + `reflect-hooks/einfacht-env.sh` | the hooks' `REFLECT_*` source dying **silently**: a knob name misspelled by one letter is ignored by every program (the value never reaches the hooks — everything else keeps running); a file knob pointing at a missing file makes the hook's `[ -f ]` guard silently skip; an empty value or a comments-only file looks configured while loading nothing; broken `sh` syntax kills the hook at commit time with a misleading error. The knob registry is **discovered** (scans `zreflect/*.py` for `REFLECT_*` tokens — a hand-written list would drift, the same disease). Pluggable: no `Einfacht.env` ⇒ says out loud it is off, exit 0 |
| **Start-of-work doctor** (a gate with `runs_at="start-of-work"`) | `zreflect/doctor.py` | "every file invariant is green" ≠ "the environment is alive" (two real incidents, Octave-Full-Wasm HISTORY §5.86/§5.83: a reboot killed the acceptance site and build container while every file invariant held; another repo's dev server squatted the experiment port and the probe read someone else's page). Declarative **liveness** pre-flight, same data-not-code style as invariants: `{"checks": [{kind: http/docker/port-free, …, why}]}` — "must be alive" (http GET / `docker inspect`) **and** "must be free" (connect probe). Stdout bare-value contract: `ok` / `DOWN: <which>`. **Every probe carries a timeout** (`REFLECT_DOCTOR_TIMEOUT`, default 2s — a connect to a dead port otherwise waits forever: the probe must be decoupled from the probed thing). It **is** a gate, but its phase is `start-of-work`: it checks things that *die*, so running it at commit time is the wrong frequency — and the phase is a **declared field** (`runs_at`), not the old naming accident ("it isn't called `check_`"). The execution face (`registry --run start-of-work`) picks it up. Pluggable: no spec ⇒ says out loud it is off, exit 0 |
| **Reflection world** (pluggable gate) | `zreflect/check_world.py` | multi-line repos sharing one verification environment: the gates verify **whichever world happens to be deployed** (three real incidents, Octave-Full-Wasm 2026-10-07: a commit on `wasm64-NEXT` went red because the environment still held `IllegalPerformance`'s site; the same shape on `master`; NEXT-rebuilt artifacts leaked into a shared container's `rust_sort`). The world is **data**, not code: `{"lines": {<name>: {site, artifacts, container, fork_pin_ref, …}}, "active": <name>, "stamps": {<name>: {"value", "cmd"}}}`. One interface `resolve_line()` (env override > branch-if-a-line > `active`) replaces four ambient knobs with different names / defaults / coverage; branch-is-a-line-but-≠active ⇒ red (the switch-line script wasn't run); every stamp's `cmd` replays verbatim — **the same bare-value contract as the replay gate** (`run_cmd` grafted), stdout must equal `value` (the "environment polluted by another line" incident). Switching lines = running a script that does the three steps and **writes the declaration + stamps**; the commit gate then certifies declaration vs environment. Runs in pre-commit (unlike the doctor: the declaration is a stable file and the accidents were commit-time reds). Pluggable: no `world.json` ⇒ says out loud it is off, exit 0 (single-line repos unaffected — one world = current behavior) |
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
| **git hooks** | `reflect-hooks/` | gates lying in the repo **never executed**: pre-commit recomputes the machine block and runs every gate; pre-push refuses stale blocks (**it never edits files or rewrites history**). Both load a repo-local `Einfacht.env` through the **removable plugin** `einfacht-env.sh` (issue #8) — git does not export custom env to hooks, and "who remembered to `export`" doesn't survive a machine, CI, or personnel change; a file is the hooks' reproducible source (shape: `Einfacht.env.example`; hooks dir first, repo root second; delete the plugin ⇒ the guarded source line skips it and the hooks fall back to plain env vars + default names) |

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
  it proves the checker **is not decoration**. It also **refuses an empty case list** — the `0/0`
  accident above used to pass the runner's grep; now it is a shape error that fires on the spot.

**Deepened (2026-10-07).** The three case classes were enforced, but the *plumbing around them* was
not: each of the 13 checkers hand-copied its `run()` tail (15–45 lines), and the copies had already
drifted into three conventions — some printed problems to stdout and some to stderr, some printed
the header before the lines and some after, and exit codes disagreed (`check_world` returned 1 where
`doctor` returned 2 for the same "spec shape is broken" condition). So `gate.py` grew into the
gate lifecycle's single home:

- `off()` (0, says out loud it is off) / `fatal()` (2, configuration broken — kept distinct from
  "problems found" = 1) / `load_spec()` / `finish()` own the verdict; a checker's implementation
  shrinks to a pure `problems()` plus one `GATE = gate.meta(…)` declaration line;
- `main_selftest_or()` is the universal `__main__` tail (it shipped with **zero callers** while 15
  modules hand-rolled their own — including three that re-implemented the selftest loop and forgot
  the machine summary line once);
- four capabilities that were shallow or private got their own modules with real seams:
  `runner.py` (the verbatim executor — the replay gate and the world gate are its two adapters),
  `knobs.py` (the `REFLECT_*` roster — declared-or-die, so a docstring-only *phantom* knob reports),
  `registry.py` (gates self-declare; the discovery registry renders the **AUTO:GATES** machine block
  and derives the red-list, so the hand-written "ten gates" list that had already drifted is gone),
  and `guard.py` (the ledger write guards' decision, separated from execution so the path that
  actually refuses has selftests — a guard here once shipped dead from birth).

The lesson is the one this whole repo is built on: **the narration drifts exactly like the numbers
do.** The gate *set* was discovered, but "how many gates are there and which" was hand-written prose
— and it was wrong. It is now derived from the same declaration lines the runner reads.

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

**Fourth tier: instrument calibration** (issue #6 ①): the re-run
contract catches *dead* commands (rc≠0), not **silently distorted
instruments** — a command that succeeds, returns a stable value, and
passes replay forever while measuring the wrong thing (`grep -c X`
exits 0 successfully when the tool doesn't know mnemonic X). Any
`cmd` claiming "does the artifact contain X" should carry a
**known-positive sample**: `calibrate` (a cheap command run against
the sample) + `calibrate_expect` (the sample's known output). Like
`witness`, orthogonal to `replay`, run **every commit**, judged by
the same bare-value contract; the pair must be given together.

**Instrument lifecycle is pluggable** (`check_instruments.py`):
constant-value detection (`first_seen` — stamped at collection,
carried over by `measure()` while a value is unchanged) fires past
`REFLECT_INSTRUMENT_DAYS`: "is this cmd really measuring, or always
returning the same number?". Falsified **measurement methods** get a
registry like `retractions.json` (`REFLECT_INSTRUMENTS=instruments.json`,
schema `{"methods": [{text, why, fixed_in}]}`): a ledger `cmd`
containing a falsified method is reported — bad methods don't stay in
the ledger. Both knobs unset ⇒ the gate says out loud it is off and
exits 0; repos that don't need it pay nothing.

**Declarative invariants are pluggable too** (`check_invariants.py`,
issue #7): "this repo file must/must not contain this fragment"
as **data** — a JSON spec, not code:
`REFLECT_INVARIANTS=invariants.json`
(`{"checks": [{path, must_contain?, must_not_contain?, why}]}`).
The engine is generic and read-only; `why` is mandatory (a check
without a reason is a zombie nobody dares delete). This is the
`collect.py` principle-5 landing spot made checkable: the
invariants file *is* the input record, the gate *is* its cheap
source invariant. Orthogonal to `calibrate`, don't mix: `calibrate`
guards the *measuring tool*, invariants guard the *repo files
themselves*. Boundary, stated out loud: it is **grep-level** — a
fragment in a comment passes too, so it proves "this text is still
here", not "the code really uses it". A declarative check's
strength is bounded by the text form it matches; anything stronger
is `calibrate` (on the artifact) or `witness` (on the source).

**The env-file carrier is pluggable too** (`check_envfile.py`,
| **Derived-copy pin** (pluggable) | `zreflect/check_pins.py` | a submodule/fork pointer bumps while a provisioned copy (container tree, deploy dir) still serves the old content — drift invisible to git. The provisioner writes a stamp (`name branch commit dirty`); the gate re-reads it every commit: commit match / copy clean / version string match. Spec `{"pins": [{name, kind: tree\|version, worktree, stamp_read?, version_read?, expect_version?, why}]}`; unreadable ⇒ `SKIP:` out loud; empty pins ⇒ zero-value guard |
| **Lock manifest** (pluggable) | `zreflect/check_locks.py` | upstreams without a git-able home (netlib/freedesktop/sourceforge lineages) pinned as URL + sha256; file-form entries require the hash (missing/mismatch ⇒ report), dir-form checks existence, `optional` entries SKIP out loud |
| **A/B same-flag** (pluggable) | `zreflect/check_ab.py` | comparing two artifacts' declared surfaces: any key differing outside the tested axis is a confounder ⇒ the A/B verdict is void (real case: allocator A/B first reported −39% with a `--diag`-polluted baseline; same-flags re-measure = −27%). Spec `{"pairs": [{name, a, b, key?, allow[], why}]}`; missing artifact ⇒ `SKIP:` out loud; empty pairs ⇒ zero-value guard; `why` required |
issue #8): hooks read their `REFLECT_*` knobs from a
repo-local `Einfacht.env`, loaded by the removable plugin
`reflect-hooks/einfacht-env.sh` (hooks dir first, repo root
second; `REFLECT_ENV_FILE` renames the file). The plugin is
a **mechanism, not a welded step**: deleting it changes
nothing in the hooks — the guarded source line skips and
they fall back to plain environment variables. The gate
guards the file's *silent* failure modes (see the table
row above). Its knob registry is **discovered** — scanning
`zreflect/*.py` for `REFLECT_*` tokens — because a
hand-written list would drift like any other; that is also
why the gate's own source never spells a wrong knob name
literally: its selftest's typo sample is built by
concatenation, or the scanner would whitelist the very
typo the guard exists to catch. No `Einfacht.env` in
either location ⇒ the gate says out loud it is off and
exits 0.

**A start-of-work doctor is a small plugin, not a gate**
(`zreflect/doctor.py`, issue #10): "every file
invariant is green" ≠ "the environment is alive".
Two real incidents (Octave-Full-Wasm HISTORY
§5.86/§5.83): a reboot killed the acceptance site and
build container while every file invariant held —
the first symptom was a benchmark round failing
halfway through; and another repo's dev server
squatted the experiment port, so the probe read
someone else's page and the verdict was "the new
artifact won't start". git, the gates and witnesses
all govern **files and artifacts**; process,
container and port states answer to no mechanism.
The doctor is a declarative **liveness** pre-flight
(same data-not-code style as invariants):

```json
{ "checks": [
  { "kind": "http", "url": "http://127.0.0.1:8761/",
    "expect_status": 200,
    "expect_headers": {"Cross-Origin-Opener-Policy": "same-origin"},
    "why": "acceptance bar: the site must be up and send COI headers" },
  { "kind": "docker", "container": "o113",
    "state": "running", "why": "build lane" },
  { "kind": "port-free", "port": 8868,
    "why": "experiment's exclusive port — squatted ⇒ probes misread" } ] }
```

Both assertion kinds exist: **must be alive**
(http GET / `docker inspect`) and **must be free**
(connect probe). Stdout bare-value contract:
`ok` / `DOWN: <which>`. **Every probe carries a
timeout** (`REFLECT_DOCTOR_TIMEOUT`, default 2
seconds): a connect to a dead port otherwise waits
forever — the probe must be decoupled from the
probed thing (same lesson as "probes don't join the
boot path"). All probes are read-only and harmless.
It is **not in the discovered registry on purpose**:
it checks things that *die*, so it runs **at start
of work, not in pre-commit** — wrong frequency
there, and it would slow every commit. (So it is
`doctor.py`, not `check_doctor.py`: the discovery
loop `for g in zreflect/check_*.py` never sees it;
`gates-selftest.sh` names it once to prove it can
turn red, same as the env plugin.) Liveness is an
instantaneous fact ⇒ **not in ledger replay** — it
runs for real at every start of work. Boundary,
stated out loud: the doctor probes *liveness* only;
content is the existing gates'/acceptance's job;
which services must live and which ports must be
exclusive is **policy**, configured per repo (the
spec is data). Zero-value guards: empty list /
missing kind / missing why / unknown kind all report.

**A reflection world for multi-line repos**
(`zreflect/check_world.py`, issue #13): in a
repo with several independently maintained
lines sharing one verification environment, the
gates verify **whichever world happens to be
deployed** — three real incidents
(Octave-Full-Wasm, 2026-10-07): a commit on
`wasm64-NEXT` went red because the acceptance
site still belonged to `IllegalPerformance`; the
same shape on `master` (whose verification
object is the repo's own `site/`, not the shared
deployment); and NEXT-rebuilt artifacts leaking
into a shared container's `rust_sort` (the
container ran another line's build script). The
seam existed, but it was **four parallel
half-seams**: different names, different
defaults, different coverage — nothing forced
the gates to align with the line's world when a
line switched.

The world is **declarative data**, same style as
invariants:

```json
{ "lines": {
    "wasm64-NEXT": { "site": "/…/next-base/site",
                      "artifacts": "/…/next-base/w64-artifacts",
                      "container": "o113",
                      "fork_pin_ref": "upstream/octave" } },
  "active": "wasm64-NEXT",
  "stamps": {
    "container": { "value": "sha256:…",
                    "cmd": "docker inspect --format '{{.Image}}' o113" },
    "site":     { "value": "sha256:…",
                    "cmd": "find /…/site -type f | sort | xargs sha256sum | sha256sum" },
    "scripts":  { "value": "sha256:…",
                    "cmd": "sha256sum relink.sh link-web.sh | sha256sum" } } }
```

Three jobs: **resolve the current line**
(`REFLECT_WORLD_LINE` override for CI / special
runs > the branch name if it is a listed line >
`active` — the human's decision; other gates
consume verification objects through
`resolve_line()`, replacing the four ambient
knobs); **branch reconciliation** (branch is a
listed line but ≠ `active` ⇒ red — the
switch-line script wasn't run, or `active`
wasn't updated); **stamp reconciliation**
(every stamp's `cmd` replays verbatim, stdout
must equal `value` — the same bare-value
contract as the replay gate, `run_cmd` grafted
directly). **Switching lines = running a script
that does the three steps and then writes the
declaration (active + stamps)**; the commit gate
certifies declaration vs environment — the
"three-step switch" becomes an attested action
instead of spoken discipline.

It runs in **pre-commit** (unlike the doctor:
the world declaration is a stable file, and all
three accidents were red at commit time).
Pluggable: no `world.json` / knob unset ⇒ says
out loud it is off, exit 0 — **single-line repos
are unaffected** (one world = current behavior;
this bites the "several lines share one
verification environment" shape). Boundaries,
stated out loud: **no automatic line selection**
(which line is current is a human decision,
`active`); cross-engine reproducibility
(relaxed_madd makes BLAS last-digit results
vary — IEEE-compliant but not reproducible) is a
separate, orthogonal issue; stamps' `cmd`s are
repo-written — the same trust boundary as
replay. Zero-value guards: empty lines / missing
active / active not in lines / line missing
fields / empty stamps / stamp missing `value` or
`cmd` all report.

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

The **plugin's** selftest is wired into the same runner:
`reflect-hooks/einfacht-env.sh --selftest` (six scenarios,
including the falsifiable "delete the plugin ⇒ the hooks
fall back" proof). A plugin is not a `check_*.py` gate,
so discovery can't see it — it is named once in the
runner, and a missing or red plugin turns the run red.

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
- Single-entry list: `REFLECT_READMES=maintaince.md` (a discipline file, not a trio) ⇒ the
  structure check's **cross-link rule is vacuous** — "the switcher must link every language"
  holds automatically when there is only one language, so the gate **says out loud that it
  does not apply** (same style as every other gate announcing its off state) while the
  existence / non-empty checks stay in force. The push criterion is **not** vacuous:
  "every push must update it" is still a real judgment (issue #8).

## Usage

```bash
cp -r zreflect reflect-hooks gates-selftest.sh /path/to/your-repo/
# 1. Write your measure(): fill FACTS.json with measured facts (see measure_example in facts.py)
#    ⚠️ the collector's four principles live in zreflect/collect.py — persistent disk only,
#    no inputs that change by themselves, say "unavailable" out loud, cache the expensive ones.
python3 zreflect/facts.py                       # measure once
python3 zreflect/facts.py --render-doc STATE.md # write the machine blocks (facts + gate registry) into the doc
python3 zreflect/facts.py --get py_lines         # bare value of one fact (for scripts / other languages)
# 2. Install pre-commit / pre-push (recompute block + run all gates;
#    pre-push additionally refuses pushes that don't update the README trio together)
sh reflect-hooks/install.sh
# 2b. (optional) give the hooks a durable knob carrier (issue #8):
#     cp reflect-hooks/Einfacht.env.example reflect-hooks/Einfacht.env
#     — git does not export custom env to hooks, so REFLECT_* values the
#     hooks read live in that file (absent ⇒ every knob falls back to default)
# 2c. (optional) start-of-work liveness pre-flight (issue #10):
#     cp zreflect/doctor.json.example doctor.json   # edit: what must be
#     alive / which ports must be exclusive — then run
#     python3 zreflect/doctor.py before any suite / benchmark
#     (NOT in pre-commit: it checks things that die; wrong frequency there)
# 2d. (optional) declare the verification world (issue #13):
#     cp zreflect/world.json.example world.json   # edit: lines,
#     active, stamps — for multi-line repos sharing one
#     verification environment; single-line repos leave
#     it absent (the gate says out loud it is off)
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

Those variables reach the **hooks** through a repo-local env file (issue #8):
`reflect-hooks/pre-commit` and `reflect-hooks/pre-push` load
`reflect-hooks/Einfacht.env` through the removable plugin
`einfacht-env.sh` — falling back to a repo-root `Einfacht.env` — before
anything else, because git does not pass the caller's custom environment to hooks;
a knob set only via `export` in some shell is a knob the hooks never see.
No file ⇒ every knob falls back to its default (the guard: a missing file is not
an error). The file's `export`s override ambient same-name values — for a hook,
the file is the reproducible source. Shape: `reflect-hooks/Einfacht.env.example`.
Delete the plugin ⇒ the guarded source line skips it and the hooks fall back
to plain env vars + default names (the mechanism is removable by design).

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
| `REFLECT_DOCTOR` | `doctor.json` (absent ⇒ off) | start-of-work liveness pre-flight spec (issue #10): `{"checks": [{kind: http/docker/port-free, …, why}]}`; stdout contract `ok` / `DOWN: <which>`; **not a pre-commit gate** (checks things that die — runs at start of work; named once via `registry.SPECIAL_PLUGINS`) |
| `REFLECT_DOCTOR_TIMEOUT` | `2` | seconds per doctor probe; the decoupling rope — a connect to a dead port otherwise waits forever. Must be a positive number (a broken value is FATAL, not a silent default) |
| `REFLECT_AB` | `ab.json` | spec name of the A/B same-flag gate (`--spec` overrides; a knob set but pointing nowhere is FATAL, not "off") |
| `REFLECT_PINS` | `pins.json` | spec name of the derived-tree pin gate (`--spec` overrides; same explicit-missing semantics) |
| `REFLECT_WORLD` | `world.json` (absent ⇒ off) | reflection-world declaration (issue #13): `{"lines": {…}, "active": …, "stamps": {…}}` — multi-line repos sharing one verification environment; each stamp replays with the same bare-value contract as the ledger (`run_cmd` grafted) |
| `REFLECT_WORLD_LINE` | empty | line override for CI / special runs (must name a listed line — a dangling override is reported); unset ⇒ resolution order is branch-if-a-line > `active` |
| `REFLECT_INVARIANTS` | empty (absent ⇒ off) | declarative-invariants spec (issue #7): `{"checks": [{path, must_contain?, must_not_contain?, why}]}` |
| `REFLECT_INSTRUMENTS` | empty (absent ⇒ off) | falsified-measurement-method registry (issue #6 ①): `{"methods": [{text, why, fixed_in}]}` |
| `REFLECT_INSTRUMENT_DAYS` | empty (absent ⇒ off) | constant-value detection threshold in days (issue #6 ①): a ledger entry whose `first_seen` is older ⇒ "is this cmd measuring, or always returning the same number?" |
| `REFLECT_ENV_FILE` | `Einfacht.env` | file name of the hooks' knob carrier (issue #8), resolved by the removable plugin `einfacht-env.sh` (hooks dir first, repo root second) |
| `REFLECT_RETRACTIONS` | `retractions.json` | refuted-claims ledger (the retraction gate scans the `REFLECT_DOCS` docs for their reappearance) |
| `REFLECT_QUESTIONS` | `questions` | open-questions directory (one question per file; each must name a runnable settler) |

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
