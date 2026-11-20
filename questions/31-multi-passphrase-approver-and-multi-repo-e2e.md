# 31: 审批端多口令/多审批员支持与多仓库并发端到端实测

**What to build:** 验证“一把私钥 + 多审批员口令 + 多业务仓库并发”的真实可用性：
1. 审批端支持在 `admin.pass` 配置多行 `approver_name:passphrase`（或单行口令），在审批/拒绝记录 `decided_by`，并使用带盐/PBKDF2 口令校验。
2. 编写不依赖外部 root 守护进程的隔离端到端自测（临时双仓库 `RepoA` + `RepoB` + 临时多口令审批服务实例），实测验证：多仓库各自独立 `<repo>#<seq>` 编号、多文件回执包互不覆盖、跨仓回执重放被拒、不同审批员口令均可通过及记录 `decided_by`。

**Blocked by:** [questions/30-require-approval-for-new-questions-and-core-seal.md](30-require-approval-for-new-questions-and-core-seal.md)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是双仓多口令端到端测试脚本/自测（覆盖 `RepoA` 与 `RepoB` 并发提单、回执隔离、多口令鉴权与 `decided_by` 留痕）。

## 复跑方式

```sh
python3 zreflect/approval.py --selftest && python3 zreflect/registry.py --run commit
```
