#!/usr/bin/env python3
"""Retraction gate: **a retracted assertion may not quietly return as the
current state.**

Each entry in `retractions.json` = one retracted assertion:
  `text` the search snippet -- the assertion's signature fragment, matched
  verbatim against document lines · `evidence` how to replay the refutation ·
  `fixed_in` where the corrected claim lives now

  There is no `why` field: it would be free prose that nothing reads. The
  evidence command is what explains the correction, and it can be re-run.

Criterion: a retracted assertion (`text`) may **not** appear on any living-state
line in a declared document, even with a history marker; historical accounts
belong in `HISTORY.md` (off every scan surface) or a declared
`REFLECT_HISTORY_SECS` section. This is the only mechanism that raises the alarm
when "a retracted sentence reappears" -- a measured cost: one corrected
assertion survived **in the same file**, and also had a copy in another
document. Prose relies on good intentions; this relies on a gate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate  # noqa: E402
import knobs  # noqa: E402
from facts import living_lines, load_or_fatal  # noqa: E402
from gate import fatal, finish, guard_nonempty, main_selftest_or, meta, repo  # noqa: E402
from i18n import M  # noqa: E402

REQUIRED = ("id", "text", "evidence", "fixed_in")
# **Resolved via the knob helper**: the parse lives in `knobs.history_secs()`
# (the single producer -- `check_stale` reads the same helper), so the two
# gates cannot drift apart on "what counts as a history section".
HIST_SECS = knobs.history_secs()


def _entry_field_problems(retractions):
    """Required fields of every retraction entry (one missing => the ledger
    entry cannot be trusted)."""
    return [M("retractions.entry_missing_field", field=fld, entry=r.get("id"))
            for r in retractions
            for fld in REQUIRED if not r.get(fld)]


def _run_evidence(ev, runner, cache):
    if runner is not None:
        return runner(ev)
    if cache is not None and ev in cache:
        return cache[ev]
    res = gate.run_cmd(ev)
    if cache is not None:
        cache[ev] = res
    return res


def _evidence_problems(retractions, runner=None, verify_evidence=False):
    """`evidence` must be **replayable** and pass when `verify_evidence` is enabled."""
    out = []
    cache: dict[str, tuple[int | None, str]] = {}
    for r in retractions:
        ev = r.get("evidence")
        if (not str(ev or "").strip()
                or gate.prose_in_exec_problems(
                    "retractions/%s" % r.get("id", "?"), "evidence", ev)):
            out.append(M("retractions.evidence_not_runnable",
                         entry=r.get("id"), evidence=str(ev)[:60]))
            continue
        if verify_evidence or runner is not None:
            rc, _ = _run_evidence(str(ev), runner, cache)
            if rc != 0:
                out.append(M("retractions.evidence_failed",
                             entry=r.get("id"), rc=str(rc), evidence=str(ev)[:60]))
    return out


def _resurfaced_problems(retractions, docs, hist):
    """Resurfacing: living-state lines may **not** contain retracted `text`
    (even with a history tag -- prose belongs in `HISTORY.md`).

    Only **living state** is scanned (`zreflect/facts.py`'s `living_lines`):
    append-only history sections declared via `REFLECT_HISTORY_SECS` are exempt
    -- their "as it was then" is not "as it is now".
    """
    out = []
    for r in retractions:
        text = r.get("text") or ""
        if not text:
            continue
        for name, body in sorted(docs.items()):
            for i, line, is_living in living_lines(body or "", hist):
                if is_living and text in line:
                    out.append(M("retractions.resurfaced", name=name, line=i,
                                 text=text, entry=r.get("id", "?")))
    return out


def problems(retractions, docs, hist_secs=None, runner=None, verify_evidence=False):
    """Return the problem list (pure function: the selftest needs that)."""
    hist = HIST_SECS if hist_secs is None else hist_secs
    if retractions is None or "retractions" not in (retractions or {}):
        return [M("retractions.missing_key")]
    if not docs:
        return [M("retractions.no_docs")]
    entries = [r for r in (retractions.get("retractions") or [])
               if isinstance(r, dict)]
    return _entry_problems(entries, docs, hist, runner=runner, verify_evidence=verify_evidence)


def _entry_problems(entries, docs, hist, runner=None, verify_evidence=False):
    """Concatenate field completeness, evidence checks, and document resurfacing."""
    return (_entry_field_problems(entries)
            + _evidence_problems(entries, runner=runner, verify_evidence=verify_evidence)
            + _resurfaced_problems(entries, docs, hist))


def scanned_docs():
    """The list of documents this gate scans (`knobs.docs_names()`, single
    origin)."""
    return knobs.docs_names()


def run(argv):
    # The name is configurable (issue #1, item 2): never hardcoded -- switching
    # repos means changing only the environment variable.
    rp = repo(knobs.get("REFLECT_RETRACTIONS"))
    if not os.path.exists(rp):
        return fatal(M("retractions.file_missing", name=rp))
    docs = {}
    for name in (argv or scanned_docs()):
        p = repo(name)
        if os.path.exists(p):
            docs[name] = open(p, encoding="utf-8", errors="replace").read()
    rc = guard_nonempty("check_retractions", docs, M("retractions.scanned_docs"))
    if rc:
        return rc
    led = load_or_fatal(rp)
    verify_ev = int(os.environ.get("EINFACHT_REPLAY_DEPTH", "0") or 0) == 0
    probs = problems(led, docs, verify_evidence=verify_ev)
    n = len(led.get("retractions") or [])
    return finish(M("retractions.title"), probs,
                  M("retractions.ok", count=n, documents=len(docs)))


def _cases():
    ok_r = {"retractions": [{"id": "R-1", "text": "this thing is green",
                             "evidence": "python3 zreflect/facts.py --check",
                             "fixed_in": "doc y"}]}
    doc_marked = "(record) this thing is green -- retracted, see R-1\n"
    return [
        ("\u2605 retractions.hist_mark_does_not_exempt",
         lambda: [p.code for p in problems(ok_r, {"A.md": doc_marked})]
         == ["retractions.resurfaced"]),
        ("retractions.assertion_absent",
         lambda: problems(ok_r, {"A.md": "clean document\n"}) == []),
        ("retractions.no_retractions",
         lambda: problems({"retractions": []}, {"A.md": "x\n"}) == []),
        ("retractions.declared_history_section",
         lambda: problems(ok_r, {"A.md": "## 5 history\nthis thing is green.\n"},
                          hist_secs=("5",)) == []),
        ("★ retractions.resurfaced",
         lambda: [p.code for p in problems(
             ok_r, {"A.md": "this thing is green.\n"})] == ["retractions.resurfaced"]),
        ("★ retractions.resurfaced_undeclared_history",
         lambda: [p.code for p in problems(
             ok_r, {"A.md": "## 5 history\nthis thing is green.\n"}, hist_secs=())]
         == ["retractions.resurfaced"]),
        ("\u2605 retractions.entry_missing_field",
         lambda: [p.code for p in problems(
             {"retractions": [{"id": "R-2", "text": "t", "fixed_in": "f"}]},
             {"A.md": "x\n"})]
         == ["retractions.entry_missing_field", "retractions.evidence_not_runnable"]),
        ("\u2605 retractions.evidence_not_runnable",
         lambda: [p.code for p in problems(
             {"retractions": [{"id": "R-3", "text": "t",
                               "evidence": "a subagent report",
                               "fixed_in": "f"}]}, {"A.md": "x\n"})]
         == ["retractions.evidence_not_runnable"]),
        ("★ retractions.no_docs",
         lambda: [p.code for p in problems(ok_r, {})] == ["retractions.no_docs"]),
        ("★ retractions.missing_key",
         lambda: [p.code for p in problems({}, {"A.md": "x\n"})]
         == ["retractions.missing_key"]),
        ("★ retractions.missing_key_none",
         lambda: [p.code for p in problems(None, {"A.md": "x\n"})]
         == ["retractions.missing_key"]),
        ("★ retractions.evidence_failed",
         lambda: [p.code for p in problems(
             ok_r, {"A.md": "clean\n"}, runner=lambda _c: (1, "fail"))]
         == ["retractions.evidence_failed"]),
    ]


GATE = meta("Retraction-resurfacing check", "a retracted assertion may not quietly return as the current state",
            knobs=("REFLECT_RETRACTIONS", "REFLECT_DOCS", "REFLECT_HISTORY_SECS"), name_dependent=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "check_retractions", _cases, run))
