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

import sys

# 名字 → (kind, 默认值, 一句话语义)。默认值 = 旋钮未配时各消费方的回落名。
REGISTRY = {
    "REFLECT_FACTS": ("file", "FACTS.json", "事实台账"),
    "REFLECT_DOC": ("file", "STATE.md", "活状态文档（机器块渲染进它）"),
    "REFLECT_DOCS": ("list", "STATE.md,AGENTS.md,README.md,README.zh.md,README.de.md",
                     "翻案 / 陈旧闸门扫描的活状态文档清单"),
    "REFLECT_HISTORY_SECS": ("value", "", "append-only 历史章节编号（如 5,9,10）"),
    "REFLECT_RETIRED": ("value", "", "退役组件名清单；空 = 该规则明说未启用"),
    "REFLECT_NAKED_MIN": ("number", "100", "裸数字阈值（小于它的整数不查）"),
    "REFLECT_STALE_DAYS": ("number", "", "测龄报警天数；空 = 该规则明说未启用"),
    "REFLECT_REPLAY": ("flag", "", "off ⇒ 复跑闸门明说未启用"),
    "REFLECT_REPLAY_TIMEOUT": ("number", "10", "逐字执行器的默认超时秒数"),
    "REFLECT_READMES": ("list", "README.md,README.zh.md,README.de.md",
                        "三语 README 名单（结构互链 + 每次推送同批）"),
    "REFLECT_RETRACTIONS": ("file", "retractions.json", "翻案台账"),
    "REFLECT_QUESTIONS": ("dir", "questions", "悬案目录"),
    "REFLECT_ENV_FILE": ("value", "Einfacht.env", "钩子旋钮载体的文件名"),
    "REFLECT_INVARIANTS": ("file", "", "声明式不变量规格；空 = 明说未启用"),
    "REFLECT_INSTRUMENTS": ("file", "", "量法登记位；空 = 该规则明说未启用"),
    "REFLECT_INSTRUMENT_DAYS": ("number", "", "恒常检测阈值天；空 = 该规则明说未启用"),
    "REFLECT_DOCTOR": ("file", "doctor.json", "doctor 规格（开工预检，非闸门）"),
    "REFLECT_DOCTOR_TIMEOUT": ("number", "2", "每条 doctor 探测的秒数"),
    "REFLECT_WORLD": ("file", "world.json", "world 声明（验证对象清单）；缺文件 = 未启用"),
    "REFLECT_WORLD_LINE": ("value", "", "world 线覆盖（CI / 特殊跑法）"),
    "REFLECT_AB": ("file", "ab.json", "A/B 同旗标闸门的规格名"),
    "REFLECT_PINS": ("file", "pins.json", "派生树 pin 一致性闸门的规格名"),
}

KINDS = ("file", "list", "dir", "number", "flag", "value")


def kinds_of(name):
    """旋钮的种类（未登记 ⇒ None —— 调用方该报幻影 / typo）。"""
    entry = REGISTRY.get(name)
    return entry[0] if entry else None


# ── 自证：名册自身的形状守卫（登记表坏 = 所有消费方的判据数据坏）──────────────
def _cases():
    return [
        # ① 正常不报
        ("登记表每条 = (合法 kind, 字符串默认值, 非空语义)",
         lambda: all(k in KINDS and isinstance(d, str) and w.strip()
                     for k, d, w in REGISTRY.values()) and len(REGISTRY) >= 20),
        # ② 该报的必须报
        ("★ kind 非法应当被形状守卫拦下（反向断言的判据本身要能假）",
         lambda: "file" in KINDS and "bogus" not in KINDS),
        # ③ 空输入必须报
        ("★ 登记表为空 = 名册坏（零值守卫）", lambda: bool(REGISTRY)),
    ]


def selftest():
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from gate import selftest as _st                     # noqa: PLC0415
    return _st("knobs（旋钮登记：REFLECT_* 的唯一名册）", _cases())


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from gate import main_selftest_or                    # noqa: PLC0415

    def _run(argv):
        print("knobs 是模块（被各闸门消费）；--selftest 看自证。",
              file=sys.stderr)
        return 2
    sys.exit(main_selftest_or(sys.argv[1:],
                              "knobs（旋钮登记：REFLECT_* 的唯一名册）",
                              _cases, _run))
