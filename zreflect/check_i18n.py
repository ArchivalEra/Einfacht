#!/usr/bin/env python3
"""语言覆盖闸门（**可插拔模块**，issue #26）：本体真·零语言化的机械保证。

它守的是一条**封闭判据**——「本体里不许有用户可见的自然语言」：

  · **消息**必须是 `M(<字面量 code>, **params)`——不许 `out.append("中文…")`
    这种裸字面量（那是「本体在说人话」，正是本条要消灭的）；
  · **自证用例标签**按用户决策（1C）**id 化**——不许自然语言句子；
  · **docstring** 豁免（维护者文档，不是输出）；
  · **语言包**里可以有任何自然语言（那是可选数据，不在本体里）。

为什么这条判据必须存在（不给就是「看起来零语言、实际漏一半」）：

  语言包是可选的 ⇒ 用户可能只装 `en`。若本体里还藏着一条中文硬编码消息，
  它会在 en 用户屏幕上显示中文，且**没有任何东西会报**——正是本仓立身
  要消灭的静默退化。这条闸门把「本体零语言」从口号变成可判定。

诚实边界（写明的缺口）：判据是 **AST 级**的——抓「裸中文字面量出现在输出位置」，
抓不到「用英文写的消息」（那仍是本体语言，但主体已零中文；要抓它需要
更复杂的语言识别，代价过大）。所以本闸门的强度 = 「零中文 + 消息必须走 M()」。
"""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import fatal, finish, main_selftest_or, meta, off, repo, selftest  # noqa: E402

DEFAULT_ROOT = "zreflect"
KNOB = "REFLECT_I18N_ROOT"


def cjk(text):
    """含中日韩统一表意文字？"""
    return any("\u4e00" <= c <= "\u9fff" for c in text)


def _literal_text(node):
    """一个表达式里所有字符串常量的拼接（用于判断是否含中文）。"""
    return "".join(c.value for c in ast.walk(node)
                   if isinstance(c, ast.Constant) and isinstance(c.value, str))


def _is_msg_call(node):
    """`M(code, **params)` 或 `i18n.M(...)`。"""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Name) and f.id == "M") or \
           (isinstance(f, ast.Attribute) and f.attr == "M")


def _is_output_call(node):
    """产出用户可见文本的调用：append / print / off / fatal / finish。"""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Attribute) and f.attr == "append":
        return True
    return isinstance(f, ast.Name) and f.id in ("print", "off", "fatal", "finish")


def problems(paths):
    """纯函数：返回问题清单（空 = 零语言）。`paths` = [(名字, 源码文本)]。

    `paths` 可注入 ⇒ 自证用假源码，零文件 I/O。
    """
    out = []
    if not paths:
        return ["扫描面为空 —— 没找到源码不是「零语言通过」（零值守卫）"]
    for name, src in paths:
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            out.append("%s 解析不了：%s —— 解析失败不许当通过" % (name, e))
            continue
        # 收集 docstring 节点（豁免）
        doc_nodes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                d = ast.get_docstring(node, clean=False)
                if d:
                    for n in ast.walk(node):
                        if isinstance(n, ast.Constant) and n.value == d:
                            doc_nodes.add(id(n))
                            break
        # 收集「在 M(...) 里」的常量 id（合法位置）
        msg_consts = set()
        for node in ast.walk(tree):
            if _is_msg_call(node):
                for n in ast.walk(node):
                    if isinstance(n, ast.Constant):
                        msg_consts.add(id(n))
        # 豁免面（**声明的、不是猜的**）：这些位置的 CJK 不是用户可见消息。
        # 每一条都要说清为什么，否则「豁免」会变成下一张会漂的手写名单。
        exempt_ids = set()
        # ① `GATE = meta(名字, 描述…` / `MODULE = module_meta(…)` —— **声明数据**
        #    （进 AUTO:GATES 机器块，用户决策：不进语言包）。
        # ② `main_selftest_or(…, "标题"…)` 与 `selftest(…)` 的标题 —— 自证输出
        #    是**开发者界面**，不是产品输出。
        # ③ `re.compile(...)` 的实参 —— **匹配器数据**（正则里的中文是判据，
        #    不是要说给人听的话；check_stale 的 HIST_MARK 就是这类）。
        # 豁免形状①：「调用实参」——`meta(...)` / `re.compile(...)` 等
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                fn = getattr(f, "id", "") or getattr(f, "attr", "")
                if fn in ("meta", "module_meta", "main_selftest_or", "selftest",
                          "compile"):
                    for n in ast.walk(node):
                        if isinstance(n, ast.Constant):
                            exempt_ids.add(id(n))
        # 豁免形状②：「整个函数体」——AUTO 机器块渲染函数（PINNED）：
        # `render_block` / `render_gates` 的文本**必须固定一种语言**
        # （用户决策 #2：不算违规）—— 它写进 STATE.md 并被 --check 逐字节
        # 对账，跟随语言就「同一提交在不同环境结果不同」（不收敛）。
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in (
                    "render_block", "render_gates", "_gates_header"):
                for n in ast.walk(node):
                    if isinstance(n, ast.Constant):
                        exempt_ids.add(id(n))
        # 豁免形状③：「AUTO 块的常量」——`PREAMBLE` / `GATES_*` 这类模块级
        # 常量同为 PINNED 文本（同决策 #2）。
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id in ("PREAMBLE", "GATES_BEGIN",
                                                "GATES_END", "_PREAMBLE"):
                for n in ast.walk(node):
                    if isinstance(n, ast.Constant):
                        exempt_ids.add(id(n))

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            v = node.value
            if not cjk(v):
                continue
            if id(node) in doc_nodes or id(node) in msg_consts or id(node) in exempt_ids:
                continue
            out.append("%s:%d 本体里有裸中文文本 %r —— 用户可见的消息必须走 "
                       "M(<字面量 code>, **params)；自证标签按 1C 必须是 id"
                       % (name, node.lineno, v[:40]))
    return out


def collect(root):
    """读 root 下所有 .py 的源码（(名字, 文本) 列表）。"""
    out = []
    d = repo(root)
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
        return off("语言覆盖闸门：%s 未配置 ⇒ 本闸门未启用（可插拔模块；"
                   "配了才检查「本体零语言」）" % KNOB)
    paths = collect(root)
    if not paths:
        return fatal("扫描面 %s 为空 —— 没找到源码不是「零语言通过」" % root)
    return finish("语言覆盖闸门", problems(paths),
                  "语言覆盖闸门：OK（%d 个文件本体零语言；语言包可选）"
                  % len(paths))


def _cases():
    GOOD = '''
"""docstring 里有中文是允许的（维护者文档）。"""
from i18n import M

def f(x):
    out = []
    out.append(M("replay.no_cmd", k=x))
    return out
'''
    BARE = '''
def f(x):
    out = []
    out.append("`%s` 没有复跑命令 —— 没 cmd 的事实就是散文" % x)
    return out
'''
    LABEL = '''
def _cases():
    return [("★ 正文裸数字 ⇒ 必须报", lambda: True)]
'''
    EMPTY = ""
    return [
        # ① 正常不报
        ("消息全走 M()，docstring 有中文 ⇒ 不报", lambda: problems([("good.py", GOOD)]) == []),
        # ② 该报的必须报
        ("★ 裸中文 append ⇒ 必须报（本体在说人话）",
         lambda: any("裸中文文本" in x for x in problems([("bare.py", BARE)]))),
        ("★ 自证标签是中文句子 ⇒ 必须报（按 1C 必须是 id）",
         lambda: any("裸中文文本" in x for x in problems([("label.py", LABEL)]))),
        ("★ 语法坏 ⇒ 必须报（解析失败不许当通过）",
         lambda: any("解析不了" in x for x in problems([("bad.py", "def (")]))),
        # ③ 空输入必须报
        ("★ 扫描面为空 ⇒ 必须报（零值守卫）", lambda: problems([]) != []),
    ]


GATE = meta("语言覆盖闸门", "本体零语言：用户可见文本必须走 M(code)；语言包可选",
            knobs=("REFLECT_I18N_ROOT",))

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:],
                              "语言覆盖闸门（本体零语言化）", _cases(), run))
