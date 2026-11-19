# 24: 彻底清除活文档与 Python 源码中剩余的手写散文与行级免检口

**What to build:** 把 `check_explain` 扩展到模块/类文档与函数外注释、收口 `check_facts` 的 `>` 引用块与裸数逃逸口、废除 `check_stale` 整行连坐豁免并堵住 `check_retractions` 跨行绕过。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含超长模块 docstring/顶层 `#` 注释、`STATE.md` 塞多行 `>` 散文、`` `99999` `` 裸数、跨行撤回句与 `-20260101` 同行未溯源 SHA）

## 实测问题清单

1. **`check_explain.py` 漏审模块、类、顶层注释与 `strict` 模式 `#` 注释**（`zreflect/check_explain.py:90-116`）：
   - 仅遍历 `FunctionDef`/`AsyncFunctionDef`，模块级 docstring、类级 docstring、函数外顶层 `#` 注释及 `_cases`/`_cases_*` 内部全部零检查。
   - `REFLECT_COMMENTS=strict` 时只查函数 docstring 而直接 `continue` 放行函数内 `#` 注释。
2. **`check_facts.py` `>` 引用块放行与多类裸数/非整数逃逸**（`zreflect/check_facts.py:19-28, 51-61, 75, 102, 110-124, 178-181`）：
   - `hand_written_problems` 允许 `STATE.md` 与 `PRINCIPLES.md` 开头放任意数量的 `>` 引用行手写散文。
   - 反引号 `` `99999` ``、代码块围栏、`< REFLECT_NAKED_MIN`（100）整数、浮点/字符串事实，以及 `_SHAPE_PATTERNS` 中的 `stage 9999`/`12345KB`/`5000%`/`1999`/`foo/5000` 均免检；无 `AUTO:FACTS` 文档完全不跑 `_unaccounted_numbers`。
3. **`check_stale.py` 整行连坐豁免与大写 SHA 漏检**（`zreflect/check_stale.py:97, 115-132, 147, 194`）：
   - 同一行只要出现任意 `-20260101`（`DATED_RECORD`）或合法 `[[key]]`，即整行豁免所有未溯源 SHA；`DATED_RECORD` 同时整行豁免所有退役词。
   - `SHA_TOKEN` 仅匹配小写 `[0-9a-f]`，大写十六进制 SHA 漏报。
4. **`check_retractions.py` 跨行绕过与 `fixed_in` 散文**（`zreflect/check_retractions.py:40-50, 101-102`）：
   - `_resurfaced_problems` 按单行匹配，把被撤回句子拆成两行即可绕过；`fixed_in` 仅拦 6 个固定占位词，任意散文（如 `"somewhere later"`）照常通过。

## 复跑方式

```sh
python3 zreflect/check_explain.py --selftest && python3 zreflect/check_facts.py --selftest && python3 zreflect/check_stale.py --selftest && python3 zreflect/check_retractions.py --selftest
```
