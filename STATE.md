# 活状态（示例）

这个文件演示**活状态文档**该怎么写：正文只写「现在是什么」，**数字一律引用台账键**，
不手抄。机器维护的块在文件末尾。

- 本仓的脚本数：[[py_files]]（引用，不是手抄）。
- 本仓的文档数：[[md_files]]。
- 本仓 Python 代码行数：[[py_lines]]。

> ⚠️ 上面三行就是正确写法。若把最后一行写成「本仓有 486 行 Python」，
> `check_facts.py` 会报**正文裸数字** —— 因为那个数字从写下的那一刻起就开始腐烂：
> 代码一增减，它就成了假话，而没人会记得回来改它。引用键名则永远不会过期。
> （判据默认查 ≥ 100 的整数，`REFLECT_NAKED_MIN` 可调 —— `1`/`2` 这类小数字
> 遍地都是，查了全是噪音；围栏代码块 / 行内代码内的数字豁免，复跑命令天然带数字。）

## 现在是什么

- **两道守卫生效中**：重测时掉条（键没了）与改口（值换了）都会拒绝写盘，除非显式
  `--allow-drop` / `--accept-changes`（后者支持逐条：`--accept-changes=k1,k2`
  只放行列出的键，其余照旧拒绝）。
- **闸门在线**：清单见文末的闸门名录机器块（发现式名录从各闸门的声明行渲染
  —— 手写清单已退役：手写的那份实测漂过，ab/locks/pins 并入的当天清单就少了
  三道、道数也数错了，且没有任何闸门拦得住；叙述现在从声明行派生，加闸门 =
  落一个声明行，机器块自动长出来）。复跑闸门每条 `cmd` 逐字复跑（stdout 必须
  等于值；贵事实可挂 witness 见证来源 —— 每提交真跑，issue #5；可挂 calibrate
  校准仪器 —— 每提交对已知正样本真跑，issue #6 ①）。
- **钩子有持久的旋钮载体**（issue #8）：pre-commit / pre-push 在一切
  之前经**可拔插件** `reflect-hooks/einfacht-env.sh` 加载
  `reflect-hooks/Einfacht.env`（没有时回落仓库根的
  `Einfacht.env`；都没有 ⇒ 全部回落默认名）—— git 不把自定义环境
  变量传给 hooks，只在 shell 里 `export` 的 `REFLECT_*` 钩子看不见。
  删掉插件 ⇒ 带守卫的 source 行跳过，钩子回落纯环境变量（机制可拔）。
  形状：`reflect-hooks/Einfacht.env.example`。
- **开工预检 doctor**（issue #10，**小插件、不是闸门**）：
  「文件不变量全绿」≠「环境还活着」—— 声明式活性预检
  `zreflect/doctor.py`（规格 `doctor.json`，旋钮
  `REFLECT_DOCTOR`；`{"checks": [{kind: http / docker /
  port-free, …, why}]}`，「必须活着」与「必须空着」两类
  断言；stdout 裸值契约 `ok` / `DOWN: <哪条>`；每条探测
  带超时 `REFLECT_DOCTOR_TIMEOUT` 默认 2 秒）。**故意
  不进发现式名录**：查的是会死的东西，挂 pre-commit
  频率错 —— 开工前手动跑（`gates-selftest.sh` 点名一次
  证明它能红）。活性是瞬时事实 ⇒ 不进台账 replay。
- **一条悬案**：见 `questions/01-example.md`。
- **CI 正面执行同一判据**：`gates` workflow 每推跑 `facts.py --check`
  + 发现式名录里的全部闸门（每条 `cmd` 真的逐字复跑）；`readme-sync`
  查三语同批。闸门清单以文末机器块为准 —— 这里不写数字，手写数字一定会漂。
  本地 hook 只约束跑过 install.sh 的机器（issue #4 ②）。

## 那条示例翻案

活状态里提到被推翻的断言时，**必须带更正标记**，否则 `check_retractions.py` 会报。
下面这行的写法是合法的（它记录了 R-001，并标明了它已被推翻）：

> ZCODE_REFLECT_TYPO 这条是**已翻案的示例**，见 `retractions.json` 的 R-001。

<!-- AUTO:FACTS -->
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `md_files` | **7** | 2026-10-10T13:18:09+0800 | `find . -name '*.md' -not -path './.git/*' | wc -l` |
| `md_lines` | **2176** | 2026-10-10T13:18:09+0800 | `find . -name '*.md' -not -path './.git/*' -exec awk 'FNR==1{b=0} /<!-- AUTO:FACTS -->/{b=1} !b' {} + | wc -l` |
| `py_files` | **27** | 2026-10-10T13:18:09+0800 | `find . -name '*.py' -not -path './.git/*' | wc -l` |
| `py_lines` | **5046** | 2026-10-10T13:18:09+0800 | `find . -name '*.py' -not -path './.git/*' -exec cat {} + | wc -l` |

4 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。

| 闸门 | 它挡住什么 | 消费的旋钮 |
|---|---|---|
| `check_ab.py`（A/B 闸门） | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` |
| `check_envfile.py`（env 文件闸门） | 守钩子的 REFLECT_* 载体（旋钮 typo / 指向缺失 / 空值） | `REFLECT_ENV_FILE` |
| `check_facts.py`（事实闸门） | 块一致性 / 裸数字 / 坏引用 | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` |
| `check_facts_replay.py`（复跑闸门） | 台账 cmd 逐字复跑（裸值契约：stdout 必须等于值） | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` |
| `check_instruments.py`（仪器生命周期闸门） | 恒常检测（first_seen）+ 被证伪量法登记 | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` |
| `check_invariants.py`（不变量闸门） | 声明式不变量：仓库文件必须/不得含某片段（grep 级） | `REFLECT_INVARIANTS` |
| `check_locks.py`（锁定源闸门） | 锁定源清单（URL + 文件 + sha256 的内容指纹） | — |
| `check_pins.py`（pin 闸门） | 派生树 pin 一致性（stamp commit / dirty / 版本串对读） | `REFLECT_PINS` |
| `check_questions.py`（悬案闸门） | 未结案的问题必须挂一个能跑的结算件 | `REFLECT_QUESTIONS` |
| `check_readme_sync.py`（三语 README 闸门） | 语言版本是同一条断言的三份拷贝：结构互链 + 每次推送同批 | `REFLECT_READMES` |
| `check_retractions.py`（翻案重现检测） | 被推翻的断言不许悄悄回来当现状 | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` |
| `check_stale.py`（陈旧断言检测） | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |

13 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->
