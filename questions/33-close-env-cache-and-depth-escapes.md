# 33: 封堵外部环境变量（RUN_CACHE / REPLAY_DEPTH / REFLECT_QUESTIONS）与策略逃逸口

**What to build:** 封堵独立审计发现的 A 类“假通过/跳过校验”环境变量与策略缺口：
1. **`EINFACHT_RUN_CACHE` 防外部伪造**：`zreflect/gate.py` 仅信任本进程 `with_run_cache` 创建并持有的受保护缓存目录（或附带进程启动 nonce/HMAC 校验），拒绝直接复用外部预置的未签名缓存 JSON；并在自测中证明外部预置假缓存无法绕过命令重放。
2. **`REFLECT_QUESTIONS` 防锚点脱靶**：`zreflect/approval.py` 的 `check_questions_against_anchor` 与 `check_anchors_integrity` 不允许仅因外部环境变量 `REFLECT_QUESTIONS` 偏移就跳过 `ANCHORS.json["questions"]` 中已锚定目录的核对（除非配置来源为仓内 `knobs.json` 或受控审批）。
3. **`EINFACHT_REPLAY_DEPTH` 防外部跳检**：`zreflect/check_questions.py` 与 `zreflect/check_retractions.py` 对外部预设 `EINFACHT_REPLAY_DEPTH` 增加父进程/会话校验或签名令牌，防止直接设 `EINFACHT_REPLAY_DEPTH=1/2` 跳过结算与撤回重放。
4. **`FACTS.json` 关键字段与 `Settling: none -> resolved` 加固**：评估并收紧 `FACTS.json` 中 `cmd` 篡改及原 `Settling: none` 升级为弱命令免审的口子，确保仅合法增强受审或受不可弱化约束。

**Blocked by:** [questions/32-close-review-security-and-impact-gaps.md](32-close-review-security-and-impact-gaps.md)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是外部预置假 `EINFACHT_RUN_CACHE`、外部 `EINFACHT_REPLAY_DEPTH=1` 与外部 `REFLECT_QUESTIONS` 偏移被拦截的会红自测用例。

## 复跑方式

```sh
python3 zreflect/gate.py --selftest && python3 zreflect/approval.py --selftest && python3 zreflect/check_questions.py --selftest && python3 zreflect/registry.py --run commit --all
```
