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
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from gate import (
    machine,  # noqa: E402
    module_meta,  # noqa: E402
)
from i18n import M  # noqa: E402


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


def _shell_argv(cmd):
    """把一条 `cmd` 包装成「哪个 shell 能跑它」的 argv。

    三档，**强度随环境下降这件事必须可见**（不静默）：

      1. `bash -o pipefail -c` —— 最好：管道里任一环失败都带出来
         （`cat 没了 | wc -l` 打印 0 且 rc=0 的那种「失败但绿」正是要杀的）。
      2. `/bin/sh -c` —— 没有 bash 的系统（部分容器 / 精简发行版）。
         没有 `pipefail`，所以**管道中间的失败可能丢**。
      3. **Windows**：没有 `bash` 也没有 `/bin/sh`。回落到 `cmd.exe`——
         它能跑本仓台账里的那些 `python3 ...` / `git ...` 单命令，
         但不支持 POSIX 管道语义（`|` 会被 cmd 解释成管道，但 `$(...)` 等不认）。

    返回 `(argv, 强度标签)`；标签写进 `EINFACHT_REPLAY_SHELL` 供诊断。
    """
    bash = shutil.which("bash")
    if bash:
        return [bash, "-o", "pipefail", "-c", _python_of(cmd)], "bash"
    if os.name != "nt" and os.path.exists("/bin/sh"):
        return ["/bin/sh", "-c", _python_of(cmd)], "sh"
    # Windows（或极端精简的 POSIX）：用系统 shell
    return [os.environ.get("COMSPEC", "cmd.exe"), "/c", _python_of(cmd)], "cmd"


# 台账里的 `cmd` 一律用 `python3`（惯用写法，Linux/macOS 上就是它）。
# Windows 上没有 `python3` 这个名字（setup-python 给的是 `python.exe`）——
# 所以在这里把**开头的 `python3`** 换成**当前解释器**。
#
# 为什么这不是作弊：`python3 <脚本>` 的语义是「用这个仓的 Python 跑它」，
# 换成 `sys.executable` 是同一件事的当前进程版本。而且台账 `cmd` 的契约是
# **逐字复跑**（`stdout == value`），不是「逐字执行同一条命令」—— 值才是判据。
_PY_CMD = re.compile(r"^\s*python3(?=\s)")


def _python_of(cmd):
    """把行首的 `python3` 换成当前解释器（Windows 兼容）；其余原样。

    ⚠️ 顺带把紧随其后的 `zreflect/<script>` 解析成**工具仓的绝对路径**。
    为什么必须：台账 `cmd` 里的 `zreflect/facts.py` 是**相对路径**，而
    `run_cmd` 的 cwd 是**被检查仓**（`gate.GATE_REPO`）。两者一致时没问题
    （自己量自己），不一致时（套件被拷到别处、或夹具仓只造数据）复跑就
    `No such file` —— 而错误信息会指向「命令失败」，不是「路径解析错了」。
    实测：harness 的换名夹具就撞上这个。
    """
    interp = ('"%s"' % sys.executable
              if " " in sys.executable else sys.executable)
    out = _PY_CMD.sub(lambda _m: interp, cmd, count=1)
    return _TOOL_REL.sub(
        lambda m: '"%s"' % os.path.join(gate.tool_repo(), m.group(1)),
        out, count=1)


# 行首 `python3` 之后的 `zreflect/<script>`（工具仓相对路径）
_TOOL_REL = re.compile(r"(?<!\w)(zreflect/[A-Za-z_][A-Za-z0-9_]*\.py)")


def run_cmd(cmd, timeout=None):
    """逐字跑一条 `cmd`（cwd=仓库根），返回 (返回码, stdout)。超时 ⇒ 返回码 None。

    ⚠️ **Windows 上没有 bash 也没有 `/bin/sh`**：此前这里硬写
    `["/bin/sh", "-c", cmd]`，于是 CI 的 Windows 腿每条 cmd 都 OSError 127。
    现在由 `_shell_argv` 分三档，并把实际用的是哪一档写进
    `EINFACHT_REPLAY_SHELL`（`bash` / `sh` / `cmd`）—— 判据强度随环境变化，
    不许静默。
    """
    t = default_timeout() if timeout is None else timeout
    argv, shell_kind = _shell_argv(cmd)
    # ⚠️ **环守卫的跨进程那一半**：把深度传给子进程。一条 cmd 可以是另一个
    # 闸门（复用），而那个闸门可能又触发复跑 —— 没有这个变量，环会无限
    # spawn 直到 OOM（实测）。深度上限由复跑器判（`_MAX_DEPTH`）。
    env = dict(os.environ)
    env["EINFACHT_REPLAY_SHELL"] = shell_kind
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
    import os  # noqa: PLC0415
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
        # **`python3` 前缀在 Windows 上不存在**（`setup-python` 给的是
        # `python.exe`）—— 台账 `cmd` 一律写 `python3`，所以执行前要换成
        # 当前解释器。这条钉住三条边界：只改行首、不误伤 `python3x`、
        # 不碰中段的同名串。
        ("\u2605 runner.python3_prefix_rewritten",
         lambda: _python_of("python3 x.py") != "python3 x.py"
         and _python_of("python3 x.py").endswith(" x.py")),
        ("\u2605 runner.python3x_untouched",
         lambda: _python_of("python3x foo") == "python3x foo"),
        ("\u2605 runner.python3_midstring_untouched",
         lambda: _python_of("echo 'python3 x'") == "echo 'python3 x'"),
        # ③ 空输入必须报（对 runner 而言，「空」是空输出/空命令的形状）
        ("★ runner.quote_empty_is_visible",
         lambda: quote("") == "''"),
        ("★ runner.empty_command_not_a_pass",
         lambda: run_cmd("")[1] == ""),
    ]


def _selftest():
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gate import main_selftest_or  # noqa: PLC0415

    def _run(argv):
        print(M("runner.module_banner"), file=sys.stderr)
        return 2
    return main_selftest_or(sys.argv[1:],
                            M("gate.title.runner"),
                            _cases, _run)


MODULE = module_meta("逐字执行器", "裸值契约的公共 seam（复跑 / world 印章共用）", selftest=True)


if __name__ == "__main__":
    sys.exit(_selftest())
