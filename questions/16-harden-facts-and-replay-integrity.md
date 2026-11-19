# 16: 台账守卫、裸数审查与逐字重放漏洞（`facts` / `check_facts` / `check_facts_replay`）

**What to build:** 封堵台账元数据静默篡改、假 `AUTO:*` 块与注释隐藏引用、裸数规则走私、`REFLECT_DOCS=","` 空扫放行以及重放深度/原理/校准字段绕过。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/facts.py --selftest && python3 zreflect/check_facts.py --selftest && python3 zreflect/check_facts_replay.py --selftest —— rc=0 ⇒ facts/check_facts/check_facts_replay 台账守卫与重放漏洞全部收口；rc≠0 ⇒ 仍有台账或裸数绕过

## 实测问题清单

1. **`facts.py` 元数据未受保护、假 `AUTO` 块裁剪、早退与 CLI 解析漏洞**（`zreflect/facts.py:39, 89-95, 243-259, 666-697, 737-746`）：
   - `_PROTECTED` 只含 `("value", "cmd", "calibrate", "calibrate_expect")`：静默篡改 `kind`（把 `"value"` 改成 `"principle"` 直接跳过精确 stdout 比对）、`measured_at`（重置陈旧天数）、`first_seen` 或 `source` 均不触发 `guard.refuse_changed`。
   - `prose_of()` 遇到任意 `<!-- AUTO:... -->` 到 `<!-- /AUTO:... -->` 即整段剥离，用 `<!-- AUTO:FAKE -->...<!-- /AUTO:FAKE -->` 即可在 `STATE.md` / `PRINCIPLES.md` / `AGENTS.md` / `README.md` 隐藏任意散文和裸数字。
   - `cmd_init` 的 `if not created: return 0` 在 6 个根文件已存在时跳过 `PRINCIPLES.md` 渲染与 `questions/01-example.md` 初始化；`main()` 对 `--allow-drop`/`--accept-changes` 前缀及后续 `--bogus` 参数未作严格拒绝；`cmd_accept` 未检查 `prose_in_exec_problems` 与表格破坏字符 `|`。
2. **`check_facts.py` 裸数走私、整行豁免、空扫描放行与注释隐藏引用**（`zreflect/check_facts.py:19-28, 66-86, 105, 144-198`）：
   - `_SHAPE_PATTERNS` 走私：line 25 缺前置 `\b`（`myline=5000` 被当成 `line=5000` 剥离），且 `v1.5000`、`5000B`、`1900-2099`、`foo/5000` 均免检。
   - `_unaccounted_numbers` 遇到任意 `DATED_RECORD`（如行尾加 `-20260101`）直接 `continue` 豁免**整行**所有裸数字。
   - `REFLECT_DOCS=","` 返回空扫描列表且 `check_facts` 无 `guard_nonempty`，直接 `rc=0` 通过；若 `REFLECT_DOCS` 漏掉 `STATE.md`，`extra_block_problems` 直接 `continue` 跳过对 `STATE.md` 机器块的检查。
   - 在 prose 行放 `<!-- [[key]] -->` HTML 注释不被剥离，同时满足引用存在与反抄写豁免。
3. **`check_facts_replay.py` 深度重置、`principle` 降级与 `calibrate` 盲区**（`zreflect/check_facts_replay.py:32-43, 74-102`、`zreflect/gate.py:362-366`）：
   - `EINFACHT_REPLAY_DEPTH` 可设为负数（`-999999`）或在子命令中清零绕过 `_MAX_DEPTH=2`。
   - 任何 `kind="principle"` 条目只要求 `rc == 0` 且 stdout 非空非 `OFF:`（`echo ok` 即可通过；且命令退出 `0` 时 `stderr` 里的 `OFF:` 会被 `run_cmd` 丢弃）。
   - 原始 `FACTS.json` 中有 `calibrate` 无 `calibrate_expect` 时默认期望 `""`（`true` 即可通过），`calibrate: ""` 则静默跳过校准；且 `calibrate` 未经 `prose_in_exec_problems`；`"value": ""` + `"cmd": "true"` 直接通过。

## 复跑方式

```sh
python3 zreflect/facts.py --selftest && python3 zreflect/check_facts.py --selftest && python3 zreflect/check_facts_replay.py --selftest
```
