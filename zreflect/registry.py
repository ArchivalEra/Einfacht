#!/usr/bin/env python3
"""registry —— 发现式名录的数据面：闸门清单 / 插件清单 / 红名单。

「登记是被发现的，不是被记得的」—— 本仓早已把闸门的**集合**做成发现式
（hooks / runner / CI 的 `for g in zreflect/check_*.py`），但集合的**叙述**
仍是手写：STATE.md 手写「N 道闸门」并逐一列名（实测漂过：ab/locks/pins
并入的当天，清单就少了三道，没有任何闸门拦得住 —— 手写的"十道"连道数
都数错了）；gates-selftest.sh 手写红名单（默认名下实际红的 6 道，名单里
只有 4 道）；插件与 doctor 靠点名。本 module 把叙述做成数据：

  · `gates()`：ast 解析每个 check_*.py 的模块级声明行
        GATE = gate.meta("名字", "一句话", knobs=(…), name_dependent=…)
    —— **声明即登记**；不 import 闸门模块（无副作用、无执行成本）。
    没有声明行的 check_*.py ⇒ 名录不收（problems 报，render 拒绝渲染）；
  · `red_need()`：换名自证里**必须红**的闸门（默认名承担载荷的那批）。
    name_dependent 旗标是显式登记的 —— 机器推不出「off 态短路」（仪器
    闸门默认关着，它消费的默认名永远轮不到用，不能凭消费就断言红），
    但登记被两头拦：夹具要求它真红，`problems()` 要求它真消费改名的
    默认名；
  · `plugins()`：reflect-hooks/*.sh 带自证标记的（发现式）+ 点名特殊件
    （doctor.py —— 理由住在数据旁）。

消费方：`facts.py --render-doc` 渲染 AUTO:GATES 机器块（同 AUTO:FACTS
先例 —— 手写清单退役，`check_facts` / `--check` 自动拦漂移）；
gates-selftest.sh 消费 `--red-need` 与 `--plugins`（手写红名单、
插件与 doctor 的点名退役）。

诚实边界：本 module 只**叙述**名录，不执行闸门；闸门能不能红永远由
gates-selftest.sh 实跑证明 —— 叙述与执行的判据各归各，别混。
"""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import fatal, repo, selftest                    # noqa: E402
from knobs import REGISTRY                                # noqa: E402

GATES_BEGIN = "<!-- AUTO:GATES -->"
GATES_END = "<!-- /AUTO:GATES -->"


def _zdir():
    """闸门名录所在的目录 = **本文件所在处**，与 GATE_REPO 无关。

    名录是**工具**的属性（`zreflect/` 里的 check_*.py 就是工具自带的那批），
    不是**被检查仓库**的属性：GATE_REPO 指向「被检查的仓库」（可能是换名
    夹具、别的仓库），那里根本没有 zreflect/ 目录 —— 用 repo("zreflect")
    会让夹具里名录为空、render 拒绝（实测踩到：换名自证的夹具里
    check_facts 因「名录空」而红）。"""
    return os.path.dirname(os.path.abspath(__file__))

# 换名自证的夹具把哪些默认名改掉了（gates-selftest.sh 跨仓库节的改名面）。
# 名册纪律同 knobs：只登记真的被夹具改名的默认名 —— 这是红名单对账的判据数据。
RENAMED_DEFAULTS = ("FACTS.json", "STATE.md", "retractions.json", "questions",
                    "README.md", "README.zh.md", "README.de.md")

# 点名自证的特殊件（不是 check_*.py，发现式名录扫不到 —— 理由住在数据旁）。
SPECIAL_PLUGINS = (
    ("zreflect/doctor.py",
     "开工预检查的是会死的东西（issue #10）：挂 pre-commit 频率错，"
     "故意不进发现式名录 —— 但自证没人跑就会漂，所以点名一次"),
)


def selftest_modules(zdir=None):
    """发现式自证模块名录：zreflect/*.py 里**写了自证**（`_cases` / `CASES`）
    的模块 —— 不分是不是 check_*.py。返回 (mods, missing)。

    为什么需要它：本仓立身的纪律「没人跑的检查器 = 没人盯」（runner 只扫
    check_*.py）治的是**闸门**，却漏了**平台模块**（guard / knobs / registry /
    render / ledger / facts）—— 它们也写自证，但此前没有任何 harness 执行，
    自证存在而从不运行 = 装饰（实测：Phase 4 加的 guard.py 正犯此病）。
    「登记被两头拦」：`mods` 里每个都必须带自证机器摘要行（harness 实跑校验），
    `missing` 里每个都不许写 `_cases` / `CASES`（写而不登记 = 不可机器读的自证）。
    """
    d = zdir if zdir is not None else _zdir()
    mods, missing = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        try:
            tree = ast.parse(open(os.path.join(d, n), encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        if not _has_cases(tree):
            continue
        text = open(os.path.join(d, n), encoding="utf-8").read()
        can = ("--selftest" in text or "main_selftest_or" in text
               or "_selftest()" in text)
        rel = "zreflect/" + n
        if can:
            mods.append(rel)
        else:
            missing.append(rel)
    return mods, missing


def _has_cases(tree):
    """模块里**写**了自证用例（`_cases` 或 `CASES` 赋值/定义）。

    只认这两个名字：`selftest` 不算 —— gate.py 自己**定义** selftest（平台
    函数），拿它当判据会把平台本身误收进名录（实测踩到：gate.py 被当模块
    自证跑，却没有用例清单、也不该有）。
    """
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ("_cases", "CASES"):
                    return True
        if isinstance(node, ast.FunctionDef) and node.name == "_cases":
            return True
    return False


def gates(zdir=None):
    """发现式闸门名录：ast 解析每个 check_*.py 的模块级声明行。

    返回 (gates, missing)。gates = [{file, name, desc, knobs,
    name_dependent}]；missing = **叫 check_ 却没有声明行**的文件
    （problems 报、render 拒绝 —— 那是「忘了写声明」的形状）。

    发现谓词 = `check_` 前缀（**执行面也用它**：hooks / CI / runner 的
    `for g in zreflect/check_*.py`）—— 谓词只能有一个，否则「被发现」与
    「被执行」会分叉。命名约定于是是**承重的**：`check_` = 会被执行的闸门。
    「声明了却不叫 check_」的孤儿由 `misnamed()` 报告（不许静默 ——
    否则它进了 AUTO:GATES 却不被跑，比完全看不见更坏）。
    """
    d = zdir if zdir is not None else _zdir()
    out, missing = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []                     # zreflect/ 不在：调用方按零值守卫报
    for n in names:
        if not (n.startswith("check_") and n.endswith(".py")):
            continue
        rel = "zreflect/" + n
        meta = _declaration(os.path.join(d, n), rel)
        if meta:
            out.append(meta)
        else:
            missing.append(rel)
    return out, missing


def misnamed(zdir=None):
    """**声明了却不叫 check_** 的文件（孤儿）：它们进了 AUTO:GATES 的叙述，
    却不被执行面（glob `check_*.py`）跑到 —— 静默缺口，必须报。"""
    d = zdir if zdir is not None else _zdir()
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        if n.startswith("check_"):
            continue
        rel = "zreflect/" + n
        if _declaration(os.path.join(d, n), rel):
            out.append(rel)
    return out


def _declaration(path, rel):
    """从文件里 ast 提取 `GATE = meta(名字, 一句话, knobs=…, name_dependent=…)`。
    没有 ⇒ None。"""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "GATE"
                and isinstance(node.value, ast.Call)
                and len(node.value.args) >= 2):
            func = node.value.func
            # 两种等价写法都认：meta(…)（裸导入名）与 gate.meta(…)（属性）
            if not (getattr(func, "id", "") == "meta"
                    or getattr(func, "attr", "") == "meta"):
                continue
            try:
                knobs, name_dep = (), False
                for kw in node.value.keywords:
                    if kw.arg == "knobs":
                        knobs = ast.literal_eval(kw.value)
                    elif kw.arg == "name_dependent":
                        name_dep = ast.literal_eval(kw.value)
                return {"file": rel,
                        "name": ast.literal_eval(node.value.args[0]),
                        "desc": ast.literal_eval(node.value.args[1]),
                        "knobs": tuple(knobs),
                        "name_dependent": bool(name_dep)}
            except (ValueError, IndexError):
                return None
    return None


def _touches_renamed(g):
    """这道闸门消费的旋钮里，有没有默认名被换名自证改名。"""
    for k in g["knobs"]:
        kind, dflt, _ = REGISTRY.get(k, ("", "", ""))
        vals = ({x.strip() for x in dflt.split(",")} if kind == "list"
                else {dflt} if dflt else set())
        if vals & set(RENAMED_DEFAULTS):
            return True
    return False


def problems(gs, missing, orphans=None, mods=None, mods_missing=None):
    """名录的对账（纯函数）：空 = 绿。自证期间不许 print。

    `orphans` / `mods` / `mods_missing` 可注入（自证用夹具目录）；
    None ⇒ 现读真仓。

    · 叫 check_ 却没有 GATE 声明行 ⇒ 报（忘写声明 = 叙述会漂）；
    · 声明了却不叫 check_ ⇒ 报（孤儿：进叙述却不被执行面跑到）；
    · 标了 name_dependent 却不消费任何改名默认名 ⇒ 报（旗标错了）；
    · 写了自证却没有 --selftest 入口 ⇒ 报（写而不跑 = 装饰）；
    · 名录整体为空 ⇒ 报（零值守卫）。
    """
    out = []
    if missing:
        out.append("以下闸门没有 GATE = gate.meta(…) 声明行 —— 名录不收"
                   "无名之辈（手写名录会漂，声明即登记）：%s"
                   % ", ".join(missing))
    orph = misnamed() if orphans is None else orphans
    if orph:
        out.append("以下文件声明了 GATE 却不叫 check_ —— 发现谓词是 check_ 前缀"
                   "（执行面 hooks/CI 也用它），孤儿会进 AUTO:GATES 叙述却不被"
                   "执行（比看不见更坏）。改名成 check_*.py，或去掉声明：%s"
                   % ", ".join(orph))
    for g in gs:
        if g["name_dependent"] and not _touches_renamed(g):
            out.append("`%s` 标了 name_dependent，但消费的旋钮没有一个默认名"
                       "在换名自证的改名清单里 —— 旗标错了（要么去掉旗标，"
                       "要么把新默认名加进 registry.RENAMED_DEFAULTS）"
                       % g["file"])
    if not gs and not missing:
        out.append("一个闸门都没发现 —— 零值守卫：空输入不是通过")
    if mods is None or mods_missing is None:
        mods, mods_missing = selftest_modules()
    if mods_missing:
        out.append("以下模块写了自证用例（_cases/CASES）却没有 --selftest 入口 —— "
                   "写而不跑的自证 = 装饰：%s" % ", ".join(mods_missing))
    if not mods:
        out.append("没有任何平台模块自证可发现 —— 零值守卫：空输入不是通过")
    return out


def red_need(gs=None):
    """换名自证里**必须红**的闸门文件名（默认名承担载荷的那批）。"""
    if gs is None:
        gs, _ = gates()
    return sorted(os.path.basename(g["file"]) for g in gs
                  if g["name_dependent"] and _touches_renamed(g))


def plugins(hooks_dir=None):
    """自证点名的插件清单：reflect-hooks/*.sh 带自证标记的（发现式收编）
    + 点名特殊件（doctor.py —— 理由见 SPECIAL_PLUGINS）。"""
    d = hooks_dir if hooks_dir is not None else repo("reflect-hooks")
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        names = []
    for n in names:
        if not n.endswith(".sh"):
            continue
        try:
            text = open(os.path.join(d, n), encoding="utf-8",
                        errors="replace").read()
        except OSError:
            continue
        if "--selftest" in text:
            out.append("reflect-hooks/" + n)
    out.extend(p for p, _why in SPECIAL_PLUGINS)
    return out


def render_gates(gs):
    """闸门名录 → AUTO:GATES 机器块（含首尾标记）。**纯函数**：
    同一名录渲染两次逐字节相同。"""
    lines = [GATES_BEGIN,
             "> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录"
             "（zreflect/registry.py 的声明行）渲染，**不要手改**。",
             "",
             "| 闸门 | 它挡住什么 | 消费的旋钮 |", "|---|---|---|"]
    for g in sorted(gs, key=lambda x: x["file"]):
        lines.append("| `%s`（%s） | %s | %s |"
                     % (os.path.basename(g["file"]), g["name"], g["desc"],
                        ", ".join("`%s`" % k for k in g["knobs"]) or "—"))
    lines += ["", "%d 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = "
              "落一个声明行，这里自动长出来）。" % len(gs), GATES_END]
    return "\n".join(lines)


def main(argv):
    if "--red-need" in argv:
        print(" ".join(red_need()))
        return 0
    if "--plugins" in argv:
        print("\n".join(plugins()))
        return 0
    if "--selftest-modules" in argv:
        mods, missing = selftest_modules()
        for m in missing:
            print("  ❌ %s 写了自证却没有 --selftest 入口（写而不跑 = 装饰）" % m,
                  file=sys.stderr)
        if missing:
            return 1
        print("\n".join(mods))
        return 0
    if "--gates" in argv:
        gs, missing = gates()
        probs = problems(gs, missing)
        for x in probs:
            print("  · %s" % x, file=sys.stderr)
        if probs:
            return fatal("名录有问题（%d）" % len(probs))
        for g in gs:
            print("%s\t%s\t%s" % (g["file"], g["name"], g["desc"]))
        return 0
    print("用法：registry.py [--gates|--red-need|--plugins|--selftest-modules|--selftest]",
          file=sys.stderr)
    return 2


def _cases():
    import atexit                                        # noqa: PLC0415
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    open(os.path.join(d, "check_ok.py"), "w").write(
        'GATE = gate.meta("甲闸门", "挡甲", knobs=("REFLECT_FACTS",),'
        ' name_dependent=True)\n')
    open(os.path.join(d, "check_plain.py"), "w").write(
        'GATE = gate.meta("乙闸门", "挡乙", knobs=("REFLECT_WORLD",))\n')
    open(os.path.join(d, "check_bare.py"), "w").write("X = 1\n")
    open(os.path.join(d, "named_other.py"), "w").write(
        'GATE = gate.meta("丙", "声明了却不叫 check_（孤儿）", knobs=())\n')
    open(os.path.join(d, "platform.py"), "w").write("Y = 2\n")   # 无声明 = 平台模块
    gs, missing = gates(d)
    ok = [g for g in gs if g["file"].endswith("check_ok.py")][0]
    plain = [g for g in gs if g["file"].endswith("check_plain.py")][0]
    real, real_missing = gates()

    def real_files():
        return {"zreflect/" + n for n in os.listdir(_zdir())
                if n.startswith("check_") and n.endswith(".py")}
    return [
        # ① 正常不报
        ("ast 提取声明行：名字 / 一句话 / 旋钮 / 旗标",
         lambda: ok["name"] == "甲闸门" and ok["desc"] == "挡甲"
         and ok["knobs"] == ("REFLECT_FACTS",)
         and ok["name_dependent"] is True),
        ("无声明且非 check_ ⇒ 平台模块，既不入名录也不入 missing",
         lambda: all(not m.endswith("platform.py") for m in missing)
         and all(not g["file"].endswith("platform.py") for g in gs)),
        ("真仓名录与磁盘一致：每个 check_*.py 都在名录里",
         lambda: not real_missing and real_files() <= {g["file"] for g in real}),
        ("真仓无孤儿（没有声明了却不叫 check_ 的文件）",
         lambda: misnamed() == []),
        ("红名单非空且每道都标了旗标（真仓一致性）",
         lambda: (lambda rn: len(rn) >= 1 and all(
             any(g["file"].endswith(b) and g["name_dependent"] for g in real)
             for b in rn))(red_need(real))),
        ("插件：einfacht-env.sh 发现式收编 + doctor 点名",
         lambda: "reflect-hooks/einfacht-env.sh" in plugins()
         and "zreflect/doctor.py" in plugins()),
        ("render_gates 是纯函数且含每道闸门（含首尾标记）",
         lambda: render_gates(gs) == render_gates(gs)
         and "甲闸门" in render_gates(gs)
         and GATES_BEGIN in render_gates(gs) and GATES_END in render_gates(gs)),
        # ② 该报的必须报
        ("★ 叫 check_ 却没声明 ⇒ 必须报（忘写声明行的形状）",
         lambda: missing == ["zreflect/check_bare.py"]),
        ("★ 声明了却不叫 check_ ⇒ 必须报（孤儿：进叙述不被执行）",
         lambda: any("却不叫 check_" in x for x in problems(
             [], [], orphans=["zreflect/named_other.py"],
             mods=["zreflect/x.py"], mods_missing=[]))),
        ("★ 标了 name_dependent 却不消费改名默认名 ⇒ 必须报（旗标错了）",
         lambda: any("旗标" in x for x in problems(
             [dict(plain, name_dependent=True)], [], orphans=[],
             mods=["zreflect/x.py"], mods_missing=[]))),
        ("★ 写了自证却没有 --selftest 入口 ⇒ 必须报（写而不跑 = 装饰）",
         lambda: any("写而不跑" in x for x in problems(
             [], [], orphans=[], mods=["zreflect/x.py"],
             mods_missing=["zreflect/y.py"]))),
        # ③ 空输入必须报
        ("★ 空名录 + 空模块 ⇒ 必须报（零值守卫）",
         lambda: problems([], [], orphans=[], mods=[], mods_missing=[]) != []),
    ]


if __name__ == "__main__":
    sys.exit(selftest("registry（发现式名录的数据面）", _cases())
             if "--selftest" in sys.argv else main(sys.argv[1:]))
