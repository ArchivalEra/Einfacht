#!/usr/bin/env python3
"""Verbatim executor (bare-value-contract runner, **public seam**).

The replay gate (ledger `cmd`) and the world stamp (environment
reconciliation) are both adapters over this interface: "run a command
verbatim, and stdout stripped of leading/trailing whitespace must equal the
expected value".

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
    """Wrap `cmd` as `(argv, tier)` (`bash -o pipefail`, `/bin/sh`, or `(None, 'no-shell')`)."""
    bash = shutil.which("bash")
    if bash:
        return [bash, "-o", "pipefail", "-c", _python_of(cmd)], "bash"
    if os.name != "nt" and os.path.exists("/bin/sh"):
        return ["/bin/sh", "-c", _python_of(cmd)], "sh"
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
    """Subprocess emitting UTF-8 CJK returns a decoded str from `run_cmd`."""
    cmd = ('python3 -c "import sys;'
           'sys.stdout.reconfigure(encoding=\'utf-8\');'
           'print(chr(0x95F8) + chr(0x95E8))"')
    rc, out = run_cmd(cmd)
    return rc == 0 and isinstance(out, str) and out.strip() != ""


def run_cmd(cmd, timeout=None):
    """Run `cmd` verbatim in `gate.GATE_REPO`; returns `(returncode, stdout)` (`None` on timeout)."""
    t = default_timeout() if timeout is None else timeout
    argv, shell_kind = _shell_argv(cmd)
    if argv is None:
        argv = _windows_argv(_python_of(cmd))
    env = dict(os.environ)
    try:
        env["EINFACHT_REPLAY_DEPTH"] = str(
            int(os.environ.get("EINFACHT_REPLAY_DEPTH", "0") or 0) + 1)
    except ValueError:
        env["EINFACHT_REPLAY_DEPTH"] = "1"
    try:
        p = subprocess.run(argv, cwd=gate.GATE_REPO, capture_output=True, text=True,
                           errors="replace", timeout=t, env=env,
                           encoding="utf-8")
    except subprocess.TimeoutExpired:
        return None, ""
    except OSError as e:
        return 127, machine().emit(
            "fatal", "%s [shell=%s argv=%r]" % (e, shell_kind, argv[:2]))
    if p.returncode != 0 and p.stderr:
        return p.returncode, (p.stdout or "") + p.stderr
    if p.stdout is None:
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
    """Shell runner selftest cases."""
    return [
        ("runner.echo_rc0",
         lambda: run_cmd("echo hello") == (0, "hello\n")),
        ("runner.stdout_newline_preserved",
         lambda: run_cmd("printf 'v1'") == (0, "v1")),
        ("★ runner.nonzero_rc_passthrough",
         lambda: run_cmd("exit 3")[0] == 3),
        ("★ runner.pipefail_catches_swallowed_error",
         lambda: run_cmd("false | cat")[0] != 0),
        ("★ runner.timeout_rc_none",
         lambda: run_cmd("sleep 5", timeout=0.3)[0] is None),
        ("★ runner.missing_command_not_a_pass",
         lambda: run_cmd("definitely_not_a_command_xyz")[0] != 0),
        ("runner.quote_truncates_long",
         lambda: quote("a" * 100).endswith("...'")),
        ("runner.quote_keeps_short",
         lambda: quote("ok") == "'ok'"),
        ("runner.default_timeout_bad_value_falls_back",
         lambda: _timeout_falls_back()),
        ("\u2605 runner.python3_prefix_rewritten",
         lambda: _python_of("python3 x.py") != "python3 x.py"
         and _python_of("python3 x.py").endswith(" x.py")),
        ("\u2605 runner.python3x_untouched",
         lambda: _python_of("python3x foo") == "python3x foo"),
        ("\u2605 runner.python3_midstring_untouched",
         lambda: _python_of("echo 'python3 x'") == "echo 'python3 x'"),
        ("★ runner.windows_argv_strips_quotes",
         lambda: _windows_argv('"C:\\Program Files\\Py\\python.exe" x.py')
         == ["C:\\Program Files\\Py\\python.exe", "x.py"]),
        ("★ runner.windows_argv_keeps_backslashes",
         lambda: _windows_argv("a\\b c") == ["a\\b", "c"]),
        ("\u2605 runner.non_local_encoding_output_survives",
         lambda: _non_local_encoding_ok()),
        ("★ runner.quote_empty_is_visible",
         lambda: quote("") == "''"),
        ("★ runner.empty_command_not_a_pass",
         lambda: run_cmd("")[1] == ""),
    ]


def _selftest():
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
