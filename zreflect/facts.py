#!/usr/bin/env python3
"""CLI for the facts ledger: measure once, write the ledger, render machine blocks, plus **the two guards**.

Usage
    python3 zreflect/facts.py                      # measure once and write FACTS.json (drops/rewrites are refused)
    python3 zreflect/facts.py --allow-drop         # allow drops this run (dropped keys are printed)
    python3 zreflect/facts.py                      # measure once (numeric facts + principle verdict commands)
    python3 zreflect/facts.py --accept-changes     # allow rewrites this run (old value -> new value is printed)
    python3 zreflect/facts.py --accept-changes=k1,k2  # accept only the listed keys; other rewrites still refused (issue #3 (1))
    python3 zreflect/facts.py --render-doc [file]  # write machine blocks (no file = all docs)
    python3 zreflect/facts.py --check [file]       # does the block in the doc match the ledger
    python3 zreflect/facts.py --get key            # print only that key's value (consumer exit, issue #4 (4))
    python3 zreflect/facts.py show [key]           # print one fact
    python3 zreflect/facts.py --selftest           # self-proof: both guards must be able to go red

⚠️ **If it cannot be measured, do not write it** (better absent than fake). E.g. "latest
all-green regression" is only measurable on a machine with logs; without logs leave that
fact **empty** rather than writing 0 -- 0 is a number, and people will cite it as a result.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate  # noqa: E402
import knobs  # noqa: E402
import ledger  # noqa: E402
import registry  # noqa: E402
from check_facts import block_homes  # noqa: E402
from gate import (  # noqa: E402
    machine,  # noqa: E402
    main_selftest_or,
    module_meta,
    repo,
)
from i18n import M  # noqa: E402
from ledger import (  # noqa: E402
     age_days,
    fact,
    facts_of,
    load_or_fatal,
    render_block,
    value_of,
)

REPO_REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _out():
    """Ledger write path. **A function, not a module constant**: `repo()` reads
    `gate.GATE_REPO` when called, so fixtures can change the path."""
    return repo(knobs.get("REFLECT_FACTS"))
# ⚠️ **Not a module-level constant**: `REFLECT_DOC` is a name-type knob, hooks may
# change it mid-run (fixtures do). `doc.state_name()` reads it fresh every time --
# the single source.
# There used to be an import-time `DOC = os.environ.get(...)` snapshot here, which
# together with `doc.state_name()` formed **two sources** (the exact shape the
# snapshot gate catches).
def _doc():
    import doc  # noqa: PLC0415
    return doc.state_name()


# == Your part ==================================================================
_COUNT_CMD = "python3 zreflect/facts.py --count"


def count_files(root, suffix):
    """Number of files under `root` ending in `suffix` (skips `.git`)."""
    n = 0
    for _dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        n += sum(1 for f in filenames if f.endswith(suffix))
    return n


def count_lines(root, suffix):
    """**Total line count** of files under `root` ending in `suffix` (skips `.git`).

    Kept separate from `count_files` rather than one function with a mode flag:
    the two differ in *what they count* (files vs lines); merging them would give
    `cmd` an extra parameter -- and one more place to get it wrong.
    """
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            if not name.endswith(suffix):
                continue
            try:
                with open(os.path.join(dirpath, name), encoding="utf-8",
                          errors="replace") as fh:
                    total += sum(1 for _ in fh)
            except OSError:
                continue                # uncountable files are not counted -- better absent than fake
    return total


_AUTO_BLOCK = re.compile(r"^\s*<!--\s*(/?AUTO:[A-Z]+)\s*-->\s*$")


def _count_file_lines(path):
    """Lines **outside machine blocks** in one `.md` file. Unreadable => 0.

    A marker counts as a block boundary only when it occupies the line by
    itself; one merely mentioned in prose must not start a block. State resets
    per file, and every `AUTO:*` block is excluded, not just FACTS.
    """
    total = 0
    in_block = False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _AUTO_BLOCK.match(line)
                if m:
                    in_block = not m.group(1).startswith("/")
                    continue
                if not in_block:
                    total += 1
    except OSError:
        return 0                    # unreadable files are not counted -- better absent than fake
    return total


def count_md_lines(root):
    """Lines **outside machine blocks** in `.md` files: the single replayable
    implementation of the `md_lines` fact (pure Python, cross-platform).

    Excludes **all** `AUTO:*` blocks, not just FACTS -- `AUTO:GATES` and
    `AUTO:RULES` are render output too; counting them makes every render shift
    the total, so `check_facts_replay` stays permanently red. The ledger's `cmd`
    calls this function: measurement and replay share one source.

    Per-file state is owned by `_count_file_lines`; unreadable files count 0.
    """
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        total += sum(_count_file_lines(os.path.join(dirpath, name))
                     for name in sorted(filenames) if name.endswith(".md"))
    return total


def measure_example():
    """Placeholder measurement (`py_files`, `md_files`, `py_lines`, `md_lines`); override via `REFLECT_MEASURE_MODULE`."""
    facts = {}
    n_py = 0
    n_md = 0
    lines_py = 0
    for root, dirs, files in os.walk(gate.GATE_REPO):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if f.endswith(".py"):
                n_py += 1
                try:
                    lines_py += sum(1 for _ in open(os.path.join(root, f), encoding="utf-8",
                                                    errors="replace"))
                except OSError:
                    pass
            elif f.endswith(".md"):
                n_md += 1
    py_files_cmd = "%s -files .py" % _COUNT_CMD
    md_files_cmd = "%s -files .md" % _COUNT_CMD
    facts["py_files"] = fact(n_py, py_files_cmd, "repo",
                             M("facts.note.example_fact"))
    facts["md_files"] = fact(n_md, md_files_cmd, "repo")
    facts["py_lines"] = fact(lines_py, "%s -lines .py" % _COUNT_CMD, "repo",
                             M("facts.note.bare_number_demo"))
    md_lines_cmd = '%s -md' % _COUNT_CMD
    md_lines = count_md_lines(gate.GATE_REPO)
    facts["md_lines"] = fact(md_lines, md_lines_cmd, "repo",
                              M("facts.note.excludes_machine_block"))
    v = os.environ.get("UPSTREAM_VERSION", "").strip()
    if v:
        facts["upstream_version"] = fact(v, "echo \"$UPSTREAM_VERSION\"", "env",
                                         M("facts.note.measure_or_omit"))
    return facts


# == No need to change anything below ===========================================
def _has_principles_doc():
    """Does this repo accept the suite's principles? -- The **declaration** lives in
    `doc.accepts_principles()`; this only forwards (the decision exists in one place)."""
    import doc  # noqa: PLC0415
    return doc.accepts_principles()


def _doc_names():
    """Names of docs carrying machine blocks (`STATE.md` and `PRINCIPLES.md` unless opted out)."""
    import doc  # noqa: PLC0415
    names = [_doc()]
    if _has_principles_doc():
        names.append(doc.PRINCIPLES)
    return tuple(names)


def _read_doc(p, path_rel):
    """Read a doc. Returns `(text, rc)`; rc != 0 = FATAL already reported.

    ⚠️ **Unreadable != stale block**: invalid UTF-8 / permissions / a directory --
    all configuration accidents (FATAL rc=2), not rc=1 "criterion red".
    """
    try:
        return open(p, encoding="utf-8").read(), 0
    except (OSError, UnicodeError) as e:
        print(machine().emit("fatal", M("facts.doc_unreadable",
                                        path=path_rel, error=e)),
              file=sys.stderr)
        return None, 2


def _own_blocks(path_rel, ledger):
    """The machine blocks **owned by** this doc. Returns `(blocks, rc)`; rc != 0
    means the failure was already reported.

    No owner found => rc 2, never a silent-green `blocks=[]`: a doc outside the
    ownership table has nothing to validate, and "no block is stale" would be a
    sentence that checked nothing. Only markers belonging to this doc are
    returned; other docs' markers are expected to be absent here.
    """
    homes, err = block_homes(ledger)
    if err:
        print(machine().emit("fatal", err), file=sys.stderr)
        return None, 2
    # Validate only blocks **belonging to this doc**. Other blocks' markers live in
    # other docs -- not finding them here is normal (previously all blocks were
    # crammed into one doc: the discipline block's markers were not in STATE.md => reported).
    mine = [b for name, blocks in homes
            if name in (os.path.basename(path_rel), path_rel)
            for b in blocks]
    if mine:
        return mine, 0
    print(machine().emit("fatal",
                          M("facts.doc_has_no_home", path=path_rel,
                            known=", ".join(name for name, _ in homes))),
          file=sys.stderr)
    return None, 2


def _replace_blocks(text, blocks, path_rel):
    """Replace each block in place with new content. Returns `(new_text, rc)`.

    Both the begin and end markers must be present -- if missing, the doc has been
    damaged; **never silently append**: silent appending turns "stale block" into
    "two copies of the block", a much harder failure mode to diagnose.
    """
    new = text
    for begin, end, body in blocks:
        if begin not in new or end not in new:
            print(machine().emit("fatal",
                                  M("facts.markers_missing_render",
                                    path=path_rel, begin=begin, end=end)),
                  file=sys.stderr)
            return None, 2
        pre, _, rest = new.partition(begin)
        _, _, post = rest.partition(end)
        new = pre + body + post
    return new, 0


def _swallowed_marker_problems(new, blocks, path_rel):
    """Integrity guard run before writing: the replacement must preserve the markers
    of **all** blocks.

    A marker literal written into a body makes first-occurrence replacement
    swallow the text between two blocks, so other blocks vanish. Ambiguity =>
    refuse to write and let a human fix the doc. There is deliberately no
    pre-replacement count assertion: a block's `cmd` may legitimately quote a
    begin literal.
    """
    out = []
    for begin, end, _ in blocks:
        if begin not in new or end not in new:
            out.append(M("facts.marker_swallowed_body",
                         path=path_rel, begin=begin))
    return out


def write_doc(path_rel, ledger):
    """Write the machine block into a doc (in-place replacement). No markers => error,
    **never silently append**.

    The three steps are each a named helper (read / replace / integrity guard): each
    has its own set of "refuse to write" exits; merged together, a reader must count
    returns to know what has already been checked.
    """
    p, blocks, text, rc = _prepare_render(path_rel, ledger)
    if rc:
        return rc
    new, rc = _replace_blocks(text, blocks, path_rel)
    if rc:
        return rc
    swallowed = _swallowed_marker_problems(new, blocks, path_rel)
    if swallowed:
        for x in swallowed:
            print(machine().emit("fatal", x), file=sys.stderr)
        return 2
    if new == text:
        print(M("facts.render_unchanged", path=path_rel))
        return 0
    rc = _write_or_fatal(p, new, path_rel)
    if rc:
        return rc
    print(M("facts.render_written", path=path_rel))
    return 0


def _prepare_render(path_rel, ledger):
    """Three preconditions: doc exists / block ownership checks out / doc is readable.
    Returns `(path, blocks, text, rc)`.

    Any failure returns a non-zero rc (FATAL already reported) -- "does the file
    exist / is the ownership right / can it be read" are three different
    configuration accidents with their own error codes.
    """
    p = gate.repo_path(path_rel)
    if not os.path.exists(p):
        print(machine().emit("fatal", M("facts.doc_missing_render", path=p)),
              file=sys.stderr)
        return p, None, None, 2
    blocks, rc = _own_blocks(path_rel, ledger)
    if rc:
        return p, None, None, rc
    text, rc = _read_doc(p, path_rel)
    return p, blocks, text, rc


def _write_or_fatal(p, new, path_rel):
    """Write to disk. Failure is an **environment accident** (FATAL rc=2), not a
    "stale block" (rc=1).

    The old `open(...).write(...)` turned this into a raw traceback + rc=1 -- the
    caller would go inspect block content while the real problem was an unwritable
    file. Read-only / disk full / permissions all belong to this class.
    """
    try:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(new)
    except OSError as e:
        print(machine().emit("fatal", M("facts.doc_unwritable",
                                        path=path_rel, error=e)),
              file=sys.stderr)
        return 2
    return 0


def check_doc(path_rel, ledger):
    """Check one document's machine blocks via `check_facts.doc_block_problems`."""
    import check_facts  # noqa: PLC0415
    p = gate.repo_path(path_rel)
    if not os.path.exists(p):
        print(machine().emit("fatal", M("facts.doc_missing_check", path=p)), file=sys.stderr)
        return 2
    blocks, rc = _own_blocks(path_rel, ledger)
    if rc:
        return rc
    text, rc = _read_doc(p, path_rel)
    if rc:
        return rc
    probs = check_facts.doc_block_problems(path_rel, text, blocks)
    if probs:
        print(machine().emit("fatal", probs[0]), file=sys.stderr)
        return 2 if probs[0].code == "facts.markers_missing_check" else 1
    print(M("facts.block_consistent", path=path_rel))
    return 0


def _age_human(entry):
    """Human wording for `measured_at` (issue #3 (2)): today / N days ago / unrecorded."""
    d = age_days(entry)
    if d is None:
        return M("facts.age.unrecorded")
    if d < 1:
        return M("facts.age.today")
    return M("facts.age.days_ago", days=int(d))


def _measure():
    """Dispatch via `REFLECT_MEASURE_MODULE` (FATAL rc=2 if configured and unusable, else placeholder)."""
    mod_name = os.environ.get("REFLECT_MEASURE_MODULE", "").strip()
    if mod_name:
        try:
            _m = __import__(mod_name)
            fn = getattr(_m, "measure")   # noqa: B009 -- contract entry name
        except Exception as e:                            # noqa: BLE001
            print(machine().emit("fatal", M(
                "facts.measure_module_unusable", module=mod_name,
                error=repr(e), hint=M("facts.measure_module_where"))),
                file=sys.stderr)
            raise SystemExit(2) from e
        if os.path.abspath(gate.GATE_REPO) == os.path.abspath(REPO_REAL):
            return fn()
    else:
        print("⚠ %s" % M("facts.measure_placeholder_used"), file=sys.stderr)
        own = _own_code_hint()
        if own:
            print("  %s" % own, file=sys.stderr)
    return measure_example()


# Common shapes of "a repo with its own code" (directory names only, no content guessing).
_OWN_CODE_DIRS = ("src", "lib", "app", "pkg", "packages")


def _own_code_hint():
    """Does this repo look like it has its own code? If yes, return one **specific** hint.

    Called only when `REFLECT_MEASURE_MODULE` is unset -- the "you haven't told me
    what to measure" moment, and the only moment a hint is appropriate.
    """
    root = gate.GATE_REPO
    found = [d for d in _OWN_CODE_DIRS if os.path.isdir(os.path.join(root, d))]
    if not found:
        return None
    return str(M("facts.measure_own_code_hint", dirs=", ".join(found)))


def _carry_first_seen(facts, old):
    """Instrument lifecycle (issue #6 (1)): keys whose value did not change keep the old
    `first_seen` (changed values / new keys get today stamped by `ledger.fact()`) --
    constancy detection (the pluggable gate `check_instruments.py`) depends on it.
    """
    for key, entry in facts.items():
        prior = old.get(key)
        fs = prior.get("first_seen") if isinstance(prior, dict) else None
        if fs and value_of(prior) == value_of(entry):
            entry["first_seen"] = fs


def _write_ledger_doc(out, facts):
    """Write the ledger to disk. Returns `(rc, error message or None)`.

    The **one serialization site**: `--accept*`'s `_write_ledger` and
    `--init`'s `_init_principles_into_ledger` delegate here.
    """
    import json  # noqa: PLC0415
    doc = {"schema": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "_why": M("facts.ledger_why"),
           "facts": facts}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return 0, None


def _attach_core_seal(facts):
    """Verify sealed core (if sealed) and attach `core_seal`; return 2 on tamper."""
    import seal  # noqa: PLC0415
    if not seal.seal_exists():
        return 0
    probs = seal.verify_problems()
    if probs:
        print(machine().emit("fatal", probs[0]), file=sys.stderr)
        return 2
    sha = seal.current_tree_sha(verified=True)
    if sha:
        facts["core_seal"] = fact(
            sha, "python3 zreflect/registry.py --verify-seal",
            "seal", M("facts.note.core_seal"))
    return 0


def measure(argv):
    """Measure facts, run drop/change guards via `ledger.decide`, and write ledger."""
    facts = _measure()
    rc = _attach_core_seal(facts)
    if rc:
        return rc

    out = _out()
    rc = _shape_guard(facts)
    if rc:
        return rc
    old = facts_of(load_or_fatal(out)) if os.path.exists(out) else {}

    rc = _guarded_write(argv, old, facts)
    if rc:
        return rc
    _carry_first_seen(facts, old)
    rc, err = _write_ledger_doc(out, facts)
    if err:
        print(machine().emit("fatal", err), file=sys.stderr)
        return 2
    print(M("facts.measure_written",
            path=os.path.relpath(out, gate.GATE_REPO), count=len(facts)))
    for k, v in sorted(facts.items()):
        print("  %-20s %s (%s)" % (k, v["value"], _age_human(v)))
    return 0


def _shape_guard(facts):
    """Shape of `measure()`'s return value: every entry must have `ledger.fact()`'s
    shape -- `{"key": {"value": ..., "cmd": ..., "source": ...}}`, never a bare
    `{"key": 12}`.

    Checked **before writing**: a bad shape reported after the write leaves a
    half-written ledger and a bare traceback. Legitimate origins all carry a
    `value` key (`ledger.fact()`, old-ledger dicts on the `--accept*` path,
    `facts_of(ledger)` merges), so "has a `value` key" is the criterion. Returns
    0 or 2 (FATAL already emitted).
    """
    bad = sorted(k for k, v in (facts or {}).items()
                 if not (isinstance(v, dict) and "value" in v))
    if not bad:
        return 0
    print(machine().emit("fatal", M(
        "facts.measure_bad_shape", count=len(bad),
        keys=", ".join(bad[:6]), hint=M("facts.measure_shape_hint"))),
        file=sys.stderr)
    return 2


def _guarded_write(argv, old, facts):
    """The two guards (drop / rewrite) plus the blind-write guard. Returns rc (0 = pass, 2 = refuse)."""
    verdict, problems, notes = ledger.decide(old, facts,
                                             accepted=ledger.accepted_keys(argv),
                                             allow_drop="--allow-drop" in argv)
    for x in notes["err"]:
        print(x, file=sys.stderr)
    for x in notes["out"]:
        print(x)
    if verdict == "refuse":
        for x in problems:
            print(machine().emit("fatal", x), file=sys.stderr)
        return 2
    fatal_w, warn_w = ledger.write_target_problems(_out())
    if warn_w:
        print("⚠ %s" % warn_w, file=sys.stderr)
    if fatal_w:
        print(machine().emit("fatal", fatal_w), file=sys.stderr)
        return 2
    return 0


def _facts_with_principles(led):
    """Combine `facts_of(led)` with `doc.facts_of_rules()` when principles are active."""
    import doc  # noqa: PLC0415
    f = dict(facts_of(led))
    if _has_principles_doc():
        f.update(doc.facts_of_rules())
    return f


def get_value(led, key):
    """Fetch a ledger or principle value by key (`(True, val)` or `(False, err_msg)`)."""
    f = _facts_with_principles(led)
    if key not in f:
        return False, M("facts.unknown_key", key=key,
                        existing=", ".join(sorted(f)) or M("facts.none"))
    return True, value_of(f[key])


def _load_or_empty():
    """Read the ledger; **a missing ledger yields an empty one** (used by `--accept*`).

    `_accept*` must be able to create the ledger in a fresh repo; `_load_or_die`
    serves rendering/checking, where a missing ledger is FATAL.
    """
    out = _out()
    if not os.path.exists(out):
        return {"schema": 1, "facts": {}}
    return load_or_fatal(out)


def _load_or_die():
    """Read ledger; missing => actionable FATAL hint pointing at `REFLECT_FACTS`."""
    out = _out()
    if not os.path.exists(out):
        print(machine().emit("fatal",
                              M("facts.no_ledger_yet",
                                name=os.path.basename(out),
                                path=os.path.relpath(out, gate.GATE_REPO))),
              file=sys.stderr)
        raise SystemExit(2)
    return load_or_fatal(out)


def main(argv):
    """Command dispatch. **Dispatch only** -- one `cmd_*` handler per command;
    handlers do not share a local scope.

    `_classify(argv)` decides the branch: `measure` (also for `--allow-drop` /
    `--accept-changes*` modifiers), `help` and `unknown` both print usage, and a
    registered command is looked up in `_command_table()`. Unknown commands exit
    2; they never fall back to `measure()`, which would write the ledger.
    """
    kind = _classify(argv)
    if kind == "measure":
        return measure(argv)
    if kind == "help":
        print(_usage(), file=sys.stderr)
        return 0
    if kind == "unknown":
        print(_usage(), file=sys.stderr)
        print(machine().emit("fatal", M("facts.unknown_command",
                                       command=argv[0])), file=sys.stderr)
        return 2
    return _command_table()[argv[0]](argv)


def _classify(argv):
    """Classify `argv` into `'measure' | 'help' | 'command' | 'unknown'`."""
    if not argv:
        return "measure"
    first = argv[0]
    if first in ("--help", "-h", "help"):
        return "help"
    if first in _command_table():
        return "command"
    if first.startswith(("--allow-drop", "--accept-changes")):
        return "measure"
    return "unknown"



# Command name -> handler. **The table lives outside the function**: dispatch itself
# is one line; adding a command = adding a function + one registration line.
# Deliberately a dict rather than an if-chain -- the latter adds a branch per
# command, complexity growing linearly with the command count (observed: 27).
# Command name -> handler. **The table is filled in at the end of the file** (handlers
# are defined in between), so it starts empty; `_command_table()` just gives "reading
# the table" a name, and keeps the "why a table, not an if-chain" explanation next to
# the reading site.
_COMMANDS: dict = {}


def _usage():
    """Language-pack usage line (`facts.usage`)."""
    return M("facts.usage")


def _command_table():
    """Command name -> handler.

    The table is the one readable list of available commands; handlers stay
    independent and individually testable.
    """
    return _COMMANDS


def cmd_render(argv):
    """The `--render` command."""
    sys.stdout.write(render_block(_load_or_die()) + "\n")
    return 0


def cmd_render_doc(argv):
    """The `--render-doc` command (no doc given => render every doc in `block_homes`)."""
    led = _load_or_die()
    if len(argv) > 1:
        return write_doc(argv[1], led)
    rc = 0
    for name in _doc_names():
        rc = write_doc(name, led) or rc
    return rc


def cmd_check(argv):
    """The `--check` command."""
    # No doc name given => check **every** doc carrying machine blocks (`block_homes`
    # is the single source). "The only two things that must be measured" = STATE
    # (numbers) + PRINCIPLE (verdicts) -- both docs are on this surface; skipping one
    # makes that doc's "do not hand-edit" an empty threat.
    if len(argv) > 1:
        return check_doc(argv[1], _load_or_die())
    ledger = _load_or_die()
    rc = 0
    for name in _doc_names():
        r = check_doc(name, ledger)
        rc = rc or r
    return rc


def cmd_get(argv):
    """The `--get` command."""
    if len(argv) < 2:
        print(machine().emit("fatal", M("facts.get_needs_key")), file=sys.stderr)
        return 2
    ok, v = get_value(_load_or_die(), argv[1])
    if not ok:
        print(machine().emit("fatal", v), file=sys.stderr)
        return 2
    print(v)                       # print only the value itself: no explanation, no prefix
    return 0


def _init_skeleton(root, state):
    """Skeleton docs to generate: `{filename: body}`. **Pure data**, never touches disk.

    ⚠️ **Every name comes from a knob**: renamed documents must be generated under
    the same names the gates look for.
    """
    import doc  # noqa: PLC0415
    import registry as _reg  # noqa: PLC0415
    retract_name = knobs.get("REFLECT_RETRACTIONS")
    history_name = knobs.get("REFLECT_HISTORY")
    readme_name = (knobs.readme_names() or ["README.md"])[0]
    return {
        state: (
            "# " + state + "\n\n"
            "> live state: only what is true **now**, and every line below is\n"
            "> rendered from the ledger; never copy a number into prose.\n\n"
            + ledger.BLOCK_BEGIN + "\n" + ledger.BLOCK_END + "\n\n"
            + _reg.GATES_BEGIN + "\n" + _reg.GATES_END + "\n"),
        doc.PRINCIPLES: (
            "# PRINCIPLES\n\n"
            "> design rules that do not change. Each one is a **runnable\n"
            "> command**, replayed by `check_facts_replay` on every commit.\n\n"
            + doc.RULES_BEGIN + "\n" + doc.RULES_END + "\n"),
        # The prose carrier must exist from the start: a repo that adopts the
        # suite gets `check_history` in its commit phase immediately, and a
        # missing history document is a red one. Seeding it here is what makes
        # "prose has one legal home" true on day one rather than after the first
        # red commit.
        history_name: (
            "# " + history_name + "\n\n"
            "> The one carrier where prose is allowed. Every entry here answers\n"
            "> \"why does this rule exist\" -- an account reproducible only under\n"
            "> the conditions of that moment, so it stays off every scan surface.\n\n"
            "## Entries\n"),
        retract_name: '{"schema": 1, "retractions": []}\n',
        readme_name: (
            "# " + os.path.basename(root) + "\n\n"
            "> the project's human-facing docs. `check_readme_sync` treats the\n"
            "> README trio as three copies of one assertion -- if you add\n"
            "> `README.zh.md` / `README.de.md`, keep all three in step.\n"),
        "AGENTS.md": (
            "# AGENTS.md\n\n"
            "Routing only. Rules live in `zreflect/doc.py` (`RULES`);\n"
            "state lives in `" + state + "`; history is not tracked.\n\n"
            "```bash\n"
            "python3 zreflect/registry.py --run commit\n"
            "python3 zreflect/harness.py\n"
            "```\n"),
    }


def _create_missing(root, files):
    """Create missing files, **never overwrite existing ones**. Returns `(created, kept)`."""
    created, kept = [], []
    for name, body in files.items():
        p = os.path.join(root, name)
        if os.path.exists(p):
            kept.append(name)
            continue
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        created.append(name)
    return created, kept


def _init_principles_doc():
    """Render `PRINCIPLES.md` (`AUTO:RULES` block) from `doc.RULES`."""
    import doc  # noqa: PLC0415
    if not doc.accepts_principles():
        return 0
    return write_doc(doc.PRINCIPLES, {"schema": 1, "facts": {}})


def _init_questions_dir(root):
    """The `questions/` directory plus one example open question.

    An empty directory is rejected by `check_questions`' zero-trust guard
    (`questions.guard_empty`) -- so we plant a **sample open question**: it doubles as
    the template for "how to write an open question".
    """
    # Delegates to the single source (it strips; the same criterion used to exist in
    # three copies, one without stripping -- observed: an empty string made
    # check_questions treat the repo root as the questions directory).
    qdir = knobs.questions_path(root)
    if not os.path.isdir(qdir):
        os.makedirs(qdir, exist_ok=True)
        print(str(M("facts.init_created", name="questions/")))
    if [n for n in os.listdir(qdir) if n.endswith(".md")]:
        return
    with open(os.path.join(qdir, "01-example.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "# Example open question\n\n"
            "**Status:** ready-for-agent\n\n"
            "**Settling:** `python3 -c \"raise SystemExit(1)\"` "
            "-- rc=0 settles A; rc=1 settles B\n\n"
            "Replace this with a real open question, or delete it\n"
            "once you have some.\n")


def cmd_count(argv):
    """`--count-files SUF` / `--count-lines SUF` / `--count-md`: the ledger's replay commands.

    Separate subcommands rather than inlined in `measure()`: a ledger `cmd` must be
    **replayable verbatim** (`check_facts_replay`), while `measure()` writes to disk
    -- a replayer must not trigger a write.

    All **pure Python**: `find | wc` does not exist on Windows, and `cmd` is the
    template consumers copy -- the template itself must be cross-platform.
    """
    rest = argv[1:]
    if rest == ["-md"]:
        print(count_md_lines(gate.GATE_REPO))
        return 0
    if len(rest) == 2 and rest[0] in ("-files", "-lines"):
        fn = count_files if rest[0] == "-files" else count_lines
        print(fn(gate.GATE_REPO, rest[1]))
        return 0
    print(M("facts.count_usage"), file=sys.stderr)
    return 2


def cmd_init(argv):
    """The `--init` command: fresh-repo bootstrap that generates a qualified
    skeleton in one shot (`STATE.md` seeded with both AUTO markers, `PRINCIPLES.md`
    rendered with `AUTO:RULES`, and `questions/`).

    Never overwrites existing files -- only gaps are filled, and each step prints
    what it did. Returns 0 immediately when nothing was created, so running
    `--init` twice is idempotent.
    """
    import doc  # noqa: PLC0415
    root = gate.GATE_REPO
    state = doc.state_name()
    created, kept = _create_missing(root, _init_skeleton(root, state))
    for name in created:
        print(str(M("facts.init_created", name=name)))
    for name in kept:
        print(str(M("facts.init_kept", name=name)))
    if not created:
        return 0
    rc = _init_principles_doc()
    if rc:
        return rc
    _init_questions_dir(root)
    print(str(M("facts.init_next")))
    return 0


def cmd_accept(argv):
    """The `--accept` command."""
    # Manually register one fact: `--accept <key> <value> <cmd> <source>`
    # (the user's own measurement, without touching measure()). The value must be a
    # **bare value**.
    if len(argv) < 5:
        print(machine().emit("fatal", M("facts.accept_usage")), file=sys.stderr)
        return 2
    key, value = _arg(argv, 1), _arg(argv, 2)
    cmd, source = _arg(argv, 3), _arg(argv, 4)
    if not key or not cmd.strip():
        print(machine().emit("fatal", M("facts.accept_usage")), file=sys.stderr)
        return 2
    led = _load_or_empty()
    new = dict(facts_of(led))
    new[key] = fact(value, cmd, source)
    return _write_ledger(led, new, argv, accept_all=True)


def cmd_show(argv):
    """The `show` command."""
    led = _load_or_die()
    f = _facts_with_principles(led)
    keys = [argv[1]] if len(argv) > 1 else sorted(f)
    rc = 0
    for k in keys:
        if k not in f:
            print(M("facts.show_unknown_key", key=k,
                    existing=", ".join(sorted(f))), file=sys.stderr)
            rc = 1
            continue
        e = f[k] if isinstance(f[k], dict) else {"value": f[k]}
        print("%-20s %s" % (k, e.get("value")))
        print(M("facts.show.source", value=e.get("source", "?")))
        print(M("facts.show.cmd", value=e.get("cmd", "?")))
        if e.get("note"):
            print(M("facts.show.note", value=e["note"]))
    return rc


def _arg(argv, i):
    return argv[i] if len(argv) > i else ""


def _write_ledger(led, facts, argv, accept_all=False):
    """Write `facts` back to the ledger (through the same guard). `accept_all` => accept all rewrites this run."""
    out = _out()
    old = facts_of(led)
    accepted = None if accept_all else ledger.accepted_keys(argv)
    verdict, problems, notes = ledger.decide(old, facts, accepted=accepted,
                                             allow_drop="--allow-drop" in argv)
    for x in notes["err"]:
        print(x, file=sys.stderr)
    if verdict == "refuse":
        for x in problems:
            print(machine().emit("fatal", x), file=sys.stderr)
        return 2
    fatal_w, warn_w = ledger.write_target_problems(out)
    if warn_w:
        print("⚠ %s" % warn_w, file=sys.stderr)
    if fatal_w:
        print(machine().emit("fatal", fatal_w), file=sys.stderr)
        return 2
    rc, err = _write_ledger_doc(out, facts)
    if err:
        print(machine().emit("fatal", err), file=sys.stderr)
        return 2
    print(M("facts.measure_written",
            path=os.path.relpath(out, gate.GATE_REPO), count=len(facts)))
    return 0


def _tmp_doc(content, name="doc.md"):
    """A temp doc for selftests (tempfile + atexit cleanup; parallel-safe path)."""
    import atexit  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    p = os.path.join(d, name)
    open(p, "w", encoding="utf-8").write(content)
    return p


CASES = [
    # (3) Empty input must be reported (the guard's decision wiring is proven in
    #    zreflect/guard.py's selftest; the drop / rewrite pure functions live in
    #    ledger.py's selftest -- each in its own home)
    ("★ facts.check_doc_no_markers",
     lambda: check_doc(_tmp_doc("empty document\n"), {"facts": {"a": 1}}) == 2),
    ("★ facts.check_doc_file_missing",
     lambda: check_doc(os.path.join(_tmp_doc("", "x.md"), "..",
                                    "no_such_%d.md" % os.getpid()),
                       {"facts": {"a": 1}}) == 2),
    # (2) Human-readable fact age (issue #3 (2))
    ("facts.age_unrecorded",
     lambda: _age_human({"value": 1}).code == "facts.age.unrecorded"),
    ("facts.age_today",
     lambda: _age_human({"measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}).code
     == "facts.age.today"),
    # (4) The official read-only exit (issue #4 (4))
    ("facts.get_dict_shape",
     lambda: get_value({"facts": {"n": {"value": 12, "cmd": "c"}}}, "n") == (True, 12)),
    ("facts.get_bare_shape",
     lambda: get_value({"facts": {"n": 7}}, "n") == (True, 7)),
    ("★ facts.get_unknown_key",
     lambda: get_value({"facts": {"n": 1}}, "zzz")[0] is False),
    # **Unknown commands must not fall back to measure** (observed: `facts.py --help`
    # once "measured once and wrote the ledger"). `measure` is a **real write** path
    # -- using it as a fallback means every mistyped command rewrites the ledger.
    ("★ facts.unknown_command_is_2", lambda: _unknown_cmd_rc() == 2),
    # Empty-input tier: `--help` is the onboarding surface; must be rc=0 and **must
    # not land on measure** (no ledger write).
    ("★ facts.help_is_not_a_measure",
     lambda: _help_rc() == 0 and not _is_unknown_cmd("--help")),
    # Converse: `--allow-drop` / `--accept-changes` are **measure modifiers**, not
    # commands. The guard above used to classify them as unknown => the only exit
    # that advances the ledger broke (observed).
    ("★ facts.measure_modifiers_route_to_measure",
     lambda: not _is_unknown_cmd("--accept-changes=k1")),
    # **Bootstrap end-to-end convergence**: `--init` -> measure -> two renders ->
    # registry all green.
    ("★ facts.fresh_repo_bootstraps_green", lambda: _fresh_bootstraps()),
    ("★ facts.private_phase_gate_not_copied",
     lambda: _private_phase_gate_not_copied()),
    # **Real-project shape**: a repo with build.sh / src / an existing README must
    # also complete the run. There was a time when "any .sh in the repo => the whole
    # chain FATAL"; this is that regression's guard.
    ("★ facts.real_repo_shaped_bootstraps", lambda: _real_repo_shaped()),
    # **The opt-out also applies to --check / --render-doc** (#27(2)): a repo with
    # `REFLECT_NO_PRINCIPLES=1` must not be blocked by FATAL `doc_missing_check` --
    # the same opt-out behaved differently in doc.accepts_principles (honored) vs
    # _doc_names/_block_homes (formerly not), exactly the "one rule, two sources"
    # shape (downstream observed: pre-push always red).
    ("★ facts.no_principles_opt_out_respected", lambda: _opt_out_check_case()),
    # **A corrupt ledger is a configuration accident, not a red criterion**: must be
    # FATAL rc=2. Observed: a `{ broken` FACTS.json made `--check` print a traceback
    # with rc=0 (the caller believed the check ran), and made gates rc=1 (recorded as
    # "criterion red" in `registry --run` -- users would go fix gates instead of data).
    ("★ facts.corrupt_ledger_is_fatal_not_traceback",
     lambda: _corrupt_ledger_rc() == 2),
    ("★ ledger.corrupt_load_raises_typed",
     lambda: _corrupt_load_raises()),
    # **Environment accidents are always FATAL rc=2**: doc with invalid encoding /
    # unwritable / corrupt ledger -- what they share is "not a content problem".
    # All used to be raw tracebacks + rc=1, and rc=1 is recorded as "criterion red"
    # in `registry --run` (a completely different fix).
    ("★ facts.unwritable_doc_is_fatal",
     lambda: _unwritable_doc_rc() == 2),
]


def _cases_block_homes():
    """`block_homes` ownership map covers the configured doc names."""
    homes, err = block_homes({"facts": {"a": {"value": 1, "cmd": "c"}}})
    return err is None and isinstance(homes, list) and len(homes) >= 1


def _tampered_seal_measure_rc():
    """Tampered core under SEAL.json makes `facts.py` fail FATAL rc=2."""
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
        _copy_suite_into(d)
        p = os.path.join(d, "zreflect", "knobs.py")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\n")
        return subprocess.run(
            [sys.executable, "zreflect/facts.py", "--accept-changes"],
            cwd=d, env=fixture_env(), capture_output=True, text=True,
            timeout=180, encoding="utf-8", errors="replace").returncode
    except Exception:                                    # noqa: BLE001
        return None
    finally:
        shutil.rmtree(d, True)


CASES.append(("facts.block_homes_present", lambda: _cases_block_homes()))
CASES.append(("★ facts.tampered_seal_is_fatal", lambda: _tampered_seal_measure_rc() == 2))


# The command table is built at the **end of the file**: handlers are defined above,
# and the literals must wait until they exist (evaluating at the top = NameError --
# observed).
_COMMANDS.update({
    "--render": cmd_render,
    "--render-doc": cmd_render_doc,
    "--check": cmd_check,
    "--get": cmd_get,
    "--init": cmd_init,
    "--accept": cmd_accept,
    "show": cmd_show,
    "--count": cmd_count,
})


def _unknown_cmd_rc():
    """rc for an unknown command (`--definitely-not-a-command`)."""
    import contextlib  # noqa: PLC0415
    import io  # noqa: PLC0415
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return main(["--definitely-not-a-command"])


def _help_rc():
    import contextlib  # noqa: PLC0415
    import io  # noqa: PLC0415
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return main(["--help"])


def _is_unknown_cmd(first):
    """Would this first arg land on the "unknown command" branch?

    Delegates to the pure `_classify`, so selftests can assert the dispatch
    decision without executing a command. Selftests must be side-effect free:
    calling `main([first])` here would run `measure()` for `--accept-changes*`
    and write the caller's ledger.
    """
    return _classify([first]) == "unknown"


def _copy_suite_into(d):
    """Copy built-in gates, declared modules, `SEAL.json`, language packs, and hook roster into `d`."""
    import shutil  # noqa: PLC0415
    src_z = gate.zdir()
    dst_z = os.path.join(d, "zreflect")
    os.makedirs(dst_z)
    _gs, _missing = registry.gates(src_z)
    mods, _missing2 = registry.modules(src_z)
    builtin = set(registry.BUILTIN_PHASES)
    roster = sorted(
        {os.path.basename(g["file"]) for g in _gs
         if (g.get("runs_at") or "commit") in builtin}
        | {os.path.basename(m["file"]) for m in mods})
    for rel in roster:
        src = os.path.join(src_z, rel)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(dst_z, rel))
    sp = os.path.join(src_z, "SEAL.json")
    if os.path.isfile(sp):
        shutil.copy(sp, os.path.join(dst_z, "SEAL.json"))
    lang_src = os.path.join(src_z, "lang")
    if os.path.isdir(lang_src):
        for n in sorted(os.listdir(lang_src)):
            pkg = os.path.join(lang_src, n)
            if os.path.isdir(pkg) and any(x.endswith(".json")
                                          for x in os.listdir(pkg)):
                shutil.copytree(pkg, os.path.join(dst_z, "lang", n))
    _copy_hooks_roster(src_z, d)
    ruff_conf = os.path.join(gate.tool_repo(), "ruff.toml")
    if os.path.isfile(ruff_conf):
        shutil.copy(ruff_conf, d)


def _copy_hooks_roster(src_z, d):
    """Copy the hook platform files."""
    import shutil  # noqa: PLC0415
    hooks_src = os.path.join(os.path.dirname(src_z), "reflect-hooks")
    if not os.path.isdir(hooks_src):
        return
    os.makedirs(os.path.join(d, "reflect-hooks"))
    for name in sorted(os.listdir(hooks_src)):
        src = os.path.join(hooks_src, name)
        if (os.path.isfile(src) and not name.startswith(".")
                and not name.endswith((".pyc", ".mypy_cache"))):
            shutil.copy(src, os.path.join(d, "reflect-hooks", name))


def fixture_env(extra=None):
    """Environment for a fixture subprocess: no inherited knobs, **and no GATE_REPO**.

    `harness` sets `GATE_REPO` to *this* repo when it runs selftests, while a
    fixture is a *different* repo; leaving it in makes the child audit this repo
    instead of the fixture. One source, so the environment cannot drift.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("REFLECT_") and k != "GATE_REPO"}
    if extra:
        env.update(extra)
    return env


def _corrupt_ledger_rc():
    """`--check`'s rc under a corrupt ledger (fixture repo; this repo's ledger untouched)."""
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
        _copy_suite_into(d)
        open(os.path.join(d, "FACTS.json"), "w", encoding="utf-8").write("{ broken")
        env = fixture_env()
        p = subprocess.run(
            [sys.executable, os.path.join(d, "zreflect", "facts.py"), "--check"],
            cwd=d, env=env, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
        return p.returncode
    except Exception:                                    # noqa: BLE001
        return None
    finally:
        shutil.rmtree(d, True)


def _unwritable_doc_rc():
    """`--render-doc`'s rc on a read-only doc (needs a real write => must be FATAL 2)."""
    import shutil  # noqa: PLC0415
    import stat  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
        subprocess.run(["git", "-C", d, "config", "user.email", "a@b"], check=True)
        subprocess.run(["git", "-C", d, "config", "user.name", "a"], check=True)
        _copy_suite_into(d)
        env = fixture_env({"GATE_REPO": d})

        def run(*args):
            return subprocess.run([sys.executable, *args], cwd=d, env=env,
                                  capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")

        run("zreflect/facts.py", "--init")
        run("zreflect/facts.py", "--accept-changes")
        run("zreflect/facts.py", "--render-doc")
        # Make the doc need a write again: change one value in the ledger.
        run("zreflect/facts.py", "--accept", "probe", "9", "echo 9", "s")
        doc = os.path.join(d, "STATE.md")
        os.chmod(doc, stat.S_IRUSR)
        try:
            return run("zreflect/facts.py", "--render-doc").returncode
        finally:
            os.chmod(doc, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:                                    # noqa: BLE001
        return None
    finally:
        shutil.rmtree(d, True)


def _corrupt_load_raises():
    """`ledger.load_or_fatal` exits rc=2 on bad JSON (not a bare `JSONDecodeError`)."""
    import tempfile  # noqa: PLC0415

    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("{ broken")
        try:
            load_or_fatal(path)
        except SystemExit as e:
            return e.code == 2
        except Exception:                                # noqa: BLE001
            return False
        return False
    finally:
        os.unlink(path)


def _bootstrap_steps():
    """Steps to run after `--init` (`(argv, whether to apply env)`)."""
    return [
        ([sys.executable, "zreflect/facts.py", "--accept-changes"], True),
        ([sys.executable, "zreflect/facts.py", "--render-doc"], True),
        ([sys.executable, "zreflect/registry.py", "--run", "commit"], True),
    ]


def _private_phase_gate_not_copied():
    """A private-phase gate must not enter a fixture (issue #37).

    The red-test shape: a file declaring `GATE = meta(..., runs_at="lab")` IS
    collected by discovery, but copying it drags a gate whose enabling knob
    (REFLECT_PHASES) lives in the env file #34 excluded -- gate present, its
    living condition absent => `registry.unknown_phase` FATAL. Three tiers:
    (a) every GATE declaration in the fixture declares a built-in phase (the
    filter is the phase, not "copy nothing" -- parsed by AST, so literals in
    comments/docstrings do not count); (b) built-in-phase gates and platform
    modules ARE copied (the copy happened); (c) this repo itself keeps its
    own files untouched (filter, not deletion).
    """
    import ast  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    builtin = ("commit", "start-of-work")
    d = tempfile.mkdtemp()
    try:
        _copy_suite_into(d)
        fixture_z = os.path.join(d, "zreflect")
        for f in sorted(os.listdir(fixture_z)):
            if not f.endswith(".py"):
                continue
            tree = ast.parse(open(os.path.join(fixture_z, f),
                                  encoding="utf-8", errors="replace").read())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "meta"):
                    continue
                kw = {k.arg: k.value for k in node.keywords}
                runs = kw.get("runs_at")
                if isinstance(runs, ast.Constant) and runs.value not in builtin:
                    return False                 # (a) non-built-in phase copied
        has_platform = (os.path.isfile(os.path.join(fixture_z, "gate.py"))
                        and os.path.isfile(os.path.join(fixture_z,
                                                        "check_facts.py")))
        repo_z = gate.zdir()
        return (has_platform                          # (b) copy did happen
                and os.path.isfile(os.path.join(repo_z, "gate.py")))  # (c) kept
    finally:
        shutil.rmtree(d, True)


def _real_repo_shaped():
    """Bootstrap succeeds on a real-project repo containing `.sh`, `src/`, bad code, and `README.md`."""
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True,
                       capture_output=True)
        _copy_suite_into(d)
        for name in ("build.sh", "deploy.sh"):
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\necho %s\n" % name)
        os.makedirs(os.path.join(d, "src"))
        with open(os.path.join(d, "src", "app.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("def f():\n    return 1\n")
        os.makedirs(os.path.join(d, "examples"))
        bad_body = ("import os\n\n\ndef f():\n    print(%r)\n"
                    % "".join(chr(c) for c in (0x8FD9, 0x6761, 0x4E2D, 0x6587)))
        with open(os.path.join(d, "examples", "bad.py"), "w",
                  encoding="utf-8") as fh:
            fh.write(bad_body)
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("# my project\n\nNo machine block here.\n")
        base = fixture_env()
        subprocess.run([sys.executable, "zreflect/facts.py", "--init"],
                       cwd=d, env=base, capture_output=True, text=True,
                       timeout=180,
                           encoding="utf-8", errors="replace")
        for argv in ([sys.executable, "zreflect/facts.py", "--accept-changes"],
                     [sys.executable, "zreflect/facts.py", "--render-doc"]):
            p = subprocess.run(argv, cwd=d, env=base,
                               capture_output=True, text=True, timeout=180,
                               encoding="utf-8", errors="replace")
            if p.returncode != 0:
                return False
        p = subprocess.run([sys.executable, "zreflect/registry.py",
                            "--run", "commit"],
                           cwd=d, env=base,
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0
    except Exception:                                    # noqa: BLE001
        return False
    finally:
        shutil.rmtree(d, True)


def _opt_out_check_case():
    """With `REFLECT_NO_PRINCIPLES=1`, `--check` ignores missing `PRINCIPLES.md`."""
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
        _copy_suite_into(d)
        base = fixture_env()
        subprocess.run([sys.executable, "zreflect/facts.py", "--init"],
                       cwd=d, env=base, capture_output=True, timeout=180)
        for argv in ([sys.executable, "zreflect/facts.py", "--accept-changes"],
                     [sys.executable, "zreflect/facts.py", "--render-doc"]):
            subprocess.run(argv, cwd=d, env=base, capture_output=True,
                           timeout=180)
        os.remove(os.path.join(d, "PRINCIPLES.md"))
        env_opt = dict(base)
        env_opt["REFLECT_NO_PRINCIPLES"] = "1"
        p = subprocess.run([sys.executable, "zreflect/facts.py", "--check"],
                           cwd=d, env=env_opt, capture_output=True, text=True,
                           timeout=180, encoding="utf-8", errors="replace")
        return p.returncode == 0 and "PRINCIPLES" not in (p.stdout + p.stderr)
    except Exception:                                    # noqa: BLE001
        return False
    finally:
        shutil.rmtree(d, True)


def _fresh_bootstraps():
    """A brand-new repo: `--init` -> measure -> render -> `registry --run commit` all green."""
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", d], check=True,
                       capture_output=True)
        _copy_suite_into(d)
        base = fixture_env()
        subprocess.run([sys.executable, "zreflect/facts.py", "--init"],
                       cwd=d, env=base, capture_output=True, text=True,
                       timeout=180,
                           encoding="utf-8", errors="replace")
        for argv, _with_env in _bootstrap_steps():
            p = subprocess.run(argv, cwd=d, env=base, capture_output=True,
                               text=True, timeout=180,
                               encoding="utf-8", errors="replace")
            if p.returncode != 0:
                return False
        return True
    except Exception:                                    # noqa: BLE001
        return False
    finally:
        shutil.rmtree(d, True)


MODULE = module_meta("ledger CLI", "measure / render / --get / the two guards", selftest=True)


if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], M("gate.title.facts_cli"),
                              CASES, main))



