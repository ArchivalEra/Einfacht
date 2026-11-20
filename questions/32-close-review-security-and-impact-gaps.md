# 32: 审批系统 3 列双向 RBAC 重构与评审安全/影响面缺口修复

**What to build:** 重构审批端链路并封堵 44 提交对抗性评审发现的核心缺口：
1. **审批系统双向 RBAC、自动触发与双向 Webhook 重构**：`einfacht-approver` 与 `approval.py` 端到端链路支持 3 列 `approver:repos:passphrase` 仓库范围授权与跨仓越权 `403` 拦截、`POST /requests` 幂等去重与 120s 拒单冷却、分仓库 1.5s webhook 批量合并与双向路由（提单唤醒审批端 + 批/拒后唤醒对应编码端）、`_auto_sync_for_probs` 在门禁检测未授权/过期回执时自动机械提单与拉取回执、以及 `GET /api/delegations` / `POST /api/revoke` / `decided_by` 回执签名。
2. **本仓启用 `lock_core`**：在 `ANCHORS.json` 启用 `"lock_core": true`，使 `seal.core` 在 Einfacht 自身仓内同样生效。
3. **`ANCHORS.json` 防删除与防篡改**：`load_anchors` 同时核对 `git cat-file -e HEAD:ANCHORS.json` 封堵 `git rm ANCHORS.json`；`check_anchors_integrity` 对账 `HEAD:ANCHORS.json`，拦截未经授权削弱 `lock_core`/`revoked_ids`/`repo`/`principles`/`off_gates`/`questions` 的篡改。
4. **`impact.py` 覆盖动态 `measure_*.py`**：`zreflect/impact.py` 将 `zreflect/measure_*.py` 映射到 `zreflect/facts.py` 依赖图及 `.py` 静态/密钥闸门。
5. **Worktree、换行与解析对齐**：`_default_receipt_path` 通过 `git rev-parse --git-dir` 兼容 worktree；`canonical_payload` 统一 `ensure_ascii=False`；`_strip_status_settling` 对齐大小写不敏感解析；`seal.py` 使用规范化 `_entry_for` 哈希与 `file` 参数精准过滤。

**Blocked by:** [questions/31-multi-passphrase-approver-and-multi-repo-e2e.md](31-multi-passphrase-approver-and-multi-repo-e2e.md)

**Status:** resolved

**Settling:** python3 zreflect/approval.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/impact.py --selftest -- rc=0 => 3-col repo-scoped RBAC, idempotency, _auto_sync_for_probs auto-submit/deny-surface, ANCHORS integrity, worktree git-dir, seal normalization, and measure_*.py impact pass; rc!=0 => Q32 regression

## 复跑方式

```sh
python3 zreflect/approval.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/impact.py --selftest && python3 zreflect/registry.py --run commit
```
