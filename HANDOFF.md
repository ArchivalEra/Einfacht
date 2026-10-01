# HANDOFF · 事实系统（zcode-reflect）接续说明

> 给接手维护的人。本文只讲三件事：**现状、怎么接、别踩什么**。
> 「怎么用」读 `README.md`，「硬规矩」读 `AGENTS.md` —— 本文不重复它们，只补交接该有的东西。
> 全文不依赖任何特定项目；这套是通用库，所有文件名/路径都可配置（见 README「配置」节）。

## 0. 一句话：你接手的是什么

一套让「测出来的数字」**只被生产一次**的小系统：`zreflect/` 库 + 6 道闸门 + git hooks + 发现式自证。
README 是三语的（英语默认 / 中文 / 德语），三份是同一条断言 —— pre-push 要求每次推送同批更新。
当前全部绿（接手时的健康判据见 §2，逐条可复跑）。

**三条不能破的不变量**（README/AGENTS 是它们的展开，违反了系统存在的意义就没了）：

1. **数字只生产一次**：台账（默认 `FACTS.json`）是唯一产地；活状态文档用 `[[键名]]` 引用，不手抄。
2. **闸门必须能证明自己会红**：每个检查器带 `--selftest`（三类用例：正常不报 / 该报的必须报 / 空输入必须报）；
   `gates-selftest.sh` **发现式**扫描 `zreflect/check_*.py` —— 新增闸门自动入列，缺 `--selftest` 就红。
3. **断言有生命周期**：活状态只写实测；推断进 `questions/` 且必须挂可跑的结算件；
   被推翻的进 `retractions.json`，`check_retractions.py` 会在旧说法重新出现时报错。

## 1. 心智模型（60 秒版）

- **事实** = {键， 值， 复跑命令， 出处， measured_at}，由 `measure()` 采集。
  写 `measure()` 先读 `zreflect/collect.py` 的四条契约（只读持久盘 / 不引入
  会自己变的输入 / 读不到就 `unavailable()` 明说 / 贵的测量做缓存）。
  `measured_at` 是采集时刻的**记录**，不是测量输入（拿它当输入 ⇒ `--check`
  永不收敛，issue #3 ②）。
- **渲染** = `facts.py --render-doc` 把台账写进活状态文档末尾的 AUTO 块（**别手改**，hook 会重算并 `git add`）。
- **闸门** = 六道：`check_facts`（块一致性 / 正文裸数字（`REFLECT_NAKED_MIN`
  可配、代码块内豁免）/ 坏引用）、`check_facts_replay`（台账 `cmd`
  逐字复跑，stdout 必须等于值 —— 裸值契约见 `ledger.fact()`）、`check_retractions`（翻案重现，
  扫描面 = `REFLECT_DOCS`）、`check_questions`（悬案必须挂结算件）、`check_readme_sync`（三语 README
  同批：默认模式查结构互链，`--changed` 模式查推送改动集；pre-push 与 CI 都走后者）、
  `check_stale` + `living.py`（活状态 vs 历史章节的口径；另带测龄报警 `REFLECT_STALE_DAYS`，
  不配 = 明说未启用）。
- **守卫** = `facts.py` 写盘前的两道闸：**掉条**拒绝（`--allow-drop` 显式放行）、**改口**拒绝
  （`--accept-changes`；`--accept-changes=k1,k2` 只放行列出的键，其余照旧拒绝，issue #3 ①）。

## 2. 接手当天（30 分钟，逐条可复跑）

1. `sh reflect-hooks/install.sh` —— 把 pre-commit / pre-push 装上（它们会自动重算机器块 + 跑全部闸门）。
2. 手动复验（hooks 会跑的那几条），**全绿才继续**：

   ```sh
   python3 zreflect/facts.py --render-doc STATE.md
   for g in zreflect/check_*.py; do python3 "$g" || exit 1; done   # 发现式名录，别列清单
   ```

3. `sh gates-selftest.sh` —— 应输出「发现 6 个闸门，全部能红」，另有跨仓库换名自证 6/6。
4. **故意弄红一次再恢复**（练手感，10 分钟）：在 `STATE.md` 正文写一句含 ≥100 裸数字的话 →
   `check_facts` 应红（裸数字）→ 删掉恢复变绿。再试：把 `FACTS.json` 某键的值改掉 →
   `facts.py` 应拒绝写盘并提示 `--accept-changes`。
5. 读 README 的「四个部件 + 第二组」「它不做什么」「配置」三节。

## 3. 日常操作（每条一个入口）

- **重测**：`python3 zreflect/facts.py`（无参 = 重测 + 渲染 + 写盘；结尾打印每条事实
  的测龄，如「3 天前测的」）。
- **值变了** → `--accept-changes`（先确认是真实测出来的，不是输入坏了；只确认其中
  几条 ⇒ `--accept-changes=k1,k2` 逐条放行，其余照旧拒绝）；**键没了** → `--allow-drop`
  （先想清楚为什么掉：输入消失？测量坏了？掉条是**信号**，不是麻烦）。
- **新增事实**：写 `measure()` → 跑 → 渲染 → 提交（复跑命令跟着进台账）。
- **新增闸门**：`zreflect/check_<名>.py` + `--selftest`（自证里必须有"该报的必须报"用例；
  收尾必须有机器摘要行 `=== N PASS / M FAIL ===`，照 `gate.selftest()` 写自动有）。
- **翻案**：`retractions.json` 追加 `R-xxx`（text/why/evidence/fixed_in），活状态里的旧句子**带更正标记**。
- **悬案**：`questions/NN-*.md`，头部 `**Settling:**` 指向一个**可跑**的结算件（写不出结算件的推断 = 猜想）。
- **三语 README**：改任何一份 = 这次推送的改动集**三份全含**（pre-push 缺一份拒推，CI 同判据）。
  改判据/口径时三份都要动 —— 语言漂移就是口径漂移的开始。换语言名单：`REFLECT_READMES`。

## 4. 已知边界（别当新 bug 重复发现）

- `check_questions` 的结算件判据只看路径**首词**（README 已记此限制）。
- `check_facts` 的裸数字判据：阈值 `REFLECT_NAKED_MIN`（默认 100，1/2 这类小数字遍地
  都是，查了全是噪音）；围栏代码块 / 行内代码内豁免（复跑命令天然带数字）。
- **测龄报警默认关**：`REFLECT_STALE_DAYS` 不配 = 测龄规则明说未启用；开了之后，
  `measured_at` 缺失/坏 ⇒ 也报（读不到就明说，不许猜 0）。
- **纯函数保持安静**：`problems()` 一类的纯函数不许 print —— 自证输出是给人核对的接口（issue #1 ③）。
- 自证输出末尾的机器摘要行（`=== N PASS / M FAIL ===`）是 runner/CI 的读接口，
  `gates-selftest.sh` 会校验它在（issue #3 ③）。
- 闸门有盲区：只看「已暂存/已登记」输入的检查器，看不见从未登记的文件；新增目录后主动看一眼。
- 守卫失效的典型方式是「只在真的该报警时才崩」—— 所以反向断言不是可选项。

## 5. 接手时的状态快照

- HEAD 以 `git log -1` 为准；origin 已配置。
- 六道闸门全绿；发现式自证 6/6；跨仓库换名自证 6/6（证明没有硬编码路径）；两道守卫在线。
  三语 README 同批判据：pre-push（本地）+ GitHub Actions（正面）双层执行。
- `questions/` 里有 1 张**示例**悬案（它存在的意义是示范 `Settling:` 的写法，看完可删）。
- 来源与 License：见 README 末两节。

## 6. 想深入时的顺序

`README.md`（为什么 / 怎么用 / 配置）→ `AGENTS.md`（七条纪律 + 硬坑）→
`zreflect/collect.py`（采集器契约）→ `zreflect/gate.py`（闸门平台与自证约定）→
`gates-selftest.sh`（发现式 runner，**别把它改回手写清单**）。
