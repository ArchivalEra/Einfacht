# 38: 收敛 Trust、Facts 和 impact 的重复实现

**What to build:** 先统一 Trust 和 Facts 中重复的判断，再让 impact 一次计算受影响的 gate 和模块。

**Blocked by:** None

**Status:** ready-for-agent

**Settling:** None -- 第一交付物是能区分重复实现与统一实现的自证。先在重构前看到红例，落地后将本字段换成实际可回放的自测命令。

## 实施范围

- Trust：让 `--submit` 和 `--sync` 共用五项预检。将问题文件规范化成快照，让工作树和锚点共用变更分类及免审批流转判定。保留 `HEAD → ANCHORS.json → 工作树` 两段校验及各入口现有的退出码和读写行为。重复点在 `zreflect/trust.py` 的 `_sync_settled`、`_all_anchor_probs`、`_eval_existing_question` 和 `zreflect/trust_core.py` 的 `_eval_existing_question_entry`。
- Facts：计量与回放共用原则事实组装，生成块校验共用一处块比较。保留 `doc.RULES` 单一来源、回放对真实原则键的识别，以及 `check_facts` 对正文引用和未登记数字的检查。对照 `zreflect/facts.py`、`zreflect/check_facts.py` 的 `problems` 和 `zreflect/check_facts_replay.py` 的 `replay_all`。
- impact：由 `affected_plan` 同时给出受影响的 gate 和模块，去掉 `harness.py` 重建依赖图的路径。保留全量回退、gate 注册身份和自测入口。

## 停点

自证需覆盖同一问题变更在两段校验中的结果、原则事实的组合和机器块比较，以及同一 impact 计划的 gate 与模块结果。可回放的 `Settling` 命令、`python3 zreflect/registry.py --run commit --all` 和 `python3 zreflect/harness.py` 均通过后，记录结果并将状态改为 `resolved`。交付到此为止。[Q39](39-unify-doc-seal-authorization.md) 和 [Q40](40-decide-suite-signature-lifetime.md) 各自等待裁决。
