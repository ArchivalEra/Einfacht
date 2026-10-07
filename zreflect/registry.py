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


def gates(zdir=None):
    """发现式闸门名录：ast 解析每个 check_*.py 的模块级声明行。

    返回 (gates, missing)。gates = [{file, name, desc, knobs,
    name_dependent}]；missing = 没有可解析 GATE 声明的 check_*.py
    （problems 报，render 拒绝渲染 —— 逼声明行落地）。
    """
    d = zdir if zdir is not None else repo("zreflect")
    out, missing = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []                     # zreflect/ 不在：调用方按零值守卫报
    for n in names:
        if not (n.startswith("check_") and n.endswith(".py")):
            continue
        rel = "zreflect/" + n
        meta = None
        try:
            tree = ast.parse(open(os.path.join(d, n), encoding="utf-8").read())
        except (OSError, SyntaxError):
            tree = None
        if tree is not None:
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
                        meta = {"file": rel,
                                "name": ast.literal_eval(node.value.args[0]),
                                "desc": ast.literal_eval(node.value.args[1]),
                                "knobs": tuple(knobs),
                                "name_dependent": bool(name_dep)}
                    except (ValueError, IndexError):
                        meta = None
                    break
        if meta:
            out.append(meta)
        else:
            missing.append(rel)
    return out, missing


def _touches_renamed(g):
    """这道闸门消费的旋钮里，有没有默认名被换名自证改名。"""
    for k in g["knobs"]:
        kind, dflt, _ = REGISTRY.get(k, ("", "", ""))
        vals = ({x.strip() for x in dflt.split(",")} if kind == "list"
                else {dflt} if dflt else set())
        if vals & set(RENAMED_DEFAULTS):
            return True
    return False


def problems(gs, missing):
    """名录的对账（纯函数）：空 = 绿。自证期间不许 print。

    · check_*.py 没有 GATE 声明行 ⇒ 报（未登记 = 叙述会漂）；
    · 标了 name_dependent 却不消费任何改名默认名 ⇒ 报（旗标错了 ——
      要么去掉旗标，要么把新默认名登记进 RENAMED_DEFAULTS）；
    · 名录整体为空 ⇒ 报（零值守卫）。
    """
    out = []
    if missing:
        out.append("以下闸门没有 GATE = gate.meta(…) 声明行 —— 名录不收"
                   "无名之辈（手写名录会漂，声明即登记）：%s"
                   % ", ".join(missing))
    for g in gs:
        if g["name_dependent"] and not _touches_renamed(g):
            out.append("`%s` 标了 name_dependent，但消费的旋钮没有一个默认名"
                       "在换名自证的改名清单里 —— 旗标错了（要么去掉旗标，"
                       "要么把新默认名加进 registry.RENAMED_DEFAULTS）"
                       % g["file"])
    if not gs and not missing:
        out.append("一个闸门都没发现 —— 零值守卫：空输入不是通过")
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
    print("用法：registry.py [--gates|--red-need|--plugins|--selftest]",
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
    open(os.path.join(d, "helper.py"), "w").write(
        'GATE = gate.meta("丙", "非 check_ 前缀不应被发现", knobs=())\n')
    gs, missing = gates(d)
    ok = [g for g in gs if g["file"].endswith("check_ok.py")][0]
    plain = [g for g in gs if g["file"].endswith("check_plain.py")][0]
    real, real_missing = gates()

    def real_files():
        return {"zreflect/" + n for n in os.listdir(repo("zreflect"))
                if n.startswith("check_") and n.endswith(".py")}
    return [
        # ① 正常不报
        ("ast 提取声明行：名字 / 一句话 / 旋钮 / 旗标",
         lambda: ok["name"] == "甲闸门" and ok["desc"] == "挡甲"
         and ok["knobs"] == ("REFLECT_FACTS",)
         and ok["name_dependent"] is True),
        ("非 check_ 前缀的文件不收（helper.py 的声明行被无视）",
         lambda: all(not g["file"].endswith("helper.py") for g in gs)),
        ("真仓名录与磁盘一致：每个 check_*.py 都有声明、无 missing",
         lambda: not real_missing
         and {g["file"] for g in real} == real_files()),
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
        ("★ 无声明的 check_*.py ⇒ 必须报（名录不收无名之辈）",
         lambda: missing == ["zreflect/check_bare.py"]),
        ("★ 标了 name_dependent 却不消费改名默认名 ⇒ 必须报（旗标错了）",
         lambda: any("旗标" in x for x in problems(
             [dict(plain, name_dependent=True)], []))),
        # ③ 空输入必须报
        ("★ 空名录 ⇒ 必须报（零值守卫）", lambda: problems([], []) != []),
    ]


if __name__ == "__main__":
    sys.exit(selftest("registry（发现式名录的数据面）", _cases())
             if "--selftest" in sys.argv else main(sys.argv[1:]))
