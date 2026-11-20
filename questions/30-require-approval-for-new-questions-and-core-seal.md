# 30: 新建悬案立案强制审批与全核心 `--reseal` 审批锁

**What to build:** 堵住“初始靶子画错”和“只锁 `doc.py` 不锁其他核心文件”两处结构性口子：
1. **立案即受审（`question.create`）**：当 `ANCHORS.json` 存在且出现未在 `ANCHORS.json` 登记的新 `questions/*.md` 时，`zreflect/approval.py` 不再返回 `[]` 放行，而是强制要求 `action="question.create"` 的 Ed25519 审批回执（审批通过并写入 `ANCHORS.json` 后，后续 `ready-for-agent -> resolved` 结算仍免审批但强制实跑）。
2. **全核心 `--reseal` 审批锁（`seal.core`）**：`zreflect/seal.py` 将 `--reseal` 的审批检查从仅限 `zreflect/doc.py` 扩展到全部受封目标（`zreflect/doc.py` 对应 `seal.doc`，其余受封核心文件对应 `seal.core`，由 `ANCHORS.json` 开关/默认在下游 `--init` 启用）。

**Blocked by:** [questions/29-fix-receipt-bundle-gitignore-and-repo-id.md](29-fix-receipt-bundle-gitignore-and-repo-id.md)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是未锚定新悬案被 `approval.receipt_required(action='question.create')` 拦截、以及未授权 `--reseal` 非 `doc.py` 核心文件被 `seal.core` 拦截的会红自测用例。

## 复跑方式

```sh
python3 zreflect/approval.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/registry.py --run commit
```
