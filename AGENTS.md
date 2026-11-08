# AGENTS.md

**这个文件只干一件事：告诉 agent「套件在哪、规矩在哪、状态在哪」。**

它不写规矩本身。规矩的唯一产地是 `zreflect/doc.py` 的 `RULES` 数据表（在套件里，
有判据守着）。这里再抄一遍就是第三份拷贝 —— 本仓对「必须一致的两份」的唯一处置
是**配对账器**，而手抄的文档没法对账。

## 套件在哪

Einfacht 是**可移植的套件**，不是本仓专有。全部判据都住在 `zreflect/`：

```
zreflect/gate.py         rc 契约 / off 态 / 三档自证 / 相位执行器
zreflect/machine.py      机器行协议：哪一行是机器行（唯一产地）
zreflect/i18n.py         本体零语言 + 语言包（zh/en/de）
zreflect/doc.py          文档体系：纪律登记表（规矩的唯一产地）
zreflect/next.py         「接着上一轮」采集器（宿主无关：只产 stdout 行）
zreflect/check_*.py      闸门（清单见 registry --gates）
zreflect/lang/<lang>/    语言包；一个都不装也能跑（输出 code+参数）
ruff.toml                静态机器检查的判据（check_lint 读它，CI 读同一份）
reflect-hooks/           钩子入口（只暴露一个口，不抢钩子座位）
harness.py               发现式自证 harness
```

**给人看的**：`README.md`（英文，默认）/ `README.zh.md` / `README.de.md`。
三份是同一条断言的三份拷贝，改一份必须同批改三份（`check_readme_sync.py` 拦）。

## 两段：唯二必须丈量的东西

| 段 | 文件 | 写什么 | 怎么被丈量 |
|---|---|---|---|
| **原则** | [`PRINCIPLES.md`](PRINCIPLES.md) | 每条原则 = 一句话 + 一条判定命令 | 每次提交逐条真跑（`check_facts_replay`） |
| **现在** | [`STATE.md`](STATE.md) | 此刻是什么样；数字一律 `[[键名]]` | `--check` 比机器块与台账 |

原则与状态**都进 `FACTS.json`**（原则的键是 `principle.<id>`），所以它们共用
**同一条复跑路径** —— 没有第二套执行器。

`AGENTS.md` 就是这两份的**路由**。**没有历史文档**：append-only 的经过只在
「当时那个条件」下可复现，复不了的就不占一个会被判的位置。

别的东西（笔记、别处的 md）可以**手动注册**成事实来查，但不在默认面上。

## 怎么跑

```bash
# 开工前：唯二必须丈量的两份（state = 数值，principle = 判定）
python3 zreflect/facts.py --check            # 两份文档的机器块都与台账一致
python3 zreflect/check_facts_replay.py       # 全部原则的判定命令逐条真跑

python3 zreflect/registry.py --run commit   # 全部 commit 相位闸门（ran/off/failed 分列）
python3 zreflect/harness.py                 # 每个闸门先证明自己会红
python3 zreflect/facts.py                   # 重量测
python3 zreflect/facts.py --render-doc      # 渲染机器块（不带文件名 = 状态文档）
```

`registry.py --run` 是**执行面的唯一入口** —— 不要 glob `check_*.py`。什么该跑由各闸门
的 `GATE = gate.meta(...)` 声明行决定，相位是声明字段（`runs_at`）。

## 想知道什么，去问谁

| 想知道 | 去看 |
|---|---|
| 有哪些原则、各自跑什么命令 | `PRINCIPLES.md` 的 `AUTO:RULES` 块 |
| 某条原则现在过不过 | `python3 zreflect/facts.py --get principle.<id>` |
| 全部原则逐条复跑 | `python3 zreflect/check_facts_replay.py` |
| 每个旋钮的语义 | `python3 zreflect/knobs.py --list` |
| 闸门清单 | `python3 zreflect/registry.py --gates` |
| 此刻什么在跑、什么在 off | `python3 zreflect/registry.py --run commit` |
| 数字是多少 | `python3 zreflect/facts.py --get <键>` |

## 记忆是自动的

不用在压缩前手工整理 handoff。`zreflect/next.py` 在每次调用时**现算**一段
「接着上一轮」（从 git 状态长出来：未推送提交、工作区、悬案）：

```bash
python3 zreflect/next.py                    # 纯文本行，不落盘
REFLECT_LANG=zh python3 zreflect/next.py    # 换输出语言（只影响这条命令）
```

**它不落盘** —— 每轮都变的东西不占一个会被判的位置，所以 `facts.py --check`
里没有它，也没有「文档说它自动、其实从没写过」的中间态。

⚠️ **套件不管宿主怎么接。** 它不认任何编辑器的钩子协议、不写任何宿主的配置、
不校验任何宿主的 schema。要接进会话开始钩子，使用方自己加一层薄壳读它的
stdout —— 这是「在别的仓里用」的一部分，不是套件的事。宿主那边的接入是否
真的生效，只有那个宿主自己的日志能回答。

## 在别的仓里用

把 `zreflect/` + `reflect-hooks/` 拷过去，然后在那个仓里：

```bash
python3 zreflect/facts.py --init     # 生成合格骨架（不覆盖已有文件）
python3 zreflect/facts.py            # 量一遍
python3 zreflect/facts.py --render-doc STATE.md   # 渲染机器块
python3 reflect-hooks/install.py --chain          # 接钩子
```

`--init` 会建 `STATE.md` / `PRINCIPLES.md` / `AGENTS.md` / `README.md` /
`retractions.json` / `questions/`（含一条示例悬案）/ `Einfacht.env`，并且：

- **`STATE.md` 里预先放好 `<!-- AUTO:FACTS -->` / `<!-- AUTO:GATES -->` 标记**
  —— 没有它们 `--render-doc` 会 `FATAL: facts.markers_missing_render`，
  而标记字符串此前只住在 `render.py` 源码里；
- **`Einfacht.env` 按实际生成的文档写** `REFLECT_DOCS` / `REFLECT_READMES`
  —— 默认值假设你已经有六份文档（STATE / AGENTS / PRINCIPLES / README×3），
  新仓只有一份 README，不写这一份每个闸门都会报「找不到 README.zh.md」。

跑完上面四条，`registry --run commit` 应当 **failed=0 / fatal=0**。
若不然，先看 `--init` 的输出里有没有 `already exists, left alone`（旧文件没被覆盖）。

⚠️ **`docs/` 不行** —— 那在套件外面，闸门扫不到。

⚠️ 量测对象默认是**套件自己**（`zreflect/measure_example.py` 的占位实现）。
量你自己的项目：在 `Einfacht.env` 里设 `REFLECT_MEASURE_MODULE=<你的模块>`，
或直接改 `zreflect/facts.py` 的 `measure_example()`。不设就量套件 —— 那时
`STATE.md` 里的数字是**关于 Einfacht 的**，不是关于你的项目的。

旋钮全在 `zreflect/knobs.py` 登记，名字型旋钮（`REFLECT_DOCS` / `REFLECT_READMES`
/ `REFLECT_QUESTIONS` …）在那个仓的 `Einfacht.env` 里改，不改代码。

## 本仓规程：接线与防直写

本仓是**套件仓**：别的 agent 对它的产出一律走 issue 反哺（带复现与根因
file:line），由 owner 会话裁决后落补丁，**不许直写**。

**各跑各的**：每个仓自己接 git 钩子（`reflect-hooks/install.py --chain`），
要「接着上一轮」就在对应仓手跑 `python3 zreflect/next.py <仓>`。宿主不代管
（`host_agnostic` 原则不动）——不在用户级 config 注册会话钩子。

防直写用 OS 层 advisory 锁（宿主侧 `einfacht-lock.sh`，不进判据面）：
`chmod -R a-w` 全树，缓存目录（`.ruff_cache` / `__pycache__` 等）保持可写，
否则 ruff 写不了缓存、`check_lint` 会 FATAL。同用户进程能 chmod 回来，挡的是
误写与莽撞，不是对抗。

```bash
~/.kimi-code/hooks/einfacht-lock.sh claim <session_id>  # 登记 owner
~/.kimi-code/hooks/einfacht-lock.sh seal                # 收工时加锁
~/.kimi-code/hooks/einfacht-lock.sh open                # 自己要写时解锁
~/.kimi-code/hooks/einfacht-lock.sh release             # 全放
```

直写先撞 EACCES；绕过 chmod 硬写视为越界。

## 不懂就问

**如果非无人值守目标处于进行状态，则不懂就问**（只有无人值守时才许自行推断补齐）。
