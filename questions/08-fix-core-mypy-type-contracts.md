# 08: 修复核心与基础模块 mypy 类型契约与运行时隐患

**What to build:** 修复 `act` 本地 CI 中 `mypy==1.13.0`（`--check-untyped-defs --ignore-missing-imports`）在核心与基础模块暴露的真实隐患与类型契约缺口（共 `9` 个文件，修完各自一次到清零）：
1. **运行时拼串隐患与字典类型收窄**：
   - `zreflect/examples.py`：`_run_step()` 处理 `subprocess.TimeoutExpired` 时分别将 `.stdout` / `.stderr` 从 `bytes | str | None` 安全解码后再拼接，避免 `bytes + ""` 触发 `TypeError`；同时为 `manifests` 补全容器注解；
   - `zreflect/gate.py`：`run_phase()` 显式注解 `res: dict[str, Any]`（消除 `object + int` / `.append` / 下标赋值冲突），并为模块内空列表 `out` 补全类型注解。
2. **`__slots__` 子类属性声明**：
   - `zreflect/i18n.py`：为 `Catalog` 声明 `.table`（及构造函数字段）类型，为 `Message(str)` 声明 `code: str`、`params: dict[str, Any]`、`forged: bool`；
   - `zreflect/knobs.py`：为 `_Semantic(str)` 声明 `code: str`。
3. **其余基础模块局部容器注解（`[var-annotated]`）**：
   - `zreflect/registry.py`、`zreflect/doctor.py`、`zreflect/doc.py`、`zreflect/facts.py`、`zreflect/next.py` 中对应局部容器补齐最小明确注解。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 -c "import os,subprocess,sys; files=['zreflect/i18n.py','zreflect/knobs.py','zreflect/gate.py','zreflect/registry.py','zreflect/examples.py','zreflect/doctor.py','zreflect/doc.py','zreflect/facts.py','zreflect/next.py']; env=dict(os.environ, MYPYPATH='zreflect'); r=subprocess.run([sys.executable,'-m','mypy']+files+['--check-untyped-defs','--ignore-missing-imports','--no-error-summary'], env=env); sys.exit(r.returncode)" && python3 zreflect/registry.py --verify-seal && python3 zreflect/registry.py --run commit && python3 zreflect/harness.py —— rc=0 ⇒ 核心与基础 9 个模块在 mypy 1.13.0 下零报错、TimeoutExpired 安全处理验证成立、seal 与全部门禁全绿；rc≠0 ⇒ 仍有 mypy 报错、核心破坏或门禁失败

## 锁定边界（不可改动）

- **不改变既有运行时契约**：`M(code, **params)` 零语言行为、`facts.py` 裸值 stdout、`gate.selftest()` 摘要与退出码契约、`examples.py` 示范步骤语义均保持原样。
- **遵循 `ruff.toml` 复杂度与注释纪律**：`C901 <= 8`、`check_explain` 注释预算、不得把英文散文或未纳入语言包的报错字符串写入代码。
