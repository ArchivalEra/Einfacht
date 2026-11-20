# 34: 打通 seal.py 自动提单拉回执并加固本地基线与 CI 兜底

**What to build:** 封堵独立审计发现的 B 类“仍需手工/本地可绕过”缺口：
1. **`seal.py` 接入 `_auto_sync_for_probs`**：`zreflect/seal.py` 的 `_check_reseal_approval` 在遇 `seal.core` / `seal.doc` 缺少回执或过期时，自动调用 `approval._auto_sync_for_probs` 机械提单并拉取已批回执，消除 `--reseal` 链路的手工 `--request` 依赖，并补充会红自测用例。
2. **`ANCHORS.json` 远端基线兜底**：在存在 `origin/main`（或上游分支）时，评估 `check_anchors_integrity` 对 `HEAD:ANCHORS.json` 之外的上游基线校验或明确标注本地 `--no-verify` 仅由 CI `--all` 兜底。
3. **CI 入口防外部环境变量污染**：确保 CI 工作流显式传 `--all` 且清理外部 `EINFACHT_RUN_CACHE` / `EINFACHT_REPLAY_DEPTH` 等变量，杜绝干净工作区或缓存导致零门禁放行。

**Blocked by:** [questions/33-close-env-cache-and-depth-escapes.md](33-close-env-cache-and-depth-escapes.md)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是 `zreflect/seal.py` 触发 `seal.core` 缺回执时自动调用 `_auto_sync_for_probs` 提单并拉取回执的会红自测用例。

## 复跑方式

```sh
python3 zreflect/seal.py --selftest && python3 zreflect/approval.py --selftest && python3 zreflect/registry.py --run commit --all
```
