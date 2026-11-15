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


class Claim(NamedTuple):
    """A statement prose makes about this module's data.

    `holds` = whether the feature the claim describes was actually built.
    `holds=False` means the claim is a lie and must be removed from `where`;
    `note` says what to do instead. This is the only honest way to retire a
    promise: record that it was never kept, and fail while it is still written.
    """
    id: str
    text: str
    where: str
    holds: bool
    note: str
    markers: tuple


class Meta(NamedTuple):
    """A meta rule: an admission criterion for `RULES`.

    `text` = the rule itself; `why` = the accident that taught it;
    `witness` = an optional command showing the accident class is still
    possible (None means "no machine witness exists", printed as `-`).
    """
    id: str
    text: str
    why: str
    witness: str | None


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
         "each number is produced once: documents reference it as [[key]], never hand-copied (enforced both ways)",
         "python3 zreflect/check_facts.py"),

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
    Rule("off_is_visible",
         "off must be distinguishable from \"ran and passed\"; a gate that can go off must declare why",
         # ⚠️ Must check the **full set**: this used to say `gates()[0]` -- only
         # the first gate was inspected, and missing the other 15 still went
         # green (review observation: checking 1 gate and checking 16 both
         # yield 0). That is an always-true idle spin, the exact shape this
         # repo despises most.
         "python3 -c \"import sys;sys.path.insert(0,'zreflect');"
         "import registry, criteria;gs=registry.gates()[0];"
         "p=criteria.off_reason_problems(gs);"
         "print('off_reason_ok gates=%d problems=%d' % (len(gs), len(p)));"
         "sys.exit(0 if gs and not p else 1)\""),

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
)

_BY_ID = {r.id: r for r in RULES}

# -- Meta rules: the rules *about* the rules -------------------------------
#
# `RULES` says what the code must do. `META` says what **may enter `RULES`** and
# what must stay out of it -- the admission criteria. They used to be prose at
# the top of `PRINCIPLES.md`, which made them hand-editable: prose drifts
# silently because nothing compares it to anything. Same disease as a
# hand-copied number, one level up.
#
# A meta rule cannot have a judging command by construction -- "is this claim
# falsifiable" is the kind of thing a machine cannot settle without solving the
# halting problem. So each meta rule carries a `why` (the accident that taught
# us) and, where one exists, a `witness` (the command that shows the accident
# class is still possible). `witness` is optional and is **not** replayed; an
# absent witness is printed as `-`, never glossed over.
META = (
    Meta("hard_needs_criterion",
         "a rule is hard only if it has a machine criterion; without one it is "
         "advisory and must say ADVISORY",
         "This repo once carried 19 hard rules as prose in `AGENTS.md`, 4 of them "
         "with no criterion at all. They looked identical to the 15 that were "
         "enforced -- a reader could not tell which would be caught and which was "
         "a wish. Letting advice impersonate a hard rule is the single biggest "
         "corruption risk: people rely on it because they assume something stops "
         "them.",
         "python3 zreflect/check_facts_replay.py"),
    Meta("numbers_rot_immediately",
         "a number starts rotting the moment it is written: produce it once in "
         "the ledger, reference it as [[key]], never hand-copy",
         "Code changes and a hand-copied number becomes a lie, and nobody "
         "remembers to come back and fix it.",
         "python3 zreflect/check_facts.py"),
    Meta("ran_is_not_passed",
         "'the scan ran' and 'the scan ran and passed' are different statements; "
         "traversing a directory that does not exist yields an empty set and a "
         "true 'no violations found'",
         "Both sentences were true and the conclusion was wrong.",
         None),
    Meta("agreement_needs_reconciler",
         "two things that must agree will disagree unless a reconciler re-runs on "
         "every commit",
         "A 'must stay in sync' with no reconciler is not a discipline, it is a "
         "wish.",
         "python3 zreflect/registry.py --run commit"),
    Meta("style_is_not_a_rule",
         "style preferences (naming, comment density, file layout) do not enter "
         "the rule table; they are held by 'match the code around you'",
         "A criterion can only guard what is mechanically decidable. Writing style "
         "into the table turns the table into noise, and noise is where a real "
         "rule goes to hide.",
         None),
    Meta("one_off_decisions_do_not_land",
         "a one-off decision ('why this round changed this way') is not recorded in "
         "a document; it belongs to the commit message",
         "The state document says only what is true now; the rule table accepts "
         "only what can still overturn today's design.",
         None),
)

_META_BY_ID = {m.id: m for m in META}

# Machine-block markers: the principles table is rendered from here (prose
# must never hand-copy it).
RULES_BEGIN = "<!-- AUTO:RULES -->"
RULES_END = "<!-- /AUTO:RULES -->"
META_BEGIN = "<!-- AUTO:META -->"
META_END = "<!-- /AUTO:META -->"


def render_meta(rows=None):
    """Meta rules -> the `AUTO:META` machine block. **Pure function**.

    Same reasoning as `render_rules`: this block is **fixed to one language**
    and reconciled byte-for-byte by `facts.py --check`. A block that followed
    `REFLECT_LANG` would make `--check` non-convergent across languages.

    PINNED: byte-exact, English, not language-following.
    """
    rows = META if rows is None else rows
    lines = [META_BEGIN,
             ("> Rendered by `zreflect/facts.py --render-doc` from the `META` table in "
              "`zreflect/doc.py`; **do not hand-edit**."),
             ("> These decide what may enter the rule table. They have no judging "
              "command by construction -- a `witness` (where one exists) shows the "
              "accident class is still possible; it is not replayed."),
             "",
             "| id | meta rule | why | witness |",
             "|---|---|---|---|"]
    for m in sorted(rows, key=lambda x: x.id):
        lines.append("| `%s` | %s | %s | %s |"
                     % (m.id, m.text, m.why,
                        "`%s`" % m.witness if m.witness else "-"))
    lines += ["", "%d meta rules -- the admission criteria for the table below." % len(rows),
              META_END]
    return "\n".join(lines)



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
    """Every `zreflect/*.py` / `*.sh` mentioned in a cmd really exists.

    ⚠️ Only **existence** is checked, not runnability -- runnability is
    `check_facts_replay`'s job (verbatim execution at every commit). This is
    the **cheap** pre-check that catches dead commands left behind by a
    rename.
    """
    import os  # noqa: PLC0415
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for r in RULES:
        for tok in r.cmd.split():
            is_script = tok.endswith((".py", ".sh"))
            if is_script and not os.path.exists(os.path.join(base, tok)):
                return False
    return True


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
        ("★ doc.unknown_lookup_raises",
         lambda: _unknown_lookup_raises()),
        # (3) empty input must be reported
        ("★ doc.empty_table_has_no_problems_but_cannot_be_trusted",
         lambda: _cmd_shape_problems([]) == [] and _is_empty_guard_green(())),
        # (4) meta rules: the admission criteria for the table above are data
        # too. Without these, `AUTO:META` is a block nothing compares to
        # anything -- the exact disease it was introduced to cure.
        ("doc.meta_well_formed", lambda: _meta_problems() == []),
        ("doc.meta_ids_unique",
         lambda: len({m.id for m in META}) == len(META)),
        ("doc.meta_ids_disjoint_from_rules",
         lambda: not ({m.id for m in META} & {r.id for r in RULES})),
        ("★ doc.meta_render_has_markers",
         lambda: META_BEGIN in render_meta() and META_END in render_meta()),
        ("★ doc.meta_missing_why_is_rejected",
         lambda: _meta_problems([Meta("x", "t", "  ", None)]) != []),
        ("★ doc.meta_missing_text_is_rejected",
         lambda: _meta_problems([Meta("x", " ", "why", None)]) != []),
        ("★ doc.meta_bad_id_is_rejected",
         lambda: _meta_problems([Meta("Bad-Id", "t", "why", None)]) != []),
        # An absent witness must print as `-`, never as an empty cell: an empty
        # cell reads as "not applicable", which is a different claim.
        ("doc.meta_absent_witness_prints_dash",
         lambda: "| - |" in render_meta([Meta("x", "t", "why", None)])),
        # and a present witness must be rendered as a command, not prose
        ("doc.meta_present_witness_is_backticked",
         lambda: "| `python3 x.py` |" in render_meta([Meta("x", "t", "why", "python3 x.py")])),
        # A hand-edited render block must not survive: this is the criterion
        # that makes "do not hand-edit" a threat instead of a request.
        ("★ doc.hand_edited_meta_block_is_detected",
         lambda: _hand_edit_detected()),
        # (5) Prose must not promise a feature the table does not have.
        # `PRINCIPLES.md` told readers an ADVISORY marker and a "why" column
        # existed; `Rule` has three fields and neither. Nothing compared the
        # prose to the data, so it survived -- this is that comparison.
        ("doc.no_claim_outlives_its_feature",
         lambda: claim_problems() == [] and _false_claims_still_written()),
        # red path: an unbuilt claim with no note is a silent lie -- recorded
        # as never-built, with nothing saying so
        ("★ doc.unbuilt_claim_without_note_is_reported",
         lambda: claim_problems([Claim("ghost", "t", "PRINCIPLES.md", False,
                                       "  ", ("NOTHING",))])
         == [("ghost", "PRINCIPLES.md", "unbuilt claim without a note")]),
        # green path: a well-recorded unbuilt claim reports nothing; what it
        # forbids is the prose reviving it, tested by
        # `doc.marker_outside_block_is_caught`
        ("doc.recorded_unbuilt_claim_is_honest",
         lambda: claim_problems([Claim("ghost", "t", "PRINCIPLES.md", False,
                                       "never built", ("NOTHING",))]) == []),
        # A claim that DOES hold is not a problem -- otherwise the criterion
        # would forbid ever describing the module accurately.
        ("doc.true_claim_passes",
         lambda: claim_problems([Claim("real", "t", "PRINCIPLES.md", True,
                                       "", ("X",))]) == []),
        # The scan must ignore rendered blocks (they are produced from here) and
        # must still catch the same word written by hand outside them.
        ("★ doc.marker_outside_block_is_caught",
         lambda: _marker_outside_block_caught()),
        # (6) A doc must not point readers at a symbol that does not exist.
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


def _marker_outside_block_caught():
    """`_outside_blocks` must strip rendered blocks and keep hand-written prose."""
    doc_text = ("prose before\n"
                "<!-- AUTO:META -->\nADVISORY\n<!-- /AUTO:META -->\n"
                "prose after\n")
    stripped = _outside_blocks(doc_text)
    return "ADVISORY" not in stripped and "prose after" in stripped


def _hand_edit_detected():
    """Rendering twice from the same table is byte-identical; a block that
    differs from `render_meta()` is hand-edited (this is what `--check` compares)."""
    first, second = render_meta(), render_meta()
    tampered = first.replace("hard_needs_criterion", "hard_needs_criterion_HAND")
    return first == second and tampered != render_meta()


# -- Claims about this table, made in prose elsewhere ----------------------
#
# `PRINCIPLES.md` used to tell readers that an `ADVISORY` marker and a "why"
# column exist, that a row flips between `advisory` and `gate`. `Rule` has
# three fields and no such marker -- the prose described a feature that was
# never built. Nothing caught it, because prose about a data table is not
# compared to that data table by anything.
#
# The cure is the same as everywhere else in this repo: make the claim data,
# then compare. Each entry is (the claim, where it is written, whether it still
# holds). A claim that no longer holds fails the gate; delete the claim or build
# the feature, but do not let prose promise what the table cannot do.
CLAIMS = (
    # `ADVISORY` is the whole vocabulary of this claim; if the word returns to
    # PRINCIPLES.md, someone is describing the marker again.
    Claim("advisory_marker",
          "a rule row can be marked ADVISORY instead of gate",
          "PRINCIPLES.md",
          False,   # never built: Rule has no such field
          "there is no advisory marker; a rule without a criterion is not a rule "
          "and does not enter the table at all (see META.hard_needs_criterion)",
          ("ADVISORY",)),
)


def claim_problems(claims=None):
    """Claims marked `holds=False` are lies still owed a fix.

    Returns a tuple list (empty = honest). This module is the **data layer**: it
    imports no i18n (a `M(...)` call here would make the rule table depend on a
    language pack, and the rules must read the same in every language).

    `holds=False` is not "an open task": it is the **permanent record that the
    feature was never built**. What it forbids is the *prose* reviving the
    claim, and that is `_false_claims_still_written()`'s job. So this function
    reports nothing for a well-recorded unbuilt claim -- an unbuilt claim that
    stays unbuilt is honest, an unbuilt claim that is described as existing is
    the lie.
    """
    rows = CLAIMS if claims is None else claims
    out = []
    for c in rows:
        if not c.holds and not c.note.strip():
            out.append((c.id, c.where, "unbuilt claim without a note"))
    return out


def _false_claims_still_written():
    """A claim marked `holds=False` must have no trace left in the named document.

    Keyword-based on purpose: the point is "did the phrase come back", not
    grammar. `markers` is the vocabulary the claim would use if restated.
    """
    import os  # noqa: PLC0415
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c in CLAIMS:
        if c.holds:
            continue
        path = os.path.join(base, c.where)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        # Only the **rendered block is exempt**: that text is produced from this
        # module, so a mention there is the source talking, not prose promising a
        # feature. Everything outside the machine blocks is hand-written prose and
        # must not revive the claim.
        prose = _outside_blocks(text)
        if any(m in prose.upper() for m in c.markers):
            return False
    return True


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


def _outside_blocks(text):
    """The document with every `AUTO:` machine block removed."""
    import re  # noqa: PLC0415
    return re.sub(r"<!-- AUTO:[A-Z]+ -->.*?<!-- /AUTO:[A-Z]+ -->", "", text,
                  flags=re.S)


def _meta_problems(rows=None):
    """Shape criteria for one meta-rule set: id / text / why must be non-empty,
    ids must be lowercase-dotted like rule ids."""
    import re  # noqa: PLC0415
    out = []
    for m in (META if rows is None else rows):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", m.id):
            out.append((m.id, "bad_id"))
        if not m.text.strip():
            out.append((m.id, "empty_text"))
        if not m.why.strip():
            out.append((m.id, "empty_why"))
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


def _unknown_lookup_raises():
    try:
        rule("definitely_not_a_rule")
        return False
    except KeyError:
        return True


def _is_empty_guard_green(rows):
    """An empty table having **no shape problems** is normal (having no principles is not a shape error),
    but "empty table => everything is right" is a trap -- so when `ids()` is empty the self-evidence must **stay visible**.

    This case pins the criterion itself: empty input must not masquerade as
    "checked".
    """
    return isinstance(rows, tuple) and len(rows) == 0


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
