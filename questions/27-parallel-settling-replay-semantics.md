# 27: 悬案 `Settling:` 可选并发重放语义与去重优化

**What to build:** 为 `questions/*.md` 增加可选的并发语义声明（如 `**Parallel:** true | false`），允许 `check_questions.py` 对显式声明可并行的独立 `Settling:` 命令并发重放（默认保守或显式开启），并对 `&&` 复合命令中的公共子命令做去重缓存，解决全量悬案重放串行耗时过长（~10 分钟）的问题。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Settling:** `python3 zreflect/check_questions.py --selftest && python3 zreflect/check_lint.py` -- rc=0 => Parallel field validation, sub-command dedup, and parallel replay hold; rc!=0 => parallel replay regression

## 实测问题清单

1. **`check_questions.py` 全量重放纯串行执行且无子命令去重，单次 `commit` 耗时 ~10 分钟**（`zreflect/check_questions.py:210-237`）：
   - `04`～`09` 与 `19` 号已结悬案的 `Settling:` 各自包含 `registry.py --run commit`、`harness.py`、`examples.py --all` 等重型命令，当前按文件顺序串行执行，且 `&&` 链中重复出现的子命令无法跨悬案复用缓存。
   - 需在 `questions/*.md` 引入可选的 `Parallel` 字段语义（严格校验合法值，防止静默忽略拼写错误），在不改变任何判定语义的前提下支持显式可并发悬案的并发重放与公共子命令结果复用。

## 复跑方式

```sh
python3 zreflect/check_questions.py --selftest && python3 zreflect/check_questions.py
```
