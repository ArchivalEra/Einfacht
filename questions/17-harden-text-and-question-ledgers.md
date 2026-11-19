# 17: 文本、撤回、陈旧、悬案、历史与 README 细节漏洞

**What to build:** 收口 `check_retractions`、`check_stale`、`check_questions`、`check_history` 与 `check_readme_sync` 中除“活文档混入历史（单 12）”之外的其余实现绕过点。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/check_retractions.py --selftest && python3 zreflect/check_stale.py --selftest && python3 zreflect/check_questions.py --selftest && python3 zreflect/check_history.py --selftest && python3 zreflect/check_readme_sync.py --selftest —— rc=0 ⇒ 文本、撤回、陈旧、悬案、历史与 README 细节漏洞全部收口；rc≠0 ⇒ 仍有文本/解析边界绕过

## 实测问题清单

1. **`check_retractions.py` & `check_stale.py` 章节豁免、匹配脆弱与部分缺失放行**（`zreflect/facts.py:139-154`、`check_retractions.py:30, 75-76, 129-133`、`check_stale.py:74, 87, 118-127, 154, 201`）：
   - `section_is_living()` 无条件豁免活文档中任何 `## 附...` 标题之后的内容（且 `living_lines()` 遇到后续 `# ` 顶级标题不会恢复 `keep=True`）。
   - `text in line` 精确匹配大小写、单空格与单行，改一个大小写或加个空格/换行即逃脱撤回告警；`fixed_in` 只查真值（`"tbd"` 照过）；`REFLECT_DOCS` 列表中只要至少 1 个文件存在，其余缺失文件被静默跳过。
   - `_is_sourced(line)` 只要行内含任意 `[[key]]`（哪怕无关或不存在）即同时豁免同行全部裸 SHA 与全部 `REFLECT_RETIRED` 词；`SHA_NEAR` 漏掉 `commit:`/`digest:`/`checksum:`；`REFLECT_RETIRED` 逗号分隔不做 `.strip()`。
2. **`check_questions.py` `PATHISH` 只看首词与解析边界缺陷**（`zreflect/check_questions.py:65-66, 69-96, 149-156`）：
   - `sv.split()[0]` 只取首词：对于合法以解释器开头的 `python3 nonexistent.py -- rc=0 => a; rc=1 => b`，`tok` 为 `"python3"`，从不检查 `nonexistent.py` 是否存在。
   - `NONE_LIKE` 前缀匹配且区分大小写：`nonexistent.py` 因 `"none"` 前缀被误判为 `NONE_LIKE`，而 `"NONE"` 则失效；`field()` 遇到重复 `**Status:**`/`**Settling:**` 只认第一个；续行正则把 `https://...` 当成新字段名导致换行 `Settling:` 被截断。
3. **`check_history.py` 接受空文件与软链接绕过**（`zreflect/check_history.py:62-63, 96-110`）：
   - 0 字节或全空白 `HISTORY.md` 通过；`_norm()` 用 `abspath` 而非 `realpath`，把 `HISTORY.md` 软链接到活文档可绕过 `is_exempt`。
4. **`check_readme_sync.py` 旗标漏校验、重复项与注释欺骗**（`zreflect/check_readme_sync.py:82-96, 128-132, 151-160`）：
   - 传未知旗标（如 `--bogus`）静默走默认模式并返回 `0`；`REFLECT_READMES="README.md,README.md"` 可虚增成员数通过结构检查；正文里藏 `<!-- README.zh.md -->` HTML 注释即可满足互链；`--changed` 未归一化 `./README.md` 路径。

## 复跑方式

```sh
python3 zreflect/check_retractions.py --selftest && python3 zreflect/check_stale.py --selftest && python3 zreflect/check_questions.py --selftest && python3 zreflect/check_history.py --selftest && python3 zreflect/check_readme_sync.py --selftest
```
