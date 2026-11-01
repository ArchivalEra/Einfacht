#!/usr/bin/env python3
"""旋钮登记（REFLECT_* 的**唯一名册**）：一处登记，处处派生。

「旋钮」这个概念此前没有 module：读取散在各闸门、声明活在 docstring 文字里、
判据数据在 check_envfile 的 FILE_KNOBS、名册靠扫全部文本 —— 扫描器明说
「文档字符串里的提及也算」，于是 REFLECT_AB / REFLECT_PINS 这类只写在
文档里的**幻影旋钮**进了名册、通过了 typo 检查，而用户真的 export 它们时
**静默无效**（Phase 0 已把它们实现化）。三个 module 各持一份互相不一致的
「旋钮是什么」—— 这正是浅 seam 的病。

本 module 收拢成一个 interface：**登记即存在**。名字、种类、默认值、
一句话语义，全部登记式；check_envfile 的判据从这里读；扫描面里出现而
登记表里没有的 REFLECT_* 记号 = 幻影 / typo ⇒ 报（docstring 提名不算数，
登记才算数）；三语 README 里出现的 REFLECT_* 名字 ⊆ 登记（反向断言，
envfile 的自证执行）。

种类（kind）—— envfile 按它决定要不要查存在性：

  file    值是相对仓库根的文件名（存在性要查；空默认 = 未配即未启用）
  list    逗号分隔的文件名清单（逐个查）
  dir     值是相对仓库根的目录名
  number  数字（秒 / 天 / 阈值；空默认 = 该规则明说未启用）
  flag    枚举开关（如 off）
  value   任意字符串（覆盖 / 名字 / 编号清单）

⚠️ 名册纪律：**只登记真的被 `os.environ.get` 读的旋钮**。给「将来可能用」
的名字留位子 = 自己制造幻影 —— 幻影旋钮的形状教训：文档承诺了、代码不读、
用户配了静默无效。这里连举例都不写具体未登记的名字（扫描对账会把例子
当幻影报出来 —— 对账不看上下文，这正是它的强度）。
"""
from __future__ import annotations

import os
import re
import sys

import gate                                            # noqa: E402
from gate import module_meta                          # noqa: E402
from i18n import M, bind, load_pack, pack_dir, NULL                # noqa: E402

class _Semantic(str):
    """旋钮的一行语义（`REGISTRY` 第三项）：**延迟渲染**的用户可见文本。

    `REGISTRY` 在 import 时构造，而语言包在入口 `main_selftest_or` 里才
    `activate()` —— 若这里直接 `M(...)`，值会在构造时就渲染并**永远停在
    null 包**上（实测形状：zh 用户看到的是 code 而不是语义）。所以保存 code，
    `__str__` 时按**当前**语言重渲（消费方只用 `%(entry)s` 格式化它，
    见 check_envfile 的 file_missing / dir_missing 消息）。
    """

    __slots__ = ("code",)

    def __new__(cls, code):
        obj = str.__new__(cls, code)
        obj.code = code
        return obj

    def __str__(self):
        return str(M(self.code))


# 名字 → (kind, 默认值, 一句话语义)。默认值 = 旋钮未配时各消费方的回落名。
# 语义按本体零语言（issue #26）：code 进语言包，本体不写自然语言。
REGISTRY = {
    "REFLECT_FACTS": ("file", "FACTS.json",
                      _Semantic("knobs.sem.reflect_facts")),
    "REFLECT_DOC": ("file", "STATE.md",
                    _Semantic("knobs.sem.reflect_doc")),
    "REFLECT_DOCS": ("list", "STATE.md,AGENTS.md,README.md,README.zh.md,README.de.md",
                     _Semantic("knobs.sem.reflect_docs")),
    "REFLECT_HISTORY_SECS": ("value", "",
                             _Semantic("knobs.sem.reflect_history_secs")),
    "REFLECT_RETIRED": ("value", "",
                        _Semantic("knobs.sem.reflect_retired")),
    "REFLECT_NAKED_MIN": ("number", "100",
                          _Semantic("knobs.sem.reflect_naked_min")),
    "REFLECT_STALE_DAYS": ("number", "",
                           _Semantic("knobs.sem.reflect_stale_days")),
    "REFLECT_REPLAY": ("flag", "",
                       _Semantic("knobs.sem.reflect_replay")),
    "REFLECT_REPLAY_TIMEOUT": ("number", "10",
                               _Semantic("knobs.sem.reflect_replay_timeout")),
    "REFLECT_READMES": ("list", "README.md,README.zh.md,README.de.md",
                        _Semantic("knobs.sem.reflect_readmes")),
    "REFLECT_RETRACTIONS": ("file", "retractions.json",
                            _Semantic("knobs.sem.reflect_retractions")),
    "REFLECT_QUESTIONS": ("dir", "questions",
                          _Semantic("knobs.sem.reflect_questions")),
    "REFLECT_ENV_FILE": ("value", "Einfacht.env",
                         _Semantic("knobs.sem.reflect_env_file")),
    "REFLECT_ENV_HINT": ("flag", "",
                         _Semantic("knobs.sem.reflect_env_hint")),
    "REFLECT_INVARIANTS": ("file", "",
                           _Semantic("knobs.sem.reflect_invariants")),
    "REFLECT_INSTRUMENTS": ("file", "",
                            _Semantic("knobs.sem.reflect_instruments")),
    "REFLECT_INSTRUMENT_DAYS": ("number", "",
                                _Semantic("knobs.sem.reflect_instrument_days")),
    "REFLECT_DOCTOR": ("file", "doctor.json",
                       _Semantic("knobs.sem.reflect_doctor")),
    "REFLECT_DOCTOR_TIMEOUT": ("number", "2",
                               _Semantic("knobs.sem.reflect_doctor_timeout")),
    "REFLECT_WORLD": ("file", "world.json",
                      _Semantic("knobs.sem.reflect_world")),
    "REFLECT_WORLD_LINE": ("value", "",
                           _Semantic("knobs.sem.reflect_world_line")),
    "REFLECT_AB": ("file", "ab.json",
                   _Semantic("knobs.sem.reflect_ab")),
    "REFLECT_PINS": ("file", "pins.json",
                     _Semantic("knobs.sem.reflect_pins")),
    "REFLECT_LOCKS": ("file", "upstream-lock.json",
                      _Semantic("knobs.sem.reflect_locks")),
    "REFLECT_MEASURE_MODULE": ("value", "",
                               _Semantic("knobs.sem.reflect_measure_module")),
    "REFLECT_PHASES": ("value", "",
                       _Semantic("knobs.sem.reflect_phases")),
    "REFLECT_LANG": ("value", "",
                     _Semantic("knobs.sem.reflect_lang")),
    "REFLECT_I18N": ("dir", "",
                     _Semantic("knobs.sem.reflect_i18n")),
    "REFLECT_I18N_ROOT": ("dir", "",
                          _Semantic("knobs.sem.reflect_i18n_root")),
}

KINDS = ("file", "list", "dir", "number", "flag", "value")

# 占位符记号（`%(name)s`）—— 自证对账 zh / en 的占位符名是否一致。
_PLACEHOLDER_RE = re.compile(r"%\((\w+)\)")

# 旋钮记号：REFLECT_ + 大写。**左边界必需** —— 不加时，翻案示例文本
# （`ZCODE_` 前缀 + 一个记号）会被从中间切成假记号，三语 README 对账
# 各报一次假阳性（实测踩到）。⚠️ 本文件里**不写出**那个假记号字面量。
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])REFLECT_[A-Z0-9_]+")


def kinds_of(name):
    """旋钮的种类（未登记 ⇒ None —— 调用方该报幻影 / typo）。"""
    entry = REGISTRY.get(name)
    return entry[0] if entry else None


def scan_surface_problems(py_dir=None):
    """扫描面（zreflect/*.py）里出现、登记表里没有的 REFLECT_* 记号。

    **名册自洽性**，与任何载体（Einfacht.env）是否存在无关 —— 它属于
    「名册」本身（C3）：此前这条判据焊在 check_envfile.run() 的
    「载体存在」前置之后，本仓没有 Einfacht.env ⇒ 幻影守卫从未执行
    （实测踩到）。`py_dir` 可注入（自证用假源码树）。
    """
    d = py_dir if py_dir is not None else _zdir()
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    toks = set()
    for n in names:
        if not n.endswith(".py"):
            continue
        try:
            toks.update(_TOKEN_RE.findall(
                open(os.path.join(d, n), encoding="utf-8",
                     errors="replace").read()))
        except OSError:
            continue
    for tok in sorted(toks):
        if tok not in REGISTRY:
            out.append(M("knobs.phantom_token", token=tok))
    return out


def readme_problems(files=None, readmes=None):
    """三语 README（REFLECT_READMES 名单）里出现、登记表里没有的 REFLECT_*
    名字（文档侧幻影防御）。`files` 可注入假文件系统（自证用）。"""
    out = []
    names = readmes if readmes is not None else [
        s.strip() for s in os.environ.get(
            "REFLECT_READMES",
            "README.md,README.zh.md,README.de.md").split(",") if s.strip()]
    for name in names:
        if files is not None:
            if name not in files:
                continue
            text = files[name]
        else:
            p = os.path.join(gate.GATE_REPO, name)
            if not os.path.exists(p):
                continue
            text = open(p, encoding="utf-8", errors="replace").read()
        for tok in sorted(set(_TOKEN_RE.findall(text))):
            if tok not in REGISTRY:
                out.append(M("knobs.readme_phantom", file=name, token=tok))
    return out


def _zdir():
    return os.path.dirname(os.path.abspath(__file__))


def declared_vs_read_problems(gates):
    """C4 对账①：闸门**声明**消费的旋钮 ⊆ 它**实际读**的旋钮。

    声明在 `GATE = meta(…, knobs=(…))`，实读在源码里的
    `os.environ.get("REFLECT_…")`（旋钮名一定以字面量出现在源码某处 ——
    否则它读不到那个环境变量）。两者此前无任何比较 —— AUTO:GATES 表
    可能列着闸门根本不读的旋钮（声明与实现不符，静默）。
    `gates` = registry.gates() 的结果（含 file / knobs）。
    """
    out = []
    for g in gates:
        declared = set(g.get("knobs") or ())
        if not declared:
            continue
        try:
            text = open(os.path.join(gate.GATE_REPO, g["file"]), encoding="utf-8",
                        errors="replace").read()
        except OSError:
            continue
        read = set(_TOKEN_RE.findall(text))
        ghost = sorted(k for k in declared if k not in read)
        if ghost:
            out.append(M("knobs.declared_not_read",
                         file=g["file"], knobs=", ".join(ghost)))
    return out


def registry_vs_readme_problems(readmes=None, tables=None):
    """C4 对账②：登记表里的旋钮 ⊆ 三语 README 配置表。

    `knobs.REGISTRY` 与三语 README 的配置表是两份「旋钮清单」，此前只查
    单向（README ⊆ REGISTRY，见 readme_problems）。这条查反向：登记了的
    旋钮必须在三语 README 里都有配置行 —— 否则新旋钮登记了却没人知道
    怎么配（文档缺口，静默）。`tables` 可注入（自证用假 README）。
    """
    row = re.compile(r"\|\s*`(REFLECT_[A-Z0-9_]+)`\s*\|")
    out = []
    names = readmes if readmes is not None else [
        s.strip() for s in os.environ.get(
            "REFLECT_READMES",
            "README.md,README.zh.md,README.de.md").split(",") if s.strip()]
    for name in names:
        if tables is not None:
            if name not in tables:
                continue
            text = tables[name]
        else:
            p = os.path.join(gate.GATE_REPO, name)
            if not os.path.exists(p):
                continue
            text = open(p, encoding="utf-8", errors="replace").read()
        have = set(row.findall(text))
        if not have:
            continue                    # 非配置表形态：不误报
        missing = sorted(k for k in REGISTRY if k not in have)
        if missing:
            out.append(M("knobs.readme_missing_rows",
                         file=name, knobs=", ".join(missing)))
    return out


# ── 自证：名册自身的形状守卫（登记表坏 = 所有消费方的判据数据坏）──────────────

def _semantic_packs_intact(langs=None):
    """**每个已装的语言包**都必须含全部旋钮语义，占位符名与基准侧一致，
    且在它自己的包下真渲染出句子（不是回落的裸 code）。

    这是 `_Semantic` 延迟渲染的**可证伪**证据：语义从本体搬到包里若掉了条目，
    这里当场红（而不是等人看见 `knobs.sem.reflect_facts` 这种裸 code）。

    `langs=None` ⇒ 用 `installed_langs()`（与对账器同一发现口径）。
    ⚠️ 此前硬写 `zh` / `en` 两个：下游仓只装一个包（**正是产品的主场景**：
    「从一堆包里挑一个」）时这条自证直接红（实测：只有 zh 的包目录
    ⇒ 16 PASS / 1 FAIL），产品没问题，是判据过窄。
    """
    langs = installed_langs() if langs is None else list(langs)
    codes = [w.code for _k, _d, w in REGISTRY.values()
             if isinstance(w, _Semantic)]
    if not codes:
        return False                        # 语义全没了 = 名册坏，不许绿
    tables = {}
    for lang in langs:
        try:
            tables[lang] = load_pack(lang)
        except Exception:                                # noqa: BLE001
            return False            # 坏包 ⇒ 语义完整性无从证明，不许绿
    # 零值守卫：一个包都没装 ⇒ 不是「完整」，是没装
    if not tables or not any(tables.values()):
        return False
    # ① 每个包都必须含**全部**语义 code（条目掉了 ⇒ 那边用户看到裸 code）。
    for lang in sorted(tables):
        if any(c not in tables[lang] for c in codes):
            return False
    # ② 占位符名一致性**走同一个对账器**（与 `pack_sync_problems` 同一份判据：
    # 两处各写一遍循环，规则就会漂 —— C4）。
    if pack_sync_problems(langs=sorted(tables),
                          loader=lambda l: tables[l]):
        return False
    # 每个包里都真渲染出句子（不是回落成 code）
    for lang in sorted(tables):
        with bind(lang, {lang: tables[lang]}):
            if any(str(w) == w.code for _k, _d, w in REGISTRY.values()
                   if isinstance(w, _Semantic)):
                return False
    return True


def _discovery_sees_planted_lang():
    """往真包目录里种一个半残的语言，默认 discovery 必须看得见它。

    用临时 `REFLECT_I18N`（只含 zh + 种下的 de）—— 不碰真仓的 lang/。
    """
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    import json                                          # noqa: PLC0415
    # 基准包用**第一个已装的**，不写死 zh：只装一个包（产品主场景）时，
    # 写死 zh 会让这条自证假红（实测 en-only ⇒ 16 PASS / 1 FAIL）。
    base = a_pack_lang()
    if not base:
        # 零包是**合法态**（用户要的零语言默认）⇒ 没有基准包可种，这条的
        # 条件真空成立。真仓永远有包，所以这条在真环境里必然真考。
        return True
    zh = load_pack(base)
    if not zh:
        return False
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, base), exist_ok=True)
        with open(os.path.join(d, base, "all.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(zh, fh, ensure_ascii=False)
        # 种一个**半残**的 de：只有一半的键 —— 不发现它就会漏判
        os.makedirs(os.path.join(d, "de"), exist_ok=True)
        half = dict(list(zh.items())[: len(zh) // 2])
        with open(os.path.join(d, "de", "all.json"), "w", encoding="utf-8") as fh:
            json.dump(half, fh, ensure_ascii=False)
        prev = os.environ.get("REFLECT_I18N")
        os.environ["REFLECT_I18N"] = d
        try:
            got = installed_langs()
            probs = pack_sync_problems()       # 默认 discovery
            return "de" in got and probs != []
        finally:
            if prev is None:
                os.environ.pop("REFLECT_I18N", None)
            else:
                os.environ["REFLECT_I18N"] = prev
    finally:
        shutil.rmtree(d, True)


def installed_langs():
    """语言包目录里实际装了哪些语言（**发现式**，不写名单）。

    C4「手写名录一定会漂」在这里同样成立：此前 `langs=("zh", "en")` 是写死的，
    于是往 `zreflect/lang/` 里加一个 `de/`（半装、缺键）时对账器**完全不看它**
    ——「装了但没对账」正是本仓要消灭的那类静默。现在是扫目录。

    **判据不是「有那个目录」，而是「那里真有 .json 包文件」**：早先按目录名
    收，目录里随便放个 `straynotes/` 或一个 `extra.json` 也会被当成语言，
    凭空报出「缺键」并让 roster 红（实测）。语言包的判据是「有包文件」。
    """
    base = pack_dir()
    out = set()
    try:
        for n in sorted(os.listdir(base)):
            p = os.path.join(base, n)
            if os.path.isdir(p):
                if any(x.endswith(".json") for x in os.listdir(p)):
                    out.add(n)
            elif n.endswith(".json"):
                out.add(n[:-len(".json")])
    except OSError as e:
        # ⚠️ **不许编 0**（AGENTS 纪律 7：读不到就明说，绝不编造）。此前这里
        # `return []`，于是「权限坏掉 / 目录读不了」与「一个包都没装」塌缩成
        # 同一个假值 ⇒ 对账器全绿、roster 全绿 —— 那是「部署了 ≠ 在跑」家族
        # 里最坏的一种（实测：chmod 000 的包目录，pack_sync_problems() == []）。
        raise PacksUnreadable(str(e))
    return sorted(out)


class PacksUnreadable(RuntimeError):
    """包目录本身读不了（权限 / I-O）。**区分于「没装包」**：后者合法，前者是事故。"""



def a_pack_lang():
    """取一个**已装**的语言包名（自证「读真包」类判据用）；一个都没装 ⇒ None。

    这些判据验的是「渲染保真」（消息模板里占位符对不对、句子还在不在），
    **语言是谁不重要** —— 所以不能写死 `zh`。下游仓只装一个包是产品主场景
    （「从一堆包里挑一个」），写死 zh 会让 `REFLECT_I18N=<只有en>` 的自证假红。
    """
    langs = installed_langs()
    return langs[0] if langs else None


_CODE_RE = re.compile(r'M\("([a-z][a-z0-9_.]+)"')
# `_Semantic(...)` 产的也是用户可见消息（延迟渲染），一并计入。
_SEM_RE = re.compile(r'_Semantic\("([a-z][a-z0-9_.]+)"')

# 自证 / 文档专用的 code：它们**从不**渲染给用户（只出现在 `--selftest`
# 的断言里，或作为 docstring 的示例）。用**显式前缀**声明，而不是手写名录 ——
# 新增这类 code 只要用这个前缀即可（发现式，不漂）。
_SELFTEST_CODE_PREFIXES = ("probe.", "gate.off.body")


def used_codes(py_dir=None):
    """本体源码里**实际会发给用户**的消息 code（`M("…")` / `_Semantic("…")`）。

    **发现式**：扫源码，不写名录。这是「包完整性」判据的参照面 —— 没有它，
    「两个包同时缺同一条」会全绿（zh↔en 的差集比较看不见共缺）。

    **剥 docstring**：文档里的示例（`M(…)` 形态）不是输出，不剥会把文档
    示例当真消息（实测踩到假阳性）。
    `_SELFTEST_CODE_PREFIXES` 里的前缀是自证专用 code（同样不发给用户）。
    """
    import ast                                           # noqa: PLC0415
    d = py_dir if py_dir is not None else _zdir()
    out = set()
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return set()
    for n in names:
        if not n.endswith(".py"):
            continue
        try:
            src = open(os.path.join(d, n), encoding="utf-8",
                       errors="replace").read()
        except OSError:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        # docstring 常量（豁免：示例不是输出）
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docs.add(doc)
        text_wanted = argparse_strip(src, docs)
        out |= set(_CODE_RE.findall(text_wanted))
        out |= set(_SEM_RE.findall(text_wanted))
    return {c for c in out
            if not any(c.startswith(p) for p in _SELFTEST_CODE_PREFIXES)}


def argparse_strip(src, docs):
    """把 docstring 正文从源码里抹掉（只做粗粒度替换，够用于扫面）。"""
    for doc in docs:
        if doc:
            src = src.replace(doc, "")
    return src


def _unreadable_dir_is_loud():
    """包目录读不了 ⇒ 必须报 `pack_unreadable`，不许当「零包」（合法态）。"""
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    if os.geteuid() == 0:
        return True        # root 无视权限位，这条测不出来（明说不适用）
    d = tempfile.mkdtemp()
    try:
        os.chmod(d, 0)
        prev = os.environ.get("REFLECT_I18N")
        os.environ["REFLECT_I18N"] = d
        try:
            try:
                installed_langs()
            except PacksUnreadable:
                return True
            return False
        finally:
            if prev is None:
                os.environ.pop("REFLECT_I18N", None)
            else:
                os.environ["REFLECT_I18N"] = prev
    finally:
        os.chmod(d, 0o755)
        shutil.rmtree(d, True)


def pack_coverage_problems(codes=None, langs=None, loader=None, discovery=None):
    """C4 对账④：**源码用到的每个 code 都必须在每个已装包里**。

    zh↔en 的差集比较（`pack_sync_problems`）看不见「两边一起缺」——
    实测：从 zh 和 en 同时删掉 `locks.ok`，`pack_sync_problems()` 返回 `[]`，
    而 `REFLECT_LANG=zh` 的用户在屏幕上看到 `locks.ok(count=3)`（裸 code），
    退出码正常。那是**本仓立身的静默退化**，是 C4 的经典失效模式
    （「两份必须一致」只保证一致，不保证完整）。

    参照面是**源码**（`used_codes()`），不是另一个包 —— 这样两个包一起漂
    也照样被抓。零包是合法态 ⇒ 无包可查，返回空。
    """
    load = loader if loader is not None else load_pack
    codes = used_codes() if codes is None else set(codes)
    if langs is None:
        try:
            langs = installed_langs()
        except PacksUnreadable as e:
            return [M("knobs.pack_unreadable", lang="*", error=e)]
    langs = list(langs)
    if not codes or not langs:
        return []                       # 零包 / 零 code：没有可比的两侧
    out = []
    for lang in sorted(langs):
        try:
            table = load(lang)
        except Exception as e:                           # noqa: BLE001
            return [M("knobs.pack_unreadable", lang=lang, error=e)]
        missing = sorted(codes - set(table))
        if missing:
            out.append(M("knobs.pack_missing_code",
                         lang=lang, count=len(missing),
                         codes=", ".join(missing[:8])))
    return out


def pack_sync_problems(langs=None, loader=None, discovery=None):
    """C4 对账③：各语言包的**键集**与**占位符名**必须一致。

    此前无任何东西强制这件事 —— 手工把一条 code 加进 zh 却忘了 en，
    `REFLECT_LANG=en` 的用户就静默看到裸 code（本仓立身要消灭的静默退化）。
    实测现状两份是相等的，但「相等」是运气不是判据。

    `langs=None` ⇒ 用 `discovery()` 发现（默认 `installed_langs()`）。
    `discovery` 可注入，**好让自证真的考 discovery** —— 此前那条用例显式传
    `langs=(…)`，把发现整个绕开了：把 discovery 换回手写名单，自证照样绿
    （实测）。断言没覆盖它声称保护的东西。
    `loader` 可注入（自证用假包）；默认走 `i18n.load_pack`（**合并视图**，
    与真装载器看同一张表 —— 只读单个分片会与装载器分叉）。
    """
    load = loader if loader is not None else load_pack
    if langs is None:
        try:
            langs = (discovery or installed_langs)()
        except PacksUnreadable as e:
            return [M("knobs.pack_unreadable", lang="*", error=e)]
    langs = list(langs)
    tables = {}
    for lang in langs:
        try:
            tables[lang] = load(lang)
        except Exception as e:                           # noqa: BLE001
            # **这里必须捕获**：`load_pack` 对坏分片抛 `MissingPack`，
            # `pack_sync_problems` 又可能在 `activate_or_fatal()` **之外**被调用
            # （`registry --gates` 的 roster 对账就是），于是异常一路冒到顶层
            # 变成裸 traceback rc=1 —— 逃出本仓的 rc 契约（配置坏 = FATAL rc 2）。
            # 实测踩到：`REFLECT_LANG` 未设 + 坏分片 ⇒ rc=1 traceback，
            # 同一个输入加 `REFLECT_LANG=zh` 才是 rc=2。
            return [M("knobs.pack_unreadable", lang=lang, error=e)]
    out = []
    # **零包是合法态**（用户要的「本体没有任何语言表达也能用」）：一个包都没
    # 装 ⇒ 没有「彼此一致」可言，但也不是配置坏 —— 返回空（不报）。
    # 「设了包却读不到」由 `pack_unreadable` / 激活路径的 `i18n.pack_absent`
    # 负责，那是另一件事：**没要** vs **要了却没有**。
    if not tables:
        return []
    # 装了但全是空表 ⇒ 那是坏包（声称有目录却没有内容），报。
    if not any(tables.values()):
        return [M("knobs.pack_sync_empty", pack_dir=pack_dir())]
    ref_lang = sorted(tables)[0]
    ref = tables[ref_lang]
    for lang in sorted(tables):
        if lang == ref_lang:
            continue
        other = tables[lang]
        only_ref = sorted(set(ref) - set(other))
        only_other = sorted(set(other) - set(ref))
        if only_ref:
            out.append(M("knobs.pack_missing_keys",
                         lang=lang, reference=ref_lang,
                         keys=", ".join(only_ref[:8])))
        if only_other:
            out.append(M("knobs.pack_extra_keys",
                         lang=lang, reference=ref_lang,
                         keys=", ".join(only_other[:8])))
        # 占位符名一致：差一个 ⇒ 渲染时 KeyError（或更糟，静默少显示一段）
        for code in sorted(set(ref) & set(other)):
            a = sorted(_PLACEHOLDER_RE.findall(ref[code]))
            b = sorted(_PLACEHOLDER_RE.findall(other[code]))
            if a != b:
                # 参数名不能叫 `code`：`M(code, **params)` 的首参就叫 code，
                # 同名 kwarg 会 `TypeError: M() got multiple values`（实测踩到）。
                out.append(M("knobs.pack_placeholder_mismatch",
                             lang=lang, key=code,
                             reference_lang=ref_lang,
                             expected_params=", ".join(a) or "-",
                             actual_params=", ".join(b) or "-"))
    return out


def null_pack():
    """一个**显式 null 包**的 context manager（自证专用）。

    自证里的形状判据（「没装包时应该是 code」）必须自带 null 作用域：入口
    `activate()` 会把 `REFLECT_LANG` 设成 zh/en，断言若不自带作用域，就变成
    「跑在什么环境就考什么」—— 实测 `REFLECT_LANG=zh gates-selftest.sh` 下
    这类用例全红。
    """
    return bind(NULL, {})


def _semantics_are_codes_under(cm):
    """在 `cm` 语言包作用域下，每条旋钮语义都渲染成 code（且非空）。"""
    sem = [(k, w) for k, _d, w in REGISTRY.values()
           if isinstance(w, _Semantic)]
    if not sem:
        return False                        # 零值守卫：语义全没了 ⇒ 名册坏
    cm.__enter__()
    try:
        return all(str(w) == w.code for _k, w in sem)
    finally:
        cm.__exit__(None, None, None)


def _cases():
    import atexit                                        # noqa: PLC0415
    import shutil                                        # noqa: PLC0415
    import tempfile                                      # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    open(os.path.join(d, "good.py"), "w").write(
        'X = os.environ.get("REFLECT_FACTS")\n')
    # 幻影记号用拼接构造：本文件在扫描面内（zreflect/*.py），字面量写出来
    # 会被自己的 scan_surface_problems() 收编（本仓老坑）。
    # 夹具（假源码 / 假 README）的正文用**英文** —— 它们是被扫描的输入，
    # 不是本体输出（同 facts.py 体例：中文夹具会被零语言闸门当消息）。
    phantom = "REFLECT_" + "GHOSTX"
    open(os.path.join(d, "phantom.py"), "w").write(
        '# a comment mentions the nonexistent knob ' + phantom + '\n')
    return [
        # ① 正常不报
        ("knobs.registry_entry_shape",
         lambda: all(k in KINDS and isinstance(dflt, str) and w.strip()
                     for k, dflt, w in REGISTRY.values()) and len(REGISTRY) >= 20),
        ("knobs.scan_clean",
         lambda: scan_surface_problems() == []),
        ("knobs.readme_nominations_registered",
         lambda: readme_problems(files={
             "README.md": "uses REFLECT_FACTS and REFLECT_DOC.",
             "README.zh.md": "x", "README.de.md": "x"}) == []),
        ("knobs.real_tree_scan_clean", lambda: scan_surface_problems() == []),
        ("knobs.real_readmes_clean", lambda: readme_problems() == []),
        ("knobs.semantic_renders_as_code_by_default",
         # 自带 **null 作用域**：这条测的是「没装包时是 code」，与入口激活了
         # 什么包无关。此前直接读 `str(w)`，`REFLECT_LANG=zh` 下渲染成句子
         # 于是全红（实测）—— 断言没声明作用域 = 跑在什么环境就考什么。
         lambda: _semantics_are_codes_under(null_pack())),
        # 语义延迟渲染的**正向证据**：真 zh 包里每条语义都有条目，且在 zh 包
        # 下渲染出的是那句话（不是 code）。读磁盘真包 = 证明迁移没丢语义
        # （注入假表只能证明「我写的模板渲染出我写的字」—— 循环论证）。
        # 复跑：REFLECT_LANG=zh python3 zreflect/knobs.py --selftest
        ("knobs.semantics_present_in_real_packs",
         # 条件判据：**装了包就必须完整**。零包（合法态）⇒ 无对象可验，
         # 条件真空成立；装了坏包 ⇒ 这条照样红（已用 planted 包验证过）。
         lambda: not installed_langs() or _semantic_packs_intact()),
        # zh / en 键集与占位符名一致（C4 对账③）。真包绿 = 迁移没落一边；
        # 反向断言见 ② 档（假包必须报）。
        ("knobs.real_packs_in_sync",
         # 同上：零包合法 ⇒ 无「彼此」可对；有包就必须一致。
         lambda: not installed_langs() or pack_sync_problems() == []),
        # ② 该报的必须报
        ("★ knobs.phantom_token",
         lambda: any(p.code == "knobs.phantom_token"
                     and p.params.get("token") == phantom
                     for p in scan_surface_problems(py_dir=d))),
        ("★ knobs.readme_phantom",
         lambda: any(x.code == "knobs.readme_phantom" for x in readme_problems(files={
             "README.md": "see " + "REFLECT_" + "GHOSTY" + ".",
             "README.zh.md": "x", "README.de.md": "x"}))),
        # 对账器本身必须能红（否则它只是一条恒绿的装饰）
        ("★ knobs.pack_missing_keys",
         lambda: [p.code for p in pack_sync_problems(
             langs=("zh", "en"), loader=lambda l: {
             "zh": {"a": "x"}, "en": {"a": "x", "b": "y"}}[l])
         ] == ["knobs.pack_missing_keys"]),
        ("★ knobs.pack_placeholder_mismatch",
         lambda: [p.code for p in pack_sync_problems(
             langs=("zh", "en"), loader=lambda l: {
             "zh": {"a": "x %(k)s"}, "en": {"a": "x %(j)s"}}[l])
         ] == ["knobs.pack_placeholder_mismatch"]),
        # 多键方向也必须能报（此前只测了缺键 —— 「多出来一个键」同样会让
        # 另一侧的用户看到裸 code，是同一个洞的另一面）。
        # 参考侧是 `sorted(...)[0]`（这里 = "en"），所以「zh 多一个键」才走
        # extra_keys；反过来会被报成 en 缺键（同一个洞，两种措辞）。
        ("★ knobs.pack_extra_keys",
         lambda: [p.code for p in pack_sync_problems(
             langs=("zh", "en"), loader=lambda l: {
             "zh": {"a": "x", "b": "y"}, "en": {"a": "x"}}[l])
         ] == ["knobs.pack_extra_keys"]),
        # 发现式（不写名单）：磁盘上多装一个半残的包也必须被对账器看见。
        # 此前 `langs=("zh","en")` 写死 ⇒ 加一个缺键的 `de/` 时它**完全不看**
        # ——「装了但没对账」正是本仓要消灭的那类静默。
        # 发现式（不写名单）：必须**通过 discovery 通道**验，否则把
        # `installed_langs()` 换回手写 `("zh","en")` 时自证照样绿（实测）
        # —— 断言没覆盖它声称保护的东西（rule 4）。
        ("★ knobs.pack_sync_sees_every_installed_lang",
         # 走 **默认 discovery**（不传 `discovery=`）—— 传了就等于替被测
         # 对象把答案递过去（实测：那样即使把 installed_langs 换回手写
         # 名单，这条仍 PASS）。
         lambda: _discovery_sees_planted_lang()),
        # ④ **包完整性**（C4 对账④）：源码用到的 code 必须在每个已装包里。
        # 这条抓的是「两边一起缺」——此前 `pack_sync_problems` 只比差集，
        # 双向共缺会全绿，用户看到裸 code（实测：两包同删 locks.ok ⇒ 全绿）。
        ("knobs.coverage_real_repo_clean",
         lambda: pack_coverage_problems() == []),
        ("★ knobs.pack_missing_code",
         lambda: [p.code for p in pack_coverage_problems(
             codes={"a.b", "c.d"}, langs=("zh", "en"),
             loader=lambda l: ({"a.b": "x", "c.d": "y"} if l == "en"
                               else {"a.b": "x"}))
         ] == ["knobs.pack_missing_code"]),
        # **不可读目录 ≠ 没装包**（AGENTS 纪律 7：读不到就明说，绝不编 0）。
        # 此前 `installed_langs()` 在 OSError 时 return []，于是权限坏掉
        # 与「零包」塌缩成同一个假值 ⇒ 对账全绿（实测 chmod 000 ⇒ []）。
        ("★ knobs.pack_unreadable_on_oserror",
         lambda: _unreadable_dir_is_loud()),
        # ③ 空输入必须报
        ("★ knobs.pack_sync_empty",
         lambda: [p.code for p in pack_sync_problems(
             langs=("zh", "en"), loader=lambda l: {})]
         == ["knobs.pack_sync_empty"]),
        ("★ knobs.registry_empty", lambda: bool(REGISTRY)),
        ("knobs.phases_registered", lambda: "REFLECT_PHASES" in REGISTRY),
    ]


MODULE = module_meta("旋钮登记", "REFLECT_* 的唯一名册 + 名册自洽性判据", selftest=True)


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from gate import main_selftest_or                    # noqa: PLC0415

    def _run(argv):
        print(M("knobs.module_only"), file=sys.stderr)
        return 2
    # 自证标题是**开发者界面**（check_i18n 的豁免面 ②），按设计保留一种语言。
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.knobs"),
                              _cases, _run))
