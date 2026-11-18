#!/usr/bin/env python3
"""Two-tier hard SHA-256 seal for shared suite code and selftest yardsticks.

Tier 1 (`yardstick_sha256` + case counts): `_cases*`, `_fixture*`, `GATE`,
`MODULE`, `RULES`, `CASES`, and `ruff.toml`. Tier 2 (`file_sha256` + Merkle root
`tree_sha256`): full normalized file contents across shared suite surfaces.
Consumer files (`measure_*.py`, `Einfacht.env`, custom-phase gates) stay outside.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from gate import fatal, main_selftest_or, module_meta  # noqa: E402
from i18n import M  # noqa: E402

SEAL_NAME = "SEAL.json"
DECL_NAMES = frozenset({"GATE", "MODULE", "RULES", "CASES"})
OPTIONAL_ROOT_FILES = ("gates-selftest.sh",)


def seal_path(zdir=None):
    """Path to `SEAL.json` inside `zdir` (defaults to `gate.zdir()`)."""
    return os.path.join(zdir or gate.zdir(), SEAL_NAME)


def seal_exists(zdir=None):
    """Is a hard-hash `SEAL.json` present in the suite directory?"""
    return os.path.isfile(seal_path(zdir))


def _read_norm(path):
    """Read UTF-8 text with CRLF normalized to LF for deterministic hashing."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def _sha256_text(text):
    """Hex SHA-256 of normalized UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_yardstick_stmt(stmt):
    """Is `stmt` a Tier-1 declaration, case builder, or case-append statement?"""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return stmt.name.startswith(("_cases", "_fixture"))
    if isinstance(stmt, ast.Assign):
        return any(isinstance(t, ast.Name) and t.id in DECL_NAMES for t in stmt.targets)
    if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)):
        return stmt.value.func.value.id == "CASES"
    return False


def _case_counts_in_node(node):
    """Count `(total_cases, red_cases)` static 2-tuple case literals inside `node`."""
    total = red = 0
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Tuple) and len(sub.elts) == 2):
            continue
        first = sub.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            total += 1
            if first.value.lstrip().startswith("\u2605"):
                red += 1
    return total, red


def _py_yardstick(norm_text):
    """Compute `(yardstick_sha256, cases, red_cases)` for one normalized `.py` file."""
    tree = ast.parse(norm_text)
    lines = norm_text.splitlines()
    segments = []
    total = red = 0
    for stmt in tree.body:
        if not _is_yardstick_stmt(stmt):
            continue
        end = stmt.end_lineno or stmt.lineno
        segments.append("\n".join(lines[stmt.lineno - 1:end]))
        t, r = _case_counts_in_node(stmt)
        total += t
        red += r
    if not segments:
        return None, 0, 0
    return _sha256_text("\n---\n".join(segments)), total, red


def _runs_at_from_call(call):
    """Extract string literal `runs_at` keyword from a `meta(...)` call, default `'commit'`."""
    for kw in call.keywords:
        if kw.arg == "runs_at" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "commit"


def _core_decl_ok(path, builtin):
    """Should this `.py` file be sealed? Built-in gates and declared modules only."""
    try:
        tree = ast.parse(_read_norm(path))
    except (OSError, SyntaxError, UnicodeError):
        return False
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        names = {t.id for t in stmt.targets if isinstance(t, ast.Name)}
        if "MODULE" in names:
            return True
        if "GATE" in names and isinstance(stmt.value, ast.Call):
            return _runs_at_from_call(stmt.value) in builtin
    return False


def _builtin_phases():
    """Built-in phases owned by registry (lazy import avoids module cycle)."""
    import registry  # noqa: PLC0415
    return set(registry.BUILTIN_PHASES)


def _allowed_shell():
    """Shell whitelist owned by criteria (lazy import avoids module cycle)."""
    import criteria  # noqa: PLC0415
    return set(criteria.ALLOWED_SHELL)


def _sealed_zreflect(root, zdir, builtin):
    """Collect sorted repo-relative paths of sealed files inside `zreflect/`."""
    out = []
    for name in sorted(os.listdir(zdir)):
        if name.endswith(".py") and not name.startswith("measure_") and name != "__init__.py":
            full = os.path.join(zdir, name)
            if _core_decl_ok(full, builtin):
                out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    _collect_lang_packs(root, zdir, out)
    return out


def _collect_lang_packs(root, zdir, out):
    """Append sorted repo-relative paths for all `zreflect/lang/*/*.json` pack shards."""
    lang_dir = os.path.join(zdir, "lang")
    if not os.path.isdir(lang_dir):
        return
    for lang in sorted(os.listdir(lang_dir)):
        pkg = os.path.join(lang_dir, lang)
        if not os.path.isdir(pkg):
            continue
        for fname in sorted(os.listdir(pkg)):
            if fname.endswith(".json"):
                full = os.path.join(pkg, fname)
                out.append(os.path.relpath(full, root).replace(os.sep, "/"))


def _sealed_hooks(root, allowed_sh):
    """Collect sorted repo-relative paths of sealed files under `reflect-hooks/`."""
    hooks = os.path.join(root, "reflect-hooks")
    if not os.path.isdir(hooks):
        return []
    out = []
    for name in sorted(os.listdir(hooks)):
        if name == "Einfacht.env":
            continue
        rel = "reflect-hooks/" + name
        full = os.path.join(hooks, name)
        if os.path.isfile(full) and (name.endswith(".py") or rel in allowed_sh):
            out.append(rel)
    return out


def _sealed_targets(root, zdir):
    """All core files in `(root, zdir)` that belong under the SHA-256 seal."""
    builtin = _builtin_phases()
    allowed_sh = _allowed_shell()
    targets = _sealed_zreflect(root, zdir, builtin) + _sealed_hooks(root, allowed_sh)
    for rel in ("ruff.toml", "gates-selftest.sh"):
        if os.path.isfile(os.path.join(root, rel)):
            targets.append(rel)
    return sorted(set(targets))


def _entry_for(root, rel):
    """Build seal metadata dict `{file_sha256, [yardstick_sha256, cases, red_cases]}`."""
    norm = _read_norm(os.path.join(root, rel))
    entry = {"file_sha256": _sha256_text(norm)}
    if rel.endswith(".py"):
        ysha, cases, red = _py_yardstick(norm)
        if ysha is not None:
            entry["yardstick_sha256"] = ysha
            entry["cases"] = cases
            entry["red_cases"] = red
    elif rel == "ruff.toml":
        entry["yardstick_sha256"] = entry["file_sha256"]
    return entry


def _merkle_root(files_map):
    """Deterministic Merkle root SHA-256 over sorted `(rel, file_sha256, yardstick_sha256)`."""
    lines = ["%s:%s:%s" % (rel, e["file_sha256"], e.get("yardstick_sha256") or "")
             for rel, e in sorted(files_map.items())]
    return _sha256_text("\n".join(lines))


def _load_seal(path):
    """Read and minimally validate `SEAL.json`. Returns `(data, err_msg)`."""
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError, UnicodeError) as exc:
        return None, M("seal.corrupt", error=exc)
    if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("files"), dict)
            or not isinstance(data.get("tree_sha256"), str)):
        return None, M("seal.corrupt", error="schema")
    return data, None


def current_tree_sha(root=None, zdir=None, verified=False):
    """Return `tree_sha256` from `SEAL.json`, or `None` when absent/invalid."""
    zd = zdir or gate.zdir()
    if not seal_exists(zd):
        return None
    data, err = _load_seal(seal_path(zd))
    if err or (not verified and verify_problems(root=root, zdir=zd)):
        return None
    return data["tree_sha256"]


def _compare_entry(rel, expected, actual, out):
    """Compare one disk file's computed entry against sealed `expected` entry."""
    if expected.get("yardstick_sha256") != actual.get("yardstick_sha256"):
        out.append(M("seal.yardstick_tampered", file=rel))
    elif expected.get("file_sha256") != actual.get("file_sha256"):
        out.append(M("seal.file_tampered", file=rel))


def _skip_optional(root, rel):
    """Optional files absent in minimal bootstrap copies (`gates-selftest.sh`, hooks if absent)."""
    if rel in OPTIONAL_ROOT_FILES:
        return True
    return rel.startswith("reflect-hooks/") and not os.path.isdir(
        os.path.join(root, "reflect-hooks"))


def _verify_entry(root, rel, expected, out):
    """Verify one sealed file path on disk against its `expected` metadata."""
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        if not _skip_optional(root, rel):
            out.append(M("seal.file_missing", file=rel))
        return
    try:
        actual = _entry_for(root, rel)
    except (OSError, SyntaxError, UnicodeError):
        out.append(M("seal.file_tampered", file=rel))
        return
    _compare_entry(rel, expected, actual, out)


def verify_problems(root=None, zdir=None):
    """Verify disk files against `SEAL.json`. Returns list of `Message` problems."""
    zd = zdir or gate.zdir()
    rt = root or gate.tool_repo()
    sp = seal_path(zd)
    if not os.path.isfile(sp):
        return [M("seal.missing", path=sp)]
    data, err = _load_seal(sp)
    if err:
        return [err]
    out = []
    sealed_files = data["files"]
    if _merkle_root(sealed_files) != data["tree_sha256"]:
        out.append(M("seal.tree_mismatch"))
    for rel, expected in sorted(sealed_files.items()):
        _verify_entry(rt, rel, expected, out)
    for rel in _sealed_targets(rt, zd):
        if rel not in sealed_files:
            out.append(M("seal.unsealed_core_file", file=rel))
    return out


def _reseal_guard(rel, old, new, yardstick, allow_drop):
    """Enforce Tier-1 / Tier-2 reseal separation and case-count monotonicity."""
    if not yardstick and old is not None and (
            old.get("yardstick_sha256") != new.get("yardstick_sha256")):
        return M("seal.reseal_refused_yardstick", file=rel)
    if yardstick and old is not None and not allow_drop:
        oc, nc = old.get("cases", 0), new.get("cases", 0)
        ored, nred = old.get("red_cases", 0), new.get("red_cases", 0)
        if nc < oc or nred < ored:
            return M("seal.reseal_refused_case_drop", file=rel,
                     old_cases=oc, new_cases=nc, old_red=ored, new_red=nred)
    return None


def _norm_target_names(targets, disk_targets):
    """Expand explicit target list (or `['ALL']`) and return `(resolved, unknown)`."""
    if targets == ["ALL"]:
        return disk_targets, []
    disk_set = set(disk_targets)
    resolved, unknown = [], []
    for raw in targets:
        rel = raw.strip().replace("\\", "/")
        if rel in disk_set:
            resolved.append(rel)
        else:
            unknown.append(rel)
    return resolved, unknown


def reseal(targets, yardstick=False, allow_case_drop=False, root=None, zdir=None):
    """Update `SEAL.json` for nominated files. Returns `(tree_sha256, error_msg)`."""
    zd = zdir or gate.zdir()
    rt = root or gate.tool_repo()
    disk_targets = _sealed_targets(rt, zd)
    resolved, unknown = _norm_target_names(list(targets), disk_targets)
    if unknown:
        return None, M("seal.reseal_unknown_target", file=", ".join(unknown))
    sp = seal_path(zd)
    existing = {}
    if os.path.isfile(sp):
        data, err = _load_seal(sp)
        if err:
            return None, err
        existing = dict(data["files"])
    return _apply_reseal(rt, sp, existing, resolved, yardstick, allow_case_drop)


def _apply_reseal(root, sp, files_map, resolved, yardstick, allow_drop):
    """Validate and write updated entries for `resolved` into `sp`."""
    for rel in resolved:
        old = files_map.get(rel)
        new = _entry_for(root, rel)
        err = _reseal_guard(rel, old, new, yardstick, allow_drop)
        if err:
            return None, err
        files_map[rel] = new
    tree = _merkle_root(files_map)
    payload = {"schema": 1, "tree_sha256": tree, "files": files_map}
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return tree, None


def _make_seal_fixture(tmp, files):
    """Create a minimal sealed temp suite layout with `files` `{rel: content}`."""
    zd = os.path.join(tmp, "zreflect")
    os.makedirs(zd, exist_ok=True)
    for rel, content in files.items():
        full = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    return tmp, zd


def _base_fixture_files():
    """Minimal valid core module + language pack for temp-repo seal selftests."""
    sample_py = (
        "def run():\n    return 0\n"
        "def _cases():\n    return [\n"
        "        ('ok', lambda: True),\n"
        "        ('\u2605 red', lambda: 1 > 2),\n"
        "    ]\n"
        "MODULE = {'name': 'm', 'desc': 'd', 'selftest': True}\n"
    )
    return {"zreflect/mod_a.py": sample_py,
            "zreflect/lang/en/a.json": '{\n "a.ok": "ok"\n}\n'}


def _case_tamper_and_exempt():
    """Clean verify + 1-byte code/yardstick/merkle tamper + consumer exemption."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
        sha, err = reseal(["ALL"], yardstick=True, root=rt, zdir=zd)
        if err or not sha or not seal_exists(zd) or current_tree_sha(rt, zd) != sha:
            return False
        if verify_problems(rt, zd) != []:
            return False
        # Consumer additions must never trip seal
        with open(os.path.join(zd, "measure_custom.py"), "w", encoding="utf-8") as fh:
            fh.write("def measure():\n    return {}\n")
        with open(os.path.join(zd, "check_custom.py"), "w", encoding="utf-8") as fh:
            fh.write("GATE = meta('x', 'y', runs_at='lab')\n")
        if verify_problems(rt, zd) != []:
            return False
        # 1-byte code tamper -> seal.file_tampered
        p = os.path.join(zd, "mod_a.py")
        orig = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(orig.replace("return 0", "return 1"))
        if [x.code for x in verify_problems(rt, zd)] != ["seal.file_tampered"]:
            return False
        # 1-byte yardstick tamper -> seal.yardstick_tampered
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(orig.replace("1 > 2", "2 > 1"))
        return [x.code for x in verify_problems(rt, zd)] == ["seal.yardstick_tampered"]


def _case_reseal_guards():
    """Reseal refuses yardstick drift and case drops; allows with explicit flags."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
        reseal(["ALL"], yardstick=True, root=rt, zdir=zd)
        p = os.path.join(zd, "mod_a.py")
        orig = open(p, encoding="utf-8").read()
        # Implementation edit succeeds under --reseal
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(orig.replace("return 0", "return 1"))
        sha2, err2 = reseal(["zreflect/mod_a.py"], yardstick=False, root=rt, zdir=zd)
        if err2 or not sha2 or verify_problems(rt, zd):
            return False
        # Yardstick edit refused under --reseal
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(orig.replace("        ('\u2605 red', lambda: 1 > 2),\n", ""))
        _s3, err3 = reseal(["zreflect/mod_a.py"], yardstick=False, root=rt, zdir=zd)
        if not err3 or err3.code != "seal.reseal_refused_yardstick":
            return False
        # Case drop refused without allow_case_drop
        _s4, err4 = reseal(["zreflect/mod_a.py"], yardstick=True, root=rt, zdir=zd)
        if not err4 or err4.code != "seal.reseal_refused_case_drop":
            return False
        # Succeeds when allow_case_drop=True
        sha5, err5 = reseal(["zreflect/mod_a.py"], yardstick=True, allow_case_drop=True,
                            root=rt, zdir=zd)
        return err5 is None and bool(sha5) and verify_problems(rt, zd) == []


def _case_merkle_and_missing():
    """Missing SEAL.json and tampered tree_sha256 are both reported."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
        if [x.code for x in verify_problems(rt, zd)] != ["seal.missing"]:
            return False
        reseal(["ALL"], yardstick=True, root=rt, zdir=zd)
        sp = seal_path(zd)
        data = json.loads(open(sp, encoding="utf-8").read())
        data["tree_sha256"] = "0" * 64
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data))
        return "seal.tree_mismatch" in [x.code for x in verify_problems(rt, zd)]


def _cases():
    return [
        ("★ seal.tamper_and_consumer_exempt", lambda: _case_tamper_and_exempt()),
        ("★ seal.reseal_guards", lambda: _case_reseal_guards()),
        ("★ seal.merkle_and_missing", lambda: _case_merkle_and_missing()),
    ]


def _cli(argv):
    if "--verify" in argv:
        probs = verify_problems()
        if probs:
            for p in probs:
                print("  · %s" % p, file=sys.stderr)
            return 1
        print(current_tree_sha(verified=True) or "")
        return 0
    return fatal(M("seal.missing", path=seal_path()))


MODULE = module_meta(
    "Core seal",
    "two-tier SHA-256 verification and monotonic reseal for the shared core",
    selftest=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "seal", _cases, _cli))
