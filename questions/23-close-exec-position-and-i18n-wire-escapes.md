# 23: 彻底堵死执行位英文散文/换行注入与 `i18n` 伪造豁免

**What to build:** 收口 `gate.starts_with_interpreter` 的英文散文与 `\n`/`$(...)` 命令链绕过、`i18n._SHARP` 标题伪造以及 `check_i18n` 中 `PINNED:`、`M(var)`、点分前缀与未翻译语言包漏洞。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** `python3 zreflect/gate.py --selftest && python3 zreflect/i18n.py --selftest && python3 zreflect/check_i18n.py --selftest && python3 zreflect/doc.py --selftest` -- rc=0 => exec-position prose/escapes and i18n guards hold; rc!=0 => escape regression

## 实测问题清单

1. **执行位英文散文与换行/子壳绕过**（`zreflect/gate.py:29, 252-273`、`zreflect/doc.py:230-244`）：
   - `_PROSE_CHARS` 仅匹配中文字符，`"echo this is prose"`、`"make sure this works"`、`"/not/a/cmd prose"` 全部通过 `prose_in_exec_problems`。
   - 仅拦截引号外 `||` 与 `;`，用换行 `\n`（如 `"false\ntrue"`）、`$(false)`、`&` 或引号内 `||` 仍可绕过并在 `bash -c` 返回 `0`。
2. **`i18n.py` `_SHARP` 漏防 `human_summary` 伪造**（`zreflect/i18n.py:56-57`）：
   - `clean()` 与 `reject()` 仍未覆盖 `=== ... ===` 标题行，允许渲染正文或语言包伪造节标题。
3. **`check_i18n.py` 多处残留豁免与语言包校验缺口**（`zreflect/check_i18n.py:45-55, 135, 142, 184-190, 315-319`）：
   - `_pinned_by_comment` 与 `_pinned_lines` 只检查 `PINNED:` 字串出现，**不校验 20 字符理由**，可零理由豁免整段赋值或整函数。
   - `_non_literal_code_problems` 仅黑名单 5 类 AST 节点，放行 `M(var)` / `M(obj.code)`（`used_codes()` 也因此漏收）；第 135 行仍用 `re.match` 放行 `"a.b 任意中文"`。
   - `pack_sync_problems` 静默忽略未安装的 `REFLECT_LANGS` 项，且不校验非英语语言包（如 `de.json`）是否直接整份复制英文未翻译。

## 复跑方式

```sh
python3 zreflect/gate.py --selftest && python3 zreflect/i18n.py --selftest && python3 zreflect/check_i18n.py --selftest
```
