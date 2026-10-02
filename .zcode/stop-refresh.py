#!/usr/bin/env python3
"""Stop hook 壳：重渲染机器块，**永远退 0**（issue #4 ① 第四层）。

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
DOC = os.environ.get("REFLECT_DOC", "STATE.md")

p = subprocess.run(
    [sys.executable, os.path.join(REPO, "zreflect", "facts.py"),
     "--render-doc", DOC],
    cwd=REPO, capture_output=True, text=True)
if p.returncode != 0:
    tail = (p.stderr or p.stdout or "").strip().splitlines()
    print("stop-refresh: 机器块重渲染失败（rc=%s）：%s"
          % (p.returncode, tail[-1] if tail else "（无输出）"),
          file=sys.stderr)
sys.exit(0)          # 永远退 0：Stop 不阻塞
