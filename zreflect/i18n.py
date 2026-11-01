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

# ── 语言包位置：**唯一解析点** ────────────────────────────────────────────────
# 曾经有 3～4 个产地（i18n._table_for / knobs._real_pack / check_facts /
# check_facts_replay），改口径时只修到其中两处 —— 另外两处继续用 GATE_REPO
# 相对，跨仓夹具里当场全红（实测：GATE_REPO=$(mktemp -d) 下 check_facts
# 17 PASS / 1 FAIL）。现在一律走 `pack_dir()` / `load_pack()`，别处只许调它们。
_TOOL_DIR = os.path.dirname(os.path.abspath(__file__))        # .../zreflect
_TOOL_REPO = os.path.dirname(_TOOL_DIR)                       # 承载套件的仓根
# 未设 `REFLECT_I18N` 时用的**内建包目录**（相对工具仓根）。设了就不是它了
# —— 见 `pack_dir()` 的三条口径，别再把它当「默认路径值」写进文档。
BUILTIN_PACKS = "zreflect/lang"

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

# `NULL` 哨兵的定义在 `bind()` 附近（与 `activate` 共用，只有一个）。

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


def pack_dir():
    """语言包目录的绝对路径 —— **全仓唯一的解析点**。

    三条口径（每条都是踩过的坑，别简化）：

      · **未设 `REFLECT_I18N`** ⇒ 用套件自带的内建包 `BUILTIN_PACKS`，锚在
        **工具仓根**。这是「拉了套件就能用」的那个场景：语言包随工具走。
        也因此跨仓夹具（`GATE_REPO=$(mktemp -d)`）能正常装载 —— 实测踩到过：
        锚成 GATE_REPO 相对时，夹具里每个闸门都 MissingPack（0/15 全红）。
        语言包是**工具**的属性，不是被检查仓库的。
      · **设了相对路径** ⇒ 相对**被检查仓根**（`GATE_REPO`）。与 `REFLECT_DOCS`
        等所有名字型旋钮同一口径 —— env 里写的「相对仓库根的名字」才对得上。
        ⚠️ 这条此前**没落地**：代码 join 到 `_TOOL_REPO`，而三语 README 与本文
        都说「相对被检查仓根」。实测：`GATE_REPO=$T REFLECT_I18N=lang` 解析成
        `/…/Einfacht/lang` 而不是 `$T/lang` ⇒ FATAL。文档与代码不一致时，
        以「与其他旋钮同口径」为准（文档那条是对的）。
      · **设了绝对路径** ⇒ 原样用。

    注意「未设用工具、设了用被检查仓」不是矛盾：未设是「跟着套件走」（零配置
    可用的场景），设了是「我在自己的仓里放了一份」（与其他旋钮一致的语义）。
    """
    raw = os.environ.get("REFLECT_I18N", "").strip()
    if not raw:
        return os.path.join(_TOOL_REPO, BUILTIN_PACKS)
    if os.path.isabs(raw):
        return raw
    # 懒导入：本模块被 `gate` 懒导入，模块级反向 import 会成环。
    import gate                                          # noqa: PLC0415
    return os.path.join(gate.GATE_REPO, raw)


def load_pack(lang):
    """读语言包的**合并表**（dict）—— 与真装载器（`_table_for`）看到的那张表一致。

    两种形状都认，且**总是合并**：

      · `<lang>/*.json`  按命名空间分文件（并行开发用，后者覆盖同 code）
      · `<lang>.json`    单文件（小仓 / 样板）

    合并是必须的：真装载器就是合并的。任何只读某一个分片的读者都会与装载器
    分叉 —— 实测踩到：自证里按分片读，于是文档认可的单文件包被判红
    （10 PASS / 1 FAIL）。别处也不许再自己 `open(...json...)`（曾经四处产地
    各写各的，改口径只修到两处）。

    ⚠️ **坏 JSON 不许静默跳过**：此前每个分片 `except ...: continue`，于是
    一个坏掉的 `registry.json` 只让那部分 code 变成裸 code，**rc 仍 0** ——
    正是本仓立身要消灭的「半装的语言包看起来像装好了」（实测：写坏一个分片，
    装载仍成功、`registry.empty_phase` 打出裸 code、退出码 0）。现在坏分片
    直接抛 `MissingPack`，装配失败走 FATAL。

    缺失 / 空 ⇒ `{}`（不抛）：自证里「读真包」的断言靠空表当场红，比让整条
    自证崩掉更好定位。**真装载走 `_table_for`**，它才判「整包不在」。区分的是
    「没有」与「有但坏了」：后者是配置事故，必须响。
    """
    import json                                          # noqa: PLC0415
    base = pack_dir()
    table = {}
    d = os.path.join(base, lang)
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if not n.endswith(".json"):
                continue
            p = os.path.join(d, n)
            try:
                with open(p, encoding="utf-8") as fh:
                    part = json.load(fh)
            except (OSError, ValueError) as e:
                raise MissingPack("i18n.shard_unreadable", lang=lang,
                                   path=p, error=e) from e
            if not isinstance(part, dict):
                raise MissingPack("i18n.shard_not_object", lang=lang,
                                   name=n)
            table.update(part)
    single = os.path.join(base, "%s.json" % lang)
    if os.path.exists(single):
        try:
            with open(single, encoding="utf-8") as fh:
                part = json.load(fh)
        except (OSError, ValueError) as e:
            raise MissingPack("i18n.single_unreadable", lang=lang,
                               path=single, error=e) from e
        if not isinstance(part, dict):
            raise MissingPack("i18n.single_not_object", lang=lang,
                               path=single)
        table.update(part)
    return table


def _table_for(lang, tables):
    """解析语言包：注入的 tables 优先，其次磁盘（`pack_dir()`）。

    未装语言包 ⇒ `None`（走 null 包）。**不做 fallback** —— 半装的语言包
    不该让人看到中英混杂（本仓纪律：宁可明说未启用，不假装查过）。

    ⚠️ 注入的 tables **同样要过 `_validate`**：此前注入路径直接 `return got`，
    于是「空包不是已翻译」这条零值守卫**只在磁盘路径上成立** —— 自证里用
    注入表测它永远绿（实测踩到：`i18n.empty_pack_rejected` 在 null 模式红）。
    自证跑的是注入路径，守卫若只守在另一个路径上，等于没守。
    """
    if tables is not None:
        got = tables.get(lang) if lang else None
        if got is None and lang:
            raise MissingPack("i18n.injected_lang_absent", lang=lang)
        if got is not None:
            _validate(got, lang)
        return got
    if not lang:
        return None
    table = load_pack(lang)
    if not table:
        base = pack_dir()
        raise MissingPack("i18n.pack_absent", lang=lang,
                           single=os.path.join(base, "%s.json" % lang),
                           directory=os.path.join(base, lang))
    _validate(table, lang)
    return table


class MissingPack(Exception):
    """语言包装配问题（缺失 / 损坏 / 形状非法）。调用方转 FATAL rc 2。

    **携带 `(code, params)` 而不是拼好的句子**（issue #26 的硬要求：`REFLECT_LANG=en`
    时给用户看的任何东西都不许是中文）。包不可用 ⇒ 任何语言包都渲染不了 ⇒
    按 **null 包形状**输出 `code(params…)`，那是唯一诚实的表示。此前是中文
    散文，于是 `REFLECT_LANG=en` 的 FATAL 行里仍冒中文（实测）。

    `str(e)` 因此是**机器可读**的 code 形状；`e.code` / `e.params` 可用于
    判据（自证按 `.code` 断言，不按文案）。
    """

    def __init__(self, code, **params):
        self.code = code
        self.params = params
        super().__init__(_render(code, params, None))


def _validate(table, lang):
    """校验语言包形状：值不许伪装成机器行（契约结构上不可被翻译）。"""
    if not isinstance(table, dict) or not table:
        raise MissingPack("i18n.pack_empty", lang=lang)
    for code, value in table.items():
        if not isinstance(value, str):
            raise MissingPack("i18n.value_not_string", lang=lang, key=code)
        # 只判**行首**：契约串的危险是「伪装成整行」，不是正文里提到它。
        if any(s.match(value) for s in _CONTRACT_SHAPES):
            raise MissingPack("i18n.value_masquerades_contract", lang=lang,
                               key=code, value=value[:40])


class _Binding:
    """`bind()` 的上下文：装/卸语言包（可重入）。"""

    def __init__(self, lang, tables, forced_null=False):
        self.lang = lang
        self.tables = tables
        self.forced_null = forced_null
        self.prev = None

    def __enter__(self):
        self.prev = _ACTIVE[0]
        _ACTIVE[0] = (None, None) if self.forced_null \
            else (self.lang, _table_for(self.lang, self.tables))
        return self

    def __exit__(self, *exc):
        _ACTIVE[0] = self.prev
        return False


_ACTIVE = [(None, None)]           # (lang, table)


NULL = object()                   # 「显式要 null 包」的哨兵（区别于「没传」）


def bind(lang=None, tables=None):
    """装一个语言包（上下文管理器）。

    · `lang=NULL` ⇒ **显式 null 包**（不看环境变量 —— 自证用它把形状判据
      钉在「没装包」这一档上；否则 `REFLECT_LANG=zh` 下这些用例全红）。
    · `lang=None` ⇒ 没传，回落 `REFLECT_LANG`；都没有 ⇒ null 包。
    · 字符串 ⇒ 装那个包（不在 ⇒ `MissingPack`）。

    `tables={lang: {code: template}}` ⇒ 纯内存（**自证专用**：零文件 I/O）。
    """
    if lang is NULL:
        return _Binding(None, {}, forced_null=True)
    return _Binding(lang if lang is not None else
                    (os.environ.get("REFLECT_LANG", "").strip() or None), tables)


def activate(lang=None, tables=None):
    """进程级激活语言包（入口调一次）。返回生效的语言（None = null 包）。

    与 `bind()` 的区别：`bind` 是**作用域**（进出即还原，给需要隔离的场景）；
    `activate` 是**进程默认**（CLI 入口用，一次到位，不用每处写 `with`）。

    `lang=NULL` 与 `bind` 同义：**显式 null 包**（不吃 `REFLECT_LANG`）。
    ⚠️ 此前漏了这个分支：`activate(NULL)` 把哨兵当语言名去 `join`，
    直接 `TypeError`（实测）。两个入口的哨兵语义必须一样，否则调用方
    在 `bind`/`activate` 之间换一下就是个坑。

    `tables=` 与 `bind` 同义：**注入内存表 ⇒ 零文件 I/O**（自证专用）。
    """
    if lang is NULL:
        _ACTIVE[0] = (None, None)
        return None
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

    def scope(lang, tables, fn):
        """在指定语言包作用域下跑 fn（进出即还原，不污染别的用例）。

        `lang=NULL` ⇒ 显式 null 包（不吃 `REFLECT_LANG`）。
        """
        b = bind(lang, tables)
        b.__enter__()
        try:
            return fn()
        finally:
            b.__exit__(None, None, None)

    def with_en(fn):
        """在 en 语言包下跑 fn。"""
        return scope("en", {"en": fake}, fn)

    def with_null(fn):
        """在 **null 包**下跑 fn —— 断言测的是「无语言包」的形状，与调用环境无关。

        ⚠️ 此前这些用例直接 `M(...)`：入口 `activate()` 一旦把 zh / en 设上，
        它们就全红（实测 `REFLECT_LANG=zh gates-selftest.sh` 下 KeyError）——
        断言**没有声明自己的作用域**，于是成了「跑在什么环境就考什么」。形状
        判据必须自带 null 作用域，否则 zh 用户的自证永远是红的。
        """
        return scope(NULL, {}, fn)

    def said(**params):
        """在 null 包下渲染一条 M(...) 的文本。"""
        return with_null(lambda: str(M("probe.code", **params)))

    return [
        # ① 正常不报 —— null 包（无语言包）形状
        ("i18n.null_no_params",
         lambda: with_null(lambda: str(M("gate.off.body")) == "gate.off.body")),
        ("i18n.null_with_params",
         lambda: with_null(
             lambda: str(M("replay.no_cmd", k="py_lines"))
             == "replay.no_cmd(k='py_lines')")),
        ("i18n.null_params_sorted",
         lambda: with_null(lambda: str(M("x", bb=2, aa=1)) == "x(aa=1, bb=2)")),
        # `repr` 必须处理引号嵌套：值里带单引号时，手拼 `'%s'` 会产出畸形串。
        ("★ i18n.repr_quotes",
         lambda: (lambda s: s.count("'") >= 2 and s.startswith("probe.code("))(
             said(command="find . -name '*.md' | wc -l"))),
        ("i18n.null_long_value_truncated",
         lambda: len(said(cmd="f" * 200)) < 80),
        ("i18n.pack_applied",
         lambda: with_en(lambda: str(M("replay.no_cmd", k="f.py"))
                         == "`f.py` has no replay command")),
        ("i18n.message_is_str",
         lambda: (lambda m: (bool([m]), "  · " + m, len([m]))[0] is True)(M("a"))),
        # `.code` / `.params` 是身份，与语言无关 —— 不随激活变。但它们得在
        # null 包下构造：`Message` 是**构造时渲染**的，拿捏造的 code 去撞真
        # zh 包会 KeyError（实测 `REFLECT_LANG=zh` 下这两条红）。
        ("i18n.code_readable",
         lambda: with_null(lambda: M("replay.no_cmd", k=1).code
                           == "replay.no_cmd")),
        ("i18n.params_readable",
         lambda: with_null(lambda: M("replay.no_cmd", k="py_lines").params
                           == {"k": "py_lines"})),
        ("i18n.activate_sets_default",
         lambda: after_activate("en", "replay.no_cmd", dict(k="f.py"),
                                "`f.py` has no replay command",
                                {"en": fake})),
        # ② 该报的必须报
        ("★ i18n.pack_empty",
         lambda: _raises(lambda: _validate(empty, "xx"))),
        ("★ i18n.pack_masquerades_contract",
         lambda: _raises(lambda: _validate(bad_shape, "xx"))),
        # 缺失的语言包必须**报**，不是静默回落中文（`_table_for` 的反向证据）。
        ("★ i18n.missing_pack_raises",
         lambda: _raises(lambda: _table_for("xx", {"zh": {}}))),
        # 空包不是「已翻译」（零值守卫第一档）。
        ("★ i18n.empty_pack_rejected",
         lambda: _raises(lambda: _table_for("xx", {"xx": {}}))),
        # **坏分片必须当场抛**（本仓立身那条：半装的语言包不许看起来像装好了）。
        # 反向证据：造一个坏 JSON 的包目录，`load_pack` 必须抛而不是静默跳过 ——
        # 静默跳过的后果是那部分消息退回裸 code 而退出码仍是 0（实测踩到）。
        ("★ i18n.broken_shard_raises",
         lambda: _broken_pack_raises()),
        # **`pack_dir` 三条口径的机器判据**（它是最显眼的契约，此前零自证 ——
        # 「写而不跑」的形状）。未设 ⇒ 工具自带；绝对 ⇒ 原样；相对 ⇒ 被检查仓根。
        ("★ i18n.pack_dir_three_rules", lambda: _pack_dir_rules_ok()),
        # `activate(NULL)` 与 `bind(NULL)` 语义必须一致（此前 activate 把哨兵
        # 当语言名 join，直接 TypeError）。
        ("★ i18n.activate_accepts_null",
         lambda: _activate_null_ok()),
        # ③ 空输入必须报
        ("★ i18n.empty_code",
         lambda: with_null(lambda: str(M("")) == "")),
    ]
def _broken_pack_raises():
    """坏分片必须抛 `MissingPack`，不许静默跳过（自证用临时目录，用完即删）。"""
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, "xx"))
        with open(os.path.join(d, "xx", "bad.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{ not json")
        prev = os.environ.get("REFLECT_I18N")
        os.environ["REFLECT_I18N"] = d
        try:
            try:
                load_pack("xx")
            except MissingPack:
                return True
            return False           # 静默跳过 = 这条断言红
        finally:
            if prev is None:
                os.environ.pop("REFLECT_I18N", None)
            else:
                os.environ["REFLECT_I18N"] = prev
    finally:
        shutil.rmtree(d, True)


def _pack_dir_rules_ok():
    """`pack_dir()` 的三条口径逐条验（每条都是踩过的坑，别只验一条）。"""
    import gate                                          # noqa: PLC0415
    prev = os.environ.get("REFLECT_I18N")
    try:
        env = os.environ
        # ① 未设 ⇒ 工具自带的包目录（跨仓夹具靠它）
        env.pop("REFLECT_I18N", None)
        if not os.path.isdir(pack_dir()):
            return False
        # ② 绝对路径 ⇒ 原样（不拼任何前缀）
        probe = os.path.abspath(os.sep)
        env["REFLECT_I18N"] = probe
        if pack_dir() != probe:
            return False
        # ③ 相对路径 ⇒ **被检查仓根**（与其他名字型旋钮同口径）。
        #    这条曾经错 join 到工具仓根，实测 `GATE_REPO=$T REFLECT_I18N=lang`
        #    解析成 /…/Einfacht/lang ⇒ FATAL。
        #    ⚠️ 必须把两个仓根**真的分开**才能验：不设 GATE_REPO 时两者同值，
        #    错口径也能过（实测踩到：断言自称能红，换回旧实现仍 True）。
        env["REFLECT_I18N"] = "rel/probe"
        saved = gate.GATE_REPO
        gate.GATE_REPO = os.sep + "tmp-probe-repo"
        try:
            return pack_dir() == os.path.join(gate.GATE_REPO, "rel/probe")
        finally:
            gate.GATE_REPO = saved
    finally:
        if prev is None:
            os.environ.pop("REFLECT_I18N", None)
        else:
            os.environ["REFLECT_I18N"] = prev


def _activate_null_ok():
    """`activate(NULL)` 必须干净返回 None，并且真的落到 null 包。"""
    prev = _ACTIVE[0]
    try:
        got = activate(NULL)
        return got is None and _ACTIVE[0] == (None, None)
    finally:
        _ACTIVE[0] = prev


def _selftest():
    import sys                                           # noqa: PLC0415
    from gate import main_selftest_or                    # noqa: PLC0415

    def _run(argv):
        # 走 M()：`REFLECT_LANG=en` 下这条也必须说英语。此前是裸中文字面量，
        # 靠 `check_i18n` 的整文件豁免（本文件通篇是装包机制）遮住 ——
        # 豁免是对的（循环依赖），但**这条不是**循环依赖，它只是普通消息。
        print(M("i18n.module_banner"), file=sys.stderr)
        return 2
    return main_selftest_or(sys.argv[1:],
                            M("gate.title.i18n"), _cases, _run)


from gate import module_meta                             # noqa: E402

MODULE = module_meta("i18n", "本体零语言 + 语言包可选（Message/M/bind/activate）",
                     selftest=True)

if __name__ == "__main__":
    import sys                                           # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # ⚠️ 不能直接 `sys.exit(_selftest())`：本文件作为**脚本**运行时，这份代码是
    # `__main__`，而 `gate.activate_or_fatal` 里 `import i18n` 加载的是**另一个
    # 模块对象**（同名模块副本）。`_ACTIVE` 是模块级状态 ⇒ 激活设在副本上、
    # 渲染读 `__main__` 的 `_ACTIVE` ⇒ 永远 null 包（实测症状：`REFLECT_LANG=en
    # i18n.py` 打出裸 `i18n.module_banner`）。委派给模块副本，两边就是同一个对象。
    import i18n as _mod                                  # noqa: PLC0415
    sys.exit(_mod._selftest())
