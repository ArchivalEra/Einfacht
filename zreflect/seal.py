#!/usr/bin/env python3
"""Single-tier SHA-256 seal for shared suite files (`file_sha256` + `tree_sha256`).

Locks shared core modules, built-in gates, language packs, hooks, and `ruff.toml`
while leaving consumer `measure_*.py` and consumer-added `check_*.py` unsealed.
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


def _runs_at_from_call(call):
    """Extract string literal `runs_at` keyword from a `meta(...)` call, default `'commit'`."""
    for kw in call.keywords:
        if kw.arg == "runs_at" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "commit"


def _decl_kind(path, builtin):
    """Return `'module'`, `'builtin_gate'`, or `None` for `.py` file at `path`."""
    try:
        tree = ast.parse(_read_norm(path))
    except (OSError, SyntaxError, UnicodeError):
        return None
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        names = {t.id for t in stmt.targets if isinstance(t, ast.Name)}
        if "MODULE" in names:
            return "module"
        if ("GATE" in names and isinstance(stmt.value, ast.Call)
                and _runs_at_from_call(stmt.value) in builtin):
            return "builtin_gate"
    return None


def _builtin_phases():
    """Built-in phases owned by registry (lazy import avoids module cycle)."""
    import registry  # noqa: PLC0415
    return set(registry.BUILTIN_PHASES)


def _collect_lang_packs(root, zdir, out):
    """Append sorted repo-relative paths for all `zreflect/lang/*.json` and `lang/*/*.json` packs."""
    lang_dir = os.path.join(zdir, "lang")
    if not os.path.isdir(lang_dir):
        return
    for entry in sorted(os.listdir(lang_dir)):
        full = os.path.join(lang_dir, entry)
        if os.path.isfile(full) and entry.endswith(".json"):
            out.append(os.path.relpath(full, root).replace(os.sep, "/"))
        elif os.path.isdir(full):
            for fname in sorted(os.listdir(full)):
                if fname.endswith(".json"):
                    p = os.path.join(full, fname)
                    out.append(os.path.relpath(p, root).replace(os.sep, "/"))


def _sealed_zreflect(root, zdir, builtin, include_gates=True):
    """Collect sorted repo-relative paths of sealed files inside `zreflect/`."""
    out = []
    for name in sorted(os.listdir(zdir)):
        if name.endswith(".py") and not name.startswith("measure_") and name != "__init__.py":
            full = os.path.join(zdir, name)
            kind = _decl_kind(full, builtin)
            if kind == "module" or (include_gates and kind == "builtin_gate"):
                out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    _collect_lang_packs(root, zdir, out)
    return out


def _sealed_hooks(root):
    """Collect sorted repo-relative paths of sealed `.py` files under `reflect-hooks/`."""
    hooks = os.path.join(root, "reflect-hooks")
    if not os.path.isdir(hooks):
        return []
    return ["reflect-hooks/" + name for name in sorted(os.listdir(hooks))
            if os.path.isfile(os.path.join(hooks, name)) and name.endswith(".py")]


def _sealed_targets(root, zdir, include_gates=True):
    """Core files in `(root, zdir)` that belong under the SHA-256 seal."""
    builtin = _builtin_phases()
    targets = _sealed_zreflect(root, zdir, builtin, include_gates) + _sealed_hooks(root)
    if os.path.isfile(os.path.join(root, "ruff.toml")):
        targets.append("ruff.toml")
    return sorted(set(targets))


def _entry_for(root, rel):
    """Build seal metadata dict `{'file_sha256': <hex>}`."""
    return {"file_sha256": _sha256_text(_read_norm(os.path.join(root, rel)))}


def _merkle_root(files_map):
    """Deterministic Merkle root SHA-256 over sorted `rel:file_sha256`."""
    lines = ["%s:%s" % (rel, e["file_sha256"]) for rel, e in sorted(files_map.items())]
    return _sha256_text("\n".join(lines))


def _valid_entry(entry):
    """Is `entry` a valid single-tier file hash dictionary?"""
    return (isinstance(entry, dict)
            and isinstance(entry.get("file_sha256"), str)
            and len(entry["file_sha256"]) == 64)


def _load_seal(path):
    """Read and validate `SEAL.json`. Returns `(data, err_msg)`."""
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError, UnicodeError) as exc:
        return None, M("seal.corrupt", error=exc)
    if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("files"), dict)
            or not isinstance(data.get("tree_sha256"), str)
            or not all(_valid_entry(v) for v in data["files"].values())):
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


def _skip_optional(root, rel):
    """Allow hooks to be absent only in non-git minimal unit-test fixtures."""
    return (rel.startswith("reflect-hooks/")
            and not os.path.isdir(os.path.join(root, "reflect-hooks"))
            and not os.path.isdir(os.path.join(root, ".git")))


def _verify_entry(root, rel, expected, out):
    """Verify one sealed file path on disk against its `expected` SHA-256."""
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        if not _skip_optional(root, rel):
            out.append(M("seal.file_missing", file=rel))
        return
    try:
        actual = _entry_for(root, rel)
    except (OSError, UnicodeError):
        out.append(M("seal.file_tampered", file=rel))
        return
    if expected.get("file_sha256") != actual.get("file_sha256"):
        out.append(M("seal.file_tampered", file=rel))


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
    for rel in _sealed_targets(rt, zd, include_gates=False):
        if rel not in sealed_files:
            out.append(M("seal.unsealed_core_file", file=rel))
    return out


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


def reseal(targets, root=None, zdir=None):
    """Update `SEAL.json` for nominated files. Returns `(tree_sha256, error_msg)`."""
    zd = zdir or gate.zdir()
    rt = root or gate.tool_repo()
    disk_targets = _sealed_targets(rt, zd, include_gates=True)
    resolved, unknown = _norm_target_names(list(targets), disk_targets)
    if unknown:
        return None, M("seal.reseal_unknown_target", file=", ".join(unknown))
    sp = seal_path(zd)
    files_map = {}
    if os.path.isfile(sp) and list(targets) != ["ALL"]:
        data, err = _load_seal(sp)
        if err:
            return None, err
        files_map = dict(data["files"])
    for rel in resolved:
        files_map[rel] = _entry_for(rt, rel)
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
        "def _cases():\n    return [('ok', lambda: 1 == 1), ('\u2605 red', lambda: 1 > 2)]\n"
        "MODULE = {'name': 'm', 'desc': 'd', 'selftest': True}\n"
    )
    return {"zreflect/mod_a.py": sample_py,
            "zreflect/lang/en.json": '{\n "a.ok": "ok"\n}\n'}


def _case_tamper_and_exempt():
    """Clean verify + 1-byte tamper + consumer measure/custom-gate exemption."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
        sha, err = reseal(["ALL"], root=rt, zdir=zd)
        if err or not sha or not seal_exists(zd) or current_tree_sha(rt, zd) != sha:
            return False
        if verify_problems(rt, zd) != []:
            return False
        with open(os.path.join(zd, "measure_custom.py"), "w", encoding="utf-8") as fh:
            fh.write("def measure():\n    return {}\n")
        with open(os.path.join(zd, "check_custom.py"), "w", encoding="utf-8") as fh:
            fh.write("GATE = meta('x', 'y', runs_at='commit')\n")
        if verify_problems(rt, zd) != []:
            return False
        p = os.path.join(zd, "mod_a.py")
        orig = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(orig.replace("return 0", "return 1"))
        return [x.code for x in verify_problems(rt, zd)] == ["seal.file_tampered"]


def _case_reseal_and_unsealed():
    """Reseal updates hash; unsealed platform module is caught."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
        reseal(["ALL"], root=rt, zdir=zd)
        p = os.path.join(zd, "mod_a.py")
        orig = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(orig.replace("return 0", "return 1"))
        sha2, err2 = reseal(["zreflect/mod_a.py"], root=rt, zdir=zd)
        if err2 or not sha2 or verify_problems(rt, zd) != []:
            return False
        with open(os.path.join(zd, "mod_b.py"), "w", encoding="utf-8") as fh:
            fh.write("MODULE = {'name': 'b', 'desc': 'd', 'selftest': False}\n")
        return [x.code for x in verify_problems(rt, zd)] == ["seal.unsealed_core_file"]


def _case_merkle_and_missing():
    """Missing SEAL.json, corrupt entry schema, and tampered tree_sha256 report."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
        if [x.code for x in verify_problems(rt, zd)] != ["seal.missing"]:
            return False
        reseal(["ALL"], root=rt, zdir=zd)
        sp = seal_path(zd)
        data = json.loads(open(sp, encoding="utf-8").read())
        data["tree_sha256"] = "0" * 64
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data))
        if "seal.tree_mismatch" not in [x.code for x in verify_problems(rt, zd)]:
            return False
        data["files"]["zreflect/mod_a.py"] = {"file_sha256": "short"}
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data))
        return [x.code for x in verify_problems(rt, zd)] == ["seal.corrupt"]


def _cases():
    return [
        ("★ seal.tamper_and_consumer_exempt", lambda: _case_tamper_and_exempt()),
        ("★ seal.reseal_and_unsealed_module", lambda: _case_reseal_and_unsealed()),
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
    "single-tier SHA-256 verification and reseal for the shared core",
    selftest=True)

if __name__ == "__main__":
    sys.exit(main_selftest_or(sys.argv[1:], "seal", _cases, _cli))
