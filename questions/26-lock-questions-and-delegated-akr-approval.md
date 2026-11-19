# 26: 悬案防篡改锁与两级委托审批验签契约（`akr` 一次授信 → 审批 Agent 签批）

**What to build:** 防止干活 Agent 擅自修改/弱化已立案悬案的 `Settling:` 与问题清单或擅自标 `wontfix`，并建立宿主无关的两级委托审批验签契约（人类通过 `akr` MFA 一次签发委托证书给独立审批 Agent 公钥 → 审批 Agent 签发绑定目标 SHA-256 的短期凭证 → Einfacht 验签放行悬案修改与可插拔闸门 `OFF:`）。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含干活 Agent 私改既有悬案 `Settling:` / 问题正文或标 `wontfix` 且无有效委托签名链被拦截、可插拔闸门无审批凭证 `OFF:` 被拒、合法两级委托签名链验签通过）

## 实测问题清单

1. **`questions/*.md` 对干活 Agent 完全开放自由修改，验收标准无防篡改锚点**（`zreflect/check_questions.py`、`zreflect/facts.py`、`zreflect/seal.py`）：
   - `FACTS.json` 有 `guard` 防篡改、`zreflect/` 有 `SEAL.json` 锁哈希，但 `questions/*.md` 无任何锁定机制。
   - 干活 Agent 可直接把已立案悬案的 `Settling:` 改弱为 `python3 -c "raise SystemExit(0)"`、删减 `## 实测问题清单` 条目、或擅自改为 `Status: wontfix` 并直接通过 `check_questions.py`。
   - **目标裁决**：悬案立案锚定后，干活 Agent 只能把 `Status` 推进到 `resolved` 并跑通既有 `Settling:`（或从 `none -- first deliverable` 首次补齐真实 `Settling:`）；任何对既有 `Settling:` 的改动、问题正文删改或标 `wontfix`，必须附带有效审批凭证。
2. **缺少宿主无关（`host_agnostic`）的两级委托审批验签契约**（`zreflect/registry.py`、`zreflect/knobs.py`）：
   - 外部 `akr`（Akamai MFA）适合做人类一次性根授信，不宜由干活 Agent 直接持有或每次打断人工；审批 Agent（无论运行在 Antigravity、T3code 还是本地独立 Socket 后方）与干活 Agent 之间需要**密码学边界**而非仅靠“不同会话”自律。
   - 需在 `zreflect/` 内实现纯本地、宿主无关的验签接口（不直接调用 `akr`）：验证 `Root 公钥 (akr 一次授信签发委托证书) -> 审批 Agent 公钥 -> 具体批准凭证（绑定 repo + action + target_sha256 + 有效期）`，同时覆盖受核准的可插拔闸门 `OFF:`、悬案改写/`wontfix` 等高风险动作。

## 复跑方式

```sh
python3 zreflect/check_questions.py && python3 zreflect/registry.py --run commit
```
