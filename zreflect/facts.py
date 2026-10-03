#!/usr/bin/env python3
"""事实台账的 CLI：量一遍、写台账、渲染机器块，以及**两道守卫**。

用法
    python3 zreflect/facts.py                      # 量一遍并写 FACTS.json（掉条/改口会拒绝）
    python3 zreflect/facts.py --allow-drop         # 允许本次掉条（掉掉的键会打出来）
    python3 zreflect/facts.py --accept-changes     # 允许本次改口（旧值→新值会打出来）
    python3 zreflect/facts.py --accept-changes=k1,k2  # 只接受列出的键，其余改口仍拒绝（issue #3 ①）
    python3 zreflect/facts.py --render-doc [文件]  # 把机器块写进文档（默认 STATE.md）
    python3 zreflect/facts.py --check [文件]       # 文档里的块是否与台账一致
    python3 zreflect/facts.py --get 键名           # 只打印该键的值（消费方出口，issue #4 ④）
    python3 zreflect/facts.py show [键]            # 打印某条事实
    python3 zreflect/facts.py --selftest           # 自证：两道守卫必须都能红

⚠️ **量不到的项不写**（宁缺勿假）。比如「最近一次全绿回归」只在有日志的机器上量得出来；
没日志就把那条事实**留空**，而不是写 0 —— 0 是一个数字，会被人当结果引用。
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import GATE_REPO, repo, selftest             # noqa: E402
from ledger import (age_days, changed_keys, dropped_keys,  # noqa: E402
                    fact, facts_of, load, _short, _value)
from render import BLOCK_BEGIN, BLOCK_END, body_of, prose_of, render_block  # noqa: E402

LEDGER_NAME = os.environ.get("REFLECT_FACTS", "FACTS.json")
OUT = repo(LEDGER_NAME)
DOC = os.environ.get("REFLECT_DOC", "STATE.md")


# ══ 你的部分 ══════════════════════════════════════════════════════════════════
def measure_example():
    """**占位实现 —— 换掉它。** 系统只提供机制，你的输入只有你知道怎么量。

    这里量的东西和「事实」无关，只是为了让仓库开箱能跑。真要落地时，把每条
    `fact(值, 复跑命令, 出处)` 换成你自己量出来的数；特别是那条复跑命令 ——
    它必须**真的能跑**，否则这条事实就又变成了一句散文。
    """
    facts = {}
    n_py = 0
    n_md = 0
    lines_py = 0
    for root, _dirs, files in os.walk(GATE_REPO):
        if "/.git" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                n_py += 1
                try:
                    lines_py += sum(1 for _ in open(os.path.join(root, f), encoding="utf-8",
                                                    errors="replace"))
                except OSError:
                    pass                      # 数不出来的文件不计数 —— 宁缺勿假
            elif f.endswith(".md"):
                n_md += 1
    facts["py_files"] = fact(n_py, "find . -name '*.py' -not -path './.git/*' | wc -l",
                             "repo", "示例事实：换掉 measure_example()")
    facts["md_files"] = fact(n_md, "find . -name '*.md' -not -path './.git/*' | wc -l", "repo")
    # 这条刻意大于 BARE_MIN（check_facts 的裸数字阈值 = 100），好在 STATE.md 里
    # 演示「手抄这个数字会被闸门拦下」。太小的数字遍地都是，查了全是噪音 ⇒ 不查。
    facts["py_lines"] = fact(lines_py, "find . -name '*.py' -not -path './.git/*' "
                             "-exec cat {} + | wc -l", "repo",
                             "刻意 ≥100，用来示范裸数字判据")
    # ⑥ 块排除模式（issue #4 ⑥）：md_lines 数**块以外**的行 —— 机器块
    # 就渲染在这些文档里，数进去 ⇒ 渲染一遍值就过期 ⇒ 复跑恒定失败
    # （而 check_facts 比的是「块↔台账」，两边一起陈旧 ⇒ 全绿）。
    # awk 的 FNR==1{b=0} 是必需的：find -exec {} + 会把多个文件喂给
    # 同一个 awk 进程，漏了按文件重置，第一个带块的文件之后全被跳过，
    # 而输出仍然「像个行数」。起始标记与 render.py 的输出逐字一致。
    md_lines_cmd = ("find . -name '*.md' -not -path './.git/*'"
                    " -exec awk 'FNR==1{b=0} /<!-- AUTO:FACTS -->/{b=1} !b' {} + | wc -l")
    # cwd=GATE_REPO：计数（os.walk(GATE_REPO)）与复跑（闸门在仓库根
    # 逐字执行 cmd）都锚定 GATE_REPO —— 不传 cwd 时，在夹具里量到的是
    # 调用方仓库的行数，换名自证会红（跨仓库可配置性自证抓到的回归）。
    facts["md_lines"] = fact(
        int(subprocess.run(md_lines_cmd, shell=True, capture_output=True,
                             text=True, check=True,
                             cwd=GATE_REPO).stdout.strip()),
        md_lines_cmd, "repo",
        "不含机器块：块就渲染在文档里，数进去会让渲染一遍值就过期")

    # 例：**量不到就不写**。把 UPSTREAM_VERSION 设上才有这条事实。
    v = os.environ.get("UPSTREAM_VERSION", "").strip()
    if v:
        facts["upstream_version"] = fact(v, "echo \"$UPSTREAM_VERSION\"", "env",
                                         "量不到就不写 —— 宁缺勿假")
    return facts


# ══ 以下不用改 ════════════════════════════════════════════════════════════════
def write_doc(path_rel, ledger):
    """把块写进文档（就地替换）。没有标记就报错，**不悄悄追加** ——
    悄悄追加会让「块过期」变成「有两份块」，那是更难查的坏法。"""
    p = path_rel if os.path.isabs(path_rel) else repo(path_rel)
    if not os.path.exists(p):
        print("FATAL: %s 不存在。先手工放一次 %s / %s 两个标记。" % (p, BLOCK_BEGIN, BLOCK_END),
              file=sys.stderr)
        return 2
    text = open(p, encoding="utf-8").read()
    if BLOCK_BEGIN not in text or BLOCK_END not in text:
        print("FATAL: %s 缺 %s / %s 标记（第一次落地时要手工放一次）"
              % (p, BLOCK_BEGIN, BLOCK_END), file=sys.stderr)
        return 2
    pre, _, rest = text.partition(BLOCK_BEGIN)
    _, _, post = rest.partition(BLOCK_END)
    new = pre + render_block(ledger) + post
    if new != text:
        open(p, "w", encoding="utf-8").write(new)
        print("已刷新 %s 的事实块" % path_rel)
    else:
        print("%s 的事实块无变化" % path_rel)
    return 0


def check_doc(path_rel, ledger):
    p = path_rel if os.path.isabs(path_rel) else repo(path_rel)
    if not os.path.exists(p):
        print("FATAL: 文档 %s 不存在（--check 不能因为找不到文件就算通过）" % p, file=sys.stderr)
        return 2
    text = open(p, encoding="utf-8").read()
    if BLOCK_BEGIN not in text or BLOCK_END not in text:
        print("FATAL: %s 缺事实块标记" % path_rel, file=sys.stderr)
        return 2
    if body_of(text) != body_of(render_block(ledger)):
        print("FATAL: %s 的事实块与 FACTS.json 不一致 ⇒ 跑 --render-doc" % path_rel, file=sys.stderr)
        return 1
    print("%s 的事实块与台账一致" % path_rel)
    return 0


def _accepted_keys(argv):
    """解析 `--accept-changes[=k1,k2]`（issue #3 ①）：裸旗 ⇒ None（全收）；
    列键 ⇒ 集合（空串 ⇒ 空集 = 一个都不收）；没传 ⇒ False（全拒，同旧行为）。"""
    for a in argv:
        if a == "--accept-changes":
            return None
        if a.startswith("--accept-changes="):
            raw = a.split("=", 1)[1].strip()
            return {k.strip() for k in raw.split(",") if k.strip()}
    return False


def filter_accepted(changed, accepted):
    """改口清单里**还没被接受**的部分（纯函数：自证要用）。

    `accepted=None` ⇒ 全收；`False` ⇒ 全拒；集合 ⇒ 只留未列出的键。
    """
    if accepted is None:
        return []
    if accepted is False:
        return list(changed or [])
    return [c for c in (changed or []) if c[0] not in accepted]


def _age_human(entry):
    """`measured_at` 的人话（issue #3 ②）：今天 / N 天前 / 未记录。"""
    d = age_days(entry)
    if d is None:
        return "未记录测量时间"
    if d < 1:
        return "今天测的"
    return "%d 天前测的" % int(d)


def measure(argv):
    """量一遍并写台账。**必须接 `argv`** —— 两道守卫都要读它。

    ⚠️ 这里踩过：`measure()` 曾经没有 `argv` 参数，而守卫里写着 `not in argv`。
    因为 `and` 短路，**只在真的掉条时**才走到那句 ⇒ 报的不是「掉了哪几条」而是一段
    NameError traceback；`--allow-drop` 从未生效过。写盘被拦住只是**顺带**（异常早于写盘），
    那不叫守卫，那叫故障。所以本文件把 argv 显式传进来，并且守卫自己也吃一条反向断言。
    """
    facts = measure_example()

    old = facts_of(load(OUT)) if os.path.exists(OUT) else {}

    # 守卫一：掉条（键没了）
    dropped = dropped_keys(old, facts)
    if dropped and "--allow-drop" not in argv:
        print("FATAL: 本次会从台账里**掉掉 %d 条事实**（输入不在？）：%s"
              % (len(dropped), ", ".join(dropped)), file=sys.stderr)
        print("       台账不写。要么把输入准备好，要么显式 `--allow-drop`"
              "（并把掉掉的键记进 HISTORY）。", file=sys.stderr)
        return 2
    if dropped:
        print("⚠ --allow-drop：本次掉掉 %d 条：%s" % (len(dropped), ", ".join(dropped)),
              file=sys.stderr)

    # 守卫二：改口（值换了）。`--accept-changes[=k1,k2]`：裸旗全收；列键只收列出的，
    # 其余照旧拒绝 —— 全收会把"真坏了的测量"一起洗白（issue #3 ①）。
    changed = changed_keys(old, facts)
    accepted = _accepted_keys(argv)
    remaining = filter_accepted(changed, accepted)
    if remaining:
        print("FATAL: 本次重测会**改掉 %d 条事实的值**（未经接受的改口）：" % len(remaining),
              file=sys.stderr)
        for k, o, n in remaining:
            print("       %-24s %s → %s" % (k, _short(o), _short(n)), file=sys.stderr)
        if accepted:
            print("       已按 --accept-changes 接受 %d 条：%s —— 其余仍拒绝。"
                  % (len(changed) - len(remaining), ", ".join(sorted(accepted))),
                  file=sys.stderr)
        print("       台账不写。逐条确认这些变化**是实测出来的**（不是输入不在/量错了）之后，"
              "再显式 `--accept-changes`（或 `--accept-changes=k1,k2` 逐条放行）。",
              file=sys.stderr)
        return 2
    if changed:
        print("⚠ --accept-changes：本次接受 %d 条改口：" % len(changed))
        for k, o, n in changed:
            print("       %-24s %s → %s" % (k, _short(o), _short(n)))

    if not facts:
        print("FATAL: 一条事实都没量到。空台账不是通过（零值守卫）。", file=sys.stderr)
        return 2

    # 仪器生命周期（issue #6 ①）：值没变的键沿用旧 first_seen
    # （换值 / 新键的 first_seen 已由 ledger.fact() 盖今天）——
    # 恒常检测（可插拔闸门 check_instruments.py）靠它。
    for k, entry in facts.items():
        o = old.get(k)
        fs = o.get("first_seen") if isinstance(o, dict) else None
        if fs and _value(o) == _value(entry):
            entry["first_seen"] = fs

    import json                                         # noqa: PLC0415
    import time                                         # noqa: PLC0415
    doc = {"schema": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "_why": "事实台账：每条 = 一个**测出来**的值 + 复跑命令 + 出处。"
                   "别手改，跑 zreflect/facts.py。",
           "facts": facts}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print("已写出 %s（%d 条事实）" % (os.path.relpath(OUT, GATE_REPO), len(facts)))
    for k, v in sorted(facts.items()):
        print("  %-20s %s（%s）" % (k, v["value"], _age_human(v)))
    return 0


def get_value(ledger, key):
    """按键取台账值 —— 跨语言消费方的**官方只读出口**（issue #4 ④）。

    消费方（CI、其它语言的测试进程）一律走 `facts.py --get KEY`，
    **不要自己解析 FACTS.json**：手写 parser 的经典坑是 substring 找
    `"value"` 再取引号内 —— 同一文件里到处都是 `"value": …`，会取到
    **别的键**上的值。这里把值取完整。
    键不存在 ⇒ (False, 错误句)；存在 ⇒ (True, 值)。
    """
    f = facts_of(ledger)
    if key not in f:
        return False, "台账里没有键 `%s`（现有：%s）" % (
            key, ", ".join(sorted(f)) or "空")
    return True, _value(f[key])


def _load_or_die():
    """读台账；**没有就给出可操作的提示**而不是原始 traceback。
    为什么单列：新仓库第一次用时台账还不存在，而这个脚本今天会直接抛
    FileNotFoundError —— 那是"为本仓写死"的味道（我们那边永远有 FACTS.json）。
    语义仍是 fail-loud（空台账照样拒绝渲染），只是**把下一步写在错误里**。"""
    if not os.path.exists(OUT):
        print("FATAL: 还没有台账 %s\n"
              "       先在仓库根跑一遍量测：python3 zreflect/facts.py\n"
              "       然后再 --render-doc 把机器块写进文档。" % os.path.basename(OUT),
              file=sys.stderr)
        raise SystemExit(2)
    return load(OUT)


def main(argv):
    if argv and argv[0] == "--render":
        sys.stdout.write(render_block(_load_or_die()) + "\n")
        return 0
    if argv and argv[0] == "--render-doc":
        return write_doc(argv[1] if len(argv) > 1 else DOC, _load_or_die())
    if argv and argv[0] == "--check":
        return check_doc(argv[1] if len(argv) > 1 else DOC, _load_or_die())
    if argv and argv[0] == "--get":
        if len(argv) < 2:
            print("FATAL: --get 需要一个键名：--get KEY", file=sys.stderr)
            return 2
        ok, v = get_value(_load_or_die(), argv[1])
        if not ok:
            print("FATAL: %s" % v, file=sys.stderr)
            return 2
        print(v)                       # 只打印值本身：不解释、不带前缀
        return 0
    if argv and argv[0] == "show":
        led = _load_or_die()
        f = facts_of(led)
        keys = [argv[1]] if len(argv) > 1 else sorted(f)
        rc = 0
        for k in keys:
            if k not in f:
                print("没有这条事实：%s（现有：%s）" % (k, ", ".join(sorted(f))), file=sys.stderr)
                rc = 1
                continue
            e = f[k] if isinstance(f[k], dict) else {"value": f[k]}
            print("%-20s %s" % (k, e.get("value")))
            print("    出处  %s" % e.get("source", "?"))
            print("    复跑  %s" % e.get("cmd", "?"))
            if e.get("note"):
                print("    备注  %s" % e["note"])
        return rc
    return measure(argv)


CASES = [
    # ① 正常不报
    ("不掉条 ⇒ 守卫不报", lambda: dropped_keys({"a": 1}, {"a": 1, "b": 2}) == []),
    ("值没变 ⇒ 改口守卫不报", lambda: changed_keys({"a": {"value": 1}},
                                                   {"a": {"value": 1}}) == []),
    # ② 该报的必须报
    ("★ 掉条 ⇒ 守卫报出来", lambda: dropped_keys({"a": 1, "b": 2}, {"a": 1}) == ["b"]),
    ("★ 改口 ⇒ 守卫报出来且带旧值→新值",
     lambda: changed_keys({"a": {"value": 1}}, {"a": {"value": 2}}) == [("a", 1, 2)]),
    # ③ 空输入必须报
    ("★ 空文档（没有块标记）⇒ check_doc 必须报，不许算通过",
     lambda: (lambda: (open("/tmp/_zr_empty.md", "w").write("空空如也\n"),
                       check_doc("/tmp/_zr_empty.md", {"facts": {"a": 1}}))[1])() == 2),
    ("★ 文档文件不存在 ⇒ check_doc 必须报（不许因为找不到就算通过）",
     lambda: check_doc("/tmp/_zr_no_such_file_%d.md" % os.getpid(), {"facts": {"a": 1}}) == 2),
    # ① 逐条接受（issue #3 ①）
    ("解析：裸旗 --accept-changes ⇒ 全收", lambda: _accepted_keys(["--accept-changes"]) is None),
    ("解析：--accept-changes=k1,k2 ⇒ 键集",
     lambda: _accepted_keys(["--accept-changes=a,b"]) == {"a", "b"}),
    ("解析：没传旗 ⇒ 全拒（同旧行为）", lambda: _accepted_keys([]) is False),
    ("逐条接受：列出的键被滤掉，其余留下",
     lambda: filter_accepted([("a", 1, 2), ("b", 3, 4)], {"a"}) == [("b", 3, 4)]),
    ("裸旗 ⇒ 改口全被接受", lambda: filter_accepted([("a", 1, 2)], None) == []),
    ("★ 逐条接受：未列出的键必须仍算改口（该报的必须报）",
     lambda: filter_accepted([("a", 1, 2)], {"zzz"}) == [("a", 1, 2)]),
    ("★ 空接受集 ⇒ 一条都不收（空输入不是通过）",
     lambda: filter_accepted([("a", 1, 2)], set()) != []),
    # ② 测龄人话（issue #3 ②）
    ("年龄：缺失 measured_at ⇒ 明说未记录",
     lambda: _age_human({"value": 1}) == "未记录测量时间"),
    ("年龄：刚刚测的 ⇒ 今天",
     lambda: _age_human({"measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) == "今天测的"),
    # ④ 官方只读出口（issue #4 ④）
    ("--get：键存在（字典形状）⇒ (True, 裸值)",
     lambda: get_value({"facts": {"n": {"value": 12, "cmd": "c"}}}, "n") == (True, 12)),
    ("--get：键存在（裸值形状）⇒ (True, 值)",
     lambda: get_value({"facts": {"n": 7}}, "n") == (True, 7)),
    ("★ --get：键不存在 ⇒ (False, 错误句)（空输入不是通过）",
     lambda: get_value({"facts": {"n": 1}}, "zzz")[0] is False),
]


if __name__ == "__main__":
    sys.exit(selftest("facts.py（两道守卫 + 文档一致性）", CASES)
             if "--selftest" in sys.argv else main(sys.argv[1:]))
