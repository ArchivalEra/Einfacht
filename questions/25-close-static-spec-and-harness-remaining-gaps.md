# 25: 补齐 `check_snapshots`、Spec 闸门类型崩溃/路径穿透与 `harness`/`examples` 覆盖缺口

**What to build:** 补齐 `check_snapshots` 原地修改/星号/相对导入、Spec 闸门顶层非对象崩溃与中间软链接穿透、`secrets.json` 豁免理由、以及 `harness`/`examples` 名录与模块覆盖率检查。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含 `DICT[k]=v`/`from . import X` 跨模块快照、中间目录软链接穿透、顶层 JSON `[]` 规范报错、`secrets.json` 缺理由字段及 `examples` 覆盖核心模块）

## 实测问题清单

1. **`check_snapshots.py` 漏检原地修改、`from mod import *` 与相对导入**（`zreflect/check_snapshots.py:130-168, 382-419`）：
   - `_mutated_globals` 只捕获绑定语句，完全漏掉 `DICT[k] = v`、`LIST.append(...)`、`.update()`、`del` 等原地修改（如 `i18n._DEFAULT[0] = ...`）。
   - 忽略 `from mod import *` 与相对导入 `from . import X`。
2. **Spec 闸门异常崩溃、中间软链接穿透与静默跳过**（`zreflect/check_ab.py:132`、`check_locks.py:108`、`check_pins.py:92,122,160`、`check_instruments.py:180`、`check_invariants.py:96`、`check_world.py:178-179`）：
   - 顶层 JSON 为数组 `[]` 或缺关键字段时触发 `AttributeError`/`KeyError` 崩溃而非返回规范错误或 `FATAL`；`check_pins` 在 `kind="version"` 省略 `expect_version` 时静默跳过。
   - `check_invariants` `_safe_repo_read` 仅检查末级 `os.path.islink`，未用 `os.path.realpath` 阻断中间目录软链接逃逸到仓外。
   - `check_world` 在 detached `HEAD` 或未列入 `lines` 的分支上仍静默跳过分支审计。
3. **`check_secrets.py` 漏扫与 `secrets.json` 无理由豁免违背 `AGENTS.md`**（`zreflect/check_secrets.py:77-92, 119-133, 203-206`、`secrets.json:11-58`）：
   - 前 8192 字节含 `>= 4` 个 `\x00` 即当成二进制跳过；`git ls-files` 失败静默返回 `[]` 且不查未跟踪目录。
   - `AGENTS.md:27` 声明 `secrets.json` 豁免需带理由，但当前 `allow` 与 `ignore_paths` 均未强制且未填写 `why`/`reason`。
4. **`harness.py` 与 `examples.py` 覆盖率盲区**（`zreflect/harness.py:88-92, 181-212, 273-277`、`zreflect/examples.py:119-125`）：
   - `run_gates` 忽略 `registry.gates()` 返回的 `missing` 列表，`run_modules` 忽略 `undeclared`；`_CORE_MUST_RUN` 为硬编码 10 项清单。
   - `examples.coverage_problems` 仅检查 `gates`，未要求核心 `MODULE` 具备示范覆盖。

## 复跑方式

```sh
python3 zreflect/check_snapshots.py --selftest && python3 zreflect/check_secrets.py --selftest && python3 zreflect/harness.py && python3 zreflect/examples.py --check
```
