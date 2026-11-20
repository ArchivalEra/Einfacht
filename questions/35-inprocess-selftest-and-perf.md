# 35: 进程内 selftest 调度与全量门禁性能优化

**What to build:** 在不恢复外部环境变量 `EINFACHT_RUN_CACHE` 信任口的前提下，解决 Q33 移除跨进程共享缓存后 `registry.py --run commit --all` / `check_questions.py` 重复拉起子进程导致耗时膨胀（约 4–6 分钟）的问题：
1. **进程内直调受封签 `--selftest`**：在 `zreflect/gate.py`（`run_cmd_cached`）及调用方识别受封签 `zreflect/*.py --selftest`（含 `&&` 链中拆解出的单个 `--selftest` 项）时，优先在当前进程内复用已加载模块并直接执行 `selftest()` / `_cases()`（完整捕获 stdout/stderr 与返回码，并共享 `_INPROC_CACHE`），避免反复启动新 Python 进程与重复初始化。
2. **不可伪造的运行期去重 / 调度复用**：对于必须走 `subprocess` 的命令（如 `check_facts_replay` / `check_questions` 内部重放），仅当运行期由父进程生成一次性临时密钥/HMAC 校验或进程内调度器直接复用同轮已验证结果时才允许命中缓存，彻底拒绝外部预设假缓存。
3. **红例自证与耗时回归约束**：补充进程内执行失败时仍返回非零 `rc`、伪造缓存仍未命中且重跑的 `★` 会红自测，并实测 `python3 zreflect/registry.py --run commit --all` 完整通过且显著提速（不跳过任何门禁或已解决悬案）。

**Blocked by:** [questions/34-wire-seal-auto-sync-and-anchor-origin.md](34-wire-seal-auto-sync-and-anchor-origin.md)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是在 `zreflect/gate.py` 实现受封签 `--selftest` 进程内直调与捕获输出/返回码的原型及会红自测用例（证明失败红例在进程内直调下仍返回 `rc!=0`）。

## 复跑方式

```sh
python3 zreflect/gate.py --selftest && python3 zreflect/registry.py --run commit --all
```
