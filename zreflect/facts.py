#!/usr/bin/env python3
"""事实台账的 CLI：量一遍、写台账、渲染机器块，以及**两道守卫**。

用法
    python3 zreflect/facts.py                      # 量一遍并写 FACTS.json（掉条/改口会拒绝）
    python3 zreflect/facts.py --allow-drop         # 允许本次掉条（掉掉的键会打出来）
    python3 zreflect/facts.py                      # 量一遍（数值事实 + 原则的判定命令）
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

import gate                                            # noqa: E402
from gate import module_meta, main_selftest_or, repo  # noqa: E402
from gate import machine                                  # noqa: E402
from i18n import M                                        # noqa: E402
from ledger import age_days, fact, facts_of, load, value_of  # noqa: E402
from render import BLOCK_BEGIN, BLOCK_END, render_block  # noqa: E402
import guard                                             # noqa: E402
import registry                                          # noqa: E402

REPO_REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_NAME = os.environ.get("REFLECT_FACTS", "FACTS.json")

def _out():
    """台账写盘路径。**函数而不是模块常量**：`repo()` 读的是 `gate.GATE_REPO`，
    而夹具会改它 —— 存成模块级字符串会让路径停在被 import 的那一刻。
    实测：改 `gate.GATE_REPO` 后，旧的 `OUT` 常量仍是原仓路径（陈旧快照）。"""
    return repo(LEDGER_NAME)
# ⚠️ **不是模块级常量**：`REFLECT_DOC` 是名字型旋钮，钩子在运行期间可以改它
# （夹具就换它）。`doc.state_name()` 每次现读 —— 唯一的产地。
# 此前这里有个 `DOC = os.environ.get(...)` 的 import 时快照，与
# `doc.state_name()` 构成**两个产地**（snapshot 闸门抓的那种形状）。
def _doc():
    import doc                                           # noqa: PLC0415
    return doc.state_name()


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
    for root, _dirs, files in os.walk(gate.GATE_REPO):
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
                             "repo", M("facts.note.example_fact"))
    facts["md_files"] = fact(n_md, "find . -name '*.md' -not -path './.git/*' | wc -l", "repo")
    # 这条刻意大于 BARE_MIN（check_facts 的裸数字阈值 = 100），好在 STATE.md 里
    # 演示「手抄这个数字会被闸门拦下」。太小的数字遍地都是，查了全是噪音 ⇒ 不查。
    facts["py_lines"] = fact(lines_py, "find . -name '*.py' -not -path './.git/*' "
                             "-exec cat {} + | wc -l", "repo",
                             M("facts.note.bare_number_demo"))
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
                             cwd=gate.GATE_REPO).stdout.strip()),
        md_lines_cmd, "repo",
        M("facts.note.excludes_machine_block"))

    # 例：**量不到就不写**。把 UPSTREAM_VERSION 设上才有这条事实。
    v = os.environ.get("UPSTREAM_VERSION", "").strip()
    if v:
        facts["upstream_version"] = fact(v, "echo \"$UPSTREAM_VERSION\"", "env",
                                         M("facts.note.measure_or_omit"))
    return facts


# ══ 以下不用改 ════════════════════════════════════════════════════════════════
def _has_principles_doc():
    """这个仓接受本套件的原则吗？—— **声明**在 `doc.accepts_principles()`，
    这里只转发（判断只在那一处）。"""
    import doc                                           # noqa: PLC0415
    return doc.accepts_principles()


def _doc_names():
    """有机器块的文档名（按 `_block_homes` 的归属派生，不手写名单）。"""
    import doc                                           # noqa: PLC0415
    return (_doc(), doc.PRINCIPLES)


def _block_homes(ledger):
    """**块 ← 文档**的归属（数据，不是散在代码里的 if）。

        AUTO:FACTS → STATE.md        台账渲染，**数字的唯一产地**
        AUTO:GATES → STATE.md        发现式名录渲染，**闸门叙述的唯一产地**
        AUTO:RULES → PRINCIPLES.md   纪律表渲染，**规矩叙述的唯一产地**

    为什么纪律块单独一份文档：纪律是「不变的设计原则」，状态是「此刻什么样」，
    历史是「当年的经过」。混在一份里 ⇒ `check_stale` 只能整份当活状态扫，
    历史里的旧数字一露面就红。

    返回 ([(文档名, [(begin, end, 渲染结果), …]), …], 错误句)。
    名录对账不过（缺声明 / 孤儿 / 旗标错）⇒ 拒绝渲染 —— 判据只有一份产地。
    """
    gs, missing = registry.gates()
    probs = registry.problems(gs, missing)
    if probs:
        return None, M("facts.registry_mismatch", entries="\n  · ".join(probs))
    import doc                                           # noqa: PLC0415
    return [
        (_doc(), [(BLOCK_BEGIN, BLOCK_END, render_block(ledger)),
               (registry.GATES_BEGIN, registry.GATES_END,
                registry.render_gates(gs))]),
        (doc.PRINCIPLES, [(doc.RULES_BEGIN, doc.RULES_END,
                           doc.render_rules())]),
    ], None



def write_doc(path_rel, ledger):
    """把机器块写进文档（就地替换）。没有标记就报错，**不悄悄追加** ——
    悄悄追加会让「块过期」变成「有两份块」，那是更难查的坏法。"""
    p = path_rel if os.path.isabs(path_rel) else repo(path_rel)
    if not os.path.exists(p):
        print(machine().emit("fatal", M("facts.doc_missing_render", path=p)),
              file=sys.stderr)
        return 2
    homes, err = _block_homes(ledger)
    if err:
        print(machine().emit("fatal", err), file=sys.stderr)
        return 2
    # 只校验**属于这个文档**的块。别的块的标记在别的文档里 —— 在这儿找不到是
    # 正常的（此前把所有块都往一份文档塞：纪律块的标记不在 STATE.md 里 ⇒ 报）。
    #
    # ⚠️ 找不到归属 ⇒ **必须报**，不许 `blocks=[]` 静默绿。一个不在归属表里的
    # 文档（比如老用户传了个自定义名字）没有块可校验，那「返回 0」就是在说
    # 「没有块过期」—— 一句什么都没查过的话。这是零值守卫。
    mine = [b for name, blocks in homes
            if name in (os.path.basename(path_rel), path_rel)
            for b in blocks]
    if not mine:
        print(machine().emit("fatal",
                              M("facts.doc_has_no_home", path=path_rel,
                                known=", ".join(name for name, _ in homes))),
              file=sys.stderr)
        return 2
    blocks = mine
    text = open(p, encoding="utf-8").read()
    new = text
    for begin, end, body in blocks:
        if begin not in new or end not in new:
            print(machine().emit("fatal",
                                  M("facts.markers_missing_render",
                                    path=path_rel, begin=begin, end=end)),
                  file=sys.stderr)
            return 2
        pre, _, rest = new.partition(begin)
        _, _, post = rest.partition(end)
        new = pre + body + post
    # 写盘前的完整性守卫：替换必须保得住**全部**块的标记。标记字面量若被
    # 写进正文（哪怕在行内代码里），首现替换会把两块之间的内容整个吞掉、
    # 让别的块消失 —— 实测踩过：bullet 里写了标记字面量，渲染一次丢掉整个
    # 事实块。歧义 ⇒ 拒绝写盘，人先修文档（块内 cmd 引用 begin 字面量是
    # 合法嵌套 —— md_lines 的 awk 判据 —— 故不做替换前的计数断言）。
    for begin, end, _ in blocks:
        if begin not in new or end not in new:
            print(machine().emit("fatal",
                                  M("facts.marker_swallowed_body",
                                    path=path_rel, begin=begin)),
                  file=sys.stderr)
            return 2
    if new != text:
        open(p, "w", encoding="utf-8").write(new)
        print(M("facts.render_written", path=path_rel))
    else:
        print(M("facts.render_unchanged", path=path_rel))
    return 0


def check_doc(path_rel, ledger):
    p = path_rel if os.path.isabs(path_rel) else repo(path_rel)
    if not os.path.exists(p):
        print(machine().emit("fatal", M("facts.doc_missing_check", path=p)), file=sys.stderr)
        return 2
    homes, err = _block_homes(ledger)
    if err:
        print(machine().emit("fatal", err), file=sys.stderr)
        return 2
    # 只校验**属于这个文档**的块。别的块的标记在别的文档里 —— 在这儿找不到是
    # 正常的（此前把所有块都往一份文档塞：纪律块的标记不在 STATE.md 里 ⇒ 报）。
    #
    # ⚠️ 找不到归属 ⇒ **必须报**，不许 `blocks=[]` 静默绿。一个不在归属表里的
    # 文档（比如老用户传了个自定义名字）没有块可校验，那「返回 0」就是在说
    # 「没有块过期」—— 一句什么都没查过的话。这是零值守卫。
    mine = [b for name, blocks in homes
            if name in (os.path.basename(path_rel), path_rel)
            for b in blocks]
    if not mine:
        print(machine().emit("fatal",
                              M("facts.doc_has_no_home", path=path_rel,
                                known=", ".join(name for name, _ in homes))),
              file=sys.stderr)
        return 2
    blocks = mine
    text = open(p, encoding="utf-8").read()
    for begin, end, body in blocks:
        if begin not in text or end not in text:
            print(machine().emit("fatal",
                                  M("facts.markers_missing_check",
                                    path=path_rel, begin=begin, end=end)),
                  file=sys.stderr)
            return 2
        cur = text.split(begin, 1)[1].split(end, 1)[0]
        fresh = body.split(begin, 1)[1].split(end, 1)[0]
        if cur != fresh:
            print(machine().emit("fatal",
                                  M("facts.block_stale",
                                    path=path_rel, begin=begin)),
                  file=sys.stderr)
            return 1
    print(M("facts.block_consistent", path=path_rel))
    return 0


def _age_human(entry):
    """`measured_at` 的人话（issue #3 ②）：今天 / N 天前 / 未记录。"""
    d = age_days(entry)
    if d is None:
        return M("facts.age.unrecorded")
    if d < 1:
        return M("facts.age.today")
    return M("facts.age.days_ago", days=int(d))


def _measure():
    """采集入口（issue #15 A1/C3）：`REFLECT_MEASURE_MODULE` 旋钮分派。

    · 旋钮未配 / 模块导入失败 / 夹具场景（gate.GATE_REPO 不是本仓）⇒ 回落
      `measure_example()`（占位），并**打印警告** —— 下游实测过：手动跑
      facts.py 忘带旋钮 ⇒ 空表 + `--allow-drop` 诱惑（OM 仓「会掉 24 条」
      的吓人 FATAL，真因只是旋钮没传）。回落必须可闻，不许静默。
    · 旋钮已配且导入成功且 gate.GATE_REPO 是真仓 ⇒ 用旋钮指定的 measure()。
    """
    mod_name = os.environ.get("REFLECT_MEASURE_MODULE", "").strip()
    if mod_name:
        try:
            _m = __import__(mod_name)
            fn = getattr(_m, "measure")   # noqa: B009 — 模块是变量，属性名固定是契约
            if os.path.abspath(gate.GATE_REPO) == os.path.abspath(REPO_REAL):
                return fn()
        except Exception as e:                            # noqa: BLE001
            print("⚠ %s" % M("facts.measure_module_unusable",
                             module=mod_name, error=repr(e)), file=sys.stderr)
    else:
        # ⚠️ 警告**不分仓**：此前只在「GATE_REPO 就是套件自己的仓」时打，
        # 于是**所有下游仓**（正是最需要这条提示的地方）静默拿到一份
        # 「关于 Einfacht 的数字」（子代理验收实测：新仓 `py_lines 13269`
        # 而它的代码只有 67 行，`STATE.md` 里写的全是套件自己的规模）。
        print("⚠ %s" % M("facts.measure_placeholder_used"), file=sys.stderr)
        # 再给一条**具体**的：这个仓有它自己的代码吗？有就说怎么量它。
        own = _own_code_hint()
        if own:
            print("  %s" % own, file=sys.stderr)
    return measure_example()


# 一个仓「有自己的代码」的常见形状（只看目录名，不猜内容）。
_OWN_CODE_DIRS = ("src", "lib", "app", "pkg", "packages")


def _own_code_hint():
    """这个仓看起来有自己的代码吗？有 ⇒ 返回一句**具体**的提示。

    只在 `REFLECT_MEASURE_MODULE` 没配时调用 —— 那是「你还没告诉我要量什么」
    的时刻，也是唯一该提示的时刻。
    """
    root = gate.GATE_REPO
    found = [d for d in _OWN_CODE_DIRS if os.path.isdir(os.path.join(root, d))]
    if not found:
        return None
    return str(M("facts.measure_own_code_hint", dirs=", ".join(found)))


def measure(argv):
    """量一遍并写台账。**必须接 `argv`** —— 两道守卫都要读它。

    ⚠️ 这里踩过：`measure()` 曾经没有 `argv` 参数，而守卫里写着 `not in argv`。
    因为 `and` 短路，**只在真的掉条时**才走到那句 ⇒ 报的不是「掉了哪几条」而是一段
    NameError traceback；`--allow-drop` 从未生效过。写盘被拦住只是**顺带**（异常早于写盘），
    那不叫守卫，那叫故障。所以本文件把 argv 显式传进来；守卫的**决策**在
    `zreflect/guard.py`（decide()，接线有自证），本函数只执行它。
    """
    facts = _measure()
    # 原则是与数值事实同处一张表的事实 —— 一起量、一起守、一起复跑。
    # 「唯二必须丈量的东西」= STATE（这些数值）与 PRINCIPLE（这些判定）。
    #
    # ⚠️ 只在**有 PRINCIPLES.md 的仓**里登记原则：跨仓夹具的临时目录没有那份
    # 文档，把本仓的原则复制进它的台账 ⇒ 每条命令都在外仓语境下跑，全红
    # （实测）。「这个仓要不要遵守这些原则」由**那份文档存在与否**决定 ——
    # 与 `_block_homes` 用的是同一个声明（块 ← 文档），不是第二套判断。
    import doc                                           # noqa: PLC0415
    if _has_principles_doc():
        facts.update(doc.facts_of_rules())

    out = _out()
    old = facts_of(load(out)) if os.path.exists(out) else {}

    verdict, problems, notes = guard.decide(old, facts,
                                            accepted=guard.accepted_keys(argv),
                                            allow_drop="--allow-drop" in argv)
    for x in notes["err"]:
        print(x, file=sys.stderr)
    for x in notes["out"]:
        print(x)
    if verdict == "refuse":
        for x in problems:
            print(machine().emit("fatal", x), file=sys.stderr)
        return 2

    # 仪器生命周期（issue #6 ①）：值没变的键沿用旧 first_seen
    # （换值 / 新键的 first_seen 已由 ledger.fact() 盖今天）——
    # 恒常检测（可插拔闸门 check_instruments.py）靠它。
    for k, entry in facts.items():
        o = old.get(k)
        fs = o.get("first_seen") if isinstance(o, dict) else None
        if fs and value_of(o) == value_of(entry):
            entry["first_seen"] = fs

    # 盲写守卫（issue #20 ②）：写盘前查目标 —— 被 gitignore 覆盖 ⇒ FATAL；
    # 仓里有 Einfacht.env 而本次没设旋钮 ⇒ warn（两个产地此刻分叉）。
    fatal_w, warn_w = guard.write_target_problems(
        out, knob_set=bool(os.environ.get("REFLECT_FACTS", "").strip()))
    if warn_w:
        print("⚠ %s" % warn_w, file=sys.stderr)
    if fatal_w:
        print(machine().emit("fatal", fatal_w), file=sys.stderr)
        return 2
    import json                                         # noqa: PLC0415
    import time                                         # noqa: PLC0415
    doc = {"schema": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "_why": M("facts.ledger_why"),
           "facts": facts}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(M("facts.measure_written",
            path=os.path.relpath(out, gate.GATE_REPO), count=len(facts)))
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
        return False, M("facts.unknown_key", key=key,
                        existing=", ".join(sorted(f)) or M("facts.none"))
    return True, value_of(f[key])


def _load_or_empty():
    """读台账；**不存在就给空台账**（`--accept*` 用）。

    为什么和 `_load_or_die` 分开：「手动注册第一条事实」与「渲染/校验」是两件事 ——
    前者**本来就该能在新仓里创建台账**，后者没有台账就没什么可校验。
    合用一个读法会让 `--accept` 在新仓里 FATAL（实测）。
    """
    out = _out()
    if not os.path.exists(out):
        return {"schema": 1, "facts": {}}
    return load(out)


def _load_or_die():
    """读台账；**没有就给出可操作的提示**而不是原始 traceback。
    为什么单列：新仓库第一次用时台账还不存在，而这个脚本今天会直接抛
    FileNotFoundError —— 那是"为本仓写死"的味道（我们那边永远有 FACTS.json）。
    语义仍是 fail-loud（空台账照样拒绝渲染），只是**把下一步写在错误里**。"""
    out = _out()
    if not os.path.exists(out):
        # issue #20 ② 补充 2：旧提示「先在仓库根跑一遍量测」正是写出野文件
        # 的那个动作 —— 提示文本本身也是「默认值产地」的一部分，不许教人
        # 踩坑。改说「先确认 REFLECT_FACTS 指向哪里」。
        print(machine().emit("fatal",
                              M("facts.no_ledger_yet",
                                name=os.path.basename(out),
                                path=os.path.relpath(out, gate.GATE_REPO))),
              file=sys.stderr)
        raise SystemExit(2)
    return load(out)


def main(argv):
    if argv and argv[0] == "--render":
        sys.stdout.write(render_block(_load_or_die()) + "\n")
        return 0
    if argv and argv[0] == "--render-doc":
        return write_doc(argv[1] if len(argv) > 1 else _doc(), _load_or_die())
    if argv and argv[0] == "--check":
        # 不给文档名 ⇒ 查**全部**有机器块的文档（`_block_homes` 是唯一产地）。
        # 「唯二必须丈量的东西」= STATE（数值）+ PRINCIPLE（判定）—— 两份文档
        # 都在这个面上，少查一份就是让那份的「不要手改」变成空话。
        if len(argv) > 1:
            return check_doc(argv[1], _load_or_die())
        ledger = _load_or_die()
        rc = 0
        for name in _doc_names():
            r = check_doc(name, ledger)
            rc = rc or r
        return rc
    if argv and argv[0] == "--get":
        if len(argv) < 2:
            print(machine().emit("fatal", M("facts.get_needs_key")), file=sys.stderr)
            return 2
        ok, v = get_value(_load_or_die(), argv[1])
        if not ok:
            print(machine().emit("fatal", v), file=sys.stderr)
            return 2
        print(v)                       # 只打印值本身：不解释、不带前缀
        return 0
    if argv and argv[0] == "--init":
        # **新仓 bootstrap**：一次生成合格骨架，而不是让人照文档猜标记名。
        #
        # ⚠️ 这条是验收驱动的（子代理在全新仓里照 `AGENTS.md` 逐字做，卡在
        # `FATAL: facts.doc_missing_render` —— 文档说「建 STATE.md」，
        # 但没说它必须含 `<!-- AUTO:FACTS -->` / `<!-- AUTO:GATES -->`，
        # 而那两个字符串只住在 `render.py` 源码里）。
        #
        # 它**不覆盖**已存在的文件（只补缺的），并且明确打印每一步做了什么。
        import doc                                       # noqa: PLC0415
        import registry as _reg                          # noqa: PLC0415
        root = gate.GATE_REPO
        state = doc.state_name()
        created, kept = [], []
        files = {
            state: (
                "# " + state + "\n\n"
                "> live state: only what is true **now**. Cite numbers by\n"
                "> key (double-bracket form), never hand-copy them.\n\n"
                "## Now\n\n"
                "<!-- write what is true NOW; cite numbers by key -->\n\n"
                + BLOCK_BEGIN + "\n" + BLOCK_END + "\n\n"
                + _reg.GATES_BEGIN + "\n" + _reg.GATES_END + "\n"),
            doc.PRINCIPLES: (
                "# PRINCIPLES\n\n"
                "> design rules that do not change. Each one is a **runnable\n"
                "> command**, replayed by `check_facts_replay` on every commit.\n\n"
                + doc.RULES_BEGIN + "\n" + doc.RULES_END + "\n"),
            "retractions.json": '{"schema": 1, "retractions": []}\n',
            "README.md": (
                "# " + os.path.basename(root) + "\n\n"
                "> the project's human-facing docs. `check_readme_sync` treats the\n"
                "> README trio as three copies of one assertion — if you add\n"
                "> `README.zh.md` / `README.de.md`, keep all three in step.\n"),
            "AGENTS.md": (
                "# AGENTS.md\n\n"
                "Routing only. Rules live in `zreflect/doc.py` (`RULES`);\n"
                "state lives in `" + state + "`; history is not tracked.\n\n"
                "```bash\n"
                "python3 zreflect/registry.py --run commit\n"
                "python3 zreflect/harness.py\n"
                "```\n"),
        }
        for name, body in files.items():
            p = os.path.join(root, name)
            if os.path.exists(p):
                kept.append(name)
                continue
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            created.append(name)
        for n in created:
            print(str(M("facts.init_created", name=n)))
        for n in kept:
            print(str(M("facts.init_kept", name=n)))
        if created:
            # 原则也要进台账 —— 否则 `PRINCIPLES.md` 的 `[[RULES:…]]` 引用
            # 在新仓里全是坏引用（实测：`facts.missing_key_cite(line=3)`）。
            if doc.accepts_principles():
                import json as _json                        # noqa: PLC0415
                out = _out()
                led = _load_or_empty()
                facts = dict(facts_of(led))
                facts.update(doc.facts_of_rules())
                with open(out, "w", encoding="utf-8") as fh:
                    _json.dump({"schema": 1, "_why": M("facts.ledger_why"),
                                "facts": facts}, fh, indent=1,
                               ensure_ascii=False)
                    fh.write("\n")
            # **按实际生成的文档**写一份 `Einfacht.env`：默认旋钮假设你已经
            # 有六份文档（STATE/AGENTS/PRINCIPLES/README×3），而新仓只有
            # 刚生成的那几份。不写这一份 ⇒ 每个闸门都报「找不到 README.zh.md」。
            # `questions/` 目录：`check_questions` 要求它存在（悬案闸门）。
            qdir = os.path.join(root, os.environ.get("REFLECT_QUESTIONS", "")
                                .strip() or "questions")
            if not os.path.isdir(qdir):
                os.makedirs(qdir, exist_ok=True)
                print(str(M("facts.init_created", name="questions/")))
            # 空目录会被 `check_questions` 的零值守卫拒（`questions.guard_empty`）
            # —— 放一个**示例悬案**：它同时是「怎么写悬案」的样板。
            if os.path.isdir(qdir) and not [n for n in os.listdir(qdir)
                                            if n.endswith(".md")]:
                with open(os.path.join(qdir, "01-example.md"), "w",
                          encoding="utf-8") as fh:
                    fh.write(
                        "# Example open question\n\n"
                        "**Status:** ready-for-agent\n\n"
                        "**Settling:** `python3 -c \"raise SystemExit(1)\"` "
                        "— rc=0 settles A; rc=1 settles B\n\n"
                        "Replace this with a real open question, or delete it\n"
                        "once you have some.\n")
            env_path = os.path.join(root, "Einfacht.env")
            if not os.path.exists(env_path):
                docs = ",".join(n for n in (state, doc.PRINCIPLES, "AGENTS.md")
                                if os.path.exists(os.path.join(root, n)))
                with open(env_path, "w", encoding="utf-8") as fh:
                    fh.write("export REFLECT_DOC=%s\n" % state)
                    fh.write("export REFLECT_DOCS=%s\n" % docs)
                    fh.write("export REFLECT_READMES=README.md\n")
                print(str(M("facts.init_created", name="Einfacht.env")))
            print(str(M("facts.init_next")))
        return 0
    if argv and argv[0] == "--accept-principles":
        # 「原则进台账」的显式出口。**此前只写在 docstring 里，没有实现**
        # （review 抓到的幻影）—— 而它是用户需求的一部分：「其他的当然也可以
        # 被手动注册成为被检测的东西」。
        #
        # 它写的是**原则的判定命令**（`principle.*`），不碰数值事实；写盘仍过
        # 同一道守卫（掉条 / 改口都要显式接受）。
        import doc as _doc                              # noqa: PLC0415
        led = _load_or_empty()
        new = facts_of(led)
        new.update(_doc.facts_of_rules())
        return _write_ledger(led, new, argv, accept_all=True)
    if argv and argv[0] == "--accept":
        # 手动注册一条事实：`--accept <key> <value> <cmd> <source>`
        # （用户自己的量测，不必改 measure()）。值必须是**裸值**。
        if len(argv) < 5:
            print(machine().emit("fatal", M("facts.accept_usage")), file=sys.stderr)
            return 2
        key, value = _arg(argv, 1), _arg(argv, 2)
        cmd, source = _arg(argv, 3), _arg(argv, 4)
        if not key or not cmd.strip():
            print(machine().emit("fatal", M("facts.accept_usage")), file=sys.stderr)
            return 2
        led = _load_or_empty()
        new = dict(facts_of(led))
        new[key] = fact(value, cmd, source)
        return _write_ledger(led, new, argv, accept_all=True)
    if argv and argv[0] == "show":
        led = _load_or_die()
        f = facts_of(led)
        keys = [argv[1]] if len(argv) > 1 else sorted(f)
        rc = 0
        for k in keys:
            if k not in f:
                print(M("facts.show_unknown_key", key=k,
                        existing=", ".join(sorted(f))), file=sys.stderr)
                rc = 1
                continue
            e = f[k] if isinstance(f[k], dict) else {"value": f[k]}
            print("%-20s %s" % (k, e.get("value")))
            print(M("facts.show.source", value=e.get("source", "?")))
            print(M("facts.show.cmd", value=e.get("cmd", "?")))
            if e.get("note"):
                print(M("facts.show.note", value=e["note"]))
        return rc
    return measure(argv)


def _arg(argv, i):
    return argv[i] if len(argv) > i else ""


def _write_ledger(led, facts, argv, accept_all=False):
    """把 `facts` 写回台账（过同一道守卫）。`accept_all` ⇒ 本次改口全部接受。"""
    out = _out()
    old = facts_of(led)
    accepted = None if accept_all else guard.accepted_keys(argv)
    verdict, problems, notes = guard.decide(old, facts, accepted=accepted,
                                            allow_drop="--allow-drop" in argv)
    for x in notes["err"]:
        print(x, file=sys.stderr)
    if verdict == "refuse":
        for x in problems:
            print(machine().emit("fatal", x), file=sys.stderr)
        return 2
    # ⚠️ **同一个盲写守卫**：`measure()` 写盘前查目标（被 gitignore 覆盖 ⇒
    # FATAL；有载体却没设旋钮 ⇒ warn）。`--accept*` 是**第二条写盘路径** ——
    # 漏了它就能写进 gitignored 路径而 rc=0（实测：`.gitignore` 里有 L.json
    # 时 `--accept` 照写，`measure` 照 FATAL）。两条路径必须同一道守卫（C4）。
    fatal_w, warn_w = guard.write_target_problems(
        out, knob_set=bool(os.environ.get("REFLECT_FACTS", "").strip()))
    if warn_w:
        print("⚠ %s" % warn_w, file=sys.stderr)
    if fatal_w:
        print(machine().emit("fatal", fatal_w), file=sys.stderr)
        return 2
    import json                                          # noqa: PLC0415
    import time                                          # noqa: PLC0415
    doc = {"schema": 1,
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "_why": M("facts.ledger_why"),
           "facts": facts}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(M("facts.measure_written",
            path=os.path.relpath(out, gate.GATE_REPO), count=len(facts)))
    return 0


def _tmp_doc(content, name="doc.md"):
    """自证用的临时文档（tempfile + atexit 清理 —— 此前写固定的 /tmp
    路径，非 pid 唯一，并行跑两份自证会互相踩）。"""
    import atexit                                        # noqa: PLC0415
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    p = os.path.join(d, name)
    open(p, "w").write(content)
    return p


CASES = [
    # ③ 空输入必须报（守卫的决策接线在 zreflect/guard.py 的自证里；
    #    掉条 / 改口的纯函数在 ledger.py 的自证里 —— 各归各）
    ("★ facts.check_doc_no_markers",
     lambda: check_doc(_tmp_doc("empty document\n"), {"facts": {"a": 1}}) == 2),
    ("★ facts.check_doc_file_missing",
     lambda: check_doc(os.path.join(_tmp_doc("", "x.md"), "..",
                                    "no_such_%d.md" % os.getpid()),
                       {"facts": {"a": 1}}) == 2),
    # ② 测龄人话（issue #3 ②）
    ("facts.age_unrecorded",
     lambda: _age_human({"value": 1}).code == "facts.age.unrecorded"),
    ("facts.age_today",
     lambda: _age_human({"measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}).code
     == "facts.age.today"),
    # ④ 官方只读出口（issue #4 ④）
    ("facts.get_dict_shape",
     lambda: get_value({"facts": {"n": {"value": 12, "cmd": "c"}}}, "n") == (True, 12)),
    ("facts.get_bare_shape",
     lambda: get_value({"facts": {"n": 7}}, "n") == (True, 7)),
    ("★ facts.get_unknown_key",
     lambda: get_value({"facts": {"n": 1}}, "zzz")[0] is False),
]


MODULE = module_meta("台账 CLI", "量一遍 / 渲染 / --get / 两道守卫", selftest=True)


if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], M("gate.title.facts_cli"),
                              CASES, main))



