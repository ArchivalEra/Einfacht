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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import fatal, finish, main_selftest_or, meta, off, repo, selftest  # noqa: E402
from i18n import M                                        # noqa: E402

DEFAULT_ROOT = "zreflect"
KNOB = "REFLECT_I18N_ROOT"


# CJK 统一表意文字的码点区间（U+4E00–U+9FFF）。**用码点常量而不是字面字符**：
# 写成 `"一"`/`"鿿"` 会让本闸门扫到自己的源码（那两个就是区间端点）——
# 实测踩到（报了两条「一」「鿿」的假违规）。
CJK_LO, CJK_HI = 0x4E00, 0x9FFF


def cjk(text):
    """含中日韩统一表意文字？"""
    return any(CJK_LO <= ord(c) <= CJK_HI for c in text)


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
        return [M("i18n_cover.empty_scan")]
    for name, src in paths:
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            out.append(M("i18n_cover.parse_error", file=name, error=e))
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
        # ② `re.compile(...)` 的实参 —— **匹配器数据**（正则里的中文是判据，
        #    不是要说给人听的话；check_stale 的 HIST_MARK 就是这类）。
        # ⚠️ **自证标题曾在豁免里，已撤销**（用户裁决：「选英文出中文肯定不允许」，
        #    自证标题确实打在屏幕上）。现在 13 个闸门的标题都走
        #    `M("gate.title.<name>")` ⇒ 进语言包。豁免留在这里会给「写回中文
        #    标题」放行 —— 那条豁免正是让英文模式漏中文的原因。
        # 豁免形状①：「调用实参」——`meta(...)` / `re.compile(...)` 等
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                fn = getattr(f, "id", "") or getattr(f, "attr", "")
                if fn in ("meta", "module_meta",
                          "compile", "startswith", "endswith", "match", "search",
                          "fullmatch", "find"):
                    for n in ast.walk(node):
                        if isinstance(n, ast.Constant):
                            exempt_ids.add(id(n))
        # 豁免形状②：「整个函数体」——AUTO 机器块渲染函数（PINNED）：
        # `render_block` / `render_gates` 的文本**必须固定一种语言**
        # （用户决策 #2：不算违规）—— 它写进 STATE.md 并被 --check 逐字节
        # 对账，跟随语言就「同一提交在不同环境结果不同」（不收敛）。
        # 豁免形状⑤：「语言包装载器自身的错误」—— `i18n.py` 里 `MissingPack`
        # 的文案**不能用 M()**（循环依赖：M 依赖语言包，语言包坏了才抛它）。
        # 这是设计上的合法例外，不是漏迁。文件级豁免，因为该文件通篇是
        # 「语言包怎么装载」的机制，它的错误文案必然在语言包之外。
        if name == "i18n.py":
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    exempt_ids.add(id(node))
        # ⚠️ 曾试图豁免整个 `_cases()` 函数体 —— **错了**：夹具里的源码样例
        # （`GOOD`/`BARE`/`LABEL` 的多行字符串）正是本闸门自证要扫的对象，
        # 豁免它们会让三条反向断言失效（实测踩到 2 PASS / 3 FAIL）。
        # 夹具**源码文本**豁免，夹具**标签**不豁免 —— 后者按 1C 必须 id 化。
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
            # 用户决策 1C 的真实含义：标签**以点分 id 开头**即可，后面可以跟
            # 简短的中文括注帮扫读。所以「已 id 化」的标签不算违规。
            if re.match(r"^\s*(★\s*)?[a-z_][a-z0-9_]*(\.[a-z0-9_.]+)+",
                        v):
                continue
            out.append(M("i18n_cover.bare_text",
                         file=name, lineno=node.lineno, text=v[:40]))
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
        return off(M("i18n_cover.off", knob=KNOB))
    paths = collect(root)
    if not paths:
        return fatal(M("i18n_cover.scan_empty_dir", root=root))
    return finish(M("i18n_cover.title"), problems(paths),
                  M("i18n_cover.ok", files=len(paths)))


def _cj(n):
    """按码点造 n 个 CJK 字符（源码里不出现中文字面量，AST 求值后是真 CJK）。

    ⚠️ 夹具**必须含真中文**（否则「该报的必须报」用例没有对象），但字面量
    又会被本闸门扫到（闸门看的是 AST 求值后的值）。用码点构造是唯一干净的
    写法 —— 与 `cjk()` 里用码点区间同源。
    """
    return "".join(chr(CJK_LO + i) for i in range(n))


def _cases():
    SAMPLE = _cj(4)          # 夹具里的中文样例
    GOOD = f'''
"""docstring may contain CJK (maintainer docs) — {SAMPLE}"""
from i18n import M

def f(x):
    out = []
    out.append(M("replay.no_cmd", k=x))
    return out
'''
    BARE = f'''
def f(x):
    out = []
    out.append("`%s` {SAMPLE}" % x)  # CJK sample
    return out
'''
    LABEL = f'''
def _cases():
    return [("{SAMPLE}", lambda: True)]  # CJK label sample (must be flagged)
'''
    EMPTY = ""
    return [
        # ① 正常不报
        ("i18n_cover.good_fixture", lambda: problems([("good.py", GOOD)]) == []),
        # ② 该报的必须报
        ("★ i18n_cover.bare_text（本体在说人话）",
         lambda: [x.code for x in problems([("bare.py", BARE)])
                  ] == ["i18n_cover.bare_text"]),
        ("★ i18n_cover.bare_text（自证标签按 1C 必须是 id）",
         lambda: [x.code for x in problems([("label.py", LABEL)])
                  ] == ["i18n_cover.bare_text"]),
        ("★ i18n_cover.parse_error（解析失败不许当通过）",
         lambda: [x.code for x in problems([("bad.py", "def (")])] == ["i18n_cover.parse_error"]),
        # ③ 空输入必须报
        ("★ i18n_cover.empty_scan（零值守卫）", lambda: problems([]) != []),
    ]


GATE = meta("语言覆盖闸门", "本体零语言：用户可见文本必须走 M(code)；语言包可选",
            knobs=("REFLECT_I18N_ROOT",))

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.i18n_cover"), _cases(), run))
