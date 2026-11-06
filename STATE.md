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
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `md_files` | **9** | 2026-11-06T13:00:14+0800 | `python3 zreflect/facts.py --count -files .md` |
| `md_lines` | **2686** | 2026-11-06T13:00:14+0800 | `python3 zreflect/facts.py --count -md` |
| `principle.assertion_lifecycle` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_retractions.py` |
| `principle.declared_not_globbed` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/registry.py --gates` |
| `principle.falsifiable` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/registry.py --selftest` |
| `principle.host_agnostic` | **ok** | 2026-11-06T13:00:14+0800 | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-hooks') for r,_,fs in os.walk(d) for f in fs if f.endswith(('.py','.sh')) and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.machine_rows` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/machine.py --selftest` |
| `principle.no_retired_names` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_stale.py` |
| `principle.number_once` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_facts.py` |
| `principle.off_is_visible` | **ok** | 2026-11-06T13:00:14+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry, criteria;gs=registry.gates()[0];p=criteria.off_reason_problems(gs);print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));sys.exit(0 if gs and not p else 1)"` |
| `principle.only_measured` | **ok** | 2026-11-06T13:00:14+0800 | `python3 -c "import json,sys;d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `principle.open_questions_settle` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_questions.py` |
| `principle.selfcert_harness` | **ok** | 2026-11-06T13:00:14+0800 | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.modules()[1];print('undeclared_modules=%d' % len(u));sys.exit(1 if u else 0)"` |
| `principle.snapshot_hygiene` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_snapshots.py` |
| `principle.three_readmes` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_readme_sync.py` |
| `principle.zero_language` | **ok** | 2026-11-06T13:00:14+0800 | `python3 zreflect/check_i18n.py` |
| `py_files` | **35** | 2026-11-06T13:00:14+0800 | `python3 zreflect/facts.py --count -files .py` |
| `py_lines` | **15706** | 2026-11-06T13:00:14+0800 | `python3 zreflect/facts.py --count -lines .py` |

18 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。
> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段（`runs_at`），不是文件名。

| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 | 可未启用的理由 |
|---|---|---|---|---|
| `check_ab.py`（A/B 闸门） | commit | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` | 不做 A/B 对照实验的仓不需要它：规格未配 ⇒ 明说未启用 |
| `check_envfile.py`（env 文件闸门） | commit | 守钩子的 REFLECT_* 载体（旋钮 typo / 指向缺失 / 空值） | `REFLECT_ENV_FILE` | 没有 env 载体的仓（旋钮全用默认值）不需要它：规格未配 ⇒ 明说未启用 |
| `check_facts.py`（事实闸门） | commit | 块一致性 / 裸数字 / 坏引用 | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` | — |
| `check_facts_replay.py`（复跑闸门） | commit | 台账 cmd 逐字复跑（裸值契约：stdout 必须等于值） | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` | 显式设 REFLECT_REPLAY=off 时整道闸门关闭（这是整仓出口；未配时照跑） |
| `check_i18n.py`（语言覆盖闸门） | commit | 本体零语言：用户可见文本必须走 M(code)；语言包可选 | `REFLECT_I18N_ROOT` | — |
| `check_instruments.py`（仪器生命周期闸门） | commit | 恒常检测（first_seen）+ 被证伪量法登记 | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` | 两个旋钮都未配 ⇒ 特化机制没启用（可插拔，本仓按需再开） |
| `check_invariants.py`（不变量闸门） | commit | 声明式不变量：仓库文件必须/不得含某片段（grep 级） | `REFLECT_INVARIANTS` | 不写声明式不变量的仓不需要它：规格未配 ⇒ 明说未启用（可插拔） |
| `check_lint.py`（静态机器检查） | commit | ruff 的 C901/F/E9/B，判据在 ruff.toml —— 「已清」必须由每次提交复跑，不是一次手工跑完写进台账（R-004） | — | 本机没装 ruff（外部工具，不是本仓依赖）⇒ 明说未启用；CI 里 pip 装了它，那道会真跑 |
| `check_locks.py`（锁定源闸门） | commit | 锁定源清单（URL + 文件 + sha256 的内容指纹） | `REFLECT_LOCKS` | 不钉上游字节的仓不需要它：规格未配 ⇒ 明说未启用 |
| `check_pins.py`（pin 闸门） | commit | 派生树 pin 一致性（stamp commit / dirty / 版本串对读） | `REFLECT_PINS` | 没有派生树的仓不需要它：规格未配 ⇒ 明说未启用 |
| `check_questions.py`（悬案闸门） | commit | 未结案的问题必须挂一个能跑的结算件 | `REFLECT_QUESTIONS` | — |
| `check_readme_sync.py`（三语 README 闸门） | commit | 语言版本是同一条断言的三份拷贝：结构互链 + 每次推送同批 | `REFLECT_READMES` | — |
| `check_retractions.py`（翻案重现检测） | commit | 被推翻的断言不许悄悄回来当现状 | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` | — |
| `check_snapshots.py`（模块级快照闸门） | commit | 跨模块 import 的可变全局是值拷贝（陈旧快照）：改成 import 模块 + 读属性 | `REFLECT_SNAPSHOT_ROOT` | — |
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` | — |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` | 单线仓库不需要它：规格未配 ⇒ 明说未启用 |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` | 本仓没有 doctor.json 规格：不查进程/端口活性 ⇒ 明说未启用 |

17 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）；其中 10 道**可未启用**（末列是**声明**理由，不是运行时状态 —— 此刻谁 off 要看 `registry --run <相位>`）。
<!-- /AUTO:GATES -->
