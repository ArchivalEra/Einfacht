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
from gate import module_meta, fatal, repo, main_selftest_or             # noqa: E402
from i18n import M                                        # noqa: E402
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
# C4 对账③：`FIXTURE_RENAMES` 是「原名 → 夹具名」的**唯一产地** ——
# gates-selftest.sh 的夹具从 `--fixture-renames` 派生它建的文件名，不再手写
# 两份会漂的清单（此前夹具的名字与这张表是两处手写，无对账器）。
FIXTURE_RENAMES = {
    "FACTS.json": "LEDGER.json",
    "STATE.md": "NOTES.md",
    "retractions.json": "RETRACT.json",
    "questions": "cases",
    "README.md": "R1.md",
    "README.zh.md": "R2.md",
    "README.de.md": "R3.md",
}
RENAMED_DEFAULTS = tuple(FIXTURE_RENAMES)

# 已知相位（C1）：闸门声明自己的运行频率。执行面（gate.run_phase）按它过滤。
#   commit        每次提交跑（pre-commit / pre-push / CI）
#   start-of-work 开工前手动跑（doctor —— 查会死的东西，挂提交频率错）
# ⚠️ issue #21：相位清单**焊死在这里**会逼下游 fork —— 使用方有自己的相位
# （S26 仓的 lab：*.lab.py 只在实验目录在场时跑）。旋钮 `REFLECT_PHASES`
# 追加自定义相位（逗号分隔，追加在两个内置相位之后）；核心两个不可删、
# 不可重名 —— 相位是执行面与声明的公共词汇，乱改会让既有 runs_at 声明
# 静默变孤儿。problems() 仍拦未知相位：声明了 runs_at 却不在清单 ⇒ 红。
BUILTIN_PHASES = ("commit", "start-of-work")


def phases():
    """已知相位 = 内置两个 + `REFLECT_PHASES` 追加（下游自定义，如 lab）。"""
    raw = os.environ.get("REFLECT_PHASES", "").strip()
    out = list(BUILTIN_PHASES)
    for p in (x.strip() for x in raw.split(",")):
        if p and p not in out:
            out.append(p)
    return tuple(out)


def phases_problems():
    """相位清单自洽（旋钮坏值的判据；纯函数）。"""
    raw = os.environ.get("REFLECT_PHASES", "").strip()
    out = []
    if raw:
        dup = [p for p in (x.strip() for x in raw.split(","))
               if p in BUILTIN_PHASES]
        if dup:
            out.append(M("registry.builtin_phase_repeated",
                         phases=", ".join(sorted(set(dup)))))
    return out

def modules(zdir=None):
    """平台模块名录（C5）：ast 解析 `MODULE = module_meta(…)` 声明行。

    返回 (declared, undeclared)：`declared` = [{file, name, desc, selftest}]；
    `undeclared` = **非闸门、非 __init__ 却没有 MODULE 声明**的 .py ——
    平台模块必须声明自己（哪怕是 selftest=False，也要正面说「我不用自证」），
    否则「该有自证却没写」无人问（文本猜 `_cases` 猜不出来「本该有」）。
    """
    d = zdir if zdir is not None else _zdir()
    declared, undeclared = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        rel = "zreflect/" + n
        if _declaration(os.path.join(d, n), rel, attr="MODULE", func="module_meta"):
            declared.append(_declaration(os.path.join(d, n), rel,
                                         attr="MODULE", func="module_meta"))
        elif _declaration(os.path.join(d, n), rel):
            continue                    # 是闸门（有 GATE 声明），不算平台模块
        else:
            undeclared.append(rel)
    return declared, undeclared


def selftest_modules(zdir=None):
    """有自证义务的模块名录（C5，声明驱动）：`MODULE = module_meta(…,
    selftest=True)` 声明的模块 —— 闸门（GATE 声明）不算在内（它们由
    run_gates 覆盖）。返回 (mods, missing)：`mods` = 该跑自证的；
    `missing` = 声明了 selftest=True 却没有 --selftest 入口的（写而不跑 = 装饰）。
    """
    declared, _und = modules(zdir)
    d = zdir if zdir is not None else _zdir()
    mods, missing = [], []
    for m in declared:
        if not m.get("selftest"):
            continue
        text = open(os.path.join(d, os.path.basename(m["file"])),
                    encoding="utf-8").read()
        can = ("--selftest" in text or "main_selftest_or" in text
               or "_selftest()" in text)
        if can:
            mods.append(m["file"])
        else:
            missing.append(m["file"])
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
    """发现式闸门名录：**声明即闸门** —— ast 解析 zreflect/*.py 的模块级
    `GATE = gate.meta(…)` 行，与文件名无关（C1）。

    返回 (gates, missing)。gates = [{file, name, desc, knobs,
    name_dependent, runs_at}]；missing = **叫 check_ 却没有声明行**的文件
    （problems 报、render 拒绝 —— 那是「起名叫闸门却忘了声明」的形状）。

    谓词 = **声明**，不是文件名（2026-10-10，C1）：执行面（hooks / CI）
    改为读 registry.runnable() ⇒ 谓词只有一处（这里）。于是：
      · 名字不再承重 —— doctor 靠 `runs_at="start-of-work"` 正面声明频率，
        不靠「它没叫 check_」这种否定式命名意外；
      · 「孤儿」（声明了却不叫 check_）概念消失 —— 声明了就是闸门，会被
        runnable() 收进执行清单，不存在「进叙述不被执行」的中间态。
    """
    d = zdir if zdir is not None else _zdir()
    out, missing = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []                     # zreflect/ 不在：调用方按零值守卫报
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        rel = "zreflect/" + n
        meta = _declaration(os.path.join(d, n), rel)
        if meta:
            out.append(meta)
        elif n.startswith("check_"):
            # 起名叫 check_ 却没声明 ⇒ 忘写声明（名录不收、render 拒绝）。
            # 非 check_ 且无声明 = 平台模块（gate/knobs/registry/…），不是闸门。
            missing.append(rel)
    return out, missing


def _decl_call(node, attr, func):
    """`node` 是不是 `<attr> = <func>(…)` 形状的声明行？是 ⇒ 那个调用节点。

    两种等价写法都认：meta(…)（裸导入名）与 gate.meta(…)（属性）。
    不是声明行 / 调用的不是 `func` ⇒ None（调用方继续扫下一行）。
    """
    if not (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == attr
            and isinstance(node.value, ast.Call)
            and len(node.value.args) >= 2):
        return None
    fn = node.value.func
    if getattr(fn, "id", "") == func or getattr(fn, "attr", "") == func:
        return node.value
    return None


def _module_meta(call, rel):
    """`MODULE = module_meta(…)` → {file, name, desc, selftest}。"""
    st = True
    for kw in call.keywords:
        if kw.arg == "selftest":
            st = ast.literal_eval(kw.value)
    return {"file": rel,
            "name": ast.literal_eval(call.args[0]),
            "desc": ast.literal_eval(call.args[1]),
            "selftest": bool(st)}


def _gate_meta(call, rel):
    """`GATE = gate.meta(…)` → {file, name, desc, knobs, name_dependent, runs_at}。"""
    knobs, name_dep, runs_at = (), False, "commit"
    for kw in call.keywords:
        if kw.arg == "knobs":
            knobs = ast.literal_eval(kw.value)
        elif kw.arg == "name_dependent":
            name_dep = ast.literal_eval(kw.value)
        elif kw.arg == "runs_at":
            runs_at = ast.literal_eval(kw.value)
    return {"file": rel,
            "name": ast.literal_eval(call.args[0]),
            "desc": ast.literal_eval(call.args[1]),
            "knobs": tuple(knobs),
            "name_dependent": bool(name_dep),
            "runs_at": str(runs_at)}


def _declaration(path, rel, attr="GATE", func="meta"):
    """从文件里 ast 提取声明行（默认 `GATE = meta(…)`；C5 用
    `MODULE = module_meta(…)`）。没有 ⇒ None。

    `attr` / `func` 可换（同一套解析服务闸门与平台模块两类声明）。
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        call = _decl_call(node, attr, func)
        if call is None:
            continue
        try:
            if func == "module_meta":
                return _module_meta(call, rel)
            return _gate_meta(call, rel)
        except (ValueError, IndexError):
            return None
    return None


def runnable(phase="commit", zdir=None):
    """按相位给出**该跑**的闸门清单（C1：执行面唯一产地）。

    `phase="commit"` ⇒ 每次提交跑的（hooks / CI）；`phase="start-of-work"`
    ⇒ 开工前手动跑的（doctor）。返回 [{file, name, runs_at, …}]。
    声明面（GATE = meta(…, runs_at=…)）是唯一产地 —— 执行面不再 glob 文件名。
    """
    gs, _missing = gates(zdir)
    return [g for g in gs if g.get("runs_at", "commit") == phase]


def _touches_renamed(g):
    """这道闸门消费的旋钮里，有没有默认名被换名自证改名。"""
    for k in g["knobs"]:
        kind, dflt, _ = REGISTRY.get(k, ("", "", ""))
        vals = ({x.strip() for x in dflt.split(",")} if kind == "list"
                else {dflt} if dflt else set())
        if vals & set(RENAMED_DEFAULTS):
            return True
    return False


def _missing_declaration_problems(missing):
    """叫 check_ 却没有 GATE 声明行 —— 忘写声明 = 叙述会漂。"""
    if not missing:
        return []
    return [M("registry.missing_declaration", files=", ".join(missing))]


def _phase_problems(gs):
    """runs_at 必须是已知相位 —— 频率是声明字段，写错值会让执行面漏掉它。"""
    out = []
    for g in gs:
        if g.get("runs_at", "commit") not in phases():
            out.append(M("registry.unknown_phase",
                         file=g["file"], runs_at=g.get("runs_at"),
                         phases=" | ".join(phases())))
    return out


def _name_dependent_problems(gs):
    """标了 name_dependent 却不消费任何改名默认名 —— 旗标错了。"""
    out = []
    for g in gs:
        if g["name_dependent"] and not _touches_renamed(g):
            out.append(M("registry.name_dependent_wrong", file=g["file"]))
    return out


def _empty_gate_problems(gs, missing):
    """名录整体为空 —— 零值守卫：空输入不是通过。"""
    if not gs and not missing:
        return [M("registry.empty_roster")]
    return []


def _selftest_roster_problems(mods, mods_missing):
    """平台模块自证名册：声明了就必须能跑，且名录不许为空。"""
    if mods is None or mods_missing is None:
        mods, mods_missing = selftest_modules()
    out = []
    if mods_missing:
        out.append(M("registry.selftest_no_entry",
                     files=", ".join(mods_missing)))
    if not mods:
        out.append(M("registry.no_module_selftest"))
    return out


def _undeclared_module_problems(undeclared):
    """C5：平台模块必须声明自己（MODULE = module_meta(…)），否则
    「该有自证却没写」无人问（文本猜 _cases 猜不出「本该有」）。"""
    if undeclared is None:
        _decl, undeclared = modules()
    if not undeclared:
        return []
    return [M("registry.undeclared_module", files=", ".join(undeclared))]


def _knob_problems(knob_problems, gs):
    """名册自洽性（C3）：幻影旋钮 / README 幻影 —— 与任何载体是否存在无关。

    此前焊在 check_envfile.run() 的「载体存在」前置之后，本仓没有
    Einfacht.env ⇒ 从未执行（实测踩到）。名册的家在这里收口。
    """
    if knob_problems is None:
        import knobs                                     # noqa: PLC0415
        knob_problems = (knobs.scan_surface_problems()
                         + knobs.readme_problems()
                         # C4 对账：声明↔实读、REGISTRY↔README 表、zh↔en 包
                         + knobs.declared_vs_read_problems(gs)
                         + knobs.registry_vs_readme_problems()
                         + knobs.pack_sync_problems()
                         # C4 对账④：**源码用到的 code 必须在每个已装包里**
                         # （zh↔en 差集看不见「两边一起缺」，那是静默退化）
                         + knobs.pack_coverage_problems())
    return list(knob_problems)


def problems(gs, missing, mods=None, mods_missing=None,
             knob_problems=None, undeclared=None):
    """名录的对账（纯函数）：空 = 绿。自证期间不许 print。

    `mods` / `mods_missing` / `knob_problems` 可注入（自证用夹具）；
    None ⇒ 现读真仓。

    · 叫 check_ 却没有 GATE 声明行 ⇒ 报（忘写声明 = 叙述会漂）；
    · runs_at 不是已知相位 ⇒ 报（频率是声明字段，写错值会让执行面漏掉它）；
    · 标了 name_dependent 却不消费任何改名默认名 ⇒ 报（旗标错了）；
    · 写了自证却没有 --selftest 入口 ⇒ 报（写而不跑 = 装饰）；
    · 名册自洽性（幻影旋钮 / README 幻影）⇒ 报（C3，与载体无关）；
    · 名录整体为空 ⇒ 报（零值守卫）。
    """
    out = []
    out += phases_problems()
    out += _missing_declaration_problems(missing)
    out += _phase_problems(gs)
    out += _name_dependent_problems(gs)
    out += _empty_gate_problems(gs, missing)
    out += _selftest_roster_problems(mods, mods_missing)
    out += _undeclared_module_problems(undeclared)
    out += _knob_problems(knob_problems, gs)
    return out


def _pinned_under(lang):
    """自证帮手：在指定 REFLECT_LANG 下渲染 AUTO 块（用于证明它不随语言变）。"""
    old = os.environ.get("REFLECT_LANG", "")
    os.environ["REFLECT_LANG"] = lang
    try:
        gs, _ = gates()
        return render_gates(gs)
    finally:
        os.environ["REFLECT_LANG"] = old


def _with_phases(val):
    """自证帮手：临时设 REFLECT_PHASES，返回 (phases(), problems())，恢复现场。"""
    old = os.environ.get("REFLECT_PHASES", "")
    os.environ["REFLECT_PHASES"] = val
    try:
        return phases(), phases_problems()
    finally:
        os.environ["REFLECT_PHASES"] = old


def red_need(gs=None):
    """换名自证里**必须红**的闸门文件名（默认名承担载荷的那批）。"""
    if gs is None:
        gs, _ = gates()
    return sorted(os.path.basename(g["file"]) for g in gs
                  if g["name_dependent"] and _touches_renamed(g))


def plugins(hooks_dir=None):
    """自证点名的**插件**清单：reflect-hooks/*.sh 带自证标记的（发现式收编）。

    doctor 不再是「点名特殊件」—— C1 起它是正常声明的闸门
    （`runs_at="start-of-work"`），由 gates()/runnable() 收编，不再需要
    旁路点名（此前它靠 SPECIAL_PLUGINS 手写一行，是「名字承重」时代的产物）。
    """
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
    return out


def render_gates(gs):
    """闸门名录 → AUTO:GATES 机器块（含首尾标记）。**纯函数**：
    同一名录渲染两次逐字节相同。

    ⚠️ **PINNED**（issue #26，D' 的洞见）：本块的文本**永远用固定语言**，
    不跟随 `REFLECT_LANG`。理由：它写进 `STATE.md` 并被 `facts.py --check`
    逐字节对账 —— 若随语言变，`REFLECT_LANG=de --render-doc` 之后
    `REFLECT_LANG=zh --check` 必然红，**同一提交在不同语言环境下结果不同**
    （`collect.py` 原则 2 的同族病：不引入会自己变的输入）。
    实测过：不 PINNED 就会不收敛。
    """
    lines = [GATES_BEGIN,
             "> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录"
             "（zreflect/registry.py 的声明行）渲染，**不要手改**。",
             "> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段"
             "（`runs_at`），不是文件名。",
             "",
             "| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 |", "|---|---|---|---|"]
    for g in sorted(gs, key=lambda x: (x.get("runs_at", "commit"), x["file"])):
        lines.append("| `%s`（%s） | %s | %s | %s |"
                     % (os.path.basename(g["file"]), g["name"],
                        g.get("runs_at", "commit"), g["desc"],
                        ", ".join("`%s`" % k for k in g["knobs"]) or "—"))
    lines += ["", "%d 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = "
              "落一个声明行，这里自动长出来）。" % len(gs), GATES_END]
    return "\n".join(lines)


def _arg_after(argv, flag):
    """`--flag [value]` 的可选值（缺省 / 以 - 开头 ⇒ 默认 commit）。"""
    i = argv.index(flag)
    return (argv[i + 1] if len(argv) > i + 1
            and not argv[i + 1].startswith("-") else "commit")


def _main_run(argv):
    """执行面：跑一个相位的全部闸门并聚合 ran / off / failed（C1+C2）。

    hooks / CI 只调这一行 —— glob 退役，谓词只有 gates() 一处。
    """
    phase = _arg_after(argv, "--run")
    from gate import run_phase                          # noqa: PLC0415
    gs = runnable(phase)
    if not gs:
        return fatal(M("registry.empty_phase", phase=phase))
    res = run_phase(phase, gs)
    print(M("registry.phase_summary", phase=phase, ran=res["ran"],
            off=res["off"], failed=res["failed"]))
    for f in res["off_list"]:
        print(M("registry.phase_off", file=f))
    for f in res["fail_list"]:
        print("  FAILED %s" % f, file=sys.stderr)
    return 1 if res["failed"] else 0


def cli_selftest_missing_lines(missing):
    """`--selftest-modules` 的逐行点名（纯函数：自证用，零 print）。"""
    return [M("registry.selftest_no_entry_cli", file=m) for m in missing]


def _main_selftest_modules():
    mods, missing = selftest_modules()
    for line in cli_selftest_missing_lines(missing):
        # CLI 逐行点名与 roster 的汇总句是**两处不同输出**（此前各一句措辞），
        # 迁移时保持两条 code，不把 CLI 行改成汇总句的样子。
        print(line, file=sys.stderr)
    if missing:
        return 1
    print("\n".join(mods))
    return 0


def _main_gates():
    gs, missing = gates()
    probs = problems(gs, missing)
    for x in probs:
        print("  · %s" % x, file=sys.stderr)
    if probs:
        return fatal(M("registry.roster_problems", count=len(probs)))
    for g in gs:
        print("%s\t%s\t%s" % (g["file"], g["name"], g["desc"]))
    return 0


def _main_lists(argv):
    """`--red-need` / `--runnable` / `--all-runnable` 三个清单打印。

    返回 rc；没有这些旗标 ⇒ None（调用方继续往下探）。
    """
    if "--red-need" in argv:
        print(" ".join(red_need()))
        return 0
    if "--runnable" in argv:
        # 执行面唯一产地（C1）：--runnable [phase]，默认 commit。
        for g in runnable(_arg_after(argv, "--runnable")):
            print(g["file"])
        return 0
    if "--all-runnable" in argv:
        # 全部相位的闸门（自证用：每道闸门都必须证明自己能红，与相位无关）。
        gs, _m = gates()
        for g in gs:
            print(g["file"])
        return 0
    return None


def _main_listings(argv):
    """`--plugins` / `--fixture-renames` 两个逐行清单。

    返回 rc；没有这些旗标 ⇒ None（调用方继续往下探）。
    """
    if "--plugins" in argv:
        print("\n".join(plugins()))
        return 0
    if "--fixture-renames" in argv:
        # C4 对账③：夹具改名集的唯一产地（原名=夹具名，每行一条）。
        for orig, fix in sorted(FIXTURE_RENAMES.items()):
            print("%s=%s" % (orig, fix))
        return 0
    return None


def _usage():
    """用法行。**函数而不是模块常量**：入口在 `main_selftest_or` 里才
    `activate()` 语言包，模块级 `M(…)` 会在 import 时就被冻在 null 包上。"""
    return M("registry.usage")


def main(argv):
    rc = _main_lists(argv)
    if rc is not None:
        return rc
    if "--run" in argv:
        return _main_run(argv)
    rc = _main_listings(argv)
    if rc is not None:
        return rc
    if "--selftest-modules" in argv:
        return _main_selftest_modules()
    if "--gates" in argv:
        return _main_gates()
    print(_usage(), file=sys.stderr)
    return 2


def _cases():
    import atexit                                        # noqa: PLC0415
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    # 夹具的声明数据用**ASCII 名**：它们是被 ast 提取的输入（进 AUTO:GATES
    # 机器块），不是本体输出 —— 中文夹具会被零语言闸门收编。
    open(os.path.join(d, "check_ok.py"), "w").write(
        'GATE = gate.meta("gate_a", "blocks_a", knobs=("REFLECT_FACTS",),'
        ' name_dependent=True)\n')
    open(os.path.join(d, "check_plain.py"), "w").write(
        'GATE = gate.meta("gate_b", "blocks_b", knobs=("REFLECT_WORLD",))\n')
    open(os.path.join(d, "check_bare.py"), "w").write("X = 1\n")
    open(os.path.join(d, "named_other.py"), "w").write(
        'GATE = gate.meta("gate_c", "declared means registered", knobs=())\n')
    open(os.path.join(d, "doc_gate.py"), "w").write(
        'GATE = gate.meta("gate_d", "start-of-work phase", knobs=(),'
        ' runs_at="start-of-work")\n')
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
        ("registry.ast_declaration_fields",
         lambda: ok["name"] == "gate_a" and ok["desc"] == "blocks_a"
         and ok["knobs"] == ("REFLECT_FACTS",)
         and ok["name_dependent"] is True and ok["runs_at"] == "commit"),
        ("registry.undeclared_noncheck_is_module",
         lambda: all(not m.endswith("platform.py") for m in missing)
         and all(not g["file"].endswith("platform.py") for g in gs)),
        ("registry.declaration_is_registration",
         lambda: any(g["file"].endswith("named_other.py") for g in gs)
         and not any(m.endswith("named_other.py") for m in missing)),
        ("registry.real_roster_matches_disk",
         lambda: not real_missing and real_files() <= {g["file"] for g in real}),
        ("registry.runnable_filters_by_phase",
         lambda: (lambda cm, sw: all(g["runs_at"] == "commit" for g in cm)
                  and [g["file"] for g in sw]
                  == ["zreflect/doc_gate.py"])(runnable("commit", d),
                                               runnable("start-of-work", d))),
        ("registry.doctor_is_start_of_work",
         lambda: any(g["file"].endswith("doctor.py") for g in real)
         and not any(g["file"].endswith("doctor.py")
                     for g in runnable("commit"))),
        ("registry.red_need_flagged",
         lambda: (lambda rn: len(rn) >= 1 and all(
             any(g["file"].endswith(b) and g["name_dependent"] for g in real)
             for b in rn))(red_need(real))),
        ("registry.real_modules_declared",
         lambda: modules()[1] == [] and len(modules()[0]) >= 8),
        ("registry.fixture_renames_single_source",
         lambda: set(FIXTURE_RENAMES) == set(RENAMED_DEFAULTS)
         and len(FIXTURE_RENAMES) >= 7),
        ("registry.plugin_discovery",
         lambda: "reflect-hooks/einfacht-env.sh" in plugins()
         and "zreflect/doctor.py" not in plugins()),
        ("★ registry.auto_block_pinned_across_langs",
         lambda: _pinned_under("en") == _pinned_under("zh")
         and _pinned_under("de") == _pinned_under("")),
        ("registry.render_gates_pure",
         lambda: render_gates(gs) == render_gates(gs)
         and "gate_a" in render_gates(gs)
         and GATES_BEGIN in render_gates(gs) and GATES_END in render_gates(gs)),
        # ② 该报的必须报
        ("★ registry.missing_declaration",
         lambda: missing == ["zreflect/check_bare.py"]),
        ("★ registry.unknown_phase",
         lambda: [p.code for p in problems(
             [dict(plain, runs_at="whenever")], [],
             mods=["zreflect/x.py"], mods_missing=[], knob_problems=[],
             undeclared=[])] == ["registry.unknown_phase"]),
        ("★ registry.name_dependent_wrong",
         lambda: [p.code for p in problems(
             [dict(plain, name_dependent=True)], [],
             mods=["zreflect/x.py"], mods_missing=[], knob_problems=[],
             undeclared=[])] == ["registry.name_dependent_wrong"]),
        # 这两条的空名录与「空清单不是通过」同时在场（gs=[] 必然触发零值守卫），
        # 所以用 `any(code == …)` 而不是整表相等 —— 断言仍精确指向那一条。
        ("★ registry.selftest_no_entry",
         lambda: any(p.code == "registry.selftest_no_entry" for p in problems(
             [], [], mods=["zreflect/x.py"],
             mods_missing=["zreflect/y.py"],
             knob_problems=[]))),
        # CLI 逐行点名也必须能产出（否则它是「写而不跑」的装饰 —— 本仓纪律）。
        ("★ registry.selftest_no_entry_cli",
         lambda: [m.code for m in cli_selftest_missing_lines(
             ["zreflect/y.py"])] == ["registry.selftest_no_entry_cli"]
         and cli_selftest_missing_lines([]) == []),
        ("★ registry.undeclared_module",
         lambda: any(p.code == "registry.undeclared_module" for p in problems(
             [], [], mods=["zreflect/x.py"], mods_missing=[],
             knob_problems=[],
             undeclared=["zreflect/orphan_mod.py"]))),
        # ③ 空输入必须报
        ("★ registry.empty_roster",
         lambda: problems([], [], mods=[], mods_missing=[],
                          knob_problems=[], undeclared=[]) != []),
        # issue #21：相位旋钮 —— 下游自定义相位（如 S26 的 lab）不再 fork PHASES
        ("registry.phases_extra_appended",
         lambda: _with_phases("lab")[0] == ("commit", "start-of-work", "lab")),
        ("★ registry.builtin_phase_repeated",
         lambda: [p.code for p in _with_phases("commit,lab")[1]
                  ] == ["registry.builtin_phase_repeated"]),
        ("registry.phases_default_builtin_only",
         lambda: _with_phases("")[0] == ("commit", "start-of-work")),
        # 人性化提示（env_hint）：四条判据
        ("registry.env_hint_silent_without_carrier",
         lambda: __import__("gate").env_hint(consumed=("REFLECT_FACTS",)) is None
         or __import__("gate").env_carrier() is not None),
        ("registry.env_hint_off_silent",
         lambda: (lambda: (os.environ.update(REFLECT_ENV_HINT="off"),
                           __import__("gate")._maybe_hint(),
                           os.environ.pop("REFLECT_ENV_HINT", None),
                           True))()),
    ]


MODULE = module_meta("发现式名录", "闸门/模块/插件的声明派生：执行面 + 叙述 + 红名单", selftest=True)


if __name__ == "__main__":
    # 收尾统一走 `main_selftest_or`：它先做语言包激活（`activate_or_fatal`），
    # 再分流 `--selftest` 与 `main()`。此前这里自己抄了一份 activate+FATAL，
    # 而 gate 自己的 `__main__` 又是第三种写法（连 FATAL 都没有）—— 同一件事
    # 三份拷贝，口径必然漂。
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.registry"),
                              _cases, main))
