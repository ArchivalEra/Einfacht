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
    """The **tool's own** `zreflect/` directory -- the repo-wide single source.

    Purpose: "scan my own source" (discovery-based roster / phantom knobs / code
    coverage). This is a different thing from `GATE_REPO` (the **audited** repo
    root): in a cross-repo fixture `GATE_REPO` points at a temp directory while the
    tool's source still lives in the suite.
    """
    return os.path.dirname(os.path.abspath(__file__))


def tool_repo():
    """The **tool repo** root (the parent of `zreflect/`) -- the repo-wide single source.

    `i18n.pack_dir()`'s "unset => use the suite's bundled packs" anchors here.
    """
    return os.path.dirname(zdir())


def machine():
    """Lazily fetch `machine` (the machine-line protocol).

    ⚠️ **Must not be a module-level `import machine`**: `machine` needs
    `from gate import module_meta` to declare itself (a registry adoption
    requirement), so a module-level import would be circular (observed ImportError).
    Same reason as `i18n.py`'s lazy import -- a cycle can only be broken by ordering
    "who goes first", not by each side grabbing a piece inside the loop.
    """
    import machine  # noqa: PLC0415
    return machine


def require_nonempty(name, seq, what=None):
    """Zero-trust guard: if collection received nothing => error, **never treat it as
    "clean"**.

    The most important line in this package. The root cause of nearly all "a gate
    pretended to pass" incidents is this guard missing: walking a nonexistent
    directory yields an empty set, then "no violations found" -- both statements are
    true, the conclusion is wrong.

    `what` = a name for the collected thing (defaults to the language pack's
    `gate.input_label`).
    """
    import i18n  # noqa: PLC0415
    if what is None:
        what = i18n.M("gate.input_label")
    items = list(seq)
    if not items:
        # `FATAL:` is a machine-contract prefix -- a literal at the **emission
        # point** (not in the language pack). `what` may be a caller-supplied
        # Message (e.g. `M("stale.scanned_docs")`): str() it flat first, otherwise
        # the null pack renders a nested `repr(Message)`.
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
    """Not enabled: say so explicitly + exit 0.

    ⚠️ **off and "actually ran and passed" must be distinguishable** (C2): both have
    rc 0 (off is not a failure; hooks' `|| exit` should not treat it as red), but off
    prints a machine-readable `OFF: ...` marker line on stdout -- the executor
    (`gate.run_phase`) uses it to split gates into ran / off / failed instead of
    counting "didn't run" as green.
    """
    print(machine().emit("off", notice))
    _maybe_hint()
    return 0


def fatal(msg):
    """Broken config / environment: FATAL + exit 2."""
    print(machine().emit("fatal", msg), file=sys.stderr)
    return 2


def fatal_exit(msg):
    """The **exiting** form of `fatal` (for call sites that cannot `return 2`).

    ⚠️ **Must be `SystemExit(2)`, not `SystemExit(msg)`**: the latter is Python's
    "print and exit 1" convention -- it prints the letters `FATAL:` while the exit
    code is **1**. Callers (`registry._record`) classify by rc: 1 = criterion red /
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
    """`(filename, text)` of all `.py` under the `base` directory; unreadable => skip.

    **Single source**: this `listdir` + `open(errors="replace")` block used to be
    written out in **three** places -- `knobs._py_sources`,
    `check_snapshots.collect`, and `check_i18n`'s collection loop. All call here now.

    Unreadable => that file is skipped (not a whole-directory failure): each caller
    judges emptiness itself -- "empty" means something different to each of them
    (phantom scan: "nothing suspicious"; `used_codes`: "no codes"; `envfile`: "the
    gate is broken").

    ⚠️ `base` must be passed explicitly: upstream defaults differ (the tool repo's
    `zreflect` vs the audited repo's `zreflect`); providing a default would hide that
    difference (observed).
    """
    import os  # noqa: PLC0415
    out = []
    if not os.path.isdir(base):
        return out
    # ⚠️ **Recursive**: previously only one `listdir` level, so a common layout like
    # `REFLECT_I18N_ROOT=src` reported "the scan surface is empty" -- while the
    # directory was not empty at all (observed: in a subagent's acceptance repo,
    # `src/mycli/cli.py` plainly held a line of Chinese and the criterion saw
    # nothing). Names are **paths relative to base**: otherwise `a/util.py` and
    # `b/util.py` overwrite each other and errors cannot say which one.
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in ("__pycache__", ".git"))
        for n in sorted(filenames):
            if not n.endswith(".py"):
                continue
            p = os.path.join(dirpath, n)
            # ⚠️ **Normalize to forward slashes**: three places compare this `rel`
            # as a **filename** (`check_i18n`'s `name == "i18n.py"`, `criteria`'s
            # `name == "gate.py"`, `knobs`' phantom scan). On Windows `relpath`
            # yields `zreflect\i18n.py` => those equality checks never fire, so
            # "file-level exemptions" fail wholesale on Windows (observed: CI's
            # Windows leg classified it the same way as unregistered shell text).
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
        _maybe_hint()
        return 1
    print(ok)
    _maybe_hint()
    return 0


def _env_hint_off():
    """Is `REFLECT_ENV_HINT` explicitly off -- goes through `knobs.flag` (the single
    source of the flag vocabulary).

    ⚠️ This used to be `.lower() == "off"`: a **second flag vocabulary** next to
    `doc.accepts_principles`'s `("1","true","yes")` (the latter case-sensitive;
    observed: `TRUE` didn't take effect). Now unified through `knobs.flag`.
    """
    import knobs  # noqa: PLC0415
    return knobs.flag("REFLECT_ENV_HINT") is False


def _maybe_hint():
    """Print the env hint to stderr (**never stdout** -- that stream carries the
    machine contract).

    `REFLECT_ENV_HINT=off` disables it entirely (the exit for repos that "don't like
    hints"; the hint itself is **human courtesy**, not a criterion).
    """
    if _env_hint_off():
        return
    h = env_hint()
    if h:
        print("ℹ %s" % h, file=sys.stderr)


def env_carrier():
    """The repo's Einfacht.env carrier path (hooks dir first, repo root second); none => None."""
    name = (os.environ.get("REFLECT_ENV_FILE", "Einfacht.env").strip()
            or "Einfacht.env")
    for d in (repo("reflect-hooks"), repo()):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def gate_knobs(module=None):
    """The caller module's declared `GATE = meta(..., knobs=...)` (unavailable => empty).

    Lets `env_hint()` avoid hand-writing knob names at every entry -- the declaration
    already holds one copy (single source).
    """
    import sys as _sys  # noqa: PLC0415
    mod = module if module is not None else _sys.modules.get("__main__")
    decl = getattr(mod, "GATE", None)
    if isinstance(decl, dict):
        return tuple(decl.get("knobs") or ())
    return ()


def env_hint(consumed=(), module=None):
    """**Human courtesy hint**: for env-fed entries, how to run when "env was provided
    but didn't take effect".

    `consumed` = the knob names this entry actually reads (e.g. `("REFLECT_FACTS",)`).
    Returns a one-line hint string, or None (no hint needed).

    When to hint (three classes, each only when **helpful** to the user):

      1. The repo **has** an Einfacht.env but this process **set none of the knobs**
         (none of `consumed` is in the environment) -- the classic bare manual run:
         `python3 zreflect/check_x.py` => criteria all fall back to default names,
         results may differ from the hook context, and **nothing tells the user**
         (issue #20(2) / #15 both tripped here).
      2. The repo **has** an Einfacht.env and current settings **disagree** with it?
         -- Not checked (judging requires comparing values, and values depend on
         shell semantics); only "is it set" is checked, keeping the criterion cheap
         and reliable.
      3. The repo **has no** Einfacht.env => **no hint** (bare runs are normal usage
         for such repos; a hint would just be noise -- this repo's lesson that "a
         gate with false positives eventually gets switched off entirely").

    The hint wording lives here (one place), and every entry calls it -- no more
    per-entry copies.
    """
    carrier = env_carrier()
    if not carrier:
        return None                      # repo without a carrier: bare runs are normal usage, don't nag
    if not consumed:
        consumed = gate_knobs(module)     # the declared knob list (zero hand-writing)
    if not consumed:
        return None
    # ⚠️ **"Knob is set" must not be silently accepted across the board** (#28): the
    # hook system relies on sourcing the carrier to put knobs into the environment
    # -- in a correctly wired repo "knobs are in the environment" is always true, so
    # the original fourth tier (carrier present but knobs unset => hint) was
    # unreachable in any normally wired repo.
    # Four-tier semantics (one carrier comparison; costs one file read):
    #   1. No carrier => silent (bare runs are normal usage)
    #   2. None of the consumed knobs set => **hint** (carrier present, but nobody
    #      sourced / exported)
    #   3. Knobs set and values **match** the carrier => carrier is in effect, silent
    #   4. Knobs set but values **differ** from the carrier (or the carrier doesn't
    #      mention them) => **hint** (manual exports can drift -- exactly the scene
    #      worth nagging about)
    import check_envfile  # noqa: PLC0415
    try:
        with open(carrier, encoding="utf-8", errors="replace") as fh:
            exported = check_envfile.parse_exports(fh.read())
    except OSError:
        exported = {}                    # carrier unreadable: treat as "not written" (record in guard)
    set_kv = {k: os.environ[k].strip() for k in consumed
              if os.environ.get(k, "").strip()}
    if not set_kv:
        # Tier 2: carrier present, but not a single knob set => the original hint scene
        rel = os.path.relpath(carrier, GATE_REPO)
        import i18n  # noqa: PLC0415
        return i18n.M("gate.env_hint", file=rel)
    if all(exported.get(k) == v for k, v in set_kv.items()):
        return None                      # Tier 3: carrier is in effect, silent
    # Tier 4: at least one knob manually exported and differing from the carrier
    # (or absent from it)
    rel = os.path.relpath(carrier, GATE_REPO)
    import i18n  # noqa: PLC0415
    return i18n.M("gate.env_hint", file=rel)


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
    """Platform module declaration line (C5): registry's ast extraction target.

    Gates declare with `GATE = meta(...)`; **platform modules** (gate / runner /
    knobs / registry / guard / ledger / render / facts ...) declare their existence
    and "whether they owe a selftest" with `MODULE = module_meta(...)`.
    `selftest=True` makes registry demand an entry that actually supports
    `--selftest`; `False` means the module provides `selftest()` itself, where
    bootstrapping a second entry would collide.
    """
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


# Builtin whitelist: they **inline logic inside the lambda** rather than delegate --
# the generator/arguments are right there in the AST, so always-true detection can
# still scan them (classifying builtins as delegation would false-positive half the
# assertions; observed: 6 false positives).
_BUILTIN_OK = frozenset({
    "any", "all", "bool", "len", "sorted", "sum", "min", "max",
    "isinstance", "getattr", "hasattr", "str", "int", "set",
    "list", "tuple", "dict", "repr",
})


def _assertion_node(fn):
    """Locate the lambda AST node(s) for this assertion. Unlocatable => `[]` (no guessing)."""
    code = getattr(fn, "__code__", None)
    if code is None:
        return []                                        # not a Python function
    tree = _ast_for(code.co_filename)
    if not tree:
        return []                                        # unreadable / unparseable
    return _lambda_nodes(tree, code.co_firstlineno)


def _delegation_reason(nodes):
    """**Pure delegation** (the lambda body is a single non-builtin Call) => the
    assertion logic lives inside the called function, invisible to this criterion.

    Returns the `delegated` code rather than None, so callers can print the case as
    `note |` and count it separately -- never silently treated as clean.
    """
    import i18n  # noqa: PLC0415
    for node in nodes:
        if isinstance(node.body, ast.Call):
            f = node.body.func
            fname = getattr(f, "id", None) or getattr(f, "attr", None)
            if fname not in _BUILTIN_OK:
                return i18n.M("gate.never_falsifiable_delegated")
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
    """Select the lambda only when its source position is unambiguous.

    An unlocatable assertion, or several lambdas sharing one starting line, yields
    no candidates: no guessing. A single candidate can be judged for delegation
    and short circuits.
    """
    if not nodes or len(nodes) > 1:
        return None
    return nodes[0]


def _falsifiability_reason(node):
    """Judge one located lambda: delegation before short circuits.

    Delegation must be reported explicitly: the called helper's body is outside
    the static scan. `_short_circuit_reason_of` then recognizes `or <truthy>` /
    `and <falsy>` / `x == x`, excluding the purity check of calling a bare
    function twice.
    """
    if node is None:
        return None
    return (_delegation_reason([node])
            or _short_circuit_reason_of([node]))


def never_falsifiable(fn):
    """Does this selftest case have falsification power?

    Returns a reason string (unfalsifiable or explicitly delegated) or None
    (looks like it has teeth). Static AST inspection: zero execution, zero side
    effects, no guessing when the source cannot be read. Only explicit short
    circuits, self-comparisons and a lambda body that is a single `Call` are
    judged; subtler forms and helper internals are outside this criterion.
    """
    return _falsifiability_reason(_falsifiability_located(_assertion_node(fn)))


def _is_delegated(why):
    """Is this `why` the "delegated assertion" criterion (rather than an always-true
    short circuit)?

    ⚠️ Must look at `.code`, never `str(why)`: `why` is a `Message` whose str value
    has already been rendered **in the current language** -- under `zh` it becomes
    Chinese, matching against the English code never hits, and a delegated assertion
    gets reported as an always-true short circuit (observed: `KeyError: 'label'`).
    """
    return getattr(why, "code", None) == "gate.never_falsifiable_delegated"


def _run_safely(label, fn):
    """Run the assertion body. Returns `(passed?, failure line or None)`. **Exceptions
    must not escape**.

    `SystemExit` is caught separately: selftest assertions like `raises(...)`
    deliberately raise -- that is the behavior under test, not a selftest failure;
    but if it truly leaks to this layer, the case was written wrong.
    """
    import i18n  # noqa: PLC0415
    try:
        return bool(fn()), None
    except SystemExit as e:
        return False, i18n.M("gate.case_unexpected_systemexit",
                             label=label, error=e)
    except Exception as e:                      # noqa: BLE001
        return False, i18n.M("gate.case_raised", label=label, error=e)


def _case_verdict(label, fn):
    """Run one case. Returns `(passed?, delegated?, failure line or None)`.

    An unfalsifiable assertion fails without executing. A delegated assertion is
    **still executed**: its verdict returns `delegated=True` so `_report_one`
    prints `note |` and counts it separately. Any other assertion executes
    normally. In all three branches `_run_safely` keeps exceptions from escaping.
    """
    import i18n  # noqa: PLC0415
    why = never_falsifiable(fn)
    if why and _is_delegated(why):
        passed, failure = _run_safely(label, fn)
        return passed, True, failure
    if why:
        # `fail | ` is the selftest machine-line prefix -- an emission-point literal,
        # not in the language pack
        return False, False, i18n.M("gate.case_unfalsifiable",
                                    label=label, why=why)
    passed, failure = _run_safely(label, fn)
    return passed, False, failure


def _print_banner(name, total, bad, delegated):
    """The summary's three lines: delegated count (listed separately) / human summary /
    machine summary line.

    Delegated is not a failure, but it is also not "scanned and clean" -- it gets
    its own human line. The machine summary line is independent of the checker
    name and has a fixed format; runner/CI grep it directly. The `=== ` prefix
    and trailing ` ===` are emission-point literals (language pack values must
    not start with `^===`).
    """
    import i18n  # noqa: PLC0415
    if delegated:
        print(machine().emit("human_summary",
                           i18n.M("gate.selftest_delegated",
                                  name=name, count=delegated)))
    print(machine().emit("human_summary",
                       i18n.M("gate.selftest_summary",
                              name=name, passed=total - bad, failed=bad)))
    print(machine().emit_summary(total - bad, bad))


def _report_one(label, fn):
    """Run one case and **report its outcome on the spot**. Returns `(passed?,
    delegated?, failure line or None)`.

    The four outcomes each have an output path, but "how to report" and "whether to
    report" must stay separate:

      - delegated + passed  -> `note | ... | delegated`
      - delegated + failed  -> **`fail | ...`** (this used to `continue`, discarding
        the result entirely)
      - always-true / exception -> `fail | <reason>`
      - normal              -> `PASS | ...` or `fail | ...`
    """
    passed, was_delegated, failure = _case_verdict(label, fn)
    if was_delegated:
        print(machine().emit("note", "%s | delegated" % label))
        if not passed:
            print(machine().emit("fail", label))
        return passed, True, None
    if failure is not None:
        print(machine().emit("fail", failure))
        return False, False, failure
    # The pass line is `PASS | `, the failure line is `fail | ` -- two kinds, one table
    print(machine().emit("pass" if passed else "fail", label))
    return passed, False, None


def selftest(name, cases):
    """Run cases, each `(label, callable) -> bool`; empty cases => FATAL rc 2.

    All three case classes must be present: normal runs that don't report
    (positive control), cases that do report (reverse assertion), and empty
    input that reports (zero-trust guard). `_report_one` decides per-case output
    and `_print_banner` emits the summary; this function only accumulates counts.
    Returns 0 when all cases pass, 1 otherwise.
    """
    import i18n  # noqa: PLC0415
    if not cases:
        # The 0/0 hole (the third incident recorded at the top of this file): a
        # selftest with an empty case list checks nothing, prints "0 PASS / 0 FAIL",
        # and exits green -- the runner's grep still accepts it. An empty list is a
        # shape error in writing the selftest; sound on the spot, never green.
        fatal_exit(i18n.M("gate.selftest_empty_cases", name=name))
    bad = delegated = 0
    for label, fn in cases:
        ok, was_delegated, _failure = _report_one(label, fn)
        delegated += 1 if was_delegated else 0
        bad += 0 if ok else 1
    _print_banner(name, len(cases), bad, delegated)
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
    """The process-level language-pack activation point. Returns 0 on success; on
    assembly failure prints FATAL and returns 2.

    `lang` lets **one process** assemble a specific pack (unset = read
    `REFLECT_LANG`); it affects only that process and adds no knob. Activation
    must happen **before** `--selftest` dispatch: unset => null pack; set but
    missing pack => FATAL rc 2, never a silent fallback. Entries outside
    `main_selftest_or` share the same activate+FATAL wiring.
    """
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
    on stderr). Returning only `p.stdout` => the aggregator gets (2, ""), knowing
    neither which file broke nor why (observed:
    `REFLECT_SNAPSHOT_ROOT=/nonexistent` => stdout='').
    """
    import subprocess  # noqa: PLC0415
    p = subprocess.run([sys.executable, f], capture_output=True, text=True,
                       cwd=repo_root or GATE_REPO,
                           encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _empty_result():
    """The initial shape of the aggregate result. `fail_out` keeps **each failed
    gate's raw output**.

    ⚠️ When the aggregator prints only filenames, users must re-run the gate
    themselves to learn why it went red (observed: the hook reported only
    `FAILED check_facts.py`, while running it directly showed
    `facts.bare_number_unaccounted(line=9, ...)`).
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
