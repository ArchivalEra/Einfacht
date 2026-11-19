# 19: Python 静态闸门、`harness` 与 `examples` 覆盖盲区

**What to build:** 补全 `check_i18n`、`check_snapshots`、`check_explain`、`check_lint` 的 AST/作用域盲区，并堵住 `harness` 与 `examples` 对 `OFF:`/`SKIP:` 与平台跳过的虚假绿灯。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/check_i18n.py --selftest && python3 zreflect/check_snapshots.py --selftest && python3 zreflect/check_explain.py --selftest && python3 zreflect/check_lint.py --selftest && python3 zreflect/harness.py && python3 zreflect/examples.py --all —— rc=0 ⇒ Python 静态闸门、harness 与 examples 覆盖盲区全部收口；rc≠0 ⇒ 仍有静态门禁或假绿口子

## 实测问题清单

1. **`check_i18n.py` 动态 `M(var)`、`used_codes()` 与 `_EXEMPT_CALLS` 漏洞**（`zreflect/check_i18n.py:23-25, 95-102, 134, 141-152, 260, 360`）：
   - `_non_literal_code_problems` 仅黑名单 5 类节点，放行 `M(var)` / `M(obj.code)`；同时 `used_codes()` 仅用正则搜双引号 `M("...")`，漏检动态码与单引号 `M('...')`（且 `text.replace(doc, "")` 可能误删短串）。
   - `_EXEMPT_CALLS` 连同调用接收者整个子树豁免（`"中文".startswith("x")`、`compile("中文")` 皆通过）；`_bare_text_problems` 第 134 行对 `"a.b 中文"` 类点分前缀整串豁免；默认不扫无 `GATE=`/`MODULE=` 的 `.py`（如 `measure_*.py`）。
2. **`check_snapshots.py` 漏掉小写全局变量、原地修改与别名导入**（`zreflect/check_snapshots.py:130-168, 302-306, 412, 455`）：
   - 第 412 行 `if name != name.upper(): continue` 放过所有小写与驼峰全局可变状态；`_mutated_globals` 只认 `=` 重绑定，完全漏掉 `DICT[k] = v`、`LIST.append(...)`、`.update()`、`.clear()` 与 `del` 等原地修改。
   - 忽略 `import mod as alias`、`from mod import *` 与相对导入 `from . import X`；同样跳过无 `GATE=`/`MODULE=` 声明的 `.py` 文件。
3. **`check_explain.py` 漏扫模块/类文档、函数外注释与 `# !` 无限豁免**（`zreflect/check_explain.py:31, 62-82, 96-108, 126-138`）：
   - 只遍历 `FunctionDef`/`AsyncFunctionDef`，完全不管模块级 docstring、类级 docstring 与函数外顶层 `#` 注释；`strict` 模式完全跳过 `#` 注释额度；`_PRAGMAS` 含 `"!"`，`# ! 任意长散文` 无限豁免；不扫 `measure_*.py` 与子目录。
4. **`check_lint.py` 漏扫未声明模块及 `ruff` 调用不一致**（`zreflect/check_lint.py:72-82, 129-132`）：
   - `suite_files()` 过滤 `declares_itself()`，跳过 `measure_*.py` 及纯辅助 `.py`；当 `PATH` 存在独立 `ruff` 而当前 `sys.executable` 未装 `ruff` 模块时，探测通过却运行失败 `FATAL`。
5. **`harness.py` 与 `examples.py` 假绿口子**（`zreflect/harness.py:88, 182, 268-275`、`zreflect/examples.py:119-125, 173-188, 249-250`）：
   - `harness.run_configurable` 的 `_renamed_all_green` 只检查 `rc == 0`，不检查除外部工具之外的闸门是否在改名夹具里偷偷变成了 `OFF:`；`run_gates`/`run_modules` 忽略名录返回的 `missing` 列表。
   - `examples.coverage_problems` 只检查 `gates`，不覆盖核心 `modules`；标成 `["windows"]` 的示范在 Linux CI 直接跳过却退出 `0`；未显式配置 `not_contains` 时允许示范步输出 `OFF:`/`SKIP:` 通过。

## 复跑方式

```sh
python3 zreflect/check_i18n.py --selftest && python3 zreflect/check_snapshots.py --selftest && python3 zreflect/harness.py
```
