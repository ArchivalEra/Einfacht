#!/usr/bin/env python3
"""模块级快照闸门（**可插拔模块**，deepening 第 5 轮）。

守的是一条**踩了三次的坑**：

    from gate import GATE_REPO        # ← 值拷贝，此刻冻结
    ...
    gate.GATE_REPO = other_repo       # ← 后来改了，上面那个副本不知道
    subprocess.run(..., cwd=GATE_REPO)  # ← 还在用旧仓

`from X import CONST` 在 Python 里是**值拷贝**，不是引用。若 `CONST` 之后会被
重新赋值（`gate.GATE_REPO` 就是，任何夹具都会改它），所有拷贝都变成**陈旧快照** ——
而且失败得没有声音：不报错、不抛异常，只是悄悄地读错仓库。

本仓实际踩到三次：

  1. `i18n.pack_dir()` 用 GATE_REPO 相对 ⇒ 跨仓夹具里装载器找不到包（0/15 全红）
  2. `knobs.installed_langs()` 同类
  3. `check_envfile` 的自证想改 `os.environ["GATE_REPO"]` 却发现无效（`repo()`
     读的是模块级变量，不是环境变量）

第三次最典型：**作者以为改环境变量就够了**，因为看不见「这个值是 import 时
定下的」。本闸门把这个隐形耦合变成可判定的。

## 判据（AST，零执行）

对 `zreflect/*.py` 里每一条 `from <本地模块> import <大写名>`：

  · 若 `<大写名>` 在**源模块里是模块级可赋值名字**（且不是函数 / 常量数据），
    且导入方**在运行路径上用了它** ⇒ 报。

「模块级可赋值」的判据：源模块里有模块顶层的 `NAME = ...` 赋值，且该名字
**不是** frozen 数据（`REGISTRY` 这类只在 import 时构造一次、此后没人改的）。

诚实边界：静态判据只会看「谁 import 了可变全局」，**判不出**「这里改它是否
真的发生过」。所以它报的是**风险形状**，不是已发生的事故 —— 这是写明的缺口。
修法永远是同一个：改成 `import gate` + `gate.GATE_REPO`（每次读属性，不拷贝）。
"""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import fatal, finish, main_selftest_or, meta, off, selftest  # noqa: E402
from i18n import M                                        # noqa: E402

KNOB = "REFLECT_SNAPSHOT_ROOT"
# ⚠️ **不再用手写名单**。此前这里是一串硬编码模块名（`("gate", "knobs", …)`），
# 违反 AGENTS「手写名录一定会漂」：全仓 28 个 `zreflect/*.py` 里只有 12 个在册，
# 另外 16 个（全部 `check_*.py`）作为**被导入源**时判据完全看不到。
# 现在是**发现式**：扫描面里每个 `.py` 都是候选源模块 —— 名单 = 扫描面本身。
# （第三方库不会被误收：只认 `from X import …` 且 X 在扫描面里。）


def _module_level_assigns(tree):
    """模块顶层被赋值的名字集合（`NAME = ...` / `NAME: T = ...`）。"""
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


def _aliases_of(trees, src_mod):
    """扫描面里 `import <src_mod> as <alias>` 的别名集合（`_reassigned_elsewhere` 用）。"""
    out = set()
    for _mod, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == src_mod and a.asname:
                        out.add(a.asname)
    return out


def _reassigned_elsewhere(trees, src_mod, name):
    """有没有**任何模块**在运行期给 `src_mod.name` 赋值（`src_mod.name = …`）？

    ⚠️ 判据形状的关键：不是「源模块自己赋值几次」（`gate.GATE_REPO` 只赋一次），
    而是「**别人会不会改它**」—— `check_envfile` / `i18n` 的自证都在
    `gate.GATE_REPO = …` 改它。那才是拷贝变陈旧的真正条件。

    只赋值一次、无人改写的常量（`REGISTRY`）不报 ——
    它们的语义是「一个数据表」，拷贝与引用没区别。
    """
    aliases = _aliases_of(trees, src_mod)
    for _mod, tree in trees.items():
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            for t in targets:
                # 形状①：`<src_mod>.<name> = …`（**别的模块**从外面改）
                # 形状①b：`<alias>.<name> = …`，其中 `import <src_mod> as <alias>`
                #   —— 别名是同一件事的另一种写法，此前漏报（实测 `[]`）。
                if isinstance(t, ast.Attribute) and t.attr == name \
                        and isinstance(t.value, ast.Name) \
                        and (t.value.id == src_mod or t.value.id in aliases):
                    return True
            # 形状②：源模块自己用 `global NAME` + 再赋值（同一模块内改写）
            if _mod == src_mod and isinstance(node, (ast.Assign, ast.AugAssign)):
                for t in targets:
                    if isinstance(t, ast.Name) and t.id == name \
                            and _uses_global(tree, name):
                        return True
    return False


def _uses_global(tree, name):
    """这个模块里有没有 `global <name>` 声明？（配合赋值即「会变」的证据）"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Global) and name in node.names:
            return True
    return False


def _functions_reading(src_tree, src_mod, name):
    """`src_mod` 里**读** `name` 的顶层函数名（`repo()` 这类薄封装）。

    派生快照常经由这种封装出现：`OUT = repo(LEDGER_NAME)`，
    表达式文本里没有 `gate.GATE_REPO`，但 `repo()` 的体里有 —— 只看文本会漏。
    """
    out = set()
    for node in src_tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and n.id == name \
                    and isinstance(n.ctx, ast.Load):
                out.add(node.name)
                break
    return out


def _module_level_derivations(tree, src_mod, name, readers=()):
    """模块顶层有没有 `OTHER = <表达式里含 src_mod.name>`？那是**同一类快照**。

    两种写法都会在 import 那一刻冻结：
        from gate import GATE_REPO      # 值拷贝
        OUT = repo(LEDGER_NAME)        # repo() 内部读 gate.GATE_REPO ⇒ 冻结成字符串

    只抓第一种会漏掉第二种 —— 而那正是本仓实际存在的一处（`facts.py:35`，
    实测：改 `gate.GATE_REPO` 后 `facts.OUT` 仍是旧路径）。
    """
    hits = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        text = ast.unparse(node.value)
        hit = ("%s.%s" % (src_mod, name)) in text
        # 或者：表达式调用了源模块里「会读 name」的函数（如 repo()）
        if not hit and readers:
            for n in ast.walk(node.value):
                if isinstance(n, ast.Call):
                    fn = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                    if fn in readers:
                        hit = True
                        break
        if hit:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    hits.append(t.id)
    return hits


def _used_in_module(tree, name):
    """导入方**真的用到**这个名字了吗（排除「import 了没用」的死导入）。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name \
                and isinstance(node.ctx, ast.Load):
            return True
    return False


def problems(paths=None, sources=None):
    """纯函数：返回问题清单（空 = 没有快照风险）。

    `sources` 可注入 `{模块名: 源码}`（自证用，零文件 I/O）。
    """
    if sources is None:
        if paths is None:
            return [M("snapshot.empty_scan")]
        sources = {}
        for name, src in paths:
            sources[name[:-3] if name.endswith(".py") else name] = src
    if not sources:
        return [M("snapshot.empty_scan")]

    # 先建「各模块的可变模块级名字」索引
    trees = {}
    for mod, src in sources.items():
        try:
            trees[mod] = ast.parse(src)
        except SyntaxError:
            continue
    # 一个（模块, 名字）对是否构成「可变全局」：它在本模块顶层被赋值，
    # 且**有别的模块在运行期改它**。
    assigned = {mod: _module_level_assigns(tree) for mod, tree in trees.items()}

    out = []
    # ② **派生快照**：模块顶层把「含可变全局的表达式」存成常量（同 import 一样会冻住）
    for mod, tree in sorted(trees.items()):
        for src_mod, names in sorted(assigned.items()):
            for name in sorted(names):
                if not _reassigned_elsewhere(trees, src_mod, name):
                    continue
                readers = _functions_reading(trees[src_mod], src_mod, name)
                for derived in _module_level_derivations(tree, src_mod, name,
                                                         readers):
                    if _used_in_module(tree, derived):
                        out.append(M("snapshot.derived_copy",
                                     file=mod + ".py", derived=derived,
                                     source=src_mod, imported=name))
    for mod, tree in sorted(trees.items()):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module not in trees:
                continue                # 不在扫描面里 ⇒ 不是本地兄弟模块（如第三方）
            src_mod = node.module
            if src_mod not in assigned:
                continue                    # 源模块不在扫描面里 ⇒ 不猜
            for alias in node.names:
                name = alias.name
                if name != name.upper():
                    continue                # 函数 / 类 / 小写名不是「值快照」
                if name not in assigned[src_mod]:
                    continue                # 源模块没有这个模块级名字
                if not _reassigned_elsewhere(trees, src_mod, name):
                    continue                # 没人改它 ⇒ 拷贝安全
                if not _used_in_module(tree, alias.asname or name):
                    continue                # 死导入，不报
                out.append(M("snapshot.mutable_copy",
                             file=mod + ".py", imported=name,
                             source=src_mod))
    return out


def collect(root):
    """读 root 下所有 .py 的源码。"""
    out = []
    d = root
    if not os.path.isdir(d):
        return out
    for n in sorted(os.listdir(d)):
        if not n.endswith(".py"):
            continue
        p = os.path.join(d, n)
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                out.append((n, fh.read()))
        except OSError:
            continue
    return out


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = os.environ.get(KNOB, "").strip()
    if not root:
        return off(M("snapshot.off", knob=KNOB))
    paths = collect(root)
    if not paths:
        return fatal(M("snapshot.scan_empty_dir", root=root))
    return finish(M("snapshot.title"), problems(paths),
                  M("snapshot.ok", files=len(paths)))


ALIAS_GATE = 'GATE_REPO = "/repo"\n'
ALIAS_USER = 'import gate as g\ng.GATE_REPO = "/other"\n'
ALIAS_VICTIM = 'from gate import GATE_REPO\ndef f():\n    return GATE_REPO\n'
# 一个此前不在 LOCAL_MODULES 里的模块（`check_zzz`）作为**源模块**
CHECK_AS_SOURCE = 'SHARED = "/x"\n'
CHECK_AS_VICTIM = ('import check_zzz\ncheck_zzz.SHARED = "/y"\n'
                   'from check_zzz import SHARED\ndef f():\n    return SHARED\n')

GATE_WITH_REPO = """
GATE_REPO = "/repo"
def repo(*parts):
    return os.path.join(GATE_REPO, *parts)
def set_repo(p):
    global GATE_REPO
    GATE_REPO = p
"""


def _cases():
    # 正常：常量只赋值一次 ⇒ 拷贝安全
    GOOD = '''
GATE_REPO = "/repo"
CONST = [1]
'''
    GOOD_USER = '''
from gate import CONST
def f():
    return CONST
'''
    # 该报：模块级可变全局被拷贝并真用了
    BAD_GATE = '''
GATE_REPO = "/repo"
def set_repo(p):
    global GATE_REPO
    GATE_REPO = p
'''
    BAD_USER = '''
from gate import GATE_REPO
def f():
    return GATE_REPO
'''
    # 安全写法：import 模块、读属性
    OK_STYLE = '''
import gate
def f():
    return gate.GATE_REPO
'''
    return [
        # ① 正常不报
        ("snapshot.constant_copy_is_fine",
         lambda: problems(sources={"gate": GOOD,
                                   "check_x": GOOD_USER}) == []),
        ("snapshot.attribute_style_is_fine",
         lambda: problems(sources={"gate": BAD_GATE,
                                   "check_x": OK_STYLE}) == []),
        # ② 该报的必须报
        ("★ snapshot.mutable_copy",
         lambda: [p.code for p in problems(
             sources={"gate": BAD_GATE, "check_x": BAD_USER})
         ] == ["snapshot.mutable_copy"]),
        # 死导入不报（import 了没用的不算风险）
        ("snapshot.dead_import_not_reported",
         lambda: problems(sources={"gate": BAD_GATE,
                                   "check_x": "from gate import GATE_REPO\n"}) == []),
        # ② 别名模块赋值（`import gate as g; g.GATE_REPO = …`）—— 与
        #    `gate.GATE_REPO = …` 是同一件事的另一种写法，此前漏报（实测 []）
        ("★ snapshot.mutable_copy_via_alias",
         lambda: [p.code for p in problems(sources={
             "gate": ALIAS_GATE, "usr": ALIAS_USER, "victim": ALIAS_VICTIM})
         ] == ["snapshot.mutable_copy"]),
        # ② 发现式源模块：**扫描面里的任何 .py** 都可作为源模块，不再只认
        #    手写名单里的 12 个名字（此前 16 个 check_*.py 全部看不见）
        ("★ snapshot.source_from_any_module",
         lambda: [p.code for p in problems(sources={
             "check_zzz": CHECK_AS_SOURCE, "victim": CHECK_AS_VICTIM})
         ] == ["snapshot.mutable_copy"]),
        # ② 派生快照：模块顶层把「经薄封装读到可变全局」的表达式存成常量
        #    （`OUT = repo(NAME)`，repo() 体内读 GATE_REPO ⇒ 冻在 import 那一刻）
        ("★ snapshot.derived_copy",
         lambda: [p.code for p in problems(sources={
             "gate": GATE_WITH_REPO,
             "facts": "OUT = repo('L.json')\nprint(OUT)\n"})
         ] == ["snapshot.derived_copy"]),
        # ③ 空输入必须报
        ("★ snapshot.empty_scan", lambda: problems(sources={}) != []),
    ]


GATE = meta("模块级快照闸门",
            "跨模块 import 的可变全局是值拷贝（陈旧快照）：改成 import 模块 + 读属性",
            knobs=("REFLECT_SNAPSHOT_ROOT",))

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.snapshot"), _cases(), run))
