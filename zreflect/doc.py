#!/usr/bin/env python3
"""Principles registry (`RULES`) and `AUTO:RULES` renderer for `PRINCIPLES.md`."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
import i18n  # noqa: E402
import knobs  # noqa: E402
from gate import main_selftest_or, module_meta  # noqa: E402


class Rule(NamedTuple):
    """One architectural principle: sentence (`text`) + runnable command (`cmd`)."""
    id: str
    text: str
    cmd: str


def enforced_by(script):
    """Print enforcing gate file if declared in `registry.gates()`, else return rc=1."""
    import registry  # noqa: PLC0415
    gs, _m = registry.gates()
    hits = [g["file"] for g in gs if os.path.basename(g["file"]) == script]
    if not hits:
        print("missing_gate=%s" % script)
        return 1
    print("enforced_by=%s" % hits[0])
    return 0


def _read_json_safe(path):
    try:
        return json.loads(open(path, encoding="utf-8").read()) or {}
    except (OSError, ValueError):
        return {}


def _question_exec_problems(qdir):
    import glob  # noqa: PLC0415
    out: list[i18n.Message] = []
    if not qdir or not os.path.isdir(qdir):
        return out
    for qp in sorted(glob.glob(os.path.join(qdir, "*.md"))):
        for line in open(qp, encoding="utf-8", errors="replace").read().splitlines():
            if line.startswith("**Settling:**"):
                sv = line[len("**Settling:**"):].strip()
                if sv and not sv.lower().startswith(("none", "n/a")):
                    out += gate.prose_in_exec_problems(os.path.basename(qp), "Settling", sv)
                break
    return out


def all_exec_position_problems(root=None):
    """Collect prose-in-command errors across `world.json`, `pins.json`, `retractions.json`, `questions/*.md`."""
    base = root or gate.GATE_REPO
    out = []
    for knob_key, name in (("REFLECT_WORLD", "world.json"), ("REFLECT_PINS", "pins.json")):
        p = knobs.repo_path(knob_key, base)
        if p and os.path.isfile(p):
            out += gate.exec_position_problems(_read_json_safe(p), name)
    ret = knobs.repo_path("REFLECT_RETRACTIONS", base)
    if ret and os.path.isfile(ret):
        for r in _read_json_safe(ret).get("retractions") or []:
            if isinstance(r, dict):
                out += gate.prose_in_exec_problems("retractions/%s" % r.get("id", "?"),
                                                   "evidence", r.get("evidence"))
    return out + _question_exec_problems(knobs.questions_path(base))


def _enforced(script):
    return ("python3 -c \"import sys;sys.path.insert(0,'zreflect');"
            "import doc;sys.exit(doc.enforced_by('%s'))\"" % script)


RULES = (
    Rule("only_measured",
         "numbers/behavior trust measurement only; every fact must carry a re-run command",
         "python3 -c \"import json,sys;sys.path.insert(0,'zreflect');import knobs;"
         "d=json.load(open(knobs.repo_path('REFLECT_FACTS'),encoding='utf-8'))['facts'];"
         "bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];"
         "print('facts_without_cmd=%d' % len(bad));"
         "sys.exit(1 if bad else 0)\""),
    Rule("number_once",
         "each number is produced once and re-reconciled every commit: documents cite it as `[[key]]`, never hand-copy it",
         _enforced("check_facts.py")),
    Rule("hard_needs_criterion",
         "a rule is hard only if it has a machine criterion; without one it does not enter the table at all",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import doc;"
         "p=doc._cmd_shape_problems();"
         "print('shape_problems=%d' % len(p));"
         "sys.exit(1 if p else 0)\""),
    Rule("falsifiable",
         "claims must be falsifiable: every declared gate carries a runnable --selftest",
         "python3 zreflect/registry.py --all-runnable"),
    Rule("declared_not_globbed",
         "predicates are declarations, not filenames: the execution surface reads registry --run <phase>",
         "python3 zreflect/registry.py --gates"),
    Rule("zero_language",
         "zero language in the core: user-visible messages go through M(code); machine contracts are untranslatable by construction",
         _enforced("check_i18n.py")),
    Rule("machine_rows",
         "machine rows are defined in one place (`i18n.ROWS`) for both producers and consumers",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import i18n;"
         "print('rows=%d' % len(i18n.ROWS));sys.exit(0 if i18n.ROWS else 1)\""),
    Rule("three_readmes",
         "the README group is checked structurally and kept in the same push batch",
         _enforced("check_readme_sync.py")),
    Rule("snapshot_hygiene",
         "a mutable global imported across modules is a value copy: read via the module attribute instead",
         _enforced("check_snapshots.py")),
    Rule("assertion_lifecycle",
         "a retracted claim must not quietly return as current state",
         _enforced("check_retractions.py")),
    Rule("no_retired_names",
         "retired names must not appear as current state; sha provenance and age are checkable",
         _enforced("check_stale.py")),
    Rule("open_questions_settle",
         "every unresolved open question must carry a runnable settler",
         _enforced("check_questions.py")),
    Rule("selfcert_harness",
         "every declared module must have a --selftest entry",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import registry;"
         "u=registry.selftest_modules()[1];"
         "print('missing_selftest=%d' % len(u));sys.exit(1 if u else 0)\""),
    Rule("host_agnostic",
         "the suite's source recognizes no host's directory names or config formats",
         "python3 -c \"import os,sys;"
         "w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR',"
         "'hook'+'SpecificOutput'];"
         "bad=[(d,f) for d in ('zreflect','reflect-hooks') "
         "for r,_,fs in os.walk(d) for f in fs if f.endswith('.py') "
         "and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];"
         "print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)\""),
    Rule("exec_position_is_a_command",
         "every execution position (stamp cmd / pin cmd / Settling / evidence) must hold a runnable command",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import doc;"
         "bad=doc.all_exec_position_problems();"
         "[print(p) for p in bad] or print('prose_positions=0');sys.exit(1 if bad else 0)\""),
    Rule("comments_earn_their_place",
         "explanation volume must fit AST complexity under `mismatch`, or carry no docstrings under `strict`",
         _enforced("check_explain.py")),
    Rule("style_is_not_a_rule",
         "style preferences do not enter the rule table",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import doc;"
         "style=('style','naming','comment','layout','format');"
         "bad=[r.id for r in doc.RULES if r.id in style];"
         "print('style_ids=%d' % len(bad));sys.exit(1 if bad else 0)\""),
    Rule("core_sealed",
         "shared suite core modules, gates, hooks, and language packs match `zreflect/SEAL.json`",
         "python3 zreflect/registry.py --verify-seal"),
)

_BY_ID = {r.id: r for r in RULES}
RULES_BEGIN = "<!-- AUTO:RULES -->"
RULES_END = "<!-- /AUTO:RULES -->"
PRINCIPLES = "PRINCIPLES.md"
STATE = "STATE.md"


def render_rules(rows=None):
    """PINNED: render fixed-language `AUTO:RULES` block from `RULES`."""
    rows = RULES if rows is None else rows
    lines = [RULES_BEGIN,
             ("> This block is rendered by `zreflect/facts.py --render-doc` from the "
              "`RULES` table in `zreflect/doc.py`; **do not hand-edit**."),
             ("> Every row's judging command is executed verbatim at every commit (`check_facts_replay`)."),
             "", "| id | principle | judging command |", "|---|---|---|"]
    for r in sorted(rows, key=lambda x: x.id):
        lines.append("| `%s` | %s | `%s` |" % (r.id, r.text, r.cmd))
    lines += ["", "%d principles -- each with a judging command that **really runs**." % len(rows),
              RULES_END]
    return "\n".join(lines)


def accepts_principles(repo_root=None):
    """Return True if `PRINCIPLES.md` exists and `REFLECT_NO_PRINCIPLES` is not true."""
    if knobs.flag("REFLECT_NO_PRINCIPLES") is True:
        return False
    base = repo_root or gate.GATE_REPO
    return os.path.exists(os.path.join(base, PRINCIPLES))


def state_name():
    """Return configured state document filename (`REFLECT_DOC`)."""
    return knobs.get("REFLECT_DOC")


def rule(rid):
    """Fetch a `Rule` by id (raises `KeyError` if absent)."""
    return _BY_ID[rid]


def facts_of_rules():
    """Convert `RULES` to `{principle.<id>: fact_dict}` for direct replay."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    today = time.strftime("%Y-%m-%d")
    return {
        "principle." + r.id: {
            "value": "ok", "cmd": r.cmd, "source": "principle",
            "measured_at": now, "first_seen": today,
            "note": r.text, "kind": "principle",
        }
        for r in RULES
    }


def _cmd_shape_problems(rows=None):
    out = []
    for r in (RULES if rows is None else rows):
        cmd = r.cmd.strip()
        if not cmd:
            out.append((r.id, "empty_cmd"))
        elif not re.match(r"^(python3|python|sh|bash|env)\s", cmd):
            out.append((r.id, "not_an_interpreter"))
        elif re.search(r"(^|[;&|]\s*)(export|set\s+-a)|>\s*\S", cmd.replace(">/dev/null", "")):
            out.append((r.id, "mutates_env"))
    return out


def _accepts_principles_ok():
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as root:
        if accepts_principles(root):
            return False
        open(os.path.join(root, PRINCIPLES), "w", encoding="utf-8").write("# PRINCIPLES\n")
        saved = os.environ.pop("REFLECT_NO_PRINCIPLES", None)
        try:
            if not accepts_principles(root):
                return False
            os.environ["REFLECT_NO_PRINCIPLES"] = "1"
            return not accepts_principles(root)
        finally:
            if saved is not None:
                os.environ["REFLECT_NO_PRINCIPLES"] = saved
            else:
                os.environ.pop("REFLECT_NO_PRINCIPLES", None)


def _cases():
    return [
        ("doc.rules_well_formed", lambda: _cmd_shape_problems() == []),
        ("doc.ids_unique_and_valid",
         lambda: len({r.id for r in RULES}) == len(RULES)
         and all(re.fullmatch(r"[a-z][a-z0-9_]*", r.id) and r.text.strip() for r in RULES)),
        ("doc.lookup_works", lambda: rule("only_measured").id == "only_measured"),
        ("doc.render_rules_has_markers",
         lambda: RULES_BEGIN in render_rules() and RULES_END in render_rules()
         and "nope" in render_rules([Rule("nope", "t", "python3 -c 'pass'")])),
        ("★ doc.empty_cmd_is_rejected",
         lambda: _cmd_shape_problems([Rule("x", "t", "")]) == [("x", "empty_cmd")]),
        ("★ doc.enforced_by_missing_fails", lambda: enforced_by("check_nope_xyz.py") == 1),
        ("doc.state_name_uses_knob", lambda: state_name() == knobs.get("REFLECT_DOC")),
        ("★ doc.accepts_principles_opt_out", lambda: _accepts_principles_ok()),
        ("★ doc.exec_position_rejects_prose",
         lambda: [p.code for p in gate.prose_in_exec_problems("w", "cmd", "say hi")]
         == ["criteria.exec_position_is_prose"]),
    ]


MODULE = module_meta("Principles registry", "RULES table, AUTO:RULES renderer, facts_of_rules",
                     selftest=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "doc", _cases, lambda _argv: 0))
