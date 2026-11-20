# 26: 悬案与 `PRINCIPLES` 防篡改锁及极简带外审批验签契约

**What to build:** 防止干活 Agent 擅自修改/弱化已立案悬案（`Settling:`、问题清单、`wontfix`）或擅自修改/删改/停用 `PRINCIPLES`（`PRINCIPLES.md`、`zreflect/doc.py` `RULES`、`REFLECT_NO_PRINCIPLES` 及涉及核心规则的 `--reseal`），并建立**功能收口、宿主无关**的带外审批验签契约：审批面仅聚焦**仓库名称**与受控范围（`zreflect/`、`reflect-hooks/` 及受锁的 `questions/*.md` / `PRINCIPLES.md` / 开关声明）的 **diff**，支持单次批准、限时放权与即时收回；`zreflect/` 仅用公钥离线校验 Ed25519 回执与锚定基线。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含干活 Agent 私改既有悬案 `Settling:` / 问题正文或标 `wontfix` 且无有效审批回执被拦截、私改/删除 `PRINCIPLES.md` 或 `zreflect/doc.py` `RULES` 或设 `REFLECT_NO_PRINCIPLES=1` 且无审批回执被拒、无审批对 `zreflect/doc.py` 执行 `--reseal` 被拒、可插拔闸门无审批回执 `OFF:` 被拒、篡改已批文件内容导致 `target_sha256` 不符被拒、合法 Ed25519 回执验签通过且锚定更新后 CI 重跑稳定通过）

## 实测问题清单

1. **`questions/*.md` 对干活 Agent 完全开放自由修改，验收标准无防篡改锚点**（`zreflect/check_questions.py`、`zreflect/facts.py`、`zreflect/seal.py`）：
   - `FACTS.json` 有 `guard` 防篡改、`zreflect/` 有 `SEAL.json` 锁哈希，但 `questions/*.md` 无任何锁定机制。
   - 干活 Agent 可直接把已立案悬案的 `Settling:` 改弱为 `python3 -c "raise SystemExit(0)"`、删减 `## 实测问题清单` 条目、或擅自改为 `Status: wontfix` 并直接通过 `check_questions.py`。
   - **目标裁决**：悬案立案锚定后，干活 Agent 只能把 `Status` 推进到 `resolved` 并跑通既有 `Settling:`（或从 `none -- first deliverable` 首次补齐真实 `Settling:`）；任何对既有 `Settling:` 的改动、问题正文删改或标 `wontfix`，必须附带有效审批回执并同步推进锚定基线。
2. **`PRINCIPLES`（`PRINCIPLES.md`、`zreflect/doc.py` `RULES` 与 `REFLECT_NO_PRINCIPLES`）同样缺乏审批锁与防绕过锚点**（`zreflect/doc.py:98-174, 198-203`、`zreflect/seal.py:232-258`、`zreflect/registry.py:349-356`、`zreflect/check_facts.py:31-35, 110-124, 163-164`、`zreflect/check_facts_replay.py:123, 138`、`zreflect/knobs.py:54`）：
   - `doc.RULES` 是 `PRINCIPLES.md` 全部纪律的唯一源头；`zreflect/doc.py` 虽在 `SEAL.json` 内，但 `seal.reseal()` 与 `registry.py --reseal=` 无任何审批回执校验，干活 Agent 修改/弱化 `doc.RULES` 后直接 `--reseal=zreflect/doc.py` 并运行 `facts.py --render-doc` 即可全部通过。
   - `PRINCIPLES.md` 本身无防篡改锚点：直接删除 `PRINCIPLES.md` 或设置 `REFLECT_NO_PRINCIPLES=1` 会令 `doc.accepts_principles()` 静默返回 `False`，使 `check_facts` 与 `check_facts_replay` 跳过全部原则校验；`PRINCIPLES.md` 标题与导语行也不在 `SEAL.json` 与 `AUTO:RULES` 比对范围内。
   - **目标裁决**：`PRINCIPLES` 作为“不变的设计纪律”，**任何**增/删/改 `doc.RULES`、修改或删除 `PRINCIPLES.md`（除 `facts.py --init` 按已封核心模板首次初始化外）、启用 `REFLECT_NO_PRINCIPLES`、或涉及 `zreflect/doc.py` 的 `--reseal`，都必须附带对应动作与目标 SHA-256 的有效审批回执；无回执一律拦截。
3. **缺少功能收口、宿主无关（`host_agnostic`）的带外审批与离线 Ed25519 验签契约**（`zreflect/registry.py`、`zreflect/knobs.py`、`zreflect/seal.py`）：
   - 经实测，仅用 `akr` + `ssh-keygen -Y sign` 存在**盲签**问题；而引入整套企业级访问平面过重。审批契约应刻意**功能缩减**：审批界面与申请载荷只聚焦**仓库名称**与受控范围（`zreflect/`、`reflect-hooks/` 的 diff，以及受锁的 `questions/*.md`、`PRINCIPLES.md`、退场开关变更），不做泛化全仓或任意命令审批。
   - **带外控制面边界**：签名私钥与放权/吊销状态必须运行在干活 Agent 无法读取或改写的隔离进程/远端控制面（不绑定特定宿主工具），人类在明文看到**仓库名 + diff + 单次/限时**后签批，并可随时提前收回（Revoke）已放出的限时委托。
   - **门禁离线验签与基线分离**：`zreflect/` 仅持审批公钥本地验签 Ed25519 回执（校验 `repo + action + prev_sha256 + target_sha256 + expires_at` 及未吊销状态）；变更落盘时推进受锚基线，避免后续离线 CI 重跑 `check_questions --all-resolved` 或 `check_facts_replay` 因短期回执过期而误挂。

## 复跑方式

```sh
python3 zreflect/check_questions.py && python3 zreflect/check_facts.py && python3 zreflect/check_facts_replay.py && python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit
```
