# STATE · 此刻是什么样

> **这是活状态文档。** 正文只写「现在是什么」；数字一律引用台账键（`[[键名]]`），
> 不手抄 —— 手抄的数字从写下那一刻起就开始腐烂。
> 不变的设计原则：看 [`PRINCIPLES.md`](PRINCIPLES.md)。
>
> **没有历史文档**：append-only 的经过只在「当时那个条件」下可复现，
> 复不了的就不占一个会被判的位置。

本仓规模（引用，不是手抄）：脚本 [[py_files]] 个、文档 [[md_files]] 份、
Python 代码 [[py_lines]] 行。

> ⚠️ 上面这行若写成「本仓有 `10310` 行 Python」，`check_facts.py` 会报**正文裸数字**
> —— 那个数字从写下的那一刻起就开始腐烂：代码一增减它就是假话，而没人会记得
> 回来改它。引用键名则永远不会过期。（判据默认查 ≥ `100` 的整数，
> `REFLECT_NAKED_MIN` 可调；围栏代码块 / 行内代码内的数字豁免，复跑命令天然带数字。）

## 现在是什么

- **两道守卫生效中**：重测时掉条（键没了）与改口（值换了）都会拒绝写盘，除非显式
  `--allow-drop` / `--accept-changes`（后者支持逐条：`--accept-changes=k1,k2`
  只放行列出的键，其余照旧拒绝）。
- **闸门在线**：清单见文末的闸门名录机器块（发现式名录从各闸门的**声明行**
  渲染 —— 手写清单已退役：手写的那份实测漂过，ab/locks/pins 并入的当天清单
  就少了三道、道数也数错了，且没有任何闸门拦得住；叙述现在从声明行派生，
  加闸门 = 落一个声明行，机器块自动长出来）。**执行面读声明，不读文件名**
  （`registry --run <相位>`）：相位（`runs_at`）是声明字段 —— `commit`
  每次提交跑，`start-of-work` 开工前手动跑；名字不再承重（此前 doctor 只能靠
  「不叫 check_」表达频率）。off 态与「跑过且通过」可区分（`OFF:` 机器标记 ⇒
  聚合 `ran / off / failed`，「全绿」不把「没跑」算进去）。复跑闸门每条 `cmd`
  逐字复跑（stdout 必须等于值；贵事实可挂 witness 见证来源 —— 每提交真跑，
  issue #5；可挂 calibrate 校准仪器 —— 每提交对已知正样本真跑，issue #6 ①）。
- **钩子有持久的旋钮载体**（issue #8）：pre-commit / pre-push 在一切
  之前经**可拔插件** `reflect-hooks/einfacht-env.sh` 加载
  `reflect-hooks/Einfacht.env`（没有时回落仓库根的
  `Einfacht.env`；都没有 ⇒ 全部回落默认名）—— git 不把自定义环境
  变量传给 hooks，只在 shell 里 `export` 的 `REFLECT_*` 钩子看不见。
  删掉插件 ⇒ 带守卫的 source 行跳过，钩子回落纯环境变量（机制可拔）。
  形状：`reflect-hooks/Einfacht.env.example`。
- **开工预检 doctor**（issue #10，**声明 `runs_at=start-of-work` 的闸门**）：
  「文件不变量全绿」≠「环境还活着」—— 声明式活性预检
  `zreflect/doctor.py`（规格 `doctor.json`，旋钮
  `REFLECT_DOCTOR`；`{"checks": [{kind: http / docker /
  port-free, …, why}]}`，「必须活着」与「必须空着」两类
  断言；stdout 裸值契约 `ok` / `DOWN: <哪条>`；每条探测
  带超时 `REFLECT_DOCTOR_TIMEOUT` 默认 2 秒）。它**是**闸门，
  但相位是 `start-of-work`（查的是会死的东西，挂 pre-commit
  频率错）—— 频率由声明字段定，不再靠「它没叫 check_」；
  执行面 `registry --run start-of-work` 收它。活性是瞬时事实
  ⇒ 不进台账 replay。
- **一条悬案**：见 `questions/01-example.md`。
- **CI 正面执行同一判据**：`gates` workflow 每推跑 `registry --gates`
  对账 + `facts.py --check` + `registry --run commit`（跑 commit 相位的
  全部闸门并聚合 ran/off/failed，off 不是通过）；`readme-sync` 查三语同批。
  闸门清单以文末机器块为准 —— 这里不写数字，手写数字一定会漂。
  本地 hook 只约束跑过 install.py 的机器（issue #4 ②）。

## 那条示例翻案

活状态里提到被推翻的断言时，**必须带更正标记**，否则 `check_retractions.py` 会报。
下面这行的写法是合法的（它记录了 R-001，并标明了它已被推翻）：

> ZCODE_REFLECT_TYPO 这条是**已翻案的示例**，见 `retractions.json` 的 R-001。

<!-- AUTO:FACTS -->
> This block is rendered by `zreflect/facts.py --render-doc` from `FACTS.json`; **do not edit by hand** (pre-commit recomputes and `git add`s it).
> 'Measured numbers' in the prose are produced only here: to cite one, write `[[key]]`; never copy the number by hand.

| key | value | measured at | replay cmd |
|---|---|---|---|
| `md_files` | **11** | 2026-11-08T19:42:12+0800 | `python3 zreflect/facts.py --count -files .md` |
| `md_lines` | **799** | 2026-11-08T19:42:12+0800 | `python3 zreflect/facts.py --count -md` |
| `principle.assertion_lifecycle` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_retractions.py` |
| `principle.declared_not_globbed` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/registry.py --gates` |
| `principle.falsifiable` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/registry.py --selftest` |
| `principle.host_agnostic` | **ok** | 2026-11-08T19:42:12+0800 | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-hooks') for r,_,fs in os.walk(d) for f in fs if f.endswith(('.py','.sh')) and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.machine_rows` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/machine.py --selftest` |
| `principle.no_retired_names` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_stale.py` |
| `principle.number_once` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_facts.py` |
| `principle.off_is_visible` | **ok** | 2026-11-08T19:42:12+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `principle.only_measured` | **ok** | 2026-11-08T19:42:12+0800 | `python3 -c "import json,sys;d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.open_questions_settle` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_questions.py` |
| `principle.selfcert_harness` | **ok** | 2026-11-08T19:42:12+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.modules()[1];print('undeclared_modules=%d' % len(u));sys.exit(1 if u else 0)"` |
| `principle.snapshot_hygiene` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_snapshots.py` |
| `principle.three_readmes` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_readme_sync.py` |
| `principle.zero_language` | **ok** | 2026-11-08T19:42:12+0800 | `python3 zreflect/check_i18n.py` |
| `py_files` | **35** | 2026-11-08T19:42:12+0800 | `python3 zreflect/facts.py --count -files .py` |
| `py_lines` | **18843** | 2026-11-08T19:42:12+0800 | `python3 zreflect/facts.py --count -lines .py` |

18 facts.
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the discovered roster (declaration lines in zreflect/registry.py); **do not hand-edit**.
> The execution plane (hooks / CI) reads `registry --run <phase>` — the phase is a declared field (`runs_at`), not a file name.

| Gate | Phase | What it guards | Knobs consumed | Why it may be off |
|---|---|---|---|---|
| `check_ab.py`（A/B gate） | commit | A/B same-flags invariant (a difference outside the allow axis = confounding variable, A/B void) | `REFLECT_AB` | repos that run no A/B experiments do not need it: spec unset => explicitly not enabled |
| `check_envfile.py`（env-file gate） | commit | guards the hooks' REFLECT_* carrier (knob typos / dangling targets / empty values) | `REFLECT_ENV_FILE` | a repo without an env carrier (all knobs at their defaults) does not need it: spec not configured ⇒ state it is off |
| `check_facts.py`（Facts gate） | commit | block agreement / bare numbers / bad citations | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` | — |
| `check_facts_replay.py`（Replay gate） | commit | ledger cmds re-run verbatim (bare-value contract: stdout must equal the value) | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` | the whole gate closes only when REFLECT_REPLAY=off is set explicitly (this is the repo-wide exit; unset it still runs) |
| `check_i18n.py`（language coverage gate） | commit | the core is zero-language: user-visible text must go through M(code); language packs are optional | `REFLECT_I18N_ROOT` | — |
| `check_instruments.py`（Instrument lifecycle gate） | commit | constancy detection (first_seen) + falsified-method registry | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` | both knobs unset => the specialized mechanism is not enabled (pluggable; this repo turns it on when needed) |
| `check_invariants.py`（Invariants gate） | commit | declarative invariants: repo files must / must not contain a snippet (grep level) | `REFLECT_INVARIANTS` | repos that write no declarative invariants do not need it: spec unset => explicitly not enabled (pluggable) |
| `check_lint.py`（Static machine check） | commit | ruff's C901/F/E9/B, criteria in ruff.toml -- the 'all clear' must be re-established by every commit, not handwritten into the ledger from a single manual run (R-004) | — | ruff not installed on this machine (external tool, not a repo dependency) => explicitly not enabled; CI pip-installs it, and there the gate really runs |
| `check_locks.py`（Locked-sources gate） | commit | locked-sources list (content fingerprints of URL + file + sha256) | `REFLECT_LOCKS` | repos that do not pin upstream bytes do not need it: spec unset => explicitly not enabled |
| `check_pins.py`（pin gate） | commit | derived-tree pin consistency (stamp commit / dirty / version string cross-read) | `REFLECT_PINS` | repos without a derived tree do not need it: spec unset => explicitly not enabled |
| `check_questions.py`（Question ledger gate） | commit | an unresolved question must carry a runnable settler | `REFLECT_QUESTIONS` | — |
| `check_readme_sync.py`（Trilingual README gate） | commit | language versions are three copies of one assertion: structural cross-links + same-batch on every push | `REFLECT_READMES` | — |
| `check_retractions.py`（Retraction-resurfacing check） | commit | a retracted assertion may not quietly return as the current state | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` | — |
| `check_snapshots.py`（module-level snapshot gate） | commit | a mutable global imported across modules is a value copy (stale snapshot): switch to importing the module and reading the attribute | `REFLECT_SNAPSHOT_ROOT` | — |
| `check_stale.py`（Stale-assertion gate） | commit | sha provenance / retired names / age check | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` | — |
| `check_world.py`（world gate） | commit | declarative validation target: world reconciliation of a multi-line repo's shared validation environment | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` | a single-line repo does not need it: spec not configured ⇒ state it is off |
| `doctor.py`（start-of-work doctor） | start-of-work | process / port liveness (probes things that can die ⇒ runs_at=start-of-work, not in pre-commit) | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` | this repo has no doctor.json spec: no process/port liveness is checked ⇒ state it is off |

17 gates (derived from the discovered roster — a hand-written list drifts; adding a gate = landing one declaration line, and it grows here automatically); 10 of them **may be disabled** (the last column is a **declared** justification, not runtime state — who is off right now is seen via `registry --run <phase>`).
<!-- /AUTO:GATES -->
