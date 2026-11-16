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


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
