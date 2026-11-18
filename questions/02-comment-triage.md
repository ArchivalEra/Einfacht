# 02: 哪些被 `check_explain` 扫出来的函数需要整改

**What to build:** 把 `check_explain` 的 `mismatch` 模式从「110 条，都要改吗」
收窄成「哪些是设计理由伪装成调用契约、哪些是真的契约」。收窄的产物是一条
**更窄的判据**，不是一份人工清单。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/check_explain.py —— rc=0 ⇒ 原分类裁决已由 04 改用复杂度额度模型接管；rc≠0 ⇒ 注释纪律失败

## 为什么不是「列个清单」

110 条 docstring 超长，但**其中哪些真的要改**不是清单能回答的问题。人工清单
的三个毛病这个仓都踩过：

- 清单会漂（手写的名录实测少过三道闸门，且没有判据拦得住）；
- 清单不可复跑（改完代码，清单还写着旧函数名）；
- 清单把判断留给了没有上下文的人（三个月后没人知道当初为什么放过第 7 条）。

所以本单要的不是清单，是让判断**可判定、可复跑、可对账**。

## 已经量到的分层（这是起点，不是结论）

按 `body <= 3` 且 `docstring >= 300 × body` 筛：

    57 个  body<=3 且 doc >= 100x body
    21 个  body<=3 且 doc >= 300x body
     8 个  body<=3 且 doc >= 500x body

抽查 21 个那一档的三个样本，形态一致：它们解释的是**为什么这么实现**，不是
**怎么调用**。

- `gate.zdir` — "Purpose: scan my own source"，后半段讲它是与 `GATE_REPO` 的
  区别（契约），前半段讲为什么需要它（经过）
- `gate.scanned_sources` — "Single source: 两处曾各写一遍"（纯经过）
- `check_questions.is_resolved` — "next.py used to filter `!= resolved`"（纯经过）

## 三条候选判据，各自的已知问题

写这张单之前试过三条，都记下来避免重走：

| 判据 | 结果 | 为什么不行 |
|---|---|---|
| docstring 段数 > 参数数 + 2 | 46 条 | 无参函数全中——零参数不是「宽」，是不需要说明参数 |
| 契约词（must/never/raise/…）出现即算契约 | 111 条里 98 条命中 | 分辨率等于零，两个方向都判不出来 |
| 比值（字符数 / 行数） | 中位 14.3 | 三行函数配 150 字是合理的，比值高不代表有问题 |

## 要建的东西

`check_explain.py --classify`：把每条报告归入三类之一，**分类依据必须是数据，
不是启发式**。

    history      docstring 里带时态标记（used to / first version / 曾经 / 当时 …）
                 ⇒ 它讲的是经过，进 HISTORY.md
    contract     不含时态标记，且函数是公开接口（无前导下划线）
                 ⇒ 它可能在说调用约定，保留（但需要人确认一次）
    undecided    不含时态标记，但函数是私有的
                 ⇒ 判不出来，必须人裁决

`undecided` 是这张单真正要产出的东西：**它把「110 条都要看」压成「N 条要裁决」**，
而 N 是可复跑算出来的。

## 结算条件

`--classify` 的 rc：
- `0` — `undecided` 为空（每条都归了类，且归类可复跑）
- `1` — `undecided` 非空，逐条裁决后写入一个声明文件（`explain-dispositions.json`），
        每条附理由；下一次跑应降到 0
- `2` — 分类器本身没实现

**注意**：结算要求的是「没有未裁决项」，不是「110 条都改完了」。改不改 docstring
是各仓的裁决；这条判据只保证**每条都有结论**。

两个不同的数，不要混：
- `--classify` rc=0 ⇒ 三类都有结论，没有 `undecided`（本单的结算条件）
- `REFLECT_COMMENTS=mismatch` 仍可能报**合约类**残留（那是经裁决保留的，不是
  未裁决项）；`strict` 更是另一条判答——它报的是「任何 docstring」，与本单的
  「哪些是设计理由伪装成契约」不是同一个问题

## 不要做的事

- 不要生成人工清单（见上）
- 不要一次性重写 110 个 docstring（不可验证的动作去满足判据，本仓反对这个）
- 不要把 `mismatch` 的阈值调到能过为止（那是「把判据调松到不报」，与 `off_is_visible` 同形的反面）

## 结论

分类器建成后按文件独占分区拆函数，共处理 109 条：

    history    61 -> 0     经过段（used to / 上一版 / 某次实测故事）直接删
    contract   30 -> 1     真契约保留；宽接口由职责拆分成内部函数承载
    undecided  18 -> 0     私有函数逐个读全文裁决，无一条需要人工豁免

`--classify` 现返回 rc=0（history 0 / contract 1 / undecided 0）。唯一残留的
`ledger.fact` 归 `contract`：它的 docstring 全是调用约定（cmd 只打印值、无
opt-out、calibrate 成对），不是设计理由，删掉会让调用者用错。按
codebase-design 的 deletion test，它该留。

**因此 `mismatch` 模式仍报 1 条、`strict` 模式仍报 704 条**——那是经裁决保留
的契约，不是本单未清的项。本单结的是「哪些需要整改」这个问题，不是「所有模式
零告警」。

范围说明：下面两个例子来自前序提交 `19c2d84`，不是本次 109 条拆分的一部分；
列在这里只是说明「契约留 / 经过删」的形状。
- `next._git` 758 -> 304：留下「失败返回 None、不伪造 0」的契约，删掉
  「为什么不用 runner」的经过
- `ledger.fact` 2908 -> 853：删掉 `replay:false` 与 witness 的历史，四个调用
  层级的约定全部保留；顺带把 witness 整套移除（参数 9 -> 7）

**重要**：拆的是 docstring 里的经过段，不是函数行为。签名、返回值、调用点在
每个文件都用 AST 对比确认与改动前一致；`PINNED:` 声明一个都没动。

## 一条留给未来的观测

`strict` 模式报 704 条，其中 **484 条（68%）是私有函数或 `_cases` 自证辅助**
（`_cases` 本身 18 条、`_cases_fixture` 10 条、`_cases_pack` 3 条，其余是各类
`_helper`）。也就是说 strict 主要撞的是**自证代码**，不是产品代码。

这不是「strict 判错了」——自证代码也是代码，同样该能从签名读懂。但它解释了
为什么 strict 在真实仓库里会先崩溃：先倒下的是测试，不是被测物。

`mismatch` 没有这个偏斜（110 条里公开/私有大致各半），所以它是更可落地的
起点。若某个仓要开 strict，建议先清 `_cases*` 一族，那是数量的主要来源。
