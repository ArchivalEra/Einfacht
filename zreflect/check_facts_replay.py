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
`replay: false` **且无见证** ⇒ 报（全豁免不是「通过」，是「这个闸门什么都没查」；
挂了 witness 的贵事实照样被查 —— issue #5）。

第三档：**见证**（issue #5）—— `replay=False` 的贵事实可挂便宜见证
（`witness` + `witness_expect`，两者同给，残缺形状由 `ledger.fact()`
当场报错）。见证与 `replay` **正交**：值本身不逐字复跑，但
**来源/上下文**（"产出它的工具/输入就是我以为的那个"）**每次提交真跑**，
判据同裸值契约（`stdout.strip() == witness_expect`）。「贵」恰恰是
最需要便宜复查的地方：产物没变、但产出它的工具变了，能一路蒙混到
最贵的端到端回归才炸 —— 见证在提交时就抓住它。

边界（issue #2 ① 明说的，别做过头）：复跑只该覆盖**不需要构建产物**的事实。
要起服务、要编二进制的那些，写 `fact(值, cmd, 出处, replay=False)` 显式退出 ——
这是有名单、有明说的豁免，不是静默；整道闸也留了 `REFLECT_REPLAY=off` 的整仓出口
（同 `REFLECT_RETIRED` 的先例：**明说未启用，不假装查过**）。
还有一类不需要构建产物、只是**每跑必变**（随机填充长度、GREASE 载荷、时间戳
类，issue #4 ⑤）：存**一次实测采样** + 配一对 `*_stable` 稳定性标记键
（消费侧分两档：stable 逐字判、不稳定档结构判），或显式 `replay=False` ——
**不许裸存**：裸存 = 这条事实永远红 = 噪音 = 最后整闸被关。
值会变 ≠ 不能进台账，得先声明它怎么变。

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
    stats = {"ok": 0, "attempts": 0, "ran": 0, "skipped": 0,
             "witness_attempts": 0, "witnessed": 0}
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
            out.append("`%s` 复跑输出与台账不符：stdout=%s vs 台账=%s —— 修法是"
                       "**重测**：python3 zreflect/facts.py，改口逐条"
                       " `--accept-changes=k1,k2` 放行；重测后仍不符，才是"
                       "cmd 违反裸值契约（stdout 只能打值本身）"
                       % (k, _q(got), _q(want)))
            continue
        stats["ok"] += 1
    if stats["attempts"] and stats["ran"] == 0:
        out.append("%d 条尝试复跑**一条都没跑成**（全部 rc≠0/超时）—— 环境或 shell "
                   "整体坏了的时候，逐条报错会伪装成「数据都查过了」（零值守卫）"
                   % stats["attempts"])
    # 见证档（issue #5）：与 replay 正交 —— 贵事实（replay=False）
    # 的来源/上下文每次提交真跑，判据同裸值契约。
    for k in sorted(f):
        entry = f[k] if isinstance(f[k], dict) else {"value": f[k]}
        wit = str(entry.get("witness") or "").strip()
        if not wit:
            continue
        expect = entry.get("witness_expect")
        stats["witness_attempts"] += 1
        rc, stdout = run(wit)
        if rc is None:
            out.append("`%s` 见证**超时**（%.0fs）：`%s` —— 见证该便宜，"
                       "挂贵的见证等于没挂" % (k, t, wit))
            continue
        if rc != 0:
            out.append("`%s` 见证**命令报错**（rc=%s）：`%s` —— 见证命令本身死了"
                       "（见证要便宜、无害、只读）" % (k, rc, wit))
            continue
        got = stdout.strip()
        want = str(expect) if expect is not None else ""
        if got != want:
            out.append("`%s` 见证不符：witness=%s vs 期望=%s —— 来源/上下文"
                       "漂移（产出它的工具/输入变了），值本身没变也**算事故**"
                       % (k, _q(got), _q(want)))
            continue
        stats["witnessed"] += 1
    if not stats["attempts"] and stats["skipped"] and not stats["witness_attempts"]:
        out.append("全部 %d 条事实都声明 replay=False 且无见证 ⇒ 本闸门什么都没查 —— "
                   "至少留一条能复跑的；贵事实挂 witness（issue #5）让它"
                   "的来源每提交被核；整仓都不适用就设 REFLECT_REPLAY=off 明说"
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
    wtail = "，见证 %d 条" % r["witnessed"] if r["witnessed"] else ""
    print("复跑闸门：OK（%d 条事实逐字复跑，stdout 与台账一致%s%s）"
          % (r["ok"], tail, wtail))
    return 0


LED = {"facts": {"n": {"value": 12, "cmd": "c"}}}


def _cases():
    multi = {"facts": {"a": {"value": 1, "cmd": "ca"},
                       "b": {"value": 2, "cmd": "cb", "replay": False}}}
    wit = {"facts": {"expensive": {"value": "bench-42", "cmd": "run-bench",
                                    "replay": False,
                                    "witness": "echo tool-ok",
                                    "witness_expect": "tool-ok"}}}
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
        ("★ stdout ≠ 台账值 ⇒ 必须报，且报错指向重测（issue #4 ③）",
         lambda: any("不符" in x and "重测" in x and "accept-changes" in x for x in
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
        # ③ 见证档（issue #5）
        ("贵事实挂见证：见证过 ⇒ 不报",
         lambda: replay_all(wit, runner=lambda c: (0, "tool-ok"))["problems"] == []),
        ("贵事实挂见证 ⇒ 计入 witnessed（run() 输出用）",
         lambda: replay_all(wit, runner=lambda c: (0, "tool-ok"))["witnessed"] == 1),
        ("★ 见证不符 ⇒ 必须报（来源漂移，值没变也算事故）",
         lambda: any("见证不符" in x for x in
                       replay_all(wit, runner=lambda c: (0, "tool-CHANGED"))["problems"])),
        ("★ 见证命令 rc≠0 ⇒ 必须报（见证命令本身死了）",
         lambda: any("见证**命令报错" in x for x in
                       replay_all(wit, runner=lambda c: (1, ""))["problems"])),
        ("★ 见证超时 ⇒ 必须报（见证该便宜，挂贵的见证等于没挂）",
         lambda: any("见证**超时" in x for x in
                       replay_all(wit, runner=lambda c: (None, ""))["problems"])),
        ("★ 全部 replay=False 但都挂见证 ⇒ 不报「什么都没查」（守卫跟着调）",
         lambda: not any("什么都没查" in x for x in
                           replay_all(wit, runner=lambda c: (0, "tool-ok"))["problems"])),
    ]


if __name__ == "__main__":
    sys.exit(selftest("check_facts_replay（台账 cmd 逐字复跑：stdout 必须等于值）", _cases())
             if "--selftest" in sys.argv else run(sys.argv[1:]))
