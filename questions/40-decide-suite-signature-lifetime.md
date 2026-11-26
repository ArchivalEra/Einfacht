# 40: 裁决套件发布签名的有效期

**What to build:** 确定 `suite.release` 的有效期及现有消费仓的升级方案。`trust_core.verify_suite_sig` 沿用普通回执校验，而审批仓 `approver/store.py` 的签发默认有效期为一小时，并限制复用已发布序号。

**Blocked by:** [Q38](38-consolidate-trust-facts-and-impact.md) 结案，以及 owner 裁决发布签名有效期和两仓上线顺序。

**Status:** ready-for-human

**Settling:** None -- 第一交付物是两仓兼容性自测，覆盖旧客户端、发布签名的过期行为、吊销和序号回退。

需要裁决发布签名是否长期有效，以及旧客户端如何升级到支持新规则的版本。保留 `SUITE.sig` 的上游来源验证、签名吊销和版本防回退，普通变更回执和委托继续使用各自的期限。

裁决记录进本案后才进入实现。审批端和消费端的兼容性自测通过后，填写可回放的 `Settling` 并结案。
