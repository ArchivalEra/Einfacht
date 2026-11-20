# 21: 强制全量重放已结悬案/撤回、封堵深度逃生与 Hook/Push 检查面

**What to build:** 让已提交的 `Status: resolved` 悬案在 CI 与全量校验中真正重跑，堵死 `EINFACHT_REPLAY_DEPTH` 逃生与 `principle` `SKIP:` 伪过，并补齐本地 Hook 的 `start-of-work` 与 `push` 提交面校验。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** `python3 zreflect/check_questions.py --selftest && python3 zreflect/check_retractions.py --selftest && python3 zreflect/check_facts_replay.py --selftest && python3 reflect-hooks/hook.py --selftest` -- rc=0 => full replay and hook checks hold; rc!=0 => replay or hook regression

## 实测问题清单

1. **`check_questions.py` 默认与 CI 均不重跑已提交的 `resolved` 悬案**（`zreflect/check_questions.py:240-258, 275-282`、`.github/workflows/gates.yml:57`、`reflect-hooks/hook.py:183-184`）：
   - 未传 `--all-resolved` 时仅检查 `git status --porcelain` 中的脏文件；用 `--no-verify` 提交坏 settler 或后续破坏其依赖脚本后，CI 与后续局部运行均永久放行。
   - `Status: wontfix` 无需理由且从不执行验证。
2. **`EINFACHT_REPLAY_DEPTH >= 1` 静默禁用悬案与撤回命令重放**（`zreflect/check_questions.py:241-242`、`zreflect/check_retractions.py:150`）：
   - 只要环境变量 `EINFACHT_REPLAY_DEPTH >= 1`，两道闸门直接跳过全部 `Settling:` / `evidence` 执行并返回 `rc=0`（而非像 `check_facts_replay.py` 那样受控报错或仅豁免自引用）。
3. **`check_facts_replay.py` 对 `kind="principle"` 未拦截 `SKIP:` 输出**（`zreflect/check_facts_replay.py:38`）：
   - 仅检查 `kind == "off"`，原理命令输出 `SKIP: ...` 且 `rc=0` 仍判定通过。
4. **`reflect-hooks/hook.py` 漏跑 `start-of-work` 且 `push` 检查错对象**（`reflect-hooks/hook.py:85-88, 164, 183-184`）：
   - 本地钩子从不运行 `registry --run start-of-work`（`check_explain` / `check_history` 本地盲区）。
   - `push` 阶段对脏工作区而非待推送提交跑 `facts --check` 与 `registry --run commit`；stdin 为空时 `_push_readmes_together` 直接返回 `True`。

## 复跑方式

```sh
python3 zreflect/check_questions.py --all-resolved && python3 zreflect/check_retractions.py
```
