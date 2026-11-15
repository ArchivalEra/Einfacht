# STATE · 此刻是什么样

> Every line below is rendered from the ledger. Never copy a number into prose.
> Unchanging rules: [`PRINCIPLES.md`](PRINCIPLES.md).

<!-- AUTO:FACTS -->
> This block is rendered by `zreflect/facts.py --render-doc` from `FACTS.json`; **do not edit by hand** (pre-commit recomputes and `git add`s it).
> 'Measured numbers' in the prose are produced only here: to cite one, write `[[key]]`; never copy the number by hand.

| key | value | measured at | replay cmd |
|---|---|---|---|
| `md_files` | **18** | 2026-11-15T21:29:10+0800 | `python3 zreflect/facts.py --count -files .md` |
| `md_lines` | **718** | 2026-11-15T21:29:10+0800 | `python3 zreflect/facts.py --count -md` |
| `principle.assertion_lifecycle` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_retractions.py` |
| `principle.declared_not_globbed` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/registry.py --gates` |
| `principle.doc_references_real` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;d=doc.dangling_references();[print('dangling=%d %s.%s@%s' % (len(d),m,s_,f)) for f,m,s_ in d] or print('dangling=0');sys.exit(1 if d else 0)"` |
| `principle.exec_position_is_a_command` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import json,os,sys;sys.path.insert(0,'zreflect');import criteria,knobs;specs=[(k,knobs.REGISTRY[k][1]) for k in ('REFLECT_WORLD','REFLECT_PINS')];bad=[(n,w,f) for k,n in specs if n and os.path.exists(n) for w,f,_ in criteria.exec_position_problems(json.load(open(n,encoding='utf-8')),n)];print('prose_positions=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.falsifiable` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/registry.py --selftest` |
| `principle.hard_needs_criterion` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;p=doc._cmd_shape_problems();print('shape_problems=%d' % len(p));sys.exit(1 if p else 0)"` |
| `principle.host_agnostic` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-hooks') for r,_,fs in os.walk(d) for f in fs if f.endswith(('.py','.sh')) and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.machine_rows` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/machine.py --selftest` |
| `principle.no_echo_between_carriers` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import glob,sys;sys.path.insert(0,'zreflect');import doc,echoes,ledger;f=(echoes.forms_from_rules(doc.RULES)+echoes.forms_from_ledger(ledger.load('FACTS.json'))+echoes.forms_from_questions(sorted(glob.glob('questions/*.md'))));h=echoes.echo_problems(f);[print('echo=%s~%s(%.3f)' % (a,b,r)) for r,a,b in h] or print('echoes=0 of %d forms' % len(f));sys.exit(1 if h else 0)"` |
| `principle.no_retired_names` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_stale.py` |
| `principle.number_once` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_facts.py` |
| `principle.one_form_per_fact` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;c=doc.form_collision_problems();[print('collision=%s' % i) for _, ids in c for i in ids] or print('forms=%d' % len(doc.RULES));sys.exit(1 if c else 0)"` |
| `principle.one_off_decisions_do_not_land` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import os,re,sys;p='|'.join([''.join(chr(c) for c in (0x8FD9,0x8F6E)),''.join(chr(c) for c in (0x672C,0x8F6E)),r'round\s+N']);hit=[(f,m.group()) for f in ('PRINCIPLES.md','STATE.md','AGENTS.md') if os.path.exists(f) for m in [re.search(p,open(f,encoding='utf-8').read())] if m];print('round_narrative=%d' % len(hit));sys.exit(1 if hit else 0)"` |
| `principle.only_measured` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import json,sys;d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.open_questions_settle` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_questions.py` |
| `principle.ran_is_not_passed` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `principle.selfcert_harness` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.modules()[1];print('undeclared_modules=%d' % len(u));sys.exit(1 if u else 0)"` |
| `principle.snapshot_hygiene` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_snapshots.py` |
| `principle.style_is_not_a_rule` | **ok** | 2026-11-15T21:29:10+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;style=('style','naming','comment','layout','format');bad=[r.id for r in doc.RULES if r.id in style];print('style_ids=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.three_readmes` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_readme_sync.py` |
| `principle.zero_language` | **ok** | 2026-11-15T21:29:10+0800 | `python3 zreflect/check_i18n.py` |
| `py_files` | **49** | 2026-11-15T21:29:10+0800 | `python3 zreflect/facts.py --count -files .py` |
| `py_lines` | **20784** | 2026-11-15T21:29:10+0800 | `python3 zreflect/facts.py --count -lines .py` |

25 facts.
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the discovered roster (declaration lines in zreflect/registry.py); **do not hand-edit**.
> The execution plane (hooks / CI) reads `registry --run <phase>` -- the phase is a declared field (`runs_at`), not a file name.

| Gate | Phase | What it guards | Knobs consumed | Why it may be off |
|---|---|---|---|---|
| `check_ab.py`（A/B gate） | commit | A/B same-flags invariant (a difference outside the allow axis = confounding variable, A/B void) | `REFLECT_AB` | repos that run no A/B experiments do not need it: spec unset => explicitly not enabled |
| `check_envfile.py`（env-file gate） | commit | guards the hooks' REFLECT_* carrier (knob typos / dangling targets / empty values) | `REFLECT_ENV_FILE` | a repo without an env carrier (all knobs at their defaults) does not need it: spec not configured => state it is off |
| `check_facts.py`（Facts gate） | commit | block agreement / bare numbers / bad citations | `REFLECT_FACTS`, `REFLECT_NAKED_MIN` | -- |
| `check_facts_replay.py`（Replay gate） | commit | ledger cmds re-run verbatim (bare-value contract: stdout must equal the value) | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` | the whole gate closes only when REFLECT_REPLAY=off is set explicitly (this is the repo-wide exit; unset it still runs) |
| `check_i18n.py`（language coverage gate） | commit | the core is zero-language: user-visible text must go through M(code); language packs are optional | `REFLECT_I18N_ROOT` | -- |
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
| `doctor.py`（start-of-work doctor） | start-of-work | process / port liveness (probes things that can die => runs_at=start-of-work, not in pre-commit) | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` | this repo has no doctor.json spec: no process/port liveness is checked => state it is off |

18 gates (derived from the discovered roster -- a hand-written list drifts; adding a gate = landing one declaration line, and it grows here automatically); 12 of them **may be disabled** (the last column is a **declared** justification, not runtime state -- who is off right now is seen via `registry --run <phase>`).
<!-- /AUTO:GATES -->
