# 39: 裁决 doc.py 的套件封印授权

**What to build:** `zreflect/doc.py` 已列入 `SEAL.json`，Trust 还用 `principles.doc_py_sha256` 检查该文件并要求 `seal.doc`。评估能否由套件授权统一覆盖该文件。

**Blocked by:** [Q38](38-consolidate-trust-facts-and-impact.md) 结案，以及 owner 裁决 `lock_core=false` 的授权语义。

**Status:** ready-for-human

**Settling:** None -- 第一交付物是裁决后的迁移自测，覆盖锁定和未锁定消费仓、旧锚点和旧回执。

目前 `trust.verify_problems` 在 `lock_core=false` 时跳过套件授权，`trust.check_principles_repo` 仍可能要求 `seal.doc`。需要裁决未锁定消费仓是否继续单独保护 `doc.py`，据此决定旧字段和待处理回执怎样迁移。保留 `principles.edit`、`principles.disable` 和签名升级时仅重渲染生成块的现有行为。

裁决记录进本案后才进入实现。迁移自测与全量门禁通过、发布前的消费仓升级行为得到验证后，填写可回放的 `Settling` 并结案。
