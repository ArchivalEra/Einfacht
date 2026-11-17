#!/usr/bin/env python3
"""Comment discipline: **a comment is a claim the code could not make.**

Two modes, because the two answers are different questions and a repo may want
either:

    strict     any docstring at all is a report -- the function is supposed to be
               legible from its signature and body
    mismatch   a docstring **wider than its interface** is a report -- many
               paragraphs explaining few parameters means the explanation is
               about why the design is what it is, which is history, not contract

Under `mismatch`, `fact()` is the specimen that motivated this: nine parameters,
six paragraphs, 2908 characters. Nothing there explained how to call it; it
explained why a previous opt-out was removed. That belongs in `HISTORY.md`.

## Why a flag instead of one verdict

The strict reading ("code complex enough to need a comment is at odds with this
suite") is a real position and a harsh one: measured on this repo, 699 of 861
functions carry a docstring. `mismatch` is the same idea with a threshold, and it
catches 46. Whichever a repo adopts, adopting it must be a **declaration**, not
a default that surprises someone -- hence `REFLECT_COMMENTS`: `strict`, `off`
(the default), or unset for `off`.

## Why it is not simply "no comments"

Some docstrings are the interface: ordering constraints, error modes, the
contract a caller must know and cannot infer. Deleting those does not make the
code cleaner, it makes it guesswork. So the strict mode is offered, not imposed.
"""
from __future__ import annotations

import ast
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from gate import fatal, main_selftest_or, meta, module_meta, off  # noqa: E402
from i18n import M  # noqa: E402

MODES = ("strict", "mismatch")
DEFAULT_MODE = "off"
# `mismatch` = a docstring carrying more explanation than the code it explains.
# Measured on this repo: `doc >= 500 chars` on a body of `<= 20 lines` catches 33
# functions, and the ones it catches are the specimens -- `fact()` explains 2908
# characters over 59 lines, `module_meta` 592 over 12. A **ratio** was the first
# shape and it was wrong: a three-line function with a 150-character docstring
# scores 50 and is perfectly reasonable (the docstring is longer than the body
# because the body is trivial).
DOC_MAX_CHARS = 500
BODY_MAX_LINES = 20

# `--classify`: a docstring that recounts what a previous version did is
# **history**, not a contract. Measured on this repo: 61 of 111 over-long
# docstrings carry a temporal marker, 30 are public and carry none (a possible
# calling contract), and 20 are private and carry none -- those cannot be decided
# mechanically because nothing in the text says whether it explains "how to call
# me" or "why I exist".
#
# The point of three classes rather than a list: a hand-written list of "these
# need fixing" drifts, cannot be re-run, and hands the judgement to whoever reads
# it next. A classifier shrinks "111 to look at" into "N to decide", and N is
# recomputed on every run.
TEMPORAL = re.compile(
    r"(used to|first version|was wrong|no longer|had been|"
    r"\u4e0a\u4e00\u7248|\u539f\u6765|\u66fe\u662f|\u539f\u672c|"
    r"\u6b64\u524d|\u66fe\u7ecf|\u5f53\u65f6|observed)", re.I)
CLASSES = ("history", "contract", "undecided")


def classify(path, src, chosen="mismatch"):
    """Group over-long docstrings into `{class: [(file, line, name)]}`.

    `history` = carries a temporal marker (it recounts), `contract` = public and
    carries none (it may state a calling convention), `undecided` = private and
    carries none (nothing in the text says which it is).
    """
    out = {k: [] for k in CLASSES}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node) or ""
        if len(doc) < DOC_MAX_CHARS:
            continue
        after_doc = max((node.body[1].lineno if len(node.body) > 1
                         else (node.end_lineno or node.lineno)), node.lineno)
        body = (node.end_lineno or node.lineno) - after_doc + 1
        if body > BODY_MAX_LINES:
            continue
        if TEMPORAL.search(doc):
            out["history"].append((path, node.lineno, node.name))
        elif node.name.startswith("_"):
            out["undecided"].append((path, node.lineno, node.name))
        else:
            out["contract"].append((path, node.lineno, node.name))
    return out


def classify_tree(zdir=None):
    """Classify every file under `zdir`. Returns `(merged, functions_seen)`.

    `functions_seen` is the zero-value guard: if the classifier is broken and
    returns nothing at all, "0 undecided" is indistinguishable from "it never
    looked". Measured: replacing `classify()` with a constant empty result made
    `--classify` print all zeros and exit 0 -- the settlement criterion was
    blind to the classifier failing. A repo with zero functions is not a
    passing classification, it is an environment accident.
    """
    import os.path  # noqa: PLC0415
    base = zdir or gate.zdir()
    merged = {k: [] for k in CLASSES}
    seen = 0
    for name in sorted(os.listdir(base)):
        if not name.endswith(".py"):
            continue
        src = open(os.path.join(base, name), encoding="utf-8").read()
        seen += sum(1 for node in ast.walk(ast.parse(src))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for key, rows in classify(name, src).items():
            merged[key].extend(rows)
    return merged, seen


def mode():
    """The declared mode (`REFLECT_COMMENTS`, a value knob); empty/unset => `off`."""
    raw = os.environ.get("REFLECT_COMMENTS", "").strip().lower()
    return raw or DEFAULT_MODE


def function_reports(path, src, chosen):
    """Per-function reports for one source. `chosen` = "strict" | "mismatch"."""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node) or ""
        if not doc.strip():
            continue
        if chosen == "strict":
            out.append(M("comments.docstring_in_strict_mode",
                         file=path, line=node.lineno, name=node.name))
            continue
        # **Code** lines, not the whole block: `end_lineno - lineno` includes the
        # docstring itself, so a long docstring inflates the very number that is
        # supposed to measure how little code it explains (observed: a 12-line
        # rationale over `return a + b` measured 29 "body" lines and passed).
        after_doc = max((node.body[1].lineno if len(node.body) > 1
                         else (node.end_lineno or node.lineno)), node.lineno)
        body = (node.end_lineno or node.lineno) - after_doc + 1
        if len(doc) >= DOC_MAX_CHARS and body <= BODY_MAX_LINES:
            out.append(M("comments.docstring_wider_than_interface",
                         file=path, line=node.lineno, name=node.name,
                         chars=len(doc), body=body))
    return out


def problems(paths, chosen):
    """Every report across `[(name, source)]`. Pure function."""
    if chosen not in MODES:
        return [M("comments.bad_mode", mode=chosen, supported=", ".join(MODES))]
    return [p for name, src in paths
            for p in function_reports(name, src, chosen)]


def _classifier_has_teeth():
    """The classifier must still recognise a known history sample.

    Without this, deleting the body of `classify()` produces three empty groups
    and `--classify` exits 0 -- the settlement criterion would certify a broken
    classifier (measured). This is the same "a criterion must be able to go red"
    rule applied to the classifier itself.
    """
    sample = ('def f():\n    """Does the thing.\n\n'
              + "A sentence of rationale that runs on. " * 20 + "\n\n"
              + 'The first version returned None.\n    """\n    return 1\n')
    merged = classify("teeth.py", sample)
    return (len(merged["history"]) == 1
            and not merged["contract"] and not merged["undecided"])


def _print_classification(merged):
    """The `--classify` report: three groups, then the exit code the ticket names."""
    for key in CLASSES:
        rows = sorted(merged[key])
        print("%-10s %d" % (key, len(rows)))
        for path, line, name in rows:
            print("    %s:%d  %s" % (path, line, name))
    # rc: 0 = nothing left to decide, 1 = someone must rule on `undecided`.
    return 1 if merged["undecided"] else 0


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--classify" in argv:
        merged, seen = classify_tree()
        if seen == 0:
            return fatal(M("comments.classify_scanned_nothing"))
        if not _classifier_has_teeth():
            return fatal(M("comments.classifier_cannot_go_red"))
        if not any(merged.values()):
            # Nothing at all in scope is legitimate only when the suite really
            # has no over-long docstrings -- which is a *measured* state, not an
            # empty result from a broken classifier. Pin that with a selftest
            # case below rather than accepting it silently.
            print(M("comments.classify_empty_scope"))
        return _print_classification(merged)
    chosen = mode()
    if chosen == "off":
        return off(M("comments.off"))
    if chosen not in MODES:
        return fatal(M("comments.bad_mode", mode=chosen,
                       supported=", ".join(MODES)))
    paths = [(rel, open(os.path.join(gate.zdir(), rel), encoding="utf-8").read())
             for rel in sorted(os.listdir(gate.zdir()))
             if rel.endswith(".py")]
    probs = problems(paths, chosen)
    return gate.finish(M("comments.title"), probs,
                       M("comments.ok", mode=chosen, files=len(paths),
                         count=len(probs)))


def _hollow_classifier_case():
    """A classifier returning three empty groups must fail the red sample."""
    saved = globals()["classify"]
    try:
        globals()["classify"] = lambda *a, **k: {x: [] for x in CLASSES}
        return not _classifier_has_teeth()
    finally:
        globals()["classify"] = saved


def _classify_case():
    """One source with all three shapes must yield one row in each class."""
    filler = "".join("A sentence of rationale that runs on. " * 2 + "\n\n"
                     for _ in range(12))          # comfortably over DOC_MAX_CHARS
    hist = ('def pub():\n    """Does the thing.\n\n' + filler
            + 'The first version returned None.\n    """\n    return 1\n')
    contract = ('def pub2():\n    """Does the thing.\n\n' + filler
                + '"""\n    return 1\n')
    undecided = ('def _priv():\n    """Does the thing.\n\n' + filler
                 + '"""\n    return 1\n')
    merged = classify("x.py", hist + contract + undecided)
    return (len(merged["history"]) == 1 and len(merged["contract"]) == 1
            and len(merged["undecided"]) == 1)


def _cases():
    narrow = 'def f(a, b):\n    """Does the thing.\n\n    a: what a is.\n    b: what b is.\n    """\n'
    # >= 500 chars of docstring on a body of <= 20 lines: the shape this mode
    # rejects (design rationale where the code is trivially small)
    wide = ('def f(a, b):\n    """Does the thing.\n\n'
            + "".join("Rationale line %d of the design that used to be here.\n\n"
                      % i for i in range(12))
            + '    """\n    return a + b\n')
    plain = "def f(a, b):\n    return a + b\n"
    return [
        ("comments.off_by_default", lambda: mode() == "off"),
        # strict: any docstring is a report, including the narrow one
        ("★ comments.strict_reports_narrow",
         lambda: [p.code for p in problems([("x.py", narrow)], "strict")]
         == ["comments.docstring_in_strict_mode"]),
        ("comments.strict_ignores_bare_code",
         lambda: problems([("x.py", plain)], "strict") == []),
        # mismatch: the narrow one is a contract and passes
        ("comments.narrow_docstring_is_a_contract",
         lambda: problems([("x.py", narrow)], "mismatch") == []),
        ("★ comments.wide_docstring_is_history",
         lambda: [p.code for p in problems([("x.py", wide)], "mismatch")]
         == ["comments.docstring_wider_than_interface"]),
        # an unknown mode is a configuration error, not a silent pass
        ("★ comments.bad_mode_is_reported",
         lambda: [p.code for p in problems([("x.py", narrow)], "loud")]
         == ["comments.bad_mode"]),
        # --classify must separate the three kinds, not just count them: a
        # recounting docstring is history, a public one may be a contract, and a
        # private one carrying neither signal is what a human has to rule on.
        ("comments.classify_splits_three_ways",
         lambda: _classify_case()),
        # The classifier must fail its own red sample: a hollow classifier
        # returning three empty groups made `--classify` certify success.
        ("comments.classifier_red_sample",
         lambda: _classifier_has_teeth()),
        ("★ comments.hollow_classifier_is_rejected",
         lambda: _hollow_classifier_case()),
    ]


GATE = meta("Comment discipline",
            "strict: no docstrings; mismatch: no docstring wider than its interface",
            knobs=("REFLECT_COMMENTS",),
            runs_at="start-of-work",
            off_reason="a repo that has not decided whether comments are a claim "
                       "or a crutch keeps this off; declare strict or mismatch to "
                       "turn it on")

MODULE = module_meta("Comment discipline", "two readings of 'this comment earns its place'")


if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "check_explain", _cases, run))
