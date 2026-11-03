#!/usr/bin/env python3
"""逐字执行器（裸值契约的 runner，**公共 seam**）。

「逐字跑一条命令、stdout 去掉首尾空白后必须等于期望值」是本仓最重要的
interface 之一 —— 复跑闸门（台账 `cmd`，issue #2 ①）与 world 印章（环境
对账，issue #13）都是它的 adapter。「两个 adapter = 真实 seam」：它原本
住在 check_facts_replay 的私有区，check_world 掏邻居的下划线名字来用
（docstring 自称「嫁接」）—— 现在归位成 module，闸门之间不再互掏私有。

判据（`cmd` 逐字执行，cwd = 仓库根）：

  · **裸值契约**：stdout 去掉首尾空白后必须**等于**期望 —— 只打印
    「含该值的整行」人眼可读、机器不可判，各 adapter 自己报不符；
  · rc≠0 / 超时 / OSError 都**不算通过** —— 返回 (rc, stdout) 让
    adapter 决定措辞（超时 ⇒ rc=None）；
  · 管道不吞错：有 bash 用 `bash -o pipefail -c`（`cat 没了 | wc -l`
    打印 0 且 rc=0 的那种「失败但绿」正是要抓的东西），没有 bash 退回
    /bin/sh —— 判据强度随环境变化这件事，不许静默；
  · 超时默认 `REFLECT_REPLAY_TIMEOUT`（10s）：挂在 pre-commit 里的
    命令不该永远等不到。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate                                            # noqa: E402
from gate import module_meta                          # noqa: E402
from gate import machine                                  # noqa: E402
from i18n import M                                                    # noqa: E402



def default_timeout():
    """逐字执行的默认超时秒数（`REFLECT_REPLAY_TIMEOUT`；坏值 ⇒ 默认 10）。"""
    try:
        return float(os.environ.get("REFLECT_REPLAY_TIMEOUT", "10"))
    except ValueError:
        return 10.0


def quote(s, n=60):
    """把一段输出缩成可引用的 repr（复现事故时别把 1 MiB stdout 糊进终端）。"""
    t = s if len(s) <= n else s[:n] + "…"
    return repr(t)


def run_cmd(cmd, timeout=None):
    """逐字跑一条 `cmd`（cwd=仓库根），返回 (返回码, stdout)。超时 ⇒ 返回码 None。"""
    t = default_timeout() if timeout is None else timeout
    bash = shutil.which("bash")
    argv = [bash, "-o", "pipefail", "-c", cmd] if bash else ["/bin/sh", "-c", cmd]
    # ⚠️ **环守卫的跨进程那一半**：把深度传给子进程。一条 cmd 可以是另一个
    # 闸门（复用），而那个闸门可能又触发复跑 —— 没有这个变量，环会无限
    # spawn 直到 OOM（实测）。深度上限由复跑器判（`_MAX_DEPTH`）。
    env = dict(os.environ)
    try:
        env["EINFACHT_REPLAY_DEPTH"] = str(
            int(os.environ.get("EINFACHT_REPLAY_DEPTH", "0") or 0) + 1)
    except ValueError:
        env["EINFACHT_REPLAY_DEPTH"] = "1"
    try:
        p = subprocess.run(argv, cwd=gate.GATE_REPO, capture_output=True, text=True,
                           timeout=t, env=env)
    except subprocess.TimeoutExpired:
        return None, ""
    except OSError as e:                # 连 shell 起不来 —— 报成失败，不许算通过
        return 127, machine().emit("fatal", e)
    return p.returncode, p.stdout


def _timeout_falls_back():
    """`REFLECT_REPLAY_TIMEOUT` 是坏值 ⇒ 必须回落 10.0（不是 raise）。"""
    import os                                            # noqa: PLC0415
    prev = os.environ.get("REFLECT_REPLAY_TIMEOUT")
    try:
        os.environ["REFLECT_REPLAY_TIMEOUT"] = "not-a-number"
        return default_timeout() == 10.0
    finally:
        if prev is None:
            os.environ.pop("REFLECT_REPLAY_TIMEOUT", None)
        else:
            os.environ["REFLECT_REPLAY_TIMEOUT"] = prev


def _cases():
    """三档自证（真跑 shell —— runner 的判据就是 shell 行为，假 runner 自证
    runner 是循环论证；但命令都是 echo/printf/false，无副作用、无网络）。"""
    return [
        # ① 正常不报
        ("runner.echo_rc0",
         lambda: run_cmd("echo hello") == (0, "hello\n")),
        ("runner.stdout_newline_preserved",
         lambda: run_cmd("printf 'v1'") == (0, "v1")),
        # ② 该报的必须报
        ("★ runner.nonzero_rc_passthrough",
         lambda: run_cmd("exit 3")[0] == 3),
        ("★ runner.pipefail_catches_swallowed_error",
         lambda: run_cmd("false | cat")[0] != 0),
        ("★ runner.timeout_rc_none",
         lambda: run_cmd("sleep 5", timeout=0.3)[0] is None),
        ("★ runner.missing_command_not_a_pass",
         lambda: run_cmd("definitely_not_a_command_xyz")[0] != 0),
        # quote 的截断（复现事故时不糊终端）
        ("runner.quote_truncates_long",
         lambda: quote("a" * 100).endswith("…'")),
        ("runner.quote_keeps_short",
         lambda: quote("ok") == "'ok'"),
        # 稳态：`default_timeout()` 读到坏值时必须回落 10（不是崩）
        ("runner.default_timeout_bad_value_falls_back",
         lambda: _timeout_falls_back()),
        # ③ 空输入必须报（对 runner 而言，「空」是空输出/空命令的形状）
        ("★ runner.quote_empty_is_visible",
         lambda: quote("") == "''"),
        ("★ runner.empty_command_not_a_pass",
         lambda: run_cmd("")[1] == ""),
    ]


def _selftest():
    import os                                            # noqa: PLC0415
    import sys                                           # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gate import main_selftest_or                    # noqa: PLC0415

    def _run(argv):
        print(M("runner.module_banner"), file=sys.stderr)
        return 2
    return main_selftest_or(sys.argv[1:],
                            M("gate.title.runner"),
                            _cases, _run)


MODULE = module_meta("逐字执行器", "裸值契约的公共 seam（复跑 / world 印章共用）", selftest=True)


if __name__ == "__main__":
    sys.exit(_selftest())
