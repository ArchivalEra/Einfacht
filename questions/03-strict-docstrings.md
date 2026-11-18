# 03: `strict` 模式还剩 708 条 docstring——它们该不该存在

**What to build:** 回答一个问题，不是清理一批文件：**这个套件的函数该不该有 docstring**。
`check_explain` 的 strict 模式已经能量出代价（708 条），但「量出来」不等于「该删」。

**Blocked by:** None (can start immediately)

**Status:** wontfix

**Settling:** python3 zreflect/check_explain.py --selftest —— rc=0 ⇒ 注释纪律已改由复杂度额度模型接管（本单 wontfix，由 04 吸纳）；rc≠0 ⇒ 注释闸门自证失效

## 现状（量出来的，不是意见）

    REFLECT_COMMENTS=strict  ->  708 条

    public     221     公开接口上的 docstring
    private    382     私有函数上的
    _cases*    105     自证夹具上的

    分布：criteria 64 / facts 62 / knobs 60 / gate 55 / registry 51 /
          check_i18n 35 / 其余 31 个文件若干

`mismatch` 模式（超长才算）现在是 1 条，已裁决保留；`--temporal` 是 0。
所以本单问的是**剩下的这 708 条该不该整体清掉**，与「超长」和「讲过去」都无关。

## 三种答案，各自是完整立场

**A. `no-docstrings`** —— 用户原话：「复杂到需要写注释的代码，本身就与 Einfacht
生态相斥」。函数本该从签名和函数体读懂；读不懂说明接口不够深，该拆而不是该解释。

   代价：708 条全删。`check_explain` 的 strict 模式变成默认，`mismatch` 退役。
   风险：`_replay_one` 那种 5 分支函数、`_windows_argv` 那种平台特定逻辑，
         删掉说明后新人只能逆向。

**B. `contracts-keep`** —— 区分「契约」与「辩解」：能写清返回形状、失败模式、
顺序约束、不变量的 docstring 留下；解释「为什么这么设计」的进 HISTORY。
这正是 `--classify` 已经在做的事，只是现在只作用于超长 docstring。

   代价：要定一条「什么叫契约」的判据，而这条判据本身很难机械化
         （试过「契约词」，111 条里 98 条命中，分辨率等于零）。
   风险：判据定不下来，最后靠人治。

**C. `mixed-by-visibility`** —— 公开接口要 docstring（调用者只有它可以依），
私有函数不要（调用者是同一个文件的代码，能读函数体）。

   现实数据支持这个切法：public 221 / private 487，比例接近 1:2.2。
   代价：要定「什么算公开」——本仓的下划线约定够用，但 `check_*` 模块的顶层
         函数没有下划线却在内部使用。

## 为什么不是一个「清理任务」

708 条可以派人删完，但那是**在没有裁决的情况下执行**。若最终答案是 B 或 C，
删掉的契约就要靠 git 历史捞回来——而本仓刚建了 HISTORY 来说明「不可复现的东西
不占会被判的位置」，git 历史不等于可读的约定。

所以顺序必须是**先裁决、再执行**，而裁决是数据（`explain-strict.json`），能被
判据读入并与 `REFLECT_COMMENTS` 的行为对账。

## 已经付过的学费（不要重走）

- 「段数 > 参数数 + 2」当判据 → 无参函数全中，零参数不是宽
- 「契约词出现即算契约」→ 111 条里 98 条命中，两个方向都判不出
- 「字符数 / 行数比值」→ 三行函数配 150 字是合理的
- 调高 `DOC_MAX_CHARS` 让它不报 → 那是「把判据调松到不报」，与 `off_is_visible`
  同形的反面

## 与悬案 02 的边界

02 结的是「哪些**超长** docstring 需要整改」，已 resolved（109 条 → 0 history /
1 contract / 0 undecided）。
本单问的是「**所有** docstring 该不该存在」，范围更大且是设计决策。
两单不重叠：02 的结果是 03 的输入之一（`mismatch` 现在只剩 1 条，说明「超长」
这一维度已经清了，剩下的纯是「要不要有」）。
