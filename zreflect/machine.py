#!/usr/bin/env python3
"""Machine-line protocol: the **single source of "which line is a machine line"** (C1 + C4).

## The shape of the hole

A `^`-anchored criterion judges only the **first line**: a language-pack value
of `"context\nOFF: masquerading"` would be accepted, and once rendered the
`OFF:` stands as its own line that `run_phase` classifies as `off`.

Runtime data (filenames, document lines, exception text) fills template
placeholders `%s`, so a filename containing a newline can render a forged
machine line. **A language pack is a static asset (changing it goes through
code review); a filename is not.**

`s.splitlines()` recognizes **10** separators (`\n \r \x0b \x0c \x1c \x1d
\x1e \x85 U+2028 U+2029`) and does not recognize `\t \xa0 \u200b \ufeff`.
The defense must use the **same** line-splitting semantics, otherwise the
defense and the consumers each count lines their own way.

## interface

One table + two directions:

    Row(kind, grammar, frame)          # declaration: what this line kind looks like, how to emit it
    ROWS                               # all declarations (including the human tier)
    scan(text) -> tuple[(lineno, kind, line, was-neutralised)]   # consume: are there machine lines in this output
    emit(kind, body) -> str            # produce: emit a machine line (**guaranteed** only line 1 is a machine line)
    clean(text) -> (text', tuple)      # neutralise: break up forged lines in a **rendered result**
    reject(value) -> first forged line | None   # load time: does a language-pack value contain a forged line (broad table)

The two channels have **deliberately different** policies:

  - **Language packs** (static; the author fixes one word) => `reject`
    **loudly refuses**, FATAL rc 2. Uses the **broad table**: any
    `^[A-Z][A-Z0-9_]*:` counts as a reserved prefix (`OFF:` / `FATAL:` /
    `HTTP: 500` / `DNS: failed` ... the author can rephrase; it is not worth
    loosening the other side for that).
  - **Rendered output** (dynamic; the filename cannot be changed) => `clean`
    **neutralises only, never refuses**. Uses the **narrow table**: it breaks
    only shapes consumers **actually parse** (`OFF:` / `FATAL:` / the four
    self-proof prefixes / the machine summary). Things like `HTTP: 500` are
    not machine lines and must not be rewritten without cause.

## Why neutralisation uses a `\\` prefix instead of an error

A half-finished gate crashing because a **filename** contains a newline turns
something the author cannot control into an incident. `\\` is the only
character consumers cannot undo: `strip()` eats leading spaces, and a regex
`^` does not stop anchoring because of `\\`. The cost is the user seeing a
`\\OFF: x` -- which is **intentionally visible**: "this line tried to
masquerade as a machine line; I held it down". `clean` also **reports back**
the neutralised lines to the caller.

## Why `human` is its own tier

`=== ` lines come in two kinds: the machine summary `=== N PASS / M FAIL ===`
(grepped by `gates-selftest.sh`) and the human-readable summary
`=== gate.title.facts selftest: 18 PASS / 0 fail ===` (translatable). The two
grammars are **mutually exclusive** (verified item by item), so banning
`^===` wholesale would be wrong -- it would ban the legitimate human-readable
lines.

## Honest boundaries

  - Under `REFLECT_LANG` the **human-readable summary line** varies
    (translation), so the `human` tier judges shape per line, not content;
    the machine summary line is an emit-site literal and does not vary with
    language.
  - The shell side still holds **one** machine-summary shape:
    `reflect-hooks/einfacht-env.sh` (it must be shell -- hooks `source` it to
    export variables). What guards it is **not** regex reconciliation but
    `harness.run_plugins()`: it actually runs that script and reports
    `harness.no_machine_summary(file=...)` if the summary line's shape is
    wrong.
"""
from __future__ import annotations

import re
from typing import NamedTuple

# Every separator `str.splitlines()` recognizes. **Do not hand-write a near-copy**
# -- missing one opens a seam between this module and its consumers (measured:
# `\x1c` and `U+2029` are both real line separators).
LINE_BREAKS = ("\r\n", "\n", "\r", "\x0b", "\x0c",
               "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")


class Row(NamedTuple):
    """One kind of machine line: `grammar` judges the **whole line**, `frame` is the emit template."""
    kind: str
    grammar: str
    frame: str


# ⚠️ **Order is priority**: `machine_summary` must be tried before
# `human_summary` -- otherwise `=== 3 PASS / 0 FAIL ===` gets swallowed first
# by human's looser grammar (both grammars **can** match that line; their
# mutual exclusion is guaranteed jointly by the negative lookahead in human
# and this ordering).
ROWS = (
    Row("off",            r"^OFF:",                                     "OFF: %s"),
    Row("fatal",          r"^FATAL:",                                   "FATAL: %s"),
    Row("skip",           r"^SKIP:",                                    "SKIP: %s"),
    Row("down",           r"^DOWN: ",                                   "DOWN: %s"),
    Row("pass",           r"^PASS \| ",                                 "PASS | %s"),
    Row("fail",           r"^fail \| ",                                 "fail | %s"),
    Row("note",           r"^note \| ",                                 "note | %s"),
    Row("machine_summary",
        r"^=== [0-9]+ PASS / [0-9]+ FAIL ===$",                         "=== %d PASS / %d FAIL ==="),
    Row("human_summary",
        r"^=== (?!(?:[0-9]+ PASS / [0-9]+ FAIL) ===$).* ===$",          "=== %s ==="),
)

_KIND = {r.kind for r in ROWS}
_BY_KIND = {r.kind: r for r in ROWS}
# Kinds that can be emitted by filling one `body` via `%s`. `machine_summary`
# needs two integers and goes through `emit_summary` -- two entry points,
# because the parameter shapes genuinely differ (cramming them into one would
# degenerate into a runtime guess of "is the parameter a str or a tuple").
_EMITTABLE = _KIND - {"machine_summary"}

# Narrow table: shapes consumers **actually** parse. Only these get broken up
# in rendered output. `HTTP: 500` / `DNS: failed` / `README: see docs` are not
# in it -- no consumer parses them, and rewriting user-visible text for them
# is gilding the lily.
_SHARP = re.compile(r"^(?:"
                    r"OFF:|FATAL:|SKIP:|DOWN: |PASS \| |fail \| |note \| "
                    r"|=== [0-9]+ PASS / [0-9]+ FAIL ===$"
                    r")")

# Broad table: language-pack load time. Any capitalized word + colon counts as
# a reserved prefix (including `HTTP:`). Rationale: a language pack is
# **static** -- the author just rephrases; loosening this would let prefixes
# like `WARN:` / `ACHTUNG:` that "some consumer might parse someday" slip into
# packs unnoticed.
_BROAD = re.compile(r"^[A-Z][A-Z0-9_]*:")

# Neutralisation prefix. `\` is not eaten by `strip()` and not un-anchored by any `^`.
GUARD = "\\"

# Multi-line values **allowed** in language packs (measured: the continuation
# lines of the 3 existing legitimate multi-line values are all indented with
# spaces). This is not a whitelist; it only explains why per-line judging does
# not kill them -- not one of their lines starts with a machine shape.


def _body(part):
    """One chunk of `splitlines(keepends=True)` -> the body with **at most one** trailing separator removed.

    ⚠️ Do not use `rstrip(...)`: that would also strip a `\\x0b` **legitimately
    contained** in the body.
    """
    for sep in LINE_BREAKS:
        if part.endswith(sep):
            return part[:-len(sep)]
    return part


def _is_sharp(line):
    """Is this **entire line** a machine line consumers parse? (narrow table, for rendered output)"""
    return bool(_SHARP.match(line))


def _is_broad(line):
    """Does this **entire line** fall under a reserved prefix? (broad table, for language-pack load time)"""
    return bool(_BROAD.match(line))


def is_summary(line):
    """Is this whole line the **machine summary** (`=== N PASS / M FAIL ===`)?

    The `machine_summary` grammar in `ROWS` is the single source; consumers ask
    here instead of holding their own regex.
    """
    return re.match(_BY_KIND["machine_summary"].grammar, line) is not None


def scan(text, keepends=False):
    """Return the machine lines in `text`: `[(lineno, kind, line body)]`.

    Line splitting uses the same separators as `str.splitlines()`. With
    `keepends=False` (default) line bodies carry no trailing separator; with
    `keepends=True` separators are kept for reassembling the text.
    """
    out = []
    for i, part in enumerate((text or "").splitlines(keepends=True), 1):
        body = part if keepends else _body(part)
        kind = _kind_of(_body(part))
        if kind:
            out.append((i, kind, body))
    return tuple(out)


def _kind_of(line):
    """Which declared kind does this line belong to? Order is priority (see the comment above `ROWS`)."""
    for r in ROWS:
        if re.match(r.grammar, line):
            return r.kind
    return None


def emit(kind, body=""):
    """Emit one machine line. **Guarantees** that only the first line of the returned string is this `kind`; no other line is a machine line.

    This is the single source for the **producer** side: the prefix in `frame`
    is a literal, and nothing inside `body` may be allowed to forge another
    machine line.
    """
    if kind not in _EMITTABLE:
        raise KeyError("machine.emit_undeclared_kind(kind=%r, available=%r)"
                       % (kind, ", ".join(sorted(_EMITTABLE))))
    text = _BY_KIND[kind].frame % (body,)
    # Line 1 is the machine line we **want**; keep it. The extra lines the body
    # brought in get broken up as usual.
    cleaned, _hits = clean(text, preserve_first=True)
    return cleaned


def emit_summary(passed, failed):
    """The machine summary line (`=== N PASS / M FAIL ===`). The numbers must be integers."""
    if not isinstance(passed, int) or not isinstance(failed, int):
        raise TypeError("machine.emit_summary_needs_ints(passed=%r, failed=%r)"
                        % (passed, failed))
    return "=== %d PASS / %d FAIL ===" % (passed, failed)


def clean(text, kinds=None, preserve_first=False):
    """Break up forged machine lines in a rendered result. Returns
    `(neutralised text, neutralised lines)`.

    `kinds` restricts which tiers are broken; by default every shape in the
    narrow table is broken. With `preserve_first=True` the first line is kept
    verbatim (for `emit`, whose first line is the wanted machine line); the
    remaining lines are still neutralised.
    """
    parts = (text or "").splitlines(keepends=True)
    hits = []
    out = []
    for i, part in enumerate(parts, 1):
        body = _body(part)
        if not (preserve_first and i == 1) and _is_sharp(body):
            kind = _kind_of(body)
            if kinds is None or kind in kinds:
                out.append(GUARD + part)
                hits.append((i, kind, body))
                continue
        out.append(part)
    return "".join(out), tuple(hits)


def reject(value):
    """Load-time criterion for language-pack values: returns the first forged line
    `(lineno, line body)`, or None.

    Uses only the two explicit tables: `_BROAD` (any capitalized word + colon)
    and `_SHARP` (the narrow set consumers parse). Every line is checked, not
    only the first. `human_summary` (`=== ... ===`) is deliberately not judged:
    no consumer parses it, but a forged machine summary is in `_SHARP`.
    """
    for i, ln in enumerate((value or "").splitlines(), 1):
        if _is_broad(ln) or _is_sharp(ln):
            return i, ln
    return None


# -- Self-proof ----------------------------------------------------------------

def _try_reject(value):
    """`reject` must flag this value (used for reverse assertions)."""
    return reject(value) is not None


def _clean_has_no_row(value):
    """After neutralisation, no line is any longer a machine line consumers can parse."""
    cleaned, _hits = clean(value)
    return not any(_is_sharp(ln) for ln in cleaned.splitlines())


def _emit_is_single_row(kind, body):
    """The string from `emit`: line 1 is this kind; the remaining lines are not machine lines of any kind."""
    text = emit_summary(1, 0) if kind == "machine_summary" else emit(kind, body)
    rows = scan(text, keepends=True)
    return (len(rows) == 1 and rows[0][0] == 1 and rows[0][1] == kind)


def _packs_have_no_forgery():
    """Run the broad table over every value and line of the **real packs** (not fixtures) -- before the fix this was green on `"x\\nOFF: y"`."""
    import i18n  # noqa: PLC0415
    import knobs  # noqa: PLC0415
    bad = []
    # **Discovery based** (`knobs.installed_langs()`), not a hand-written
    # ("zh","en","de") -- a hand-written roster silently skips newly installed
    # language packs (C4: a hand-written roster always drifts).
    for lang in sorted(knobs.installed_langs()):
        try:
            table = i18n.load_pack(lang)
        except Exception as e:                           # noqa: BLE001
            return [("load_failed", lang, e)]
        for code, value in sorted(table.items()):
            hit = reject(value)
            if hit:
                bad.append((lang, code, hit[0], hit[1][:40]))
    return bad


# All ten real line separators, one by one -- skipping one in verification leaves a seam
_BREAKS = [("\n", "LF"), ("\r", "CR"), ("\x0b", "VT"), ("\x0c", "FF"),
           ("\x1c", "FS"), ("\x1d", "GS"), ("\x1e", "RS"), ("\x85", "NEL"),
           ("\u2028", "LS"), ("\u2029", "PS")]


def _cases_clean():
    """Clean prose and legitimate mentions must not be flagged."""
    return [
        ("machine.clean_text_is_untouched",
         lambda: clean("all fine here")[0] == "all fine here"),
        ("machine.legit_multiline_passes",
         lambda: reject("hint\n  set -a; . x; set +a") is None),
        ("machine.body_mention_is_fine",
         lambda: reject("`OFF:` is not a failure") is None),
        ("machine.human_summary_is_not_machine",
         lambda: reject("=== gate.title.facts selftest: 18 PASS / 0 fail ===")
         is None),
    ]


def _cases_forgery():
    """Four forgery classes: line breaks, broad prefixes, note prefix, summary."""
    per_sep = [("\u2605 machine.forgery_%s" % name,
                (lambda sep: lambda: _try_reject(
                    "ctx" + sep + "OFF: masquerading"))(sep))  # noqa: B023
               for sep, name in _BREAKS]
    return per_sep + [
        ("\u2605 machine.broad_prefix_reserved",
         lambda: _try_reject("HTTP: 500")),
        ("\u2605 machine.note_prefix",
         lambda: _try_reject("note | delegated")),
        ("\u2605 machine.machine_summary_is_machine",
         lambda: _try_reject("=== 9 PASS / 0 FAIL ===")),
    ]


def _cases_empty():
    """Empty-input guards: empty body, empty pack value, empty scan."""
    return [
        ("\u2605 machine.empty_body_keeps_the_row",
         lambda: emit("off", "") == "OFF: "),
        ("machine.empty_value_is_not_a_forgery",
         lambda: reject("") is None),
        ("\u2605 machine.empty_scan_reports_nothing",
         lambda: scan("") == ()),
    ]


def _cases_scrub():
    """Neutralisation guarantees: parameter injection, no collateral damage, idempotence."""
    return [
        ("\u2605 machine.param_filename_neutralised",
         lambda: _clean_has_no_row("evil\nOFF: gate not configured.py")),
        ("\u2605 machine.off_concat_neutralised",
         lambda: _clean_has_no_row("OFF: a\nOFF: b: cfg")),
        ("machine.narrow_does_not_touch_http",
         lambda: clean("HTTP: 500 upstream")[0] == "HTTP: 500 upstream"),
        ("\u2605 machine.guard_survives_strip",
         lambda: clean("OFF: x")[0].strip().startswith(GUARD)),
        ("machine.keeps_inner_separator_bytes",
         lambda: clean("a\x0bOFF: x")[0] == "a\x0b" + GUARD + "OFF: x"),
        ("machine.clean_is_idempotent",
         lambda: (lambda once: clean(once)[0] == once)(clean("OFF: x")[0])),
    ]


def _cases_emit():
    """Output guarantees: emit cannot create a second machine line; the summary line is exact; unknown kinds raise."""
    return [
        ("\u2605 machine.emit_single_row",
         lambda: _emit_is_single_row("fail", "x\nOFF: y")),
        ("\u2605 machine.emit_summary_exact",
         lambda: emit_summary(3, 0) == "=== 3 PASS / 0 FAIL ==="),
        ("\u2605 machine.emit_unknown_kind_raises",
         lambda: _emit_unknown_kind_raises()),
        # scan's line numbers and kinds must be accurate (consumers classify by them)
        ("machine.scan_reports_kind_and_line",
         lambda: scan("ok\nOFF: x\nok")[0][0] == 2
         and scan("ok\nOFF: x\nok")[0][1] == "off"),
    ]


def _cases():
    """Assemble the five selftest groups plus real-pack check."""
    return (_cases_clean() + _cases_forgery() + _cases_empty()
            + _cases_scrub() + _cases_emit()
            + [("\u2605 machine.real_packs_have_no_forgery",
                lambda: _packs_have_no_forgery() == [])])


def _emit_unknown_kind_raises():
    try:
        emit("bogus", "x")
        return False
    except KeyError:
        return True


def _selftest():
    import sys  # noqa: PLC0415

    # ⚠️ Suspended **inside a function**: `gate` imports this module at top
    # level (consumers of the machine-line protocol need it), so a module-level
    # `from gate import ...` would be circular. Same reason as `i18n.py`.
    from gate import main_selftest_or  # noqa: PLC0415
    from i18n import M  # noqa: PLC0415

    def _run(argv):
        # This module has no CLI: it is a pure function library. Running it as
        # a plain program => say explicitly how to self-prove.
        print(M("machine.no_cli"), file=sys.stderr)
        return 0
    return main_selftest_or(sys.argv[1:], M("gate.title.machine"),
                            _cases, _run)


# ⚠️ The declaration line **must be this literal shape** (`MODULE = module_meta(...)`) --
# `registry.modules()` is an ast parse, it does not execute code; writing
# `MODULE = _declare()` or putting it inside an `if` branch means it never gets
# collected (measured: registry.real_modules_declared goes red on the spot).
# The circularity is solved by **lazy imports** (see the comment on `_selftest`
# above), not by rewriting the declaration shape.
from gate import module_meta  # noqa: E402

MODULE = module_meta(
    "machine-line protocol",
    "the single source of \"which line is a machine line\": one table + scan/emit/clean/reject "
    "(produce, consume, language-pack loading, rendered-output neutralisation -- four paths share the same table)",
    selftest=True)

if __name__ == "__main__":
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import machine as _mod  # noqa: PLC0415
    sys.exit(_mod._selftest())

