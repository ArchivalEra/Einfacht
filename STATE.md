# STATE · 此刻是什么样

> Every line below is rendered from the ledger. Never copy a number into prose.
> Unchanging rules: [`PRINCIPLES.md`](PRINCIPLES.md).

<!-- AUTO:FACTS -->
> This block is rendered by `zreflect/facts.py --render-doc` from `FACTS.json`; **do not edit by hand** (pre-commit recomputes and `git add`s it).
> 'Measured numbers' in the prose are produced only here: to cite one, write `[[key]]`; never copy the number by hand.

| key | value | measured at | replay cmd |
|---|---|---|---|
| `core_seal` | `b03674a3ef83094f...` | 2026-11-20T10:09:58+0800 | `python3 zreflect/registry.py --verify-seal` |
| `md_files` | **46** | 2026-11-20T10:09:58+0800 | `python3 zreflect/facts.py --count -files .md` |
| `md_lines` | **2173** | 2026-11-20T10:09:58+0800 | `python3 zreflect/facts.py --count -md` |
| `py_files` | **42** | 2026-11-20T10:09:58+0800 | `python3 zreflect/facts.py --count -files .py` |
| `py_lines` | **11705** | 2026-11-20T10:09:58+0800 | `python3 zreflect/facts.py --count -lines .py` |

5 facts.
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the discovered roster; **do not hand-edit**.
> The execution plane (hooks / CI) reads `registry --run <phase>` -- the phase is a declared field (`runs_at`), not a file name.

| Gate | Phase | What it guards | Knobs consumed | Why it may be off |
|---|---|---|---|---|
| `check_ab.py`（A/B gate） | commit | A/B same-flags invariant (a difference outside the allow axis = confounding variable, A/B void) | `REFLECT_AB` | repos that run no A/B experiments do not need it: spec unset => explicitly not enabled |
| `check_facts.py`（Facts gate） | commit | block agreement / bare numbers / bad citations | `REFLECT_DOC`, `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_NAKED_MIN`, `REFLECT_QUESTIONS` | -- |
| `check_facts_replay.py`（Replay gate） | commit | ledger cmds re-run verbatim (bare-value contract: stdout must equal the value) | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` | closes only when REFLECT_REPLAY=off is explicitly set |
| `check_i18n.py`（language coverage gate） | commit | zero-language core output via M(code) and optional language pack sync/coverage | `REFLECT_I18N_ROOT` | -- |
| `check_instruments.py`（Instrument lifecycle gate） | commit | constancy detection (first_seen) + falsified-method registry | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` | both knobs unset => the specialized mechanism is not enabled (pluggable; this repo turns it on when needed) |
| `check_invariants.py`（Invariants gate） | commit | declarative invariants: repo files must / must not contain a snippet (grep level) | `REFLECT_INVARIANTS` | repos that write no declarative invariants do not need it: spec unset => explicitly not enabled (pluggable) |
| `check_lint.py`（Static machine check） | commit | ruff's C901/F/E9/B, criteria in ruff.toml -- the 'all clear' must be re-established by every commit, not handwritten into the ledger from a single manual run (R-004) | -- | ruff not installed on this machine (external tool, not a repo dependency) => explicitly not enabled; CI pip-installs it, and there the gate really runs |
| `check_locks.py`（Locked-sources gate） | commit | locked-sources list (content fingerprints of URL + file + sha256) | `REFLECT_LOCKS` | repos that do not pin upstream bytes do not need it: spec unset => explicitly not enabled |
| `check_pins.py`（pin gate） | commit | derived-tree pin consistency (stamp commit / dirty / version string cross-read) | `REFLECT_PINS` | repos without a derived tree do not need it: spec unset => explicitly not enabled |
| `check_questions.py`（Question ledger gate） | commit | an unresolved question must carry a runnable settler | `REFLECT_QUESTIONS` | -- |
| `check_readme_sync.py`（Trilingual README gate） | commit | language versions are three copies of one assertion: structural cross-links + same-batch on every push | `REFLECT_READMES` | a repo that sets REFLECT_READMES to an empty list states it has no README group; unset is different and uses the registry default |
| `check_retractions.py`（Retraction-resurfacing check） | commit | a retracted assertion may not quietly return as the current state | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` | -- |
| `check_secrets.py`（Secrets gate） | commit | plain-text credential detection with explicit paths and justified exact exemptions | `REFLECT_SECRETS` | a repo that declares no credential-scanning spec keeps this gate off; a spec named explicitly but absent is a configuration error, never a disable |
| `check_snapshots.py`（module-level snapshot gate） | commit | a mutable global imported across modules is a value copy (stale snapshot): switch to importing the module and reading the attribute | `REFLECT_SNAPSHOT_ROOT` | -- |
| `check_stale.py`（Stale-assertion gate） | commit | sha provenance / retired names / age check | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` | -- |
| `check_world.py`（world gate） | commit | declarative validation target: world reconciliation of a multi-line repo's shared validation environment | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` | a single-line repo does not need it: spec not configured => state it is off |
| `check_explain.py`（Comment discipline） | start-of-work | strict: no docstrings; mismatch: explanation chars within AST complexity budget | `REFLECT_COMMENTS` | only disabled when REFLECT_COMMENTS=off is explicitly set |
| `check_history.py`（History document） | start-of-work | the one carrier where prose is allowed: it must exist and must stay off every scan surface | `REFLECT_HISTORY`, `REFLECT_DOCS`, `REFLECT_READMES`, `REFLECT_QUESTIONS`, `REFLECT_FACTS` | a repo that keeps no history document states so by pointing REFLECT_HISTORY at nothing; the exemption then has no subject |
| `doctor.py`（start-of-work doctor） | start-of-work | process / port liveness (probes things that can die => runs_at=start-of-work, not in pre-commit) | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` | this repo has no doctor.json spec: no process/port liveness is checked => state it is off |

19 gates; 13 may be disabled.
<!-- /AUTO:GATES -->
