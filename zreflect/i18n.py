#!/usr/bin/env python3
"""消息模块：**本体零语言，语言包可选**（issue #26）。

设计前提（用户定的场景）：用户拉下 Einfacht 套件后，**从一堆包里挑一个语言包**——
英语、中文、或任何别的。本体本身**不做语言表达**，输出的是消息 code 与参数。
没装语言包时，输出 `code(k=v)` 这种**结构化、可读、无自然语言**的形式。

换句话说：**中文不是源语言**，中文只是可选包之一。这砍掉了传统 i18n 的两个组件：

  · 不需要「改中文文案强制重译」（没有中文可改，所有语言平等）；
  · 不需要 fallback chain / draft 状态（包要么装了要么没装）。

interface（两个入口，A' 的 `Message(str)` 形状 —— 四份 design-it-twice 里唯一
做到「现有消费者零改动」的）：

    M(code, **params) -> Message      # 唯一构造点；code 必须是字面量
    bind(lang=None, tables=None)      # 装语言包；tables= 是自证注入点（零文件 I/O）

`Message` 是 **str 的子类**，它的值就是渲染结果，同时可读 `.code` / `.params`。
于是所有现有 `str` 消费者（`if problems` / `len(...)` / `"  · " + p`）**零改动**：

    >>> p = M("replay.no_cmd", k="py_lines")
    >>> bool([p]), "  · " + p
    (True, '  · replay.no_cmd(k=py_lines)')
    >>> p.code
    'replay.no_cmd'

契约字面量（`OFF:` / `FATAL:` / `=== N PASS / M FAIL ===` / `PASS | ` / `DOWN: `）
**在发射点用字面量**，不在数据里 —— 语言包**结构上不可能**产出它们（见 `NAMING` 校验）。

诚实边界：自证用例标签按用户决策（1C）**id 化**——自证输出是可机器读的 code 列表，
不再是自然语言句子。这是「本体真·零语言」的代价，用户明说接受。
"""
from __future__ import annotations

import os
import re

# 契约前缀：语言包的值**不许**以这些形状开头（否则一条翻译就能伪装成机器行，
# 让 run_phase 的 `startswith("OFF:")`、runner 的 `=== N PASS` grep 全部失效）。
# ⚠️ 这些谓词**只在成品行首**生效（`_validate` 检查模板渲染后的形态），
# 不是对模板本身的子串扫描 —— 消息正文里出现「A | B」是正常内容
# （实测踩到：`(tree | version)` 这种合法正文被 `\s\|\s` 误伤）。
_CONTRACT_SHAPES = (
    re.compile(r"^[A-Z][A-Z0-9_]*:"),      # OFF: / FATAL: / DOWN: / SKIP:
    re.compile(r"^==="),                   # === N PASS / M FAIL ===
    re.compile(r"^PASS \| "),              # selftest 行首
    re.compile(r"^fail \| "),
)

# null 包（唯一内置）：无语言包时的输出形状。
# `code` 无参数 ⇒ 只打 code；有参数 ⇒ `code(k=v, …)`。
_NULL = object()


class Message(str):
    """一条消息。**值是渲染结果**，`.code` / `.params` 是身份与数据。

    str 子类是有意为之：`finish()`/`if problems`/`"  · " + p`/`len(...)` 这些
    现有消费者全部继续工作 —— 这是四份方案里唯一做到零消费者改动的形状。
    """

    __slots__ = ("code", "params")

    def __new__(cls, code, params):
        # 构造时就用**当前生效**的语言包渲染 —— `bind()` 必须是上下文
        # 管理器而不是全局开关，正是为了让「谁渲染」有确定的作用域。
        return super().__new__(cls, _render(code, params, _ACTIVE[0][1]))

    def __init__(self, code, params):
        self.code = code
        self.params = params


_MAX_VALUE = 40            # null 包里单个值最多显示多少字符（长命令不撑屏）


def _fmt_value(v):
    """null 包里一个参数值怎么显示。

    用 `repr`：它**自动处理引号嵌套**（`find . -name '*.md'` 会被渲成
    `"find . -name '*.md'"`），手拼 `'%s'` 会在值内含引号时产出畸形串
    （实测踩到：`command='find . -name '*.md' | wc -l'`）。长值截断。
    """
    s = repr(v)
    if len(s) > _MAX_VALUE:
        s = s[:_MAX_VALUE - 1] + "…" + s[-1] if s[-1] in "\"'" else s[:_MAX_VALUE] + "…"
    return s


def _render(code, params, table):
    """把 (code, params) 渲染成文本。`table=None` ⇒ null 包形状。

    null 包（本体零语言）的格式：

        code(key='py_lines', actual=6180, expected=6014)

    **参数名必须是完整的英文单词**（`key` 不是 `k`，`actual` 不是 `got`）——
    这是 null 包唯一「可读」的来源：没有句子，但名字能自解释。参见本模块
    的「参数命名纪律」。

    无参数时只打 code。**不加安装提示**（那本身是自然语言，违背零语言；
    提示归 README 与 `--help`）。
    """
    if table is not None and code in table:
        return table[code] % params
    if not params:
        return str(code)
    inner = ", ".join("%s=%s" % (k, _fmt_value(params[k]))
                      for k in sorted(params))
    return "%s(%s)" % (code, inner)


def M(code, **params):
    """构造一条消息。`code` 必须是**字面量**（覆盖闸门会拒变量 code —— 否则
    目录无法被证明完备）。"""
    return Message(code, params)


def _table_for(lang, tables):
    """解析语言包：注入的 tables 优先，其次磁盘（`REFLECT_I18N/<lang>.json`）。

    未装语言包 ⇒ `None`（走 null 包）。**不做 fallback** —— 半装的语言包
    不该让人看到中英混杂（本仓纪律：宁可明说未启用，不假装查过）。
    """
    if tables is not None:
        got = tables.get(lang) if lang else None
        if got is None and lang:
            raise MissingPack("自证注入的 tables 里没有 %r" % lang)
        return got
    if not lang:
        return None
    import json                                          # noqa: PLC0415
    # ⚠️ 语言包是**工具**的属性，不是被检查仓库的 —— 用**本文件所在处**作锚，
    # 不用 `gate.repo()`（那是 GATE_REPO 相对）。
    # 实测踩到：跨仓夹具把 GATE_REPO 指向临时目录，那里没有 zreflect/lang
    # ⇒ `REFLECT_LANG=zh` 时夹具里每个闸门都 MissingPack FATAL（0/15 全红）。
    # 与 registry 的 `_zdir()` 是同一类修正。
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    i18n_dir = os.environ.get("REFLECT_I18N", "").strip() or "lang"
    base = (i18n_dir if os.path.isabs(i18n_dir)
            else os.path.join(tool_dir, i18n_dir))
    # 两种形状都认（后者是为**并行开发**设计的，避免多人写同一个文件）：
    #   lang/<lang>.json        单文件（小仓 / 样板）
    #   lang/<lang>/*.json      按命名空间分文件（每闸门一份，合并时后者覆盖同 code）
    single = os.path.join(base, "%s.json" % lang)
    d = os.path.join(base, lang)
    table = {}
    merged_any = False
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if not n.endswith(".json"):
                continue
            with open(os.path.join(d, n), encoding="utf-8") as fh:
                part = json.load(fh)
            if not isinstance(part, dict):
                raise MissingPack("语言包 %s 里的 %s 不是对象" % (lang, n))
            table.update(part)
            merged_any = True
    if os.path.exists(single):
        with open(single, encoding="utf-8") as fh:
            table.update(json.load(fh))
        merged_any = True
    if not merged_any:
        raise MissingPack(
            "语言包 %s 不在（%s 或 %s/ 都没有）。装一个，或撤掉 REFLECT_LANG "
            "—— 本仓不做「没装就回落中文」：那会让半装的语言包看起来像装好了"
            % (lang, single, d))
    _validate(table, lang)
    return table


class MissingPack(Exception):
    """语言包装配问题（缺失 / 损坏 / 形状非法）。调用方转 FATAL rc 2。"""


def _validate(table, lang):
    """校验语言包形状：值不许伪装成机器行（契约结构上不可被翻译）。"""
    if not isinstance(table, dict) or not table:
        raise MissingPack("语言包 %s 为空或不是对象 —— 空包不是「已翻译」"
                          "（零值守卫）" % lang)
    for code, value in table.items():
        if not isinstance(value, str):
            raise MissingPack("语言包 %s 的 `%s` 不是字符串" % (lang, code))
        # 只判**行首**：契约串的危险是「伪装成整行」，不是正文里提到它。
        if any(s.match(value) for s in _CONTRACT_SHAPES):
            raise MissingPack("语言包 %s 的 `%s` 值看起来像机器契约行（%r）—— "
                              "契约串在发射点用字面量，语言包不许产出它们"
                              % (lang, code, value[:40]))


class _Binding:
    """`bind()` 的上下文：装/卸语言包（可重入）。"""

    def __init__(self, lang, tables):
        self.lang = lang
        self.tables = tables
        self.prev = None

    def __enter__(self):
        self.prev = _ACTIVE[0]
        _ACTIVE[0] = (self.lang, _table_for(self.lang, self.tables))
        return self

    def __exit__(self, *exc):
        _ACTIVE[0] = self.prev
        return False


_ACTIVE = [(None, None)]           # (lang, table)


def bind(lang=None, tables=None):
    """装一个语言包（上下文管理器）。`lang=None` ⇒ null 包。

    `tables={lang: {code: template}}` ⇒ 纯内存（**自证专用**：零文件 I/O）。
    `lang` 未给时读 `REFLECT_LANG`；两者都没有 ⇒ null 包。
    """
    return _Binding(lang if lang is not None else
                    (os.environ.get("REFLECT_LANG", "").strip() or None), tables)


def activate(lang=None, tables=None):
    """进程级激活语言包（入口调一次）。返回生效的语言（None = null 包）。

    与 `bind()` 的区别：`bind` 是**作用域**（进出即还原，给需要隔离的场景）；
    `activate` 是**进程默认**（CLI 入口用，一次到位，不用每处写 `with`）。

    `tables=` 与 `bind` 同义：**注入内存表 ⇒ 零文件 I/O**（自证专用）。
    """
    resolved = lang if lang is not None else \
        (os.environ.get("REFLECT_LANG", "").strip() or None)
    _ACTIVE[0] = (resolved, _table_for(resolved, tables))
    return resolved


def active_lang():
    """当前生效的语言（None = null 包）。"""
    return _ACTIVE[0][0]


def render_msg(msg):
    """按**当前**语言重新渲染一条消息（`Message` 的 str 值可能是旧语言下渲的）。"""
    return _render(msg.code, msg.params, _ACTIVE[0][1])


def tr(code, **params):
    """便捷：直接拿当前语言的字符串（给不走 `Message` 的输出点用）。"""
    return _render(code, params, _ACTIVE[0][1])


# ── 自证 ──────────────────────────────────────────────────────────────────────
def after_activate(lang, code, params, expect, tables=None):
    """自证帮手：activate(lang, tables=…) 后 M() 是否按该包渲染（用完还原）。"""
    prev = _ACTIVE[0]
    try:
        activate(lang, tables)
        return str(M(code, **params)) == expect
    finally:
        _ACTIVE[0] = prev


def _raises(fn):
    """这条调用必须抛 MissingPack（反向断言用）。"""
    try:
        fn()
    except (MissingPack, SystemExit):
        return True
    return False


def _cases():
    fake = {
        "replay.no_cmd": "`%(k)s` has no replay command",
        "replay.mismatch": "`%(k)s` replay != ledger: %(got)s vs %(want)s",
    }
    bad_shape = {"ok": "OFF: not configured"}          # 伪装成机器行
    empty = {}

    def with_en(fn):
        """在 en 语言包下跑 fn（`bind` 是上下文管理器）。"""
        b = bind("en", {"en": fake})
        b.__enter__()
        try:
            return fn()
        finally:
            b.__exit__(None, None, None)

    return [
        # ① 正常不报 —— null 包（无语言包）形状
        ("i18n.null_no_params", lambda: str(M("gate.off.body")) == "gate.off.body"),
        ("i18n.null_with_params",
         lambda: str(M("replay.no_cmd", k="py_lines")) == "replay.no_cmd(k='py_lines')"),
        ("i18n.null_params_sorted",
         lambda: str(M("x", bb=2, aa=1)) == "x(aa=1, bb=2)"),
        ("★ i18n.repr_quotes",
         lambda: (lambda s: s.count("'") >= 2 and s.startswith("x(command="))(
             str(M("x", command="find . -name '*.md' | wc -l")))),
        ("i18n.null_long_value_truncated",
         lambda: (lambda m: len(m) < 80)(str(M("x", cmd="f" * 200)))),
        ("i18n.pack_applied",
         lambda: with_en(lambda: str(M("replay.no_cmd", k="f.py"))
                         == "`f.py` has no replay command")),
        ("i18n.message_is_str",
         lambda: (lambda m: (bool([m]), "  · " + m, len([m]))[0] is True)(M("a"))),
        ("i18n.code_readable",
         lambda: M("replay.no_cmd", k=1).code == "replay.no_cmd"),
        ("i18n.params_readable",
         lambda: M("replay.no_cmd", k="py_lines").params == {"k": "py_lines"}),
        ("i18n.activate_sets_default",
         lambda: after_activate("en", "replay.no_cmd", dict(k="f.py"),
                                "`f.py` has no replay command",
                                {"en": fake})),
        # ② 该报的必须报
        ("★ i18n.pack_empty",
         lambda: _raises(lambda: _validate(empty, "xx"))),
        ("★ i18n.pack_masquerades_contract",
         lambda: _raises(lambda: _validate(bad_shape, "xx"))),
        # ③ 空输入必须报
        ("★ i18n.empty_code",
         lambda: str(M("")) == ""),
    ]


def _selftest():
    import sys                                           # noqa: PLC0415
    from gate import main_selftest_or                    # noqa: PLC0415

    def _run(argv):
        print("i18n 是模块（被各闸门与平台模块消费）；--selftest 看自证。",
              file=sys.stderr)
        return 2
    return main_selftest_or(sys.argv[1:],
                            "i18n（本体零语言 + 语言包可选）", _cases, _run)


from gate import module_meta                             # noqa: E402

MODULE = module_meta("i18n", "本体零语言 + 语言包可选（Message/M/bind/activate）",
                     selftest=True)

if __name__ == "__main__":
    import sys                                           # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(_selftest())
