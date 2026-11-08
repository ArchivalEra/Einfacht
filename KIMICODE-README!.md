# Kimi Code 接入说明（Einfacht）

> 文件名是 `KIMICODE-README!.md`（用户指定，带感叹号）。它不是三语 README
> 之一，`check_readme_sync` 不管它；但它是 `.md`，会被 `md_files` / `md_lines`
> 量到，改完必须走 `facts.py --accept-changes` → `--render-doc` → `--check`。

## 这台机器上的 harness 是什么

Kimi Code 是 Pi 系 harness 的精装修复刻：会话、`config.toml`、hooks、skills 的
形状都像 Claude Code / ZCode，但**钩子注册只有用户级**（`~/.kimi-code/config.toml`
的 `[[hooks]]`），没有按仓挂载这回事。文档原话：*Hook rules live only in your
user-level config.toml and in local plugins — there is no project-level hook
file*。于是「接一个钩子」的真实含义是**给这台机器上所有会话接一个钩子**。

ZCode 时代那种 `.zcode/` 按仓接线在这里不成立；Einfacht 的 `host_agnostic`
原则说得比我们早：套件不认宿主协议，接线是使用方自己的一层薄壳。

## 我们试过什么，为什么全摘了

2026-11-08 的一天里，用户级钩子换了四代，全部回滚：

| 代 | 形状 | 实际后果 |
|---|---|---|
| 1 | 硬编码 Einfacht 路径的 bridge | **Einfacht 的待办被注进 10 个外仓会话**（Shirone 39 次、LLVM-wasm 10 次…），其中「工作区不干净」的话术把别的 agent 引进本仓直写 RFP |
| 2 | vendor-aware bridge | 修了硬编码，但凡有 `zreflect/` 的 13 个仓全被自动接线；老版仓没有 `reflect-hooks/gate.py`，python「can't open file」rc 2 被当成闸门红，**假拦截 LLVM-wasm 37 次提交** |
| 3 | 中央 opt-in 名单 | 仍然是宿主替所有仓做决定，且名单外的仓被静默改了行为 |
| 4 | 仓级 `kimi-hook` + 哑中继 | 最接近正解，但钩子脚本以 `.py` 落进仓根，被 `measure_example` 的 os.walk 扫进 `py_files`（36 vs 台账 35）→ `check_facts_replay` 红；`env_hint` 的提示噪音又被误读成拦截原因 |

**结论**：用户级钩子这个座位本身不适合「按仓注入」。config.toml 里现在
`hooks: []`（备份：`config.toml.bak-20261108-before-remove-hooks`），宿主侧只
留 `einfacht-lock.sh`（`chmod -R a-w` 防直写，缓存目录保持可写）。

## 现在的接线：各跑各的

每个仓自己接自己的，`宿主不代管`：

```bash
# 1. git 钩子（提交/推送时真跑闸门）
python3 reflect-hooks/install.py --chain

# 2. 想要「接着上一轮」时，在对应仓手跑（语言由该仓的 Einfacht.env 定）
REFLECT_LANG=zh python3 zreflect/next.py .

# 3. 或者用本仓自搓的薄壳（AGENTS.md 要求的「使用方自己加的一层」）
printf '%s' '{"cwd":"'"$PWD"'"}' | .kimi-code/hooks/kimi-hook
```

`.kimi-code/hooks/kimi-hook` 是**仓库级薄壳，不注册进任何用户级 config**：
它只认 stdin 里的 `cwd`，向上找最近的「有 `zreflect/` 的 git 仓」，找不到就
静默退出；经 `einfacht-env.sh` 加载该仓的 `REFLECT_*`，走 `activate_or_fatal()`
+ `next.section()` 输出。别的仓复制这份即可，各说各话。

⚠️ 两个实测踩过的坑，写壳时别再踩：

- `python3 - <<'PY'` 的 heredoc 会**占用 stdin**，payload 根本进不去（表现为
  hook 静默绿）。payload 走变量，python 用 `-c`，仓根用环境变量传。
- 别把壳写成 `.py` 放仓根：`measure_example` 会把它算进 `py_files`，台账立刻
  对不上。这个壳是 `/bin/sh`，无后缀。

## 壳的实测记录（2026-11-08，本仓）

| 输入 | 预期 | 实测 |
|---|---|---|
| `{"cwd":"<本仓>"}` | 中文「接着上一轮」段 | rc 0，6 行，含未推送提交/工作区/悬案三段 |
| `not-json` | 静默（不猜、不假装有 0） | rc 0 无输出 |
| `{}`（无 cwd） | 静默 | rc 0 无输出 |
| `{"cwd":"/tmp"}` | 静默（别的仓各跑各的） | rc 0 无输出 |
| 外部 `REFLECT_LANG=en` | 仍按本仓载体出中文 | 中文（载体显式覆盖，符合「各跑各的」） |

## 一个仍然存在的现象

本会话的用户消息开头偶尔还会出现 `<hook_result>` 块——这是**当前进程持有的
旧配置缓存**（config 已 `hooks: 0`，日志里没有钩子执行记录）。新开会话即消失；
不需要为它动 config。宿主 `~/.kimi-code/hooks/einfacht-bridge.py` 留了一个
439 字节的 no-op 文件，只为让缓存了旧条目的在途会话不把「脚本不存在」当硬
错误；重启后可删。

## 想重新接用户级钩子时

先回答：*这次要影响机器上所有会话，谁授权？* 如果答案不是「全部」，就别接
——用仓级薄壳 + 手跑。这就是本仓 `AGENTS.md`「本仓只读锁 + 宿主钩子不接线」
一节的意思。
