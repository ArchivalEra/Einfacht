# PRINCIPLES · 不变的设计纪律

> The one question behind every rule: **who re-ran the proof that this is true now?**
> *What* is true now: [`STATE.md`](STATE.md). Knob semantics: `python3 zreflect/knobs.py --list`.

<!-- AUTO:RULES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the `RULES` table in `zreflect/doc.py`; **do not hand-edit**.
> Every row's judging command is in `FACTS.json` and is executed verbatim at every commit (`check_facts_replay`).

| id | principle | judging command |
|---|---|---|
| `assertion_lifecycle` | a retracted claim must not quietly return as current state | `python3 zreflect/check_retractions.py` |
| `declared_not_globbed` | predicates are declarations, not filenames: the execution surface reads registry --run <phase> | `python3 zreflect/registry.py --gates` |
| `doc_references_real` | a document must not point at a symbol that does not exist | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;d=doc.dangling_references();[print('dangling=%d %s.%s@%s' % (len(d),m,s_,f)) for f,m,s_ in d] or print('dangling=0');sys.exit(1 if d else 0)"` |
| `falsifiable` | claims must be falsifiable: always-true shortcuts are swept by AST and any hit fails | `python3 zreflect/registry.py --selftest` |
| `hard_needs_criterion` | a rule is hard only if it has a machine criterion; without one it does not enter the table at all (there is no advisory state) | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;p=doc._cmd_shape_problems();print('shape_problems=%d' % len(p));sys.exit(1 if p else 0)"` |
| `host_agnostic` | the suite's source recognizes no host's directory names / config formats (host wiring belongs to the consumer) | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-hooks') for r,_,fs in os.walk(d) for f in fs if f.endswith(('.py','.sh')) and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `machine_rows` | machine rows are defined in one place, machine.ROWS; the shell side has a behavior reconciler | `python3 zreflect/machine.py --selftest` |
| `no_retired_names` | retired names must not appear as current state; sha provenance and age are checkable | `python3 zreflect/check_stale.py` |
| `number_once` | each number is produced once and re-reconciled every commit: documents cite it as [[key]], never hand-copy it | `python3 zreflect/check_facts.py` |
| `one_form_per_fact` | a fact exists as state, as a principle, or as an open question -- never in two of them at once | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;c=doc.form_collision_problems();[print('collision=%s' % i) for _, ids in c for i in ids] or print('forms=%d' % len(doc.RULES));sys.exit(1 if c else 0)"` |
| `one_off_decisions_do_not_land` | a one-off decision ('why this round changed this way') is not recorded in a document; it belongs to the commit message | `python3 -c "import os,re,sys;p='|'.join([''.join(chr(c) for c in (0x8FD9,0x8F6E)),''.join(chr(c) for c in (0x672C,0x8F6E)),r'round\s+N']);hit=[(f,m.group()) for f in ('PRINCIPLES.md','STATE.md','AGENTS.md') if os.path.exists(f) for m in [re.search(p,open(f,encoding='utf-8').read())] if m];print('round_narrative=%d' % len(hit));sys.exit(1 if hit else 0)"` |
| `only_measured` | numbers/behavior trust measurement only; every fact must carry a re-run command | `python3 -c "import json,sys;d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `open_questions_settle` | every unresolved open question must carry a runnable settler | `python3 zreflect/check_questions.py` |
| `ran_is_not_passed` | "ran" and "ran and passed" are different statements, and so are "off" and "ran": a gate that can go off must declare why, and an empty traversal must say so | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `selfcert_harness` | every gate must have a --selftest entry (written but never run = decoration) | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.modules()[1];print('undeclared_modules=%d' % len(u));sys.exit(1 if u else 0)"` |
| `snapshot_hygiene` | a mutable global imported across modules is a value copy (stale snapshot): read via the module attribute instead | `python3 zreflect/check_snapshots.py` |
| `style_is_not_a_rule` | style preferences (naming, comment density, file layout) do not enter the rule table; they are held by 'match the code around you' | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;style=('style','naming','comment','layout','format');bad=[r.id for r in doc.RULES if r.id in style];print('style_ids=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `three_readmes` | the three-language READMEs are three copies of one assertion: change one, change all three in the same batch | `python3 zreflect/check_readme_sync.py` |
| `zero_language` | zero language in the core: user-visible messages go through M(code); machine contracts are untranslatable by construction | `python3 zreflect/check_i18n.py` |

19 principles -- each with a judging command that **really runs**.
<!-- /AUTO:RULES -->
