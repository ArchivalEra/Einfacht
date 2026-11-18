#!/usr/bin/env python3
"""Facts gate: blocks in documents must agree with the ledger, prose must not contain bare numbers, citations must not point at nonexistent keys.

Three rules, each tied to a real incident:

  · Block disagrees with the ledger -- someone hand-edited the block (or
    edited the ledger and forgot to re-render);
  · Bare numbers in prose -- a number hand-copied into prose starts rotting
    the moment it is written (threshold configurable via `REFLECT_NAKED_MIN`;
    fenced code blocks / inline code are exempt -- re-run commands in docs
    naturally contain numbers, and treating those as bare numbers is a false
    positive, issue #3 (4));
  · Citation of a nonexistent key -- the key was renamed/deleted and the
    citation became, in place, an assertion with no provenance.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate  # noqa: E402
import knobs  # noqa: E402
from gate import fatal, finish, main_selftest_or, meta, repo  # noqa: E402
from i18n import M, load_pack  # noqa: E402
from knobs import a_pack_lang  # noqa: E402
from ledger import (  # noqa: E402
    BLOCK_BEGIN,
    BLOCK_END,
    body_of,
    facts_of,
    load_or_fatal,
    prose_of,
    render_block,
    value_of,
)
from living import (
    CITE_RE,  # noqa: E402
    DATED_RECORD,  # noqa: E402
)

FENCE_RE = re.compile(r"^\s*```")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _bare_min():
    """Bare-number threshold (issue #3 (4)): configurable via `REFLECT_NAKED_MIN`."""
    raw = os.environ.get("REFLECT_NAKED_MIN", "").strip()
    default = int(knobs.get("REFLECT_NAKED_MIN"))
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("⚠ %s" % M("facts.bad_bare_min", value=raw, default=default),
              file=sys.stderr)
        return default


def _number_lines(doc_text):
    """Lines the bare-number criterion scans (issue #3 (4)): **fenced code blocks and inline code are exempt**.

    Returns [(line number, line with inline code stripped)]; line numbers keep
    the **original numbering** -- diagnostics must line up with the
    human-readable document. The fence open/close lines themselves are not
    scanned.
    """
    prose = prose_of(doc_text)
    in_fence = False
    out = []
    for i, line in enumerate(prose.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append((i, INLINE_CODE_RE.sub("", line)))
    return out



# Shape whitelist (issue #24): numbers in these shapes are **not**
# "hand-copied measured values" and must not be reported. If the reverse
# criterion (whitelist-style) did not exclude them, prose would instantly be
# flooded by version numbers/ports/dates and eventually be `--accept`ed away
# wholesale -- worse than not checking at all (the repeatedly observed fate of
# this repo: "a gate with false positives eventually gets switched off
# entirely").
_SHAPE_PATTERNS = (
    r"\d+\.\d+(\.\d+)*",          # version strings 11.3.0 / 1.2
    r"[A-Za-z_]\w*\d+\w*",           # digits inside identifiers sha256 / utf8 / v128
    r"\d{4}-\d{2}-\d{2}",            # ISO dates
    r"\d{2}:\d{2}(:\d{2})?",         # times of day
    r"0x[0-9a-fA-F]+",                 # hex
    r"\d+%",                           # percentages
    r"\d+[KMG]i?B",                    # capacities 74MB / 32MiB
    r"[\w./-]+/\d+",                  # path segments /113/
    # Thousands separators (#27 (1)): `6,757,104` is **one number**. Without
    # this entry it gets split into the three fake tokens 6 / 757 / 104, and
    # the latter two get reported as "bare numbers without provenance" --
    # numbers that do not exist anywhere in the original text, so they cannot
    # be matched against the document during triage (downstream observed).
    r"\d{1,3}(,\d{3})+",
)


def _shape_exempt(token):
    """Does this number's **position** fall under the shape whitelist (version/identifier/date/path...)?"""
    return any(re.fullmatch(pat, token) for pat in _SHAPE_PATTERNS)


_SHA_NEAR = re.compile(r"sha|hash|checksum|fingerprint|commit", re.I)


def _known_values(facts):
    """The set of integer values that ever appeared in the ledger (the blacklist criterion "copied but not cited" is checked separately)."""
    known = set()
    for entry in facts.values():
        v = value_of(entry)
        if isinstance(v, int) and not isinstance(v, bool):
            known.add(v)
    return known


def _has_provenance(token, line):
    """Does `token` have provenance in `line` (already stripped of shape strings)?

    Any one hit suffices: shape whitelist / a bare sha with sha context /
    a `[[key]]` on the same line.
    """
    if _shape_exempt(token):
        return True
    # Bare sha: allowed only when the line has sha/hash/commit context (that
    # is check_stale's job; a contextless 8-digit number is a measured value,
    # not a sha -- observed pitfall: 99887766 was wrongly allowed by the pure
    # hex whitelist).
    if (re.fullmatch(r"[0-9a-f]{7,64}", token)
            and _SHA_NEAR.search(line)):
        return True
    return bool(CITE_RE.search(line))    # a [[key]] on the same line => counts as citation-style provenance


def _unaccounted_numbers(facts, bare_min, nlines):
    """Reverse criterion (issue #24): numbers in prose with **no provenance** at or above the threshold.

    Criterion (whitelist-style): scan the prose (outside fences/inline code,
    already stripped by `_number_lines`); every integer token >= bare_min must
    have one of these **provenances**, otherwise report:

      · immediately followed by `[[key]]` (same line) -- citation-style
        provenance;
      · hits the shape whitelist (version string / identifier / date / path /
        bare sha / percentage / capacity);
      · the line carries an explicit provenance marker (`DATED_RECORD`-type
        deliverable name or a backtick sha);
      · the value **exactly equals** some ledger fact's value (the blacklist
        criterion already checks "copied but not cited" separately; not
        double-reported here).
    """
    known = _known_values(facts)
    out = []
    # First strip "shape strings" from the whole line (dates/times/versions/
    # capacities/percentages/paths/identifiers) -- otherwise `2026-10-31`
    # yields the fake token `2026` (`-` is not in \w, and per-token matching
    # cannot prevent it; observed pitfall).
    strip_re = re.compile("|".join(_SHAPE_PATTERNS))
    for lineno, line in nlines:
        if DATED_RECORD.search(line):
            continue                     # a record line with explicit provenance is exempt as a whole (same scope as stale)
        line = strip_re.sub(" ", line)
        for token in re.findall(r"(?<![\w.])\d+\b", line):
            try:
                val = int(token)
            except ValueError:
                continue
            if val < bare_min or val in known:
                continue
            if _has_provenance(token, line):
                continue
            out.append(M("facts.bare_number_unaccounted",
                         line=lineno, number=token))
    return out


def _cite_problems(prose, facts):
    """`[[key]]` citations in prose that point at nonexistent keys."""
    out = []
    for i, line in enumerate(prose.splitlines(), 1):
        for k in CITE_RE.findall(line):
            if k not in facts:
                out.append(M("facts.missing_key_cite", line=i, key=k))
    return out


def _copied_fact_problems(facts, nlines, bare_min):
    """Blacklist criterion: a ledger value hand-copied into prose without `[[key]]` on the same line."""
    out = []
    for k, entry in sorted(facts.items()):
        v = value_of(entry)
        if isinstance(v, bool) or not isinstance(v, int) or v < bare_min:
            continue
        for i, line in nlines:
            if str(v) in line and ("[[%s]]" % k) not in line:
                out.append(M("facts.copied_value", line=i, value=v, key=k))
    return out


# The state document renders **everything**; hand-written prose is where rubbish
# accumulates (measured: 55 hand-written lines of mechanism narration, including
# four `issue #N` references and a paragraph about a hand-written roster that had
# drifted -- prose in a rendered document is drift waiting to happen).
#
# Both measured documents render everything they say. What may live outside the
# machine blocks, and nothing else:
#   * the H1 title line
#   * blank lines
#   * a **block-quote intro** (`> ...`) directly after the title
# A line-count window was the earlier shape and it was wrong the same way every
# line-count cap is wrong: it handed out 8 legal lines of rubbish. Shape-based
# means the intro is prose you can read at the top and the rest is rendered.
# Derived, not hand-written: the two documents that carry machine blocks are
# exactly the ones that render everything. A literal set here would be a second
# source for a value `knobs`/`doc` already own.
def rendered_docs():
    """The two measured documents (`doc.state_name()` and `doc.PRINCIPLES`)."""
    import doc  # noqa: PLC0415
    return frozenset({doc.state_name(), doc.PRINCIPLES})


def hand_written_problems(doc_text, name="STATE.md"):
    """Lines of a fully rendered doc (`ledger.prose_of(...)`) that are narration rather than render."""
    # **Position matters, not just shape.** An earlier version exempted any
    # `#`-prefixed or `>`-prefixed line wherever it appeared, which made
    # "# a whole hand-written section" and a `>` paragraph in the middle of the
    # document legal -- the rule was hollowed out by its own exemption.
    # Allowed: the first `# ` line, and `>` lines that are **contiguous with the
    # top of the document** (title, blank lines, then the intro quote). Anything
    # after the first non-blank, non-quote, non-title line is hand-written.
    out = []
    in_intro = True                  # still in the title/intro zone
    title_seen = False               # exactly one `# ` line, at the top
    for lineno, line in enumerate(doc_text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if in_intro and not title_seen and stripped.startswith("# "):
            title_seen = True
            continue                 # the title
        if in_intro and stripped.startswith(">"):
            continue                 # the intro block-quote
        in_intro = False             # the rendered body starts here
        out.append(M("facts.hand_written_in_state", name=name, lineno=lineno,
                     text=stripped[:60]))
    return out


def problems(ledger, doc_text, bare_min=None, name="STATE.md"):
    """Return the problem list (pure function: self-evidence needs it). Empty list = pass.

    `bare_min` overrides the bare-number threshold (passed explicitly by the
    selftest); by default `REFLECT_NAKED_MIN` is read.
    """
    bm = _bare_min() if bare_min is None else bare_min
    f = facts_of(ledger)
    if not f:
        # Zero-value guard: an empty ledger is not "no violations", it is
        # "nothing was measured".
        return [M("facts.empty_ledger")]
    if BLOCK_BEGIN not in doc_text or BLOCK_END not in doc_text:
        return [M("facts.no_block_markers",
                  begin=BLOCK_BEGIN, end=BLOCK_END)]

    out = []
    if body_of(doc_text).strip() != body_of(render_block(ledger)).strip():
        out.append(M("facts.block_mismatch"))

    out += _cite_problems(prose_of(doc_text), f)

    nlines = _number_lines(doc_text)
    out += _copied_fact_problems(f, nlines, bm)
    # Reverse criterion (issue #24): numbers that never entered the ledger need provenance too.
    out += _unaccounted_numbers(f, bm, nlines)
    return out


def _docs_to_scan(argv):
    """The list of documents to scan (`argv[0]` or `knobs.docs_names()`)."""
    if argv:
        return [argv[0]]
    return knobs.docs_names()


def _echo_problems(led):
    """Cross-carrier near-copy detection across rules, ledger notes, and questions."""
    import doc  # noqa: PLC0415
    import echoes  # noqa: PLC0415
    forms = (echoes.forms_from_rules(doc.RULES)
             + echoes.forms_from_ledger(led, doc.RULES)
             + echoes.forms_from_questions(_question_paths()))
    return [M("facts.echo_of_another_carrier", ratio=ratio, a=a, b=b)
            for ratio, a, b in echoes.echo_problems(forms)]


def _block_body(text, begin, end):
    """Trimmed body between `begin` and `end` markers."""
    return text.partition(begin)[2].partition(end)[0].strip()


def _lookup_doc(docs_by_name, target):
    """Find `(doc_key, text)` in `docs_by_name` matching `target` by path or basename."""
    if target in docs_by_name:
        return target, docs_by_name[target]
    for k, v in docs_by_name.items():
        if os.path.basename(k) == target:
            return k, v
    return None, None


def block_homes(ledger):
    """Map docs to owned machine blocks (`AUTO:FACTS`, `AUTO:GATES`, `AUTO:RULES`). Returns `(homes, err)`."""
    import doc  # noqa: PLC0415
    import registry  # noqa: PLC0415
    gs, missing = registry.gates()
    probs = registry.problems(gs, missing)
    if probs:
        return None, M("facts.registry_mismatch", entries="\n  · ".join(probs))
    homes = [(doc.state_name(), [(BLOCK_BEGIN, BLOCK_END, render_block(ledger)),
                                 (registry.GATES_BEGIN, registry.GATES_END,
                                  registry.render_gates(gs))])]
    if doc.accepts_principles():
        homes.append((doc.PRINCIPLES,
                      [(doc.RULES_BEGIN, doc.RULES_END, doc.render_rules())]))
    return homes, None


def doc_block_problems(path_rel, text, blocks):
    """Compare each `(begin, end, expected)` block in `blocks` against `text`."""
    out = []
    for begin, end, expected in blocks:
        if begin not in text or end not in text:
            out.append(M("facts.markers_missing_check", path=path_rel, begin=begin, end=end))
        elif _block_body(text, begin, end) != _block_body(expected, begin, end):
            out.append(M("facts.block_stale", path=path_rel, begin=begin))
    return out


def extra_block_problems(docs_by_name, homes):
    """Check non-`AUTO:FACTS` machine blocks (`AUTO:GATES`, `AUTO:RULES`) against `homes`."""
    out = []
    for name, blocks in homes:
        doc_key, text = _lookup_doc(docs_by_name, name)
        if text is None:
            continue
        rest = [(b, e, exp) for b, e, exp in blocks if b != BLOCK_BEGIN]
        out += doc_block_problems(doc_key, text, rest)
    return out


def _repo_sync_problems(led, loaded):
    """Repo-level `block_homes` agreement (`AUTO:GATES`, `AUTO:RULES`)."""
    homes, err = block_homes(led)
    if err:
        return None, err
    return extra_block_problems(loaded, homes), None


def _question_paths():
    """`questions/*.md` under the audited repo (empty when the dir is absent).

    Resolved through `knobs.questions_path()` so `REFLECT_QUESTIONS` is honoured;
    a literal `questions/` here ignored the knob and the criterion silently ran
    on an empty set under the rename fixture.
    """
    import glob  # noqa: PLC0415
    return sorted(glob.glob(os.path.join(str(knobs.questions_path()), "*.md")))


def run(argv):
    docs = _docs_to_scan(list(argv))
    facts_name = knobs.get("REFLECT_FACTS")
    led_path = repo(facts_name)
    if not os.path.exists(led_path):
        return fatal(M("facts.ledger_missing", name=facts_name))
    led = load_or_fatal(led_path)
    probs = []
    loaded = {}
    scanned = 0
    for doc in docs:
        p = gate.repo_path(doc)
        if not os.path.exists(p):
            # A document named in the roster is absent => report (`REFLECT_DOCS`
            # is a declaration, not a suggestion). But an explicit `argv[0]`
            # keeps the original hard FATAL (that is the caller pointing at
            # the wrong path).
            if len(docs) == 1 and argv:
                return fatal(M("facts.doc_missing", path=p))
            probs.append(M("facts.doc_missing", path=p))
            continue
        scanned += 1
        text = open(p, encoding="utf-8").read()
        loaded[doc] = text
        if BLOCK_BEGIN in text and BLOCK_END in text:
            # Documents with a machine block: full criteria (block agreement
            # + citations + bare numbers).
            probs += problems(led, text, name=doc)
        else:
            probs += _copied_fact_problems(facts_of(led), _number_lines(text),
                                           _bare_min())
        if os.path.basename(doc) in rendered_docs():
            probs += hand_written_problems(prose_of(text), doc)
    extra, err = _repo_sync_problems(led, loaded)
    if err:
        return fatal(err)
    probs += extra
    probs += _echo_problems(led)
    return finish(M("facts.title"), probs,
                  M("facts.ok", count=len(facts_of(led)), docs=scanned))


LED = {"facts": {"count": {"value": 4752, "cmd": "c"}}}




def _cases_fixture():
    """Fixture ledgers, prose sample, and pack-placeholder probe."""
    good = "no bare numbers here.\n" + render_block(LED)
    numberless = {"facts": {"n": {"value": 3, "cmd": "c"}}}
    fifty = {"facts": {"n": {"value": 50, "cmd": "c"}}}

    def codes(ledger, doc, **kw):
        return [p.code for p in problems(ledger, doc, **kw)]

    pack_lang = a_pack_lang()
    real_pack = load_pack(pack_lang) if pack_lang else {}

    def pack_placeholders(code):
        """The set of placeholder names for a code in that pack (missing entry => empty set, assertion goes red on the spot)."""
        import re  # noqa: PLC0415
        return set(re.findall(r"%\((\w+)\)", real_pack.get(code, "")))

    return {'good': good, 'numberless': numberless, 'fifty': fifty, 'codes': codes, 'pack_lang': pack_lang, 'real_pack': real_pack, 'pack_placeholders': pack_placeholders}


def _cases_core(fx):
    """Core block-agreement, bare-number, and citation cases."""
    good, codes = fx["good"], fx["codes"]
    return [
    ("facts.block_ok",
     lambda: problems(LED, good) == []),
    ("facts.live_cite_ok",
     lambda: problems(LED, "see [[count]]\n" + render_block(LED)) == []),
    ("★ facts.block_mismatch",
     lambda: codes(LED, "x\n" + render_block({"facts": {}}))
     == ["facts.block_mismatch"]),
    ("★ facts.copied_value",
     lambda: codes(LED, "speed is 4752 times\n" + render_block(LED))
     == ["facts.copied_value"]),
    ("★ facts.missing_key_cite",
     lambda: codes(LED, "see [[nope]]\n" + render_block(LED))
     == ["facts.missing_key_cite"]),
    ("★ facts.bare_number_unaccounted",
     lambda: codes(LED, "measured 99887766 but not in ledger.\n"
                    + render_block(LED))
     == ["facts.bare_number_unaccounted"]
     and any("99887766" in str(p) for p in problems(
         LED, "measured 99887766 but not in ledger.\n" + render_block(LED))),
     ),
    ("facts.cite_counts_as_provenance",
     lambda: problems(LED, "see [[count]] = 99887766\n"
                      + render_block(LED)) == []),
    ("★ facts.bare_number_sentence_period",
     lambda: codes(LED, "measured 99887766.\n" + render_block(LED))
     == ["facts.bare_number_unaccounted"]),
    ("★ facts.empty_ledger",
     lambda: codes({"facts": {}}, good) == ["facts.empty_ledger"]),
    ("★ facts.hand_written_in_state",
     lambda: [p.code for p in hand_written_problems("- rubbish\n")]
     == ["facts.hand_written_in_state"]),
    ("facts.title_and_intro_are_allowed",
     lambda: hand_written_problems("# T\n\n> intro\n> more\n") == []),
    ("\u2605 facts.no_line_count_loophole",
     lambda: [p.code for p in hand_written_problems(
         "# T\n\n> i\n" + "- junk\n" * 7)]
     == ["facts.hand_written_in_state"] * 7),
    ("\u2605 facts.hand_written_in_principles",
     lambda: [p.code for p in hand_written_problems("## extra rules\n",
                                                    name="PRINCIPLES.md")]
     == ["facts.hand_written_in_state"]),
    ("★ facts.no_block_markers",
     lambda: codes(LED, "a document with no block at all")
     == ["facts.no_block_markers"]),
    ]


def _cases_naked(fx):
    """See `_cases()`: this group has 7 entries."""
    numberless, fifty, codes = fx["numberless"], fx["fifty"], fx["codes"]
    return [
    ("facts.small_int_exempt",
     lambda: problems(numberless, "there are 3\n"
                      + render_block(numberless)) == []),
    ("facts.shape_whitelist",
     lambda: problems(LED, "v11.3.0 and sha256 and 2026-10-31\n"
                      + render_block(LED)) == []),
    ("★ facts.bare_sha_needs_context",
     lambda: codes(LED, "just wrote 99887766\n" + render_block(LED))
     == ["facts.bare_number_unaccounted"]),
    # (4) bare-number criterion extensions (issue #3 (4))
    ("facts.fenced_exempt",
     lambda: problems(LED, "```\nspeed is 4752 times\n```\n"
                      + render_block(LED)) == []),
    ("facts.inline_code_exempt",
     lambda: problems(LED, "see `4752` times\n" + render_block(LED)) == []),
    ("facts.below_threshold_exempt",
     lambda: problems(fifty, "there are 50\n" + render_block(fifty)) == []),
    ("★ facts.threshold_knob",
     lambda: codes(fifty, "there are 50\n" + render_block(fifty), bare_min=10)
     == ["facts.copied_value"]
     and "50" in str(problems(fifty, "there are 50\n" + render_block(fifty),
                              bare_min=10)[0])),
    ]


def _cases_pack(fx):
    """Language-pack wiring case."""
    pack_lang, pack_placeholders = fx["pack_lang"], fx["pack_placeholders"]
    return [
    ("facts.pack_entry_wired",
     lambda: not pack_lang or
     pack_placeholders("facts.bare_number_unaccounted")
     == {"line", "number"}),
    ]


def _cases_misc(fx):
    """Fence, separator, extra-block, and principle-sync cases."""
    codes = fx["codes"]
    return [
    ("★ facts.bare_number_outside_fence",
     lambda: codes(LED, "```\n4752\n```\nspeed is 4752 times\n"
                    + render_block(LED)) == ["facts.copied_value"]),
    ("★ facts.thousands_separator_is_one_number",
     lambda: problems(LED, "release 6,757,104 B\n" + render_block(LED)) == []
     and codes(LED, "release 6,757,104 B and 99887766 measured\n"
               + render_block(LED)) == ["facts.bare_number_unaccounted"]
     and all("757" not in str(p) and "104" not in str(p)
             for p in problems(LED, "release 6,757,104 B and 99887766 measured\n"
                               + render_block(LED)))),
    ("★ facts.stale_gates_block",
     lambda: [p.code for p in extra_block_problems(
         {"STATE.md": "<!-- AUTO:GATES -->\nstale\n<!-- /AUTO:GATES -->"},
         [("STATE.md", [("<!-- AUTO:GATES -->", "<!-- /AUTO:GATES -->",
                        "<!-- AUTO:GATES -->\nfresh\n<!-- /AUTO:GATES -->")])])]
     == ["facts.block_stale"]
     and extra_block_problems(
         {"STATE.md": "<!-- AUTO:GATES -->\nfresh\n<!-- /AUTO:GATES -->"},
         [("STATE.md", [("<!-- AUTO:GATES -->", "<!-- /AUTO:GATES -->",
                        "<!-- AUTO:GATES -->\nfresh\n<!-- /AUTO:GATES -->")])]) == []),
    ("★ facts.stale_rules_block",
     lambda: [p.code for p in extra_block_problems(
         {"PRINCIPLES.md": "<!-- AUTO:RULES -->\nstale\n<!-- /AUTO:RULES -->"},
         [("PRINCIPLES.md", [("<!-- AUTO:RULES -->", "<!-- /AUTO:RULES -->",
                             "<!-- AUTO:RULES -->\nfresh\n<!-- /AUTO:RULES -->")])])]
     == ["facts.block_stale"]),
    ]


def _cases():
    """Assemble the four fixture groups. **Assembly only** -- the criteria live in the group functions."""
    fx = _cases_fixture()
    return (
    _cases_core(fx)
    + _cases_naked(fx)
    + _cases_pack(fx)
    + _cases_misc(fx)
    )


GATE = meta("Facts gate", "block agreement / bare numbers / bad citations",
            knobs=("REFLECT_DOC", "REFLECT_DOCS", "REFLECT_FACTS",
                   "REFLECT_NAKED_MIN", "REFLECT_QUESTIONS"),
            name_dependent=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], M("gate.title.facts"),
                              _cases, run))
