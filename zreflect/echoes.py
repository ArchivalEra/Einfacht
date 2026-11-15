#!/usr/bin/env python3
"""Echo detection: **the same assertion may not live in two carriers.**

The suite has exactly three places an assertion may live:

    state       a ledger fact           (FACTS.json)
    principle   a rule in `RULES`       (zreflect/doc.py)
    question    an open question        (questions/*.md)

and the discipline is "one fact, one carrier". The existing criterion for that
(`doc.form_collision_problems`) compares judging commands **byte for byte**,
which catches the crude case (two rules with the same cmd) and misses the real
one: the same sentence written twice with a few words changed. A paraphrase is
exactly what a hand-copy looks like after one edit.

## Why text ratio alone is not the criterion

A **quotation** is not a copy. The ledger keeps `principle.<id>` entries whose
`note` is the rule's own sentence, verbatim, because the rendered table has to
print it. Measured on this repo: 21 pairs at ratio 1.0, every one of them a
legitimate quotation. A gate that reported them would be noise on the first
run, and noise is what gets a gate switched off for good.

So the criterion is: two texts are highly similar **and no reference edge
explains it**. An edge exists when the later form names the earlier one (the
ledger's `principle.<id>` entry quoting `RULES[id]`). A hand-copy names
nothing.

## Interface

    echo_problems(forms, threshold=0.6) -> [(ratio, a_label, b_label)]

`forms` = `[(label, text, refs)]` where `refs` is the set of labels this form
legitimately echoes. Everything else -- normalisation, the ratio, the
order-independent comparison, the "is this an edge" test -- is behind it.
"""
from __future__ import annotations

import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import main_selftest_or, module_meta  # noqa: E402

# `0.6` catches "a few letters differ" and stays above the natural overlap of
# two genuinely different rules (measured: the closest unrelated pair in this
# repo's table is 0.535).
THRESHOLD = 0.6
# Shorter than this, two unrelated short sentences collide by accident (measured:
# "off is visible" vs "off is visibl" scores 0.94). Below the floor the pair is
# **not compared**, and `skipped_short()` reports how many forms that silenced --
# a silent floor is the same trap as a silent off state.
MIN_CHARS = 40


def _norm(text):
    """Comparable form: whitespace collapsed, case folded, punctuation trimmed.

    Punctuation and backticks differ between a rule table and the ledger note
    that quotes it; treating them as content would make every quotation look
    like a paraphrase.
    """
    s = re.sub(r"[`*_]", "", str(text or ""))
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def echo_problems(forms, threshold=None):
    """Return `[(ratio, a_label, b_label)]`: similar texts with no explaining edge.

    `forms` is `[(label, text, refs)]`; `refs` names the labels this form is
    allowed to echo. Order-independent: the edge is honoured in either
    direction, because `refs` is supplied by the producer that knows which side
    is the quotation.
    """
    limit = THRESHOLD if threshold is None else threshold
    prepared = [(label, _norm(text), set(refs or ()))
                for label, text, refs in forms
                if len(_norm(text)) >= MIN_CHARS]
    out = []
    for i in range(len(prepared)):
        for j in range(i + 1, len(prepared)):
            la, ta, ra = prepared[i]
            lb, tb, rb = prepared[j]
            if lb in ra or la in rb:
                continue                      # a quotation, not a copy
            ratio = _ratio(ta, tb)
            if ratio >= limit:
                out.append((round(ratio, 3), la, lb))
    return out


def forms_from_rules(rules):
    """`RULES` -> forms. Each rule's label is `principle:<id>`."""
    return [("principle:" + r.id, r.text, ())
            for r in rules]


def forms_from_ledger(ledger, rules=()):
    """Ledger facts -> forms.

    A `principle.<id>` entry is a **quotation**, and the edge that explains its
    overlap is granted only when its note is **byte-identical** to `RULES[id]`'s
    sentence. Granting it on the key prefix alone was the first shape here and it
    was wrong: rewriting that note into a paraphrase kept the edge and the copy
    went unreported -- which is exactly the failure this module exists to catch
    (measured: a two-word paraphrase of the same note scored 0.916 and passed).

    So the edge is **earned by content**, not by name. `rules` is the `RULES`
    list; when it is empty no edge is granted and every principle note is
    compared like any other text.
    """
    by_id = {r.id: r.text for r in rules}
    facts = ledger.get("facts") if isinstance(ledger, dict) and "facts" in ledger \
        else (ledger or {})
    out = []
    for key, entry in sorted(facts.items()):
        if not isinstance(entry, dict):
            continue
        note = entry.get("note")
        if not note:
            continue
        refs = ()
        if key.startswith("principle."):
            rid = key[len("principle."):]
            if by_id.get(rid) == note:
                refs = ("principle:" + rid,)
        out.append(("state:" + key, note, refs))
    return out


def forms_from_questions(paths):
    """`questions/*.md` -> forms. The title line is the assertion."""
    out = []
    for path in paths:
        try:
            body = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for line in body.splitlines():
            if line.startswith("# "):
                out.append(("question:" + os.path.basename(path), line[2:], ()))
                break
    return out


class _Rules:
    """Minimal stand-in for a `RULES` entry list (the builder only reads id/text)."""

    def __init__(self, text, rid="a"):
        from collections import namedtuple  # noqa: PLC0415
        rule = namedtuple("R", "id text")
        self._rules = [rule(rid, text)]

    def __iter__(self):
        return iter(self._rules)


def _cases():
    long_a = "the same assertion may not live in two carriers of the fact system"
    # (1) a near-copy with a few words changed => reported
    near = "the same assertion may not live in two carriers of the fact puzzle"
    # (2) a quotation with an explaining edge => not reported
    return [
        ("echoes.distinct_texts_ok",
         lambda: echo_problems([("principle:a", long_a, ()),
                                ("principle:b", "numbers rot the moment they are written",
                                 ())]) == []),
        ("\u2605 echoes.near_copy_is_reported",
         lambda: echo_problems([("principle:a", long_a, ()),
                                ("principle:b", near, ())]) != []),
        # a quotation names the rule it repeats: that edge explains the overlap
        ("echoes.quotation_is_not_a_copy",
         lambda: echo_problems([("principle:a", long_a, ()),
                                ("state:principle.a", long_a,
                                 ("principle:a",))]) == []),
        ("\u2605 echoes.edge_must_be_declared",
         lambda: echo_problems([("principle:a", long_a, ()),
                                ("state:principle.a", long_a, ())]) != []),
        # short texts collide by accident; they are below the floor
        ("echoes.short_texts_exempt",
         lambda: echo_problems([("principle:a", "off is visible", ()),
                                ("principle:b", "off is visibl", ())]) == []),
        # threshold is honoured in both directions
        ("\u2605 echoes.threshold_is_respected",
         lambda: echo_problems([("principle:a", long_a, ()),
                                ("principle:b", near, ())], threshold=0.99) == []),
        # **the edge is earned by content, not by name**: the builder grants it
        # only when the note is byte-identical to the rule's sentence, so a
        # paraphrase of a `principle.<id>` note is reported like any other copy
        # (the first shape granted it on the key prefix and let paraphrases by)
        ("echoes.verbatim_quote_gets_the_edge",
         lambda: forms_from_ledger(
             {"facts": {"principle.a": {"note": long_a}}}, _Rules(long_a))[0][2]
         == ("principle:a",)),
        ("\u2605 echoes.paraphrase_gets_no_edge",
         lambda: forms_from_ledger(
             {"facts": {"principle.a": {"note": near}}}, _Rules(long_a))[0][2]
         == ()),
    ]


MODULE = module_meta("Echo detection", "the same assertion may not live in two carriers")


if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "echoes", _cases, lambda argv: 0))
