#!/usr/bin/env python3
"""Discovered gate/module/plugin rosters, phase runner CLI, and SEAL.json CLI."""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
import knobs  # noqa: E402
import seal  # noqa: E402
from gate import fatal, main_selftest_or, module_meta, repo  # noqa: E402
from i18n import M  # noqa: E402

GATES_BEGIN = "<!-- AUTO:GATES -->"
GATES_END = "<!-- /AUTO:GATES -->"

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
BUILTIN_PHASES = ("commit", "start-of-work")


def phases():
    """Return built-in phases plus custom `REFLECT_PHASES` entries."""
    val = (knobs.raw("REFLECT_PHASES") or "").strip()
    out = list(BUILTIN_PHASES)
    for p in (x.strip() for x in val.split(",")):
        if p and p not in out:
            out.append(p)
    return tuple(out)


def phases_problems():
    """Verify custom `REFLECT_PHASES` does not redeclare a built-in phase."""
    val = (knobs.raw("REFLECT_PHASES") or "").strip()
    if not val:
        return []
    dup = [p for p in (x.strip() for x in val.split(",")) if p in BUILTIN_PHASES]
    if dup:
        return [M("registry.builtin_phase_repeated", phases=", ".join(sorted(set(dup))))]
    return []


def _parse_decl_node(node, attr, func, rel):
    if not (isinstance(node, ast.Assign) and len(node.targets) == 1
            and getattr(node.targets[0], "id", "") == attr):
        return None
    if attr == "MODULE" and isinstance(node.value, ast.Dict):
        try:
            d = ast.literal_eval(node.value)
            if isinstance(d, dict) and "name" in d and "desc" in d:
                return {"file": rel, "name": d["name"], "desc": d["desc"],
                        "selftest": bool(d.get("selftest", True))}
        except ValueError:
            return None
    if not (isinstance(node.value, ast.Call) and len(node.value.args) >= 2):
        return None
    fn = node.value.func
    if (getattr(fn, "id", "") or getattr(fn, "attr", "")) != func:
        return None
    return _eval_call_decl(node.value, func, rel)


def _eval_call_decl(call, func, rel):
    try:
        kw = {k.arg: ast.literal_eval(k.value) for k in call.keywords if k.arg}
        name, desc = ast.literal_eval(call.args[0]), ast.literal_eval(call.args[1])
    except (ValueError, IndexError):
        return None
    if func == "module_meta":
        return {"file": rel, "name": name, "desc": desc, "selftest": bool(kw.get("selftest", True))}
    return {"file": rel, "name": name, "desc": desc,
            "knobs": tuple(kw.get("knobs", ())),
            "name_dependent": bool(kw.get("name_dependent", False)),
            "runs_at": str(kw.get("runs_at", "commit")),
            "off_reason": kw.get("off_reason")}


def _declaration(path, rel, attr="GATE", func="meta"):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        res = _parse_decl_node(node, attr, func, rel)
        if res is not None:
            return res
    return None


def modules(zdir=None):
    """Discover `MODULE` declarations under `zdir`; return `(declared, undeclared)`."""
    d = zdir if zdir is not None else gate.zdir()
    declared, undeclared = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []
    for n in names:
        if not n.endswith(".py") or n == "__init__.py" or n.startswith("measure_"):
            continue
        rel = "zreflect/" + n
        mod = _declaration(os.path.join(d, n), rel, attr="MODULE", func="module_meta")
        if mod:
            declared.append(mod)
        elif _declaration(os.path.join(d, n), rel) is None:
            undeclared.append(rel)
    return declared, undeclared


def selftest_modules(zdir=None):
    """Return `(runnable_module_files, missing_selftest_entry_files)`."""
    declared, _und = modules(zdir)
    d = zdir if zdir is not None else gate.zdir()
    mods, missing = [], []
    for m in declared:
        if not m.get("selftest"):
            continue
        text = open(os.path.join(d, os.path.basename(m["file"])), encoding="utf-8").read()
        if "--selftest" in text or "main_selftest_or" in text or "_selftest()" in text:
            mods.append(m["file"])
        else:
            missing.append(m["file"])
    return mods, missing


def gates(zdir=None):
    """Discover `GATE = meta(...)` declarations; return `(gates, missing_check_decls)`."""
    d = zdir if zdir is not None else gate.zdir()
    out, missing = [], []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return [], []
    for n in names:
        if not n.endswith(".py") or n == "__init__.py":
            continue
        rel = "zreflect/" + n
        meta = _declaration(os.path.join(d, n), rel)
        if meta:
            out.append(meta)
        elif n.startswith("check_"):
            missing.append(rel)
    return out, missing


def runnable(phase="commit", zdir=None):
    """Return discovered gates whose `runs_at` matches `phase`."""
    gs, _missing = gates(zdir)
    return [g for g in gs if g.get("runs_at", "commit") == phase]


def _touches_renamed(g):
    for k in g["knobs"]:
        kind, dflt, _ = knobs.REGISTRY.get(k, ("", "", ""))
        vals = {x.strip() for x in dflt.split(",")} if kind == "list" else ({dflt} if dflt else set())
        if vals & set(RENAMED_DEFAULTS):
            return True
    return False


def _gate_problems(gs, missing):
    out = []
    if missing:
        out.append(M("registry.missing_declaration", files=", ".join(missing)))
    known = phases()
    for g in gs:
        if g.get("runs_at", "commit") not in known:
            out.append(M("registry.unknown_phase", file=g["file"],
                         runs_at=g.get("runs_at"), phases=" | ".join(known)))
        if g["name_dependent"] and not _touches_renamed(g):
            out.append(M("registry.name_dependent_wrong", file=g["file"]))
    if not gs and not missing:
        out.append(M("registry.empty_roster"))
    return out


def problems(gs, missing, mods=None, mods_missing=None, knob_problems=None, undeclared=None):
    """Reconcile declarations, phases, `knobs.json`, and `SEAL.json`."""
    out = phases_problems() + _gate_problems(gs, missing)
    auto = mods is None
    if mods is None or mods_missing is None:
        mods, mods_missing = selftest_modules()
    if mods_missing:
        out.append(M("registry.selftest_no_entry", files=", ".join(mods_missing)))
    if not mods:
        out.append(M("registry.no_module_selftest"))
    undecl = modules()[1] if undeclared is None else undeclared
    if undecl:
        out.append(M("registry.undeclared_module", files=", ".join(undecl)))
    out += list(knobs.config_problems() if knob_problems is None else knob_problems)
    if auto:
        out += knobs.direct_environ_problems()
    if auto and seal.seal_exists():
        out += seal.verify_problems()
    return out


def red_need(gs=None):
    """Return basenames of gates that must fail under default filenames when renamed."""
    if gs is None:
        gs, _ = gates()
    return sorted(os.path.basename(g["file"]) for g in gs
                  if g["name_dependent"] and _touches_renamed(g))


def plugins(hooks_dir=None):
    """Discover hook scripts under `reflect-hooks/` exposing `--selftest`."""
    d = hooks_dir if hooks_dir is not None else repo("reflect-hooks")
    out = []
    if not os.path.isdir(d):
        return out
    for n in sorted(os.listdir(d)):
        if not n.endswith(".py"):
            continue
        try:
            text = open(os.path.join(d, n), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "--selftest" in text:
            out.append("reflect-hooks/" + n)
    return out


def render_gates(gs):
    """PINNED: render the fixed-language `AUTO:GATES` Markdown table."""
    lines = [GATES_BEGIN,
             ("> This block is rendered by `zreflect/facts.py --render-doc` from the "
              "discovered roster; **do not hand-edit**."),
             ("> The execution plane (hooks / CI) reads `registry --run <phase>` -- "
              "the phase is a declared field (`runs_at`), not a file name."),
             "", "| Gate | Phase | What it guards | Knobs consumed | Why it may be off |",
             "|---|---|---|---|---|"]
    for g in sorted(gs, key=lambda x: (x.get("runs_at", "commit"), x["file"])):
        lines.append("| `%s`（%s） | %s | %s | %s | %s |"
                     % (os.path.basename(g["file"]), g["name"],
                        g.get("runs_at", "commit"), g["desc"],
                        ", ".join("`%s`" % k for k in g["knobs"]) or "--",
                        g.get("off_reason") or "--"))
    off_capable = sum(1 for g in gs if g.get("off_reason"))
    lines += ["", "%d gates; %d may be disabled." % (len(gs), off_capable), GATES_END]
    return "\n".join(lines)


def _arg_after(argv, flag):
    i = argv.index(flag)
    return argv[i + 1] if len(argv) > i + 1 and not argv[i + 1].startswith("-") else "commit"


_MAX_GATE_BULLETS = 5
_MAX_GATE_LINES = 6


def _format_gate_output(text):
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return []
    bullets = [ln for ln in lines if ln.startswith("  \u00b7 ")]
    if bullets:
        out, shown = [], 0
        for ln in lines:
            if ln.startswith("  \u00b7 "):
                if shown >= _MAX_GATE_BULLETS:
                    continue
                shown += 1
            out.append("      " + ln)
        extra = len(bullets) - shown
        if extra > 0:
            out.append("      " + str(M("registry.more_items", count=extra)))
        return out
    selected = lines if len(lines) <= _MAX_GATE_LINES else [lines[0], lines[1], "...", *lines[-4:]]
    return ["      " + ln for ln in selected]


def _emit_phase_group(files, code, fail_out):
    for f in files:
        print(M(code, file=f))
        for ln in _format_gate_output(fail_out.get(f) or ""):
            print(ln)


def _main_run(argv):
    phase = _arg_after(argv, "--run")
    gs = runnable(phase)
    if not gs:
        return fatal(M("registry.empty_phase", phase=phase))
    res = gate.run_phase(phase, gs)
    print(M("registry.phase_summary", phase=phase, ran=res["ran"], off=res["off"],
            failed=res["failed"], fatal=res.get("fatal", 0), error=res.get("error", 0)))
    fail_out = res.get("fail_out", {})
    _emit_phase_group(res["fail_list"], "registry.phase_failed", fail_out)
    _emit_phase_group(res.get("fatal_list", ()), "registry.phase_fatal", fail_out)
    _emit_phase_group(res.get("error_list", ()), "registry.phase_error", fail_out)
    if res["off_list"]:
        print(M("registry.phase_off_list", count=len(res["off_list"]),
                files=", ".join(res["off_list"])))
    return 1 if (res["failed"] or res.get("fatal") or res.get("error")) else 0


def _main_seal(argv):
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
    hit = [a for a in argv if a.startswith("--reseal=")]
    if hit:
        targets = [t.strip() for t in hit[0][len("--reseal="):].split(",") if t.strip()]
        tree, err = seal.reseal(targets)
        if err:
            return fatal(err)
        print(M("seal.resealed", tree=tree, count=len(targets)))
        return 0
    return None


def cli_selftest_missing_lines(missing):
    """Format CLI lines for modules missing `--selftest`."""
    return [M("registry.selftest_no_entry_cli", file=m) for m in missing]


def _main_lists(argv):
    simple = {
        "--red-need": lambda: print(" ".join(red_need())),
        "--runnable": lambda: [print(g["file"]) for g in runnable(_arg_after(argv, "--runnable"))],
        "--all-runnable": lambda: [print(g["file"]) for g in gates()[0]],
        "--plugins": lambda: print("\n".join(plugins())),
        "--fixture-renames": lambda: [print("%s=%s" % item)
                                      for item in sorted(FIXTURE_RENAMES.items())],
    }
    for flag, fn in simple.items():
        if flag in argv:
            fn()
            return 0
    return None


def _main_gates():
    gs, missing = gates()
    probs = problems(gs, missing)
    for x in probs:
        print("  · %s" % x, file=sys.stderr)
    if probs:
        return fatal(M("registry.roster_problems", count=len(probs)))
    for g in gs:
        print("%s\t%s\t%s" % (g["file"], g["name"], g["desc"]))
    return 0


def _main_selftest_mods():
    mods, missing = selftest_modules()
    for line in cli_selftest_missing_lines(missing):
        print(line, file=sys.stderr)
    if missing:
        return 1
    print("\n".join(mods))
    return 0


def main(argv):
    for rc in (_main_lists(argv), _main_seal(argv)):
        if rc is not None:
            return rc
    if "--run" in argv:
        return _main_run(argv)
    if "--selftest-modules" in argv:
        return _main_selftest_mods()
    if "--gates" in argv:
        return _main_gates()
    print(M("registry.usage"), file=sys.stderr)
    return 2


def _cases():
    gs, missing = gates()
    fake_g = [{"file": "zreflect/check_x.py", "name": "x", "desc": "d",
               "knobs": ("REFLECT_AB",), "name_dependent": True,
               "runs_at": "commit", "off_reason": None}]
    return [
        ("registry.real_gates_clean", lambda: len(gs) > 0 and problems(gs, missing) == []),
        ("★ registry.missing_declaration_reported",
         lambda: any(p.code == "registry.missing_declaration"
                     for p in problems(gs, ["zreflect/check_orphan.py"],
                                       mods=["m.py"], mods_missing=[], knob_problems=[], undeclared=[]))),
        ("★ registry.unknown_phase_reported",
         lambda: any(p.code == "registry.unknown_phase"
                     for p in problems([dict(fake_g[0], runs_at="bogus", name_dependent=False)], [],
                                       mods=["m.py"], mods_missing=[], knob_problems=[], undeclared=[]))),
        ("★ registry.name_dependent_wrong",
         lambda: any(p.code == "registry.name_dependent_wrong"
                     for p in problems(fake_g, [], mods=["m.py"], mods_missing=[],
                                       knob_problems=[], undeclared=[]))),
        ("★ registry.empty_roster",
         lambda: any(p.code == "registry.empty_roster"
                     for p in problems([], [], mods=["m.py"], mods_missing=[],
                                       knob_problems=[], undeclared=[]))),
        ("★ registry.selftest_no_entry",
         lambda: any(p.code == "registry.selftest_no_entry"
                     for p in problems(gs, missing, mods=["m.py"], mods_missing=["m.py"],
                                       knob_problems=[], undeclared=[]))),
        ("★ registry.undeclared_module",
         lambda: any(p.code == "registry.undeclared_module"
                     for p in problems(gs, missing, mods=["m.py"], mods_missing=[],
                                       knob_problems=[], undeclared=["zreflect/stray.py"]))),
        ("registry.render_gates_markers",
         lambda: GATES_BEGIN in render_gates(gs) and GATES_END in render_gates(gs)),
        ("registry.plugins_discovered",
         lambda: "reflect-hooks/hook.py" in plugins()
         and any(g["file"] == "zreflect/doctor.py" for g in gs)),
        ("registry.emit_multi_bullets_bounded", lambda: _emit_bullets_ok()),
    ]


def _emit_bullets_ok():
    joined = "\n".join(_format_gate_output(
        "hdr\n" + "\n".join("  \u00b7 p%d" % i for i in range(1, 8))))
    return "  \u00b7 p1" in joined and "  \u00b7 p5" in joined and "  \u00b7 p6" not in joined and "2" in joined


MODULE = module_meta("Roster registry", "discovered rosters, phase runner, and seal CLI",
                     selftest=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], M("gate.title.registry"), _cases, main))
