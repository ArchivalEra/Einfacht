#!/usr/bin/env python3
"""Principles registry: **each principle = one sentence + one re-runnable command**.

## Why this is not a "discipline table"

An earlier version had a table here, each discipline tied to a "criteria file
name". That was a **second mechanism**: this repo already has a whole apparatus
of "description + re-run command + verbatim execution at every commit" --
`ledger.fact(value, cmd, source)` produces facts, and `check_facts_replay.py`
**executes verbatim** every `cmd` in the ledger at every commit.

Building another "discipline → gate" link table would give "what gets checked"
a second place of origin. Deleted.

## Now: a principle is a fact

    principle = Rule(id, text, cmd)
      text  the human-facing sentence (written into the ledger as `note`)
      cmd   the machine-run judging command (rc=0 passes / non-0 reports;
            **stdout must be empty**)

Principles are written into `FACTS.json` by `facts.py --accept-principles`,
then **executed verbatim** by `check_facts_replay` at `commit` time -- they
share the same re-run path as numeric facts, with no new executor added.

## Why a principle's stdout must be empty

The numeric-fact contract is "stdout is the **bare value**". A principle is
not a value, it is a **judgment**, so the contract is "**when it passes, say
nothing**" -- the same shape as `gate`'s rc contract (0 green / non-0 red).

## Start-of-work and commit

    start-of-work  STATE.md and PRINCIPLES.md both agree with the ledger (`--check`)
    commit         every principle's cmd re-run one by one (`check_facts_replay`)

`state` and `principle` are the **only two things that must be measured**.
Other things can be **manually registered** as facts to check (`--accept`),
but they are not on the default surface.

## Why history is not in here

An append-only account of events is reproducible only "under the conditions of
that moment" -- you cannot use today's artifacts to prove it was right.
**The irreproducible does not enter the measured surface**: this repo's
founding question is "who re-ran the proof for you", and what cannot be
re-run should not occupy a position that gets judged.
"""
from __future__ import annotations

import os
import re
from typing import NamedTuple


class Rule(NamedTuple):
    """A principle.

    `text` = the human-facing sentence; `cmd` = the machine-run judging
    command (cwd = repo root, rc=0 passes, stdout must be empty).
    """
    id: str
    text: str
    cmd: str


# -- Principles registry: the **single place of origin** ----------------------
#
# Each `cmd` must be an **existing gate** -- no new executors are invented
# (that is reuse, not invention). The `>/dev/null` entries run gates that
# print human-readable summaries: discarding stdout is a **declaration made
# here**, not a stealth swallow (the principle contract is precisely that
# stdout be empty).

RULES = (
    # ⚠️ **Must not point at the re-runner itself**: `check_facts_replay`
    # executes every cmd in the ledger => it would re-run itself => unbounded
    # spawning (observed: OOM). This principle is instead proven by the
    # **shape of the ledger**.
    #
    # ⚠️ Every cmd must **take a stance** (stdout non-empty, and free of
    # `OFF:`) -- see the principle-entry contract in `check_facts_replay`.
    # So `>/dev/null` is forbidden here: throwing away a gate's stance is
    # exactly how an "off" gets laundered into a "pass".
    Rule("only_measured",
         "numbers/behavior trust measurement only; every fact must carry a re-run command",
         "python3 -c \"import json,sys;"
         # ⚠️ `encoding='utf-8'` cannot be omitted: the ledger contains Chinese
         # notes, and Windows opens with default cp1252 => UnicodeDecodeError =>
         # this judgment is permanently red on Windows
         # (observed: CI's Windows leg crashed on this line two rounds running).
         "d=json.load(open('FACTS.json', encoding='utf-8'))['facts'];"
         "bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];"
         "print('facts_without_cmd=%d' % len(bad));"
         "sys.exit(1 if bad else 0)\""),

    Rule("number_once",
         "each number is produced once and re-reconciled every commit: documents cite it as [[key]], never hand-copy it",
         "python3 zreflect/check_facts.py"),

    Rule("hard_needs_criterion",
         "a rule is hard only if it has a machine criterion; without one it does not enter the table at all (there is no advisory state)",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import doc;"
         "p=doc._cmd_shape_problems();"
         "print('shape_problems=%d' % len(p));"
         "sys.exit(1 if p else 0)\""),

    Rule("ran_is_not_passed",
         "\"ran\" and \"ran and passed\" are different statements, and so are \"off\" and \"ran\": a gate that can go off must declare why, and an empty traversal must say so",
         # Same judgment as `off_is_visible` (a gate must declare why it can be
         # off), read from the other end: it inspects the gate **roster**'s off
         # declarations instead of one gate's problems.
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');"
         "import registry, criteria;gs=registry.gates()[0];"
         "p=criteria.off_reason_problems(gs);"
         "print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));"
         "sys.exit(0 if gs and not p else 1)\""),


    Rule("falsifiable",
         "claims must be falsifiable: always-true shortcuts are swept by AST and any hit fails",
         "python3 zreflect/registry.py --selftest"),

    Rule("declared_not_globbed",
         "predicates are declarations, not filenames: the execution surface reads registry --run <phase>",
         "python3 zreflect/registry.py --gates"),

    # ⚠️ For the same reason, running `registry --run commit` is forbidden --
    # it would reach the replay gate, which loops back here. Instead inspect
    # the **declaration surface**: every gate that can go off must declare a
    # reason (`off_reason`).
    Rule("zero_language",
         "zero language in the core: user-visible messages go through M(code); machine contracts are untranslatable by construction",
         "python3 zreflect/check_i18n.py"),

    Rule("machine_rows",
         "machine rows are defined in one place, machine.ROWS; the shell side has a behavior reconciler",
         "python3 zreflect/machine.py --selftest"),

    Rule("three_readmes",
         "the three-language READMEs are three copies of one assertion: change one, change all three in the same batch",
         "python3 zreflect/check_readme_sync.py"),

    Rule("snapshot_hygiene",
         "a mutable global imported across modules is a value copy (stale snapshot): read via the module attribute instead",
         "python3 zreflect/check_snapshots.py"),

    Rule("assertion_lifecycle",
         "a retracted claim must not quietly return as current state",
         "python3 zreflect/check_retractions.py"),

    Rule("no_retired_names",
         "retired names must not appear as current state; sha provenance and age are checkable",
         "python3 zreflect/check_stale.py"),

    Rule("open_questions_settle",
         "every unresolved open question must carry a runnable settler",
         "python3 zreflect/check_questions.py"),

    # ⚠️ Same reasoning: `gates-selftest.sh` actually runs every gate's
    # selftest (including this replay gate) => cycle. Instead check the
    # **existence of the machine summary line**: every gate file must have a
    # `--selftest` entry.
    Rule("selfcert_harness",
         "every gate must have a --selftest entry (written but never run = decoration)",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');"
         "import registry;u=registry.modules()[1];"
         "print('undeclared_modules=%d' % len(u));"
         "sys.exit(1 if u else 0)\""),

    # Host coupling is **measurable**: the moment a host's directory name or
    # config filename shows up in the suite's own source, the suite has welded
    # itself to that host. For the observed cost see R-003: `check_wire` went
    # off to validate the editor's config.json schema -- switching editors
    # meant editing a gate, while the host's own trust gate (pending_trust)
    # was invisible to the suite entirely.
    #
    # The criterion scans **code** (.py/.sh), not docs: mentioning a host in
    # README/AGENTS is explanation, not dependency.
    #
    # ⚠️ The wordlist is built by **codepoint concatenation**, never written
    # as literals -- literal spellings would make this file (and the
    # retraction note in `check_i18n`) get caught by its own criterion. This
    # is the same pitfall this repo already hit with CJK-range constants:
    # the criterion's metadata must not live **inside the criterion's scan
    # surface**.
    Rule("doc_references_real",
         "a document must not point at a symbol that does not exist",
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import doc;"
         "d=doc.dangling_references();"
         "[print('dangling=%d %s.%s@%s' % (len(d),m,s_,f)) for f,m,s_ in d] "
         "or print('dangling=0');"
         "sys.exit(1 if d else 0)\"",
         ),
    Rule("host_agnostic",
         "the suite's source recognizes no host's directory names / config formats (host wiring belongs to the consumer)",
         "python3 -c \"import os,sys;"
         "w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR',"
         "'hook'+'SpecificOutput'];"
         "bad=[(d,f) for d in ('zreflect','reflect-hooks') "
         "for r,_,fs in os.walk(d) for f in fs "
         "if f.endswith(('.py','.sh')) "
         "and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() "
         "for k in w)];"
         "print('host_coupled=%d' % len(bad));"
         "sys.exit(1 if bad else 0)\""),

    Rule("no_echo_between_carriers",
         "a near-copy of an assertion in two carriers is a hand-copy: one fact lives in one carrier, and a quotation must name its source",
         "python3 -c \"import glob,sys;sys.path.insert(0,'zreflect');import doc,echoes,ledger;"
         "f=(echoes.forms_from_rules(doc.RULES)+echoes.forms_from_ledger(ledger.load('FACTS.json'),doc.RULES)"
         "+echoes.forms_from_questions(sorted(glob.glob('questions/*.md'))));"
         "h=echoes.echo_problems(f);"
         "[print('echo=%s~%s(%.3f)' % (a,b,r)) for r,a,b in h] "
         "or print('echoes=0 of %d forms' % len(f));"
         "sys.exit(1 if h else 0)\""),
    Rule("exec_position_is_a_command",
         "every execution position (stamp cmd / pin version_read / Settling / evidence) must hold a runnable command, not prose",
         "python3 -c \"import json,os,sys;sys.path.insert(0,'zreflect');import criteria,knobs;"
         "specs=[(k,knobs.REGISTRY[k][1]) for k in ('REFLECT_WORLD','REFLECT_PINS')];"
         "bad=[(n,w,f) for k,n in specs if n and os.path.exists(n) "
         "for w,f,_ in criteria.exec_position_problems(json.load(open(n,encoding='utf-8')),n)];"
         "print('prose_positions=%d' % len(bad));sys.exit(1 if bad else 0)\""),
    Rule("comments_earn_their_place",
         "a docstring is a claim the code could not make -- under `strict` no function carries one, under `mismatch` none explains more than it implements",
         "python3 -c \"import os,sys;sys.path.insert(0,'zreflect');import check_explain as c;"
         "m=os.environ.get('REFLECT_COMMENTS','').strip().lower();"
         "p=[] if not m or m=='off' else c.problems("
         "[(f,open(os.path.join('zreflect',f),encoding='utf-8').read()) "
         "for f in sorted(os.listdir('zreflect')) if f.endswith('.py')], m);"
         "[print(x) for x in p] or print('comment_mode=%s problems=%d' % (m or 'off', len(p)));"
         "sys.exit(1 if p else 0)\"",
         ),
    Rule("style_is_not_a_rule",
         "style preferences (naming, comment density, file layout) do not enter the rule table; they are held by 'match the code around you'",
         # The id vocabulary is spelled out (not derived from a shared table):
         # this rule's criterion must be readable as data on its own -- deriving
         # the list from a constant inside the same scan would make "what counts
         # as style" a second origin nobody compares.
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');import doc;"
         "style=('style','naming','comment','layout','format');"
         "bad=[r.id for r in doc.RULES if r.id in style];"
         "print('style_ids=%d' % len(bad));"
         "sys.exit(1 if bad else 0)\""),

    Rule("one_off_decisions_do_not_land",
         "a one-off decision ('why this round changed this way') is not recorded in a document; it belongs to the commit message",
         # Round narrative in the main documents is scanned, including the CJK
         # words for "this round" -- spelled by codepoint (this file is inside
         # check_i18n's scan surface; a literal would be judged as the core
         # speaking human).
         "python3 -c \"import os,re,sys;"
         "p='|'.join([''.join(chr(c) for c in (0x8FD9,0x8F6E)),"
         "''.join(chr(c) for c in (0x672C,0x8F6E)),r'round\\s+N']);"
         "hit=[(f,m.group()) for f in ('PRINCIPLES.md','STATE.md','AGENTS.md') "
         "if os.path.exists(f) "
         "for m in [re.search(p,open(f,encoding='utf-8').read())] if m];"
         "print('round_narrative=%d' % len(hit));"
         "sys.exit(1 if hit else 0)\""),
)

_BY_ID = {r.id: r for r in RULES}

# Machine-block markers: the principles table is rendered from here (prose
# must never hand-copy it).
RULES_BEGIN = "<!-- AUTO:RULES -->"
RULES_END = "<!-- /AUTO:RULES -->"


def render_rules(rows=None):
    """Principles registry → the `AUTO:RULES` machine block. **Pure function**.

    Every line is a **fact in the ledger** (key `principle.<id>`) -- on the
    surface it is documentation, but it is actually the only human-readable
    view of "what this principle's cmd is and whether it passes right now".
    Whether it passes is answered by `check_facts_replay` at every commit,
    not here.

    PINNED: this block is **fixed to one language** and does not follow
    `REFLECT_LANG`. The reason is **verifiable**: it lands in `PRINCIPLES.md`
    and is **reconciled byte-for-byte** by `facts.py --check` (`PRINCIPLES.md`
    is in `_block_homes`, part of `--check`'s validation surface). Following
    the language => after `REFLECT_LANG=de --render-doc`, a subsequent
    `REFLECT_LANG=zh --check` is guaranteed red -- the same commit would give
    different results in different environments, and `--check` would never
    converge.
    """
    rows = RULES if rows is None else rows
    lines = [RULES_BEGIN,
             ("> This block is rendered by `zreflect/facts.py --render-doc` from the "
             "`RULES` table in `zreflect/doc.py`; **do not hand-edit**."),
             ("> Every row's judging command is in `FACTS.json` and is executed verbatim "
             "at every commit (`check_facts_replay`)."),
             "",
             "| id | principle | judging command |",
             "|---|---|---|"]
    for r in sorted(rows, key=lambda x: x.id):
        lines.append("| `%s` | %s | `%s` |" % (r.id, r.text, r.cmd))
    lines += ["", "%d principles -- each with a judging command that **really runs**." % len(rows),
              RULES_END]
    return "\n".join(lines)


# The only two filenames that must be measured. `STATE.md` can be swapped via
# `REFLECT_DOC` (a name-type knob).
PRINCIPLES = "PRINCIPLES.md"
STATE = "STATE.md"


# "Does this repo accept this suite's principles?" -- answered by
# **declaration**, not by checking whether a file exists.
#
# `facts.py` used to say `if os.path.exists(PRINCIPLES.md)`: that was
# **implicit coupling** (file exists = principles accepted), and "the file
# exists" and "this repo commits to obeying these" are two different things --
# a cross-repo fixture happened to lack the file, so the principles were
# silently skipped (observed: another time a fixture had an empty
# PRINCIPLES.md, the principles got registered, and every command ran red in
# the foreign repo's context).
#
# Now: `PRINCIPLES.md` exists **and** `REFLECT_NO_PRINCIPLES=1` is not set
# => accepted. The exit is explicit, so "we don't want to obey" is a decision
# that can be spoken aloud, not something done by deleting a file.
def accepts_principles(repo_root=None):
    """Should this repo register `RULES` into the ledger (= re-run each at every commit)?"""
    import os  # noqa: PLC0415

    import knobs  # noqa: PLC0415
    # Go through `knobs.flag` (the single place of origin for the vocabulary) --
    # the previous `.strip() in ("1","true","yes")` was a **case-sensitive**
    # scheme: observed: `REFLECT_NO_PRINCIPLES=TRUE` silently did nothing.
    if knobs.flag("REFLECT_NO_PRINCIPLES") is True:
        return False
    import gate  # noqa: PLC0415
    base = repo_root or gate.GATE_REPO
    return os.path.exists(os.path.join(base, PRINCIPLES))


def state_name():
    """Filename of the "now" document: `REFLECT_DOC` wins (same knob as `facts.py`)."""
    import os  # noqa: PLC0415
    return os.environ.get("REFLECT_DOC", "").strip() or STATE


def rule(rid):
    """Fetch a principle by id (missing => KeyError, so the usable id is named)."""
    return _BY_ID[rid]


# -- Into the ledger: reuse ledger.fact, invent no new shape ------------------

def facts_of_rules():
    """Principles → `{key: ledger.fact(...)}`, for `facts.py --accept-principles` to write.

    Key prefix `principle.` -- they share the single `facts` table with numeric
    facts, and therefore the same re-run path (`check_facts_replay`).
    `kind="principle"` tells the re-runner this entry is judged by **rc**,
    not by bare value.
    """
    import ledger  # noqa: PLC0415
    out = {}
    for r in RULES:
        out["principle." + r.id] = ledger.fact(
            "ok", r.cmd, "principle", r.text, kind="principle")
    return out


# -- Self-evidence ------------------------------------------------------------

def _cmd_shape_problems(rows=None):
    """Each principle's cmd shape: non-empty, **starts with an interpreter**, **contains no environment-mutating call**.

    The criteria are about **shape** (can `check_facts_replay` execute it
    verbatim), not semantics. All three were learned the hard way:

      · `empty_cmd` -- a principle without a command is just prose (the shape
        this repo despises most);
      · `not_an_interpreter` -- the command must be an explicit interpreter
        like `python3 ...` / `sh ...`. A bare `check_x.py` depends on the execute
        bit and the shebang, unreliable under `bash -c` (the re-runner uses
        `bash -o pipefail -c`; without the execute bit it is rc=126);
      · `mutates_env` -- `export` / `set -a` / file-writing commands turn the
        re-run into a side-effecting action. A principle's judgment must be
        **read-only**, otherwise "really run at every commit" gets dirtier
        with every run.

    This is not a complete check (there is no sandbox); it blocks only the
    **three known** bad shapes.
    """
    import re  # noqa: PLC0415
    out = []
    for r in (RULES if rows is None else rows):
        cmd = r.cmd.strip()
        if not cmd:
            out.append((r.id, "empty_cmd"))
            continue
        if not re.match(r"^(python3|python|sh|bash|env)\s", cmd):
            out.append((r.id, "not_an_interpreter"))
            continue
        # ⚠️ GitRoll reported "lookahead assertion that can never be true" --
        # verified: in `(?!\S*)` the `\S*` can match the empty string, and a
        # negative lookahead fails against the empty string forever => dead
        # lookahead. Removing it is case-by-case equivalent (all nine shapes
        # of export / set -a / redirection behave the same) -- dead code.
        if re.search(r"(^|[;&|]\s*)(export|set\s+-a)|>\s*\S",
                     cmd.replace(">/dev/null", "")):
            out.append((r.id, "mutates_env"))
    return out


def _ids_unique():
    return len({r.id for r in RULES}) == len(RULES)


def _ids_well_formed():
    import re  # noqa: PLC0415
    return all(re.fullmatch(r"[a-z][a-z0-9_]*", r.id) for r in RULES)


def _every_rule_has_text():
    return all(r.text.strip() for r in RULES)


def _every_cmd_references_a_real_file():
    """Every `zreflect/*.py` / `*.sh` named in a shipped cmd really exists.

    Existence only -- runnability is `check_facts_replay`'s job (verbatim
    execution at every commit). This is the cheap pre-check that catches dead
    commands left behind by a rename.
    """
    return _cmd_targets_exist(RULES)


def _lookup_works():
    try:
        rule("only_measured")
    except KeyError:
        return False
    try:
        rule("definitely_not_a_rule")
        return False
    except KeyError:
        return True



def _cases():
    return [
        # (1) normal: no report
        ("doc.rules_well_formed", lambda: _cmd_shape_problems() == []),
        ("doc.ids_unique", lambda: _ids_unique()),
        ("doc.ids_well_formed", lambda: _ids_well_formed()),
        ("doc.every_rule_has_text", lambda: _every_rule_has_text()),
        ("doc.cmds_reference_real_files", lambda: _every_cmd_references_a_real_file()),
        ("doc.lookup_works", lambda: _lookup_works()),
        # (2) what must be reported gets reported -- every criterion has teeth
        ("★ doc.empty_cmd_is_rejected",
         lambda: _cmd_shape_problems([Rule("x", "t", "")]) == [("x", "empty_cmd")]),
        ("★ doc.missing_text_is_rejected",
         lambda: not all(r.text.strip() for r in [Rule("x", "  ", "cmd")])),
        ("★ doc.duplicate_id_is_rejected",
         lambda: len({r.id for r in [Rule("x", "a", "c"),
                                     Rule("x", "b", "d")]}) == 1),
        ("★ doc.bad_id_shape_is_rejected",
         lambda: not all(__import__("re").fullmatch(r"[a-z][a-z0-9_]*", i)
                         for i in ["Bad-Id"])),
        ("★ doc.dead_cmd_target_is_rejected",
         lambda: _cmd_targets_exist([Rule("x", "t", "python3 zreflect/nope_xyz.py")]) is False),

        # (3) An empty table is not a shape error -- but "empty => all right"
        # must never be the reading. The old case here was a tautology
        # (`isinstance((), tuple)`), which this repo's own `falsifiable` rule
        # exists to catch. The honest criterion: the shipped table is non-empty,
        # so a green run means something was actually judged.
        ("★ doc.table_is_not_empty",
         lambda: len(RULES) > 0 and _cmd_shape_problems(RULES) == []),
        # (4) The principles added from the retired META table: their cmds are
        # real criteria, so each has teeth pinned here (a cmd that can only
        # pass is not a criterion).
        # `ran_is_not_passed` green side runs off_reason_problems on a
        # well-declared gate; here the same call with the declaration dropped
        # must report -- otherwise the cmd could rot into an always-green.
        ("★ doc.ran_is_not_passed_can_red",
         lambda: [p.code for p in _off_reason_problems_of(_CALLS_OFF_SRC)]
         == ["registry.off_without_reason"]
         and _off_reason_problems_of(_DECLARED_SRC) == []),
        # `one_off_decisions_do_not_land`: the CJK round words are spelled by
        # codepoint (this file is inside check_i18n's scan surface), so the
        # pattern itself is verified against a planted hit, not trusted.
        ("★ doc.round_narrative_pattern_has_teeth",
         lambda: _round_pattern_hits(_ROUND_SAMPLE)
         == ["".join(chr(c) for c in (0x8FD9, 0x8F6E))]
         and _round_pattern_hits("round N happened") == ["round N"]
         and _round_pattern_hits("clean prose") == []),
        # (5) A doc must not point readers at a symbol that does not exist.
        ("doc.no_dangling_symbol_references",
         lambda: dangling_references() == []),
        ("★ doc.dangling_reference_is_caught",
         lambda: _dangling_reference_caught()),
    ]


def _dangling_reference_caught():
    """A reference to a symbol that does not exist must be reported.

    Uses a temporary repo so the case proves the **detection**, not the current
    state of this repo (a criterion that only runs against today's docs cannot
    show its teeth).
    """
    import os  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "docs"))
        with open(os.path.join(root, "PRINCIPLES.md"), "w", encoding="utf-8") as fh:
            fh.write("see `registry.this_symbol_never_existed`\n")
        found = dangling_references(root)
        if found != [("PRINCIPLES.md", "registry", "this_symbol_never_existed")]:
            return False
        # and a real symbol must pass, or the criterion forbids citing anything
        with open(os.path.join(root, "PRINCIPLES.md"), "w", encoding="utf-8") as fh:
            fh.write("see `registry.gates`\n")
        return dangling_references(root) == []


# -- Teeth fixtures for the principles merged in from the retired META table --

# A gate source that calls `off()` with **no declared reason** (the red input)
# and one with a declared reason (the green input). Used by
# `doc.ran_is_not_passed_can_red` against `criteria.off_reason_problems`.
_CALLS_OFF_SRC = "def run(argv):\n    off(\"x\")\n"
_DECLARED_SRC = ("off_reason=a real justification long enough\n" + _CALLS_OFF_SRC)

# The round-narrative vocabulary, spelled by codepoint: this file is inside
# check_i18n's scan surface, so a CJK literal here would be judged as the core
# speaking human. Same words as `one_off_decisions_do_not_land`'s cmd.
_CN_ROUND = ("".join(chr(c) for c in (0x8FD9, 0x8F6E)),
             "".join(chr(c) for c in (0x672C, 0x8F6E)))
_ROUND_SAMPLE = "changed this way in " + _CN_ROUND[0]
_ROUND_RE = "|".join(_CN_ROUND + (r"round\s+N",))


def _off_reason_problems_of(src):
    """`criteria.off_reason_problems` over one fake gate source (seam for the
    red-side pin of `ran_is_not_passed`)."""
    import criteria  # noqa: PLC0415
    return criteria.off_reason_problems([{"file": "check_x.py"}],
                                        sources={"check_x.py": src})


def _round_pattern_hits(text):
    """Round-narrative hits in one text (same pattern as
    `one_off_decisions_do_not_land`'s cmd -- kept adjacent so a change to the
    cmd's vocabulary must touch both, and the pin below catches a drift)."""
    import re  # noqa: PLC0415
    return re.findall(_ROUND_RE, text)


# -- Claims about this table, made in prose elsewhere ------------------------
#
# `PRINCIPLES.md` used to tell readers that an `ADVISORY` marker and a "why"
# column exist, that a row flips between `advisory` and `gate`. `Rule` has
# three fields and no such marker -- the prose described a feature that was
# never built. The claim-matching machinery that watched for the phrase coming
# back was retired (it had no consumer outside its own selftest); the single
# real entry it ever carried lives on as retraction R-021 in `retractions.json`,
# which gates the same regression: the retracted phrase may not reappear in a
# living-state document without a correction marker.

# Documents whose `module.symbol` references are checked. Only the docs an agent
# is told to read: a reference here is an instruction to go look at something.
REFERENCE_DOCS = ("README.md", "README.zh.md", "README.de.md", "AGENTS.md",
                  "PRINCIPLES.md", "STATE.md", "docs/LANG-PACK-GLOSSARY.md",
                  "examples/README.md", "skills/einfacht/SKILL.md")
REFERENCE_MODULES = ("i18n", "knobs", "machine", "gate", "registry", "doc",
                     "ledger", "criteria", "render", "runner", "examples",
                     "check_i18n", "check_facts", "check_secrets")
# An extension is a **filename**, not an attribute: `check_facts.py` names a file
# and must not be judged as "module check_facts has attr py".
FILE_EXT = frozenset({"py", "sh", "json", "md", "toml", "yml", "yaml", "txt"})


def _reference_mods():
    """Import the modules a doc may cite. A module that fails to import is
    skipped, not fatal: the reference is then simply not judged."""
    import importlib  # noqa: PLC0415
    mods = {}
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in __import__("sys").path:
        __import__("sys").path.insert(0, here)
    for name in REFERENCE_MODULES:
        try:
            mods[name] = importlib.import_module(name)
        except ImportError:
            continue
    return mods


def _refs_in_text(text, mods):
    """`(module, symbol)` pairs in one doc that its module does not define."""
    ref = re.compile(r"`([a-z][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(?:`|[^A-Za-z0-9_])")
    out = []
    for mod, sym in sorted(set(ref.findall(text))):
        if sym in FILE_EXT:
            continue
        if mod in mods and not hasattr(mods[mod], sym):
            out.append((mod, sym))
    return out


def dangling_references(root=None):
    """`module.symbol` written in a doc but absent from that module.

    Why this exists: `PRINCIPLES.md` pointed readers at
    `registry.dependency_coverage_problems` and the glossary at
    `i18n._CONTRACT_SHAPES`. Neither has ever existed. A reader who follows the
    instruction hits an AttributeError, and **nothing compared the doc to the
    module**. Two instances of the same shape is enough to make it a criterion.
    """
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if root is None else root
    mods = _reference_mods()
    out = []
    for rel in REFERENCE_DOCS:
        path = os.path.join(base, rel)
        if not os.path.exists(path):
            continue
        out += [(rel, mod, sym)
                for mod, sym in _refs_in_text(open(path, encoding="utf-8").read(), mods)]
    return out


def _cmd_targets_exist(rows):
    import os  # noqa: PLC0415
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for r in rows:
        for tok in r.cmd.split():
            if (tok.endswith((".py", ".sh"))) and \
               not os.path.exists(os.path.join(base, tok)):
                return False
    return True


def _selftest():
    import sys  # noqa: PLC0415

    from gate import main_selftest_or  # noqa: PLC0415
    from i18n import M  # noqa: PLC0415
    return main_selftest_or(sys.argv[1:], M("gate.title.doc"), _cases,
                            lambda a: 0)


from gate import module_meta  # noqa: E402

MODULE = module_meta(
    "Principles registry",
    "each principle = one sentence + one re-runnable command; enters the ledger, executed verbatim each commit by check_facts_replay",
    selftest=True)

if __name__ == "__main__":
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import doc as _mod  # noqa: PLC0415
    sys.exit(_mod._selftest())
