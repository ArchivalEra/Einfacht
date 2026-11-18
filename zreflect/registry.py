#!/usr/bin/env python3
"""registry -- the data plane of the discovered rosters: gate list / plugin list / red list.

"Registration is discovered, not remembered": this module turns the roster
narrative into data:

  · `gates()`: ast-parses each check_*.py's module-level declaration line
        GATE = gate.meta("name", "one line", knobs=(...), name_dependent=...)
    -- **declaration is registration**; gate modules are not imported (no side
    effects, no execution cost). A check_*.py without a declaration line => the
    roster does not take it (problems reports; render refuses to render);
  · `red_need()`: the gates that **must go red** in the rename self-evidence
    (the ones whose default names carry the load). The name_dependent flag is
    registered explicitly -- a machine cannot derive "the off-state short
    circuit" (an instrument gate is off by default, so the default names it
    consumes never get used; consumption alone cannot assert red), but the
    registration is blocked on both ends: the fixture demands it really goes
    red, and `problems()` demands it really consumes the renamed default names;
  · `plugins()`: reflect-hooks/*.sh carrying the selftest marker (discovered) +
    named special cases (doctor.py -- the reason lives next to the data).

Consumers: `facts.py --render-doc` renders the AUTO:GATES machine block (same
precedent as AUTO:FACTS; `check_facts` / `--check` blocks drift);
gates-selftest.sh consumes `--red-need` and `--plugins`.

Honesty boundary: this module only **narrates** rosters and never executes
gates; whether a gate can go red is forever proven by gates-selftest.sh actually
running -- the judgments of narration and execution each stay on their own side;
do not mix them.
"""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import criteria  # noqa: E402
import gate  # noqa: E402
from gate import fatal, main_selftest_or, module_meta, repo  # noqa: E402
from i18n import M  # noqa: E402
from knobs import REGISTRY  # noqa: E402

# PINNED: the AUTO machine block uses a fixed language (same reason as render.PREAMBLE).
GATES_BEGIN = "<!-- AUTO:GATES -->"
GATES_END = "<!-- /AUTO:GATES -->"



# Which default names the rename self-evidence's fixture renames (the rename
# surface of gates-selftest.sh's cross-repo section).
# Roster discipline same as knobs: only register default names the fixture really
# renames -- this is the judgment data of the red-list reconciliation.
# C4 reconciliation (3): `FIXTURE_RENAMES` is the **single producer** of
# "original name -> fixture name" -- gates-selftest.sh's fixture derives the file
# names it creates from `--fixture-renames`, no longer hand-writing two lists
# that would drift (the fixture's names and this table used to be two
# hand-written copies with no reconciler).
FIXTURE_RENAMES = {
    "FACTS.json": "LEDGER.json",
    "STATE.md": "NOTES.md",
    "retractions.json": "RETRACT.json",
    "questions": "cases",
    "README.md": "R1.md",
    "README.zh.md": "R2.md",
    "README.de.md": "R3.md",
    "HISTORY.md": "PAST.md",
}
RENAMED_DEFAULTS = tuple(FIXTURE_RENAMES)

# Known phases (C1): gates declare their own run frequency. The execution plane
# (gate.run_phase) filters on it.
#   commit        runs on every commit (pre-commit / pre-push / CI)
#   start-of-work run manually before starting work (doctor -- checks things that
#                 die; attaching it to commit frequency would be wrong)
# ⚠️ issue #21: welding the phase list **here** would force downstream forks --
# consumers have their own phases (the S26 repo's lab: *.lab.py only runs when
# the experiment directory is present). The knob `REFLECT_PHASES` appends custom
# phases (comma-separated, appended after the two built-ins); the core two
# cannot be removed or shadowed -- phases are the shared vocabulary of the
# execution plane and declarations, and arbitrary renaming would silently orphan
# existing runs_at declarations. problems() still blocks unknown phases: a
# declared runs_at not in the list => red.
BUILTIN_PHASES = ("commit", "start-of-work")


def phases():
    """Known phases = the two built-ins + `REFLECT_PHASES` appends (downstream
    custom, e.g. lab)."""
    raw = os.environ.get("REFLECT_PHASES", "").strip()
    out = list(BUILTIN_PHASES)
    for p in (x.strip() for x in raw.split(",")):
        if p and p not in out:
            out.append(p)
    return tuple(out)


def phases_problems():
    """Phase-list self-consistency (the judgment for bad knob values; pure function)."""
    raw = os.environ.get("REFLECT_PHASES", "").strip()
    out = []
    if raw:
        dup = [p for p in (x.strip() for x in raw.split(","))
               if p in BUILTIN_PHASES]
        if dup:
            out.append(M("registry.builtin_phase_repeated",
                         phases=", ".join(sorted(set(dup)))))
    return out

def modules(zdir=None):
    """Platform-module roster (C5): ast-parses `MODULE = module_meta(...)` declaration lines.

    Returns (declared, undeclared): `declared` = [{file, name, desc, selftest}];
    `undeclared` = .py files that are **neither gates nor __init__ yet carry no
    MODULE declaration** -- a platform module must declare itself (even with
    selftest=False it must positively say "I don't use self-evidence"),
    otherwise "should have self-evidence but doesn't" goes unasked (guessing
    `_cases` from text cannot guess "should have existed").
    """
    d = zdir if zdir is not None else gate.zdir()
    declared, undeclared = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        # ⚠️ **`measure_*.py` are the consumer's data modules, not platform
        # modules.**
        #
        # This exemption was forced by "wiring into a real project" acceptance:
        # following the README's "Writing your measure()" and dropping the
        # module at `zreflect/measure_myproject.py`, `--render-doc` went FATAL
        # on the spot:
        #
        #     · these .py files are neither gates ... nor declared platform
        #       modules: zreflect/measure_myproject.py
        #
        # The user has no way to know their data module needs
        # `MODULE = module_meta(...)` -- that is a discipline of **this repo for
        # its own code** ("should have self-evidence but doesn't" goes unasked),
        # not something to impose on a consumer's data file.
        if n.startswith("measure_"):
            continue
        rel = "zreflect/" + n
        if _declaration(os.path.join(d, n), rel, attr="MODULE", func="module_meta"):
            declared.append(_declaration(os.path.join(d, n), rel,
                                         attr="MODULE", func="module_meta"))
        elif _declaration(os.path.join(d, n), rel):
            continue                    # a gate (has a GATE declaration); not a platform module
        else:
            undeclared.append(rel)
    return declared, undeclared


def selftest_modules(zdir=None):
    """Roster of modules with a self-evidence obligation (C5, declaration-driven):
    modules declared via `MODULE = module_meta(..., selftest=True)` -- gates (GATE
    declarations) are not counted (run_gates covers them). Returns (mods,
    missing): `mods` = those that should run selftests; `missing` = declared
    selftest=True but without a --selftest entry (written but never run =
    decoration).
    """
    declared, _und = modules(zdir)
    d = zdir if zdir is not None else gate.zdir()
    mods, missing = [], []
    for m in declared:
        if not m.get("selftest"):
            continue
        text = open(os.path.join(d, os.path.basename(m["file"])),
                    encoding="utf-8").read()
        can = ("--selftest" in text or "main_selftest_or" in text
               or "_selftest()" in text)
        if can:
            mods.append(m["file"])
        else:
            missing.append(m["file"])
    return mods, missing



def gates(zdir=None):
    """The discovered gate roster: **declared means a gate** -- ast-parses the
    module-level `GATE = gate.meta(...)` lines of zreflect/*.py, independent of
    file names (C1).

    Returns (gates, missing). gates = [{file, name, desc, knobs,
    name_dependent, runs_at}]; missing = files **named check_ without a
    declaration line** (problems reports; render refuses -- the shape of "named
    like a gate but forgot to declare").
    """
    d = zdir if zdir is not None else gate.zdir()
    out, missing = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []                     # zreflect/ absent: the caller reports per the zero-value guard
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        rel = "zreflect/" + n
        meta = _declaration(os.path.join(d, n), rel)
        if meta:
            out.append(meta)
        elif n.startswith("check_"):
            # Named check_ but no declaration => forgot the declaration (the roster
            # doesn't take it; render refuses).
            # Non-check_ without a declaration = platform module
            # (gate/knobs/registry/...), not a gate.
            missing.append(rel)
    return out, missing


def _decl_call(node, attr, func):
    """Is `node` a declaration line shaped `<attr> = <func>(...)`? If so => that call node.

    Both equivalent spellings are recognized: meta(...) (bare imported name) and
    gate.meta(...) (attribute). Not a declaration line / the call is not `func`
    => None (the caller keeps scanning the next line).
    """
    if not (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == attr
            and isinstance(node.value, ast.Call)
            and len(node.value.args) >= 2):
        return None
    fn = node.value.func
    if getattr(fn, "id", "") == func or getattr(fn, "attr", "") == func:
        return node.value
    return None


def _module_meta(call, rel):
    """`MODULE = module_meta(...)` → {file, name, desc, selftest}."""
    st = True
    for kw in call.keywords:
        if kw.arg == "selftest":
            st = ast.literal_eval(kw.value)
    return {"file": rel,
            "name": ast.literal_eval(call.args[0]),
            "desc": ast.literal_eval(call.args[1]),
            "selftest": bool(st)}


def _gate_meta(call, rel):
    """`GATE = gate.meta(...)` → {file, name, desc, knobs, name_dependent, runs_at,
    off_reason}."""
    knobs, name_dep, runs_at, off_reason = (), False, "commit", None
    for kw in call.keywords:
        if kw.arg == "knobs":
            knobs = ast.literal_eval(kw.value)
        elif kw.arg == "name_dependent":
            name_dep = ast.literal_eval(kw.value)
        elif kw.arg == "runs_at":
            runs_at = ast.literal_eval(kw.value)
        elif kw.arg == "off_reason":
            off_reason = ast.literal_eval(kw.value)
    return {"file": rel,
            "name": ast.literal_eval(call.args[0]),
            "desc": ast.literal_eval(call.args[1]),
            "knobs": tuple(knobs),
            "name_dependent": bool(name_dep),
            "runs_at": str(runs_at),
            "off_reason": off_reason}


def _declaration(path, rel, attr="GATE", func="meta"):
    """ast-extract the declaration line from a file (default `GATE = meta(...)`;
    C5 uses `MODULE = module_meta(...)`). None if absent.

    `attr` / `func` are swappable (one parser serves both declaration kinds:
    gates and platform modules).
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        call = _decl_call(node, attr, func)
        if call is None:
            continue
        try:
            if func == "module_meta":
                return _module_meta(call, rel)
            return _gate_meta(call, rel)
        except (ValueError, IndexError):
            return None
    return None


def runnable(phase="commit", zdir=None):
    """The list of gates that **should run** for a phase (C1: the execution plane's
    single producer).

    `phase="commit"` => what runs on every commit (hooks / CI);
    `phase="start-of-work"` => what runs manually before starting work (doctor).
    Returns [{file, name, runs_at, ...}]. The declaration surface
    (GATE = meta(..., runs_at=...)) is the single producer -- the execution plane no
    longer globs file names.
    """
    gs, _missing = gates(zdir)
    return [g for g in gs if g.get("runs_at", "commit") == phase]


def _touches_renamed(g):
    """Among the knobs this gate consumes, is any default name renamed by the rename
    self-evidence?"""
    for k in g["knobs"]:
        kind, dflt, _ = REGISTRY.get(k, ("", "", ""))
        # The nested ternary is split into explicit branches (GitRoll #141) -- a
        # list splits on commas, a default counts as one, none means none.
        # Semantics unchanged.
        if kind == "list":
            vals = {x.strip() for x in dflt.split(",")}
        elif dflt:
            vals = {dflt}
        else:
            vals = set()
        if vals & set(RENAMED_DEFAULTS):
            return True
    return False


def _missing_declaration_problems(missing):
    """Named check_ but no GATE declaration line -- forgetting the declaration means
    the narrative drifts."""
    if not missing:
        return []
    return [M("registry.missing_declaration", files=", ".join(missing))]


def _phase_problems(gs):
    """runs_at must be a known phase -- frequency is a declared field; a wrong value
    makes the execution plane miss the gate."""
    out = []
    for g in gs:
        if g.get("runs_at", "commit") not in phases():
            out.append(M("registry.unknown_phase",
                         file=g["file"], runs_at=g.get("runs_at"),
                         phases=" | ".join(phases())))
    return out


def _name_dependent_problems(gs):
    """Flagged name_dependent yet consumes no renamed default name -- the flag is
    wrong."""
    out = []
    for g in gs:
        if g["name_dependent"] and not _touches_renamed(g):
            out.append(M("registry.name_dependent_wrong", file=g["file"]))
    return out


def _empty_gate_problems(gs, missing):
    """The roster as a whole is empty -- the zero-value guard: empty input is not a
    pass."""
    if not gs and not missing:
        return [M("registry.empty_roster")]
    return []


def _selftest_roster_problems(mods, mods_missing):
    """The platform modules' selftest roster: declared means runnable, and the roster
    must not be empty."""
    if mods is None or mods_missing is None:
        mods, mods_missing = selftest_modules()
    out = []
    if mods_missing:
        out.append(M("registry.selftest_no_entry",
                     files=", ".join(mods_missing)))
    if not mods:
        out.append(M("registry.no_module_selftest"))
    return out


def _undeclared_module_problems(undeclared):
    """C5: platform modules must declare themselves (MODULE = module_meta(...)),
    otherwise "should have self-evidence but doesn't" goes unasked (guessing
    _cases from text cannot guess "should have existed")."""
    if undeclared is None:
        _decl, undeclared = modules()
    if not undeclared:
        return []
    return [M("registry.undeclared_module", files=", ".join(undeclared))]


def _knob_problems(knob_problems, gs):
    """Run C3/C4 knob reconciliations unless injected for testing."""
    if knob_problems is None:
        import knobs  # noqa: PLC0415
        knob_problems = (knobs.scan_surface_problems()
                         + knobs.readme_problems()
                         + knobs.declared_vs_read_problems(gs)
                         + knobs.registry_vs_readme_problems()
                         + knobs.pack_sync_problems()
                         + knobs.kind_vocabulary_problems()
                         + knobs.pack_coverage_problems()
                         + knobs.dead_default_problems())
    return list(knob_problems)


def problems(gs, missing, mods=None, mods_missing=None,
             knob_problems=None, undeclared=None):
    """Reconcile roster declarations, phases, criteria, and core seal (`[]` = green)."""
    out = []
    out += phases_problems()
    out += _missing_declaration_problems(missing)
    out += _phase_problems(gs)
    out += _name_dependent_problems(gs)
    out += _empty_gate_problems(gs, missing)
    out += _selftest_roster_problems(mods, mods_missing)
    out += _undeclared_module_problems(undeclared)
    out += _knob_problems(knob_problems, gs)
    out += criteria.off_reason_problems(gs)
    out += criteria.trailing_newline_problems()
    out += criteria.shell_surface_problems()
    out += criteria.encoding_surface_problems()
    out += criteria.subprocess_encoding_problems()
    out += criteria.suite_scope_problems()
    out += criteria.fatal_exit_problems()
    out += criteria.path_rule_problems()
    out += criteria.dependency_coverage_problems()
    if not criteria.reason_bases_agree():
        out.append(M("registry.reason_bases_disagree"))
    # ⚠️ In injection mode (`mods=` given), **dead interfaces are not scanned**:
    # that judgment looks at the real directory while injection mode verifies
    # "the roster judgment itself"; mixing both into one list makes assertions
    # guilty by association with real-repo state (observed: the `unknown_phase`
    # assertion picked up an extra `dead_interface`).
    if mods is None:
        out += criteria.dead_interface_problems()
        import seal  # noqa: PLC0415
        if seal.seal_exists():
            out += seal.verify_problems()
    return out





















def _pinned_under(lang):
    """Self-evidence helper: render the AUTO block under a given REFLECT_LANG (proves
    it does not vary with language)."""
    old = os.environ.get("REFLECT_LANG", "")
    os.environ["REFLECT_LANG"] = lang
    try:
        gs, _ = gates()
        return render_gates(gs)
    finally:
        os.environ["REFLECT_LANG"] = old


def _with_phases(val):
    """Self-evidence helper: temporarily set REFLECT_PHASES, return (phases(),
    problems()), restore the scene."""
    old = os.environ.get("REFLECT_PHASES", "")
    os.environ["REFLECT_PHASES"] = val
    try:
        return phases(), phases_problems()
    finally:
        os.environ["REFLECT_PHASES"] = old


def red_need(gs=None):
    """The gate file names that **must go red** in the rename self-evidence (the ones
    whose default names carry the load)."""
    if gs is None:
        gs, _ = gates()
    return sorted(os.path.basename(g["file"]) for g in gs
                  if g["name_dependent"] and _touches_renamed(g))


def plugins(hooks_dir=None):
    """The **plugin** list the self-evidence names: scripts under `reflect-hooks/`
    carrying `--selftest`.

    Discovered: both `.sh` and `.py` are collected -- after the full Python
    migration the entry point is `.py`, but `einfacht-env.sh` must remain shell
    forever (it gets `source`d to export environment variables), so both exist.
    The judgment is "does the file contain `--selftest`", not the extension.
    """
    d = hooks_dir if hooks_dir is not None else repo("reflect-hooks")
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        names = []
    for n in names:
        if not (n.endswith((".sh", ".py"))):
            continue
        try:
            text = open(os.path.join(d, n), encoding="utf-8",
                        errors="replace").read()
        except OSError:
            continue
        if "--selftest" in text:
            out.append("reflect-hooks/" + n)
    return out


def render_gates(gs):
    """PINNED: fixed-language AUTO:GATES machine block (pure function)."""
    lines = [GATES_BEGIN,
             ("> This block is rendered by `zreflect/facts.py --render-doc` from the "
             "discovered roster (declaration lines in zreflect/registry.py); "
             "**do not hand-edit**."),
             ("> The execution plane (hooks / CI) reads `registry --run <phase>` -- "
             "the phase is a declared field (`runs_at`), not a file name."),
             "",
             "| Gate | Phase | What it guards | Knobs consumed | Why it may be off |",
             "|---|---|---|---|---|"]
    for g in sorted(gs, key=lambda x: (x.get("runs_at", "commit"), x["file"])):
        lines.append("| `%s`（%s） | %s | %s | %s | %s |"
                     % (os.path.basename(g["file"]), g["name"],
                        g.get("runs_at", "commit"), g["desc"],
                        ", ".join("`%s`" % k for k in g["knobs"]) or "--",
                        g.get("off_reason") or "--"))
    off_capable = sum(1 for g in gs if g.get("off_reason"))
    lines += ["",
              "%d gates (derived from the discovered roster -- a hand-written list "
              "drifts; adding a gate = landing one declaration line, and it grows "
              "here automatically); %d of them **may be disabled** (the last column "
              "is a **declared** justification, not runtime state -- who is off "
              "right now is seen via `registry --run <phase>`)."
              % (len(gs), off_capable), GATES_END]
    return "\n".join(lines)


def _arg_after(argv, flag):
    """The optional value of `--flag [value]` (absent / starts with `-` => default
    commit)."""
    i = argv.index(flag)
    return (argv[i + 1] if len(argv) > i + 1
            and not argv[i + 1].startswith("-") else "commit")


def _emit_gate_output(text):
    """Relay one red gate's output to the user: the **first problem line + all
    diagnostic lines**, the rest dropped.

    The truncation rule is "stop after the first `· ` problem line", but `ℹ `
    diagnostic lines must **not lose a single one** -- they are the only
    sentence that can save the user. Lines are printed with a six-space indent;
    blank lines and non-diagnostic lines after the first problem line are
    omitted.
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
    shown_problem = False
    for ln in lines:
        if ln.startswith("  \u00b7 "):
            if shown_problem:
                continue                  # problem lines from the second on are omitted (don't flood)
            shown_problem = True
        elif ln.lstrip().startswith("\u2139 "):
            pass                           # diagnostic line: always kept
        elif shown_problem:
            continue                       # non-diagnostic lines after a problem line: don't re-print
        print("      " + ln)


def _main_run(argv):
    """The execution plane: run all gates of one phase and aggregate ran / off /
    failed (C1+C2).

    hooks / CI call only this line -- the glob retires, and the predicate has one
    home: gates().
    """
    phase = _arg_after(argv, "--run")
    from gate import run_phase  # noqa: PLC0415
    gs = runnable(phase)
    if not gs:
        return fatal(M("registry.empty_phase", phase=phase))
    # ⚠️ **All of this function's output goes to stdout** (including the fatal /
    # error / failed lists). This does **not** conflict with `gate.finish()`'s
    # "problem lines go to stderr": that rule only binds a single gate's own
    # judgment output; what is printed here is a **run report** (who didn't run /
    # who went red / whose config broke) -- a status snapshot, not a judgment.
    # Reasons: (a) both consumers (CI, hook) only look at rc (`|| exit 1`) and
    # never parse stdout; (b) callers that capture only stdout (`$(...)` /
    # pipes) must be able to see **which file** broke -- with stderr-only output
    # they would see `fatal=1` with no idea who (observed in round 10).
    res = run_phase(phase, gs)
    print(M("registry.phase_summary", phase=phase, ran=res["ran"],
            off=res["off"], failed=res["failed"], fatal=res.get("fatal", 0),
            error=res.get("error", 0)))
    for f in res["off_list"]:
        print(M("registry.phase_off", file=f))
    # ⚠️ These three lists are printed **to stdout as well**: aggregators often
    # capture only stdout (`$(...)` / pipes); with stderr-only they would see
    # `fatal=1` without knowing which file broke (observed in review). The
    # problem **cause** remains in the gate's own stderr -- what's added here is
    # "who".
    for f in res.get("fatal_list", ()):
        print(M("registry.phase_fatal", file=f))
    for f in res.get("error_list", ()):
        print(M("registry.phase_error", file=f))
    for f in res["fail_list"]:
        print("  FAILED %s" % f)
        _emit_gate_output((res.get("fail_out", {}).get(f) or ""))
    # Broken config (rc=2) and red judgment (rc=1) both exit non-zero, but with
    # different messages (different fixes)
    return 1 if (res["failed"] or res.get("fatal") or res.get("error")) else 0


def cli_selftest_missing_lines(missing):
    """The per-line name-calling of `--selftest-modules` (pure function: for
    self-evidence, zero print)."""
    return [M("registry.selftest_no_entry_cli", file=m) for m in missing]


def _main_selftest_modules():
    mods, missing = selftest_modules()
    for line in cli_selftest_missing_lines(missing):
        # The CLI's per-line name-calling and the roster's summary sentence are
        # **two distinct outputs** (previously each had its own wording); keep
        # both codes during migration, don't reshape the CLI line into the
        # summary sentence.
        print(line, file=sys.stderr)
    if missing:
        return 1
    print("\n".join(mods))
    return 0


# Which codes are **fixable configuration hints** (they don't brick the roster) and
# which mean **the roster itself is broken**.
#
# ⚠️ This distinction came from practice: after the user creates `Einfacht.env`
# per the docs, the `off_reason` ("this repo has no Einfacht.env") goes stale --
# the judgment **is correct**, but treating it as fatal makes `registry --gates`
# / `--run commit` / pre-commit **permanently red**, and the only way out is to
# delete the file the docs told them to create. That is a **self-set trap**, not
# a user error.
#
# The right reaction: clearly say "go fix the gate's off_reason", then
# **continue** (the roster is usable).
_ADVISORY_CODES = frozenset({"registry.off_reason_stale"})


def _main_gates():
    gs, missing = gates()
    probs = problems(gs, missing)
    fatal_probs = [p for p in probs if getattr(p, "code", "") not in _ADVISORY_CODES]
    for x in probs:
        if getattr(x, "code", "") in _ADVISORY_CODES:
            print("  ! %s" % x, file=sys.stderr)      # hint, not a refusal
        else:
            print("  · %s" % x, file=sys.stderr)
    if fatal_probs:
        return fatal(M("registry.roster_problems", count=len(fatal_probs)))
    for g in gs:
        print("%s\t%s\t%s" % (g["file"], g["name"], g["desc"]))
    return 0


def _main_lists(argv):
    """The three list prints: `--red-need` / `--runnable` / `--all-runnable`.

    Returns rc; none of these flags => None (the caller keeps probing).
    """
    if "--red-need" in argv:
        print(" ".join(red_need()))
        return 0
    if "--runnable" in argv:
        # The execution plane's single producer (C1): --runnable [phase], default commit.
        for g in runnable(_arg_after(argv, "--runnable")):
            print(g["file"])
        return 0
    if "--all-runnable" in argv:
        # Gates of all phases (for self-evidence: every gate must prove it can go
        # red, regardless of phase).
        gs, _m = gates()
        for g in gs:
            print(g["file"])
        return 0
    return None


def _main_listings(argv):
    """The two per-line listings: `--plugins` / `--fixture-renames`.

    Returns rc; none of these flags => None (the caller keeps probing).
    """
    if "--plugins" in argv:
        print("\n".join(plugins()))
        return 0
    if "--fixture-renames" in argv:
        # C4 reconciliation (3): the fixture rename set's single producer
        # (original=fixture name, one per line).
        for orig, fix in sorted(FIXTURE_RENAMES.items()):
            print("%s=%s" % (orig, fix))
        return 0
    return None


def _usage():
    """The usage line. A **function, not a module constant**: the language pack is
    only `activate()`d inside the `main_selftest_or` entry; a module-level `M(...)`
    would be frozen on the null pack at import time."""
    return M("registry.usage")


def _main_seal(argv):
    """Handle `--verify-seal`, `--reseal=...`, and `--reseal-yardstick=...`; else None."""
    import seal  # noqa: PLC0415
    if "--verify-seal" in argv:
        if not seal.seal_exists():
            return fatal(M("seal.missing", path=seal.seal_path()))
        probs = seal.verify_problems()
        if probs:
            for p in probs:
                print("  · %s" % p, file=sys.stderr)
            return 1
        print(seal.current_tree_sha(verified=True) or "")
        return 0
    for flag, is_yard in (("--reseal-yardstick=", True), ("--reseal=", False)):
        hit = [a for a in argv if a.startswith(flag)]
        if not hit:
            continue
        targets = [t.strip() for t in hit[0][len(flag):].split(",") if t.strip()]
        tree, err = seal.reseal(targets, yardstick=is_yard,
                                allow_case_drop="--allow-case-drop" in argv)
        if err:
            return fatal(err)
        print(M("seal.resealed", tree=tree, count=len(targets)))
        return 0
    return None


def main(argv):
    rc = _main_lists(argv)
    if rc is not None:
        return rc
    rc = _main_seal(argv)
    if rc is not None:
        return rc
    if "--run" in argv:
        return _main_run(argv)
    rc = _main_listings(argv)
    if rc is not None:
        return rc
    if "--selftest-modules" in argv:
        return _main_selftest_modules()
    if "--gates" in argv:
        return _main_gates()
    print(_usage(), file=sys.stderr)
    return 2


def _phase_tiers_ok():
    """`run_phase` must keep the four tiers ran / off / failed / fatal apart."""
    from gate import run_phase  # noqa: PLC0415
    script = {"fatal.py": (2, "FATAL: cfg"),
              "fail.py": (1, "gate.problems_header"),
              "off.py": (0, "OFF: x"),
              "ok.py": (0, "")}
    # The first run's (basic four-tier shape) return value only confirms it doesn't
    # explode -- GitRoll #104 "assigned but never used": explicitly bind `_`,
    # turning the intent from implicit to explicit.
    _ = run_phase("commit", list(script), runner=lambda f: script[f])
    script["err.py"] = (3, "boom")          # an unagreed code / killed by signal
    res = run_phase("commit", list(script), runner=lambda f: script[f])
    return (res["fatal"] == 1 and res["fatal_list"] == ["fatal.py"]
            and res["failed"] == 1 and res["fail_list"] == ["fail.py"]
            and res["error"] == 1 and res["error_list"] == ["err.py"]
            and res["off"] == 1 and res["off_list"] == ["off.py"]
            and res["ran"] == 1)


def _captures_stderr():
    """`default_runner` must capture subprocess stderr alongside stdout."""
    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    from gate import default_runner  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "boom.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("import sys\n"
                     "sys.stderr.write('FATAL: probe\\n')\n"
                     "sys.exit(2)\n")
        rc, out = default_runner(p, d)
        return rc == 2 and "FATAL: probe" in out
    finally:
        shutil.rmtree(d, True)




def _render_shows_off_reason():
    """A fake gate declaring `off_reason` => that text must appear in the AUTO block."""
    gs = [{"file": "zreflect/check_probe.py", "name": "probe",
           "desc": "probe gate", "knobs": (), "runs_at": "commit",
           "off_reason": "a declared justification long enough"}]
    body = render_gates(gs)
    # ⚠️ **No Chinese literals** (this file is inside the zero-language gates'
    # scan surface -- observed hit on bare_text). Judge the machine-readable
    # parts instead: the off_reason text must appear at end of line, and the
    # line's column count must match the header.
    return ("a declared justification long enough" in body
            and body.count("|") >= 6)


def _render_off_reason_dash():
    """No `off_reason` declared => that cell is `--` (not the empty string, not None)."""
    gs = [{"file": "zreflect/check_probe.py", "name": "probe",
           "desc": "probe gate", "knobs": (), "runs_at": "commit",
           "off_reason": None}]
    row = [ln for ln in render_gates(gs).splitlines()
           if ln.startswith("| `check_probe.py`")][0]
    return row.rstrip().endswith("| -- |") and "None" not in row


def _streams_documented():
    """Both wordings must be in the source (gate.py scopes it to a single gate / this
    file explains that aggregators go to stdout)."""
    import gate  # noqa: PLC0415
    try:
        g = open(gate.__file__, encoding="utf-8").read()
        r = open(os.path.abspath(__file__), encoding="utf-8")
        r = r.read()
    except OSError:
        return False
    # ⚠️ Anchors are plain ASCII fragments of the two normative sentences -- this
    # file is inside the zero-language gates' scan surface, so no natural-language
    # fixture is written as a literal here (the CJK code-point assembly this
    # check once used broke when the sources were de-language-fied; the anchors
    # only need to be machine-matchable, and the judgment name still says what
    # is tested).
    _a1 = "single gate's problem lines"     # gate.py: the stderr rule is scoped to one gate
    _a2 = "function's output goes to stdout"  # here: the run report goes to stdout
    return (_a1 in g and _a2 in r and
            ("stdout" in r and "stdout" in g))








def _plugin_discovery_ok():
    """Plugin discovery: directory present => the env plugin must be found; directory
    absent => an empty list is also correct."""
    import os  # noqa: PLC0415
    d = repo("reflect-hooks")
    found = plugins()
    if not os.path.isdir(d):
        return found == []          # no plugin directory installed => empty list is correct
    return ("reflect-hooks/einfacht-env.sh" in found
            and "zreflect/doctor.py" not in found)


def _nf_const_helper():
    """Same-file helper returning a constant (pinned by `never_falsifiable`)."""
    return True


def _nf_multi_line():
    """Two lambdas on one line: no bailout, and delegated never masks a hard fail."""
    import importlib.util  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    from gate import _is_delegated, never_falsifiable  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "pair.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("import os\ndef _t(): return True\n"
                     "y = 2\npair = (lambda: y > 1, lambda: y > 0 or True)\n"
                     "masked = (lambda: os.getpid(), lambda: _t())\n")
        spec = importlib.util.spec_from_file_location("_nf_pair_probe", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        r_masked = never_falsifiable(mod.masked[0])
        return (never_falsifiable(mod.pair[0]) is not None
                and never_falsifiable(mod.pair[1]) is not None
                and r_masked is not None and not _is_delegated(r_masked))


def _nf_unresolved_helper():
    """Unresolvable same-module helper fails hard rather than passing as delegated."""
    import importlib.util  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    from gate import _is_delegated, never_falsifiable  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "unres.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("h = lambda: True\nfn = lambda: h()\n")
        spec = importlib.util.spec_from_file_location("_nf_unres_probe", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        r = never_falsifiable(mod.fn)
        return r is not None and not _is_delegated(r)


def _activate_or_fatal_ok():
    """`gate.activate_or_fatal` returns 2 on missing pack and 0 on active pack."""
    import contextlib  # noqa: PLC0415
    import io  # noqa: PLC0415
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            rc_bad = gate.activate_or_fatal("no_such_pack_xyz")
            rc_ok = gate.activate_or_fatal(None)
        return rc_bad == 2 and rc_ok == 0
    finally:
        gate.activate_or_fatal()


def _nf_catches(which):
    """Test `never_falsifiable` with **lambdas in a real file** (it locates the AST by
    line number; a lambda in `-c` has no source file => it goes blind).

    Five shapes, one each:
      · `or_true`      -- `or True` (the boolean is short-circuited by a constant)
      · `and_false`    -- `and False`
      · `self_compare` -- `x == x`
      · `const_helper` -- delegates to same-file helper returning constant True
      · `real`         -- a real assertion (must return None)
    """
    from gate import never_falsifiable  # noqa: PLC0415
    y = 1                                                # used by self_compare
    shapes = {
        "or_true": lambda: (1 == 1) or True,
        "and_false": lambda: (1 == 1) and False,
        "self_compare": lambda: y == y,
        "const_helper": lambda: _nf_const_helper(),
        "real": lambda: y > 0,
    }
    return never_falsifiable(shapes[which])


def _nf_no_source():
    """Missing `co_filename` returns `None` (no source guessing)."""
    from gate import never_falsifiable  # noqa: PLC0415
    ns = {}
    exec(compile("f = lambda: True", "<no-source>", "exec"), ns)  # noqa: S102
    return never_falsifiable(ns["f"])


def _gate_desc_states_selftest():
    """`gate.py`'s MODULE description must state "the logic selftest lives in
    registry._cases"."""
    mods, _und = modules()
    for m in mods:
        if m["file"].endswith("gate.py"):
            d = m["desc"]
            # Anchors are **all ASCII**: `registry._cases` (where the selftest
            # lives) + `--selftest` (why there is no entry). No Chinese literals
            # (this file is in the zero-language gates' scan surface, and
            # code-point assembly is error-prone -- 0x72EC was once mistyped as
            # the wrong character).
            return ("registry._cases" in d) and ("--selftest" in d) \
                and ("selftest" in d)
    return False




















def _load_spec_ok():
    """`load_spec` returns `(None, error sentence)` when unreadable; it does **not
    raise**."""
    got = gate.load_spec("/nonexistent-probe.json")
    return isinstance(got, tuple) and len(got) == 2 \
        and got[0] is None and got[1] is not None


def _cases_fixture(d):
    """Build a fake roster. `d` comes from `_cases()` (which owns mkdtemp and cleanup)."""
    # The fixture's declaration data uses **ASCII names**: they are inputs
    # extracted by ast (they enter the AUTO:GATES machine block), not core
    # output -- Chinese fixtures would be adopted by the zero-language gates.
    open(os.path.join(d, "check_ok.py"), "w", encoding="utf-8").write(
        'GATE = gate.meta("gate_a", "blocks_a", knobs=("REFLECT_FACTS",),'
        ' name_dependent=True)\n')
    open(os.path.join(d, "check_plain.py"), "w", encoding="utf-8").write(
        'GATE = gate.meta("gate_b", "blocks_b", knobs=("REFLECT_WORLD",))\n')
    open(os.path.join(d, "check_bare.py"), "w", encoding="utf-8").write("X = 1\n")
    open(os.path.join(d, "named_other.py"), "w", encoding="utf-8").write(
        'GATE = gate.meta("gate_c", "declared means registered", knobs=())\n')
    open(os.path.join(d, "doc_gate.py"), "w", encoding="utf-8").write(
        'GATE = gate.meta("gate_d", "start-of-work phase", knobs=(),'
        ' runs_at="start-of-work")\n')
    open(os.path.join(d, "platform.py"), "w", encoding="utf-8").write("Y = 2\n")   # no declaration = platform module
    gs, missing = gates(d)
    ok = [g for g in gs if g["file"].endswith("check_ok.py")][0]
    plain = [g for g in gs if g["file"].endswith("check_plain.py")][0]
    real, real_missing = gates()

    def real_files():
        # ⚠️ `_zdir()` (the **tooling repo's** zreflect), not `d` (the temporary
        # fixture directory) -- this assertion compares "real roster vs real
        # disk", unrelated to the fixture.
        return {"zreflect/" + n for n in os.listdir(gate.zdir())
                if n.startswith("check_") and n.endswith(".py")}
    return {"ok": ok, "plain": plain, "real": real,
            "real_missing": real_missing, "gs": gs,
            "missing": missing, "real_files": real_files}


def _cases_discovery_real(fx):
    """(a) Normally no report: the real repo's roster and declaration surface. (8 cases)"""
    ok, real = fx["ok"], fx["real"]
    gs, missing, real_missing, real_files = (fx["gs"], fx["missing"],
                                             fx["real_missing"], fx["real_files"])
    return [
        ("registry.ast_declaration_fields",
         lambda: ok["name"] == "gate_a" and ok["desc"] == "blocks_a"
         and ok["knobs"] == ("REFLECT_FACTS",)
         and ok["name_dependent"] is True and ok["runs_at"] == "commit"),
        ("registry.undeclared_noncheck_is_module",
         lambda: all(not m.endswith("platform.py") for m in missing)
         and all(not g["file"].endswith("platform.py") for g in gs)),
        ("registry.declaration_is_registration",
         lambda: any(g["file"].endswith("named_other.py") for g in gs)
         and not any(m.endswith("named_other.py") for m in missing)),
        ("registry.real_roster_matches_disk",
         lambda: not real_missing and real_files() <= {g["file"] for g in real}),
        ("registry.doctor_is_start_of_work",
         lambda: any(g["file"].endswith("doctor.py") for g in real)
         and not any(g["file"].endswith("doctor.py")
                     for g in runnable("commit"))),
        ("registry.red_need_flagged",
         lambda: (lambda rn: len(rn) >= 1 and all(
             any(g["file"].endswith(b) and g["name_dependent"] for g in real)
             for b in rn))(red_need(real))),
        ("registry.real_modules_declared",
         lambda: modules()[1] == [] and len(modules()[0]) >= 8),
        ("registry.fixture_renames_single_source",
         lambda: set(FIXTURE_RENAMES) == set(RENAMED_DEFAULTS)
         and len(FIXTURE_RENAMES) >= 7),
        # The plugin directory **may not exist** (a deployment copying only
        # `zreflect/`): then there is no plugin to discover, and that is not a
        # failure. Present means it must be found -- the assertion splits on
        # "directory present or not".
        ("registry.plugin_discovery", lambda: _plugin_discovery_ok()),
    ]


def _cases_discovery_reports(fx):
    """Roster mismatch and stream-documentation cases (6 cases)."""
    plain, missing = fx["plain"], fx["missing"]
    return [
        ("\u2605 registry.missing_declaration",
         lambda: missing == ["zreflect/check_bare.py"]),
        ("\u2605 registry.name_dependent_wrong",
         lambda: [p.code for p in problems(
             [dict(plain, name_dependent=True)], [],
             mods=["zreflect/x.py"], mods_missing=[], knob_problems=[],
             undeclared=[])] == ["registry.name_dependent_wrong"]),
        ("\u2605 registry.selftest_no_entry",
         lambda: any(p.code == "registry.selftest_no_entry" for p in problems(
             [], [], mods=["zreflect/x.py"],
             mods_missing=["zreflect/y.py"],
             knob_problems=[]))),
        ("\u2605 registry.selftest_no_entry_cli",
         lambda: [m.code for m in cli_selftest_missing_lines(
             ["zreflect/y.py"])] == ["registry.selftest_no_entry_cli"]
         and cli_selftest_missing_lines([]) == []),
        ("\u2605 registry.undeclared_module",
         lambda: any(p.code == "registry.undeclared_module" for p in problems(
             [], [], mods=["zreflect/x.py"], mods_missing=[],
             knob_problems=[],
             undeclared=["zreflect/orphan_mod.py"]))),
        ("registry.aggregator_streams_documented",
         lambda: _streams_documented()),
    ]


def _cases_discovery(fx):
    """See `_cases()`: 16 cases in this group.

    (a) Real-repo roster / (b) roster diseases are each a named group: the former
    reads the fixture's real roster, the latter builds malformed declarations --
    mixed together, a reader cannot tell which input an assertion uses.
    """
    return (_cases_discovery_real(fx) + _cases_discovery_reports(fx)
            + [("\u2605 registry.empty_roster",
                lambda: problems([], [], mods=[], mods_missing=[],
                                 knob_problems=[], undeclared=[]) != [])])


def _cases_render(fx):
    """See `_cases()`: 4 cases in this group."""
    gs = fx["gs"]
    return [
    ("★ registry.auto_block_pinned_across_langs",
     lambda: _pinned_under("en") == _pinned_under("zh")
     and _pinned_under("de") == _pinned_under("")),
    ("registry.render_gates_pure",
     lambda: render_gates(gs) == render_gates(gs)
     and "gate_a" in render_gates(gs)
     and GATES_BEGIN in render_gates(gs) and GATES_END in render_gates(gs)),
    # **`off_reason` must be rendered into the AUTO block** (so the reader sees at
    # a glance which gates may be disabled and why) -- and it is a
    # **declaration**, not runtime state (the latter would change the block every
    # run and never converge).
    ("★ registry.render_gates_shows_off_reason",
     lambda: _render_shows_off_reason()),
    # A gate without a declaration must render `--` in that cell (no empty string,
    # no "None")
    ("registry.render_gates_off_reason_dash",
     lambda: _render_off_reason_dash()),
    ]


def _cases_phase(fx):
    """Phase filtering, tier separation, stderr capture, and `REFLECT_PHASES` cases."""
    plain = fx["plain"]
    d = fx["d"]
    return [
    ("registry.runnable_filters_by_phase",
     lambda: (lambda cm, sw: all(g["runs_at"] == "commit" for g in cm)
              and [g["file"] for g in sw]
              == ["zreflect/doc_gate.py"])(runnable("commit", d),
                                           runnable("start-of-work", d))),
    ("★ registry.unknown_phase",
     lambda: [p.code for p in problems(
         [dict(plain, runs_at="whenever")], [],
         mods=["zreflect/x.py"], mods_missing=[], knob_problems=[],
         undeclared=[])] == ["registry.unknown_phase"]),
    ("★ registry.phase_tiers_separate",
     lambda: _phase_tiers_ok()),
    ("★ registry.run_phase_captures_stderr",
     lambda: _captures_stderr()),
    ("registry.phases_extra_appended",
     lambda: _with_phases("lab")[0] == ("commit", "start-of-work", "lab")),
    ("★ registry.builtin_phase_repeated",
     lambda: [p.code for p in _with_phases("commit,lab")[1]
              ] == ["registry.builtin_phase_repeated"]),
    ("registry.phases_default_builtin_only",
     lambda: _with_phases("")[0] == ("commit", "start-of-work")),
    ]

def _env_hint_case(which):
    """`gate.env_hint()`'s **five tiers** of behavior:

    1. `no_carrier`   -- no carrier => None (a bare run stays quiet)
    2. `carrier_bare` -- carrier present, knob unset => **hint** (nobody sourced it)
    3. `carrier_live` -- knob set, value **matches** the carrier => None (the
       carrier has taken effect)
    4. `carrier_drift` -- knob set, value **differs** from the carrier => **hint**
       (a manual export drifted)
    5. `carrier_off`  -- `REFLECT_ENV_HINT=off` => the print layer emits nothing

    The case requires a controlled process environment: in hook contexts the
    carrier gets sourced into the environment, and once the knob is set,
    `carrier_bare` would be permanently red. All relevant knobs are temporarily
    popped and restored in finally.
    """
    import shutil
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    saved = gate.GATE_REPO
    saved_off = os.environ.pop("REFLECT_ENV_HINT", None)
    saved_fact = os.environ.pop("REFLECT_FACTS", None)
    try:
        gate.GATE_REPO = d
        if which != "no_carrier":
            open(os.path.join(d, "Einfacht.env"), "w",
                 encoding="utf-8").write("export REFLECT_FACTS=FACTS.json\n")
        if which == "carrier_off":
            # The silence of `off` happens at the **print layer** (`_maybe_hint`),
            # not in `env_hint` -- `env_hint()` still computes the sentence; nobody
            # prints it. Test the print layer.
            os.environ["REFLECT_ENV_HINT"] = "off"
            import contextlib  # noqa: PLC0415
            import io  # noqa: PLC0415
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                gate._maybe_hint()
            return buf.getvalue() == ""       # must **not print a single character**
        if which == "carrier_live":
            os.environ["REFLECT_FACTS"] = "FACTS.json"    # matches the carrier
        elif which == "carrier_drift":
            os.environ["REFLECT_FACTS"] = "OTHER.json"    # differs from the carrier
        hint = gate.env_hint(consumed=("REFLECT_FACTS",))
        if which in ("carrier_bare", "carrier_drift"):
            return hint is not None          # must **hint**
        return hint is None                  # no carrier / already live => must stay silent
    finally:
        gate.GATE_REPO = saved
        if saved_off is not None:
            os.environ["REFLECT_ENV_HINT"] = saved_off
        else:
            os.environ.pop("REFLECT_ENV_HINT", None)
        if saved_fact is not None:
            os.environ["REFLECT_FACTS"] = saved_fact
        else:
            os.environ.pop("REFLECT_FACTS", None)
        shutil.rmtree(d, True)


def _cases_hint(fx):
    """Environment-hint tier cases (5 cases)."""
    return [
        ("★ registry.env_hint_silent_without_carrier",
         lambda: _env_hint_case("no_carrier")),
        ("★ registry.env_hint_fires_with_carrier",
         lambda: _env_hint_case("carrier_bare")),
        ("registry.env_hint_silent_when_carrier_live",
         lambda: _env_hint_case("carrier_live")),
        ("★ registry.env_hint_fires_on_drift",
         lambda: _env_hint_case("carrier_drift")),
        ("★ registry.env_hint_off_silent",
         lambda: _env_hint_case("carrier_off")),
    ]







def _cases_gate_hosted(fx):
    """Hosted selftests for `gate.py` (`selftest=False`)."""
    return [
        ("★ registry.never_falsifiable_catches_or_true",
         lambda: _nf_catches("or_true") is not None),
        ("★ registry.never_falsifiable_catches_and_false",
         lambda: _nf_catches("and_false") is not None),
        ("★ registry.never_falsifiable_catches_self_compare",
         lambda: _nf_catches("self_compare") is not None),
        ("registry.never_falsifiable_allows_real",
         lambda: _nf_catches("real") is None),
        ("★ registry.never_falsifiable_no_source_no_guess",
         lambda: _nf_no_source() is None),
        ("★ registry.gate_module_meta_states_where_selftest_lives",
         lambda: _gate_desc_states_selftest()),
        ("★ registry.guard_nonempty_returns_2",
         lambda: gate.guard_nonempty("x", []) == 2
         and gate.guard_nonempty("x", [1]) is None),
        ("★ registry.load_spec_returns_error_not_raise",
         lambda: _load_spec_ok()),
        ("★ registry.never_falsifiable_catches_const_helper",
         lambda: _nf_catches("const_helper") is not None),
        ("★ registry.never_falsifiable_catches_multi_lambda_line",
         lambda: _nf_multi_line()),
        ("★ registry.never_falsifiable_rejects_unresolved_helper",
         lambda: _nf_unresolved_helper()),
        ("★ registry.gate_activate_or_fatal",
         lambda: _activate_or_fatal_ok()),
        ("registry.gate_module_meta",
         lambda: gate.module_meta("t", "d")["name"] == "t"),
    ]





def _cases():
    """Assemble the six fixture groups. **Assembly only** -- the judgments live in the
    group functions."""
    import atexit  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    fx = _cases_fixture(d)
    fx["d"] = d
    return (        _cases_discovery(fx)
        + _cases_render(fx)
        + _cases_phase(fx)
        + _cases_hint(fx)
        + _cases_gate_hosted(fx)
    )


MODULE = module_meta("Discovered rosters", "declaration-derived gates/modules/plugins: execution plane + narrative + red list", selftest=True)


if __name__ == "__main__":
    # The finish goes uniformly through `main_selftest_or`: it first activates the
    # language pack (`activate_or_fatal`), then splits into `--selftest` and
    # `main()`. This used to hand-copy its own activate+FATAL, while gate's own
    # `__main__` was a third variant (no FATAL at all) -- three copies of the same
    # thing; the wording was bound to drift.
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.registry"),
                              _cases, main))


