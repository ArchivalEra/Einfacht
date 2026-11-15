# PRINCIPLES · 不变的设计纪律

> **这不是状态文档。** 这里只写「为什么这样设计」——它不随提交变化。
> 想知道**此刻**是什么样：看 [`STATE.md`](STATE.md)。想找某个旋钮：
> `python3 zreflect/knobs.py --list`。
>
> **没有历史文档。** append-only 的经过只在「当时那个条件」下可复现，
> 复不了的就不占一个会被判的位置。

本仓的立身之问只有一个：**「你说的『现在如此』，谁替你复跑证明过？」**

所有纪律都是这个问题的推论。它们不是风格偏好 —— 每一条都对应一次真实的
事故：某个断言在没有任何东西拦得住的情况下腐烂了，而周围的一切看起来都是绿的。

## 纪律表（机器渲染，不许手改）

下面是 `zreflect/doc.py` 的 `RULES` 表的渲染结果。**规矩的唯一产地是那张表**，
不是这段散文 —— 散文里再讲一遍就是第三份拷贝（假定 3）。
一张表自己讲清楚收什么、不收什么：表内每条都带判据，表外不放「建议」位。

<!-- AUTO:RULES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the `RULES` table in `zreflect/doc.py`; **do not hand-edit**.
> Every row's judging command is in `FACTS.json` and is executed verbatim at every commit (`check_facts_replay`).

| id | principle | judging command |
|---|---|---|
| `agreement_needs_reconciler` | two things that must agree will disagree unless a reconciler re-runs on every commit (block vs ledger is the standing witness) | `python3 zreflect/check_facts.py` |
| `assertion_lifecycle` | a retracted claim must not quietly return as current state | `python3 zreflect/check_retractions.py` |
| `declared_not_globbed` | predicates are declarations, not filenames: the execution surface reads registry --run <phase> | `python3 zreflect/registry.py --gates` |
| `doc_references_real` | a document must not point at a symbol that does not exist | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;d=doc.dangling_references();[print('dangling=%d %s.%s@%s' % (len(d),m,s_,f)) for f,m,s_ in d] or print('dangling=0');sys.exit(1 if d else 0)"` |
| `falsifiable` | claims must be falsifiable: always-true shortcuts are swept by AST and any hit fails | `python3 zreflect/registry.py --selftest` |
| `hard_needs_criterion` | a rule is hard only if it has a machine criterion; without one it does not enter the table at all (there is no advisory state) | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;p=doc._cmd_shape_problems();print('shape_problems=%d' % len(p));sys.exit(1 if p else 0)"` |
| `host_agnostic` | the suite's source recognizes no host's directory names / config formats (host wiring belongs to the consumer) | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-hooks') for r,_,fs in os.walk(d) for f in fs if f.endswith(('.py','.sh')) and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `machine_rows` | machine rows are defined in one place, machine.ROWS; the shell side has a behavior reconciler | `python3 zreflect/machine.py --selftest` |
| `no_retired_names` | retired names must not appear as current state; sha provenance and age are checkable | `python3 zreflect/check_stale.py` |
| `number_once` | each number is produced once: documents reference it as [[key]], never hand-copied (enforced both ways) | `python3 zreflect/check_facts.py` |
| `off_is_visible` | off must be distinguishable from "ran and passed"; a gate that can go off must declare why | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `one_off_decisions_do_not_land` | a one-off decision ('why this round changed this way') is not recorded in a document; it belongs to the commit message | `python3 -c "import os,re,sys;p='|'.join([''.join(chr(c) for c in (0x8FD9,0x8F6E)),''.join(chr(c) for c in (0x672C,0x8F6E)),r'round\s+N']);hit=[(f,m.group()) for f in ('PRINCIPLES.md','STATE.md','AGENTS.md') if os.path.exists(f) for m in [re.search(p,open(f,encoding='utf-8').read())] if m];print('round_narrative=%d' % len(hit));sys.exit(1 if hit else 0)"` |
| `only_measured` | numbers/behavior trust measurement only; every fact must carry a re-run command | `python3 -c "import json,sys;d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `open_questions_settle` | every unresolved open question must carry a runnable settler | `python3 zreflect/check_questions.py` |
| `ran_is_not_passed` | 'the scan ran' and 'the scan ran and passed' are different statements; a traversal that touches nothing must say so, not pass | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `selfcert_harness` | every gate must have a --selftest entry (written but never run = decoration) | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.modules()[1];print('undeclared_modules=%d' % len(u));sys.exit(1 if u else 0)"` |
| `snapshot_hygiene` | a mutable global imported across modules is a value copy (stale snapshot): read via the module attribute instead | `python3 zreflect/check_snapshots.py` |
| `style_is_not_a_rule` | style preferences (naming, comment density, file layout) do not enter the rule table; they are held by 'match the code around you' | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;style=('style','naming','comment','layout','format');bad=[r.id for r in doc.RULES if r.id in style];print('style_ids=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `three_readmes` | the three-language READMEs are three copies of one assertion: change one, change all three in the same batch | `python3 zreflect/check_readme_sync.py` |
| `zero_language` | zero language in the core: user-visible messages go through M(code); machine contracts are untranslatable by construction | `python3 zreflect/check_i18n.py` |

20 principles -- each with a judging command that **really runs**.
<!-- /AUTO:RULES -->

## 怎么用这张表

- 「这条规矩是谁在守」⇒ 看「判据」列。
- 判据列写 `module.function` 而不是 `file.py` 的，说明守它的是平台模块里的一个
  函数，它的自证住在 `registry._cases()`。
- **表里没有「软」条目。** 一条规矩要么有判据进这张表，要么不进——
  没有中间态，因此也没有可以挂「建议」的标记位。

## 没写进表里的东西

**风格偏好不进这张表**（`style_is_not_a_rule`）、**一次性的决策不落文档**
（`one_off_decisions_do_not_land`：轮次叙述属于提交信息）—— 两者不是口头约定，
表里的对应行就是它们的判据。其他的见各自行。
