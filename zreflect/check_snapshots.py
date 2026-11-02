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
# 本地模块名（可 import 的兄弟模块）—— 只关心这些，不扫第三方库。
LOCAL_MODULES = ("gate", "knobs", "i18n", "ledger", "render", "collect",
                 "living", "guard", "runner", "facts", "registry", "doctor")


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


def _reassigned_elsewhere(trees, src_mod, name):
    """有没有**任何模块**在运行期给 `src_mod.name` 赋值（`src_mod.name = …`）？

    ⚠️ 判据形状的关键：不是「源模块自己赋值几次」（`gate.GATE_REPO` 只赋一次），
    而是「**别人会不会改它**」—— `check_envfile` / `i18n` 的自证都在
    `gate.GATE_REPO = …` 改它。那才是拷贝变陈旧的真正条件。

    只赋值一次、无人改写的常量（`REGISTRY`、`LOCAL_MODULES`）不报 ——
    它们的语义是「一个数据表」，拷贝与引用没区别。
    """
    for _mod, tree in trees.items():
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            for t in targets:
                # 形状①：`<src_mod>.<name> = …`（**别的模块**从外面改）
                if isinstance(t, ast.Attribute) and t.attr == name \
                        and isinstance(t.value, ast.Name) \
                        and t.value.id == src_mod:
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
    for mod, tree in sorted(trees.items()):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module not in LOCAL_MODULES:
                continue
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
        # ③ 空输入必须报
        ("★ snapshot.empty_scan", lambda: problems(sources={}) != []),
    ]


GATE = meta("模块级快照闸门",
            "跨模块 import 的可变全局是值拷贝（陈旧快照）：改成 import 模块 + 读属性",
            knobs=("REFLECT_SNAPSHOT_ROOT",))

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.snapshot"), _cases(), run))
