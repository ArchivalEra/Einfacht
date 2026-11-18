#!/usr/bin/env python3
"""Knob registry and resolution (`os.environ > knobs.json > REGISTRY`)."""
from __future__ import annotations

import ast
import json
import os
import sys


class _Semantic(str):
    """Lazily rendered one-line knob description resolved against the active language pack."""

    code: str
    __slots__ = ("code",)

    def __new__(cls, code):
        obj = str.__new__(cls, code)
        obj.code = code
        return obj

    def __str__(self):
        from i18n import M  # noqa: PLC0415
        return str(M(self.code))


REGISTRY = {
    "REFLECT_FACTS": ("file", "FACTS.json", _Semantic("knobs.sem.reflect_facts")),
    "REFLECT_DOC": ("file", "STATE.md", _Semantic("knobs.sem.reflect_doc")),
    "REFLECT_DOCS": ("list", "STATE.md,AGENTS.md,README.md", _Semantic("knobs.sem.reflect_docs")),
    "REFLECT_HISTORY_SECS": ("value", "", _Semantic("knobs.sem.reflect_history_secs")),
    "REFLECT_RETIRED": ("value", "", _Semantic("knobs.sem.reflect_retired")),
    "REFLECT_NAKED_MIN": ("number", "100", _Semantic("knobs.sem.reflect_naked_min")),
    "REFLECT_STALE_DAYS": ("number", "", _Semantic("knobs.sem.reflect_stale_days")),
    "REFLECT_REPLAY": ("flag", "", _Semantic("knobs.sem.reflect_replay")),
    "REFLECT_REPLAY_TIMEOUT": ("number", "10", _Semantic("knobs.sem.reflect_replay_timeout")),
    "REFLECT_READMES": ("list", "README.md", _Semantic("knobs.sem.reflect_readmes")),
    "REFLECT_RETRACTIONS": ("file", "retractions.json", _Semantic("knobs.sem.reflect_retractions")),
    "REFLECT_QUESTIONS": ("dir", "questions", _Semantic("knobs.sem.reflect_questions")),
    "REFLECT_HISTORY": ("file", "HISTORY.md", _Semantic("knobs.sem.reflect_history")),
    "REFLECT_INVARIANTS": ("file", "", _Semantic("knobs.sem.reflect_invariants")),
    "REFLECT_INSTRUMENTS": ("file", "", _Semantic("knobs.sem.reflect_instruments")),
    "REFLECT_INSTRUMENT_DAYS": ("number", "", _Semantic("knobs.sem.reflect_instrument_days")),
    "REFLECT_DOCTOR": ("file", "doctor.json", _Semantic("knobs.sem.reflect_doctor")),
    "REFLECT_DOCTOR_TIMEOUT": ("number", "2", _Semantic("knobs.sem.reflect_doctor_timeout")),
    "REFLECT_WORLD": ("file", "world.json", _Semantic("knobs.sem.reflect_world")),
    "REFLECT_WORLD_LINE": ("value", "", _Semantic("knobs.sem.reflect_world_line")),
    "REFLECT_AB": ("file", "ab.json", _Semantic("knobs.sem.reflect_ab")),
    "REFLECT_PINS": ("file", "pins.json", _Semantic("knobs.sem.reflect_pins")),
    "REFLECT_LOCKS": ("file", "upstream-lock.json", _Semantic("knobs.sem.reflect_locks")),
    "REFLECT_MEASURE_MODULE": ("value", "", _Semantic("knobs.sem.reflect_measure_module")),
    "REFLECT_PHASES": ("value", "", _Semantic("knobs.sem.reflect_phases")),
    "REFLECT_COMMENTS": ("value", "mismatch", _Semantic("knobs.sem.reflect_comments")),
    "REFLECT_NO_PRINCIPLES": ("flag", "", _Semantic("knobs.sem.reflect_no_principles")),
    "REFLECT_LANG": ("value", "", _Semantic("knobs.sem.reflect_lang")),
    "REFLECT_LANGS": ("list", "", _Semantic("knobs.sem.reflect_langs")),
    "REFLECT_I18N": ("dir", "", _Semantic("knobs.sem.reflect_i18n")),
    "REFLECT_I18N_ROOT": ("dir", "", _Semantic("knobs.sem.reflect_i18n_root")),
    "REFLECT_SNAPSHOT_ROOT": ("dir", "", _Semantic("knobs.sem.reflect_snapshot_root")),
    "REFLECT_SECRETS": ("file", "secrets.json", _Semantic("knobs.sem.reflect_secrets")),
}

KINDS = ("file", "list", "dir", "number", "flag", "value")
CONFIG_NAME = "knobs.json"
FLAG_TRUTHY = ("1", "true", "yes", "on")
FLAG_FALSY = ("0", "false", "no", "off")


def _tool_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _repo_root(root=None):
    if root:
        return root
    g = sys.modules.get("gate")
    if g is not None and getattr(g, "GATE_REPO", None):
        return g.GATE_REPO
    return os.environ.get("GATE_REPO") or _tool_root()


def knobs_table(rows=None):
    """Render the Markdown table of registered knobs."""
    rows = REGISTRY if rows is None else rows
    lines = ["| knob | kind | default | meaning |", "|---|---|---|---|"]
    for name in sorted(rows):
        kind, default, sem = rows[name]
        lines.append("| `%s` | %s | %s | %s |" % (name, kind, default or "--", sem))
    return "\n".join(lines)


def repo_config(root=None):
    """Read optional `<repo>/knobs.json`; absent/invalid yields `{}`."""
    path = os.path.join(_repo_root(root), CONFIG_NAME)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v).strip() for k, v in data.items()
            if isinstance(k, str) and isinstance(v, (str, int, float, bool))}


def raw(name, root=None):
    """Resolve raw knob string (`os.environ > repo_config > None`), distinguishing unset from empty."""
    if name in os.environ:
        return os.environ[name]
    return repo_config(root).get(name)


def get(name, root=None):
    """Read knob `name` (trimmed); empty/unset falls back to `REGISTRY[name][1]`."""
    val = (raw(name, root) or "").strip()
    return val or REGISTRY[name][1]


def flag(name, root=None):
    """Read a flag-kind knob as `True`, `False`, or `None` (unset/unrecognized)."""
    val = (raw(name, root) or "").strip().lower()
    if val in FLAG_TRUTHY:
        return True
    if val in FLAG_FALSY:
        return False
    return None


def docs_names(root=None):
    """Configured living document paths from `REFLECT_DOCS`."""
    return [s.strip() for s in get("REFLECT_DOCS", root).split(",") if s.strip()]


def readme_names(root=None):
    """Configured README group; unset uses registry default, explicit empty returns `[]`."""
    val = raw("REFLECT_READMES", root)
    if val is None or not val.strip():
        if val is not None:
            return []
        val = REGISTRY["REFLECT_READMES"][1]
    return [s.strip() for s in val.split(",") if s.strip()]


def served_langs(root=None):
    """Languages declared in `REFLECT_LANGS` (empty = all installed packs)."""
    return [s.strip() for s in (raw("REFLECT_LANGS", root) or "").split(",") if s.strip()]


def questions_dir(root=None):
    """Open-questions directory name (`REFLECT_QUESTIONS`)."""
    return get("REFLECT_QUESTIONS", root)


def repo_path(name, root=None):
    """Resolve knob `name` relative to `root` (or current audited repo); empty returns `None`."""
    rel = get(name, root)
    if not rel:
        return None
    base = _repo_root(root)
    return rel if os.path.isabs(rel) else os.path.join(base, rel)


def questions_path(root=None):
    """Absolute path of the open-questions directory."""
    return repo_path("REFLECT_QUESTIONS", root)


def history_secs(root=None):
    """Append-only history section numbers from `REFLECT_HISTORY_SECS`."""
    return tuple(s for s in (raw("REFLECT_HISTORY_SECS", root) or "").split(",") if s)


def _config_entry_problems(base, k, v, msg):
    if k not in REGISTRY:
        return [msg("knobs.phantom_token", token=k)]
    if not isinstance(v, str) or not v.strip():
        return [msg("knobs.config_invalid_value", knob=k)]
    if REGISTRY[k][0] in ("file", "dir") and not os.path.exists(os.path.join(base, v.strip())):
        return [msg("knobs.config_missing_target", knob=k, target=v.strip())]
    return []


def config_problems(root=None):
    """Validate `<repo>/knobs.json` structure, keys, and referenced file/dir targets."""
    from i18n import M  # noqa: PLC0415
    base = _repo_root(root)
    path = os.path.join(base, CONFIG_NAME)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return [M("knobs.config_corrupt", path=CONFIG_NAME, error=exc)]
    if not isinstance(data, dict):
        return [M("knobs.config_corrupt", path=CONFIG_NAME, error="not a JSON object")]
    return [p for k, v in sorted(data.items())
            for p in _config_entry_problems(base, k, v, M)]


def _environ_read_key(node):
    """Return `REFLECT_*` key if AST node reads `os.environ.get('REFLECT_...')` or `os.environ['REFLECT_...']`."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
        tgt = node.func.value
        key_node = node.args[0] if node.args else None
    elif isinstance(node, ast.Subscript):
        tgt, key_node = node.value, node.slice
    else:
        return None
    is_env = (isinstance(tgt, ast.Attribute) and tgt.attr == "environ"
              and isinstance(tgt.value, ast.Name) and tgt.value.id == "os")
    if (is_env and isinstance(key_node, ast.Constant)
            and isinstance(key_node.value, str) and key_node.value.startswith("REFLECT_")):
        return key_node.value
    return None


def _is_test_node(stmt):
    """Exempt test/selftest functions and `__main__` blocks from direct-env check."""
    if isinstance(stmt, ast.FunctionDef):
        return stmt.name == "_cases" or "case" in stmt.name or stmt.name.endswith("_ok")
    return isinstance(stmt, ast.If)


def _suite_py_sources():
    sources = []
    root = _tool_root()
    for sub in ("zreflect", "reflect-hooks"):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith(".py") and n not in ("knobs.py", "harness.py"):
                sources.append((sub + "/" + n, open(os.path.join(d, n), encoding="utf-8").read()))
    return sources


def direct_environ_problems(sources=None):
    """Report production code outside `knobs.py` that reads `REFLECT_*` directly via `os.environ`."""
    from i18n import M  # noqa: PLC0415
    items = _suite_py_sources() if sources is None else sources
    out = []
    for rel, text in items:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for stmt in tree.body:
            if _is_test_node(stmt):
                continue
            for node in ast.walk(stmt):
                key = _environ_read_key(node)
                if key:
                    out.append(M("knobs.inline_default_literal", file=rel,
                                 lineno=getattr(node, "lineno", 0),
                                 literal="os.environ", knob=key))
    return out


def _docs_follow_case():
    import tempfile  # noqa: PLC0415
    registered = [s.strip() for s in REGISTRY["REFLECT_DOCS"][1].split(",") if s.strip()]
    prev = os.environ.pop("REFLECT_DOCS", None)
    try:
        with tempfile.TemporaryDirectory() as d:
            if docs_names(d) != registered:
                return False
            with open(os.path.join(d, CONFIG_NAME), "w", encoding="utf-8") as fh:
                fh.write('{"REFLECT_DOCS": "cfg.md"}\n')
            if docs_names(d) != ["cfg.md"]:
                return False
            os.environ["REFLECT_DOCS"] = "env.md"
            return docs_names(d) == ["env.md"]
    finally:
        os.environ.pop("REFLECT_DOCS", None)
        if prev is not None:
            os.environ["REFLECT_DOCS"] = prev


def _config_problems_case():
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, CONFIG_NAME)
        open(p, "w", encoding="utf-8").write("{broken")
        if [x.code for x in config_problems(d)] != ["knobs.config_corrupt"]:
            return False
        ghost = "REFLECT_" + "GHOST"
        open(p, "w", encoding="utf-8").write('{"%s": "1", "REFLECT_FACTS": "missing.json"}\n' % ghost)
        return [x.code for x in config_problems(d)] == [
            "knobs.config_missing_target", "knobs.phantom_token"]


def _flag_case():
    name = "REFLECT_" + "FLAG_PROBE"
    prev = os.environ.get(name)
    try:
        for v, want in (("TRUE", True), ("false", False), ("", None)):
            os.environ[name] = v
            if flag(name) is not want:
                return False
        os.environ.pop(name, None)
        return flag(name) is None
    finally:
        if prev is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prev


def _semantic_case():
    from i18n import NULL, Catalog, bind  # noqa: PLC0415
    sem = [(k, w) for k, _d, w in REGISTRY.values() if isinstance(w, _Semantic)]
    if not sem:
        return False
    with bind(NULL):
        if not all(str(w) == w.code for _k, w in sem):
            return False
    fake = {w.code: "SENTENCE %s" % w.code for _k, w in sem}
    with bind(Catalog.load("xx", {"xx": fake})):
        return all(str(w).startswith("SENTENCE ") for _k, w in sem)


def _cases():
    return [
        ("knobs.registry_entry_shape",
         lambda: all(k in KINDS and isinstance(d, str) and w.strip()
                     for k, d, w in REGISTRY.values()) and len(REGISTRY) >= 20),
        ("★ knobs.semantic_code_and_pack", lambda: _semantic_case()),
        ("★ knobs.flag_three_states", lambda: _flag_case()),
        ("★ knobs.docs_names_follow_registry", lambda: _docs_follow_case()),
        ("★ knobs.config_problems_detected", lambda: _config_problems_case()),
        ("★ knobs.direct_environ_bypass_caught",
         lambda: [p.code for p in direct_environ_problems(
             [("zreflect/bad.py", 'import os\nX = os.environ.get("REFLECT_FACTS")\n')])]
         == ["knobs.inline_default_literal"]),
        ("knobs.get_and_helpers",
         lambda: get("REFLECT_FACTS") == REGISTRY["REFLECT_FACTS"][1]
         and questions_dir() == REGISTRY["REFLECT_QUESTIONS"][1]
         and repo_path("REFLECT_FACTS", "/r") == os.path.join("/r", REGISTRY["REFLECT_FACTS"][1])
         and repo_path("REFLECT_INVARIANTS", "/r") is None
         and isinstance(repo_config(), dict)
         and config_problems() == []
         and isinstance(history_secs(), tuple)
         and len(knobs_table().splitlines()) > 10),
    ]


MODULE = {
    "name": "Knob registry",
    "desc": "single roster of REFLECT_* and os.environ > knobs.json > REGISTRY resolution",
    "selftest": True,
}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gate import main_selftest_or  # noqa: PLC0415
    from i18n import M  # noqa: PLC0415

    def _run(argv):
        if "--list" in argv:
            print(knobs_table())
            return 0
        if argv and argv[0] in ("--help", "-h"):
            print(M("knobs.usage"), file=sys.stderr)
            return 0
        print(M("knobs.module_only"), file=sys.stderr)
        print(M("knobs.usage"), file=sys.stderr)
        return 2

    sys.exit(main_selftest_or(sys.argv[1:], M("gate.title.knobs"), _cases, _run))
