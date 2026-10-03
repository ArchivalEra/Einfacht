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
- **六道闸门在线**：`check_facts`（块一致性 / 裸数字 / 坏引用）、`check_facts_replay`
  （台账 `cmd` 逐字复跑，stdout 必须等于值；贵事实可挂 witness
  见证来源 —— 每提交真跑，issue #5）、`check_retractions`（翻案重现；
  扫描面 = `REFLECT_DOCS` 清单）、`check_questions`（悬案必须挂结算件）、
  `check_readme_sync`（三语 README 同批：结构互链 + 推送集必须含全部名单）、
  `check_stale`（sha 出处 / 退役名 / 测龄：`REFLECT_STALE_DAYS` 开启）。
- **一条悬案**：见 `questions/01-example.md`。
- **CI 正面执行同一判据**：`gates` workflow 每推跑 `facts.py --check`
  + 六道闸门（每条 `cmd` 真的逐字复跑）；`readme-sync` 查三语同批。
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
| `md_files` | **8** | 2026-10-03T09:18:07+0800 | `find . -name '*.md' -not -path './.git/*' | wc -l` |
| `md_lines` | **1376** | 2026-10-03T09:18:07+0800 | `find . -name '*.md' -not -path './.git/*' -exec awk 'FNR==1{b=0} /<!-- AUTO:FACTS -->/{b=1} !b' {} + | wc -l` |
| `py_files` | **15** | 2026-10-03T09:18:07+0800 | `find . -name '*.py' -not -path './.git/*' | wc -l` |
| `py_lines` | **2049** | 2026-10-03T09:18:07+0800 | `find . -name '*.py' -not -path './.git/*' -exec cat {} + | wc -l` |

4 条事实。
<!-- /AUTO:FACTS -->
