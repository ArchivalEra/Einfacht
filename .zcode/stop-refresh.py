#!/usr/bin/env python3
"""Stop hook 壳：重渲染机器块，**永远退 0**（issue #4 ① 第四层）。

⚠️ 从这一版起，`STATE.md` 里的 `AUTO:NEXT` 块**每轮都重新渲染** —— 这是
「记忆系统无感化」的那一半：会话压缩后 agent 需要知道「上一轮做到哪、下一步
是什么」，此前这靠人在压缩前手工整理（「每次都要有人准备压缩」本身就是缺陷）。
`SessionStart`（matcher 含 `compact`）负责把它注入上下文，本钩子负责保证
它是最新的。

`AUTO:NEXT` **不参与 `facts.py --check`** 的逐字节对账（每轮都变的东西拿去
对账 ⇒ 永远红 ⇒ 闸门被关掉）。见 `facts._is_rechecked`。

ZCode 的 hook 退出码语义：0 放行、**2 阻塞**、其它非零算错误。
`facts.py --render-doc` 在台账缺失时 SystemExit(2) —— 直接把它挂进
Stop，一次台账缺文件就会把整个会话当人质。这层壳把任何失败降级为
stderr 一句 + 退出 0：注入是善意，不是人质。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "zreflect"))
DOC = os.environ.get("REFLECT_DOC", "STATE.md")

p = subprocess.run(
    [sys.executable, os.path.join(REPO, "zreflect", "facts.py"),
     "--render-doc", DOC],
    cwd=REPO, capture_output=True, text=True)
if p.returncode != 0:
    # 失败提示是**用户可见文本** ⇒ 走 M()（本体零语言；未装语言包时输出
    # `stop.refresh_failed(…)`，那是诚实的）。激活失败不阻塞会话。
    from gate import activate_or_fatal                  # noqa: PLC0415
    activate_or_fatal()
    from i18n import M                                  # noqa: PLC0415
    tail = (p.stderr or p.stdout or "").strip().splitlines()
    print(str(M("stop.refresh_failed", return_code=p.returncode,
                detail=tail[-1] if tail else M("stop.no_output"))),
          file=sys.stderr)
sys.exit(0)          # 永远退 0：Stop 不阻塞
