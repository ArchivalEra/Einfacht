# 36: 封堵 knobs.json 未验锚、未封签脚本同进程劫持、无 ANCHORS 删 SEAL 归零等 5 项审计漏洞

**What to build:** 修复消费仓（`ArchivalEra/S26-1_202609`）对新版 `bbb19a4` 实测发现的 5 项安全与完整性漏洞：
1. **`knobs.json` 运行时锚点与 `REFLECT_QUESTIONS` 防切换**：`ANCHORS.json` 锚定 `knobs_sha256` 与 `questions_dir`，`approval.check_knobs_anchor()` 在运行时校验 `knobs.json` 未被静默篡改（`registry.py --run`、`check_facts.py`、`check_questions.py` 均接入），`_eval_questions_anchor` 同步比对 `anchors["questions_dir"]`。
2. **隔离未封签消费方脚本与核心 `sys.modules`**：`zreflect/seal.py` 提供 `is_sealed_target()`，`gate.py` 的 `default_runner` 与 `_is_ro_suite_call` 仅对已封签核心文件走进程内直调，未封签自定义门禁一律走独立子进程；`facts.py` 的 `measure()` 对未封签 `measure_*.py` 改用独立子进程执行并解析 JSON，杜绝运行时内存猴子补丁。
3. **禁止无 `ANCHORS.json` 时删 `SEAL.json` + `REFLECT_NO_PRINCIPLES` 归零**：当 `zreflect/seal.py` 存在（真实套件目录）而 `SEAL.json` 缺失时，`registry.py`、`gate.py`、`facts.py` 必须报告 `seal.missing`（FATAL），不再静默跳过。
4. **修复 `check_retractions.py` 在 `depth >= 1` 跳过翻案复燃扫描**：仅在 `depth >= 1` 时跳过可重入 `evidence` 命令重跑，保留全部翻案条目执行文档复燃与 schema 检查。
5. **补齐独立 `check_anchors_integrity()` 与 `impact.py` 多提交基线**：`check_principles_repo` 与 `check_off_gates_anchor` 均校验 `check_anchors_integrity()`；`impact.py` 在无 `@{upstream}` 时先检查 `origin/main..HEAD` / `origin/master..HEAD`，均不存在时返回 `None` 触发全量兜底，避免只看最后 1 个提交。

**Blocked by:** [questions/35-inprocess-selftest-and-perf.md](35-inprocess-selftest-and-perf.md)

**Status:** resolved

**Settling:** python3 zreflect/approval.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/gate.py --selftest && python3 zreflect/check_retractions.py --selftest && python3 zreflect/impact.py --selftest -- rc=0 => knobs.json anchor, unsealed subprocess isolation, missing SEAL fatal, depth>=1 resurfacing scan, and multi-commit impact fallback hold; rc!=0 => Q36 regression

## 复跑方式

```sh
python3 zreflect/approval.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/gate.py --selftest && python3 zreflect/check_retractions.py --selftest && python3 zreflect/impact.py --selftest
```
