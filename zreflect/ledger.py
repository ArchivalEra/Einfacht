#!/usr/bin/env python3
"""Facts ledger data layer, write guards, and machine-block rendering.

Combines pure ledger storage (`load`, `fact`, `changed_keys`, `dropped_keys`),
write-guard decisions (`decide`, `accepted_keys`, `write_target_problems`), and
`AUTO:FACTS` block rendering (`render_block`, `body_of`, `prose_of`).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from gate import fatal_exit, machine, module_meta  # noqa: E402
from i18n import M  # noqa: E402

BLOCK_BEGIN = "<!-- AUTO:FACTS -->"
BLOCK_END = "<!-- /AUTO:FACTS -->"

# PINNED: AUTO machine block fixed language (does not follow REFLECT_LANG).
PREAMBLE = [
    ("> This block is rendered by `zreflect/facts.py --render-doc` from"
     " `FACTS.json`; **do not edit by hand**"
     " (pre-commit recomputes and `git add`s it)."),
    ("> 'Measured numbers' in the prose are produced only here: to cite one, write"
     " `[[key]]`; never copy the number by hand."),
]


class Unreadable(RuntimeError):
    """The ledger file exists but can't be read (bad JSON / permissions / encoding)."""


def load(path):
    """Read JSON from `path`; bad JSON / permissions / encoding raise `Unreadable`."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, UnicodeError, ValueError) as e:
        raise Unreadable(path, e) from e


def load_or_fatal(path):
    """Read the ledger; broken file -> FATAL rc=2 (`SystemExit(2)`)."""
    try:
        return load(path)
    except Unreadable as e:
        cause = e.args[1] if len(e.args) > 1 else e
        print(machine().emit("fatal", M("ledger.unreadable_gate",
                                        name=path, error=cause)),
              file=sys.stderr)
        raise SystemExit(2) from e


def facts_of(ledger):
    """The facts table inside a ledger (tolerates wrapped doc or bare table)."""
    led = ledger or {}
    return led.get("facts") if isinstance(led, dict) and "facts" in led else (led or {})


def dropped_keys(old_facts, new_facts):
    """Which keys this re-measurement would drop."""
    return sorted(set(old_facts or {}) - set(new_facts or {}))


def value_of(entry):
    """A fact's value (tolerates both dict shape and bare-value shape)."""
    return entry.get("value") if isinstance(entry, dict) else entry


def short_value(v, n=24):
    """Shrink a value to one line (64-char sha keeps its first 16)."""
    s = v if isinstance(v, str) else str(v)
    if len(s) == 64:
        return s[:16] + "..."
    return s if len(s) <= n else s[:n] + "..."


_PROTECTED = ("value", "cmd", "calibrate", "calibrate_expect")


def _entry_val(entry, fld):
    """Field value for `fld`, treating bare values as `value`."""
    if not isinstance(entry, dict):
        return entry if fld == "value" else None
    return entry.get(fld)


def _first_diff(old_e, new_e):
    """Return `(old, new)` for the first differing protected field, else `None`."""
    for fld in _PROTECTED:
        o, n = _entry_val(old_e, fld), _entry_val(new_e, fld)
        if o != n:
            return (o, n) if fld == "value" else (f"{fld}:{o}", f"{fld}:{n}")
    return None


def changed_keys(old_facts, new_facts):
    """Which keys' protected fields (`value`, `cmd`, `calibrate`, `calibrate_expect`) changed."""
    olds = old_facts or {}
    out = []
    for k, nv in sorted((new_facts or {}).items()):
        if k not in olds:
            continue
        diff = _first_diff(olds[k], nv)
        if diff is not None:
            out.append((k, diff[0], diff[1]))
    return out


def fact(value, cmd, source, note="",
         calibrate=None, calibrate_expect=None, kind="value"):
    """Build one ledger fact (`value` + replay `cmd` + `source`, paired `calibrate`/`calibrate_expect`)."""
    _require_pairs((calibrate, calibrate_expect, "calibrate"))
    d = {"value": value, "cmd": cmd, "source": source,
         "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
         "first_seen": time.strftime("%Y-%m-%d")}
    _fill_optional(d, note, calibrate, calibrate_expect, kind)
    return d


def _require_pairs(*pairs):
    """Paired parameters must be given together; one alone fails FATAL."""
    for a, b, name in pairs:
        if (a is None) != (b is None):
            fatal_exit(M("ledger.shape_incomplete", name=name))


def _fill_optional(d, note, calibrate, calibrate_expect, kind):
    """Fill optional fields into `d` only when given."""
    if note:
        d["note"] = note
    if calibrate is not None:
        d["calibrate"] = calibrate
        d["calibrate_expect"] = calibrate_expect
    if kind != "value":
        d["kind"] = kind


def age_days(entry):
    """Days since this fact's `measured_at` timestamp (missing/invalid => `None`)."""
    ts = entry.get("measured_at") if isinstance(entry, dict) else None
    if not ts:
        return None
    try:
        when = datetime.strptime(str(ts), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - when).total_seconds() / 86400.0


def _gitignored(path):
    """Is `path` covered by `.gitignore`; non-git repo / git absent => `None`."""
    import subprocess  # noqa: PLC0415
    try:
        r = subprocess.run(["git", "-C", gate.GATE_REPO, "check-ignore", "-q", path],
                           capture_output=True)
    except OSError:
        return None
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None


def write_target_problems(path, ignored=None):
    """Check whether ledger write target `path` is gitignored (`(fatal, warn)`)."""
    ig = _gitignored(path) if ignored is None else ignored
    if ig is True:
        return M("guard.write_target_gitignored", path=path), None
    if ig is None:
        return None, M("guard.write_target_no_git")
    return None, None


def accepted_keys(argv):
    """Parse `--accept-changes[=k1,k2]`: bare => `None`, list => `set`, absent => `False`."""
    for a in argv or []:
        if a == "--accept-changes":
            return None
        if a.startswith("--accept-changes="):
            raw = a.split("=", 1)[1].strip()
            return {k.strip() for k in raw.split(",") if k.strip()}
    return False


def _filter_accepted(changed, accepted):
    """Filter `changed` down to entries not covered by `accepted`."""
    if accepted is None:
        return []
    if accepted is False:
        return list(changed or [])
    return [c for c in (changed or []) if c[0] not in accepted]


def _drop_verdict(old_facts, new_facts, allow_drop, notes):
    """Guard one: dropped entries (keys vanished)."""
    dropped = dropped_keys(old_facts, new_facts)
    if not dropped:
        return [], False
    if not allow_drop:
        return [M("guard.refuse_dropped", count=len(dropped),
                  keys=", ".join(dropped)),
                M("guard.refuse_dropped_advice")], True
    notes["err"].append(M("guard.note_allow_drop", count=len(dropped),
                          keys=", ".join(dropped)))
    return [], False


def _change_verdict(old_facts, new_facts, accepted, notes):
    """Guard two: changed values/commands."""
    changed = changed_keys(old_facts, new_facts)
    remaining = _filter_accepted(changed, accepted)
    if remaining:
        problems = [M("guard.refuse_changed", count=len(remaining))]
        problems += [M("guard.changed_row", key=k, before=short_value(o),
                       after=short_value(n)) for k, o, n in remaining]
        if accepted:
            problems.append(M("guard.accepted_boundary",
                              accepted=len(changed) - len(remaining),
                              keys=", ".join(sorted(accepted))))
        problems.append(M("guard.refuse_changed_advice"))
        return problems, True
    if changed:
        notes["out"].append(M("guard.note_accept_changes", count=len(changed)))
        notes["out"] += [M("guard.changed_row", key=k, before=short_value(o),
                           after=short_value(n)) for k, o, n in changed]
    return [], False


def decide(old_facts, new_facts, accepted=False, allow_drop=False):
    """Decide whether a re-measurement may write to disk (`(verdict, problems, notes)`)."""
    notes = {"err": [], "out": []}
    problems, refused = _drop_verdict(old_facts, new_facts, allow_drop, notes)
    if refused:
        return "refuse", problems, notes
    problems, refused = _change_verdict(old_facts, new_facts, accepted, notes)
    if refused:
        return "refuse", problems, notes
    if not new_facts:
        return "refuse", [M("guard.empty_ledger")], notes
    return "write", problems, notes


def _fmt(v):
    if isinstance(v, str) and len(v) == 64:
        return "`%s...`" % v[:16]
    return "**%s**" % (v if isinstance(v, str) else str(v))


def render_block(ledger):
    """Render `ledger` into an `AUTO:FACTS` machine block (PINNED fixed language)."""
    f = facts_of(ledger)
    lines = [BLOCK_BEGIN] + list(PREAMBLE) + [""]
    if not f:
        lines += [("**The ledger is empty** -- not a single fact. Empty is not"
                   " \"pass\": first check whether measure() is broken."), ""]
    else:
        lines += ["| key | value | measured at | replay cmd |", "|---|---|---|---|"]
        for k in sorted(f):
            e = f[k] if isinstance(f[k], dict) else {"value": f[k]}
            lines.append("| `%s` | %s | %s | `%s` |"
                         % (k, _fmt(e.get("value")), e.get("measured_at", "--"),
                            e.get("cmd", "?")))
        lines += ["", "%d facts." % len(f)]
    lines.append(BLOCK_END)
    return "\n".join(lines)


def body_of(block):
    """Extract the body inside `BLOCK_BEGIN` / `BLOCK_END`."""
    if BLOCK_BEGIN not in block:
        return ""
    return block.split(BLOCK_BEGIN, 1)[1].split(BLOCK_END, 1)[0]


def prose_of(doc_text):
    """Return document prose with all `<!-- AUTO:... -->...<!-- /AUTO:... -->` blocks stripped."""
    out, i = [], 0
    while True:
        b = doc_text.find("<!-- AUTO:", i)
        if b < 0:
            out.append(doc_text[i:])
            break
        out.append(doc_text[i:b])
        e = doc_text.find("-->", b + len("<!-- AUTO:"))
        end = doc_text.find("<!-- /AUTO:", e) if e >= 0 else -1
        if end < 0:
            out.append(doc_text[b:])
            break
        close = doc_text.find("-->", end)
        i = close + 3 if close >= 0 else len(doc_text)
    return "".join(out)


def _extra_lines(block):
    return [ln for ln in body_of(block).splitlines()
            if ln.strip() and ln not in PREAMBLE]


def _cases_guards():
    """Dropped-entry and changed-value pure function cases."""
    from gate import raises  # noqa: PLC0415
    return [
        ("ledger.dropped_clean",
         lambda: dropped_keys({"a": 1}, {"a": 1, "c": 3}) == []),
        ("ledger.changed_clean",
         lambda: changed_keys({"a": {"value": 1}}, {"a": {"value": 1}}) == []),
        ("ledger.changed_note_only",
         lambda: changed_keys({"a": {"value": 1, "note": "old"}},
                              {"a": {"value": 1, "note": "new"}}) == []),
        ("★ ledger.changed_cmd_protected",
         lambda: changed_keys({"a": {"value": 1, "cmd": "old"}},
                              {"a": {"value": 1, "cmd": "new"}})
         == [("a", "cmd:old", "cmd:new")]
         and changed_keys({"a": {"value": 1, "calibrate": "old"}},
                          {"a": {"value": 1, "calibrate": "new"}})
         == [("a", "calibrate:old", "calibrate:new")]
         and changed_keys({"a": {"value": 1, "calibrate_expect": "old"}},
                          {"a": {"value": 1, "calibrate_expect": "new"}})
         == [("a", "calibrate_expect:old", "calibrate_expect:new")]),
        ("\u2605 ledger.dropped_keys",
         lambda: dropped_keys({"a": 1, "b": 2}, {"a": 1}) == ["b"]),
        ("\u2605 ledger.changed_keys",
         lambda: changed_keys({"a": {"value": 1}}, {"a": {"value": 2}})
         == [("a", 1, 2)]),
        ("ledger.first_run_dropped_silent",
         lambda: dropped_keys({}, {"a": 1}) == []),
        ("ledger.first_run_changed_silent",
         lambda: changed_keys({}, {"a": {"value": 1}}) == []),
        ("ledger.raises_detects",
         lambda: raises(lambda: (_ for _ in ()).throw(SystemExit(2)))),
    ]


def _cases_shapes():
    """Ledger shape helper cases (`facts_of`, `short_value`, `value_of`)."""
    return [
        ("ledger.facts_of_both_shapes",
         lambda: facts_of({"facts": {"a": 1}}) == {"a": 1}
         and facts_of({"a": 1}) == {"a": 1}),
        ("ledger.short_value_sha",
         lambda: short_value("a" * 64) == "a" * 16 + "..."),
        ("ledger.value_of_both_shapes",
         lambda: value_of({"value": 3}) == 3 and value_of(7) == 7),
    ]


def _cases_measurement():
    """Fact age and `first_seen` cases."""
    return [
        ("ledger.fact_stamps_measured_at",
         lambda: isinstance(fact(1, "c", "s").get("measured_at"), str)),
        ("ledger.age_days_missing_none", lambda: age_days({"value": 1}) is None),
        ("ledger.age_days_bad_stamp_none",
         lambda: age_days({"measured_at": "not-a-time"}) is None),
        ("ledger.age_days_fresh",
         lambda: 0 <= age_days({"measured_at": time.strftime(
             "%Y-%m-%dT%H:%M:%S%z")}) < 1),
        ("ledger.age_days_about_40",
         lambda: 39 < age_days({"measured_at": (
             datetime.now(timezone.utc) - timedelta(days=40)
         ).strftime("%Y-%m-%dT%H:%M:%S%z")}) < 41),
        ("ledger.fact_stamps_first_seen",
         lambda: fact(1, "c", "s").get("first_seen")
         == time.strftime("%Y-%m-%d")),
    ]


def _cases_probes():
    """Instrument calibration pair cases."""
    from gate import raises  # noqa: PLC0415
    return [
        ("ledger.calibrate_fields",
         lambda: fact(1, "c", "s", calibrate="cal", calibrate_expect="e")
         .get("calibrate") == "cal"),
        ("\u2605 ledger.calibrate_only",
         lambda: raises(lambda: fact(1, "c", "s", calibrate="cal"))),
        ("\u2605 ledger.calibrate_expect_only",
         lambda: raises(lambda: fact(1, "c", "s", calibrate_expect="e"))),
    ]


def _cases_decide():
    """Write-guard `decide`, `accepted_keys`, and `write_target_problems` cases."""
    old = {"a": {"value": 1}, "b": {"value": 2}}
    same = {"a": {"value": 1}, "b": {"value": 2}}
    new_val = {"a": {"value": 1}, "b": {"value": 9}}
    dropped = {"a": {"value": 1}}
    return [
        ("guard.decide_clean",
         lambda: decide(old, same) == ("write", [], {"err": [], "out": []})),
        ("guard.decide_added_key_not_a_change",
         lambda: decide(old, dict(same, c={"value": 3}))[0] == "write"),
        ("guard.decide_note_only_not_a_change",
         lambda: decide({"a": {"value": 1, "note": "old"}},
                        {"a": {"value": 1, "note": "new"}})[0] == "write"),
        ("★ guard.refuse_cmd_changed",
         lambda: decide({"a": {"value": 1, "cmd": "old"}},
                        {"a": {"value": 1, "cmd": "new"}})[0] == "refuse"),
        ("★ guard.refuse_dropped",
         lambda: (lambda v, p, n: v == "refuse"
                  and p[0].code == "guard.refuse_dropped"
                  and "b" in p[0].params["keys"])(*decide(old, dropped))),
        ("★ guard.note_allow_drop",
         lambda: (lambda v, p, n: v == "write"
                  and n["err"][0].code == "guard.note_allow_drop"
                  and n["err"][0].params["keys"] == "b"
                  )(*decide(old, dropped, allow_drop=True))),
        ("★ guard.changed_row",
         lambda: (lambda v, p, n: v == "refuse"
                  and any(x.code == "guard.changed_row"
                          and x.params["before"] == "2"
                          and x.params["after"] == "9" for x in p)
                  )(*decide(old, new_val))),
        ("★ guard.note_accept_changes",
         lambda: (lambda v, p, n: v == "write"
                  and any(x.code == "guard.note_accept_changes" for x in n["out"])
                  )(*decide(old, new_val, accepted={"b"}))),
        ("★ guard.accept_changes_per_key",
         lambda: decide(old, new_val, accepted={"zzz"})[0] == "refuse"),
        ("★ guard.accepted_boundary",
         lambda: any(x.code == "guard.accepted_boundary" for x in decide(
             old, {"a": {"value": 8}, "b": {"value": 9}},
             accepted={"a"})[1])),
        ("★ guard.accept_changes_bare_flag",
         lambda: decide(old, new_val, accepted=None)[0] == "write"),
        ("guard.accepted_keys_bare",
         lambda: accepted_keys(["--accept-changes"]) is None),
        ("guard.accepted_keys_list",
         lambda: accepted_keys(["--accept-changes=a,b"]) == {"a", "b"}),
        ("guard.accepted_keys_absent",
         lambda: accepted_keys([]) is False),
        ("guard.accepted_keys_empty_set",
         lambda: accepted_keys(["--accept-changes="]) == set()),
        ("★ guard.empty_ledger",
         lambda: decide(old, {})[0] == "refuse"),
        ("★ guard.accepted_keys_empty_set_refuses",
         lambda: decide(old, new_val, accepted=set())[0] == "refuse"),
        ("guard.write_target_clean",
         lambda: write_target_problems("/x/FACTS.json", ignored=False) == (None, None)),
        ("★ guard.write_target_gitignored",
         lambda: write_target_problems("/x/FACTS.json", ignored=True)[0] is not None),
        ("guard.write_target_no_git",
         lambda: getattr(write_target_problems("/x/F.json", ignored=None)[1],
                         "code", None) == "guard.write_target_no_git"),
    ]


def _cases_render():
    """Machine-block rendering and prose-extraction cases."""
    full = {"facts": {"a": 4752, "s": {"value": "b" * 64, "cmd": "c"}}}
    header = next(ln for ln in body_of(render_block(full)).splitlines()
                  if ln.startswith("|"))
    return [
        ("render.keys_in_block",
         lambda: all(k in render_block(full) for k in ("a", "s"))),
        ("render.raw_value", lambda: "**4752**" in render_block(full)),
        ("render.sha_truncated", lambda: "`" + "b" * 16 + "...`" in render_block(full)),
        ("render.block_pure",
         lambda: render_block(full) == render_block(full)),
        ("render.prose_only_outside_block",
         lambda: (lambda d: ("body" in prose_of(d) and "tail" in prose_of(d)
                             and header not in prose_of(d) and header in d))(
             "body\n" + render_block(full) + "\ntail")),
        ("render.prose_fallback_whole_doc",
         lambda: prose_of("a document without markers") == "a document without markers"),
        ("render.prose_strips_all_blocks",
         lambda: (lambda d: ("sha256" not in prose_of(d)
                             and "GATES_TABLE" not in prose_of(d)
                             and "body" in prose_of(d) and "tail" in prose_of(d)))(
             "body\n<!-- AUTO:FACTS -->\nFACTS_TABLE\n<!-- /AUTO:FACTS -->\n"
             "<!-- AUTO:GATES -->\n| x | sha256 |\n<!-- /AUTO:GATES -->\ntail")),
        ("render.prose_nested_begin_literal",
         lambda: (lambda d: "awk" not in prose_of(d) and "tail" in prose_of(d))(
             "head\n<!-- AUTO:FACTS -->\ncmd: awk '<!-- AUTO:FACTS -->'\n"
             "<!-- /AUTO:FACTS -->\ntail")),
        ("★ render.block_not_constant",
         lambda: render_block(full) != render_block({"facts": {"a": 4752}})),
        ("★ render.empty_ledger_says_so",
         lambda: (lambda b: _extra_lines(b) != []
                  and not any(ln.lstrip().startswith("|")
                              for ln in body_of(b).splitlines()))(
             render_block({"facts": {}}))),
        ("★ render.empty_differs_from_full",
         lambda: render_block({"facts": {}}) != render_block(full)),
    ]


def _cases():
    """Assemble all ledger, guard, and render selftest groups."""
    return (_cases_guards() + _cases_shapes()
            + _cases_measurement() + _cases_probes()
            + _cases_decide() + _cases_render())


def _selftest():
    from gate import activate_or_fatal, selftest  # noqa: PLC0415
    rc = activate_or_fatal()
    if rc:
        return rc
    return selftest(M("gate.title.ledger"), _cases())


MODULE = module_meta("facts ledger",
                     "read/write + drop/change guards + AUTO:FACTS rendering", selftest=True)


if __name__ == "__main__":
    sys.exit(_selftest())
