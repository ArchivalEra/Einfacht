#!/usr/bin/env python3
"""Verbatim executor (bare-value-contract runner, **public seam**).

"Run a command verbatim, and stdout stripped of leading/trailing whitespace
must equal the expected value" is one of the repo's most important interfaces
-- the replay gate (ledger `cmd`, issue #2 (1)) and the world stamp (environment
reconciliation, issue #13) are both adapters over it. "Two adapters = a real
seam": this used to live in check_facts_replay's private section, and
check_world reached into its neighbor's underscore name to use it (its own
docstring called the maneuver a "graft") -- it is now promoted to a module,
so gates no longer pick each other's privates.

Criteria (`cmd` runs verbatim, cwd = repo root):

  · **Bare-value contract**: stdout stripped of leading/trailing whitespace
    must **equal** the expected value -- printing "the whole line that contains
    the value" is readable by humans but not judgeable by machines; each
    adapter reports mismatches itself;
  · rc!=0 / timeout / OSError all **do not count as a pass** -- return
    (rc, stdout) and let the adapter choose the wording (timeout => rc=None);
  · pipes must not swallow errors: with bash use `bash -o pipefail -c`
    (the "fails but green" shape where `cat is gone | wc -l` prints 0 with
    rc=0 is exactly what this catches); without bash fall back to /bin/sh --
    criteria strength varying with the environment must never happen silently;
  · timeout defaults to `REFLECT_REPLAY_TIMEOUT` (10s): a command wired into
    pre-commit must not wait forever.
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
    """Default timeout seconds for verbatim execution (`REFLECT_REPLAY_TIMEOUT`; bad value => default 10)."""
    seconds, _bad = timeout_with_status()
    return seconds


def timeout_with_status():
    """Return `(seconds, bad_value)`.

    Unset (including empty) or a valid float => `(value, None)`. An invalid
    value => `(10.0, raw)`, where `raw` is the original string, so the caller
    decides whether to report it. Parsing lives only here.
    """
    raw = os.environ.get("REFLECT_REPLAY_TIMEOUT")
    if raw is None or not raw.strip():
        return 10.0, None                     # unset (incl. empty string) = normal default
    try:
        return float(raw), None
    except ValueError:
        return 10.0, raw                      # bad value: fall back + carry the original out


def quote(s, n=60):
    """Shrink a chunk of output into a quotable repr (don't smear 1 MiB of stdout into the terminal while reproducing an incident)."""
    t = s if len(s) <= n else s[:n] + "..."
    return repr(t)


def _shell_argv(cmd):
    """Wrap `cmd` into `(argv, strength label)` for the first available shell.

    Tiers, in order: `bash -o pipefail -c` (pipe failures propagate);
    `/bin/sh -c` (no pipefail: a failure in the middle of a pipe can be lost);
    `(None, "no-shell")` on Windows, where the caller must build an argv itself.
    The label is carried into `run_cmd` diagnostics as `[shell=...]`; the drop
    in strength must never be silent.
    """
    bash = shutil.which("bash")
    if bash:
        return [bash, "-o", "pipefail", "-c", _python_of(cmd)], "bash"
    if os.name != "nt" and os.path.exists("/bin/sh"):
        return ["/bin/sh", "-c", _python_of(cmd)], "sh"
    # Windows: **no shell at all** -- `_windows_argv` splits it into an argv.
    #
    # ⚠️ Going through `cmd.exe /c` lands you in quote hell: `sys.executable`
    # usually lives in `C:/Program Files/...` (with spaces), and cmd strips
    # the outer quotes then re-splits => **127 command not found**. Observed:
    # all 19 replay entries on CI's Windows leg went red right here.
    #
    # ⚠️ `shlex.split` is no good either: `posix=False` **keeps the quotes**
    # (a quoted path gets passed to CreateProcess verbatim => file not found);
    # `posix=True` eats the backslashes of `C:/Program Files` as escapes.
    # Both wrong. See `_windows_argv`.
    return None, "no-shell"


_QUOTED = re.compile(r'"([^"]*)"|(\S+)')


def _windows_argv(cmd):
    """Split `cmd` into an argv on Windows, with no shell in between.

    Double-quoted text is kept verbatim (spaces and backslashes included);
    everything else splits on whitespace. Backslashes are never treated as
    escapes. Shell syntax (`|`, `&&`, redirections) is not supported: every
    ledger `cmd` is a single command.
    """
    return [m.group(1) if m.group(1) is not None else m.group(2)
            for m in _QUOTED.finditer(cmd)]


# The ledger's `cmd` values always use `python3` (the conventional spelling,
# which on Linux/macOS is exactly what runs). Windows has no `python3` name
# (setup-python provides `python.exe`) -- so the **leading `python3`** is
# rewritten to the **current interpreter** here.
#
# Why this is not cheating: `python3 <script>` means "run it with this repo's
# Python"; substituting `sys.executable` is the same thing, current-process
# edition. And the ledger `cmd` contract is **verbatim re-run of the value**
# (`stdout == value`), not "execute the identical command line" -- the value
# is the criterion.
_PY_CMD = re.compile(r"^\s*python3(?=\s)")


def _python_of(cmd):
    """Rewrite a leading `python3` to the current interpreter (quoted), and rewrite
    a `zreflect/<script>.py` to an absolute path under the tool repo. Everything
    else is passed through verbatim.

    Both rewrites are required: Windows has no `python3` name, and `run_cmd`
    runs with cwd = the audited repo, not the tool repo.
    """
    interp = _quote_for_shell(sys.executable)
    out = _PY_CMD.sub(lambda _m: interp, cmd, count=1)
    return _TOOL_REL.sub(
        lambda m: _quote_for_shell(os.path.join(gate.tool_repo(), m.group(1))),
        out, count=1)


# Characters a shell gives "meaning" to: whitespace (word splitting),
# backslash (escaping -- in POSIX sh the backslashes in `C:/hosted` get eaten
# into `C:hosted`), shell metacharacters.
_NEEDS_QUOTING = re.compile(r"""[\s\\$`"'|&;<>()*?{}\[\]#~]""")


def _quote_for_shell(path):
    """Quote a path so no shell can misread it.

    A path containing whitespace, a backslash, or a shell metacharacter is
    wrapped in single quotes; if it contains a single quote, double quotes are
    used with `"` escaped. Paths needing no quoting are returned unchanged.
    """
    if not _NEEDS_QUOTING.search(path):
        return path
    # In POSIX sh, single quotes are the safest (nothing is interpreted);
    # but a Windows path may contain a single quote (extremely rare) -- that
    # one time use double quotes + escaping.
    if "'" not in path:
        return "'%s'" % path
    return '"%s"' % path.replace('"', '\\"')


# The `zreflect/<script>` after a leading `python3` (tool-repo relative path)
_TOOL_REL = re.compile(r"(?<!\w)(zreflect/[A-Za-z_][A-Za-z0-9_]*\.py)")


def _non_local_encoding_ok():
    """When a subprocess prints bytes in a **non-local encoding**, `run_cmd` must still get a str.

    Method: make the subprocess emit bytes that are **guaranteed absent from
    cp1252** (Chinese), and disguise the local environment as cp1252 --
    `PYTHONIOENCODING` alone is not enough (it governs the subprocess's
    **output**); the real criterion is the parent process's **decoding**.
    This directly verifies that `run_cmd` returns a str, not None, when the
    subprocess spits UTF-8 Chinese.
    """
    cmd = ('python3 -c "import sys;'
           'sys.stdout.reconfigure(encoding=\'utf-8\');'
           'print(chr(0x95F8) + chr(0x95E8))"')
    rc, out = run_cmd(cmd)
    return rc == 0 and isinstance(out, str) and out.strip() != ""


def run_cmd(cmd, timeout=None):
    """Run a `cmd` verbatim (cwd=repo root), returning (returncode, stdout). Timeout => returncode None.

    ⚠️ **On Windows there is neither bash nor `/bin/sh`**: this used to
    hard-code `["/bin/sh", "-c", cmd]`, so every cmd on CI's Windows leg died
    with OSError 127. `_shell_argv` now splits it into three tiers, and the
    tier that actually ran rides along in the failure diagnostics
    (`[shell=...]`) -- criteria strength varying with the environment must
    never happen silently.
    """
    t = default_timeout() if timeout is None else timeout
    argv, shell_kind = _shell_argv(cmd)
    if argv is None:
        argv = _windows_argv(_python_of(cmd))
    # ⚠️ **The cross-process half of the cycle guard**: pass the depth to the
    # child. A cmd can be another gate (reused), and that gate may itself
    # trigger a re-run -- without this variable, the cycle spawns without end
    # until OOM (observed). The depth cap is judged by the replay gate
    # (`_MAX_DEPTH`).
    env = dict(os.environ)
    try:
        env["EINFACHT_REPLAY_DEPTH"] = str(
            int(os.environ.get("EINFACHT_REPLAY_DEPTH", "0") or 0) + 1)
    except ValueError:
        env["EINFACHT_REPLAY_DEPTH"] = "1"
    try:
        # ⚠️ **`errors="replace"` must be explicit**: `text=True` decodes with
        # `locale.getpreferredencoding()`, and Windows defaults to cp1252.
        # The moment a subprocess emits non-cp1252 bytes (this repo's gates
        # print Chinese), the reader thread raises `UnicodeDecodeError` --
        # **outside the main thread** -- so `p.stdout` becomes None, downstream
        # `stdout.strip()` reports `AttributeError`, and the traceback shows
        # only one line: `Exception in thread Thread-N (_readerthread)`.
        # Observed: CI's Windows leg crashed on this layer for two rounds
        # in a row.
        p = subprocess.run(argv, cwd=gate.GATE_REPO, capture_output=True, text=True,
                           errors="replace", timeout=t, env=env,
                           encoding="utf-8")
    except subprocess.TimeoutExpired:
        return None, ""
    except OSError as e:                # even the shell won't start -- report as failure, never a pass
        # Diagnostics: carry the **actual argv** into the error. 127 can only
        # mean "the first element is not an executable" -- without spelling out
        # the argv, all you can do is guess (observed: CI's Windows leg
        # reported 19 failures with 127, never reproducible locally).
        return 127, machine().emit(
            "fatal", "%s [shell=%s argv=%r]" % (e, shell_kind, argv[:2]))
    # ⚠️ **`p.stdout` can be `None`**: `capture_output=True` usually
    # guarantees a str, but on Windows, if the subprocess dies early on a
    # decode failure, `subprocess` leaves `stdout` as None -- so downstream
    # `stdout.strip()` throws
    # `AttributeError: 'NoneType' object has no attribute 'strip'`
    # (observed: that is exactly how CI's Windows leg went red, with the
    # error pointing at `_judge_ok`, three layers away from the true cause).
    if p.returncode != 0 and p.stderr:
        # ⚠️ **On failure, stderr must be carried out**: `run_cmd` used to
        # return stdout only, so "the command crashed" and "the command
        # correctly reported a problem" were indistinguishable -- both are a
        # rc!=0 plus an empty stdout. Observed: CI's Windows leg reported
        # `command_failed(rc=1)` with **no visible reason**, pure guessing.
        # Concatenating into stdout is safe: the caller only compares stdout
        # against the value when rc==0.
        return p.returncode, (p.stdout or "") + p.stderr
    if p.stdout is None:
        # Diagnostics: when stdout is None, carry stderr / argv into the
        # result; don't let downstream see a bare `AttributeError`.
        return p.returncode, machine().emit(
            "fatal", "stdout=None rc=%s shell=%s argv=%r stderr=%r"
            % (p.returncode, shell_kind, argv[:2], (p.stderr or "")[:200]))
    return p.returncode, p.stdout


def _timeout_falls_back():
    """`REFLECT_REPLAY_TIMEOUT` is a bad value => must fall back to 10.0 (not raise)."""
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
    """Three-tier self-evidence (really runs the shell -- the runner's criterion is shell behavior, so a fake runner self-certifying the runner would be circular; but the commands are all echo/printf/false: no side effects, no network)."""
    return [
        # (1) normal: no report
        ("runner.echo_rc0",
         lambda: run_cmd("echo hello") == (0, "hello\n")),
        ("runner.stdout_newline_preserved",
         lambda: run_cmd("printf 'v1'") == (0, "v1")),
        # (2) what must be reported gets reported
        ("★ runner.nonzero_rc_passthrough",
         lambda: run_cmd("exit 3")[0] == 3),
        ("★ runner.pipefail_catches_swallowed_error",
         lambda: run_cmd("false | cat")[0] != 0),
        ("★ runner.timeout_rc_none",
         lambda: run_cmd("sleep 5", timeout=0.3)[0] is None),
        ("★ runner.missing_command_not_a_pass",
         lambda: run_cmd("definitely_not_a_command_xyz")[0] != 0),
        # quote truncation (no terminal smear while reproducing an incident)
        ("runner.quote_truncates_long",
         lambda: quote("a" * 100).endswith("...'")),
        ("runner.quote_keeps_short",
         lambda: quote("ok") == "'ok'"),
        # Steady state: `default_timeout()` must fall back to 10 on a bad value (not crash)
        ("runner.default_timeout_bad_value_falls_back",
         lambda: _timeout_falls_back()),
        # **The `python3` prefix does not exist on Windows** (`setup-python`
        # provides `python.exe`) -- ledger `cmd` values always say `python3`,
        # so it is rewritten to the current interpreter before execution.
        # This case pins three boundaries: only at line start, no false hit on
        # `python3x`, and same-named strings mid-command are untouched.
        ("\u2605 runner.python3_prefix_rewritten",
         lambda: _python_of("python3 x.py") != "python3 x.py"
         and _python_of("python3 x.py").endswith(" x.py")),
        ("\u2605 runner.python3x_untouched",
         lambda: _python_of("python3x foo") == "python3x foo"),
        ("\u2605 runner.python3_midstring_untouched",
         lambda: _python_of("echo 'python3 x'") == "echo 'python3 x'"),
        # **The Windows tier must not hand quotes to CreateProcess**: a quoted
        # path is treated as a literal filename (not found), and
        # `shlex.split(posix=False)` happens to keep the quotes.
        # Observed: all 19 replay entries on CI's Windows leg went red here.
        ("★ runner.windows_argv_strips_quotes",
         lambda: _windows_argv('"C:\\Program Files\\Py\\python.exe" x.py')
         == ["C:\\Program Files\\Py\\python.exe", "x.py"]),
        ("★ runner.windows_argv_keeps_backslashes",
         lambda: _windows_argv("a\\b c") == ["a\\b", "c"]),
        # **When a subprocess outputs a non-local encoding, the reader thread
        # must not crash silently**: `text=True` decodes with the local
        # encoding, Windows defaults to cp1252, and this repo's gates print
        # Chinese => the reader thread raises UnicodeDecodeError (**outside the
        # main thread**) => `p.stdout` is None => downstream `stdout.strip()`
        # reports AttributeError, with only one line in the log:
        # `Exception in thread Thread-N (_readerthread)`.
        ("\u2605 runner.non_local_encoding_output_survives",
         lambda: _non_local_encoding_ok()),
        # (3) empty input must be reported (for the runner, "empty" is the shape of empty output / an empty command)
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


MODULE = module_meta("Verbatim executor", "public seam of the bare-value contract (shared by replay / world stamp)", selftest=True)


if __name__ == "__main__":
    sys.exit(_selftest())
