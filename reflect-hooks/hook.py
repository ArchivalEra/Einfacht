#!/usr/bin/env python3
"""Hook entry point: **meant to be called by other hook systems**; it never
takes over hook slots.

`git config core.hooksPath` is git's **global override switch** -- once it is
set, git **stops looking at** `.git/hooks/` entirely, so husky / lefthook /
pre-commit (Python) / handwritten hooks are all **silently disabled** (the
"deployed does not mean running" state this repo exists to eliminate).

So this repo only **exposes one mouth**: any hook system can call this line
from its own hook. Hook locations, ordering, other tools -- all yours; we
provide the criteria and never take the seat.

    Usage (from any hook script):
        python3 <repo>/reflect-hooks/hook.py commit "$(git rev-parse --show-toplevel)"
        python3 <repo>/reflect-hooks/hook.py push   "$(git rev-parse --show-toplevel)"

    commit  re-render the machine block (and `git add`) + run every gate with
            runs_at="commit"
    push    verify only, modify nothing: the machine block must be fresh + all
            gates + trilingual READMEs in the same batch

    Exit codes: 0 = green; 1 = criterion red (reject); 2 = environment/config
    broken.

Python keeps the entry inside `check_i18n`'s AST-scanned surface (shell output
is invisible to it), avoids depending on `sh` on Windows, and makes pre-push's
text-parsing ref protocol explicit.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TOOL_REPO, "zreflect"))

import knobs  # noqa: E402
from gate import activate_or_fatal, meta  # noqa: E402
from i18n import M  # noqa: E402

ZERO_SHA = "0" * 40
PHASES = ("commit", "push")


def _sh(cmd, stdin=None, env=None):
    """Run one command, return `(rc, merged output)`."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, input=stdin,
                           env=env,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "hook: %r" % (e,)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _usage():
    print(str(M("hookgate.usage")), file=sys.stderr)
    return 0


def _refs_from_stdin():
    """git's pre-push ref protocol: each line is
    `<local ref> <local sha> <remote ref> <remote sha>`."""
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    except (OSError, ValueError):
        return []
    rows = []
    for ln in raw.splitlines():
        parts = ln.split()
        if len(parts) == 4:
            rows.append(tuple(parts))
    return rows


def _new_content_refs(repo, refs):
    """Filter the ref-protocol lines down to "branches actually publishing
    new content this time"; returns `[(lref, revs)]`."""
    out = []
    for lref, lsha, _rref, rsha in refs:
        if lref.startswith("refs/tags/"):
            continue                       # tags carry no new content
        if lsha == ZERO_SHA:
            continue                       # branch deletion
        if rsha == ZERO_SHA:
            rc, revs = _sh(["git", "-C", repo, "rev-list", lsha,
                            "--not", "--remotes"])
            revs = revs.strip() if rc == 0 else ""
        else:
            rc, _o = _sh(["git", "-C", repo, "rev-list", "%s..%s" % (rsha, lsha)])
            revs = "%s..%s" % (rsha, lsha) if rc == 0 else lsha
        out.append((lref, revs.strip()))
    return out


def _push_readmes_together(repo, refs):
    """pre-push third check: this push must update the trilingual READMEs in
    the same batch. Returns (ok, lines)."""
    import tempfile  # noqa: PLC0415
    lines = []
    refs_with_content = _new_content_refs(repo, refs)
    if not refs_with_content:
        lines.append(str(M("hookgate.push_nothing_to_check")))
        return True, lines
    checked = 0
    for lref, revs in refs_with_content:
        if not revs:
            lines.append(str(M("hookgate.ref_has_nothing", ref=lref)))
            checked += 1
            continue
        rev_args = [r for r in revs.splitlines() if r.strip()]
        rc, log = _sh(["git", "-C", repo, "log", "--name-only",
                       "--pretty=format:", *rev_args])
        changed = [ln for ln in (log or "").splitlines() if ln.strip()]
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("\n".join(changed) + "\n")
            rc, out = _sh([sys.executable,
                           os.path.join(repo, "zreflect", "check_readme_sync.py"),
                           "--changed", path])
            if rc != 0:
                lines.append(str(M("hookgate.push_readmes_not_together",
                                   ref=lref)))
                lines.extend(ln for ln in (out or "").splitlines()[:5])
                return False, lines
        finally:
            os.unlink(path)
        checked += 1
    lines.append(str(M("hookgate.push_readmes_ok", count=checked)))
    return True, lines


def _has_unstaged_facts(repo):
    """Does `FACTS.json` have unstaged changes in `repo`?"""
    facts_rel = knobs.get("REFLECT_FACTS", root=repo)
    if not os.path.isfile(os.path.join(repo, facts_rel)):
        return False, facts_rel
    rc, diff_out = _sh(["git", "-C", repo, "diff", "--name-only", "--", facts_rel])
    return (rc != 0 or bool(diff_out.strip())), facts_rel


def _stage_rendered_docs(repo, doc):
    """`git add` rendered machine-block documents; returns `True` on error."""
    for name in (doc, "PRINCIPLES.md"):
        if os.path.isfile(os.path.join(repo, name)):
            rc, out = _sh(["git", "-C", repo, "add", "--", name])
            if rc != 0:
                if out:
                    print(out, file=sys.stderr)
                return True
    return False


def _prepare(phase, repo, doc):
    """(1) The phase's setup step. Returns `(whether to reject)`.

    The two phases do **opposite** things, hence one named branch each:

      - commit -- re-render the machine block and `git add` (**render only,
        do not re-measure**; re-measuring is a human's job). Refuses when
        `FACTS.json` has unstaged edits so an unstaged ledger cannot be
        rendered into the staged `STATE.md`.
      - push   -- **touches no files, rewrites no history**: a stale block is
        an outright rejection
    """
    facts = os.path.join(repo, "zreflect", "facts.py")
    if phase == "commit":
        unstaged, facts_rel = _has_unstaged_facts(repo)
        if unstaged:
            print(str(M("hookgate.unstaged_facts", path=facts_rel)),
                  file=sys.stderr)
            return True
        if os.path.isfile(os.path.join(repo, doc)):
            rc, out = _sh([sys.executable, facts, "--render-doc"])
            if rc != 0:
                if out:
                    print(out, file=sys.stderr)
                return True
            if _stage_rendered_docs(repo, doc):
                return True
        return False
    rc, out = _sh([sys.executable, facts, "--check"])
    if rc == 0:
        return False
    print(str(M("hookgate.blocks_stale", detail=(out or "").strip()[:400])),
          file=sys.stderr)
    return True


def run(phase, repo, stdin_rows=None):
    """Run one phase. Returns rc. **Pure orchestration**: every judgment
    lives inside the commands it calls."""
    if phase not in PHASES:
        print(str(M("hookgate.unknown_phase", phase=phase)), file=sys.stderr)
        return 2
    if not os.path.isdir(repo):
        print(str(M("hookgate.repo_missing", repo=repo)), file=sys.stderr)
        return 2

    os.environ["GATE_REPO"] = repo
    doc = knobs.get("REFLECT_DOC", root=repo)

    if _prepare(phase, repo, doc):
        return 1

    # (2) All gates: the single source of the execution surface (C1)
    rc, out = _sh([sys.executable, os.path.join(repo, "zreflect", "registry.py"),
                   "--run", "commit"])
    if rc != 0:
        print(out, file=sys.stderr)
        return 1

    if phase == "push":
        ok, lines = _push_readmes_together(repo, stdin_rows or [])
        for ln in lines:
            print(ln, file=sys.stderr)
        if not ok:
            return 1
    return 0


# -- Self-verification -------------------------------------------------------

def _unstaged_facts_case(mk_repo, shutil):
    """Unstaged edits in `FACTS.json` must be detected by `_has_unstaged_facts`."""
    d = mk_repo(True)
    try:
        _sh(["git", "-C", d, "config", "user.email", "a@b"])
        _sh(["git", "-C", d, "config", "user.name", "a"])
        fp = os.path.join(d, "FACTS.json")
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        _sh(["git", "-C", d, "add", "FACTS.json"])
        _sh(["git", "-C", d, "commit", "-q", "-m", "init"])
        clean, _rel = _has_unstaged_facts(d)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write('{"facts": {}}\n')
        dirty, _rel2 = _has_unstaged_facts(d)
        return (not clean) and dirty
    finally:
        shutil.rmtree(d, True)


def _cases():
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    def mk_repo(with_zreflect):
        d = tempfile.mkdtemp()
        _sh(["git", "init", "-q", d])
        if with_zreflect:
            os.makedirs(os.path.join(d, "zreflect"), exist_ok=True)
        return d

    def case(args):
        return _run_cli(list(args), quiet=True)

    return [
        ("hookgate.no_args_prints_usage", lambda: case([]) == 0),
        ("★ hookgate.unstaged_facts_rejected",
         lambda: _unstaged_facts_case(mk_repo, shutil)),
        ("★ hookgate.unknown_phase_is_2", lambda: case(["bogus", "/tmp"]) == 2),
        ("★ hookgate.missing_repo_is_2",
         lambda: case(["commit", "/nonexistent-xyz"]) == 2),
        ("★ hookgate.missing_root_is_2", lambda: case(["commit"]) == 2),
        ("★ hookgate.no_zreflect_is_2", lambda: _no_zreflect_case(mk_repo,
                                                                  shutil)),
        ("★ hookgate.summary_shape_can_red", lambda: _summary_shape_ok()),
        ("★ hookgate.refs_skip_deletions", lambda: _refs_case()),
    ]


def _no_zreflect_case(mk_repo, shutil):
    d = mk_repo(False)
    try:
        return _run_cli(["commit", d], quiet=True) == 2
    finally:
        shutil.rmtree(d, True)


def _summary_shape_ok():
    """Criterion lives in `machine.is_summary()` (single source of truth; no
    per-file regex copies anymore)."""
    import machine  # noqa: PLC0415
    return machine.is_summary("=== 3 PASS / 0 FAIL ===") and \
        not machine.is_summary("=== 3 PASS / 0 fail ===")


def _refs_case():
    rows = [("refs/heads/main", ZERO_SHA, "refs/heads/main", ZERO_SHA)]
    got = _new_content_refs(".", rows)
    return got == []


def _run_cli(argv, quiet=False):
    """Walk the CLI dispatch once, return rc.

    `quiet=True` (**selftest only**): print nothing -- selftest output is the
    interface a human checks; if diagnostics flood it, there is nothing left
    to check (this repo's discipline: "pure functions stay quiet").
    """
    def _say(code, **kw):
        if not quiet:
            print(str(M(code, **kw)), file=sys.stderr)

    if not argv:
        if not quiet:
            _usage()
        return 0
    rc = _validate(argv, _say)
    if rc is not None:
        return rc
    return run(argv[0], argv[1], _refs_from_stdin())


def _validate(argv, say):
    """Command-line shape validation. Returns rc (`None` = shape is legal,
    may proceed).

    The four checks are each an exit for "not worth continuing"; jamming
    them all into the call site made complexity 9 -- and they all judge the
    **same question** (can this invocation run), so they live in one
    function.
    """
    phase = argv[0]
    if phase not in PHASES:
        say("hookgate.unknown_phase", phase=phase)
        return 2
    if len(argv) < 2:
        say("hookgate.missing_root")
        return 2
    repo = argv[1]
    if not os.path.isdir(repo):
        say("hookgate.repo_missing", repo=repo)
        return 2
    if not os.path.isdir(os.path.join(repo, "zreflect")):
        say("hookgate.not_a_suite_repo", repo=repo)
        return 2
    return None


def _main(argv):
    if "--selftest" in argv:
        rc = activate_or_fatal()
        if rc:
            return rc
        from gate import selftest  # noqa: PLC0415
        return selftest(M("gate.title.hookgate"), _cases())
    rc = activate_or_fatal()
    if rc:
        return rc
    return _run_cli(argv)


# Declared on purpose: `criteria.suite_file_without_declaration` requires every
# file under `reflect-hooks/` to say what it is. This is not "the roster picks it
# up" -- the roster scans `zreflect/` only -- it is what keeps this file from
# being read as user code and dropped from auditing.
GATE = meta("Hook entry",
            "the single mouth called by other hook systems: commit re-renders + "
            "runs gates; push verifies only + trilingual READMEs in one batch",
            knobs=("REFLECT_DOC",),
            runs_at="start-of-work",
            off_reason="the hook entry is invoked by git, not attached to the pre-commit phase")


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
