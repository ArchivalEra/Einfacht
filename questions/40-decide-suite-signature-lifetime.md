# 40: 裁决套件发布签名的有效期

**What to build:** 确定 `suite.release` 的有效期及现有消费仓的升级方案。`trust_core.verify_suite_sig` 沿用普通回执校验，而审批仓 `approver/store.py` 的签发默认有效期为一小时，并限制复用已发布序号。

**Blocked by:** None -- Owner 已裁决并允许与 Q39 并行落地。

**Status:** resolved

**Settling:** python3 zreflect/trust_core.py --selftest && python3 zreflect/trust.py --selftest -- rc=0 => suite.release verification ignores expiry while enforcing revocation/scope/seq/sig and legacy compat upgrade passes; rc!=0 => Q40 regression

## 裁决与实施结论

- `zreflect/trust_core.py` 的 `verify_suite_sig` 永不校验 `suite.release`（`SUITE.sig`）过期时间，保留 `upstream_repo`、吊销列表（`revocations`）、`suite_seq` 防回退与 Ed25519 验签；普通变更回执与委托仍保留各自期限。
- `approver/store.py` 为 `suite.release` 签发远期兼容时间戳（`SUITE_RELEASE_COMPAT_EXPIRES_AT = 4102444800`，即 `2100-01-01T00:00:00Z`），保证未升级的老 v2 客户端也能直接原地 `--upgrade`。
- 升级摩擦消除一并落地：`--allow-drop` 接受版本升级期下线的旧事实键、清理旧 `pre-push` hook 包装、缺 `PRINCIPLES.md` 且未设 `REFLECT_NO_PRINCIPLES` 时按需补建并重渲染、拒绝 `src == dst` 自覆盖误删、`lock_core=false` 升级同步刷新 `principles_md_sha256`。
- 上线顺序：先验证并部署审批端更新，再重封签并发布新版 `SUITE.sig`。
