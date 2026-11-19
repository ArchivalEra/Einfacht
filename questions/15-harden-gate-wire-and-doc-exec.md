# 15: 执行器、`i18n` 线协议、`doc` 与 `next.py` 漏洞（`gate` / `i18n` / `doc` / `next`）

**What to build:** 堵死底层命令改写/shell 链绕过、英文散文冒充命令、机器行协议缺口与 `doc` 异常吞噬。

**Blocked by:** None (can start immediately)

**Status:** needs-triage

**Settling:** none -- first deliverable: 第一交付物是一组会红的验收用例（含 `python3 fail.py || true`、`test if works` 英文散文命令、`ab.json/` 目录冒充 spec、损坏 `world.json` 逃过 `doc.all_exec_position_problems`）

## 实测问题清单

1. **`gate.py` 命令改写不全、shell 链绕过与执行位伪阳性**（`zreflect/gate.py:28-31, 101-121, 160-202, 240-258, 323-366, 482-486`）：
   - `_python_of` 正则替换 `count=1`：遇到 `&&` 连接多条命令、`env FOO=1 python3 ...` 或 `python ...` 时漏改写；`run_cmd` 走 `bash -c` / `sh -c`，`cmd || true` 或 `false; echo ok` 皆返回 `rc=0`；`rc == 0` 时静默丢弃 `stderr`。
   - `starts_with_interpreter` 的 `_PROSE_CHARS` 仅拦截中文，任何以 `EXEC_PREFIXES` 动词开头的英文散文（如 `test if this works`、`echo todo`）或任意 `/not/a/cmd prose` 均判 `True`；且 `split(" ", 1)` 不按 `\t` 分割。
   - `declares_itself` 用 `"GATE =" in text` 子串匹配（注释也可骗过，`GATE=meta(...)` 无空格反被漏掉）；`suite_sources` 不递归子目录。
   - `resolve_spec` 忽略 `--spec=path` 与尾部悬空 `--spec`；若默认 spec 位置被建为同名目录（如 `ab.json/`），`os.path.isfile` 为 `False` 却以 `OFF:` (`rc=0`) 放行；`run_phase` 仅凭合并输出中任意行匹配 `^OFF:` 即把 `rc=0` 闸门归入 `off`；`guard_nonempty` 依赖 `fatal_exit` 字符串 `SystemExit`，修复 `fatal_exit` 退出 `2` 后会退化成只打印 `"2"`。
2. **`i18n.py` 缺占位符校验与 `human_summary` 防伪造盲区**（`zreflect/i18n.py:56-57, 91-104, 168-188, 240-253`）：
   - `_validate` 不检查 `%` 格式化占位符（坏格式如 `%(bad)s` 或未转义 `%` 在加载阶段不报错，运行时直接崩溃）；`_SHARP` 不包含 `human_summary`（`=== ... ===`），`clean()` 不转义之；`installed_langs()` 仅查目录内有 `*.json` 即认定为有效语言包。
3. **`doc.py` 吞掉坏 JSON、放行 `|| true` 与 `Settling:` 解析分裂**（`zreflect/doc.py:38-57, 60-74, 214-224`）：
   - `_read_json_safe` 捕获 `(OSError, ValueError)` 后返回 `{}`，导致损坏的 `world.json`/`pins.json`/`retractions.json` 在 `all_exec_position_problems` 中静默返回空列表。
   - `_cmd_shape_problems` 允许 `;`/`||`/`&&` 掩盖真实退出码；`_question_exec_problems` 仅识别单行 `**Settling:**` 字面量，既不豁免 `"不存在"`（误红），又漏掉 `Settling:` / `**Settling**:` 与换行续写。
4. **`next.py` detached `HEAD` 误报与直接 import 缺路径**（`zreflect/next.py:58-62, 93-103`）：
   - detached `HEAD` 时 `git symbolic-ref --short HEAD` 返回 `1`，误报 `next.commits_unreadable`；模块顶层 `import knobs, i18n` 而 `sys.path.insert` 却只在 `__main__` 下。

## 复跑方式

```sh
python3 zreflect/gate.py --selftest && python3 zreflect/doc.py --selftest
```
