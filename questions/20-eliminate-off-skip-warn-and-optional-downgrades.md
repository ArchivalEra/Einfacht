# 20: 收口 `OFF:` 核准边界并彻底清零 `SKIP:`/`WARN:` 与 `optional` 降级

**What to build:** 禁止核心闸门 `OFF:`，仅允许可插拔闸门在“显式声明 + 经委托核准（见 26 号悬案）”下退出 `OFF:`；同时彻底清零 `SKIP:`、`WARN:` 与 `"optional": true` 的静默放行口。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** `python3 zreflect/registry.py --run commit && python3 zreflect/registry.py --run start-of-work && python3 zreflect/gate.py --selftest && python3 zreflect/check_ab.py --selftest && python3 zreflect/check_pins.py --selftest && python3 zreflect/check_locks.py --selftest && python3 zreflect/check_facts.py --selftest && python3 zreflect/check_facts_replay.py --selftest` -- rc=0 => core OFF/SKIP/WARN/optional guards hold; rc!=0 => bypass regression

## 实测问题清单

1. **核心与插拔闸门仍可通过默认配置或环境变量静默 `OFF:` (`rc=0`)**（`knobs.json:1-4`、`zreflect/knobs.py:61`、`zreflect/registry.py:331-335`、`.github/workflows/gates.yml:57-58`）：
   - `knobs.json` 与 CI 均未设置 `REFLECT_REQUIRED_GATES`，默认 `registry --run commit` 下 6/16 闸门呈 `OFF:` 仍返回 `rc=0`。
   - 设置 `REFLECT_REPLAY=off`、`REFLECT_COMMENTS=off`、`REFLECT_READMES=`、`REFLECT_HISTORY=`、`REFLECT_NO_PRINCIPLES=1` 或删除 `ruff.toml`/`secrets.json`，均可把核心闸门关成 `OFF:` 而 `rc=0` 放行；可插拔闸门的 `OFF:` 也缺乏显式声明与核准验证（与 26 号悬案联动）。
2. **`gate.run_phase` 把 `stderr` 的 `SKIP:` 误计为 `ran`，且 `SKIP:` 仍退出 `0`**（`zreflect/gate.py:232-234, 475, 504-514`、`zreflect/registry.py:325-335`）：
   - `run_spec_gate()` 将 `SKIP:` 打到 `stderr`、将 `ok_msg` 打到 `stdout`，`run_phase` 只扫描第一行非空输出，导致任何 `"optional": true` 跳过在汇总中都伪装成 `ran`。
   - `check_ab.py:118`、`check_pins.py:94,118`、`check_locks.py:87` 仍支持 `"optional": true` 自愿降级为 `SKIP:` (`rc=0`)。
3. **`WARN:` 与占位/回退放行**（`zreflect/facts.py:481-485`、`zreflect/check_facts.py:37-45`、`zreflect/gate.py:309-317`、`zreflect/check_stale.py:268-278`、`zreflect/examples.py:293-305`）：
   - `facts.measure()` 未设 `REFLECT_MEASURE_MODULE` 时仅输出 `WARN:` 并以示例占位指标返回 `rc=0`。
   - `REFLECT_NAKED_MIN=abc` 与 `REFLECT_REPLAY_TIMEOUT=abc` 仅打印警告并静默回退默认值（`100` / `10.0`）。
   - `check_stale` 缺配置返回 `rc=0`，`--list` 把 `rc=1` 强行改写为 `rc=0`；`examples.py` 在平台不匹配时 `skipped += 1` 仍退出 `0`。

## 复跑方式

```sh
python3 zreflect/registry.py --run commit && python3 zreflect/registry.py --run start-of-work
```
