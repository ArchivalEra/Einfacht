# AGENTS.md

给在这个仓里工作的 agent 的硬规矩。**这些不是建议，是闸门会拦的东西。**

**如果非无人值守目标处于进行状态，则不懂就问**（只有无人值守时
才许自行推断补齐）。

## 七条纪律

1. **数值/行为只认实测**，并把复跑方式写在断言旁边。
   写不出复跑方式的句子，只能当历史读 —— 不许写成「现在如此」。
   台账里的 `cmd` 由 `check_facts_replay.py` **逐字执行**（stdout 必须是裸值；坏命令 /
   超时 / 没 cmd 都报）——「能复跑」是被每道 pre-commit 重证的断言，不是口号。
2. **数字只生产一次**。文档里引用写 `[[键名]]`，**不手抄数字**。
   `check_facts.py` 会拦正文里的裸数字和指向不存在键的引用。
3. **能编过 ≠ 能用了**。碰运行期行为必须在真实环境里测；构建成功不算功能验收。
4. **断言要能证伪**：新契约至少配一条**反向**断言（该报错的必须报错）。
   每个闸门必须写 `--selftest`，且三类用例齐全：正常不报 / 该报的必须报 / 空输入必须报。
5. **断言有生命周期**：实测 / 推断 / 翻案。
   - 活状态文档里**只写实测**；
   - **推断**写进 `questions/`（作为悬案）或笔记，并注明**哪个实验能结案**；
     写不出结案实验的推断 = 猜想，不许留在活状态；
   - **被推翻**的进 `retractions.json`，`check_retractions.py` 会在它**重新出现在
  `REFLECT_DOCS` 声明的活状态文档里**时报错 —— 扫描面**有界**：清单外的文件（源码注释、
  配置）不在面内，这是写明的缺口（issue #2 ②），不是「查过」。
6. **写文档先懂"活状态"**（`zreflect/living.py`）：历史章节（`REFLECT_HISTORY_SECS` 声明）
   里的数字是"当时如此"；行内带历史/退役/已翻案标记的行也是。除此之外——**含无编号
   章节**——全是活状态，闸门会拿它跟台账对账。想把旧值留在正文里，**必须带标记**。
7. **写 `measure()` 先读采集器契约**（`zreflect/collect.py`）：只读持久盘、不引入会自己
   变的输入（墙上时钟 / HEAD sha ⇒ `--check` 永不收敛）、读不到就 `unavailable()` 明说
   （**绝不编 0**）、贵的测量用机器块回收做缓存。`measured_at`（采集时刻戳，issue #3 ②）
   是**记录**不是测量输入 —— 渲染「测于」列与测龄用它，拿它当输入会让 `--check` 永不收敛。

## 提交前

```bash
sh gates-selftest.sh                       # 每个闸门先证明自己会红
python3 zreflect/facts.py --render-doc STATE.md
for g in zreflect/check_*.py; do python3 "$g" || exit 1; done
# ↑ 发现式名录，与 hooks / gates-selftest 同款 —— 手写闸门清单本身会漂（issue #2 ②），
#   所以这里也不许列名单：新增 check_*.py 自动被三道地方（hooks / 自证 / 手动）吃到。
```
（装了 `sh reflect-hooks/install.sh` 的话，pre-commit / pre-push 会自动做这些。）

## 硬坑

- **闸门有盲区**：只看「已暂存 / 已登记」的检查器，会看不见从未 `git add` 的文件。
  新增目录后主动看一眼 `git status --short --ignored <目录>`。
- **手写名录一定会漂**。所以 `gates-selftest.sh` 是**发现式**的：它扫
  `zreflect/check_*.py`，缺 `--selftest` 就红。别把它改回手写清单。
  2026-10-07 起这也包括**集合的叙述**：闸门清单 / 红名单 / 插件点名全部从
  `zreflect/registry.py`（各闸门的 `GATE = gate.meta(…)` 声明行，ast 解析）
  派生 —— STATE.md 的闸门清单是渲染出来的 `AUTO:GATES` 机器块，不手写。
- **新闸门 = 纯函数 + 一行声明，别再手抄 run() 尾巴**（2026-10-07）：生命周期
  （旋钮解析 / off 态明说 / 规格加载 / FATAL / problems 循环 / rc 契约 / `__main__`
  尾巴）全在 `zreflect/gate.py`（`off` / `fatal` / `load_spec` / `finish` /
  `main_selftest_or` / `meta`）。实现只写 `problems()` + 一行
  `GATE = gate.meta(名字, 一句话, knobs=(…), name_dependent=?)`；没声明行的
  `check_*.py` 名录不收、`--render-doc` 拒绝渲染。旋钮必须先在
  `zreflect/knobs.py` 登记才算数（扫描面里的未登记记号按幻影/typo 报）。
- **谓词 = 声明，不是文件名**（2026-10-10，C1）：执行面（hooks / CI / runner）
  读 `registry --run <相位>`（= `registry.runnable(phase)`），**不再 glob
  `check_*.py`** —— 「什么该跑」的唯一产地是各闸门的声明行
  `GATE = gate.meta(名字, 一句话, knobs=(…), runs_at="commit"|"start-of-work")`。
  频率是**声明字段**，不是命名意外（doctor 曾经只能靠「它没叫 check_」表达
  「不挂 pre-commit」）。名字不再承重 ⇒ 「孤儿」概念消失（声明了就是闸门）。
  平台模块也声明自己：`MODULE = module_meta(名字, 一句话, selftest=True/False)`
  —— `selftest=True` ⇒ 必须真能 `--selftest` 且被 harness 实跑；`selftest=False`
  ⇒ 正面说「我不用自证」。没声明的 `.py`（非闸门、非 `__init__`）⇒ registry 报。
- **off 与「跑过且通过」必须可区分**（2026-10-10，C2）：`gate.off()` 在 stdout
  打 `OFF:` 机器标记（rc 仍 0 —— off 不是失败）；执行面聚合
  `ran / off / failed`。**「全绿」不许把「没跑」算进去** —— 本仓曾有 8/13 道
  off 而「全绿」不可见，那是本仓立身要消灭的假绿同形。off 是合法状态，
  但必须可见（`registry --run` 单列 off 清单）。
- **必须一致的两份要配对账器**（2026-10-10，C4）：本仓反复踩「两份拷贝会漂」，
  这条纪律同样适用于**代码内部**：声明旋钮 ⊆ 实读旋钮、登记表 ⊆ 三语 README
  配置表、夹具改名集唯一产地（`registry.FIXTURE_RENAMES`）—— 各配一个可复跑
  对账，接进 `registry.problems()`。**没有对账器的「必须一致」= 迟早不一致。**
- **守卫必须吃「该报的必须报」这类断言**。本系统抽出来的那次实践里，一条守卫因为一个
  未定义变量，**从落地起从未生效过** —— 它失效的方式是「只在真的该报警时才崩」。
  没有反向断言的守卫，和没有守卫是一样的。**接线的自证与纯函数的自证同等重要**：
  决策（纯函数，可自证）与执行（写盘 / 打印）分开 —— 见 `zreflect/guard.py`。
  **守卫不许随开关一起消失**（C3）：env 闸门的幻影守卫曾焊在「载体存在」之后，
  本仓没有 Einfacht.env ⇒ 从未执行 —— 判据的家要与开关解耦。
- **三语 README 是同一条断言的三份拷贝**（2026-10-01 起）：`README.md`（英语，默认）/
  `README.zh.md` / `README.de.md`。改任何一份 ⇒ 这次推送的改动集必须**三份全含**，
  pre-push 缺一份拒推、CI 跑同一条判据（`git push --no-verify` 只躲得过本地）。
  改判据/口径时三份都要动 —— 语言漂移就是口径漂移的开始。名单可换：`REFLECT_READMES`。
- **纯函数保持安静**（issue #1 ③）：自证期间 `problems()` 一类的纯函数**不许 print** ——
  自证输出是给人核对的接口（每 case 一行 + 末尾摘要行），被诊断刷屏就没法核对了；
  打印归 `run()`/顶层。同一个提示也会被十几个用例各打一遍。
- **自证必须以机器行收尾**：`=== N PASS / M FAIL ===`（与人读行并存，issue #3 ③）——
  runner/CI grep 固定格式；`gates-selftest.sh` 发现缺行即红。照 `gate.selftest()`
  写的检查器自动有这行，手写自证的要注意。
- **`--accept-changes` 支持逐条**：`--accept-changes=k1,k2` 只放行列出的键，
  其余改口照旧拒绝（issue #3 ①）—— 整批一收会把真坏了的测量一起洗白。
- **裸数字判据可配且豁免代码**：`REFLECT_NAKED_MIN`（默认 100）调阈值；围栏代码块 /
  行内代码内的数字豁免（复跑命令天然带数字，issue #3 ④）。`REFLECT_STALE_DAYS`
  开测龄报警（不配 = 明说未启用，issue #3 ②）。
- **会话 hook 接线按 ZCode schema**（issue #4 ①）：配置文件形状是
  `hooks.events.<Event>`、条目带 `type` 的 hooks 数组、且默认禁用需
  `"enabled": true`（平铺的 `hooks.<Event>` 是 ZCode 看不见的形状）；
  hook 的 stdout 按**严格 JSON 信封**解析（`hookSpecificOutput`），
  纯文本只在手工 tty 跑时发；Stop 类 hook **永远退 0**（`facts.py`
  缺台账时退 2 = 阻塞，会把会话当人质 —— 用 `.zcode/stop-refresh.py`
  壳降级）。
- **每跑必变的量不许裸存**（issue #4 ⑤）：存**一次实测采样** + 配
  `*_stable` 稳定性标记键（消费侧分两档：stable 逐字判、不稳定档
  结构判），或显式 `replay=False` —— 裸存 = 复跑永远红 = 噪音。
- **消费方读台账走 `--get KEY`**（issue #4 ④）：只打印裸值；
  **不要自己解析 `FACTS.json`**（substring 找 `"value"` 会取到
  别的键的值）。
- **贵事实挂便宜见证**（issue #5）：`replay=False` 不等于永不复查 ——
  `fact(…, replay=False, witness=…, witness_expect=…)` 两者同给；
  见证（来源/上下文：「产出它的工具/输入就是我以为的那个」）
  每次提交真跑、判据同裸值契约；只给一个是残缺形状，
  `ledger.fact()` 当场报错。策略（哪条事实挂什么见证）留各仓，
  机制（便宜来源见证每提交真跑）在闸门里。
- **仪器也有生命周期**（issue #6 ①）：复跑契约抓「命令死了」
  （rc≠0），抓不到**仪器静默失真**（命令成功、值稳定、复跑
  永远通过，而它量的根本不是想量的 —— 仪器不认 X 时 `grep -c X`
  成功退出并返回 0）。三件套：`calibrate`/`calibrate_expect`
  （校准样本，fact() 同给契约，复跑闸门每提交对已知正样本真跑）；
  `first_seen`（measure() 自动维护：值不变沿用旧日期、换值取
  今天，恒常检测靠它）；被证伪的**量法**登记进 `instruments.json`
  （`REFLECT_INSTRUMENTS`，schema `{"methods": [{text, why, fixed_in}]}`
  —— 坏量法不许留在台账里）。恒常检测（`REFLECT_INSTRUMENT_DAYS`）
  与量法登记做成**可插拔闸门** `check_instruments.py`：旋钮未配
  = 明说未启用、退 0，特化机制不焊进核心。
- **声明式不变量是可插拔闸门**（issue #7）：「仓库文件必须/不得
  含某片段」做成数据（`REFLECT_INVARIANTS=<json>`，schema
  `{"checks": [{path, must_contain?, must_not_contain?, why}]}`，
  `why` 必填 —— 没理由的检查项没人敢删，会变成僵尸）。
  未配 ⇒ 明说未启用、退 0。与 `calibrate` 正交别混：一个守
  量测仪器，一个守仓库文件本身。**grep 级边界**：分不清
  注释与代码（片段在注释里也算存在）—— 声明式检查的强度
  上限 = 它匹配的文本形态；要更强保证用 `calibrate`（对产物）
  或 `witness`（对来源）。
