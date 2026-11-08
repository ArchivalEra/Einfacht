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

## 一条纪律算不算「硬」的决定规则

**有机器判据 = 硬纪律。没有 = 建议，且必须显式标 ADVISORY。**

这条规则本身是可执行的：每条原则的「判据」列就是一条**命令**，它被
`check_facts_replay.py` 在每次提交逐字执行（rc=0 通过、stdout 必须为空）。
「跑不跑得过」不是文档说的，是每次提交算出来的。

为什么要这条规则：本仓此前把 19 条硬坑写在 `AGENTS.md` 的散文里，其中 4 条
**根本没有判据**。它们与有判据的 15 条长得一模一样，读者无从分辨哪条会被拦、
哪条只是希望。**让建议冒充硬规矩，是防腐最大的敌人** —— 因为人会按「反正会被
拦住」去依赖它。

## 三条底层假定

1. **数字从写下的那一刻起就开始腐烂。** 代码一增减，手抄的数字就是假话，而没人
   会记得回来改它。所以数字只生产一次（台账），文档只引用（`[[键名]]`）。
2. **「跑过了」与「跑过且通过」不是一件事。** 遍历一个不存在的目录得到空集，
   然后「没有发现违规」—— 两句话都是真的，结论是错的。
3. **两份必须一致的东西，一定会不一致。** 除非有一个每次都能复跑的对账器。
   没有对账器的「必须一致」不是纪律，是愿望。

## 纪律表（机器渲染，不许手改）

下面是 `zreflect/doc.py` 的 `RULES` 表的渲染结果。**规矩的唯一产地是那张表**，
不是这段散文 —— 散文里再讲一遍就是第三份拷贝（假定 3）。

<!-- AUTO:RULES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the `RULES` table in `zreflect/doc.py`; **do not hand-edit**.
> Every row's judging command is in `FACTS.json` and is executed verbatim at every commit (`check_facts_replay`).

| id | principle | judging command |
|---|---|---|
| `assertion_lifecycle` | a retracted claim must not quietly return as current state | `python3 zreflect/check_retractions.py` |
| `declared_not_globbed` | predicates are declarations, not filenames: the execution surface reads registry --run <phase> | `python3 zreflect/registry.py --gates` |
| `falsifiable` | claims must be falsifiable: always-true shortcuts are swept by AST and any hit fails | `python3 zreflect/registry.py --selftest` |
| `host_agnostic` | the suite's source recognizes no host's directory names / config formats (host wiring belongs to the consumer) | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-hooks') for r,_,fs in os.walk(d) for f in fs if f.endswith(('.py','.sh')) and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `machine_rows` | machine rows are defined in one place, machine.ROWS; the shell side has a behavior reconciler | `python3 zreflect/machine.py --selftest` |
| `no_retired_names` | retired names must not appear as current state; sha provenance and age are checkable | `python3 zreflect/check_stale.py` |
| `number_once` | each number is produced once: documents reference it as [[key]], never hand-copied (enforced both ways) | `python3 zreflect/check_facts.py` |
| `off_is_visible` | off must be distinguishable from "ran and passed"; a gate that can go off must declare why | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `only_measured` | numbers/behavior trust measurement only; every fact must carry a re-run command | `python3 -c "import json,sys;d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `open_questions_settle` | every unresolved open question must carry a runnable settler | `python3 zreflect/check_questions.py` |
| `selfcert_harness` | every gate must have a --selftest entry (written but never run = decoration) | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.modules()[1];print('undeclared_modules=%d' % len(u));sys.exit(1 if u else 0)"` |
| `snapshot_hygiene` | a mutable global imported across modules is a value copy (stale snapshot): read via the module attribute instead | `python3 zreflect/check_snapshots.py` |
| `three_readmes` | the three-language READMEs are three copies of one assertion: change one, change all three in the same batch | `python3 zreflect/check_readme_sync.py` |
| `zero_language` | zero language in the core: user-visible messages go through M(code); machine contracts are untranslatable by construction | `python3 zreflect/check_i18n.py` |

14 principles — each with a judging command that **really runs**.
<!-- /AUTO:RULES -->

## 怎么用这张表

- 想知道「这条规矩是谁在守」⇒ 看「判据」列。
- 判据列写 `module.function` 而不是 `file.py` 的，说明守它的是平台模块里的一个
  函数，它的自证住在 `registry._cases()`（本仓对「纯函数被消费但自身零断言」的
  处置，见 `registry.dependency_coverage_problems`）。
- 标 **ADVISORY** 的条目**不会被任何闸门拦**。它们是有理由的建议，理由写在
  「为什么」列。若某条 ADVISORY 后来变得可判据化，做法是**加判据**、
  把 `advisory` 换成 `gate` —— 不是把它挪进建议区。

## 没写进表里的东西

**风格偏好不进这张表。** 命名、注释密度、文件组织 —— 这些由
「与周围代码一致」承担（见 `AGENTS.md` 的下半段）。它们没有判据，也不该有：
判据只能守可机械判定的东西，把风格也写成纪律会让这张表变成噪音。

**一次性的决策不进这张表。** 「这轮为什么这么改」**不落文档** —— 它属于
提交信息。`STATE.md` 只写「此刻是什么样」。这张表只收**还能推翻今天的设计**
的东西，且每条都必须有一条能跑的判定命令。