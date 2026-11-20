# 22: 堵死 `SEAL.json`、`registry` 与 `knobs` 剩余篡改及漏封漏洞

**What to build:** 修复 `seal.verify_problems(include_gates=False)`、无保护 `--reseal`、`registry --run` 旗标回落及 `knobs` AST 逃生。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** `python3 zreflect/registry.py --verify-seal && python3 zreflect/seal.py --selftest && python3 zreflect/knobs.py --selftest && python3 zreflect/registry.py --selftest` -- rc=0 => seal, registry flag, and knobs AST guards hold; rc!=0 => tampering or AST bypass regression

## 实测问题清单

1. **`seal.verify_problems()` 仍传 `include_gates=False`，允许删改内置核心闸门**（`zreflect/seal.py:93-106, 170-174, 209, 212, 242`）：
   - 从 `SEAL.json` 删除 `zreflect/check_facts_replay.py` 等内置闸门并重算 `tree_sha256`，再把闸门内容改成 `sys.exit(0)`，`--verify-seal` 仍返回 `0`。
   - `--reseal=ALL` 无任何前置保护可随时洗白篡改；`_skip_optional` 在非 git 副本中仍放行删除 `reflect-hooks/`；`zreflect/` 下无 `MODULE`/`GATE` 声明的辅助 `.py` 与子目录漏封；删除 `ruff.toml` 并移出 `SEAL.json` 也可双绿。
2. **`registry.py` 旗标解析遗留静默回落**（`zreflect/registry.py:268-270`）：
   - `registry.py --run` 末尾无参数时仍默认回落 `"commit"`；`--runnable --badflag` 仍返回 `rc=0`。
3. **`knobs.py` AST 环境读取与豁免函数名过滤过宽**（`zreflect/knobs.py:231-256`）：
   - `_environ_read_key` 仍漏 `from os import environ`/`getenv` 及 `.pop()` 写法。
   - `_is_test_node` 仍豁免任何以 `_case` 或 `_ok` 结尾的顶级函数，可借命名绕过扫描。

## 复跑方式

```sh
python3 zreflect/registry.py --verify-seal && python3 zreflect/seal.py --selftest && python3 zreflect/knobs.py --selftest
```
