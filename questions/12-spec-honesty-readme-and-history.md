# 12: Spec 范围诚实度、`README` 结构对齐与活文档禁混历史

**What to build:** 收口 `secrets` 漏扫与伪 `why` 约束、`README` 仅查文件名互链、以及活文档借关键词留存历史废话的边界，确立“只有 `HISTORY` 与现行态一家”。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** python3 zreflect/check_retractions.py --selftest && python3 zreflect/check_secrets.py --selftest && python3 zreflect/check_readme_sync.py --selftest && python3 zreflect/check_history.py --selftest && python3 zreflect/check_secrets.py —— rc=0 ⇒ 活文档无 HIST_MARK 免检、secrets 覆盖全仓库 git ls-files、三语 README 结构同构、HISTORY 格式有效；rc≠0 ⇒ 仍有 spec/文档诚实度缺口

## 实测问题清单

1. **活文档混入历史与免检词漏洞**（`zreflect/check_retractions.py:60-79`、`zreflect/check_stale.py:121`、`zreflect/facts.py`）：
   - `check_retractions` 允许活文档中任何一行带上 `HIST_MARK`（如 `历史`/`曾经`/`已翻案`）就合法保留已推翻断言；`check_stale` R1 允许带上任意 `-YYYYMMDD`（`DATED_RECORD`）绕过 SHA 溯源。
   - **目标裁决**：活文档只留现行态；历史归档只放 `HISTORY.md`（保留 `HISTORY.md` 作为跨轮散文归档而非砍成仅查 commit message，可为 `HISTORY.md` 加轻量条目格式检查）。
2. **`secrets.json` 范围自愿申报且 7 个 spec 门禁声称要 `why` 却不校**（`check_secrets.py`、`check_ab`、`check_locks`、`check_pins`、`check_instruments`、`check_invariants`、`doctor`）：
   - 新增目录（如 `scripts/`）未加入 `secrets.json` `paths` 时静默漏扫（`git ls-files` 无覆盖率检查）。
   - 7 个 spec 门禁在 docstring/`en.json` 中声称要求 `why`/理由字段，代码实际完全不检查 `why`：要么真校验非空 `why`，要么从文案删掉虚假承诺。
3. **`check_readme_sync.py` 只查文件名字符串出现与“动过一行”**：
   - 默认模式只检查三语文件正文中包含全部成员文件名字符串；`--changed` 只校验同时出现在改动集合中（改动 1 个空格即可过关），不检查标题层级与代码块数量等基本结构同构。

## 待裁决设计点

1. `check_retractions` 是否彻底废除活文档内的 `HIST_MARK` 行级豁免（仅 `HISTORY.md` 可留存已撤回结论），以及是否收紧 `REFLECT_HISTORY_SECS`？
2. `secrets.json` 漏覆盖告警是用黑名单排除无关目录还是默认覆盖仓库 `git ls-files`（显式声明 `ignore_paths` 才放过）？
3. `check_readme_sync` 结构同构检查做到什么粒度（只核对 `#`/`##` 标题数 + 代码围栏数，避免过度耦合自然语言翻译）？

## 复跑方式

```sh
python3 zreflect/check_retractions.py && python3 zreflect/check_secrets.py && python3 zreflect/check_readme_sync.py
```
