#!/usr/bin/env python3
"""Roster criteria: **machine reconciliation of "which things must agree"** (half of
registry's criteria).

## Why this was split out of registry.py

`registry.py` was doing four jobs at once: discovery (AST-reading declaration
lines), **reconciliation criteria**, rendering machine blocks, and the CLI. The
criteria were 1145 lines / 46 functions -- the bulk of it, and evolving on a rhythm
completely different from discovery's:

  - the discovery surface changes as gates are added (fields of `GATE = meta(...)`);
  - the criteria surface changes as "pairs that must agree" are added (C4
    reconcilers).

Mixed in one file, changing either side meant finding a spot in an 1800-line file.
After the split, `registry.py` keeps discovery + rendering + CLI; `criteria.py`
holds only criteria.

## The six reconciliations housed here

    dead_interface_problems      public functions with zero consumers (zombie interfaces)
    shell_surface_problems       .sh whitelist (guard of the all-Python goal)
    trailing_newline_problems    files must end with a newline (the gap between `py_lines`'s two measuring methods)
    off_reason_problems          gates that can off must declare a reason (three-way + truthfulness + location)
    path_rule_problems           "the tool's zreflect/" may have exactly one source (C4 (8))
    dependency_coverage_problems consumed platform functions must have assertions (C4 (9))

## Interface

    problems(*args) -> aggregation of the criteria (called by `registry.problems()`)

Each is a **pure function** (injectable `sources=` / `zdir=`); selftests live in
`registry._cases_*`.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shlex

import gate  # noqa: E402
import knobs  # noqa: E402

# A token that "looks like a filename" (`off_reason` mentioning `foo.json` and such).
# Brought over from `registry.py` when it moved -- it is criterion data for
# `off_reason_problems`.
_FILE_TOKEN = re.compile(r"[A-Za-z0-9_.-]+\.[A-Za-z0-9]+")
from i18n import M  # noqa: E402

MUST_REASON_MIN = 8      # minimum length of an off reason (same discipline as `PINNED:`)


# Shell files allowed to exist (**bounded whitelist**). Under the all-Python goal,
# shell is the exception; every exception needs a reason. New arrivals (or
# unregistered ones) => report.
ALLOWED_SHELL = (
    # Assessment recorder template (issue #41): a sourced shell helper.
    "reflect-hooks/quality-record.sh",
)

_REASON_BASES = ("",)


def _reason_files(reason, repo_root=None):
    """Filenames mentioned in an `off_reason` -> `[(name, exists at repo root)]`."""
    if not reason:
        return []
    root = repo_root if repo_root is not None else gate.GATE_REPO
    out = []
    for tok in _FILE_TOKEN.findall(str(reason)):
        found = any(os.path.exists(os.path.join(root, base, tok))
                    for base in _REASON_BASES)
        out.append((tok, found))
    return out


_ENTRY_INTERFACES = frozenset({"main", "run", "problems"})
# Public helpers whose explicit purpose is cross-module selftest support.
_TEST_HELPERS = frozenset({"a_pack_lang", "bind", "raises"})


def _callees(node, fns):
    """Function names inside `fns` directly referenced as `Name` calls/loads in `node`."""
    return [sub.id for sub in ast.walk(node)
            if isinstance(sub, ast.Name) and sub.id in fns]


def _bfs_fns(fns, roots, skip=()):
    """BFS over `fns` starting at `roots`, never entering names in `skip`."""
    seen = {n.name for n in roots if n.name not in skip}
    queue = [n for n in roots if n.name not in skip]
    while queue:
        cur = queue.pop()
        for t in _callees(cur, fns):
            if t not in seen and t not in skip:
                seen.add(t)
                queue.append(fns[t])
    return seen


def _is_main_if(stmt):
    """Is `stmt` an `if __name__ == '__main__':` guard?"""
    return isinstance(stmt, ast.If) and "__main__" in ast.unparse(stmt.test)


def _test_only_fn_names(tree):
    """`_cases*` / `_fixture*` / `_selftest` and their private test-only helpers."""
    fns = {n.name: n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    test_prefix = ("_cases", "_fixture")
    is_test = {n for n in fns if n.startswith(test_prefix) or n == "_selftest"}
    prod_roots = [n for name, n in fns.items() if not name.startswith("_")]
    for stmt in tree.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _is_main_if(stmt):
            prod_roots.extend(fns[t] for t in _callees(stmt, fns) if t not in is_test)
    prod = _bfs_fns(fns, prod_roots, skip=is_test)
    return _bfs_fns(fns, [fns[n] for n in is_test], skip=prod)


def _test_fn_names(tree):
    """Transitive closure of `_cases*` / `_fixture*` functions in `tree`."""
    fns = {n.name: n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    roots = [n for name, n in fns.items() if name.startswith(("_cases", "_fixture"))]
    return _bfs_fns(fns, roots)


def _rule_cmd_loads(node):
    """Identifiers loaded inside `Rule(..., 'python3 -c ...')` command strings."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "Rule" and len(node.args) >= 3
            and isinstance(node.args[2], ast.Constant)
            and isinstance(node.args[2].value, str)):
        return set()
    try:
        toks = shlex.split(node.args[2].value)
    except ValueError:
        return set()
    if "-c" not in toks:
        return set()
    idx = toks.index("-c")
    if idx + 1 >= len(toks):
        return set()
    return _ast_loads_of(toks[idx + 1])


def _walk_loads(subtree, loads=None):
    """Collect `ast.Load` Name/Attribute identifiers inside `subtree`."""
    out = loads if loads is not None else set()
    for node in ast.walk(subtree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            out.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            out.add(node.attr)
    return out


def _ast_loads_of(src):
    """Load identifiers in `src`, returning empty set on syntax error."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    return _walk_loads(tree)


def _stmt_loads(stmt, loads):
    """Collect AST `Load` identifiers from one non-test top-level statement."""
    _walk_loads(stmt, loads)
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            loads.update(_rule_cmd_loads(node))


def _prod_load_names(text):
    """AST `Load` identifiers in non-test production code of one module."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    test_fns = _test_only_fn_names(tree)
    loads = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in test_fns:
            continue
        _stmt_loads(stmt, loads)
    return loads


def dead_interface_problems(zdir=None):
    """**Public functions with zero production consumers** are reported."""
    cand, own_text = _public_functions(zdir)
    corpus = _repo_corpus(zdir)
    loads = {rel: _prod_load_names(text) for rel, text in corpus}
    own_loads = {
        "zreflect/" + mod: (loads["zreflect/" + mod]
                            if ("zreflect/" + mod) in loads
                            else _prod_load_names(text))
        for mod, text in own_text.items()}
    out = []
    for fn, mod in sorted(cand.items()):
        if not _consumed(fn, "zreflect/" + mod, own_loads, loads):
            out.append(M("registry.dead_interface", function=fn, module=mod))
    return out


def _public_functions(zdir):
    """Candidate discovery: top-level public functions in platform modules."""
    d = zdir if zdir is not None else gate.zdir()
    cand, own_text = {}, {}
    for n in sorted(os.listdir(d)):
        if not n.endswith(".py") or n.startswith("check_"):
            continue
        try:
            text = open(os.path.join(d, n), encoding="utf-8").read()
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        own_text[n] = text
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and not node.name.startswith("_"):
                cand.setdefault(node.name, n)
    return cand, own_text


def _repo_corpus(zdir):
    """Reference text for `zreflect` + `reflect-hooks`, keyed as `sub/filename`."""
    d = zdir if zdir is not None else gate.zdir()
    root = os.path.dirname(d)
    corpus = []
    for sub in ("zreflect", "reflect-hooks"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for n in sorted(os.listdir(base)):
            if n.endswith(".py"):
                try:
                    corpus.append((sub + "/" + n, open(os.path.join(base, n),
                                                       encoding="utf-8").read()))
                except OSError:
                    continue
    return corpus


def _consumed(fn, mod_rel, own_loads, loads):
    """A public function is consumed if it is an entry point or AST-loaded in production."""
    if fn in _ENTRY_INTERFACES or fn in _TEST_HELPERS:
        return True
    if fn in own_loads.get(mod_rel, ()):
        return True
    return any(rel != mod_rel and fn in names for rel, names in loads.items())


def encoding_surface_problems(repo_root=None):
    """**Text-mode `open()` must pass an explicit `encoding=`** -- Windows defaults
    to cp1252 while every file here is UTF-8.

    Criterion (AST): a text-mode (no `b`) `open()` must carry `encoding=`;
    binary mode is exempt. Scans `zreflect/` + `reflect-hooks/`, plus `open(`
    inside rule cmds (`_rule_cmd_encoding_problems`): string literals invisible
    to the AST but executed verbatim by `check_facts_replay`.

    Honest boundary: literal calls only; `Path.read_text()` and dynamic calls
    are out of scope.
    """
    import os  # noqa: PLC0415
    root = repo_root or gate.GATE_REPO
    out = []
    for name, src in gate.py_sources(os.path.join(root, "zreflect")):
        out += _encoding_problems("zreflect/" + name, src)
    for name, src in gate.py_sources(os.path.join(root, "reflect-hooks")):
        out += _encoding_problems("reflect-hooks/" + name, src)
    out += _rule_cmd_encoding_problems()
    return out


def _matching_paren(text, open_idx):
    """When `text[open_idx] == "("`, return the index of the matching `)`; unbalanced => None."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def subprocess_encoding_problems(repo_root=None):
    """**`subprocess.run(text=True)` must pass an explicit `encoding=`**.

    `text=True` decodes with `locale.getpreferredencoding()` (cp1252 on Windows);
    non-cp1252 child output makes `subprocess`'s reader thread raise
    `UnicodeDecodeError` and the main thread see `stdout=None` -- the symptom is
    far from the cause.

    Criterion (AST): every `subprocess.run(...)` with `text=True` must also carry
    `encoding=`. Scans `zreflect/` + `reflect-hooks/`; missing directories are
    skipped.
    """
    import os  # noqa: PLC0415
    root = repo_root or gate.GATE_REPO
    out = []
    for sub in ("zreflect", "reflect-hooks"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for name, src in gate.py_sources(base):
            out += _subprocess_encoding_problems(sub + "/" + name, src)
    return out


def _subprocess_encoding_problems(name, src):
    """Spots in one file where `subprocess.run(text=True)` lacks `encoding`."""
    import ast  # noqa: PLC0415
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"):
            continue
        kw = {k.arg for k in node.keywords}
        if "text" in kw and "encoding" not in kw:
            out.append(M("registry.subprocess_without_encoding",
                         file=name, lineno=node.lineno))
    return out


def fatal_exit_problems(repo_root=None):
    """**`SystemExit` may only carry an integer** -- the rc contract guard
    (0 green / 1 criterion red / 2 broken config).

    `SystemExit(code)` forks on type: `int` => that exit code; `str` => print and
    exit 1; `None` => exit 0, broken config reported as green.

    Criterion (AST): every `SystemExit(<expression>)` in `zreflect/` +
    `reflect-hooks/` must take an integer constant or a call that looks like it
    returns an integer (`gate.fatal_exit` is allowed); the bare form is reported.
    Bad syntax is skipped.
    """
    import ast  # noqa: PLC0415
    import os  # noqa: PLC0415
    root = repo_root or gate.GATE_REPO

    out = []
    for sub in ("zreflect", "reflect-hooks"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for rel, src in gate.py_sources(base):
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            name = sub + "/" + rel.replace(os.sep, "/")
            out.extend(M("registry.system_exit_not_int", file=name,
                         line=node.lineno)
                       for node in _non_int_exits(tree))
    return out


def _non_int_exits(tree):
    """All `raise SystemExit(<non-integer constant>)` nodes in the tree (including the
    no-argument form)."""
    import ast  # noqa: PLC0415
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        call = node.exc
        if not (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "SystemExit"):
            continue
        if not call.args:
            found.append(node)              # `SystemExit()` => exit 0, also broken
            continue
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(
                arg.value, int) and not isinstance(arg.value, bool):
            continue                        # integer constant: a real exit code
        found.append(node)
    return found


def suite_scope_problems(repo_root=None):
    """**Suite gates audit only the suite's own code**: "suite code" is identified
    by a module-level declaration (`MODULE = ...` / `GATE = ...`), the same
    convention as `registry.modules()` / `gates()` -- no hand-written rosters.

    Scans `zreflect/` and `reflect-hooks/`. A `.py` **without** a declaration
    is consumer data (`measure_*` is exempt), but a suite `.py` lacking one is
    reported, because gates would silently stop auditing it. Missing dirs are
    skipped.
    """
    import os  # noqa: PLC0415
    root = repo_root or gate.GATE_REPO
    out = []
    for sub in ("zreflect", "reflect-hooks"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for rel, _src in gate.py_sources(base):
            name = rel.replace(os.sep, "/")
            if name.startswith("measure_"):
                continue                # the consumer's data module (naming the README requires)
            if not gate.declares_itself(os.path.join(base, rel)):
                out.append(M("registry.suite_file_without_declaration",
                             file=sub + "/" + name))
    return out


def _rule_cmd_encoding_problems():
    """**`open(` inside rule cmds is audited too**.

    ⚠️ `doc.RULES`'s `cmd` is a **string literal**, not a real `open()` call --
    the AST scan (`_encoding_problems`) cannot see it. Yet `check_facts_replay`
    executes it verbatim, so ledger cmds need the same encoding judgment as
    source code.
    """
    import re  # noqa: PLC0415
    out = []
    try:
        import doc  # noqa: PLC0415
    except Exception:                                    # noqa: BLE001
        return out
    for rule in getattr(doc, "RULES", ()):
        cmd = getattr(rule, "cmd", "") or ""
        # ⚠️ `open\([^)]*\)` won't do: arguments often contain
        # `os.path.join(a, b)`, whose inner `)` truncates the regex early, so the
        # trailing `encoding=` is **never seen** -- observed: the `host_agnostic`
        # rule plainly carried an encoding and was still reported.
        # Instead: "start at `open(`, balance parens to the matching `)`".
        for idx in (m.start() for m in re.finditer(r"\bopen\(", cmd)):
            end = _matching_paren(cmd, idx + 4)
            if end is None:
                continue
            call = cmd[idx:end + 1]
            if "encoding" in call or "'rb'" in call or '"rb"' in call:
                continue
            out.append(M("registry.open_without_encoding",
                         file="zreflect/doc.py (rule %s)" % rule.id,
                         lineno=0, mode="cmd"))
    return out


def _encoding_problems(name, src):
    """Spots in one file where a text-mode `open()` lacks `encoding`."""
    import ast  # noqa: PLC0415
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "open"):
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue
        mode = "r"
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = str(node.args[1].value)
        if "b" in mode:
            continue                        # binary: no encoding conversion
        out.append(M("registry.open_without_encoding",
                     file=name, lineno=node.lineno, mode=mode))
    return out


def shell_surface_problems(repo_root=None):
    """The **suite's own** `.sh` files may only appear in `ALLOWED_SHELL` -- a
    bounded whitelist where every exception carries a reason.

    Scans only `zreflect/` + `reflect-hooks/`, never the consumer's repo: a
    consumer's `build.sh` / `deploy.sh` is out of scope. `_shell_files_of`
    excludes `.git` / `node_modules` and normalizes `os.sep` before comparing,
    so Windows backslashes cannot bypass the whitelist. Missing directories are
    skipped.
    """
    import os  # noqa: PLC0415
    root = repo_root or gate.GATE_REPO
    out = []
    for sub in ("zreflect", "reflect-hooks"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        out += _shell_files_of(base, sub)
    return out


def _shell_files_of(base, prefix):
    """`.sh` files under `base` that are **not in the whitelist**."""
    import os  # noqa: PLC0415
    out = []
    for dirpath, _dirnames, filenames in os.walk(base):
        # ⚠️ **Never write `"/.git" in dirpath`**: Windows' separator is `\`, so that
        # test never fires => the dozen sample `.sh` files inside `.git/hooks/` all
        # counted as "unregistered shell" (observed: exactly how CI's Windows leg
        # went red).
        parts = dirpath.replace(os.sep, "/").split("/")
        if ".git" in parts or "node_modules" in parts:
            continue
        for n in filenames:
            if not n.endswith(".sh"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, n), base)
            # ⚠️ **`relpath` yields backslashes on Windows**, while `ALLOWED_SHELL`
            # is written with `/` -- without normalization every whitelist entry
            # would be "not on the list" (observed: CI's Windows leg reported
            # `unexpected_shell(file='reflect-hooks\\einfacht-env.sh')`).
            norm = (prefix + "/" + rel).replace(os.sep, "/")
            if norm not in ALLOWED_SHELL:
                out.append(M("registry.unexpected_shell", file=norm))
    return out


def trailing_newline_problems(zdir=None):
    """`.py` files must end with a newline.

    Why it deserves a criterion: the `py_lines` fact has **two** measuring methods --
    `facts.measure()` counts lines via `open()` (keeping a final line without a
    newline), while the ledger's `cmd` uses `cat | wc -l` (counting newline
    characters). A file without a trailing newline makes the two differ by 1, so
    `check_facts_replay` goes **permanently red** for a reason unrelated to any code.
    Tripped on **four times** (each time a writer forgot the trailing newline when
    creating a file).

    The fix targets the root: files should have trailing newlines (the POSIX text
    definition, and a prerequisite for diff tooling). The criterion reports it; a
    human adds one line.
    """
    import os  # noqa: PLC0415
    base = zdir or gate.zdir()
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return out
    for n in names:
        if not n.endswith(".py"):
            continue
        p = os.path.join(base, n)
        try:
            with open(p, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                if fh.tell() == 0:
                    continue                 # empty files are out of this criterion's range
                fh.seek(-1, os.SEEK_END)
                last = fh.read(1)
        except OSError:
            continue
        if last != b"\n":
            out.append(M("registry.no_trailing_newline", file=n))
    return out


def _source_of(rel, sources):
    """Read a gate's source; unreadable => `None` (**not an empty string** -- the two
    meanings must stay distinguishable)."""
    if sources is not None:
        return sources.get(rel)
    try:
        return open(os.path.join(gate.GATE_REPO, rel),
                    encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def _calls_off(text):
    """AST-locate `off(...)` calls (excluding the definition site and comments).
    Unreadable source => `None`."""
    if text is None:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    return any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "off"
               for n in ast.walk(tree))


def _reason_shape_problems(rel, reason, calls_off):
    """Three-way: can off but no reason / reason too short / reason declared but off
    never called.

    ⚠️ **Unreadable source (`calls_off is None`) => this direction is skipped
    entirely**: treating `False` as truth when the fixture repo lacks the file
    reports fake "reason written for nothing". Reason truthfulness does not
    depend on source and is still checked normally.
    """
    if calls_off is None:
        return []
    if not calls_off:
        return ([M("registry.off_reason_without_off", file=rel)]
                if reason else [])
    if not reason:
        return [M("registry.off_without_reason", file=rel)]
    if len(str(reason).strip()) < MUST_REASON_MIN:
        return [M("registry.off_reason_too_short", file=rel, reason=str(reason))]
    return []


def _reason_truth_problems(rel, reason):
    """**Reason truthfulness**: the reason claims "this repo has no X.json" -- if
    X.json actually exists, the reason has gone stale (the gate should have been
    enabled long ago). The symmetric criterion added in round 17: round 12 only
    demanded "a reason must exist", never "the reason must be true".
    """
    return [M("registry.off_reason_stale", file=rel, name=tok)
            for tok, exists in _reason_files(reason) if exists]


# -- Execution positions must hold commands, not prose ---------------------
#
# Several fields across the suite promise "this is how you re-run it": a world
# stamp's `cmd`, a pin's `version_read`, an instrument's `cmd`, a retraction's
# `evidence`, a question's `Settling`. Each was a place narration could hide --
# measured: a retraction whose `evidence` read "github Actions run 421...", and
# a `Settling:` naming a bare path with no way to be run. **Prose in a field
# that promises re-runnability is the same shape as an off state with no
# reason.**
#
# The criterion is deliberately blunt: an execution position must begin with a
# **command token** -- an interpreter, a common Unix utility, or an absolute
# path. Prose never does; a real command always does. The list is not meant to be
# exhaustive (a repo can always call something exotic); it exists to make
# "narration sits in a replay field" impossible, which is the failure this
# guards. `EXEC_PREFIXES` is the escape hatch: add a token here when a spec
# legitimately needs it.
EXEC_PREFIXES = (
    "python3", "python", "sh", "bash", "node", "deno", "ruby", "perl",
    "echo", "printf", "cat", "test", "true", "false", "env", "make", "git",
    "npm", "pnpm", "yarn", "cargo", "go", "gcc", "cc", "cmake", "docker",
)


_OUTCOME_SEP = re.compile(r"\s+(?:——|—|----|--)\s+")
_PROSE_CHARS = re.compile(r"[\u4e00-\u9fff（）【】；：，。]")


def _command_part(value, field_name):
    """Extract the command segment (stripping outcome tail on `Settling` and backticks)."""
    s = str(value or "").strip()
    if field_name == "Settling":
        s = _OUTCOME_SEP.split(s, 1)[0].strip()
    if s.startswith("`") and s.endswith("`") and len(s) >= 2:
        s = s[1:-1].strip()
    return s


def _strip_quoted(text):
    """Remove single/double-quoted spans so prose inside quotes is not flagged."""
    out = re.sub(r'"[^"]*"', "", text)
    return re.sub(r"'[^']*'", "", out)


def starts_with_interpreter(value, field_name="cmd"):
    """Does this execution-position value hold a runnable command without prose tails?"""
    cmd = _command_part(value, field_name)
    if not cmd:
        return False
    first = cmd.split(" ", 1)[0].strip("`\"'")
    if not (first in EXEC_PREFIXES or first.startswith("/")):
        return False
    if _PROSE_CHARS.search(_strip_quoted(cmd)):
        return False
    try:
        return bool(shlex.split(cmd))
    except ValueError:
        return False


def prose_in_exec_problems(where, field_name, value):
    """Report when an execution position holds prose instead of a command."""
    if not str(value or "").strip():
        return []
    if starts_with_interpreter(value, field_name):
        return []
    return [M("criteria.exec_position_is_prose",
              where=where, field=field_name, value=str(value)[:60])]


# Spec files and the keys whose values are execution positions.
EXEC_POSITIONS = {
    "world.json": ("stamps", "cmd"),
    "pins.json": ("pins", ("version_read", "stamp_read")),
}


def _spec_path(knobs_key, base):
    path = knobs.repo_path(knobs_key, base)
    return path if path and os.path.exists(path) else None


def _spec_exec_problems(knobs_key, spec_name, base):
    path = _spec_path(knobs_key, base)
    if path is None:
        return []
    try:
        spec = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return []
    return exec_position_problems(spec, spec_name)


def _settling_problems(base):
    """The `Settling:` line of every question (delegated to `check_questions`)."""
    import check_questions  # noqa: PLC0415
    out = []
    for rel, body in sorted(check_questions.collect(root=base).items()):
        sv = check_questions.field(body, "Settling")
        if not sv or sv.startswith(check_questions.NONE_LIKE):
            continue
        out += prose_in_exec_problems(os.path.basename(rel), "Settling", sv)
    return out


def _evidence_problems(base):
    """The `evidence` field of every retraction entry."""
    path = _spec_path("REFLECT_RETRACTIONS", base)
    if path is None:
        return []
    try:
        entries = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return []
    return [p for r in (entries or {}).get("retractions") or []
            if isinstance(r, dict)
            for p in prose_in_exec_problems("retractions/%s" % r.get("id", "?"),
                                            "evidence", r.get("evidence"))]


def all_exec_position_problems(root=None):
    """Every prose-in-an-execution-position, across specs and carriers.

    `root` = repo root (default: the audited repo). Each carrier is its own
    helper: they read different files and fail differently, so merging them
    only hides which one spoke.
    """
    base = root or gate.GATE_REPO
    return (_spec_exec_problems("REFLECT_WORLD", "world.json", base)
            + _spec_exec_problems("REFLECT_PINS", "pins.json", base)
            + _settling_problems(base)
            + _evidence_problems(base))
def exec_position_problems(spec, name):
    """Every execution position in one spec must hold a command, not prose."""
    entry_key, fields = EXEC_POSITIONS.get(name, (None, ()))
    if entry_key is None or not isinstance(spec, dict):
        return []
    fields = (fields,) if isinstance(fields, str) else fields
    # A spec's entry collection is a dict (world stamps keyed by name) or a list
    # (pins are positional); both carry execution positions.
    raw = spec.get(entry_key) or {}
    pairs = ([(str(i), e) for i, e in enumerate(raw)] if isinstance(raw, list)
             else list(raw.items()) if isinstance(raw, dict) else [])
    out = []
    for key, entry in pairs:
        if not isinstance(entry, dict):
            continue
        for field_name in fields:
            out += prose_in_exec_problems(
                "%s/%s" % (name, entry.get("name") or key),
                field_name, entry.get(field_name))
    return out


def off_reason_problems(gs, sources=None):
    """**A gate that can `off()` must declare why it may be not-enabled**: an
    `off` without a reason is indistinguishable from "this repo does not use
    that mechanism".

    Criterion (AST): source calls `off(` but the declaration has no (or a
    too-short) `off_reason` => report; declaration has `off_reason` but the
    source never calls `off(` => report (a lie); threshold is `MUST_REASON_MIN`.
    Discovery-based: `gs` + source, no roster. Shape and truthfulness are
    separate helpers sharing no state.
    """
    out = []
    for g in gs:
        rel = g["file"]
        reason = g.get("off_reason")
        out += _reason_shape_problems(rel, reason,
                                      _calls_off(_source_of(rel, sources)))
        out += _reason_truth_problems(rel, reason)
    return out


def _scan_sources(sources, base):
    """Scan surface: use `sources` when given (selftests inject a fake filesystem),
    otherwise scan the real directory.

    ⚠️ `sources=[]` counts as **injection with an empty surface**, not "scan the
    real directory": the injection-mode threshold must be able to distinguish
    "injected surface is empty" from "not injected" (`path_rule_problems` gates
    on it; scanning the real directory there would judge the host by association).
    """
    if sources is not None:
        return sorted(sources.items())
    items = []
    for n in sorted(os.listdir(base)):
        if not n.endswith(".py"):
            continue
        try:
            items.append((n, open(os.path.join(base, n), encoding="utf-8").read()))
        except OSError:
            continue
    return items


def _returns_self_computed_dir(text):
    """Does a function body self-compute `dirname(...abspath(__file__))` (return or assign)?"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and "dirname" in ast.unparse(sub)
                    and "abspath(__file__)" in ast.unparse(sub)):
                out.append(node.name)
                break
    return out


def path_rule_problems(sources=None):
    """Enforce single source (`gate.zdir`) for tool directory calculation across suite."""
    surface = _scan_sources(None, gate.zdir()) if sources is None else sources.items()
    out = []
    for name, text in surface:
        if name == "gate.py":
            continue                    # gate.py is the single source; it is allowed
        for fn in _returns_self_computed_dir(text):
            out.append(M("registry.path_rule_split", file=name, function=fn))
    return out


def _platform_functions(names, read):
    """Top-level public functions of platform modules (non-`check_*`): `{module:
    {function names}}`."""
    platform = {}
    for n in names:
        if n.startswith("check_") or not n.endswith(".py"):
            continue
        text = read(n)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        fns = {node.name for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not node.name.startswith("_")}
        if fns:
            platform[n[:-3]] = fns
    return platform


def _asserted_names(files):
    """Identifiers loaded inside `_cases*` / `_fixture*` function subtrees only."""
    asserted = set()
    for text in files.values():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        test_fns = _test_fn_names(tree)
        for stmt in tree.body:
            if not (isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and stmt.name in test_fns):
                continue
            _walk_loads(stmt, asserted)
    return asserted


def _record(consumed, consumers, pair, file):
    """Record one instance of "some file consumed some platform function"."""
    consumed.add(pair)
    consumers.setdefault(pair, set()).add(file)


def _import_aliases(tree, platform):
    """Alias table for `import <mod>`: `{alias: mod}` (platform modules only)."""
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in platform:
                    aliases[a.asname or a.name] = a.name
    return aliases


def _from_import_uses(tree, platform):
    """`from <platform module> import <platform function>` => `[(module, function)]`."""
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ImportFrom) and node.module in platform):
            continue
        for a in node.names:
            if a.name in platform[node.module]:
                out.append((node.module, a.name))
    return out


def _attribute_uses(tree, platform, aliases):
    """`<mod>.<fn>` / `<alias>.<fn>` (Load context) => `[(module, function)]`."""
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)):
            continue
        mod = aliases.get(node.value.id, node.value.id)
        if mod in platform and node.attr in platform[mod]:
            out.append((mod, node.attr))
    return out


def _consumer_files(files):
    """The real **callers**: `check_*` / `doctor.py` (platform modules calling each
    other don't count)."""
    return {n: t for n, t in files.items()
            if n.startswith("check_") or n == "doctor.py"}


def _consumers(files, platform):
    """Who consumed which platform function: `({(module, function)}, {(module,
    function): {filenames}})`.

    Scans only `check_*` / `doctor.py` -- they are the real callers; platform
    modules calling each other is not "gate consumption".

    The three discovery forms (`from import` / aliased attribute / bare attribute)
    are each a helper: merged into one function, two `ast.walk` passes plus three
    isinstance branches pushed complexity to 14.
    """
    consumed, consumers = set(), {}
    for file, text in _consumer_files(files).items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        aliases = _import_aliases(tree, platform)
        uses = (_from_import_uses(tree, platform)
                + _attribute_uses(tree, platform, aliases))
        for pair in uses:
            _record(consumed, consumers, pair, file)
    return consumed, consumers


# ⚠️ **Framework APIs are exempt from the assertion requirement**: `gate.meta` /
# `main_selftest_or` / `i18n.M` are consumed by **all 16** gates -- they are entry
# scaffolding, not the "domain function" of any particular gate. Requiring
# assertions for them means demanding "the framework writes tests for the
# framework", which is bootstrapping.
# The threshold is an **absolute number** (>= 3 gates sharing => framework API), not
# "half the gates": the latter degenerates to 1 in a single-gate fixture, which
# would skip the fixture's only consumption edge as framework (observed).
FRAMEWORK_MIN_GATES = 3


def _load_platform_sources(zdir, sources):
    """Load the scan surface: `(names, files, read)`. Unreadable => empty tables (not
    an exception).

    `read(n)` returns None for **unloaded** files -- "no such file" and "the file is
    empty" must stay distinguishable (an empty module and a missing module mean
    different things to the criteria).
    """
    d = zdir if zdir is not None else gate.zdir()

    def read(n):
        if sources is not None:
            return sources.get(n)
        try:
            return open(os.path.join(d, n), encoding="utf-8",
                        errors="replace").read()
        except OSError:
            return None

    if sources is not None:
        names = sorted(sources)
        return names, {n: sources[n] for n in names}, read
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".py"))
    except OSError:
        return [], {}, read
    files = {n: t for n in names if (t := read(n)) is not None}
    return names, files, read


def _untested_consumed(consumed, consumers, asserted):
    """Functions consumed by gates that have no assertion anywhere and are not
    framework API.

    ⚠️ The framework-API criterion is an **absolute count** (>= 3 gates sharing),
    not "half the gates": the latter degenerates to 1 in a single-gate fixture and
    would skip the fixture's only consumption edge as framework.
    """
    return [(mod, fn) for mod, fn in sorted(consumed)
            if fn not in asserted
            and len(consumers[(mod, fn)]) < FRAMEWORK_MIN_GATES]


def dependency_coverage_problems(zdir=None, sources=None):
    """C4 reconciliation (9): **platform functions consumed by gates must have an
    assertion somewhere**.

    A consumed-but-untested module is a dead link in the dependency chain: when it
    misjudges, every gate consuming it loses its criterion, while that gate's own
    selftest stays green (round 24's `living.living_lines()`).

    The four stages are each a helper (`_load_platform_sources` /
    `_platform_functions` / `_asserted_names` / `_consumers` /
    `_untested_consumed`); this function only orchestrates.
    """
    names, files, read = _load_platform_sources(zdir, sources)
    if not files:
        return []
    platform = _platform_functions(names, read)
    asserted = _asserted_names(files)
    consumed, consumers = _consumers(files, platform)
    return [M("registry.dependency_untested", module=m, function=f)
            for m, f in _untested_consumed(consumed, consumers, asserted)]


# -- Selftest: criteria belong to their own subject under test -----------------

def _dead_interface_case():
    """Plant a zero-consumer public function => must report even when mentioned in
    comments/docstrings/`_cases*`; add a real consumer => must not report."""
    import os
    import shutil
    import tempfile  # noqa: PLC0415
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "zreflect")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "probe.py"), "w", encoding="utf-8") as fh:
            fh.write(
                'def zzz_orphan():\n    """Mention zzz_orphan() only in docstring."""\n'
                '    # and in comment: zzz_orphan()\n    return 1\n'
                'def _cases_probe():\n    return [("x", lambda: zzz_orphan() == 1)]\n')
        if not dead_interface_problems(zdir=d):
            return False
        # A real external consumer was added => should no longer report
        with open(os.path.join(d, "check_probe.py"), "w", encoding="utf-8") as fh:
            fh.write("import probe\ndef run():\n    return probe.zzz_orphan()\n")
        return dead_interface_problems(zdir=d) == []
    finally:
        shutil.rmtree(root, True)



def _unexpected_shell_case():
    """An unregistered `.sh` in a **suite directory** => must report.

    ⚠️ The criterion's scan surface is `zreflect/` + `reflect-hooks/` (the suite
    itself), **not the consumer's repo** -- "all Python" is this repo's discipline
    for itself. So the fixture must also be planted inside a suite subdirectory; an
    `.sh` at the consumer's root is **not to be reported** (see
    `_owner_shell_is_allowed`).
    """
    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        suite = os.path.join(d, "zreflect")
        os.makedirs(suite)
        with open(os.path.join(suite, "probe.sh"), "w", encoding="utf-8") as fh:
            fh.write("# probe\n")
        if not shell_surface_problems(repo_root=d):
            return False
        # A registered name (`reflect-hooks/quality-record.sh`) must not report
        hooks = os.path.join(d, "reflect-hooks")
        os.makedirs(hooks)
        with open(os.path.join(hooks, "quality-record.sh"), "w",
                  encoding="utf-8") as fh:
            fh.write("# ok\n")
        got = [str(p) for p in shell_surface_problems(repo_root=d)]
        return len(got) == 1 and "probe.sh" in got[0]
    finally:
        shutil.rmtree(d, True)


def _system_exit_int_case():
    """Verify non-int `SystemExit(...)` payloads report while int exit codes pass."""
    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        suite = os.path.join(d, "zreflect")
        os.makedirs(suite)
        probe = os.path.join(suite, "probe.py")

        def count(body):
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("def f():\n" + body)
            return len(fatal_exit_problems(repo_root=d))

        return (count('    raise SystemExit("msg")\n') == 1
                and count("    raise SystemExit()\n") == 1
                and count("    raise SystemExit(2)\n") == 0)
    finally:
        shutil.rmtree(d, True)


def _undeclared_suite_file_case():
    """A `.py` in a suite directory **without a declaration line** => must report.

    Why: no declaration = treated as consumer code = the three gates stop auditing
    it. That is **a new way to switch a gate off** and must be able to go red.
    `measure_*.py` is the exception (that is the consumer's data module).
    """
    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        suite = os.path.join(d, "zreflect")
        os.makedirs(suite)
        with open(os.path.join(suite, "orphan.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("x = 1\n")
        found = [str(p) for p in suite_scope_problems(repo_root=d)]
        if not any("orphan.py" in s for s in found):
            return False
        # `measure_*.py` is the consumer's data module => must not report
        os.rename(os.path.join(suite, "orphan.py"),
                  os.path.join(suite, "measure_probe.py"))
        return suite_scope_problems(repo_root=d) == []
    finally:
        shutil.rmtree(d, True)


def _scanned_sources_two_ways_case():
    """Both scopes of `gate.scanned_sources` are tested once each (`configured`
    and not), with one declared and one undeclared file.

    Both halves must be pinned: if unset collects everything, the consumer's
    repo is reported against the suite's own discipline; if set collects only
    declared files, `REFLECT_I18N_ROOT=<dir>` reports a `scan_empty_dir` FATAL
    and breaks manual opt-in. The two drift directions have opposite costs.
    """
    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "suite.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("MODULE = 1\n")
        with open(os.path.join(d, "user.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        default = [rel for rel, _src in gate.scanned_sources(d)]
        opted_in = [rel for rel, _src in gate.scanned_sources(d, configured=True)]
        return default == ["suite.py"] and sorted(opted_in) == [
            "suite.py", "user.py"]
    finally:
        shutil.rmtree(d, True)


def _owner_shell_is_allowed():
    """`.sh` files at the **consumer's repo root** must not be reported -- those are
    their build scripts, none of the suite's business.

    This guards the `shell_surface_problems` scope: the suite audits its own
    Python sources, not the consumer's build scripts.
    """
    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        for name in ("build.sh", "deploy.sh"):
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\n")
        return shell_surface_problems(repo_root=d) == []
    finally:
        shutil.rmtree(d, True)


def _han_predicate_case():
    """`i18n.han()` recognizes Chinese, rejects ASCII, and rejects near-relatives
    outside codepoint construction."""
    from i18n import han  # noqa: PLC0415
    # The fixture's Chinese is codepoint-constructed (repo discipline: literals
    # would enter the scan surface)
    return (han(chr(0x4E2D)) and han("a" + chr(0x6587) + "b")
            and not han("plain ascii")
            and not han("")
            and not han(chr(0x3042)))     # hiragana is outside the CJK Unified Ideographs range



def _trailing_newline_case():
    """Create a file missing its trailing newline => must report; add it => must not
    report."""
    import os
    import shutil
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        open(os.path.join(d, "bad.py"), "w", encoding="utf-8").write("x = 1")
        if not trailing_newline_problems(zdir=d):
            return False
        open(os.path.join(d, "bad.py"), "w", encoding="utf-8").write("x = 1\n")
        return trailing_newline_problems(zdir=d) == []
    finally:
        shutil.rmtree(d, True)



def _selftest_false_states_it():
    """Every module with `selftest=False` must state in its description that "the
    selftest lives in registry._cases".

    All three are checked (`living.py` / `gate.py` / `registry.py`) -- discovery-
    based: take everything with `selftest=False` from `modules()`, no hand-written
    list.
    """
    from registry import modules  # noqa: PLC0415
    mods, _und = modules()
    checked = 0
    for m in mods:
        if m.get("selftest"):
            continue
        checked += 1
        if "registry._cases" not in m["desc"]:
            return False
    return checked >= 1          # zero-trust guard: checked none => not credible



def _dependency_coverage_ok():
    """Real repo: consumed platform functions all have assertions; plant one more
    "consumed but unasserted" => must report."""
    ok_real = dependency_coverage_problems() == []
    # The name must be **unique repo-wide**: a common word like `helper` would be hit
    # by a same-named variable in the real registry._cases => the assertion surface
    # "pretends" to cover it (observed: fake returned []).
    fake = {
        "check_probe.py":
            "import probe\ndef run():\n    return probe.zzz_uniquely_named()\n",
        "probe.py": "def zzz_uniquely_named():\n    return 1\n",
    }
    got = [p.code for p in dependency_coverage_problems(sources=fake)]
    return ok_real and got == ["registry.dependency_untested"]



def _selftest_refuses_empty():
    """`gate.selftest(name, [])` must SystemExit (the 0/0 hole may not exit green)
    **and exit 2**.

    Asserting only "a SystemExit was raised" is insufficient:
    `raise SystemExit("a string")` prints and exits 1, so a caller classifying
    by rc files a broken config under "criterion red". This case pins `rc == 2`;
    what was printed does not count.
    """
    try:
        gate.selftest("probe", [])
        return False                    # didn't refuse => this case is red
    except SystemExit as e:
        return e.code == 2




def _off_reason_ok(_label, sources, ok, reason=None):
    """Build a fake declaration line + fake source and verify `off_reason_problems`'s
    judgment direction.

    `sources`' values are **source snippets**; `_off(` is a placeholder later
    replaced with the real call, so this file itself doesn't get adopted by the
    criterion (it is itself a gate that can off)."""
    body = sources["check_x.py"].replace("_off(", "off(")
    gs = [{"file": "check_x.py", "off_reason": reason}]
    got = off_reason_problems(gs, sources={"check_x.py": body})
    return (got == []) if ok else (got != [])



def _off_reason_stale_ok():
    """Claims there is no `ab.json` while `ab.json` really exists => must report stale.

    Uses a temp dir as the repo root (the real repo untouched) and supplies source
    so the `off()` call holds, isolating the finding triggered **only by "the reason
    went stale"**.
    """
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "ab.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        reason = ("no " + "ab.json" + " spec in this repo")   # ASCII, to avoid triggering the no-language gate
        gs = [{"file": "check_ab.py", "off_reason": reason}]
        src = {"check_ab.py": "def run():\n    return off(null)\n"}
        old = gate.GATE_REPO
        gate.GATE_REPO = d
        try:
            got = [p.code for p in off_reason_problems(gs, sources=src)]
            # Control group with the file absent: delete ab.json => no stale expected
            os.remove(os.path.join(d, "ab.json"))
            got2 = [p.code for p in off_reason_problems(gs, sources=src)]
        finally:
            gate.GATE_REPO = old
        return got == ["registry.off_reason_stale"] and got2 == []
    finally:
        shutil.rmtree(d, True)


def _exec_position_every_carrier():
    """All three carriers must be scanned: spec, Settling, evidence.

    Uses a temp repo so the assertion does not depend on this checkout having a
    violation to find.
    """
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "questions"))
        with open(os.path.join(root, "world.json"), "w", encoding="utf-8") as fh:
            fh.write('{"lines":{"m":{"site":"s","artifacts":"a","container":"c",'
                     '"fork_pin_ref":"u"}},"active":"m","stamps":{"s":'
                     '{"value":"v","cmd":"the deploy was green last tuesday"}}}')
        with open(os.path.join(root, "pins.json"), "w", encoding="utf-8") as fh:
            fh.write('{"pins":[{"name":"p","kind":"version","worktree":"w",'
                     '"version_read":"read version from Slack",'
                     '"stamp_read":"also not a command"}]}')
        with open(os.path.join(root, "retractions.json"), "w", encoding="utf-8") as fh:
            fh.write('{"schema":1,"retractions":[{"id":"R-9","text":"t",'
                     '"evidence":"a slack thread said so","fixed_in":"f"}]}')
        with open(os.path.join(root, "questions", "01.md"), "w", encoding="utf-8") as fh:
            fh.write("# q\n\n**Status:** ready-for-agent\n\n"
                     "**Settling:** just look at it ---- rc=0 A; rc=1 B\n")
        saved = {k: os.environ.get(k) for k in
                 ("REFLECT_WORLD", "REFLECT_PINS", "REFLECT_RETRACTIONS")}
        try:
            for k in saved:
                os.environ.pop(k, None)
            fields = {p.params.get("field")
                      for p in all_exec_position_problems(root)}
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return fields == {"cmd", "version_read", "stamp_read", "Settling", "evidence"}


def _path_rule_single_source():
    """Real repo: only gate.py self-computes the tool dir; return and local assign
    in a function both report."""
    ok_real = path_rule_problems() == []
    fake = {
        "splitter.py": "def f():\n    return os.path.dirname(os.path.abspath(__file__))\n",
        "local.py": "def g():\n    d = os.path.dirname(os.path.abspath(__file__))\n    return d\n",
    }
    got = [p.code for p in path_rule_problems(sources=fake)]
    return ok_real and got == ["registry.path_rule_split", "registry.path_rule_split"]



def _cases_off_reason():
    """Off-reason shape and truthfulness cases."""
    return [
    ("★ registry.off_without_reason", lambda: _off_reason_ok(
        "no-reason", {"check_x.py": "_off()"}, ok=False)),
    ("★ registry.off_reason_too_short", lambda: _off_reason_ok(
        "too-short", {"check_x.py": "_off()"}, ok=False, reason="x")),
    ("★ registry.off_reason_without_off", lambda: _off_reason_ok(
        "declared-but-never-off", {"check_x.py": "pass\n"}, ok=False,
        reason="a real justification long enough")),
    ("registry.off_reason_ok", lambda: _off_reason_ok(
        "complete", {"check_x.py": "_off()"}, ok=True,
        reason="a real justification long enough")),
    ("★ registry.off_reason_stale", lambda: _off_reason_stale_ok()),
    ]



def _cases_path_rule():
    """Path-rule, execution-position, and `zdir()`/`tool_repo()` cases."""
    return [
    ("★ registry.path_rule_single_source",
     lambda: _path_rule_single_source()),
    ("\u2605 registry.exec_position_covers_every_carrier",
     lambda: _exec_position_every_carrier()),
    ("★ registry.zdir_matches_file",
     lambda: os.path.basename(gate.zdir()) == "zreflect"
     and os.path.exists(os.path.join(gate.zdir(), "registry.py"))),
    ("★ registry.tool_repo_is_zdir_parent",
     lambda: os.path.abspath(gate.tool_repo())
     == os.path.dirname(os.path.abspath(gate.zdir()))),
    ("★ registry.zdir_is_a_dir",
     lambda: os.path.isdir(gate.zdir())
     and os.path.basename(gate.zdir()) == "zreflect"),
    ]


def _cases(fx=None):
    """`criteria.py`'s own criteria: dead interfaces / shell surface / CJK predicate /
    trailing newline / dependency coverage / off reasons / path rule / selftest
    hardening. **Lives in this module** -- criteria belong to their subject under
    test.

    `fx` is the product of `registry._cases_fixture()` (the `off_reason` / `path_rule`
    groups need the roster fixture); when `--selftest` runs standalone, one is built
    fresh from `registry`.
    """
    if fx is None:
        import atexit
        import tempfile  # noqa: PLC0415

        from registry import _cases_fixture  # noqa: PLC0415
        d = tempfile.mkdtemp()
        atexit.register(__import__("shutil").rmtree, d, True)
        fx = _cases_fixture(d)
        fx["d"] = d
    return (
        _cases_off_reason()
        + _cases_path_rule()
        + _cases_self_checks()
    )


def _utf8_forced_case():
    """Verify `_force_utf8_streams()` makes cp1252 streams accept UTF-8 text."""
    import inspect  # noqa: PLC0415
    import io  # noqa: PLC0415
    import sys  # noqa: PLC0415

    import gate  # noqa: PLC0415
    src = inspect.getsource(gate._force_utf8_streams)
    if "reconfigure" not in src or "utf-8" not in src:
        return False                    # static assertion: it must really do the thing
    sample = "A/B " + chr(0x95F8) + chr(0x95E8)          # "gate" in Chinese

    def _can_encode(stream):
        try:
            stream.write(sample + "\n")
            stream.flush()              # explicit flush -- don't let errors hide in buffers
            return True
        except UnicodeEncodeError:
            return False

    raw = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    if _can_encode(raw):
        return False                    # cp1252 encoded it after all => fixture built wrong

    fixed = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = fixed
    try:
        gate._force_utf8_streams()
        return _can_encode(fixed)
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _cases_self_checks():
    """Core structural self-checks (dead interface, shell, CJK, encoding, scope)."""
    return [
        ("★ registry.dead_interface_detected",
         lambda: _dead_interface_case()),
        ("★ registry.unexpected_shell_detected",
         lambda: _unexpected_shell_case()),
        ("★ registry.owner_shell_is_allowed",
         lambda: _owner_shell_is_allowed()),
        ("★ registry.han_predicate",
         lambda: _han_predicate_case()),
        ("★ registry.trailing_newline_detected",
         lambda: _trailing_newline_case()),
        ("★ registry.selftest_false_modules_state_where_selftest_lives",
         lambda: _selftest_false_states_it()),
        ("★ registry.dependency_coverage",
         lambda: _dependency_coverage_ok()),
        ("★ registry.suite_file_without_declaration",
         lambda: _undeclared_suite_file_case()),
        ("★ registry.system_exit_is_int", lambda: _system_exit_int_case()),
        ("★ registry.subprocess_without_encoding_detected",
         lambda: [p.code for p in _subprocess_encoding_problems(
             "x.py", 'import subprocess\n'
                     'subprocess.run(["x"], text=True)\n')]
         == ["registry.subprocess_without_encoding"]),
        ("registry.subprocess_with_encoding_is_clean",
         lambda: _subprocess_encoding_problems(
             "x.py", 'import subprocess\n'
                     'subprocess.run(["x"], text=True,\n'
                     '               encoding="utf-8")\n') == []),
        ("★ registry.open_without_encoding_detected",
         lambda: [p.code for p in _encoding_problems(
             "x.py", 'open("a", "w").write("x")\n')]
         == ["registry.open_without_encoding"]),
        ("registry.open_with_encoding_is_clean",
         lambda: _encoding_problems(
             "x.py", 'open("a", encoding="utf-8").write("x")\n') == []),
        ("registry.binary_open_is_exempt",
         lambda: _encoding_problems("x.py", 'open("a", "rb").read()\n') == []),
        ("★ registry.utf8_streams_are_forced",
         lambda: _utf8_forced_case()),
        ("★ registry.scope_two_ways",
         lambda: _scanned_sources_two_ways_case()),
        ("★ registry.selftest_refuses_empty_cases",
         lambda: _selftest_refuses_empty()),
    ]


def _selftest():
    import sys  # noqa: PLC0415

    from gate import main_selftest_or  # noqa: PLC0415
    return main_selftest_or(sys.argv[1:], M("gate.title.criteria"),
                            _cases, lambda a: 0)


from gate import module_meta  # noqa: E402

MODULE = module_meta(
    "roster criteria",
    "machine reconciliation of \"which things must agree\": dead interfaces / "
    "shell surface / trailing newline / off reasons / path rule / dependency "
    "coverage (self-verification lives in this module's `_cases`)",
    selftest=True)


if __name__ == "__main__":
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import criteria as _mod  # noqa: PLC0415
    sys.exit(_mod._selftest())
