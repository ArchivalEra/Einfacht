# 29: 修复回执自动读取与多文件覆盖、`ANCHORS.json` 白名单初始化与多仓名碰撞

**What to build:** 修复评审发现的下游接入与多文件审批三处硬伤：
1. `zreflect/approval.py` 的 `load_receipt()` 在未设 `EINFACHT_APPROVAL_RECEIPT` 时自动回退读取 `<repo>/.git/einfacht-receipt.json`，并将多文件 `--request --wait` 落盘格式升级为回执包（兼容单张 dict 与 `{"receipts": [...]}`），避免多文件修改互相覆盖、避免用户手动导出环境变量。
2. `.gitignore` 加入 `!/ANCHORS.json`，且 `zreflect/facts.py --init` 自动生成带 `pinned_approver_pub()` 的 `ANCHORS.json`，消除下游仓漏初始化导致静默不锁的风险。
3. 仓库标识 `repo` 优先从 `git remote get-url origin` 提取规范名（如 `ArchivalEra/Einfacht`），无 remote 时才回退 `os.path.basename`，避免多仓同名目录或 worktree 碰撞。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/approval.py --selftest && python3 zreflect/facts.py --selftest && python3 zreflect/examples.py quickstart -- rc=0 => receipt bundle/fallback, ANCHORS.json init/whitelist, and remote repo_id hold; rc!=0 => Q29 regression

## 复跑方式

```sh
python3 zreflect/approval.py --selftest && python3 zreflect/facts.py --selftest && python3 zreflect/registry.py --run commit
```
