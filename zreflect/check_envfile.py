#!/usr/bin/env python3
"""env 文件闸门（**可插拔模块**，issue #8）：守钩子的 REFLECT_* 载体。

钩子经可拔插件 einfacht-env.sh 加载 Einfacht.env
（默认名；REFLECT_ENV_FILE 可换）—— 那是 issue #8
的持久载体：钩子语境里「谁记得 export」不算数。
本闸门守这份载体的**静默坏法**，全是「部署了 ≠ 在跑」
家族：

  · 旋钮名打错一位 ⇒ 被所有程序静默忽略，值永远
    到不了钩子 —— 最危险的一种：一切照常跑；
  · 文件旋钮指向不存在的文件 ⇒ 钩子的 [ -f ] 守卫
    静默跳过，机器块从这一刻起悄悄过期；
  · 值为空 / 文件里只剩注释 ⇒ 看起来配了、其实
    什么都没加载；
  · sh 语法坏 ⇒ 钩子要到提交时刻才响亮地死
    （set -e），报错还指向不明。

可插拔：Einfacht.env 不存在（钩子目录与仓库根都
没有）⇒ 明说未启用、退 0（钩子回落纯环境变量
+ 默认名）。

旋钮名册是**发现式**的：扫 zreflect/*.py 里出现的
REFLECT_* 记号（所有旋钮都经 os.environ.get 读）
—— 名册不手写（手写名录一定会漂，issue #1 ② 同款）。
⚠️ 因此本文件的任何字符串里都不得出现**假的**
REFLECT_ 旋钮名（自证里的 typo 样例用拼接构造）——
否则扫描会把 typo 收进名册，守卫就废了。
文件旋钮名单（哪些旋钮的值是路径）是本闸门的判据
数据，新旋钮若取值是路径必须登记在 FILE_KNOBS /
LIST_FILE_KNOBS / DIR_KNOBS。

诚实边界：存在性只查**相对仓库根**的路径；
core.hooksPath 改过布局的仓库，钩子目录按
reflect-hooks/ 找（声明式检查的文本形态上限，
issue #7 同款边界）。

用法（直接跑，cwd=仓库根）：
    python3 zreflect/check_envfile.py [--selftest]
退出码：0=绿 / 1=发现问题 / 2=配置或环境坏了。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import repo, selftest                            # noqa: E402

ENV_FILE = (os.environ.get("REFLECT_ENV_FILE", "Einfacht.env")
            .strip() or "Einfacht.env")

# 文件旋钮：本闸门的判据数据（不是发现式名册 ——
# 「哪个旋钮的值是路径」是语义，代码里推不出来）。
# 新旋钮若取值是相对仓库根的文件 / 目录 / 逗号
# 分隔清单，登记在这里。
FILE_KNOBS = {
    "REFLECT_FACTS": "台账文件",
    "REFLECT_DOC": "活状态文档",
    "REFLECT_RETRACTIONS": "翻案台账",
    "REFLECT_INVARIANTS": "不变量规格",
    "REFLECT_INSTRUMENTS": "量法登记",
}
LIST_FILE_KNOBS = {
    "REFLECT_DOCS": "活状态文档清单",
    "REFLECT_READMES": "README 名单",
}
DIR_KNOBS = {
    "REFLECT_QUESTIONS": "悬案目录",
}

_EXPORT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_QUOTES = re.compile(r'^["\']|["\']$')


def known_knobs(py_dir=None):
    """发现式名册：zreflect/*.py 里出现的 REFLECT_* 记号全集。

    所有旋钮都经 os.environ.get 读 ⇒ 代码中出现的
    REFLECT_* 记号 = 已知旋钮集（文档字符串里的提及
    也算 —— 无妨：typo 守卫要的是真名全集，多收录
    真名不算错）。`py_dir` 可注入（自证用假源码树）。
    """
    d = py_dir if py_dir is not None else repo("zreflect")
    knobs = set()
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return knobs
    for n in names:
        if not n.endswith(".py"):
            continue
        try:
            with open(os.path.join(d, n), encoding="utf-8",
                      errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        knobs.update(re.findall(r"REFLECT_[A-Z0-9_]+", text))
    return knobs


def parse_exports(text):
    """解析 env 文件的生效 export（纯函数：自证要用）。

    返回 {名字: 值}。注释行 / 空行跳过 —— 只剩注释
    的文件 ⇒ 空 dict（「看起来配了」的静默坏法由
    调用方报告）。值只做引号剥离，不做变量展开
    （存在性判据不需要展开后的值）。
    """
    out = {}
    for line in text.splitlines():
        m = _EXPORT_RE.match(line)
        if not m:
            continue
        out[m.group(1)] = _QUOTES.sub("", m.group(2).strip())
    return out


def problems(exports, known, file_exists, dir_exists, syntax_ok=None):
    """纯函数：返回问题清单（空 = 绿）。自证期间不许 print。

    `exports` = parse_exports 的结果；`known` = 已知
    旋钮名册；`file_exists` / `dir_exists` = 存在性
    探针（自证注入假文件系统）；`syntax_ok` = sh -n
    的结论（True / False；None = 仪器本身跑不了）。
    """
    out = []
    if not exports:
        return ["%s 里没有任何生效的 export（空文件或只剩注释）"
                " —— 看起来配了、其实什么都没加载"
                "（「部署了 ≠ 在跑」家族）" % ENV_FILE]
    for name in sorted(exports):
        if not name.startswith("REFLECT_"):
            continue                    # 非旋钮 export 不是本闸门的活
        value = exports[name]
        if not value:
            out.append("`%s` 的值是空的 —— 空值会让钩子的"
                       " [ -f ] 守卫静默跳过（空不是通过）" % name)
            continue
        if name not in known:
            out.append("旋钮名 `%s` 不在已知旋钮名册里 —— 打错"
                       "一位会被所有程序静默忽略，值永远到不了"
                       "钩子（已知：%s）"
                       % (name, ", ".join(sorted(known)) or "（名册为空）"))
            continue
        if name in FILE_KNOBS:
            targets, is_dir = [value], False
        elif name in LIST_FILE_KNOBS:
            targets = [t.strip() for t in value.split(",") if t.strip()]
            is_dir = False
        elif name in DIR_KNOBS:
            targets, is_dir = [value], True
        else:
            continue                    # 非文件旋钮（数字 / 枚举）不查存在性
        for t in targets:
            hit = dir_exists(t) if is_dir else file_exists(t)
            if not hit:
                out.append("文件旋钮 `%s`（%s）指向的%s不存在：%s"
                           " —— 钩子的 [ -f ] 守卫会静默跳过"
                           "（路径相对仓库根）"
                           % (name, FILE_KNOBS.get(name)
                              or LIST_FILE_KNOBS.get(name)
                              or DIR_KNOBS.get(name),
                              "目录" if is_dir else "文件", t))
    if syntax_ok is False:
        out.append("%s 过不了 sh -n（语法坏）⇒ 钩子要到提交"
                   "时刻才响亮地死，且报错指向不明" % ENV_FILE)
    if syntax_ok is None:
        out.append("sh -n 跑不了（sh 不在？）—— 语法检查这个"
                   "仪器本身坏了，先修检查器，不许静默跳过")
    return out


def _find_env_file():
    """插件同款的解析顺序：钩子目录优先、仓库根次之。"""
    for d in (repo("reflect-hooks"), repo()):
        p = os.path.join(d, ENV_FILE)
        if os.path.exists(p):
            return p
    return None


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    p = _find_env_file()
    if p is None:
        print("env 文件闸门：%s 不存在（钩子目录与仓库根都没有）"
              " ⇒ 本闸门未启用（可插拔模块；钩子回落纯环境变量"
              " + 默认名。要启用：cp reflect-hooks/"
              "Einfacht.env.example reflect-hooks/%s）"
              % (ENV_FILE, ENV_FILE), file=sys.stderr)
        return 0
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as e:
        print("FATAL: %s 读不了：%s" % (p, e), file=sys.stderr)
        return 2
    known = known_knobs()
    if not known:
        print("FATAL: 在 %s 里没发现任何 REFLECT_* 旋钮 —— 名册"
              "发现失败（zreflect/ 不在？），本闸门的仪器坏了"
              % repo("zreflect"), file=sys.stderr)
        return 2
    # 语法检查（仪器）：sh -n 只解析不执行。语法错 ⇒ 是要报
    # 的问题；跑不了 ⇒ 仪器坏了（syntax_ok=None，如实报）。
    syntax = None
    try:
        r = subprocess.run(["sh", "-n", p], capture_output=True)
        syntax = r.returncode == 0
    except OSError:
        syntax = None
    exports = parse_exports(text)
    probs = problems(exports, known,
                     lambda t: os.path.exists(repo(t)),
                     lambda t: os.path.isdir(repo(t)),
                     syntax_ok=syntax)
    if probs:
        print("env 文件闸门：%d 个问题（%s）" % (len(probs), p),
              file=sys.stderr)
        for x in probs:
            print("  · " + x, file=sys.stderr)
        return 1
    print("env 文件闸门：OK（%s：%d 条生效 export，旋钮名全在"
          "名册、文件旋钮指向都在）"
          % (os.path.relpath(p, repo()), len(exports)))
    return 0


def _cases():
    good_files = ("STATE.md", "README.md", "README.zh.md",
                  "README.de.md", "FACTS.json", "AGENTS.md",
                  "RETRACT.json", "invariants.json")
    fe = lambda t: t in good_files                     # noqa: E731
    de = lambda t: t in ("questions", "cases")         # noqa: E731
    known = {"REFLECT_DOC", "REFLECT_READMES", "REFLECT_DOCS",
             "REFLECT_QUESTIONS", "REFLECT_FACTS",
             "REFLECT_NAKED_MIN", "REFLECT_ENV_FILE"}
    good_env = {"REFLECT_DOC": "STATE.md",
                "REFLECT_READMES": "README.md,README.zh.md,README.de.md",
                "REFLECT_QUESTIONS": "questions",
                "REFLECT_NAKED_MIN": "100"}
    # typo 样例用拼接构造：本文件在 zreflect/ 里，会被
    # known_knobs() 扫到 —— 字面量写死会把 typo 收进名册。
    typo = "REFLECT_" + "DOCSS"
    return [
        # ① 正常不报
        ("生效 export 全合法（含数字旋钮）⇒ 不报",
         lambda: problems(good_env, known, fe, de, syntax_ok=True) == []),
        ("非 REFLECT_ 前缀的 export ⇒ 不报（不是本闸门的活）",
         lambda: problems({"PATH": "/usr/bin"}, known, fe, de,
                          syntax_ok=True) == []),
        # ② 该报的必须报
        ("★ 旋钮名打错一位 ⇒ 必须报（静默忽略家族）",
         lambda: any("不在已知旋钮名册" in x for x in problems(
             {typo: "STATE.md"}, known, fe, de, syntax_ok=True))),
        ("★ 文件旋钮指向缺失文件 ⇒ 必须报（[ -f ] 静默跳过家族）",
         lambda: any("不存在" in x and "REFLECT_DOC" in x for x in problems(
             {"REFLECT_DOC": "MYSTATE.md"}, known, fe, de, syntax_ok=True))),
        ("★ 清单旋钮有一份缺失 ⇒ 必须报（点名缺失的那份）",
         lambda: any("README.missing.md" in x for x in problems(
             {"REFLECT_READMES": "README.md,README.missing.md"},
             known, fe, de, syntax_ok=True))),
        ("★ 目录旋钮指向文件 ⇒ 必须报（目录探针不命中）",
         lambda: any("目录" in x for x in problems(
             {"REFLECT_QUESTIONS": "STATE.md"}, known, fe, de,
             syntax_ok=True))),
        ("★ 值为空 ⇒ 必须报（空值让守卫静默跳过）",
         lambda: any("值是空的" in x for x in problems(
             {"REFLECT_DOC": ""}, known, fe, de, syntax_ok=True))),
        ("★ sh -n 不过 ⇒ 必须报",
         lambda: any("sh -n" in x for x in problems(
             good_env, known, fe, de, syntax_ok=False))),
        ("★ sh -n 跑不了 ⇒ 必须报（仪器坏了不许静默跳过）",
         lambda: any("跑不了" in x for x in problems(
             good_env, known, fe, de, syntax_ok=None))),
        # ③ 空输入必须报
        ("★ 空 export 集（空文件 / 只剩注释）⇒ 必须报",
         lambda: problems({}, known, fe, de, syntax_ok=True) != []),
    ]


if __name__ == "__main__":
    sys.exit(selftest("env 文件闸门（可插拔：守钩子的 REFLECT_* 载体）",
                      _cases())
             if "--selftest" in sys.argv else run(sys.argv[1:]))
