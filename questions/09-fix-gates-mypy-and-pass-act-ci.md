# 09: 修复闸门模块 mypy 问题并跑通本地 act 完整 CI

**What to build:** 清零 `zreflect/check_*.py` 中 `mypy==1.13.0` 暴露的调用歧义、赋值冲突、AST 节点收窄与局部容器注解问题，并完成本仓本地 `act` CI（`gates.yml` `ubuntu-latest`）全流程端到端验证：
1. **调用/赋值/AST 收窄隐患修复**：
   - `zreflect/check_invariants.py`：消除 `_content_problems(*spec, read=read)` 因 `*spec` 长度未收窄导致的 `multiple values for keyword argument "read"` `[misc]` 报错；
   - `zreflect/check_facts_replay.py`：`replay_all()` 中 `stats` 字典初始化含 `"problems": []` 并标注类型（消除 `int` / `list` 赋值冲突），同步注解 `out` / `cache`；
   - `zreflect/check_i18n.py`：对 `_docstring_both()`（收窄 `ast.Expr`）、`_non_literal_code_problems()`（收窄 `ast.Call` 与 `lineno`）做类型收窄，并为 `lines` / `spans` 补全集合注解。
2. **其余闸门模块 `[var-annotated]` 补全**：
   - `zreflect/check_secrets.py`、`zreflect/check_readme_sync.py`、`zreflect/check_pins.py`、`zreflect/check_locks.py`、`zreflect/check_explain.py`、`zreflect/check_ab.py`、`zreflect/check_stale.py`、`zreflect/check_instruments.py` 局部容器补齐精确类型注解。
3. **统一重封核心印章与全量 CI 验证**：
   - 对修改后的核心文件执行 `registry.py --seal` 并更新 `FACTS.json` / `STATE.md`；
   - 本地 `act push -j gates --matrix os:ubuntu-latest -P ubuntu-latest=catthehacker/ubuntu:act-latest --pull=false --rm`（火山 PyPI 源）全步骤通过，包含 `registry`、`ruff==0.17.3`、`mypy==1.13.0`、`examples.py --all`、`harness.py` 及 `en`/`zh`/`de` 三语自证。

**Blocked by:** `questions/08-fix-core-mypy-type-contracts.md`

**Status:** ready-for-agent

**Settling:** python3 -c "import glob,os,subprocess,sys; env=dict(os.environ, MYPYPATH='zreflect'); files=sorted(glob.glob('zreflect/*.py'))+sorted(glob.glob('reflect-hooks/*.py')); sys.exit(subprocess.run([sys.executable,'-m','mypy']+files+['--check-untyped-defs','--ignore-missing-imports','--no-error-summary'], env=env).returncode)" && python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit && python3 zreflect/examples.py --all && python3 zreflect/harness.py —— rc=0 ⇒ 全仓 zreflect/ + reflect-hooks/ mypy 1.13.0 零报错且全部闸门/示范/自证全绿；rc≠0 ⇒ mypy 报错或任一门禁/示范/自证失败

## 锁定边界（不可改动）

- **不放松 CI 检查参数**：不得在 `.github/workflows/gates.yml` 里屏蔽或移除 `--check-untyped-defs`，也不靠成片 `# type: ignore` 敷衍真正能修复的类型收窄与真实 bug。
- **遵守 `ruff.toml` 与语言覆盖规则**：所有变更需同步通过 `ruff check .`（含 `C901 <= 8`）、`check_i18n` 与 `check_explain`。
