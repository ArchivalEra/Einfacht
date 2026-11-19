# 11: 消除静默降级、错误退出码与逃生口（`SKIP:` / `OFF:` / `fatal_exit` / `measure`）

**What to build:** 清零所有“报错/缺依赖/配错参数时悄悄变绿或降级放行”的灰色边界，确保失败必须可见且阻塞。

**Blocked by:** None (can start immediately)

**Status:** needs-triage

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含 `check_pins` 探针非 0 退出、`check_stale` 非数字天数、`facts.measure` 空 `{}` 配合 `SEAL.json`、`harness` 空摘要 `0 PASS / 0 FAIL`）

## 实测问题清单

1. **`SKIP:` 在多道闸门与 `run_phase` 中静默伪装成通过（`rc=0` / `ran`）**（`zreflect/gate.py:458-490`、`check_ab.py`、`check_pins.py`、`check_locks.py`）：
   - `check_pins.py` 的 `stamp_read`/`version_read` 命令非 0 退出或空输出时发 `SKIP:` 并返回 `rc=0`；`check_ab.py` 任一产物不可读发 `SKIP:` 并返回 `rc=0`；`check_locks.py` `"form": "dir"` 不校验内容指纹。
   - `gate.run_phase` 没有 `skipped` 计数，所有 `rc == 0` 且无 `OFF:` 的闸门全部计入 `ran`。
2. **`gate.fatal_exit()` 实际退出 `rc=1` 而非 `rc=2`**（`zreflect/gate.py:96-98`）：
   - 传字符串给 `SystemExit("FATAL: ...")` 导致 Python 返回 `1`，使 `run_phase` 把配置/台账损坏归入 `failed` 而非 `fatal`。
3. **`check_stale.py` 非数字 `REFLECT_STALE_DAYS` 静默关闭老化检查**（`zreflect/check_stale.py:77-85`）：
   - 写错如 `"7d"` 时返回 `None` 静默关停规则，而不像 `doctor` / `check_instruments` 报错 `rc=2`。
4. **`facts.measure()` 空返回顺序漏洞 & 缺省采集器降级**（`zreflect/facts.py:527-542`）：
   - `_attach_core_seal()` 在 `decide()` 之前执行，若 `SEAL.json` 存在，空的 `{}` 采集器返回会变非空并绕过 `guard.empty_ledger`；未配 `REFLECT_MEASURE_MODULE` 时在含 `src`/`lib` 的真实项目里仍仅发 `WARN:` 并退回 `measure_example()` 通过提交。
5. **关键闸门可被 `OFF:` 静默关停 & `harness` 接受 `0 PASS / 0 FAIL`**（`zreflect/harness.py:80-83`、`check_facts_replay.py:133`、`check_lint.py`）：
   - `REFLECT_REPLAY=off` 或缺 `ruff` 令对应闸门输出 `OFF:` 后 `registry --run commit` 仍返回 `rc=0`；仓内无“禁止关闭的关键闸门”声明。`harness.py` 的 `run_gates` 只匹配 `i18n.is_summary`，未校验 `PASS >= 1` 与 `FAIL == 0`。

## 待裁决设计点

1. `check_ab` / `check_pins` / `check_locks` 是否将所有探测失败与缺目标默认改为 `FAILED` (`rc=1`)，仅显式 `"optional": true` 允许 `SKIP:`，并让 `run_phase` 单独统计 `skipped`？
2. 是否增加强制必开列表旋钮（或 `knobs.json` 约束），禁止 CI/生产仓把 `check_facts_replay`、`check_lint` 等关键闸门置于 `OFF:`？
3. `gate.fatal_exit` 是否直接改为 `sys.stderr.write(...) ; raise SystemExit(2)`？

## 复跑方式

```sh
python3 zreflect/harness.py && python3 zreflect/registry.py --run commit
```
