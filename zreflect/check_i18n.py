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

## 它现在有四条判据族（第 16 轮的审视结论：**不拆**）

  1. **裸中文**（`bare_text`）—— 输出位置的 CJK 字符串常量
  2. **PINNED 声明面** —— `PINNED:` 标记的函数/常量整段豁免（AUTO 机器块必须
     固定语言，跟随语言就不收敛）
  3. **夹具字面量**（`fixture_literal`）—— `_cases()` 里的中文只许在**标签**
     与 **docstring**；夹具源码必须码点构造（同一错误犯三次后补的判据）
  4. **消息必须走 M()** —— `_is_msg_call` / `_is_output_call` 的形状判据

**为什么不拆成四个闸门**：它们共享同一次 `ast.parse(src)` 与同一轮文件遍历。
拆开 = 四份重复的解析与遍历，而每一份都可能独立漂（本仓最痛的那种）。
四条判据族的**差异只在「什么算合法」**，那已经由各自的 helper 隔离
（`_declares_pinned` / `_fixture_literal_problems` / `cjk`）。共享解析是拆不动
的真实理由 —— 不是因为「它们看起来像一类」。

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

# 未配旋钮时扫**这些**目录 —— 套件自己的全部 Python。此前只扫 `zreflect/`，
# `.zcode/` 的两个钩子脚本（`inject-state.py` / `stop-refresh.py`）在面外，
# 于是它们**整份裸中文**且无人拦（实测：未装语言包时注入吐中文，而闸门吐 code）。
# 钩子是套件的一部分 ⇒ 同一道判据要管它们。
DEFAULT_ROOTS = ("zreflect", ".zcode")
KNOB = "REFLECT_I18N_ROOT"


# CJK 统一表意文字的码点区间（U+4E00–U+9FFF）。**用码点常量而不是字面字符**：
# 写成 `"一"`/`"鿿"` 会让本闸门扫到自己的源码（那两个就是区间端点）——
# 实测踩到（报了两条「一」「鿿」的假违规）。
from i18n import CJK_LO, CJK_HI, han                       # noqa: E402


PINNED_MARK = "PINNED:"


def _declares_pinned(doc):
    """docstring 里有没有**带理由的** `PINNED:` 声明。

    ⚠️ 只认「`PINNED:` 后面还有字数 ≥ 8 的理由」：否则任何函数只要在
    docstring 里写个 `PINNED:` 就能把它的全部中文豁免（实测：一个普通
    `report_problem()` 加一行 `PINNED: x` 就全豁免）。豁免必须说明「为什么
    这段文本不能翻译」—— 与 `REFLECT_INVARIANTS` 的 `why` 必填同一条纪律。
    """
    if not doc or PINNED_MARK not in doc:
        return False
    idx = doc.index(PINNED_MARK)
    reason = doc[idx + len(PINNED_MARK):].strip()
    # 理由取到第一个句号 / 换行为止（一句话够用）
    for sep in ("\n", "。", ". "):
        cut = reason.find(sep)
        if cut != -1:
            reason = reason[:cut]
    return len(reason.strip()) >= 8


def _pinned_by_comment(src, node):
    """该赋值语句**紧邻的上方**（前面连续注释块里）有没有 `PINNED:`。

    模块级常量没有 docstring，声明只能写在注释里。只向上看紧邻的注释块
    （遇到空行或非注释行就停）—— 不扫全文，避免「文件里任何一处写了
    PINNED: 就全豁免」。
    """
    lines = src.splitlines()
    i = node.lineno - 2                      # 上一行（0-based）
    while i >= 0:
        line = lines[i].strip()
        if line.startswith("#"):
            if PINNED_MARK in line:
                return True
            i -= 1
            continue
        break                                # 注释块结束
    return False


# 「含中文吗」的判据住在 `i18n.han()`（零语言制度的持有者），这里只转发 ——
# 两份区间常量会漂（C4）。
cjk = han


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
                # `Rule(...)` 是**纪律声明数据**：它的 text/why 渲染进
                # `PRINCIPLES.md` 的 AUTO:RULES 块（PINNED：固定语言、逐字节对账）。
                # 与 `meta()` 的 desc 同一类 —— 声明面，不进语言包。
                if fn in ("meta", "module_meta", "Rule",
                          "compile", "startswith", "endswith", "match", "search",
                          "fullmatch", "find"):
                    for n in ast.walk(node):
                        if isinstance(n, ast.Constant):
                            exempt_ids.add(id(n))
        # 豁免形状②：「PINNED 声明面」——AUTO 机器块渲染函数与常量。
        # 文本**必须固定一种语言**（用户决策 #2：不算违规）—— 它写进 STATE.md
        # 并被 --check 逐字节对账，跟随语言就「同一提交在不同环境结果不同」。
        #
        # ⚠️ **按声明收编，不按名字**（deepening 第 8 轮）：此前这里是两份硬编码
        # 名单（函数名元组 + 常量名元组），本仓 AGENTS 明写「手写名录一定会漂」——
        # 实测：新写一个返回中文的 PINNED 渲染器（`render_world_block`）⇒ 立刻被
        # 误报为违规，除非有人记得回去改名单。
        # 现在：**生产 PINNED 文本的地方自己声明** `PINNED:`（docstring 或
        # 紧邻注释均可），本闸门扫标记。名字不再承重（与 C1 同一原则）。
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
        # 声明式收编：「PINNED:」出现在**该节点自己的 docstring** 里 ⇒ 整段豁免。
        # 函数（渲染器）与模块级常量（机器块样板）都认同一套标记。
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _declares_pinned(ast.get_docstring(node, clean=False)):
                    for n in ast.walk(node):
                        if isinstance(n, ast.Constant):
                            exempt_ids.add(id(n))
            elif isinstance(node, ast.Assign):
                # 常量：`PINNED:` 可以写在紧邻的前置注释里（模块级常量的
                # 「docstring」不存在）—— 用源码行区间回查。
                if _pinned_by_comment(src, node):
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
        out += _fixture_literal_problems(name, tree)
    return out


def _fixture_literal_problems(name, tree):
    """**自证夹具里不许有中文源码字面量**（必须是码点构造）。

    为什么这条值得判据：我踩了**三次**（第 8 轮 PINNED 理由、第 9 轮、
    第 13 轮）—— 每次都是「写个中文夹具/断言 → `check_i18n` 报 bare_text →
    才发现本文件自己在扫描面内」。第三次之后该把它变成机器判据。

    `_cases()` 里的 CJK 字符串常量只许出现在两种合法位置：
      · 自证**标签**（`(标签, callable)` 元组的首元素）—— 按 1C 决策，标签
        是 id 形式的，后面可以跟中文括注帮扫读
      · **docstring** —— 维护者文档，不是输出
    其余（夹具源码样例 / 断言里的中文串）⇒ 报。
    码点构造（`chr(CJK_LO)` / `_cj(n)`）产出的值**不在 AST 里**，天然不报 ——
    这就是正确的写法。
    """
    fns = [n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == "_cases"]
    if not fns:
        return []
    fn = fns[0]
    # ⚠️ **范围要覆盖辅助函数**：`_cases()` 调用的同文件 helper 也在自证路径上
    # （实测踩到：判据锚点写进 `_streams_documented()`，本判据扫不到 ⇒ bare_text
    # 由主判据报出、这条漏）。把 `_cases` 里**被引用的顶层函数**一并纳入。
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    # ⚠️ **PINNED 的函数不算夹具 helper**：`_cases()` 会调用 `render_gates()`
    # 来测「渲染确定性」，但那个函数的文本是 AUTO 机器块、**本来就固定语言**
    # （第 3 族已豁免）。把它拉进夹具扫描会误报（实测：7 条 PINNED 行被
    # `fixture_literal` 抓）。豁免面之间必须互相尊重。
    helpers = [n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name in called
               and not _declares_pinned(ast.get_docstring(n, clean=False))]
    bodies = [fn] + helpers                          # 统一遍历的节点清单
    # 合法节点：docstring
    docs = set()
    for node in [n for b in bodies for n in ast.walk(b)]:
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                for n in ast.walk(node):
                    if isinstance(n, ast.Constant) and n.value == d:
                        docs.add(id(n))
                        break
    # 合法节点：自证标签（元组首元素）
    labels = set()
    for node in [n for b in bodies for n in ast.walk(b)]:
        if isinstance(node, ast.Tuple) and len(node.elts) == 2 \
                and isinstance(node.elts[0], ast.Constant):
            labels.add(id(node.elts[0]))
    out = []
    for node in [n for b in bodies for n in ast.walk(b)]:
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if not cjk(node.value):
            continue
        if id(node) in docs or id(node) in labels:
            continue
        out.append(M("i18n_cover.fixture_literal",
                     file=name, lineno=node.lineno, text=node.value[:40]))
    return out


def collect_from(d, root):
    """读目录 `d` 下所有 .py 的源码（(名字, 文本) 列表）。"""
    out = []
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
    # ⚠️ 默认扫描根**不是空**：本闸门守的正是**套件自己**的代码，所以未配旋钮
    # 时扫**工具仓**的 `zreflect/`。此前 `DEFAULT_ROOT` 定义了却**从不使用**，
    # 旋钮没人配 ⇒ 活体 `registry --run commit` 里它永远 `off` ——
    # 「闸门存在、自证绿、但从没跑过」。与 `check_snapshots` 同一个病。
    #
    # 两条口径（与 `i18n.pack_dir()` 同款，别混）：
    #   · 未配 ⇒ **工具仓**的 `zreflect/`（跟着套件走，跨仓夹具也对）
    #   · 配了 ⇒ **被检查仓**相对的路径（env 里写的「相对仓库根的名字」）
    # 混成一条会导致跨仓夹具里 FATAL（实测：GATE_REPO=$tmp 时扫不到 zreflect/）。
    configured = os.environ.get(KNOB, "").strip()
    roots = [configured] if configured else list(DEFAULT_ROOTS)
    paths = []
    for root in roots:
        if configured:
            d = repo(root)
        else:
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", root)
            d = os.path.abspath(d)
        found = collect_from(d, root)
        if not found and configured:
            return fatal(M("i18n_cover.scan_empty_dir", root=root))
        paths.extend(found)
    if not paths:
        return fatal(M("i18n_cover.scan_empty_dir", root=", ".join(roots)))
    return finish(M("i18n_cover.title"), problems(paths),
                  M("i18n_cover.ok", files=len(paths)))


_PH = re.compile(r"%\(([A-Za-z_][A-Za-z0-9_]*)\)"
                 r"(?:[#0\-+ ]*)(?:\d+)?(?:\.\d+)?[hlL]?([diouxXeEfFgGcrsa])")


def _params_for(template):
    """按模板的**转换符**造参数：`%d`/`%f` 给数字，其余给串。

    ⚠️ 一律给 `"v"` 会在 `%(count)d` 上炸 `TypeError`（实测）。
    """
    return {m.group(1): (3 if m.group(2) in "dixXfFeEgG" else "v")
            for m in _PH.finditer(template)}


def _null_output_has_no_cjk():
    """**未装语言包**时渲染全部 code，断言输出零 CJK。

    null 包只输出 `code(param=…)` —— 这是「没要语言包 ⇒ 零自然语言」的
    **行为**判据。穷举全部 key（此前只探六个手挑的，漏掉了 `inject.*` 等
    后加的模板）。

    ⚠️ 注意它**不能**证明「模板里没有中文」：null 包根本不查表。后者由
    `_packs_match_their_language()` 管（装包渲染 + 按语言判 CJK）。
    """
    import i18n                                          # noqa: PLC0415
    import re                                            # noqa: PLC0415
    try:
        table = i18n.load_pack("en")
    except Exception:                                    # noqa: BLE001
        return False              # 读不到真包 ⇒ 没法证明，不算通过
    if not table:
        return False              # 零值守卫
    probes = 0
    with i18n.bind(i18n.NULL):
        for code in sorted(table):
            if cjk(str(i18n.M(code, **_params_for(table[code])))):
                return False
            probes += 1
    return probes == len(table)


def _packs_match_their_language():
    """**装包**渲染：en / de 的每一条都不许含 CJK；zh 的 *文案* 可以含。

    这是「模板本身有没有中文」的真判据 —— null 包测不到它（null 不查表）。

    判据按语言：`en` / `de` 输出里出现 CJK ⇒ 那条模板没被翻译（或漏了）。
    `zh` 允许中文（那是它的语言）。只在**已装**的包里验，装了 `de` 就验 `de`。

    零值守卫：至少验到一个非 zh 的包。
    """
    import i18n                                          # noqa: PLC0415
    checked = 0
    for lang in ("en", "de"):
        try:
            table = i18n.load_pack(lang)
        except Exception:                                # noqa: BLE001
            continue
        if not table:
            continue
        cat = i18n.Catalog.load(lang, {lang: table})
        with i18n.bind(cat):
            for code in sorted(table):
                if cjk(str(i18n.M(code, **_params_for(table[code])))):
                    return False
        checked += 1
    return checked >= 1




def _cj(n):
    """按码点造 n 个 CJK 字符（源码里不出现中文字面量，AST 求值后是真 CJK）。

    ⚠️ 夹具**必须含真中文**（否则「该报的必须报」用例没有对象），但字面量
    又会被本闸门扫到（闸门看的是 AST 求值后的值）。用码点构造是唯一干净的
    写法 —— 与 `cjk()` 里用码点区间同源。
    """
    return "".join(chr(CJK_LO + i) for i in range(n))


def _cjk_src(doc):
    """造一段含 CJK 字面量的源码（字面量用码点构造，本文件源码里不出现中文）。"""
    return ('def render_world_block(w):\n'
            '    """%s"""\n'
            '    return "%s"\n') % (doc, chr(CJK_LO) * 2)


# 理由用码点构造（本文件源码里不出现中文 —— 否则会被自己的覆盖闸门收编）
PINNED_FN = _cjk_src("PINNED: " + chr(CJK_LO) * 10 + " pinned, byte-exact.")
PINNED_BARE = _cjk_src("PINNED: x")
# 夹具字面量三例（值用码点拼，本文件源码不出现中文）
_CJ4 = chr(CJK_LO) * 4
FIXTURE_BAD = ("def _cases():\n"
               "    SAMPLE = \"" + _CJ4 + "\"\n"
               "    return [(\"ok.label\", lambda: SAMPLE == SAMPLE)]\n")
FIXTURE_LABEL = ("def _cases():\n"
                 "    return [(\"ok.label" + _CJ4 + "\", lambda: True)]\n")
FIXTURE_HELPER = ("def _helper():\n"
                  "    return \"" + _CJ4 + "\"\n"
                  "\n"
                  "def _cases():\n"
                  "    return [(\"ok\", lambda: _helper() == \"x\")]\n")
FIXTURE_DOC = ("def _cases():\n"
               "    \"\"\"doc " + _CJ4 + "\"\"\"\n"
               "    return [(\"ok\", lambda: True)]\n")
BARE_FN = _cjk_src("ordinary renderer.")


def _cases():
    SAMPLE = _cj(4)          # 夹具里的中文样例
    GOOD = f'''
"""docstring may contain CJK (maintainer docs) — {SAMPLE}"""
from i18n import M

def f(x):
    out = []
    out.append(M("replay.no_cmd", key=x))
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
        ("★ i18n_cover.bare_text",
         lambda: [x.code for x in problems([("bare.py", BARE)])
                  ] == ["i18n_cover.bare_text"]),
        ("★ i18n_cover.bare_text_in_label",
         lambda: [x.code for x in problems([("label.py", LABEL)])
                  ] == ["i18n_cover.bare_text"]),
        ("★ i18n_cover.parse_error",
         lambda: [x.code for x in problems([("bad.py", "def (")])] == ["i18n_cover.parse_error"]),
        # ② PINNED 按**声明**收编，不按名字（此前两份硬编码名单会漂）
        ("i18n_cover.pinned_by_declaration",
         # 带 `PINNED:` 声明的渲染器 ⇒ 豁免（名字随意 —— 不承重）
         lambda: problems([("r.py", PINNED_FN)]) == []),
        ("★ i18n_cover.undeclared_pinned_still_fires",
         # 同样函数**不带声明** ⇒ 必须报（否则豁免变成放水）
         lambda: [p.code for p in problems([("r.py", BARE_FN)])
                  ] == ["i18n_cover.bare_text"]),
        # **冒充 PINNED 必须有理由**（否则任何函数写一行 `PINNED: x` 就全豁免）
        ("★ i18n_cover.pinned_needs_reason",
         lambda: [p.code for p in problems([("r.py", PINNED_BARE)])]
         == ["i18n_cover.bare_text"]),
        # **自证夹具里不许有中文源码字面量**（我踩了三次：第 8/9/13 轮）。
        # 夹具源码必须码点构造；标签与 docstring 是合法位置。
        ("★ i18n_cover.fixture_literal",
         lambda: [p.code for p in problems([("t.py", FIXTURE_BAD)])
                  ] == ["i18n_cover.bare_text", "i18n_cover.fixture_literal"]),
        # helper 也在自证路径上 —— 判据必须覆盖 `_cases()` 调用的同文件函数
        # （实测踩到：锚点写进 helper，本判据漏判、只有主判据报）
        ("★ i18n_cover.fixture_literal_in_helper",
         lambda: "i18n_cover.fixture_literal" in
         [p.code for p in problems([("t.py", FIXTURE_HELPER)])]),
        ("i18n_cover.fixture_label_cjk_is_allowed",
         lambda: problems([("t.py", FIXTURE_LABEL)]) == []),
        ("i18n_cover.fixture_docstring_cjk_is_allowed",
         lambda: problems([("t.py", FIXTURE_DOC)]) == []),
        # **端到端**：null 包下真渲染几条消息，输出里不许有 CJK。
        # 静态扫描（本闸门主体）抓「源码里的裸中文」，抓不到「运行时拼出来的
        # 中文」—— 实测：注入脚本曾自动挑语言包，源码干净、输出全中文。
        ("★ i18n_cover.null_pack_output_has_no_cjk",
         lambda: _null_output_has_no_cjk()),
        # **模板本身**的中文：装包渲染，en/de 一条都不许有 CJK。
        # （null 包测不到这个 —— 它根本不查表。这是那条判据的缺口，已补。）
        ("★ i18n_cover.packs_match_their_language",
         lambda: _packs_match_their_language()),
        # 反向：把一条中文塞进 null 渲染路径 ⇒ 必须被抓（证明上一条有牙）
        ("★ i18n_cover.cjk_detector_can_red",
         lambda: cjk(chr(0x4E2D)) and not cjk("ascii only")),
        # 扫描面必须**包含钩子目录**：`.zcode/` 的两个钩子是套件的一部分，
        # 曾经整份裸中文且无人拦（实测）。判据是「默认根里有它」。
        ("★ i18n_cover.hooks_dir_is_scanned",
         lambda: ".zcode" in DEFAULT_ROOTS),
        # ③ 空输入必须报
        ("★ i18n_cover.empty_scan", lambda: problems([]) != []),
    ]


GATE = meta("语言覆盖闸门", "本体零语言：用户可见文本必须走 M(code)；语言包可选",
            knobs=("REFLECT_I18N_ROOT",))

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.i18n_cover"), _cases(), run))
