# 10: 假命令闭环清零（`Settling:` / `evidence` / `--accept` / `doc.enforced_by`）

**What to build:** 让「要求写可复跑命令」的地方真正执行并决定通过与否，消除“只查字符串长得像命令、从不执行”的假闭环。

**Blocked by:** None (can start immediately)

**Status:** needs-triage

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含 `Status: resolved` 但 `Settling:` 实际 `rc=1`、`retractions.evidence` 实际失败、`facts.py --accept` 传入假值）

## 实测问题清单

1. **`questions/*.md` 的 `Settling:` 从不被执行，且与 `Status: resolved` 解耦**（`zreflect/check_questions.py:121-161`、`zreflect/doc.py:45-74`）：
   - `check_questions.py` 未 import `subprocess` / `gate.run_cmd`，只检查 `rc=`/`⇒`/`=>` 子串、首词 pathish 文件存在及 `starts_with_interpreter`。
   - 临时仓实测：`Status: resolved` + `Settling: python3 -c "raise SystemExit(1)"` 返回 `rc=0`；`Status: resolved` + `Settling: none -- 第一交付物` 也返回 `rc=0`。
   - 事后重放现存 `01`–`09` 单：`08`/`09` 在无 `mypy` 环境下 `rc=1`，无任何门禁暴露已结案单失效。
2. **`retractions.json` 的 `evidence` 只查语法不执行**（`zreflect/check_retractions.py:45-57`）：
   - 仅调 `gate.prose_in_exec_problems`；且 `{"retractions": []}` 直接 `rc=0`。
3. **`facts.py --accept KEY VALUE CMD SOURCE` 不校验 `CMD` 输出**（`zreflect/facts.py:684-697`）：
   - 只检查 `argv[3]` 非空（甚至未过 `prose_in_exec_problems`），未运行 `CMD` 验证 `stdout == VALUE` 即写入台账。
4. **`doc.RULES` 中 8 条原则只查“脚本存在”，不查是否启用或通过**（`zreflect/doc.py:26-35, 105-149`）：
   - `doc.enforced_by('<script>')` 仅检查脚本在 `registry.gates()` 名录内；即使 `check_explain` 从未在提交/CI 运行或 `REFLECT_COMMENTS=off` 仍返回 `rc=0`。`--all-runnable` 与 `selfcert_harness` 同样只做静态存在性检查。

## 待裁决设计点

1. `Status: resolved` 是否强制禁止 `NONE_LIKE` 并现场调用 `gate.run_cmd` 要求 `rc == 0`？（`wontfix` 如何防滥用：是否要求非空理由且禁止冒充 `resolved`？）
2. 重放成本控制：是否区分“刚改写为 `resolved` 的单（pre-commit/diff）”与“全量 `resolved` 回归（CI）”？
3. 是否将 `evidence` 与 `Settling:` 的运行收口进 `check_facts_replay` 同一套执行器，避免出现第二套 runner？

## 复跑方式

```sh
python3 zreflect/check_questions.py && python3 zreflect/check_retractions.py
```
