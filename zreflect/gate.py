#!/usr/bin/env python3
"""闸门平台：rc 契约 + 零值守卫 + 三档自证。

它解决的**不是**「没有检查」，而是**检查在输入消失时静默变绿**。真实踩过的三种：

  · 三个站点同时缺 `VERSION` ⇒ 一致性闸门报「完全一致」；
  · 声明的集合是空的 ⇒ 出厂核对报 `verdict: "ok"`；
  · 自检脚本 `0/0` ⇒ 算「全部通过」。

所以任何检查器都必须能回答两句话：**输入空了我报吗？**、**该报的我会报吗？**
`require_nonempty()` 答第一句，`selftest()` 的三类用例答第二句。

**rc 契约（本平台的 interface，2026-10-07 起全仓唯一产地）**：

  · `off()`    ⇒ 0，未启用（可插拔闸门的 off 态必须**明说**，不许静默）；
  · `fatal()`  ⇒ 2，配置 / 环境坏（旋钮指向缺失、坏 JSON、规格结构坏、
    仪器本身坏了）—— 配置性失败 ≠ 检查失败，混进 1 会让「发现问题」
    与「配置坏了」不可区分；
  · `finish()` ⇒ 1（有 problems）/ 0（绿）。标题在先、问题行在后，
    问题行统一 stderr —— 此前 13 道闸门各手抄一份、已漂出两派
    （stdout/stderr 混用、标题先后不一），这里收敛成一份。

自证期间纯函数保持安静（print 归 run()/顶层，issue #1 ③）。
"""
import json
import os
import sys

# 被检查的仓库根：默认是本包的上一级，可用 GATE_REPO 覆盖（测试夹具靠它）。
GATE_REPO = os.environ.get("GATE_REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo(*parts):
    """拼一个指向被检查仓库的绝对路径。"""
    return os.path.join(GATE_REPO, *parts)


def require_nonempty(name, seq, what="输入"):
    """零值守卫：收集阶段什么都没收到 ⇒ 报错，**不许当「干净」**。

    这是本包最重要的一行。绝大多数「闸门假装通过」的事故，根因都是这里没守：
    遍历一个不存在的目录得到空集，然后「没有发现违规」——两句都是真的，结论是错的。
    """
    items = list(seq)
    if not items:
        raise SystemExit(
            "FATAL: %s：%s 是空的。空输入不是「全部通过」—— 要么收集逻辑坏了，"
            "要么路径给错了。先修输入，别关闸门。" % (name, what)
        )
    return items


def guard_nonempty(name, seq, what="输入"):
    """`require_nonempty` 的 rc 版：空 ⇒ 打印 FATAL、返回 2；非空 ⇒ None。

    给「直接跑」的检查器用（它们要的是退出码，不是异常）。
    """
    try:
        require_nonempty(name, seq, what)
        return None
    except SystemExit as e:
        print("%s" % e, file=sys.stderr)
        return 2


def off(notice):
    """未启用：明说（stderr）+ 退 0 —— 可插拔闸门 off 态的唯一产地。"""
    print(notice, file=sys.stderr)
    return 0


def fatal(msg):
    """配置 / 环境坏：FATAL + 退 2。"""
    print("FATAL: %s" % msg, file=sys.stderr)
    return 2


def load_spec(path):
    """读 JSON 规格，返回 (spec, 错误句)。错误句非 None ⇒ 调用方 `fatal()`。

    返回错误而不是 raise：调用方要把旋钮名 / 路径放进自己的 FATAL 措辞。
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as e:
        return None, "%s 读不了 / 不是合法 JSON：%s" % (path, e)


def finish(name, problems, ok):
    """问题循环 + OK 行 —— rc 契约（1 = 发现问题 / 0 = 绿）的唯一产地。"""
    if problems:
        print("%s：%d 个问题" % (name, len(problems)), file=sys.stderr)
        for p in problems:
            print("  · " + p, file=sys.stderr)
        return 1
    print(ok)
    return 0


def meta(name, desc, knobs=()):
    """闸门声明行（registry 的 ast 提取目标）：名字 + 一句话 + 消费的旋钮。

    声明即登记 —— 手写名录会漂，这里只许写事实；registry（Phase 3）从这里
    派生闸门清单与「默认名承担载荷」的红名单，STATE.md 的机器块同源渲染。
    """
    return {"name": name, "desc": desc, "knobs": tuple(knobs)}


def raises(fn):
    """「该报错的必须报错」—— 反向断言用。返回 True 表示它确实报了 SystemExit。"""
    try:
        fn()
    except SystemExit:
        return True
    return False


def selftest(name, cases):
    """跑三档用例。每个 case = (标签, callable) -> bool。

    必须写齐三类：
      ① 正常不报（阳性对照 —— 否则「总是报错」也能骗过自证）
      ② 该报的必须报（反向断言 —— 否则这个检查器可能是装饰）
      ③ 空输入必须报（零值守卫）
    """
    if not cases:
        # 0/0 洞（本文件开头记载的第三种事故）：空用例清单的自证什么都没查，
        # 却打印「0 PASS / 0 FAIL」绿着退场 —— runner 的 grep 照样认它。
        # 空清单是写自证时的形状错误，当场响，不许绿。
        raise SystemExit(
            "FATAL: %s 的自证用例清单为空 —— 三档用例齐全是硬规矩"
            "（0/0 不是通过，是「这个自证什么都没查」）" % name
        )
    bad = 0
    for label, fn in cases:
        try:
            ok = bool(fn())
        except SystemExit as e:
            ok, label = False, "%s（未预期的 SystemExit：%s）" % (label, e)
        except Exception as e:                      # noqa: BLE001
            ok, label = False, "%s（异常 %r）" % (label, e)
        print("%s | %s" % ("PASS" if ok else "fail", label))
        bad += 0 if ok else 1
    print("=== %s 自证：%d PASS / %d fail ===" % (name, len(cases) - bad, bad))
    # 机器摘要行（issue #3 ③）：与检查器名无关的固定格式，runner/CI 直接
    # grep；gates-selftest.sh 会校验每个自证都有这一行（缺了 ⇒ 红）。
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


def main_selftest_or(args, name, cases, run):
    """`--selftest` 走自证，否则走 `run(args)`。每个检查器都用它收尾。

    `cases` 可以是清单，也可以是**工厂 callable**（需要搭临时夹具的
    自证 —— ab/locks/pins 体例 —— 传函数，由这里调用）。
    """
    if "--selftest" in args:
        return selftest(name, cases() if callable(cases) else cases)
    return run([a for a in args if a != "--selftest"])


if __name__ == "__main__":
    print("闸门平台。被检查的仓库根：%s" % GATE_REPO)
    print("用法：在你的检查器里 `from gate import selftest, require_nonempty`。")
    sys.exit(0)
