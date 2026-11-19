# 14: 平台接线、封存、旋钮与 Git Hook 漏洞（`registry` / `seal` / `knobs` / `hook`）

**What to build:** 收口执行入口 `registry`、`SEAL.json`、`knobs.py` 与 `reflect-hooks/hook.py` 中的绕过口与静默退化，确保名录对账、封存边界与推送校验无盲区。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --selftest && python3 zreflect/seal.py --selftest && python3 zreflect/knobs.py --selftest && python3 reflect-hooks/hook.py --selftest —— rc=0 ⇒ registry/seal/knobs/hook 漏洞全部收口；rc≠0 ⇒ 仍有执行入口或 hook 绕过

## 实测问题清单

1. **`registry.py --run <phase>` 不调用 `problems()`，也不拒非法阶段参数**（`zreflect/registry.py:121-134, 217-232, 292-307`）：
   - `_main_run` 仅调 `runnable(phase)`，跳过 `problems(gs, missing)`：即使 `knobs.json` 损坏/含幻影键、存在未声明模块或孤儿 `check_*.py`、`SEAL.json` 被篡改，`--run commit` 仍可能返回 `rc=0`。
   - `_arg_after` 在 `registry.py --run --badflag` 时静默回落 `"commit"`；`selftest_modules()` 与 `plugins()` 只检查源码中是否存在 `"--selftest"` 子串（注释即可骗过）。
2. **`seal.py` `include_gates=False` 允许删改内置核心闸门，且漏封关键位置**（`zreflect/seal.py:53-68, 93-121, 205-248`、`zreflect/registry.py:321-328`）：
   - `verify_problems()` 固定传 `include_gates=False`：从 `SEAL.json` 删掉内置闸门（如 `check_facts_replay.py`）并重算 `tree_sha256`，再将其改为 `sys.exit(0)` 仍通过校验。
   - 显式跳过 `zreflect/__init__.py` 与子目录；`ruff.toml` 若被删且移出 `SEAL.json` 也可通过；`--reseal` 无任何前置保护，修改核心文件后直接 `--reseal=ALL` 即洗白（且局部重封不先行校验未改条目）。
3. **`knobs.py` 分隔解析、类型校验与源码环境读取扫描漏口**（`zreflect/knobs.py:170-182, 203-259`）：
   - `history_secs()` 分割 `,` 后不 `.strip()`（`"1, 2"` 生成 `" 2"` 导致节号匹配静默失效）。
   - `_config_entry_problems()` 拒绝 `REFLECT_READMES: ""`（与 `readme_names()` 及文档语义冲突），且不校验 `number`/`flag` 值格式、不区分 `file` 与 `dir`。
   - `_environ_read_key` 漏掉 `os.getenv` / `from os import environ` / `.pop`；`_is_test_node` 对任何顶层 `ast.If` 与含 `"case"` / `"_ok"` 的函数直接放行。
4. **`reflect-hooks/hook.py` 遗漏未跟踪 `FACTS.json` 与新分支 `git log` 走全史**（`reflect-hooks/hook.py:65-123, 162-185`）：
   - `_has_unstaged_facts` 只跑 `git diff --name-only`，当 `FACTS.json` 为 untracked（`??`）或工作区已删除时返回 `False`，`commit` 会直接把据此渲染的 `STATE.md` 提交而落下 `FACTS.json`。
   - `_push_readmes_together` 在新分支（`rsha == ZERO_SHA`）或 `rev-list` 回退分支传入 SHA 列表给 `git log --name-only` 时**未加 `--no-walk`**，会一直追溯到仓首提交，只要历史上曾同时改过三语 README 即永远放行单文件推送；且忽略 `git log` 的 `_rc`，tag/空 stdin 返回 `0`。
   - `push` 阶段检查当前工作区而非待推送提交（脏工作区可掩盖坏 `HEAD`），且 `_sh` 未显式设 `cwd=repo`。

## 复跑方式

```sh
python3 zreflect/registry.py --verify-seal && python3 zreflect/knobs.py --selftest
```
