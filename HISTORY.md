# HISTORY

> The one carrier where prose is allowed. Everything here is an account of how a
> rule came to exist -- reproducible only under the conditions of that moment, so
> it is deliberately **outside the measured surface**. `check_history.py` proves
> that: if this file is ever declared in `REFLECT_DOCS`, its "as it was then"
> lines become live-state claims and every stale assertion in it turns red.

Path is configurable: `REFLECT_HISTORY` (default `HISTORY.md`, relative to the
audited repo root).

## Why prose is confined to this file

The suite has exactly two things that may claim "this is how it is": a rendered
machine block (from the ledger) and a judgement (a `RULES` entry with a command
that really runs). Everything else is narration, and narration rots: a sentence
written as true stays true-looking long after the code moved.

So narration gets one home and no others. When something needs explaining, the
explanation is either

* a criterion (it can be re-run, so it belongs in `RULES`), or
* history (it happened once, so it belongs here).

There is no third place, and the criteria keep it that way: `STATE.md` and
`PRINCIPLES.md` reject hand-written lines outside their title and intro
(`facts.hand_written_in_state`); every execution position must hold a command
(`criteria.exec_position_is_prose`); a near-copy of an assertion in two carriers
is a hand-copy (`echoes`).

## Entries

### `replay: false` never had a user

The ledger once had a per-fact opt-out: `replay: false` meant "do not re-run this
one". Its docstring called it "an exemption with a roster and a stated reason".
Nothing checked the reason, and measured over the whole ledger, **zero facts used
it**. It was a door, not a path -- and a door that makes "this fact stopped being
checkable" look exactly like "this fact passes".

First attempt at a cure was to require a reason field. That was worse: a prose
reason is unverifiable, so the ambiguity survived being documented. The tier was
deleted instead, together with `ledger.fact(replay=...)`. A value that cannot be
re-run in this environment does not belong in the ledger -- it belongs here.

### `why` fields were prose that nothing read

Six spec types required a `why` string. Four of them never put it in any output;
two did. Deleting the four and keeping the two was the first instinct, and it is
the wrong cut: the question is not "is this string printed" but "may free prose
live in a criterion file at all". It may not. All six were removed; the
information they were supposed to carry is carried by `evidence` (a command) and
`fixed_in` (a pointer to the correction).

### The 8-line window let rubbish through

`STATE.md` was allowed "up to 8 hand-written lines" before the rendered blocks.
The limit was meant to permit a title and a short intro. What it actually
permitted was seven lines of anything, at the top of the document whose whole
purpose is to render. The criterion is now positional: one `#` title, then a `>`
intro, then nothing but rendered blocks. Measured: a second `#` heading and a
`>` paragraph mid-document both used to pass.

### Similarity alone would have been noise on day one

The rule "the same assertion must not live in two carriers" started as a text
similarity check. Measured on this repo before shipping it: 44 texts across the
three carriers, 21 pairs at similarity 1.0 -- every one of them the ledger's
`principle.<id>` note quoting the rule's own sentence, because the rendered table
has to print it.

A gate that fires 21 times on its first run is a gate that gets switched off. So
the criterion became "similar texts **with no reference edge explaining the
overlap**", and the edge is granted only when the note is byte-identical to the
rule's sentence. Granting it on the key prefix alone was the second mistake: a
two-word paraphrase of that same note scored 0.916 and kept the edge, so the
copy went unreported -- precisely the case the module exists to catch.

### Three language packs, three ways to be wrong

Messages go through `M(code)` with three renders. Twice in one round a parameter
was deleted from the code but not from the templates: the English/latin packs
still interpolated `%(skipped)s` and `%(why)s`, raising `KeyError` at render
time. Because the repo's own carrier sets `REFLECT_LANG=zh`, the pre-commit hook
failed on every commit while a bare-environment run stayed green.

The lesson is not "remember to update packs" -- it is that a message template and
its call site are two copies of one contract, and nothing reconciled them. That
gap is why `check_i18n` now also compares placeholder sets against the call site
rather than only checking that every code has a translation.
