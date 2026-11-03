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

from gate import GATE_REPO, activate_or_fatal                # noqa: E402

# ⚠️ **不许替用户挑语言包**。
#
# 这里曾经写过「没设 `REFLECT_LANG` 就自动挑 zh/en」——那是**偷偷装了个中文包**，
# 直接违反本仓的硬不变式：**没要语言包 ⇒ null 包**，输出 `code(param=value)`。
# 实测：同一环境里闸门吐 `OFF: locks.off(name=…)`（正确），注入却吐中文。
#
# 要中文注入就显式设 `REFLECT_LANG=zh`。「注入是人读的所以可以破例」是同一种
# 自我豁免 —— 本仓在 `machine_vocab_ok` 上抓过一次，再犯就是明知故犯。
activate_or_fatal()


def _next_block():
    """「接着上一轮」的行（`next.py` 现算，**不落盘**）。

    ⚠️ 它不进 `STATE.md`：state 是「现在是什么」、被 `--check` 逐字节对账；
    而这一块**每轮都变**。两者混在一起会让 `--check` 永远红（实测过）。
    它每次会话开始时现算 —— 便宜（读 git status 与台账计数），且永远新鲜。
    """
    try:
        import next as _next                               # noqa: PLC0415
        last, pending = _next.collect(GATE_REPO)
    except Exception:                                      # noqa: BLE001
        return None
    return last + ([""] + pending if pending else [])


def _collect():
    """注入内容（纯文本行列表）。与输出形状解耦：信封由 main() 决定。"""
    from i18n import M                                   # noqa: PLC0415
    lines = [str(M("inject.banner"))]

    # 0) 接着上一轮 —— **最要紧的一条**，放最前（压缩后 agent 第一眼看到的）
    nb = _next_block()
    if nb:
        lines.append(str(M("inject.next_header")))
        lines.extend("   " + ln.strip() for ln in nb[:8])
    else:
        lines.append(str(M("inject.next_missing", source=DOC)))

    # 1) 未结案的悬案
    try:
        from check_questions import collect, field           # noqa: PLC0415
        qs = collect("questions")
        open_qs = [(n, field(t, "Status") or "?") for n, t in sorted(qs.items())
                   if (field(t, "Status") or "") != "resolved"]
        if not qs:
            lines.append(str(M("inject.questions_none")))
        elif not open_qs:
            lines.append(str(M("inject.questions_all_closed", total=len(qs))))
        else:
            lines.append(str(M("inject.questions_open", open=len(open_qs),
                               total=len(qs))))
            for n, st in open_qs[:8]:
                lines.append("   · %s  [%s]" % (n, st))
            if len(open_qs) > 8:
                lines.append("   " + str(M("inject.questions_more",
                                            count=len(open_qs) - 8)))
    except Exception as e:                                   # noqa: BLE001
        lines.append(str(M("inject.questions_unreadable", error=e)))

    # 2) 台账规模
    try:
        from ledger import facts_of, load                    # noqa: PLC0415
        f = facts_of(load(os.path.join(GATE_REPO, os.environ.get("REFLECT_FACTS", "FACTS.json"))))
        lines.append(str(M("inject.ledger_size", count=len(f))))
    except Exception as e:                                   # noqa: BLE001
        lines.append(str(M("inject.ledger_unreadable", error=e)))

    # 3) 翻案条数
    try:
        from ledger import load as _load                     # noqa: PLC0415
        r = _load(os.path.join(GATE_REPO, "retractions.json")).get("retractions") or []
        lines.append(str(M("inject.retractions_size", count=len(r))))
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
