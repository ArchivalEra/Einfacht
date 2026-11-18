#!/usr/bin/env python3
"""Knob registry (the **single roster** of REFLECT_*): register once, derive everywhere.

The "knob" concept previously had no module: reads were scattered across gates,
declarations lived as docstring prose, judgment data sat in check_envfile's
FILE_KNOBS, and the roster was found by scanning all text -- the scanner explicitly
said "mentions in docstrings count too", so **phantom knobs** like REFLECT_AB /
REFLECT_PINS that only existed in documentation made it onto the roster, passed
the typo check, and were **silently ineffective** when a user actually exported
them (Phase 0 already turned them into real implementations). Three modules each
held a mutually inconsistent version of "what the knobs are" -- the shallow-seam
disease exactly.

This module collapses that into one interface: **registered = exists**. Name,
kind, default, one-line semantics, all registration-based; check_envfile's
judgment reads from here; a REFLECT_* token appearing in the scan surface but
absent from the roster = phantom / typo => report (a docstring mention doesn't
count, registration does); REFLECT_* names appearing in the three-language
READMEs subset of roster (reverse assertion, executed by envfile's self-evidence).

Kinds -- envfile uses them to decide whether to check existence:

  file    value is a filename relative to the repo root (existence is checked;
          empty default = not configured means not enabled)
  list    comma-separated list of filenames (each checked)
  dir     value is a directory name relative to the repo root
  number  a number (seconds / days / thresholds; empty default = that rule
          explicitly says not enabled)
  flag    enumerated switch (e.g. off)
  value   arbitrary string (overrides / names / numbered lists)

⚠️ Roster discipline: **only register knobs that are actually read via
`os.environ.get`**. Saving a seat for a "might use someday" name = manufacturing
your own phantoms -- the phantom-knob shape lesson: docs promised it, code doesn't
read it, the user configures it and it silently does nothing. Not even examples
here spell out concrete unregistered names (the scan reconciliation would report
the example as a phantom -- the reconciliation ignores context, which is exactly
its strength).
"""
from __future__ import annotations

import os
import re
import sys

import gate  # noqa: E402
from gate import module_meta  # noqa: E402
from i18n import NULL, Catalog, M, bind, load_pack, pack_dir  # noqa: E402


class _Semantic(str):
    """A knob's one-line semantics (third item of `REGISTRY`): **lazily rendered**
    user-visible text.

    `REGISTRY` is built at import time, while language packs are only
    `activate()`d inside the entry `main_selftest_or` -- calling `M(...)` directly
    here would render at construction time and be **permanently stuck on the
    null pack**. So we store the code and re-render per the **current** language
    at `__str__` time (consumers only format it via `%(entry)s`; see
    check_envfile's file_missing / dir_missing messages).
    """

    __slots__ = ("code",)

    def __new__(cls, code):
        obj = str.__new__(cls, code)
        obj.code = code
        return obj

    def __str__(self):
        return str(M(self.code))


# name -> (kind, default, one-line semantics). Default = the fallback name each
# consumer uses when the knob is unset.
# Semantics follow core zero-language (issue #26): codes go into language packs,
# the core never contains natural language.
REGISTRY = {
    "REFLECT_FACTS": ("file", "FACTS.json",
                      _Semantic("knobs.sem.reflect_facts")),
    "REFLECT_DOC": ("file", "STATE.md",
                    _Semantic("knobs.sem.reflect_doc")),
    "REFLECT_DOCS": ("list", "STATE.md,AGENTS.md,PRINCIPLES.md,README.md,README.zh.md,README.de.md",
                     _Semantic("knobs.sem.reflect_docs")),
    "REFLECT_HISTORY_SECS": ("value", "",
                             _Semantic("knobs.sem.reflect_history_secs")),
    "REFLECT_RETIRED": ("value", "",
                        _Semantic("knobs.sem.reflect_retired")),
    "REFLECT_NAKED_MIN": ("number", "100",
                          _Semantic("knobs.sem.reflect_naked_min")),
    "REFLECT_STALE_DAYS": ("number", "",
                           _Semantic("knobs.sem.reflect_stale_days")),
    "REFLECT_REPLAY": ("flag", "",
                       _Semantic("knobs.sem.reflect_replay")),
    "REFLECT_REPLAY_TIMEOUT": ("number", "10",
                               _Semantic("knobs.sem.reflect_replay_timeout")),
    "REFLECT_READMES": ("list", "README.md,README.zh.md,README.de.md",
                        _Semantic("knobs.sem.reflect_readmes")),
    "REFLECT_RETRACTIONS": ("file", "retractions.json",
                            _Semantic("knobs.sem.reflect_retractions")),
    "REFLECT_QUESTIONS": ("dir", "questions",
                          _Semantic("knobs.sem.reflect_questions")),
    "REFLECT_HISTORY": ("file", "HISTORY.md",
                        _Semantic("knobs.sem.reflect_history")),
    "REFLECT_ENV_FILE": ("value", "Einfacht.env",
                         _Semantic("knobs.sem.reflect_env_file")),
    "REFLECT_ENV_HINT": ("flag", "",
                         _Semantic("knobs.sem.reflect_env_hint")),
    "REFLECT_INVARIANTS": ("file", "",
                           _Semantic("knobs.sem.reflect_invariants")),
    "REFLECT_INSTRUMENTS": ("file", "",
                            _Semantic("knobs.sem.reflect_instruments")),
    "REFLECT_INSTRUMENT_DAYS": ("number", "",
                                _Semantic("knobs.sem.reflect_instrument_days")),
    "REFLECT_DOCTOR": ("file", "doctor.json",
                       _Semantic("knobs.sem.reflect_doctor")),
    "REFLECT_DOCTOR_TIMEOUT": ("number", "2",
                               _Semantic("knobs.sem.reflect_doctor_timeout")),
    "REFLECT_WORLD": ("file", "world.json",
                      _Semantic("knobs.sem.reflect_world")),
    "REFLECT_WORLD_LINE": ("value", "",
                           _Semantic("knobs.sem.reflect_world_line")),
    "REFLECT_AB": ("file", "ab.json",
                   _Semantic("knobs.sem.reflect_ab")),
    "REFLECT_PINS": ("file", "pins.json",
                     _Semantic("knobs.sem.reflect_pins")),
    "REFLECT_LOCKS": ("file", "upstream-lock.json",
                      _Semantic("knobs.sem.reflect_locks")),
    "REFLECT_MEASURE_MODULE": ("value", "",
                               _Semantic("knobs.sem.reflect_measure_module")),
    "REFLECT_PHASES": ("value", "",
                       _Semantic("knobs.sem.reflect_phases")),
    # Comment discipline mode: `mismatch` (default: explanation budget <=
    # 300 + 120*branches + 60*args) / `strict` (no docstrings) / `off`.
    "REFLECT_COMMENTS": ("value", "mismatch",
                         _Semantic("knobs.sem.reflect_comments")),
    # Explicitly opt out of this suite's principles (for repos that don't want
    # to run those judgment commands on every commit).
    "REFLECT_NO_PRINCIPLES": ("flag", "",
                              _Semantic("knobs.sem.reflect_no_principles")),
    "REFLECT_LANG": ("value", "",
                     _Semantic("knobs.sem.reflect_lang")),
    # Languages this repo **declares it serves** (issue #35): unset = every
    # installed pack counts (back-compat); set = only these are judged by
    # pack_coverage/pack_sync -- the other directories are suite self-evidence
    # samples, not commitments. Naming follows the plural-list knob lineage
    # (REFLECT_READMES / REFLECT_DOCS).
    "REFLECT_LANGS": ("list", "",
                      _Semantic("knobs.sem.reflect_langs")),
    "REFLECT_I18N": ("dir", "",
                     _Semantic("knobs.sem.reflect_i18n")),
    "REFLECT_I18N_ROOT": ("dir", "",
                          _Semantic("knobs.sem.reflect_i18n_root")),
    "REFLECT_SNAPSHOT_ROOT": ("dir", "",
                              _Semantic("knobs.sem.reflect_snapshot_root")),
    "REFLECT_SECRETS": ("file", "secrets.json",
                        _Semantic("knobs.sem.reflect_secrets")),
}

KINDS = ("file", "list", "dir", "number", "flag", "value")


def knobs_table(rows=None):
    """The **human-readable table** of the knob roster (`--list` output). **Pure function**.

    Semantics go through `_Semantic` (`str()` renders per the current language
    pack); with no language pack installed the output is a code like
    `knobs.sem.<name>` -- the honest "no language pack installed".
    """
    rows = REGISTRY if rows is None else rows
    lines = ["| knob | kind | default | meaning |", "|---|---|---|---|"]
    for name in sorted(rows):
        kind, default, sem = rows[name]
        lines.append("| `%s` | %s | %s | %s |"
                     % (name, kind, default or "--", sem))
    return "\n".join(lines)

# Placeholder tokens (`%(name)s`) -- self-evidence reconciles whether the zh / en
# placeholder names agree.
_PLACEHOLDER_RE = re.compile(r"%\((\w+)\)")

# Knob token: REFLECT_ + uppercase. The **left boundary is required** -- without
# it, the retraction example text (a `ZCODE_`-prefixed token) gets cut mid-token
# into a fake token, and the three-language README reconciliation reports one
# false positive per language (observed hit). ⚠️ This file **never spells out**
# that fake token literal.
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])REFLECT_[A-Z0-9_]+")


def _py_sources(base):
    """See `gate.py_sources`: one implementation only (this keeps just the module name)."""
    import gate  # noqa: PLC0415
    return gate.py_sources(base)


def scan_surface_problems(py_dir=None):
    """REFLECT_* tokens that appear in the scan surface (zreflect/*.py) but are
    absent from the roster.

    **Roster self-consistency**, independent of whether any carrier
    (Einfacht.env) exists -- it belongs to the "roster" itself (C3). `py_dir` is
    injectable (fake source tree for self-evidence).
    """
    d = py_dir if py_dir is not None else gate.zdir()
    toks = set()
    for _name, text in _py_sources(d):
        toks.update(_TOKEN_RE.findall(text))
    out = []
    for tok in sorted(toks):
        if tok not in REGISTRY:
            out.append(M("knobs.phantom_token", token=tok))
    return out


def readme_names():
    """The list of three-language READMEs (`REFLECT_READMES`; default from `REGISTRY`).

    ⚠️ **"unset" and "explicitly empty" are different intents**: unset means "use
    the default"; empty means "this repo deliberately has no README group" and
    returns `[]`. `check_readme_sync` relies on this distinction;
    `docs_names()` deliberately collapses empty to the default.
    """
    raw = os.environ.get("REFLECT_READMES")
    if raw is None or not raw.strip():
        if raw is not None:
            return []                                 # explicitly empty: a real answer
        raw = REGISTRY["REFLECT_READMES"][1]          # default from the registry
    return [s.strip() for s in raw.split(",") if s.strip()]


def get(name):
    """Read knob `name` (trimmed); empty/unset falls back to `REGISTRY[name][1]`."""
    raw = os.environ.get(name, "").strip()
    if raw:
        return raw
    return REGISTRY[name][1]


def docs_names():
    """The list of live state documents (`REFLECT_DOCS`; default from `REGISTRY`).

    Unlike `readme_names()`, an empty value means "use the default": a repo must
    have a state document. The registry is the single producer of that default.
    """
    return [s.strip() for s in get("REFLECT_DOCS").split(",") if s.strip()]


def served_langs():
    """The languages this repo **declares it serves** (`REFLECT_LANGS`).

    Unset => empty list = "every installed pack counts". Set => only these
    languages are judged by `pack_coverage_problems` / `pack_sync_problems`; the
    other pack directories are suite self-evidence samples. "Served" is a promise
    about **readers**, not about translation workload.
    """
    raw = os.environ.get("REFLECT_LANGS", "").strip()
    if not raw:
        return []                                  # unset = no narrowing
    return [s.strip() for s in raw.split(",") if s.strip()]


FLAG_TRUTHY = ("1", "true", "yes", "on")
FLAG_FALSY = ("0", "false", "no", "off")


def flag(name):
    """Read a flag-kind knob; returns `True` (on) / `False` (off) / `None` (unset).

    Matching is case-insensitive and whitespace-trimmed for `FLAG_TRUTHY` /
    `FLAG_FALSY`. `None` = unset or an unrecognized word (the caller applies its
    own default), a different decision from "explicitly off"; an unrecognized
    word is never silently treated as on.
    """
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return None                   # unset (including empty string) => caller default
    if raw in FLAG_TRUTHY:
        return True
    if raw in FLAG_FALSY:
        return False
    return None                       # unrecognized word => let the caller decide


def questions_dir(repo_root=None):
    """The open-questions directory name (`REFLECT_QUESTIONS`; default from `REGISTRY`)."""
    return get("REFLECT_QUESTIONS")


def repo_path(name, root=None):
    """Resolve knob `name` relative to `root` (default `gate.GATE_REPO`); empty => None."""
    rel = get(name)
    if not rel:
        return None
    base = root or gate.GATE_REPO
    return rel if os.path.isabs(rel) else os.path.join(base, rel)


def questions_path(repo_root=None):
    """The **absolute path** of the open-questions directory (relative to the audited repo)."""
    return repo_path("REFLECT_QUESTIONS", repo_root)


def history_secs():
    """Append-only history section numbers parsed once from `REFLECT_HISTORY_SECS`."""
    return tuple(s for s in os.environ.get("REFLECT_HISTORY_SECS", "").split(",") if s)


def _text_of(name, files=None):
    """Read a file's text. Returns `None` = absent / unreadable (**not the empty
    string**).

    If `files` is given, use it (self-evidence injects a fake filesystem);
    otherwise read from `gate.GATE_REPO`. "Missing" and "empty file" collapse to
    None here -- callers skip in both cases, because "not in the list" and "the
    file is empty" mean the same in these three reconcilers (nothing to compare).
    """
    if files is not None:
        return files.get(name)
    p = os.path.join(gate.GATE_REPO, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def readme_problems(files=None):
    """REFLECT_* names that appear in the three-language READMEs (the
    REFLECT_READMES list) but are absent from the roster (documentation-side
    phantom defense). `files` injects a fake filesystem (for self-evidence)."""
    out = []
    for name in readme_names():
        text = _text_of(name, files)
        if text is None:
            continue
        for tok in sorted(set(_TOKEN_RE.findall(text))):
            if tok not in REGISTRY:
                out.append(M("knobs.readme_phantom", file=name, token=tok))
    return out




_KNOB_HELPERS = {
    "docs_names": "REFLECT_DOCS",
    "readme_names": "REFLECT_READMES",
    "questions_dir": "REFLECT_QUESTIONS",
    "questions_path": "REFLECT_QUESTIONS",
    "history_secs": "REFLECT_HISTORY_SECS",
    "served_langs": "REFLECT_LANGS",
    "state_name": "REFLECT_DOC",
    "default_timeout": "REFLECT_REPLAY_TIMEOUT",
    "timeout_with_status": "REFLECT_REPLAY_TIMEOUT",
}


def _docstring_const_ids(tree):
    import ast  # noqa: PLC0415
    ids = set()
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (n.body and isinstance(n.body[0], ast.Expr)
                and isinstance(getattr(n.body[0], "value", None), ast.Constant)):
            ids.add(id(n.body[0].value))
    return ids


def _is_decl_stmt(stmt):
    import ast  # noqa: PLC0415
    return isinstance(stmt, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id in ("GATE", "MODULE") for t in stmt.targets)


def _is_test_stmt(stmt):
    import ast  # noqa: PLC0415
    return isinstance(stmt, ast.FunctionDef) and stmt.name.startswith(("_cases", "_fixture"))


def _read_knobs_ast(text):
    """Knobs read in production code (via literal `REFLECT_*` or `knobs.*` helper calls)."""
    import ast  # noqa: PLC0415
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set(_TOKEN_RE.findall(text))
    doc_ids = _docstring_const_ids(tree)
    out = set()
    for stmt in tree.body:
        if _is_test_stmt(stmt) or _is_decl_stmt(stmt):
            continue
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in doc_ids and _TOKEN_RE.fullmatch(node.value)):
                out.add(node.value)
            elif isinstance(node, ast.Call):
                fn = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if fn in _KNOB_HELPERS:
                    out.add(_KNOB_HELPERS[fn])
    return out


def declared_vs_read_problems(gates, sources=None):
    """C4 reconciliation (1): declared knobs == knobs read in production AST."""
    out = []
    for g in gates:
        declared = set(g.get("knobs") or ())
        text = _text_of(g["file"], sources)
        if text is None:
            continue
        read = _read_knobs_ast(text)
        if not declared and not read:
            continue
        ghost = sorted(declared - read)
        if ghost:
            out.append(M("knobs.declared_not_read", file=g["file"], knobs=", ".join(ghost)))
        undecl = sorted(read - declared)
        if undecl:
            out.append(M("knobs.read_not_declared", file=g["file"], knobs=", ".join(undecl)))
    return out


def _kind_vocabulary_used(registry):
    """Kinds actually used by the roster."""
    return {kind for kind, _d, _w in registry.values()}


def _kind_vocabulary_reports(used, existence_kinds):
    """Report each roster kind the checking half does not handle.

    `number` / `flag` / `value` are legal kinds with a vacuously absent
    existence check, so they are listed explicitly in `existence_kinds`; a new
    registered kind without a matching arm reports here.
    """
    return [M("knobs.kind_unhandled", kind=kind)
            for kind in sorted(used - set(existence_kinds))]


def kind_vocabulary_problems(existence_kinds=None, registry=None):
    """C4 reconciliation (5): the kind vocabulary's **two producers** must agree.

    `existence_kinds` is injectable (fake vocabulary for self-evidence); the
    default pins the half that does the checking (`check_envfile` is the
    consumer). `registry` is injectable for the same reason. Each unhandled
    registered kind reports `knobs.kind_unhandled`.
    """
    reg = REGISTRY if registry is None else registry
    if existence_kinds is None:
        existence_kinds = ("file", "list", "dir", "number", "flag", "value")
    return _kind_vocabulary_reports(_kind_vocabulary_used(reg), existence_kinds)


def registry_vs_readme_problems(tables=None, names=None):
    """C4 reconciliation (2): every registered knob needs a README config row.

    `tables` is an injectable `{name: text}` seam; `names` is an injectable
    **pinned list**. Without `names`, the list comes from `readme_names()` and
    reads `REFLECT_READMES`: self-evidence would then depend on the machine's
    environment. A judgment must not read the environment to decide how many
    rounds it runs. Missing rows yield `knobs.readme_missing_rows` per README.
    """
    out = []
    for name in (readme_names() if names is None else names):
        text = _text_of(name, tables)
        if text is None:
            continue
        missing = _missing_rows(text)
        if missing:
            out.append(M("knobs.readme_missing_rows",
                         file=name, knobs=", ".join(missing)))
    return out


_README_ROW = re.compile(r"\|\s*`(REFLECT_[A-Z0-9_]+)`\s*\|")


def _missing_rows(text):
    """Which registered knobs are missing from the config table. **Empty table =>
    empty** (not a config-table shape; no false positive)."""
    have = set(_README_ROW.findall(text))
    if not have:
        return []
    return sorted(k for k in REGISTRY if k not in have)


# -- Self-evidence: shape guards on the roster itself (a broken registry = broken
# judgment data for every consumer) ----------------------------------------------

def _load_semantic_tables(langs):
    """Load each installed pack. Broken / empty pack => `{}` (semantic completeness
    cannot be proven; not allowed to go green)."""
    tables = {}
    for lang in langs:
        try:
            tables[lang] = load_pack(lang)
        except Exception:                                # noqa: BLE001
            return {}
    # Zero-value guard: no pack installed at all => not "complete", just not installed
    if not tables or not any(tables.values()):
        return {}
    return tables


def _all_packs_have_codes(tables, codes):
    """(a) Every pack must contain **all** semantic codes (a dropped entry => users
    there see a bare code)."""
    return all(all(c in table for c in codes)
               for table in tables.values())


def _all_packs_render_text(tables):
    """Every pack actually renders sentences (not falling back to codes)."""
    for lang in sorted(tables):
        with bind(Catalog.load(lang, {lang: tables[lang]})):
            if any(str(w) == w.code for _k, _d, w in REGISTRY.values()
                   if isinstance(w, _Semantic)):
                return False
    return True


def _semantic_packs_intact(langs=None):
    """Every installed pack must carry all semantics and render them as text.

    `langs=None` uses `installed_langs()`, so single-pack installations are
    legal. Broken / empty packs, missing codes, placeholder drift or bare-code
    rendering => False. Load / code set / placeholders / rendering are separate
    helpers; no stage passes vacuously.
    """
    langs = installed_langs() if langs is None else list(langs)
    codes = [w.code for _k, _d, w in REGISTRY.values()
             if isinstance(w, _Semantic)]
    if not codes:
        return False                        # semantics all gone = roster broken; not green
    tables = _load_semantic_tables(langs)
    if not tables:
        return False
    if not _all_packs_have_codes(tables, codes):
        return False
    # (b) Placeholder-name consistency **goes through the same reconciler**
    # (the same judgment as `pack_sync_problems`: write the loop twice and the
    # rules will drift -- C4).
    if pack_sync_problems(discovery=lambda: sorted(tables),
                          loader=lambda l: tables[l]):
        return False
    return _all_packs_render_text(tables)


def _discovery_sees_planted_lang():
    """Plant a half-broken language pack in temp `REFLECT_I18N`; discovery must flag it."""
    import json  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    base = a_pack_lang()
    if not base:
        return True
    zh = load_pack(base)
    if not zh:
        return False
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, base), exist_ok=True)
        with open(os.path.join(d, base, "all.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(zh, fh, ensure_ascii=False)
        planted = "probe-lang"
        os.makedirs(os.path.join(d, planted), exist_ok=True)
        half = dict(list(zh.items())[: len(zh) // 2])
        with open(os.path.join(d, planted, "all.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(half, fh, ensure_ascii=False)
        prev = os.environ.get("REFLECT_I18N")
        os.environ["REFLECT_I18N"] = d
        try:
            got = installed_langs()
            probs = pack_sync_problems()
            return planted in got and probs != []
        finally:
            if prev is None:
                os.environ.pop("REFLECT_I18N", None)
            else:
                os.environ["REFLECT_I18N"] = prev
    finally:
        shutil.rmtree(d, True)


def _looks_like_pack(path):
    """Does this json **look like** a language pack by content? (the single-file
    shape's judgment)

    A language pack's signature: keys are `x.y`-shaped codes, values are strings
    (usually with `%(...)` placeholders). A json that is not a language pack
    (config / notes / metadata) must not be mistaken for a language.
    """
    import json  # noqa: PLC0415
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False        # a broken file is not a language pack (load_pack reports broken packs per installed language)
    if not isinstance(data, dict) or not data:
        return False
    dotted = sum(1 for k in data if isinstance(k, str) and "." in k)
    return dotted >= max(1, len(data) // 2)


def installed_langs():
    """Discover installed language packs containing `.json` pack files."""
    base = pack_dir()
    out = set()
    try:
        for n in sorted(os.listdir(base)):
            p = os.path.join(base, n)
            if os.path.isdir(p) and any(x.endswith(".json")
                                        for x in os.listdir(p)):
                out.add(n)
            elif n.endswith(".json") and _looks_like_pack(p):
                out.add(n[:-len(".json")])
    except OSError as e:
        # ⚠️ **Never fabricate a 0** (AGENTS discipline 7: if it can't be read,
        # say so; never invent). This used to `return []`, collapsing "broken
        # permissions / unreadable directory" and "no packs installed" into the
        # same false value => reconcilers all green, roster all green -- the worst
        # member of the "deployed != running" family (observed: a chmod 000 pack
        # directory gave pack_sync_problems() == []).
        raise PacksUnreadable(str(e)) from e
    return sorted(out)


class PacksUnreadable(RuntimeError):
    """The pack directory itself is unreadable (permissions / I-O). **Distinct
    from "no packs installed"**: the latter is legal, the former is an incident."""



def _environ_get_knob(node):
    """If `node` is `os.environ.get('REFLECT_...', ...)` return `(knob, default_node|None)`."""
    import ast  # noqa: PLC0415
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get" and node.args):
        return None, None
    arg0 = node.args[0]
    if not (isinstance(arg0, ast.Constant) and isinstance(arg0.value, str)
            and arg0.value.startswith("REFLECT_")):
        return None, None
    return arg0.value, (node.args[1] if len(node.args) > 1 else None)


def _inline_default_problems(name, tree):
    """Report hardcoded non-empty default literals for `REFLECT_*` outside `knobs.py`."""
    import ast  # noqa: PLC0415
    if os.path.basename(name) == "knobs.py":
        return []
    out = []
    for stmt in tree.body:
        if _is_test_stmt(stmt):
            continue
        for node in ast.walk(stmt):
            knob, dflt = _environ_get_knob(node)
            if (knob and isinstance(dflt, ast.Constant) and isinstance(dflt.value, str)
                    and dflt.value.strip() != ""):
                out.append(M("knobs.inline_default_literal", file=name,
                             lineno=node.lineno, knob=knob, literal=dflt.value))
    return out


def dead_default_problems(py_dir=None):
    """AST checks: unused `DEFAULT_*` constants and inline `REFLECT_*` fallback literals."""
    import ast  # noqa: PLC0415
    d = py_dir if py_dir is not None else gate.zdir()
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for n in names:
        if not n.endswith(".py"):
            continue
        try:
            tree = ast.parse(open(os.path.join(d, n), encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        defined = {t.id for node in tree.body if isinstance(node, ast.Assign)
                   for t in node.targets
                   if isinstance(t, ast.Name) and t.id.startswith("DEFAULT_")}
        loaded = {node.id for node in ast.walk(tree)
                  if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        for dead in sorted(defined - loaded):
            out.append(M("knobs.dead_default", file=n, name=dead))
        out += _inline_default_problems(n, tree)
    return out


def _dead_default_ok():
    """A `DEFAULT_X` defined but never Loaded => must report; used => must not."""
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        dead = ("DEFAULT_X = 'v'\n"
                "def run():\n"
                "    return os.environ.get('K') or 'hardcoded'\n")
        live = ("DEFAULT_X = 'v'\n"
                "def run():\n"
                "    return os.environ.get('K') or DEFAULT_X\n")
        # First with only the "dead" one
        with open(os.path.join(d, "check_dead.py"), "w", encoding="utf-8") as fh:
            fh.write(dead)
        got_dead = [p.code for p in dead_default_problems(py_dir=d)]
        # Switch to the "live" one => should not report
        with open(os.path.join(d, "check_dead.py"), "w", encoding="utf-8") as fh:
            fh.write(live)
        got_live = dead_default_problems(py_dir=d)
        return got_dead == ["knobs.dead_default"] and got_live == []
    finally:
        shutil.rmtree(d, True)


def a_pack_lang():
    """Pick an **installed** language pack name for self-evidence; none => None.

    Rendering-fidelity judgments do not depend on which language it is, so this
    is discovered, never a hard-coded `zh`: a single-pack installation is legal.
    """
    langs = installed_langs()
    return langs[0] if langs else None


_CODE_RE = re.compile(r'M\("([a-z][a-z0-9_.]+)"')
# `_Semantic(...)` also produces user-visible messages (lazily rendered); counted too.
_SEM_RE = re.compile(r'_Semantic\("([a-z][a-z0-9_.]+)"')

# Self-evidence / documentation-only codes: they are **never** rendered to users
# (they only appear in `--selftest` assertions, or as docstring examples).
# Declared via an **explicit prefix** instead of a hand-written roster -- adding
# such a code only requires using this prefix (discovered, doesn't drift).
_SELFTEST_CODE_PREFIXES = ("probe.", "gate.off.body")


def used_codes(py_dir=None):
    """Message codes the core source would **actually send to users**
    (`M("...")` / `_Semantic("...")`).

    **Discovered**: scan the source, keep no written roster; this is the
    reference surface for the "pack completeness" judgment (a set-difference
    between packs cannot see a shared omission). Docstrings are stripped, so
    examples in docs are not counted; `_SELFTEST_CODE_PREFIXES` codes are
    self-evidence-only and also excluded.
    """
    import ast  # noqa: PLC0415
    d = py_dir if py_dir is not None else gate.zdir()
    out = set()
    for _n, src in _py_sources(d):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        # docstring constants (exempt: examples are not output)
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docs.add(doc)
        text_wanted = argparse_strip(src, docs)
        out |= set(_CODE_RE.findall(text_wanted))
        out |= set(_SEM_RE.findall(text_wanted))
    return {c for c in out
            if not any(c.startswith(p) for p in _SELFTEST_CODE_PREFIXES)}


def argparse_strip(src, docs):
    """Erase docstring bodies from the source (coarse replacement only; sufficient
    for scanning)."""
    for doc in docs:
        if doc:
            src = src.replace(doc, "")
    return src


def _unreadable_dir_is_loud():
    """Pack directory unreadable => must report `pack_unreadable`; must not pass as
    "zero packs" (a legal state)."""
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    if os.name == "nt":
        # ⚠️ **On Windows `chmod 0` does not prevent reading**: `os.chmod` there
        # only toggles the read-only bit, and `listdir` still gets in. So the
        # fixture "make an unreadable directory" cannot even be built on
        # Windows -- this test can't test anything (stated as not applicable,
        # not a silent pass).
        # Observed: on the CI Windows leg, `knobs` self-test ran 28 PASS / 1
        # FAIL, and the red one was exactly this.
        return True
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return True        # root ignores permission bits; untestable (stated as not applicable)
    d = tempfile.mkdtemp()
    try:
        os.chmod(d, 0)
        prev = os.environ.get("REFLECT_I18N")
        os.environ["REFLECT_I18N"] = d
        try:
            try:
                installed_langs()
            except PacksUnreadable:
                return True
            return False
        finally:
            if prev is None:
                os.environ.pop("REFLECT_I18N", None)
            else:
                os.environ["REFLECT_I18N"] = prev
    finally:
        os.chmod(d, 0o755)
        shutil.rmtree(d, True)


def pack_coverage_problems(codes=None, loader=None, discovery=None):
    """C4 reconciliation (4): **every code used by the source must exist in every
    installed pack**.

    The zh↔en set-difference comparison (`pack_sync_problems`) cannot see "both
    sides missing the same thing"; a missing code is a bare code on screen with
    a normal exit code. The reference surface is the **source** (`used_codes()`),
    not another pack -- so two packs drifting together are still caught. Zero
    packs is a legal state => nothing to check; return empty.

    `discovery` decides "which languages count" (default `installed_langs()`),
    through the same channel as `pack_sync_problems`. `loader` and `codes` are
    injectable for self-evidence.
    """
    load = loader if loader is not None else load_pack
    codes = used_codes() if codes is None else set(codes)
    try:
        langs = list((discovery or installed_langs)())
    except PacksUnreadable as e:
        return [M("knobs.pack_unreadable", lang="*", error=e)]
    served = served_langs()
    if served:
        # Issue #35: only declared service languages carry the completeness
        # promise. Other installed packs are self-evidence samples -- a missing
        # key there has no reader to show a bare code to, so demanding it
        # fabricated a victim (issue #35's measured cost: one zh-only repo
        # writing "Chinese German" nobody reads, gate green).
        missing_service = [l for l in served if l not in langs]
        out = []
        if missing_service:
            # A declared service language with no pack installed IS a real
            # break: the declared reader would see bare codes.
            return [M("knobs.pack_missing_code", lang=l,
                      count=len(codes) or 1,
                      codes="*") for l in sorted(missing_service)]
        langs = [l for l in langs if l in served]
    if not codes or not langs:
        return []                       # zero packs / zero codes: no comparable sides
    out = []
    for lang in sorted(langs):
        try:
            table = load(lang)
        except Exception as e:                           # noqa: BLE001
            return [M("knobs.pack_unreadable", lang=lang, error=e)]
        missing = sorted(codes - set(table))
        if missing:
            out.append(M("knobs.pack_missing_code",
                         lang=lang, count=len(missing),
                         codes=", ".join(missing[:8])))
    return out


def pack_sync_problems(loader=None, discovery=None):
    """C4 reconciliation (3): every language pack's **key set** and **placeholder
    names** must agree.

    `discovery` decides "which languages count" (default `installed_langs()`).
    To pin languages, inject `discovery`, going through the same seam as
    production.
    `loader` is injectable (fake packs for self-evidence); the default is
    `i18n.load_pack` (the **merged view** -- same table as the real loader;
    reading single shards would fork from the loader).
    """
    load = loader if loader is not None else load_pack
    try:
        langs = list((discovery or installed_langs)())
    except PacksUnreadable as e:
        return [M("knobs.pack_unreadable", lang="*", error=e)]
    served = served_langs()
    if served:
        # Issue #35: key-set agreement is only promised **between service
        # languages**. Non-service packs are self-evidence samples; demanding
        # they match invented a reader that does not exist.
        served_present = [l for l in served if l in langs]
        if served_present:
            langs = served_present
        # (declared-but-absent is pack_coverage_problems' report, not this one)
    tables, err = _load_tables(langs, load)
    if err:
        return err
    early = _empty_pack_verdict(tables)
    if early is not None:
        return early
    ref_lang = sorted(tables)[0]
    ref = tables[ref_lang]
    out = []
    for lang in sorted(tables):
        # Brace-vs-percent is judged for **every** pack including the reference
        # one: `_render` is percent-only, so a braced template is dead in all
        # languages equally and comparing two packs would agree on nonsense.
        out += _brace_template_problems(lang, tables[lang])
        if lang == ref_lang:
            continue
        out += _key_set_problems(lang, ref_lang, ref, tables[lang])
        out += _placeholder_problems(lang, ref_lang, ref, tables[lang])
    return out


def _empty_pack_verdict(tables):
    """The two verdicts for "zero packs / broken packs". Returns `None` = keep
    comparing.

    **Zero packs is a legal state**: no pack installed => return empty (no
    report). "A pack was requested but can't be read" is another matter,
    handled by `pack_unreadable` / the activation path's `i18n.pack_absent`.
    Installed but all tables empty => a broken pack: report
    `knobs.pack_sync_empty`.
    """
    if not tables:
        return []
    if not any(tables.values()):
        return [M("knobs.pack_sync_empty", pack_dir=pack_dir())]
    return None


def _load_tables(langs, load):
    """Load all installed packs. Returns `(tables, error list or None)`.

    ⚠️ **Must catch `load_pack` exceptions**: `pack_sync_problems` can be called
    outside `activate_or_fatal()` (the `registry --gates` roster reconciliation
    is one such call), so an escaping exception would violate the rc contract
    (broken config = FATAL rc 2). A load failure yields `({}, [problem])`;
    success yields `(tables, None)`.
    """
    tables = {}
    for lang in langs:
        try:
            tables[lang] = load(lang)
        except Exception as e:                           # noqa: BLE001
            return {}, [M("knobs.pack_unreadable", lang=lang, error=e)]
    return tables, None


def _key_set_problems(lang, ref_lang, ref, other):
    """Key-set difference: keys only the reference has / only this pack has."""
    out = []
    only_ref = sorted(set(ref) - set(other))
    only_other = sorted(set(other) - set(ref))
    if only_ref:
        out.append(M("knobs.pack_missing_keys", lang=lang, reference=ref_lang,
                     keys=", ".join(only_ref[:8]), count=len(only_ref)))
    if only_other:
        out.append(M("knobs.pack_extra_keys", lang=lang, reference=ref_lang,
                     keys=", ".join(only_other[:8])))
    return out


# `_render` does `table[code] % params` -- percent style only. A template that
# says `{count}` is therefore never interpolated: the user sees the braces
# verbatim and no check notices, because the placeholder comparison below only
# looks for `%(name)s` on both sides. Measured: three language packs, twelve
# entries, all written with braces while the call sites passed percent kwargs.
_BRACE_RE = re.compile(r"\{[a-z_][a-z0-9_]*\}")


def _brace_template_problems(lang, table):
    """Templates using `{name}` instead of `%(name)s` -- never interpolated."""
    return [M("knobs.pack_brace_template", lang=lang, key=code, text=v[:60])
            for code, v in sorted(table.items())
            if isinstance(v, str) and _BRACE_RE.search(v)]


def _placeholder_problems(lang, ref_lang, ref, other):
    """Placeholder-name agreement: one difference => KeyError at render time (or
    worse, a silently dropped segment)."""
    out = []
    for code in sorted(set(ref) & set(other)):
        a = sorted(_PLACEHOLDER_RE.findall(ref[code]))
        b = sorted(_PLACEHOLDER_RE.findall(other[code]))
        if a == b:
            continue
        # The param must not be named `code`: `M(code, **params)`'s first
        # parameter is already named code, and a same-named kwarg raises
        # `TypeError: M() got multiple values` (observed hit).
        out.append(M("knobs.pack_placeholder_mismatch",
                     lang=lang, key=code, reference_lang=ref_lang,
                     expected_params=", ".join(a) or "-",
                     actual_params=", ".join(b) or "-"))
    return out


def _null_pack():
    """A context manager over an **explicit null pack** (self-evidence only)."""
    return bind(NULL)


def _semantics_can_red():
    """Does `_semantics_are_codes_under()` have teeth? Given a table that **won't
    render as codes** => must be False."""
    sem = [(k, w) for k, _d, w in REGISTRY.values() if isinstance(w, _Semantic)]
    if not sem:
        return False
    # Use a fake pack where "every code is translated into a sentence":
    # str(w) != w.code => should return False
    fake = {w.code: "SENTENCE %s" % w.code for _k, w in sem}
    return _semantics_are_codes_under(
        bind(Catalog.load("xx", {"xx": fake}))) is False


def _planted_red_when_blind():
    """Turn the discovery channel off (back to a hand-written list); the planted
    check must go red."""
    prev = installed_langs
    globals()["installed_langs"] = lambda: ["zh", "en"]     # pretend discovery is broken
    try:
        return _discovery_sees_planted_lang() is False
    finally:
        globals()["installed_langs"] = prev


def _semantics_are_codes_under(cm):
    """Under the `cm` language-pack scope, every knob semantic renders as a code
    (and is non-empty)."""
    sem = [(k, w) for k, _d, w in REGISTRY.values()
           if isinstance(w, _Semantic)]
    if not sem:
        return False                        # zero-value guard: semantics gone => roster broken
    cm.__enter__()
    try:
        return all(str(w) == w.code for _k, w in sem)
    finally:
        cm.__exit__(None, None, None)


def _cases_fixture(d):
    """Build fixture dir with a clean knob read and a constructed phantom token."""
    open(os.path.join(d, "good.py"), "w", encoding="utf-8").write(
        'X = os.environ.get("REFLECT_FACTS")\n')
    phantom = "REFLECT_" + "GHOSTX"
    open(os.path.join(d, "phantom.py"), "w", encoding="utf-8").write(
        '# a comment mentions the nonexistent knob ' + phantom + '\n')
    return {"d": d, "phantom": phantom}


def _cases_scan(fx):
    """See `_cases()`: 6 cases in this group."""
    d, phantom = fx["d"], fx["phantom"]
    return [
    # (a) normally no report
    ("knobs.registry_entry_shape",
     lambda: all(k in KINDS and isinstance(dflt, str) and w.strip()
                 for k, dflt, w in REGISTRY.values()) and len(REGISTRY) >= 20),
    ("knobs.scan_clean",
     lambda: scan_surface_problems() == []),
    ("knobs.real_tree_scan_clean", lambda: scan_surface_problems() == []),
    # (b) what must report, must report
    ("★ knobs.phantom_token",
     lambda: any(p.code == "knobs.phantom_token"
                 and p.params.get("token") == phantom
                 for p in scan_surface_problems(py_dir=d))),
    ("★ knobs.registry_empty", lambda: bool(REGISTRY)),
    ("knobs.phases_registered", lambda: "REFLECT_PHASES" in REGISTRY),
    ]


_README_TRIO = {"README.md": "x", "README.zh.md": "x", "README.de.md": "x"}


def _cases_readme_nominations():
    """An unregistered knob name appearing in a README (phantom defense) -- must
    report + normally silent."""
    return [
        ("knobs.readme_nominations_registered",
         lambda: readme_problems(files={
             "README.md": "uses REFLECT_FACTS and REFLECT_DOC.",
             "README.zh.md": "x", "README.de.md": "x"}) == []),
        ("knobs.real_readmes_clean", lambda: readme_problems() == []),
        ("\u2605 knobs.readme_phantom",
         lambda: any(x.code == "knobs.readme_phantom"
                     for x in readme_problems(files=dict(
                         _README_TRIO,
                         **{"README.md": "see " + "REFLECT_" + "GHOSTY" + "."})))),
    ]


def _cases_readme_declared_read():
    """Bidirectional `declared == read` reconciliation cases."""
    return [
        ("\u2605 knobs.declared_not_read",
         lambda: [p.code for p in declared_vs_read_problems(
             [{"file": "check_x.py", "knobs": ("REFLECT_FACTS",)}],
             sources={"check_x.py": "X = 1\n"})
         ] == ["knobs.declared_not_read"]
         and [p.params for p in declared_vs_read_problems(
             [{"file": "check_x.py", "knobs": ("REFLECT_FACTS",)}],
             sources={"check_x.py": "X = 1\n"})
         ] == [{"file": "check_x.py", "knobs": "REFLECT_FACTS"}]),
        ("knobs.declared_and_read_is_clean",
         lambda: declared_vs_read_problems(
             [{"file": "check_x.py", "knobs": ("REFLECT_FACTS",)}],
             sources={"check_x.py":
                      'X = os.environ.get("REFLECT_FACTS")\n'}) == []),
        ("★ knobs.read_not_declared",
         lambda: [p.code for p in declared_vs_read_problems(
             [{"file": "check_x.py", "knobs": ()}],
             sources={"check_x.py":
                      'X = os.environ.get("REFLECT_FACTS")\n'})]
         == ["knobs.read_not_declared"]),
    ]


def _cases_readme_rows():
    """Missing rows in the README config tables."""
    return [
        ("\u2605 knobs.readme_missing_rows",
         lambda: [p.code for p in registry_vs_readme_problems(
             tables=dict.fromkeys(_README_TRIO, "| `REFLECT_FACTS` | x |\n"),
             names=tuple(_README_TRIO))
         ] == ["knobs.readme_missing_rows"] * 3),
    ]


def _cases_readme_empty():
    """Empty-input guards for declared/read and README table reconcilers."""
    return [
        ("knobs.declared_vs_read_empty_in_scope",
         lambda: declared_vs_read_problems([{"file": "x.py", "knobs": ()}],
                                           sources={}) == []),
        ("knobs.registry_vs_readme_empty_tables",
         lambda: registry_vs_readme_problems(tables={}) == []),
    ]


def _cases_readme(fx):
    """Assemble README and declaration reconciliation cases."""
    return (_cases_readme_nominations() + _cases_readme_declared_read()
            + _cases_readme_rows() + _cases_readme_empty())


def _cases_semantics(fx):
    """Knob semantic rendering cases."""
    return [
("knobs.semantic_renders_as_code_by_default",
 lambda: _semantics_are_codes_under(_null_pack())),
("★ knobs.semantics_are_codes_can_red", lambda: _semantics_can_red()),
("knobs.semantics_present_in_real_packs",
 lambda: not installed_langs() or _semantic_packs_intact()),
    ]


def _cases_sync_rules():
    """Language-pack diff rules (missing keys, placeholders, extra keys, empty pack)."""
    return [
        ("\u2605 knobs.pack_missing_keys",
         lambda: [p.code for p in pack_sync_problems(
             discovery=lambda: ("zh", "en"), loader=lambda l: {
                 "zh": {"a": "x"}, "en": {"a": "x", "b": "y"}}[l])
         ] == ["knobs.pack_missing_keys"]),
        ("\u2605 knobs.pack_brace_template",
         lambda: [p.code for p in pack_sync_problems(
             discovery=lambda: ("zh", "en"), loader=lambda l: {
                 "zh": {"a": "x {k}"}, "en": {"a": "x {k}"}}[l])
         ] == ["knobs.pack_brace_template", "knobs.pack_brace_template"]),
        ("knobs.pack_percent_template_ok",
         lambda: pack_sync_problems(
             discovery=lambda: ("zh", "en"), loader=lambda l: {
                 "zh": {"a": "x %(k)s"}, "en": {"a": "x %(k)s"}}[l]) == []),
        ("\u2605 knobs.pack_placeholder_mismatch",
         lambda: [p.code for p in pack_sync_problems(
             discovery=lambda: ("zh", "en"), loader=lambda l: {
                 "zh": {"a": "x %(k)s"}, "en": {"a": "x %(j)s"}}[l])
         ] == ["knobs.pack_placeholder_mismatch"]),
        ("\u2605 knobs.pack_extra_keys",
         lambda: [p.code for p in pack_sync_problems(
             discovery=lambda: ("zh", "en"), loader=lambda l: {
                 "zh": {"a": "x", "b": "y"}, "en": {"a": "x"}}[l])
         ] == ["knobs.pack_extra_keys"]),
        ("\u2605 knobs.pack_sync_empty",
         lambda: [p.code for p in pack_sync_problems(
             discovery=lambda: ("zh", "en"), loader=lambda l: {})]
         == ["knobs.pack_sync_empty"]),
    ]


def _cases_sync_coverage():
    """Pack discovery, coverage completeness, `REFLECT_LANGS` scoping, and unreadable error cases."""
    return [
        ("\u2605 knobs.pack_sync_sees_every_installed_lang",
         lambda: _discovery_sees_planted_lang()),
        ("knobs.coverage_real_repo_clean",
         lambda: pack_coverage_problems() == []),
        ("\u2605 knobs.coverage_honours_discovery",
         lambda: (lambda seen: ([p.code for p in pack_coverage_problems(
             codes={"a.b"}, discovery=lambda: seen.append(1) or ["zz"],
             loader=lambda l: {})] == ["knobs.pack_missing_code"] and
             len(seen) == 1))([])),
        ("\u2605 knobs.pack_missing_code",
         lambda: [p.code for p in pack_coverage_problems(
             codes={"a.b", "c.d"}, discovery=lambda: ("zh", "en"),
             loader=lambda l: ({"a.b": "x", "c.d": "y"} if l == "en"
                               else {"a.b": "x"}))
         ] == ["knobs.pack_missing_code"]),
        ("★ knobs.coverage_served_unset_judges_all", lambda: _served_case(
            None, ["knobs.pack_missing_code"])),
        ("★ knobs.coverage_served_narrows_judgement", lambda: _served_case(
            "en", [])),
        ("★ knobs.coverage_served_narrowing_is_from_knob", lambda: _served_case(
            None, ["knobs.pack_missing_code"])),
        ("★ knobs.coverage_served_absent_is_red", lambda: _served_case(
            "de,en", ["knobs.pack_missing_code"])),
        ("\u2605 knobs.pack_unreadable_on_oserror",
         lambda: _unreadable_dir_is_loud()),
    ]


def _cases_sync(fx):
    """See `_cases()`: 9 cases in this group.

    Two groups (rules / discovery and coverage): the former injects discovery to
    test the rules themselves; the latter passes **no** discovery and tests
    "that it really gets called" -- mixed together, a reader cannot tell which
    class an assertion belongs to.
    """
    return _cases_sync_rules() + _cases_sync_coverage()


def _cases_pack(fx):
    """The 12 language-pack judgments: 3 semantics + 9 sync/coverage."""
    return (
        _cases_semantics(fx)
        + _cases_sync(fx)
    )


def _cases_registry(fx):
    """Registry, default-producer, flag-folding, and inline-default cases."""
    return [
    ("knobs.real_packs_in_sync",
     lambda: not installed_langs() or pack_sync_problems() == []),
    ("★ knobs.discovery_planted_can_red", lambda: _planted_red_when_blind()),
    ("★ knobs.dead_default", lambda: _dead_default_ok()),
    ("★ knobs.docs_names_follow_registry", lambda: _docs_names_follows()),
    ("★ knobs.flag_three_states", lambda: _flag_case()),
    ("knobs.kind_vocabulary_clean",
     lambda: kind_vocabulary_problems() == []),
    ("★ knobs.kind_unhandled",
     lambda: [p.code for p in kind_vocabulary_problems(
         registry={"X": ("ghostkind", "",
                         _Semantic("knobs.sem.reflect_doc"))})
     ] == ["knobs.kind_unhandled"]
     and [p.params for p in kind_vocabulary_problems(
         registry={"X": ("ghostkind", "",
                         _Semantic("knobs.sem.reflect_doc"))})
     ] == [{"kind": "ghostkind"}]),
    ("knobs.kind_vocabulary_empty_registry",
     lambda: kind_vocabulary_problems(registry={}) == []),
    ("knobs.get_and_helpers",
     lambda: get("REFLECT_FACTS") == REGISTRY["REFLECT_FACTS"][1]
     and questions_dir() == REGISTRY["REFLECT_QUESTIONS"][1]
     and repo_path("REFLECT_FACTS", "/r") == "/r/" + REGISTRY["REFLECT_FACTS"][1]
     and repo_path("REFLECT_INVARIANTS", "/r") is None
     and isinstance(history_secs(), tuple)),
    ("★ knobs.inline_default_literal_detected",
     lambda: _inline_default_case()),
    ]


def _inline_default_case():
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "check_bad.py"), "w", encoding="utf-8") as fh:
            fh.write('import os\nX = os.environ.get("REFLECT_FACTS", "FACTS.json")\n')
        return [p.code for p in dead_default_problems(py_dir=d)] == [
            "knobs.inline_default_literal"]
    finally:
        shutil.rmtree(d, True)


def _flag_case():
    """`flag()`'s three states: true / false / unset, at least one spelling each
    (including case folding).

    ⚠️ `TRUE` (uppercase) must count as true -- that is exactly the hole in the
    doc-side vocabulary. Empty string and unset must both be `None` (= unset;
    the caller applies its own default), not False.
    """
    import os  # noqa: PLC0415
    name = "REFLECT_" + "FLAG_PROBE"
    prev = os.environ.get(name)
    try:
        seen = {}
        for v in ("1", "TRUE", "Yes", "ON"):
            os.environ[name] = v
            seen[v] = flag(name)
        for v in ("0", "FALSE", "No", "OFF"):
            os.environ[name] = v
            seen[v] = flag(name)
        os.environ[name] = ""
        empty = flag(name)
        os.environ.pop(name)
        unset = flag(name)
        return (all(seen[v] is True for v in ("1", "TRUE", "Yes", "ON"))
                and all(seen[v] is False for v in ("0", "FALSE", "No", "OFF"))
                and empty is None and unset is None)
    finally:
        if prev is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prev


def _docs_names_follows():
    """The scanning gates' default surface must equal the registry.

    ⚠️ The judgment is at the **consumer end** -- which files `check_stale` /
    `check_retractions` scan when the knob is unset -- not `docs_names()` reading
    the registry (a circular comparison would stay green when both sides drift).
    With the knob set it must not fall back to the registry; otherwise the knob
    would be dead. Returns False on either failure.
    """
    import os  # noqa: PLC0415
    registered = [s.strip() for s in REGISTRY["REFLECT_DOCS"][1].split(",")
                  if s.strip()]
    prev = os.environ.get("REFLECT_DOCS")
    try:
        os.environ.pop("REFLECT_DOCS", None)
        scanned = _docs_scanned_by_gates()
        if scanned != registered:
            return False
        # With the knob set it must **not** fall back to the registry (otherwise
        # the user cannot change it; the knob would be dead)
        os.environ["REFLECT_DOCS"] = "only.md"
        return _docs_scanned_by_gates() == ["only.md"]
    finally:
        if prev is None:
            os.environ.pop("REFLECT_DOCS", None)
        else:
            os.environ["REFLECT_DOCS"] = prev


def _docs_scanned_by_gates():
    """Actual doc lists scanned by `check_stale` and `check_retractions`."""
    import check_retractions  # noqa: PLC0415
    import check_stale  # noqa: PLC0415
    stale = list(check_stale.scanned_docs())
    retr = list(check_retractions.scanned_docs())
    return stale if stale == retr else []


def _served_case(knob_value, expect_codes):
    """Shared body for the four REFLECT_LANGS coverage cases (issue #35).

    Sets the knob (or clears it), runs one coverage call over a two-pack
    fixture, restores the environment, and compares the problem codes with the
    expectation. `expect_codes=[]` = silent (non-service gaps have no reader);
    non-empty = the declared reader really would see bare codes.
    """
    import os  # noqa: PLC0415
    prev = os.environ.pop("REFLECT_LANGS", None)
    if knob_value is not None:
        os.environ["REFLECT_LANGS"] = knob_value
    try:
        codes = [p.code for p in pack_coverage_problems(
            codes={"a.b", "c.d"}, discovery=lambda: ("zh", "en"),
            loader=lambda l: ({"a.b": "x", "c.d": "y"} if l == "en"
                              else {"a.b": "x"}))]
        return codes == expect_codes
    finally:
        os.environ.pop("REFLECT_LANGS", None)
        if prev is not None:
            os.environ["REFLECT_LANGS"] = prev


def _cases():
    """Assemble the four fixture groups. **Assembly only** -- the judgments live in
    the group functions."""
    import atexit  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    fx = _cases_fixture(d)
    return (
        _cases_scan(fx)
        + _cases_readme(fx)
        + _cases_pack(fx)
        + _cases_registry(fx)
    )


MODULE = module_meta("Knob registry", "the single roster of REFLECT_* + roster self-consistency judgments", selftest=True)


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from gate import main_selftest_or  # noqa: PLC0415

    def _run(argv):
        # `--list`: the **official exit** for users to look up knob semantics
        # (AGENTS.md routes here). It did not exist before -- the docs pointed at
        # a command with rc=2 (caught in review).
        if "--list" in argv:
            print(knobs_table())
            return 0
        if argv and argv[0] in ("--help", "-h"):
            print(M("knobs.usage"), file=sys.stderr)
            return 0
        print(M("knobs.module_only"), file=sys.stderr)
        print(M("knobs.usage"), file=sys.stderr)
        return 2
    # Self-test titles are a **developer interface** (check_i18n's exempt surface
    # (b)); by design they stay in one language.
    sys.exit(main_selftest_or(sys.argv[1:],
                              M("gate.title.knobs"),
                              _cases, _run))

