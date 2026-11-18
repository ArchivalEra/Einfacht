#!/usr/bin/env python3
"""Gate platform: the rc contract + zero-trust guards + three-tier self-proof.

What it solves is **not** "having no checks" but **checks silently going green when
their input disappears**. Three real incidents:

  - Three sites all missing `VERSION` => the consistency gate reports "fully consistent";
  - The declared set is empty => the factory check reports `verdict: "ok"`;
  - A self-check script `0/0` => counted as "all passed".

So every checker must be able to answer two questions: **do I report when the input
is empty?** and **do I actually report what should be reported?**
`require_nonempty()` answers the first; `selftest()`'s three case classes answer the
second.

**The rc contract (this platform's interface, the repo-wide single source since
2026-10-07)**:

  - `off()`    => 0, not enabled (a pluggable gate's off state must **say so
    explicitly**, never silently);
  - `fatal()`  => 2, broken config / environment (knob points at something missing,
    bad JSON, malformed spec, the instrument itself is broken) -- a configuration
    failure != a check failure; merging it into 1 makes "found problems"
    indistinguishable from "the config is broken";
  - `finish()` => 1 (problems found) / 0 (green). Header first, problem lines after;
    **a single gate's problem lines all go to stderr** -- previously the 13 gates
    each hand-copied their own version and had drifted into two camps (mixed
    stdout/stderr, header order varying); this consolidates them into one.

  ⚠️ The rule above only binds **a single gate's own criterion output**. An
  **aggregator** (`registry --run <phase>`) prints a **run report** (what didn't run /
  what went red / what had broken config), not criteria -- it goes entirely to
  **stdout**; the reasoning is in `registry._main_run`'s comment. The two semantics
  differ; don't force the same convention onto both layers (conclusion of round 16).

Pure functions stay quiet during self-proof (printing belongs to run()/top level,
issue #1 (3)).
"""
import ast
import json
import os
import sys

_AST_CACHE: dict = {}   # key: file path -> parsed AST (or None)

# Root of the repo under audit: defaults to this package's parent, overridable via
# GATE_REPO (test fixtures rely on it).
GATE_REPO = os.environ.get("GATE_REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo(*parts):
    """Join an absolute path pointing into the audited repo."""
    return os.path.join(GATE_REPO, *parts)


def repo_path(path, root=None):
    """Anchor a relative path to `root` (default: the audited repo root); absolute
    paths pass through unchanged -- the single source.

    A relative path whose leading `/` is interpreted as the user's absolute spec
    path must not be joined onto the repo root: that boundary is defined here.
    """
    root = GATE_REPO if root is None else root
    return path if os.path.isabs(path) else os.path.join(root, path)


def zdir():
    """Tool's own `zreflect/` dir (distinct from audited `GATE_REPO`)."""
    return os.path.dirname(os.path.abspath(__file__))


def tool_repo():
    """The **tool repo** root (the parent of `zreflect/`) -- the repo-wide single source.

    `i18n.pack_dir()`'s "unset => use the suite's bundled packs" anchors here.
    """
    return os.path.dirname(zdir())


def machine():
    """Lazily import `machine` to avoid circular import before `module_meta` is defined."""
    import machine  # noqa: PLC0415
    return machine


def require_nonempty(name, seq, what=None):
    """Fail with `fatal_exit` if `seq` is empty; return `list(seq)`."""
    import i18n  # noqa: PLC0415
    if what is None:
        what = i18n.M("gate.input_label")
    items = list(seq)
    if not items:
        fatal_exit(i18n.M("gate.require_nonempty", name=name, what=str(what)))
    return items


def guard_nonempty(name, seq, what=None):
    """The rc-returning form of `require_nonempty`: empty => print FATAL, return 2;
    non-empty => None.

    For checkers that "run directly" (they want an exit code, not an exception).
    """
    try:
        require_nonempty(name, seq, what)
        return None
    except SystemExit as e:
        print("%s" % e, file=sys.stderr)
        return 2


def off(notice):
    """Emit explicit `OFF:` marker on stdout and return 0."""
    print(machine().emit("off", notice))
    return 0


def fatal(msg):
    """Broken config / environment: FATAL + exit 2."""
    print(machine().emit("fatal", msg), file=sys.stderr)
    return 2


def fatal_exit(msg):
    """The **exiting** form of `fatal` (for call sites that cannot `return 2`).

    ⚠️ **Must be `SystemExit(2)`, not `SystemExit(msg)`**: the latter is Python's
    "print and exit 1" convention -- it prints the letters `FATAL:` while the exit
    code is **1**. Callers (`gate._record`) classify by rc: 1 = criterion red /
    failed, 2 = broken config / fatal.
    """
    print(machine().emit("fatal", msg), file=sys.stderr)
    raise SystemExit(2)


def declares_itself(path):
    """Is this `.py` one of the **suite's own** files (a module-level `MODULE =` /
    `GATE =` declaration)?

    Criterion: the module body contains a `MODULE = ...` or `GATE = ...` assignment;
    unreadable / unparseable => False. `declares_itself()` is the boundary between
    the suite's own scan surface and a consumer's `examples/` / `scripts/`, so
    gates auditing the suite must call it rather than collecting every `.py`.
    """
    import ast  # noqa: PLC0415
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return False
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id in ("MODULE", "GATE")
               for t in node.targets):
            return True
    return False


def suite_sources(base):
    """`(relative name, text)` of `.py` files under `base` that **belong to the suite**.

    Difference from `py_sources`: collects only files where `declares_itself()` is
    true. A user's own `measure_*.py` placed in this directory (a data module, no
    declaration) does not count as suite code.
    """
    return [(rel, src) for rel, src in py_sources(base)
            if declares_itself(os.path.join(base, rel))]


def scanned_sources(base, configured=False):
    """Which `.py` files a gate should collect -- **two scopes, split on "was the knob
    explicitly configured"**.

      - **Unset** => `suite_sources`: audit only files with declarations.
      - **Set** (the user points and says "audit here") => `py_sources`: take
        everything. Narrowing here would make an explicitly configured directory
        report `scan_empty_dir` FATAL and break opt-in.
    """
    return py_sources(base) if configured else suite_sources(base)


def py_sources(base):
    """Collect `[(relpath, source)]` for `.py` files under `base` using forward slashes."""
    out = []
    if not os.path.isdir(base):
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in ("__pycache__", ".git"))
        for n in sorted(filenames):
            if not n.endswith(".py"):
                continue
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, base).replace(os.sep, "/")
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    out.append((rel, fh.read()))
            except OSError:
                continue
    return out


def resolve_spec(argv, knob, default):
    """Spec name resolution: explicit `--spec` > knob > default name. Returns
    `(name, was_explicit)`.

    A pure function. `was_explicit` tells the caller how to handle a missing file:
    explicitly specified (argv / knob) but absent => FATAL; default name absent =>
    not enabled, exit 0.
    """
    for i, a in enumerate(argv):
        if a == "--spec":
            return argv[i + 1], True
    k = (knob or "").strip()
    if k:
        return k, True
    return default, False


def load_spec(path):
    """Read a JSON spec, returning (spec, error message). Error message non-None => the
    caller calls `fatal()`.

    Returns the error instead of raising: the caller needs to weave its own knob
    name / path into its FATAL wording.
    """
    import i18n  # noqa: PLC0415
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as e:
        return None, i18n.M("gate.spec_unreadable", path=path, error=e)


def finish(name, problems, ok):
    """The problem loop + the OK line -- the single source of the rc contract
    (1 = problems found / 0 = green)."""
    import i18n  # noqa: PLC0415
    if problems:
        print(i18n.M("gate.problems_header",
                     name=name, count=len(problems)), file=sys.stderr)
        for p in problems:
            print("  · " + p, file=sys.stderr)
            # The **consumer** of `.forged`: rendering neutralized forged lines
            # (didn't reject them), but "neutralized" must be **visible** --
            # otherwise nobody ever learns a filename contained a newline and the
            # user sees only a strange `\OFF:`. Say it in one line; don't flood.
            forged = getattr(p, "forged", ())
            if forged:
                print("  " + i18n.M("gate.forged_row_neutralised",
                                    count=len(forged)), file=sys.stderr)
        return 1
    print(ok)
    return 0


def _meta_shape(name, desc, knobs):
    """The declaration's identity fields: name, one-sentence description, consumed knobs."""
    return {"name": name, "desc": desc, "knobs": tuple(knobs)}


def _meta_execution(name_dependent, runs_at, off_reason):
    """The declaration's execution fields.

    `name_dependent=True` marks gates whose default input gets renamed by the
    rename selftest; both the fixture and `registry.problems` judge them. `runs_at`
    declares frequency positively: `"commit"` (hooks / CI) or `"start-of-work"`
    (manual doctor-style checks). `off_reason` states why a gate that can call
    `off()` would be not-enabled; it must be >= 8 chars (same discipline as
    `PINNED:`). Names carry no semantics.
    """
    return {"name_dependent": bool(name_dependent),
            "runs_at": str(runs_at),
            "off_reason": (None if off_reason is None else str(off_reason))}


def meta(name, desc, knobs=(), name_dependent=False, runs_at="commit",
         off_reason=None):
    """Gate declaration line (registry's ast extraction target): name + one sentence +
    consumed knobs.

    Declaring is registering -- a hand-written roster drifts; only facts may be
    written here. `runs_at` is `"commit"` or `"start-of-work"`; registry derives
    the execution list, narration, red list and selftest list from these fields.
    """
    value = _meta_shape(name, desc, knobs)
    value.update(_meta_execution(name_dependent, runs_at, off_reason))
    return value


def _module_meta_shape(name, desc):
    """Identity fields of a platform-module declaration."""
    return {"name": name, "desc": desc}


def _module_meta_obligation(selftest):
    """Whether registry must demand that the module supports `--selftest`."""
    return {"selftest": bool(selftest)}


def module_meta(name, desc, selftest=True):
    """Module-level `MODULE = ...` declaration for AST registry discovery."""
    value = _module_meta_shape(name, desc)
    value.update(_module_meta_obligation(selftest))
    return value


def raises(fn):
    """"What should raise must raise" -- for reverse assertions. True means it did
    raise SystemExit."""
    try:
        fn()
    except SystemExit:
        return True
    return False



def _ast_for(fname):
    """Whole-file AST (cached by filename). Unreadable / unparseable => False (negative results are cached)."""
    import ast as _ast  # noqa: PLC0415
    import linecache  # noqa: PLC0415
    tree = _AST_CACHE.get((fname,))
    if tree is not None:
        return tree
    try:
        tree = _ast.parse("".join(linecache.getlines(fname)))
    except (OSError, SyntaxError):
        tree = False
    _AST_CACHE[(fname,)] = tree
    return tree


def _lambda_nodes(tree, lineno):
    """**All** Lambda nodes whose starting line == lineno (ascending by col_offset).

    ⚠️ **One line can hold several lambdas**: their code objects share
    `co_firstlineno`, and `co_positions()` only gives the outer position, so there
    is no way to tell which one the callable came from. The caller must scan
    **each** candidate; any always-true assertion on the line reports.
    """
    import ast as _ast  # noqa: PLC0415
    nodes = [n for n in _ast.walk(tree)
             if isinstance(n, _ast.Lambda) and n.lineno == lineno]
    return sorted(nodes, key=lambda n: n.col_offset)


def _const_truthy(node):
    """Is this constant node always truthy (the right-operand shape of `or True` / `or 1`)?"""
    import ast as _ast  # noqa: PLC0415
    if not isinstance(node, _ast.Constant) or node.value is None:
        return False
    return node.value is not False and bool(node.value) is True


def _const_falsy(node):
    """Is this constant node always falsy (the right-operand shape of `and False` / `and 0`)?"""
    import ast as _ast  # noqa: PLC0415
    if not isinstance(node, _ast.Constant) or node.value is None:
        return False
    return node.value is False or node.value == 0


def _short_circuit_reason(node):
    """Does this AST node constitute an always-true short circuit => reason message; else None."""
    import ast as _ast  # noqa: PLC0415

    import i18n  # noqa: PLC0415
    if isinstance(node, _ast.BoolOp):
        if isinstance(node.op, _ast.Or) and any(
                _const_truthy(o) for o in node.values):
            return i18n.M("gate.never_falsifiable_or")
        if isinstance(node.op, _ast.And) and any(
                _const_falsy(o) for o in node.values):
            return i18n.M("gate.never_falsifiable_and")
    if isinstance(node, _ast.Compare) and len(node.comparators) == 1:
        left, right = node.left, node.comparators[0]
        # Exclude the **legitimate** purity check of calling a bare function twice
        # (`render_gates(gs) == render_gates(gs)` proves render determinism).
        if isinstance(left, _ast.Call) and isinstance(right, _ast.Call):
            return None
        if _ast.dump(left) == _ast.dump(right) and isinstance(
                node.ops[0], (_ast.Eq, _ast.LtE, _ast.GtE)):
            return i18n.M("gate.never_falsifiable_self_compare")
    return None


def _assertion_node(fn):
    """Locate the lambda AST node(s) for this assertion. Unlocatable => `[]` (no guessing)."""
    code = getattr(fn, "__code__", None)
    if code is None:
        return []                                        # not a Python function
    tree = _ast_for(code.co_filename)
    if not tree:
        return []                                        # unreadable / unparseable
    return _lambda_nodes(tree, code.co_firstlineno)


def _const_lambda_reason(nodes):
    """Check whether any 0-arg candidate lambda directly returns a constant literal."""
    import i18n  # noqa: PLC0415
    for node in nodes:
        if (isinstance(node, ast.Lambda)
                and not (node.args.posonlyargs or node.args.args
                         or node.args.kwonlyargs or node.args.vararg or node.args.kwarg)
                and isinstance(node.body, ast.Constant)):
            return i18n.M("gate.never_falsifiable_constant_return")
    return None


def _short_circuit_reason_of(nodes):
    """Scan for always-true short circuits: `or <truthy constant>` / `and <falsy
    constant>` / `x == x`."""
    for node in nodes:
        for n in ast.walk(node):
            reason = _short_circuit_reason(n)
            if reason:
                return reason
    return None


def _falsifiability_located(nodes):
    """All candidate lambdas on the line (no multi-lambda bailout)."""
    return nodes or None


def _falsifiability_reason(nodes):
    """Judge every located lambda: constant body or short-circuit / self-comparison."""
    if not nodes:
        return None
    return _const_lambda_reason(nodes) or _short_circuit_reason_of(nodes)


def never_falsifiable(fn):
    """Does this selftest case have falsification power?

    Scans all lambdas on `co_firstlineno` for constant bodies, short circuits,
    and self-comparisons (`x == x`).
    """
    return _falsifiability_reason(_falsifiability_located(_assertion_node(fn)))


def _run_safely(label, fn):
    """Run the assertion body. Returns `(passed?, failure line or None)`. **Exceptions
    must not escape**."""
    import i18n  # noqa: PLC0415
    try:
        return bool(fn()), None
    except SystemExit as e:
        return False, i18n.M("gate.case_unexpected_systemexit",
                             label=label, error=e)
    except Exception as e:                      # noqa: BLE001
        return False, i18n.M("gate.case_raised", label=label, error=e)


def _case_verdict(label, fn):
    """Run one case. Returns `(passed?, failure line or None)`."""
    import i18n  # noqa: PLC0415
    why = never_falsifiable(fn)
    if why:
        return False, i18n.M("gate.case_unfalsifiable", label=label, why=why)
    return _run_safely(label, fn)


def _print_banner(name, total, bad):
    """Emit human summary line and fixed-format machine summary line."""
    import i18n  # noqa: PLC0415
    print(machine().emit("human_summary",
                       i18n.M("gate.selftest_summary",
                              name=name, passed=total - bad, failed=bad)))
    print(machine().emit_summary(total - bad, bad))


def _report_one(label, fn):
    """Run one case and report its outcome (`PASS | ...` or `fail | ...`)."""
    passed, failure = _case_verdict(label, fn)
    if failure is not None:
        print(machine().emit("fail", failure))
        return False, failure
    print(machine().emit("pass" if passed else "fail", label))
    return passed, None


def selftest(name, cases):
    """Run cases, each `(label, callable) -> bool`; empty cases => FATAL rc 2."""
    import i18n  # noqa: PLC0415
    if not cases:
        fatal_exit(i18n.M("gate.selftest_empty_cases", name=name))
    import seal  # noqa: PLC0415
    if seal.seal_exists():
        probs = seal.verify_problems()
        if probs:
            fatal_exit(probs[0])
    bad = 0
    for label, fn in cases:
        ok, _failure = _report_one(label, fn)
        bad += 0 if ok else 1
    _print_banner(name, len(cases), bad)
    return 1 if bad else 0


def _force_utf8_streams():
    """Force stdout/stderr to UTF-8 (**mandatory on Windows**).

    On Windows `sys.stdout.encoding` defaults to the code page, while gate names
    and descriptions are printed; a single `registry.py --gates` can raise
    `UnicodeEncodeError`. Only streams supporting `reconfigure` are touched;
    failures are skipped silently. The side effect is **global**, so this is
    called only at CLI entries, via `activate_or_fatal`.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            continue                # already closed / unsupported -- no guessing


def _activate_pack(lang):
    """Assemble one language pack. Returns `(ok?, fatal message or None)`.

    `MissingPack` / broken shards must not escape as a traceback rc=1: this
    module is called outside the normal rc contract, so an assembly failure is
    turned into a machine-readable FATAL message for rc 2. On failure the
    process still holds its previous-tier `Catalog`, so `M()` can render.
    """
    import i18n  # noqa: PLC0415
    try:
        i18n.activate(lang)
    except Exception as e:                               # noqa: BLE001
        return False, i18n.M("gate.pack_assembly_failed", error=e)
    return True, None


def activate_or_fatal(lang=None):
    """Activate language pack for process (returns 0 on success, 2 on FATAL)."""
    _force_utf8_streams()
    ok, failure = _activate_pack(lang)
    if not ok:
        print(machine().emit("fatal", failure), file=sys.stderr)
        return 2
    return 0


def main_selftest_or(args, name, cases, run):
    """`--selftest` runs the selftest; otherwise `run(args)`. Every checker ends with
    this.

    `cases` can be a list or a **factory callable** (selftests that need to build a
    temp fixture pass a function, invoked here). Activation happens **before**
    `--selftest` dispatch: `REFLECT_LANG` unset => null pack; set but the pack is
    missing => FATAL rc 2, never a silent fallback. Reasoning in
    `activate_or_fatal`.
    """
    rc = activate_or_fatal()
    if rc:
        return rc
    if "--selftest" in args:
        return selftest(name, cases() if callable(cases) else cases)
    return run([a for a in args if a != "--selftest"])


def default_runner(f, repo_root=None):
    """The default runner: executes one gate file, returns `(rc, merged output)`.

    ⚠️ **stdout and stderr must be merged**: this repo's convention is "problem lines
    all on stderr", so a gate with rc=2 can have **empty** stdout (the reason is all
    on stderr). Returning only `p.stdout` gives the aggregator `(2, "")`, with no
    reason for the failure.
    """
    import subprocess  # noqa: PLC0415
    p = subprocess.run([sys.executable, f], capture_output=True, text=True,
                       cwd=repo_root or GATE_REPO,
                           encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _empty_result():
    """The initial shape of the aggregate result. `fail_out` keeps **each failed
    gate's raw output**, so the aggregator can explain a red gate without asking
    the user to re-run it.
    """
    return {"ran": 0, "off": 0, "failed": 0, "fatal": 0, "error": 0,
            "off_list": [], "fail_list": [], "fatal_list": [], "error_list": [],
            "fail_out": {}}


def _record(res, f, rc, out):
    """Classify one gate into one of five tiers by rc and the `OFF:` marker.

    The tiers are **non-overlapping fix categories**:

      rc=2   broken config / environment -> fix the config
      rc<0   killed by a signal          -> error at executor level
      rc>2   an uncontracted code        -> error at executor level
      rc=1   criterion red               -> fix the problems
      rc=0 + `OFF:` marker           -> not enabled (not a pass)
      rc=0 clean                     -> ran and passed
    """
    if rc == 2:
        res["fatal"] += 1
        res["fatal_list"].append(f)
    elif rc < 0 or rc > 2:
        res["error"] += 1
        res["error_list"].append(f)
    elif rc != 0:
        res["failed"] += 1
        res["fail_list"].append(f)
        res["fail_out"][f] = out or ""
    elif any(kind == "off" for _i, kind, _ln in machine().scan(out)):
        res["off"] += 1
        res["off_list"].append(f)
    else:
        res["ran"] += 1


def _run_phase_gates(phase, gates, run, res):
    """Execute the phase's gates through one runner and classify each result."""
    for item in gates:
        f = item["file"] if isinstance(item, dict) else item
        if isinstance(item, dict) and item.get("runs_at") not in (None, phase):
            continue
        rc, out = run(f)
        _record(res, f, rc, out)


def run_phase(phase, gates, runner=None, repo_root=None):
    """Run gates for one phase; returns the aggregate result.

    `gates` is the registry-derived `(file, runs_at)` list; an item supplying
    `runs_at` is filtered on `phase`. `runner` is injectable (selftests use a
    fake executor) and defaults to `default_runner(f, repo_root)`.

    Off and "ran and passed" both have rc 0, so `_record` reads the `OFF:`
    marker from child stdout to list off separately. The result carries counts,
    the corresponding `_list` names, and `fail_out` (raw failed-gate output).
    """
    run = runner or (lambda f: default_runner(f, repo_root))
    res = _empty_result()
    _run_phase_gates(phase, gates, run, res)
    return res


# The **real meaning** of `selftest=False`: this module **has no `--selftest`
# entry** (it provides `selftest()` itself; bootstrapping both would collide).
# **This does not mean its logic has no self-proof** -- its logic lives in
# `registry._cases()`: `finish` / `meta` / `run_phase` / `default_runner` / `zdir` /
# `tool_repo` / `never_falsifiable` (via `_nf_catches`) all have substantive
# assertions. The description used to say only "provides selftest, doesn't consume
# it itself" -- which reads like "no selftest obligation", contradicting the facts
# (aligned in round 23).
MODULE = module_meta(
    "gate platform",
    "rc contract + zero-trust guards + three-tier self-proof + phase executor "
    "(no --selftest entry: bootstrapping would collide; "
    "logic self-proof lives in registry._cases)",
    selftest=False)


if __name__ == "__main__":
    import i18n  # noqa: PLC0415
    # This used to be a bare `i18n.activate()`: pack missing => MissingPack
    # **traceback rc=1** instead of the rc contract's FATAL rc=2 (observed). Goes
    # through the same activation entry now.
    rc = activate_or_fatal()
    if rc:
        sys.exit(rc)
    print(i18n.M("gate.platform_root", root=GATE_REPO))
    print(i18n.M("gate.platform_usage"))
    sys.exit(0)
