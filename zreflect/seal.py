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


def _is_consumer_custom_gate(path, builtin):
    try:
        tree = ast.parse(_read_norm(path))
    except (OSError, SyntaxError, UnicodeError):
        return False
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            names = {t.id for t in stmt.targets if isinstance(t, ast.Name)}
            if "GATE" in names and isinstance(stmt.value, ast.Call):
                return _runs_at_from_call(stmt.value) not in builtin
    return False


def _sealed_zreflect(root, zdir, builtin, include_gates=True):
    """Collect sorted repo-relative paths of sealed files inside `zreflect/`."""
    out = []
    for dirpath, dirnames, filenames in os.walk(zdir):
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", "lang"))
        in_root = os.path.abspath(dirpath) == os.path.abspath(zdir)
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            if in_root and (name.startswith("measure_")
                            or (name != "__init__.py" and _is_consumer_custom_gate(os.path.join(dirpath, name), builtin))
                            or (not include_gates and _decl_kind(os.path.join(dirpath, name), builtin) == "builtin_gate")):
                continue
            out.append(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))
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
        with open(path, encoding="utf-8") as fh:
            data = json.loads(fh.read())
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


def _verify_entry(root, rel, expected, out):
    """Verify one sealed file path on disk against its `expected` SHA-256."""
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        out.append(M("seal.file_missing", file=rel))
        return
    try:
        actual = _entry_for(root, rel)
    except (OSError, UnicodeError):
        out.append(M("seal.file_tampered", file=rel))
        return
    if expected.get("file_sha256") != actual.get("file_sha256"):
        out.append(M("seal.file_tampered", file=rel))


def _ruff_toml_problems(rt, sealed_files):
    if "zreflect/check_lint.py" not in sealed_files:
        return []
    if "ruff.toml" not in sealed_files:
        return [M("seal.unsealed_core_file", file="ruff.toml")]
    if not os.path.isfile(os.path.join(rt, "ruff.toml")):
        return [M("seal.file_missing", file="ruff.toml")]
    return []


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
    for rel in _sealed_targets(rt, zd, include_gates=True):
        if rel not in sealed_files:
            out.append(M("seal.unsealed_core_file", file=rel))
    return out + _ruff_toml_problems(rt, sealed_files)


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


def _check_core_target_approval(rel, rt, prev_files, anc, rec, approval):
    prev_sha = (prev_files.get(rel) or {}).get("file_sha256", "NONE")
    cur_sha = _entry_for(rt, rel)["file_sha256"] if os.path.isfile(os.path.join(rt, rel)) else "DELETED"
    if prev_sha == cur_sha:
        return None
    probs = approval.verify_receipt(
        rec, repo_name=anc.get("repo") or approval.repo_id(rt),
        action="seal.core", target=rel, prev_sha256=prev_sha, target_sha256=cur_sha,
        pub_b64=anc.get("approver_pub"), revoked_ids=anc.get("revoked_ids") or [],
    )
    return probs[0] if probs else None


def _collect_reseal_probs(resolved, rt, zd, prev_files, anc, rec, approval):
    probs = []
    if "zreflect/doc.py" in resolved:
        probs.extend(approval.check_principles_anchor(
            anc, doc_py_sha=approval.sha256_file(os.path.join(zd, "doc.py")),
            principles_md_sha=(anc.get("principles") or {}).get("principles_md_sha256"),
            no_principles=False, receipt=rec))
    if anc.get("lock_core", False):
        for rel in resolved:
            if rel != "zreflect/doc.py":
                p = _check_core_target_approval(rel, rt, prev_files, anc, rec, approval)
                if p is not None:
                    probs.append(p)
    return probs


def _check_reseal_approval(resolved, rt, zd, prev_files):
    import approval  # noqa: PLC0415
    anc = approval.load_anchors(rt)
    if anc is None:
        return None
    if not anc:
        return M("approval.anchors_broken")
    rec = approval.load_receipt(root=rt)
    probs = _collect_reseal_probs(resolved, rt, zd, prev_files, anc, rec, approval)
    sync_codes = ("approval.receipt_required", "approval.scope_mismatch", "approval.expired")
    if probs and any(p.code in sync_codes for p in probs) and approval._auto_sync_for_probs(rt, anc, probs):
        probs = _collect_reseal_probs(
            resolved, rt, zd, prev_files, anc, approval.load_receipt(root=rt), approval)
    return probs[0] if probs else None


def _load_prev_files(sp):
    if not os.path.isfile(sp):
        return {}, None
    data, err = _load_seal(sp)
    return ({}, err) if err else (dict(data["files"]), None)


def reseal(targets, root=None, zdir=None, force_all=False):
    """Update `SEAL.json` for nominated files. Returns `(tree_sha256, error_msg)`."""
    zd = zdir or gate.zdir()
    rt = root or gate.tool_repo()
    disk_targets = _sealed_targets(rt, zd, include_gates=True)
    resolved, unknown = _norm_target_names(list(targets), disk_targets)
    if unknown:
        return None, M("seal.reseal_unknown_target", file=", ".join(unknown))
    sp = seal_path(zd)
    prev_files, err = _load_prev_files(sp)
    if err:
        return None, err
    doc_err = _check_reseal_approval(resolved, rt, zd, prev_files)
    if doc_err is not None:
        return None, doc_err
    if os.path.isfile(sp) and list(targets) == ["ALL"] and not force_all:
        return None, M("seal.reseal_all_needs_force")
    files_map = {}
    if os.path.isfile(sp) and list(targets) != ["ALL"]:
        untouched_probs = [p for p in verify_problems(root=rt, zdir=zd)
                           if (p.params or {}).get("file") not in resolved]
        if untouched_probs:
            return None, untouched_probs[0]
        files_map = prev_files
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
            fh.write("GATE = meta('x', 'y', runs_at='custom')\n")
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


def _case_tamper_and_q22_seal_gaps():
    """Verify unsealed builtin gate, undeclared helper .py, missing hooks without .git, and reseal ALL guard."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        files = dict(_base_fixture_files())
        files["zreflect/check_core.py"] = "GATE = {'name': 'c', 'desc': 'd', 'runs_at': 'commit'}\n"
        files["reflect-hooks/hook.py"] = "def run():\n    return 0\n"
        rt, zd = _make_seal_fixture(tmp, files)
        reseal(["ALL"], root=rt, zdir=zd)
        if reseal(["ALL"], root=rt, zdir=zd)[1].code != "seal.reseal_all_needs_force":
            return False
        sp = seal_path(zd)
        data = json.loads(open(sp, encoding="utf-8").read())
        data["files"].pop("zreflect/check_core.py")
        data["tree_sha256"] = _merkle_root(data["files"])
        open(sp, "w", encoding="utf-8").write(json.dumps(data))
        if "seal.unsealed_core_file" not in [x.code for x in verify_problems(rt, zd)]:
            return False
        reseal(["ALL"], root=rt, zdir=zd, force_all=True)
        os.remove(os.path.join(rt, "reflect-hooks", "hook.py"))
        if "seal.file_missing" not in [x.code for x in verify_problems(rt, zd)]:
            return False
        open(os.path.join(zd, "helper.py"), "w", encoding="utf-8").write("x = 1\n")
        return "seal.unsealed_core_file" in [x.code for x in verify_problems(rt, zd)]


def _case_core_reseal_approval():
    """Core reseal requires Ed25519 `seal.core` receipt when ANCHORS.json sets lock_core."""
    import base64  # noqa: PLC0415
    import datetime  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    import approval  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("ascii")
    old_pub = approval.PINNED_APPROVER_PUB
    approval.PINNED_APPROVER_PUB = pub_b64
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
            reseal(["ALL"], root=rt, zdir=zd)
            prev_sha = json.loads(open(seal_path(zd), encoding="utf-8").read())["files"]["zreflect/mod_a.py"]["file_sha256"]
            open(os.path.join(rt, "ANCHORS.json"), "w", encoding="utf-8").write(json.dumps({
                "schema": 1, "repo": "Demo", "approver_pub": pub_b64, "lock_core": True, "revoked_ids": [],
            }))
            p = os.path.join(zd, "mod_a.py")
            open(p, "w", encoding="utf-8").write(open(p, encoding="utf-8").read().replace("return 0", "return 1"))
            _, err = reseal(["zreflect/mod_a.py"], root=rt, zdir=zd)
            if not err or err.code != "approval.receipt_required" or err.params.get("action") != "seal.core":
                return False
            rec = approval._sign_fixture(priv, {
                "id": "r-core", "repo": "Demo", "action": "seal.core", "target": "zreflect/mod_a.py",
                "prev_sha256": prev_sha, "target_sha256": approval.sha256_file(p),
                "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat(),
            })
            os.makedirs(os.path.join(rt, ".git"), exist_ok=True)
            approval._save_receipt_to_bundle(rec, os.path.join(rt, ".git", "einfacht-receipt.json"))
            sha2, err2 = reseal(["zreflect/mod_a.py"], root=rt, zdir=zd)
            return err2 is None and bool(sha2) and verify_problems(rt, zd) == []
    finally:
        approval.PINNED_APPROVER_PUB = old_pub


def _case_auto_sync_reseal():
    """Missing seal.core receipt triggers _auto_sync_for_probs to submit and pull approved receipt."""
    import base64  # noqa: PLC0415
    import datetime  # noqa: PLC0415
    import http.server  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    import threading  # noqa: PLC0415

    import approval  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("ascii")
    state = {"approve": False}

    class _H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            resp = {"id": "req-1", "display_id": "Demo#1", "status": "pending"}
            if state["approve"]:
                rec = approval._sign_fixture(priv, {
                    "id": "r-sync", "repo": body["repo"], "action": body["action"],
                    "target": body["target_path"], "prev_sha256": body["prev_sha256"],
                    "target_sha256": body["target_sha256"],
                    "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat(),
                })
                resp = {"id": "req-1", "display_id": "Demo#1", "status": "approved_single", "receipt": rec}
            raw = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = http.server.HTTPServer(("127.0.0.1", 0), _H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    old_pub, old_url = approval.PINNED_APPROVER_PUB, os.environ.get(approval.APPROVER_URL_ENV)
    approval.PINNED_APPROVER_PUB = pub_b64
    os.environ[approval.APPROVER_URL_ENV] = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rt, zd = _make_seal_fixture(tmp, _base_fixture_files())
            reseal(["ALL"], root=rt, zdir=zd)
            open(os.path.join(rt, "ANCHORS.json"), "w", encoding="utf-8").write(json.dumps({
                "schema": 1, "repo": "Demo", "approver_pub": pub_b64, "lock_core": True, "revoked_ids": [],
            }))
            for args in (["git", "init"], ["git", "config", "user.email", "t@e.com"],
                         ["git", "config", "user.name", "T"], ["git", "add", "."],
                         ["git", "commit", "-m", "init"]):
                subprocess.run(args, cwd=rt, check=True, capture_output=True)
            p = os.path.join(zd, "mod_a.py")
            open(p, "w", encoding="utf-8").write(open(p, encoding="utf-8").read().replace("return 0", "return 1"))
            _, err1 = reseal(["zreflect/mod_a.py"], root=rt, zdir=zd)
            if not err1 or err1.code != "approval.receipt_required":
                return False
            state["approve"] = True
            sha2, err2 = reseal(["zreflect/mod_a.py"], root=rt, zdir=zd)
            return err2 is None and bool(sha2) and verify_problems(rt, zd) == []
    finally:
        approval.PINNED_APPROVER_PUB = old_pub
        if old_url is None:
            os.environ.pop(approval.APPROVER_URL_ENV, None)
        else:
            os.environ[approval.APPROVER_URL_ENV] = old_url
        srv.shutdown()
        srv.server_close()


def _cases():
    return [
        ("★ seal.tamper_and_consumer_exempt", lambda: _case_tamper_and_exempt()),
        ("★ seal.reseal_and_unsealed_module", lambda: _case_reseal_and_unsealed()),
        ("★ seal.merkle_and_missing", lambda: _case_merkle_and_missing()),
        ("★ seal.q22_builtin_gate_helper_hooks_and_reseal_guard", lambda: _case_tamper_and_q22_seal_gaps()),
        ("★ seal.core_reseal_requires_approval", lambda: _case_core_reseal_approval()),
        ("★ seal.auto_sync_submits_and_pulls", lambda: _case_auto_sync_reseal()),
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
