#!/usr/bin/env python3
"""复跑闸门：台账每条事实的 `cmd` **真的被跑一遍**，stdout 必须等于台账值。

它挡的是机制自己最大的空头承诺（issue #2 ①）：README 开篇说「该是一条能复跑的断言」，
但发布出去的机制里**没有任何一处执行那条 `cmd`** —— cmd 腐烂了（路径移走、工具改名、
命令直接报错），它连同坏名字会被 `--render-doc` 原样印进活状态文档，每个闸门照绿不误。
「能复跑」从此不再是宣传语，而是每次 pre-commit / pre-push 都重证一次的断言。

判据（`cmd` 逐字执行，cwd = 仓库根）：

  · **裸值契约**：stdout 去掉首尾空白后必须**等于**值（`str(value)`）。
    只打印「含该值的整行」⇒ 人眼可读、机器不可判 ⇒ 判不符。
  · **返回码非 0 ⇒ 报**：坏命令不是「值变了」，是「复跑方式本身死了」。
  · **超时 ⇒ 报**（默认 10s，`REFLECT_REPLAY_TIMEOUT` 覆盖）：挂在 pre-commit 里的
    命令不该永远等不到结果。
  · **没有 `cmd` ⇒ 报**：没复跑命令的事实就是散文。
  · 管道**不再吞错**：有 bash 就用 `bash -o pipefail -c`（`cat 没了 | wc -l` 打印 0
    且 rc=0 的那种「失败但绿」正是本闸门要红的东西）。没有 bash 时退回 /bin/sh
    并在输出里明说 —— 判据强度随环境变化这件事，不许静默。

零值守卫三条：台账为空 ⇒ 报；一条都没跑成（全 rc≠0/超时）⇒ 报；全部事实都声明
`replay: false` ⇒ 报（全豁免不是「通过」，是「这个闸门什么都没查」）。

边界（issue #2 ① 明说的，别做过头）：复跑只该覆盖**不需要构建产物**的事实。
要起服务、要编二进制的那些，写 `fact(值, cmd, 出处, replay=False)` 显式退出 ——
这是有名单、有明说的豁免，不是静默；整道闸也留了 `REFLECT_REPLAY=off` 的整仓出口
（同 `REFLECT_RETIRED` 的先例：**明说未启用，不假装查过**）。

⚠️ 本闸门执行的是**本仓台账里的命令** —— 信任边界与 pre-commit 脚本本身相同。
台账是仓库自己生产、自己审查的文件；改台账 = 改构建脚本级别的承诺，不是运行时输入。
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import GATE_REPO, repo, selftest               # noqa: E402
from ledger import _value, facts_of, load                # noqa: E402


def _timeout():
    try:
        return float(os.environ.get("REFLECT_REPLAY_TIMEOUT", "10"))
    except ValueError:
        return 10.0                     # 配了个非数 ⇒ 用默认值，但 run() 会明说（见下）


def _q(s, n=60):
    """把一段输出缩成可引用的 repr（复现事故时别把 1 MiB stdout 糊进终端）。"""
    t = s if len(s) <= n else s[:n] + "…"
    return repr(t)


def run_cmd(cmd, timeout=None):
    """逐字跑一条 `cmd`（cwd=仓库根），返回 (返回码, stdout)。超时 ⇒ 返回码 None。"""
    t = _timeout() if timeout is None else timeout
    bash = shutil.which("bash")
    argv = [bash, "-o", "pipefail", "-c", cmd] if bash else ["/bin/sh", "-c", cmd]
    try:
        p = subprocess.run(argv, cwd=GATE_REPO, capture_output=True, text=True,
                           timeout=t)
    except subprocess.TimeoutExpired:
        return None, ""
    except OSError as e:                # 连 shell 起不来 —— 报成失败，不许算通过
        return 127, "FATAL: %s" % e
    return p.returncode, p.stdout


def replay_all(ledger, runner=None):
    """逐条复跑，返回 {problems, ok, attempts, skipped}。**纯副作用只经由 runner**。

    `runner(cmd) -> (rc, stdout)` 可注入（自证用假 runner —— 真 shell 进了自证，
    自证就依赖机器了）。纯函数保持安静：这里一行都不 print。
    """
    run = runner or run_cmd
    out = []
    f = facts_of(ledger)
    stats = {"ok": 0, "attempts": 0, "ran": 0, "skipped": 0}
    if not f:
        # 零值守卫：台账空着不是「没有违规」，是「什么都没量」。
        stats["problems"] = ["台账为空 —— 空不是通过（零值守卫）：先查 measure() 是不是坏了"]
        return stats
    t = _timeout()
    for k in sorted(f):
        entry = f[k] if isinstance(f[k], dict) else {"value": f[k]}
        cmd = str(entry.get("cmd") or "").strip()
        if entry.get("replay") is False:
            stats["skipped"] += 1
            continue
        if not cmd:
            out.append("`%s` 没有复跑命令 —— 没 cmd 的事实就是散文（裸值契约的前提"
                       "是它有 cmd）" % k)
            continue
        stats["attempts"] += 1
        rc, stdout = run(cmd)
        if rc is None:
            out.append("`%s` 复跑**超时**（%.0fs）：`%s` —— 要起服务/要构建的条目应写 "
                       "replay=False，别拿超时当数据" % (k, t, cmd))
            continue
        if rc != 0:
            out.append("`%s` 复跑**命令报错**（rc=%s）：`%s` —— 坏 cmd 印在活状态文档里，"
                       "就是每行都绿着的假断言" % (k, rc, cmd))
            continue
        stats["ran"] += 1      # 「跑成」= 命令本身成功（rc=0）；值不符是数据问题，另一条判据
        got = stdout.strip()
        want = str(_value(entry))
        if got != want:
            out.append("`%s` 复跑输出与台账不符：stdout=%s vs 台账=%s —— 要么值烂了"
                       "（重测并 --accept-changes），要么 cmd 违反裸值契约（stdout 只能"
                       "打值本身）" % (k, _q(got), _q(want)))
            continue
        stats["ok"] += 1
    if stats["attempts"] and stats["ran"] == 0:
        out.append("%d 条尝试复跑**一条都没跑成**（全部 rc≠0/超时）—— 环境或 shell "
                   "整体坏了的时候，逐条报错会伪装成「数据都查过了」（零值守卫）"
                   % stats["attempts"])
    if not stats["attempts"] and stats["skipped"]:
        out.append("全部 %d 条事实都声明 replay=False ⇒ 本闸门什么都没查 —— "
                   "至少留一条能复跑的；整仓都不适用就设 REFLECT_REPLAY=off 明说"
                   "（全豁免不是通过）" % stats["skipped"])
    stats["problems"] = out
    return stats


def run(argv):
    if os.environ.get("REFLECT_REPLAY", "").strip().lower() == "off":
        print("复跑闸门：REFLECT_REPLAY=off ⇒ 本闸门未启用（明说，不假装查过 —— "
              "个别要构建产物的条目请用 replay=False 逐个退出，别关整道闸）",
              file=sys.stderr)
        return 0
    t = _timeout()
    try:
        float(os.environ.get("REFLECT_REPLAY_TIMEOUT", "10"))
    except ValueError:
        print("⚠ REFLECT_REPLAY_TIMEOUT=%r 不是数 ⇒ 用默认 %.0fs" % (os.environ.get("REFLECT_REPLAY_TIMEOUT"), t),
              file=sys.stderr)
    name = os.environ.get("REFLECT_FACTS", "FACTS.json")
    p = repo(name)
    if not os.path.exists(p):
        print("FATAL: 缺事实台账（%s）。先跑 python3 zreflect/facts.py 量一遍。" % name,
              file=sys.stderr)
        return 2
    r = replay_all(load(p))
    for x in r["problems"]:
        print("  · %s" % x, file=sys.stderr)
    if r["problems"]:
        print("复跑闸门：%d 个问题" % len(r["problems"]), file=sys.stderr)
        return 1
    tail = "，%d 条声明 replay=False 未跑" % r["skipped"] if r["skipped"] else ""
    print("复跑闸门：OK（%d 条事实逐字复跑，stdout 与台账一致%s）" % (r["ok"], tail))
    return 0


LED = {"facts": {"n": {"value": 12, "cmd": "c"}}}


def _cases():
    multi = {"facts": {"a": {"value": 1, "cmd": "ca"},
                       "b": {"value": 2, "cmd": "cb", "replay": False}}}
    return [
        # ① 正常不报
        ("stdout 与台账值一致（带尾换行）⇒ 不报",
         lambda: replay_all(LED, runner=lambda c: (0, "12\n"))["problems"] == []),
        ("字符串值；stdout 首尾空白被去掉后相等 ⇒ 不报",
         lambda: replay_all({"facts": {"s": {"value": "v1", "cmd": "c"}}},
                            runner=lambda c: (0, " v1\n"))["problems"] == []),
        ("声明 replay=False 的条目被跳过，其余一致 ⇒ 不报",
         lambda: replay_all(multi, runner=lambda c: (0, "1"))["problems"] == []),
        # ② 该报的必须报
        ("★ stdout ≠ 台账值 ⇒ 必须报（值烂了要当场抓住）",
         lambda: any("不符" in x for x in
                     replay_all(LED, runner=lambda c: (0, "13"))["problems"])),
        ("★ stdout 打了「含该值的整行」⇒ 必须报（裸值契约：机器只认整段 stdout）",
         lambda: any("不符" in x for x in
                     replay_all(LED, runner=lambda c: (0, "count=12 total"))["problems"])),
        ("★ cmd 返回码非 0 ⇒ 必须报（issue #2 ① 的无管道复现：cat 不存在 rc=1）",
         lambda: any("命令报错" in x for x in
                     replay_all(LED, runner=lambda c: (1, ""))["problems"])),
        ("★ 超时 ⇒ 必须报（挂在 pre-commit 里永远等不到，不许算通过）",
         lambda: any("超时" in x for x in
                     replay_all(LED, runner=lambda c: (None, ""))["problems"])),
        ("★ 事实没有 cmd ⇒ 必须报（没复跑命令的事实就是散文）",
         lambda: any("没有复跑命令" in x for x in replay_all(
             {"facts": {"n": {"value": 1, "source": "s"}}}, runner=lambda c: (0, "1"))["problems"])),
        # ③ 空输入必须报
        ("★ 空台账 ⇒ 必须报（空不是通过）",
         lambda: replay_all({"facts": {}}, runner=lambda c: (0, ""))["problems"] != []),
        ("★ 一条都没跑成（全部 rc≠0）⇒ 必须报（零值守卫，issue #2 ① 的 selftest 要求）",
         lambda: any("一条都没跑成" in x for x in replay_all(
             {"facts": {"a": {"value": 1, "cmd": "x"}, "b": {"value": 2, "cmd": "y"}}},
             runner=lambda c: (1, ""))["problems"])),
        ("★ 全部事实都声明 replay=False ⇒ 必须报（全豁免 ≠ 通过）",
         lambda: any("什么都没查" in x for x in replay_all(
             {"facts": {"a": {"value": 1, "cmd": "x", "replay": False}}},
             runner=lambda c: (0, "1"))["problems"])),
    ]


if __name__ == "__main__":
    sys.exit(selftest("check_facts_replay（台账 cmd 逐字复跑：stdout 必须等于值）", _cases())
             if "--selftest" in sys.argv else run(sys.argv[1:]))
