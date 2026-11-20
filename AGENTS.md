# AGENTS.md

Where the suite lives, where the rules live, what state means. The rules
themselves have exactly one origin: the `RULES` table in `zreflect/doc.py`
(guarded by a criterion). Copying them here would be a third copy -- this repo
handles "two copies that must agree" with a paired reconciler, and hand-copied
prose cannot be reconciled.

## Where the suite is

Einfacht is a **portable suite**, not specific to this repo. All criteria live
in `zreflect/`:

```
zreflect/gate.py         rc contract / off state / runner / selftest / phase executor
zreflect/i18n.py         zero-language core / machine-row protocol / language packs (zh/en/de)
zreflect/doc.py          document system: the discipline registry (rules' single origin)
zreflect/next.py         the "pick up from the last turn" collector (host-agnostic: stdout lines)
zreflect/check_*.py      gates (roster: registry --gates)
zreflect/examples.py     runnable examples: every gate + every core entry, in a temp repo
zreflect/lang/<lang>.json language packs; none installed is a legal state (output: code+args)
examples/<name>/         one example per gate plus the core entry points
ruff.toml                static checks' criteria (read by check_lint; CI reads the same file)
reflect-hooks/           hook entry & installer (`hook.py`; never grabs a hook seat)
zreflect/harness.py      discovery-based selftest harness
secrets.json             this repo's credential-scan declaration (exemptions carry reasons)
```

Reader-facing: `README.md` (English, default) / `README.zh.md` / `README.de.md`.
The three are three copies of one assertion; change one, change all three in the
same batch (`check_readme_sync.py` enforces).

## The two documents that must be measured

| Part | File | Content | How it is measured |
|---|---|---|---|
| **Principles** | [`PRINCIPLES.md`](PRINCIPLES.md) | each principle = one sentence + one judging command | every commit really runs it (`check_facts_replay`) |
| **State** | [`STATE.md`](STATE.md) | what things are now; numbers only as `[[key]]` | `--check` compares machine block vs ledger |

Principles are rendered directly from `zreflect/doc.py` `RULES` and replayed at
every commit alongside numeric facts in `FACTS.json` -- one re-run path, no
second executor.

Notes and other md files can be **manually registered** as facts, but are not
on the default surface.

## How to run

```bash
# Before work: the two documents (state = numbers, principle = verdicts)
python3 zreflect/facts.py --check            # machine blocks agree with the ledger
python3 zreflect/check_facts_replay.py       # every principle's command really runs

python3 zreflect/registry.py --run commit   # all commit-phase gates (ran/off/failed)
python3 zreflect/examples.py --all          # every capability, run for real in a temp repo
python3 zreflect/harness.py                 # every gate proves it can go red first
python3 zreflect/facts.py                   # re-measure
python3 zreflect/facts.py --render-doc      # render machine blocks (STATE.md + PRINCIPLES.md)
```

`registry.py --run` is the **only execution entry** -- never glob `check_*.py`.
What runs is decided by each gate's `GATE = gate.meta(...)` declaration line;
the phase is a declaration field (`runs_at`).

## Lookups

| Want | Go to |
|---|---|
| principles and their commands | `AUTO:RULES` block in `PRINCIPLES.md` |
| re-run all principles | `python3 zreflect/check_facts_replay.py` |
| knob semantics | `python3 zreflect/knobs.py --list` |
| gate roster | `python3 zreflect/registry.py --gates` |
| what runs now vs off | `python3 zreflect/registry.py --run commit` |
| a number | `python3 zreflect/facts.py --get <key>` |
| how to use one capability | `python3 zreflect/examples.py <name>` (see `examples/README.md`) |
| which capabilities have an example | `python3 zreflect/examples.py --check` |

## Memory is automatic

No hand-written handoff before compaction. `zreflect/next.py` computes a
"pick up from the last turn" block on each call (from git state: unpushed
commits, worktree, open questions):

```bash
python3 zreflect/next.py                    # plain text lines, never persisted
REFLECT_LANG=zh python3 zreflect/next.py    # switch output language (this command only)
```

It is never persisted -- per-turn state does not occupy a judged position.

⚠️ **The suite does not care how hosts wire it.** It knows no editor's hook
protocol, writes no host config, validates no host schema. To feed a session
hook, the consumer adds its own thin shell reading stdout -- that is part of
"using it in another repo", not the suite's business.

## Using it in another repo

Copy `zreflect/` + `reflect-hooks/` over, then in that repo:

```bash
python3 zreflect/facts.py --init     # generate a qualified skeleton (never overwrites)
python3 zreflect/facts.py            # measure once
python3 zreflect/facts.py --render-doc            # render machine blocks
python3 reflect-hooks/hook.py --chain             # wire git hooks
```

`--init` creates `STATE.md` / `PRINCIPLES.md` / `AGENTS.md` / `README.md` /
`retractions.json` / `questions/` (one example question), and:

- **`STATE.md` comes pre-seeded with `<!-- AUTO:FACTS -->` / `<!-- AUTO:GATES -->`
  markers** -- without them `--render-doc` fails with
  `FATAL: facts.markers_missing_render`;
- **`REGISTRY` defaults match the skeleton docs** (`STATE.md,AGENTS.md,README.md`
  plus `PRINCIPLES.md` unless `REFLECT_NO_PRINCIPLES=1`, and `README.md`) so a fresh repo needs no extra carrier file to pass.

After those four commands, `registry --run commit` must be **failed=0 /
fatal=0**. If not, check `--init` output for `already exists, left alone`
(old files were not overwritten).

⚠️ **`docs/` does not work** -- it is outside the suite; gates cannot see it.

⚠️ The measured target defaults to **the suite itself**
(`facts.measure_example()`, the placeholder in `zreflect/facts.py`). To measure
your project, add an unsealed `zreflect/measure_<name>.py` and set
`REFLECT_MEASURE_MODULE=measure_<name>` in `knobs.json`. Unset = the suite is
measured -- then the numbers in `STATE.md` are **about Einfacht**, not about
your project.

## Where configuration lives: three places, one resolution order

Every invocation (CLI, git hooks, CI) resolves knobs in the same order:
`os.environ > repo_config("knobs.json") > REGISTRY`.

| Place | Takes effect in | Use for |
|---|---|---|
| process environment / CI `env:` | one invocation | temporary overrides, e.g. `REFLECT_LANG=zh` |
| `knobs.json` (optional, repo root) | every invocation (hooks, CLI, CI) | per-repo knob values, e.g. `REFLECT_DOCS`, `REFLECT_READMES`, `REFLECT_MEASURE_MODULE` |
| `zreflect/knobs.py` `REGISTRY` | the default for everything | declarations: name, kind, default, meaning -- never a per-repo value |

Policy data is a **fourth** thing and is neither: `ab.json`, `doctor.json`,
`invariants.json`, `locks.json`, `pins.json`, `retractions.json`, `secrets.json`,
`world.json`, `questions/`. Those are per-repo files that gates read; they hold
policy, not mechanism.

Knob names are declared once in `REGISTRY` (`python3 zreflect/knobs.py --list`);
a token that appears in `zreflect/*.py` but not in the registry is a reported
phantom. Name-type knobs are never written into code.

**Unset and explicitly empty are different intents.** Unset = "I did not
decide, use the registry default". `REFLECT_READMES=` (empty) = "this repo has
no README group" -- the gate says so and stands down instead of reporting
`README.zh.md` missing, which would diagnose a stated intent as an absent file.
`REFLECT_DOCS=` deliberately keeps the collapsing behaviour: a repo must have a
state document, so an empty document group is meaningless rather than an answer.

## This repo's protocol: wiring and no-direct-writes

This is the **tool repo**: other agents' findings go through issues (with
reproduction and root cause file:line), the owner session rules on them and
lands patches. **Never write directly.**

Each repo wires its own git hooks (`reflect-hooks/hook.py --chain`); for
"pick up from the last turn" run `python3 zreflect/next.py <repo>` in that
repo. The host does not manage this (`host_agnostic` stands) -- never register
session hooks in user-level config.

Direct-write prevention uses an OS-layer advisory lock (host-side
`einfacht-lock.sh`, never on the judged surface): `chmod -R a-w` on the whole
tree; cache dirs (`.ruff_cache` / `__pycache__` ...) stay writable or ruff
cannot write its cache and `check_lint` goes FATAL. A same-user process can
chmod back -- it stops accidents, not adversaries.

```bash
~/.kimi-code/hooks/einfacht-lock.sh claim <session_id>  # register owner
~/.kimi-code/hooks/einfacht-lock.sh seal                # lock when done
~/.kimi-code/hooks/einfacht-lock.sh open                # unlock to write
~/.kimi-code/hooks/einfacht-lock.sh release             # remove entirely
```

Direct writes hit EACCES; bypassing chmod with a hard write is out of bounds.

## Landing changes: **per-repo enablement, default off** — "edit locally → final output → owner lands"

**PlumHelper (read-only) is the node-side gh credential by design.** Push
permission is granted **per repo by an explicit owner enablement order**;
default is off. This repo's enablement is **not issued** — even if a push
succeeds in practice, that is capability, not permission. **Do not retry push,
do not test write paths, do not treat a working push as an enablement order.**

Delivery while disabled (no fourth step):

1. Finish the change locally with gates green (`registry --run commit` +
   `harness.py`); run the code-review skill on your own changes.
2. Write the change summary **and the review verdict** into your session's
   final output, and put the same into the commit message — then stop. The
   owner patrols sessions, reads final outputs, and replies with approval.
3. After approval, push over the SSH alias — never the default `github.com`
   form (both gh tokens are read-only; HTTPS push returns HTTP 403):

   ```bash
   git push git@github-ArchivalEra:ArchivalEra/Einfacht.git HEAD:main
   ```

   Everything else splits by direction:

   - **Query/reconcile**: `gh api` on refs, `gh repo view`, `gh pr list` --
     the gh CLI covers the whole account-visible surface. `gh repo sync`
     needs write access under a read-only PAT (measured: HTTP 403) -- leave it to
     write-enabled contexts.
   - **Fetch/pull**: the remote is **split** — fetch URL is HTTPS
     (`https://github.com/ArchivalEra/Einfacht.git`, read-only PAT via gh
     keyring, silent), push URL is the SSH alias
     (`ssh://git@github-ArchivalEra/...`, SK key + MFA). Daily `git fetch` /
     `git pull` therefore run **zero approvals**; only push pings the phone.
     **Any fetch over an `ssh://` URL fires a phone approval — forbidden.**
     For a manual fetch, the HTTPS URL is the fallback; never a git+SSH pull
     remote.
   - **Write**: push only, over the push URL above.

   Push mechanics live **only here** (AGENTS.md is the ops manual; README is
   the product front). Until approval: nothing lands.

Push requests and review verdicts **do not go through wo-u** -- wo-u carries
task dispatch and rulings only. Report gate status in the final output
(`ran/off/failed` counts and names, CI run links). Local commits are
unaffected -- commit does not go through gh; only push does. If an enablement
order for this repo is ever issued, it supersedes this section's delivery
steps; until then, this section governs.

## When in doubt, ask

**Ask when a non-unattended objective is in progress**; only unattended work
allows self-derived fill-ins.
