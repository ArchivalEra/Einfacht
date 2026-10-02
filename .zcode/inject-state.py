#!/usr/bin/env python3
"""SessionStart hook：把「现在是什么」注入上下文。

挂法见 `.zcode/config.json`。它做的只有两件事：列出**未结案的悬案**，以及台账的规模。
为什么值得占一个 hook：会话开始时 agent 手上没有状态，于是它会**重新提出已经结案的问题**、
或者**照抄一份过期的数字**。这个脚本把那两件事的输入摆在桌面上。

⚠️ 输出必须短。hook 的 stdout 会进上下文，一屏以上的注入会挤掉真正的工作内容。

⚠️ 输出形状（issue #4 ① 第二层）：ZCode 把 hook 的 stdout 按**严格 JSON**
解析，信封是 {"hookSpecificOutput": {"hookEventName": …, "additionalContext": …}}
—— 非 JSON / 多余键 ⇒ 验证失败、整条注入被丢弃，只在日志里留一条
failed，而日志看起来像小毛病。所以：**hook 上下文（非 tty）发 JSON 信封；
只有手工跑（tty）才发纯文本**。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zreflect"))

from gate import GATE_REPO                                   # noqa: E402


def _collect():
    """注入内容（纯文本行列表）。与输出形状解耦：信封由 main() 决定。"""
    lines = ["── zcode-reflect · 活状态 ──"]

    # 1) 未结案的悬案
    try:
        from check_questions import collect, field           # noqa: PLC0415
        qs = collect("questions")
        open_qs = [(n, field(t, "Status") or "?") for n, t in sorted(qs.items())
                   if (field(t, "Status") or "") != "resolved"]
        if not qs:
            lines.append("悬案：**一条都没有**（questions/ 是空的 —— 这本身可疑，不是好消息）")
        elif not open_qs:
            lines.append("悬案：%d 条，全部已结案。" % len(qs))
        else:
            lines.append("悬案：未结案 %d / 共 %d —— 先读这些，别重新提出已结案的问题："
                         % (len(open_qs), len(qs)))
            for n, st in open_qs[:8]:
                lines.append("   · %s  [%s]" % (n, st))
            if len(open_qs) > 8:
                lines.append("   · …还有 %d 条" % (len(open_qs) - 8))
    except Exception as e:                                   # noqa: BLE001
        lines.append("悬案：读不到（%r）—— 门开着，别把'读不到'当成'没有'" % e)

    # 2) 台账规模
    try:
        from ledger import facts_of, load                    # noqa: PLC0415
        f = facts_of(load(os.path.join(GATE_REPO, os.environ.get("REFLECT_FACTS", "FACTS.json"))))
        lines.append("台账：%d 条事实（数字请写引用，别手抄）" % len(f))
    except Exception as e:                                   # noqa: BLE001
        lines.append("台账：读不到（%r）" % e)

    # 3) 翻案条数
    try:
        from ledger import load as _load                     # noqa: PLC0415
        r = _load(os.path.join(GATE_REPO, "retractions.json")).get("retractions") or []
        lines.append("翻案：%d 条（这些断言**不许**再当现状出现）" % len(r))
    except Exception:                                        # noqa: BLE001
        pass
    return lines


def main():
    text = "\n".join(_collect()) + "\n"
    if sys.stdout.isatty():
        # 人手工跑：纯文本（hook 上下文必须发 JSON 信封，见模块 docstring）
        sys.stdout.write(text)
        return 0
    sys.stdout.write(json.dumps(
        {"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
