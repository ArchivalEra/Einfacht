#!/usr/bin/env python3
"""Offline Ed25519 approval receipt verifier & tamper-evident anchor for questions/PRINCIPLES."""

import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import gate
import knobs
from gate import module_meta, selftest
from i18n import M

ANCHORS_FILE = "ANCHORS.json"
RECEIPT_ENV = "EINFACHT_APPROVAL_RECEIPT"
APPROVER_URL_ENV = "EINFACHT_APPROVER_URL"
DEFAULT_APPROVER_URL = "http://127.0.0.1:18443"
CONTROLLED_PREFIXES = ("zreflect/", "reflect-hooks/", "questions/")
CONTROLLED_FILES = frozenset({"PRINCIPLES.md", "knobs.json", "ruff.toml"})
SYSTEM_PUB_PATH = "/etc/einfacht-approver/signing_pub.pem"
PINNED_APPROVER_PUB = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAvf9ckQEI6CkK30ookgtqjT6I3H0PXzo6ov25212pyDQ=\n"
    "-----END PUBLIC KEY-----\n"
)


def pinned_approver_pub():
    if os.path.isfile(SYSTEM_PUB_PATH):
        try:
            with open(SYSTEM_PUB_PATH, encoding="ascii") as fh:
                txt = fh.read().strip()
            if "BEGIN PUBLIC KEY" in txt:
                return txt + "\n"
        except OSError:
            pass
    return PINNED_APPROVER_PUB


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return sha256_bytes((text or "").encode("utf-8"))


def sha256_file(path):
    try:
        with open(path, "rb") as fh:
            return sha256_bytes(fh.read())
    except OSError:
        return None


def _strip_status_settling(text):
    lines = (text or "").splitlines()
    out = []
    skip_cont = False
    for ln in lines:
        if re.match(r"(?i)^\*{0,2}(Status|Settling)\*{0,2}\s*:\s*\*{0,2}", ln.strip()):
            skip_cont = ln.strip().lstrip("*").lower().startswith("settling")
            continue
        if skip_cont and (ln.startswith(("  ", "\t")) or not ln.strip()):
            if not ln.strip():
                skip_cont = False
            continue
        skip_cont = False
        out.append(ln)
    return "\n".join(out).strip()


def _field_val(text, name):
    if not text:
        return ""
    import check_questions  # noqa: PLC0415
    return check_questions.field(text, name) or ""


def _is_none_like(val):
    low = (val or "").strip().lower()
    return not low or low == "none" or low.startswith(("none ", "none--"))


def question_snapshot(text):
    return {
        "sha256": sha256_text(text),
        "status": _field_val(text, "Status").lower(),
        "settling": _field_val(text, "Settling"),
        "body_sha256": sha256_text(_strip_status_settling(text)),
    }


def canonical_payload(receipt):
    body = receipt["payload"] if isinstance(receipt.get("payload"), dict) else {
        k: v for k, v in receipt.items() if k != "sig"
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _receipt_body(receipt):
    return receipt["payload"] if isinstance(receipt.get("payload"), dict) else receipt


def _parse_iso(ts):
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _load_pubkey(pub_key):
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: PLC0415
    if "BEGIN PUBLIC KEY" in str(pub_key):
        loaded = serialization.load_pem_public_key(str(pub_key).encode("ascii"))
        if not isinstance(loaded, Ed25519PublicKey):
            raise ValueError("not ed25519")
        return loaded
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_key))


def _verify_sig(payload, sig_b64, pub_key):
    try:
        from cryptography.exceptions import InvalidSignature  # noqa: PLC0415
    except ImportError:
        return False, "crypto_unavailable"
    try:
        pub = _load_pubkey(pub_key)
        pub.verify(base64.b64decode(sig_b64), payload)
        return True, None
    except (InvalidSignature, ValueError, TypeError):
        return False, "signature_invalid"


def _select_receipt(receipt, *, action, target, target_sha256):
    if isinstance(receipt, dict) and isinstance(receipt.get("receipts"), list):
        items = receipt["receipts"]
    elif isinstance(receipt, list):
        items = receipt
    else:
        return receipt
    for item in items:
        if not isinstance(item, dict):
            continue
        body = _receipt_body(item)
        if (body.get("action") == action
                and (body.get("target") or body.get("target_path")) == target
                and body.get("target_sha256") == target_sha256):
            return item
    return items[0] if len(items) == 1 else None


def verify_receipt(receipt, *, repo_name, action, target, prev_sha256, target_sha256,
                   pub_b64, revoked_ids=(), now=None):
    """Verify an Ed25519 approval receipt offline. Returns list of `Message` (empty = valid)."""
    picked = _select_receipt(receipt, action=action, target=target, target_sha256=target_sha256)
    if not isinstance(picked, dict) or not pub_b64:
        return [M("approval.receipt_required", action=action, target=target)]
    body = _receipt_body(picked)
    rec_id = str(body.get("id") or body.get("receipt_id") or "")
    deleg_id = str(body.get("delegation_id") or "")
    rev = set(revoked_ids)
    if rec_id in rev or (deleg_id and deleg_id in rev):
        return [M("approval.revoked", id=deleg_id or rec_id)]
    exp = _parse_iso(body.get("expires_at"))
    cur = now or datetime.now(timezone.utc)
    if exp is None or exp <= cur:
        return [M("approval.expired", id=rec_id)]
    rec_target = body.get("target") or body.get("target_path")
    if (body.get("repo") != repo_name or body.get("action") != action
            or rec_target != target):
        return [M("approval.scope_mismatch", action=action, target=target)]
    if (body.get("prev_sha256") != prev_sha256
            or body.get("target_sha256") != target_sha256):
        return [M("approval.hash_mismatch", target=target)]
    ok, err = _verify_sig(canonical_payload(picked), str(picked.get("sig") or ""), pub_b64)
    if not ok:
        if err == "crypto_unavailable":
            return [M("approval.crypto_unavailable", target=target)]
        return [M("approval.signature_invalid", target=target)]
    return []


def _default_receipt_path(root=None):
    import subprocess  # noqa: PLC0415
    base = os.path.abspath(root or gate.GATE_REPO)
    try:
        r = subprocess.run(["git", "-C", base, "rev-parse", "--git-dir"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            gdir = r.stdout.strip()
            if not os.path.isabs(gdir):
                gdir = os.path.join(base, gdir)
            return os.path.join(gdir, "einfacht-receipt.json")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return os.path.join(base, ".git", "einfacht-receipt.json")


def load_receipt(path=None, root=None):
    base = root or gate.GATE_REPO
    p = path or os.environ.get(RECEIPT_ENV)
    if not p or not os.path.isfile(p):
        fallback = _default_receipt_path(base)
        p = fallback if os.path.isfile(fallback) else None
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, (dict, list)) else None
    except (OSError, ValueError):
        return None


def _save_receipt_to_bundle(receipt, out_path):
    items = []
    if os.path.isfile(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                old = json.load(fh)
            if isinstance(old, dict) and isinstance(old.get("receipts"), list):
                items = [x for x in old["receipts"] if isinstance(x, dict)]
            elif isinstance(old, dict) and ("sig" in old or "payload" in old):
                items = [old]
        except (OSError, ValueError):
            items = []
    nb = _receipt_body(receipt)
    nkey = (nb.get("repo"), nb.get("action"), nb.get("target") or nb.get("target_path"))
    kept = [x for x in items if (
        _receipt_body(x).get("repo"), _receipt_body(x).get("action"),
        _receipt_body(x).get("target") or _receipt_body(x).get("target_path"),
    ) != nkey]
    kept.append(receipt)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"receipts": kept}, fh, indent=2)


def repo_id(root=None):
    """Canonical repo identifier: `owner/repo` from git remote `origin` when available, else dir basename."""
    import subprocess  # noqa: PLC0415
    base = os.path.abspath(root or gate.GATE_REPO)
    try:
        r = subprocess.run(["git", "-C", base, "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            url = r.stdout.strip().rstrip("/")
            if url.endswith(".git"):
                url = url[:-4]
            parts = [p for p in re.split(r"[:/]", url) if p]
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return os.path.basename(base)


def load_anchors(root=None):
    base = root or gate.GATE_REPO
    p = os.path.join(base, ANCHORS_FILE)
    if not os.path.isfile(p):
        import subprocess  # noqa: PLC0415
        for cmd in (
            ["git", "-C", base, "ls-files", "--error-unmatch", ANCHORS_FILE],
            ["git", "-C", base, "cat-file", "-e", "HEAD:" + ANCHORS_FILE],
        ):
            try:
                if subprocess.run(cmd, capture_output=True, text=True, timeout=5).returncode == 0:
                    return {}
            except (OSError, subprocess.TimeoutExpired):
                pass
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return None
        if (data.get("approver_pub") or "").strip() != pinned_approver_pub().strip():
            return {}
        return data
    except (OSError, ValueError):
        return {}


def is_legal_settlement(cur_text, anchor_entry):
    """True when a question only transitions to `resolved` without altering body or weakening Settling."""
    if cur_text is None or not anchor_entry:
        return False
    cur = question_snapshot(cur_text)
    if cur["status"] != "resolved" or cur["body_sha256"] != anchor_entry.get("body_sha256"):
        return False
    prev_set = anchor_entry.get("settling", "")
    if cur["settling"] == prev_set:
        return True
    return _is_none_like(prev_set) and not _is_none_like(cur["settling"])


def check_question_change(rel_path, cur_text, anchor_entry, receipt=None,
                          pub_b64=None, repo_name="", revoked_ids=(), now=None):
    """Check one question against its anchor. Settling needs NO receipt; creation/tampering DOES."""
    cur_sha = sha256_text(cur_text) if cur_text is not None else "DELETED"
    if not anchor_entry:
        return verify_receipt(
            receipt, repo_name=repo_name, action="question.create", target=rel_path,
            prev_sha256="NONE", target_sha256=cur_sha,
            pub_b64=pub_b64, revoked_ids=revoked_ids, now=now,
        )
    if cur_sha == anchor_entry.get("sha256"):
        return []
    if is_legal_settlement(cur_text, anchor_entry):
        return []
    cur_status = _field_val(cur_text, "Status").lower() if cur_text is not None else "deleted"
    action = "question.wontfix" if cur_status == "wontfix" else "question.modify"
    return verify_receipt(
        receipt, repo_name=repo_name, action=action, target=rel_path,
        prev_sha256=anchor_entry.get("sha256", ""), target_sha256=cur_sha,
        pub_b64=pub_b64, revoked_ids=revoked_ids, now=now,
    )


def _head_anchors(root=None):
    import subprocess  # noqa: PLC0415
    base = root or gate.GATE_REPO
    try:
        r = subprocess.run(["git", "-C", base, "show", "HEAD:" + ANCHORS_FILE],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        return data if isinstance(data, dict) else {}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _is_legal_anchor_settlement(cur_entry, head_entry):
    if not head_entry or not cur_entry:
        return False
    if cur_entry.get("status") != "resolved" or cur_entry.get("body_sha256") != head_entry.get("body_sha256"):
        return False
    prev_set, cur_set = head_entry.get("settling", ""), cur_entry.get("settling", "")
    return cur_set == prev_set or (_is_none_like(prev_set) and not _is_none_like(cur_set))


def _check_anchor_questions_diff(anchors, head, rec, qdir=None):
    head_q = head.get("questions") or {}
    cur_q = anchors.get("questions") or {}
    if qdir:
        prefix = qdir.rstrip("/") + "/"
        head_q = {k: v for k, v in head_q.items() if k.startswith(prefix)}
        cur_q = {k: v for k, v in cur_q.items() if k.startswith(prefix)}
    pub = head.get("approver_pub") or anchors.get("approver_pub")
    rname = head.get("repo") or anchors.get("repo") or ""
    revoked = head.get("revoked_ids") or ()
    out = []
    for k in sorted(set(head_q) | set(cur_q)):
        ce, he = cur_q.get(k), head_q.get(k)
        if ce == he or _is_legal_anchor_settlement(ce, he):
            continue
        if he is None:
            out += verify_receipt(rec, repo_name=rname, action="question.create", target=k,
                                  prev_sha256="NONE", target_sha256=(ce or {}).get("sha256", ""),
                                  pub_b64=pub, revoked_ids=revoked)
        else:
            act = "question.wontfix" if (ce or {}).get("status") == "wontfix" else "question.modify"
            out += verify_receipt(rec, repo_name=rname, action=act, target=k,
                                  prev_sha256=he.get("sha256", ""),
                                  target_sha256=ce.get("sha256", "") if ce else "DELETED",
                                  pub_b64=pub, revoked_ids=revoked)
    return out


def check_anchors_integrity(anchors, root=None, receipt=None, qdir=None):
    """Verify `ANCHORS.json` was not weakened or tampered relative to `HEAD:ANCHORS.json`."""
    head = _head_anchors(root)
    if head is None:
        return []
    if not head or anchors.get("repo") != head.get("repo"):
        return [M("approval.anchors_broken")]
    if head.get("lock_core") and not anchors.get("lock_core"):
        return [M("approval.anchors_broken")]
    if set(head.get("revoked_ids") or ()) - set(anchors.get("revoked_ids") or ()):
        return [M("approval.anchors_broken")]
    pub = head.get("approver_pub") or anchors.get("approver_pub")
    rname = head.get("repo") or ""
    revoked = head.get("revoked_ids") or ()
    out = _check_anchor_questions_diff(anchors, head, receipt, qdir=qdir)
    hp, cp = head.get("principles") or {}, anchors.get("principles") or {}
    if cp != hp:
        out += check_principles_anchor(
            head, doc_py_sha=cp.get("doc_py_sha256"),
            principles_md_sha=cp.get("principles_md_sha256"),
            no_principles=bool(cp.get("no_principles", False)), receipt=receipt)
    for g in sorted(set(anchors.get("off_gates") or ()) - set(head.get("off_gates") or ())):
        out += verify_receipt(receipt, repo_name=rname, action="gate.off", target=g,
                              prev_sha256="on", target_sha256="off", pub_b64=pub, revoked_ids=revoked)
    return out


def _auto_sync_targets(base, probs):
    codes = ("approval.receipt_required", "approval.scope_mismatch", "approval.expired")
    targets = sorted({p.params["target"] for p in probs
                      if getattr(p, "code", "") in codes and p.params.get("target")})
    if not targets and any(getattr(p, "code", "") == "approval.expired" for p in probs):
        import impact  # noqa: PLC0415
        targets = impact.git_changed_files(base) or []
    return targets


def _post_auto_sync(url, payload, out_path):
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    try:
        req = urllib.request.Request(url + "/requests", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            resp = json.loads(r.read().decode("utf-8"))
        if resp.get("receipt"):
            _save_receipt_to_bundle(resp["receipt"], out_path)
            return True
        if resp.get("status") in ("denied", "rejected_duplicate"):
            label = resp.get("display_id") or resp.get("id", "")
            reason = resp.get("deny_reason") or resp.get("status")
            print(f"  · approval.denied(id={label!r}, target={payload['target_path']!r}, reason={reason!r})",
                  file=sys.stderr)
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return False


def _auto_sync_for_probs(base, anchors, probs):
    """Mechanically submit missing-receipt targets, surface deny_reason, and pull ready receipts."""
    if not os.path.exists(os.path.join(base, ".git")):
        return False
    if (anchors.get("approver_pub") or "").strip() != pinned_approver_pub().strip():
        return False
    targets = _auto_sync_targets(base, probs)
    if not targets:
        return False
    reqs = build_requests(targets, root=base, repo_name=anchors.get("repo") or repo_id(base))
    url = (os.environ.get(APPROVER_URL_ENV) or DEFAULT_APPROVER_URL).rstrip("/")
    out_path = os.environ.get(RECEIPT_ENV) or _default_receipt_path(base)
    results = [_post_auto_sync(url, p, out_path) for p in reqs]
    return any(results)


def _eval_questions_anchor(files, anchors, root, rec, qdir):
    q_map = anchors.get("questions") or {}
    if qdir:
        prefix = qdir.rstrip("/") + "/"
        q_map = {k: v for k, v in q_map.items() if k.startswith(prefix)}
    pub = anchors.get("approver_pub")
    rname = anchors.get("repo") or repo_id(root)
    revoked = anchors.get("revoked_ids") or []
    out = check_anchors_integrity(anchors, root=root, receipt=rec, qdir=qdir)
    for rel in sorted(set(q_map) | set(files)):
        out += check_question_change(
            rel, files.get(rel), q_map.get(rel),
            receipt=rec, pub_b64=pub, repo_name=rname, revoked_ids=revoked,
        )
    return out


def check_questions_against_anchor(files, root=None, receipt=None, qdir=None):
    base = root or gate.GATE_REPO
    anchors = load_anchors(base)
    if anchors is None:
        return []
    if not anchors:
        return [M("approval.anchors_broken")]
    rec = receipt if receipt is not None else load_receipt(root=base)
    out = _eval_questions_anchor(files, anchors, base, rec, qdir)
    if receipt is None and out and _auto_sync_for_probs(base, anchors, out):
        out = _eval_questions_anchor(files, anchors, base, load_receipt(root=base), qdir)
    return out


def check_principles_anchor(anchors, *, doc_py_sha, principles_md_sha, no_principles,
                            receipt=None, now=None):
    """Verify `PRINCIPLES.md`, `doc.py`, and `REFLECT_NO_PRINCIPLES` against anchor."""
    if not anchors:
        return []
    pr = anchors.get("principles") or {}
    pub = anchors.get("approver_pub")
    rname = anchors.get("repo") or ""
    revoked = anchors.get("revoked_ids") or []
    out = []
    if no_principles and not pr.get("no_principles", False):
        out += verify_receipt(
            receipt, repo_name=rname, action="principles.disable", target="REFLECT_NO_PRINCIPLES",
            prev_sha256="false", target_sha256="true", pub_b64=pub, revoked_ids=revoked, now=now)
    if principles_md_sha != pr.get("principles_md_sha256"):
        out += verify_receipt(
            receipt, repo_name=rname, action="principles.edit", target="PRINCIPLES.md",
            prev_sha256=pr.get("principles_md_sha256", ""),
            target_sha256=principles_md_sha or "DELETED",
            pub_b64=pub, revoked_ids=revoked, now=now)
    if doc_py_sha != pr.get("doc_py_sha256"):
        out += verify_receipt(
            receipt, repo_name=rname, action="seal.doc", target="zreflect/doc.py",
            prev_sha256=pr.get("doc_py_sha256", ""),
            target_sha256=doc_py_sha or "DELETED",
            pub_b64=pub, revoked_ids=revoked, now=now)
    return out


def check_principles_repo(root=None, receipt=None):
    base = root or gate.GATE_REPO
    anchors = load_anchors(base)
    if anchors is None:
        return []
    if not anchors:
        return [M("approval.anchors_broken")]
    doc_sha = sha256_file(os.path.join(gate.zdir(), "doc.py"))
    md_sha = sha256_file(os.path.join(base, "PRINCIPLES.md"))
    no_pr = knobs.flag("REFLECT_NO_PRINCIPLES") is True
    rec = receipt if receipt is not None else load_receipt(root=base)
    out = check_principles_anchor(anchors, doc_py_sha=doc_sha, principles_md_sha=md_sha, no_principles=no_pr, receipt=rec)
    if receipt is None and out and _auto_sync_for_probs(base, anchors, out):
        out = check_principles_anchor(
            anchors, doc_py_sha=doc_sha, principles_md_sha=md_sha, no_principles=no_pr, receipt=load_receipt(root=base))
    return out


def _eval_off_gates(extra, anchors, base, rec, now):
    pub, rname, revoked = anchors.get("approver_pub"), anchors.get("repo") or repo_id(base), anchors.get("revoked_ids") or []
    out = []
    for name in extra:
        out += verify_receipt(
            rec, repo_name=rname, action="gate.off", target=name,
            prev_sha256="on", target_sha256="off", pub_b64=pub, revoked_ids=revoked, now=now)
    return out


def check_off_gates_anchor(off_list, root=None, receipt=None, now=None):
    base = root or gate.GATE_REPO
    anchors = load_anchors(base)
    if anchors is None:
        return []
    if not anchors:
        return [M("approval.anchors_broken")]
    allowed = set(anchors.get("off_gates") or ())
    extra = sorted(os.path.basename(f) for f in off_list if os.path.basename(f) not in allowed)
    if not extra:
        return []
    rec = receipt if receipt is not None else load_receipt(root=base)
    out = _eval_off_gates(extra, anchors, base, rec, now)
    if receipt is None and out and _auto_sync_for_probs(base, anchors, out):
        out = _eval_off_gates(extra, anchors, base, load_receipt(root=base), now)
    return out


def _build_anchors(root, pub_b64=None):
    import check_questions  # noqa: PLC0415
    files = check_questions.collect(root=root)
    q_map = {k: question_snapshot(v) for k, v in sorted(files.items())}
    off_list = sorted(x.strip() for x in (knobs.get("REFLECT_OFF_GATES") or "").split(",") if x.strip())
    return {
        "schema": 1,
        "repo": repo_id(root),
        "approver_pub": pub_b64,
        "lock_core": True,
        "revoked_ids": [],
        "off_gates": off_list,
        "principles": {
            "doc_py_sha256": sha256_file(os.path.join(gate.zdir(), "doc.py")),
            "principles_md_sha256": sha256_file(os.path.join(root, "PRINCIPLES.md")),
            "no_principles": knobs.flag("REFLECT_NO_PRINCIPLES") is True,
        },
        "questions": q_map,
    }


def _sync_settled(root):
    """Update `ANCHORS.json` ONLY for questions that legally settled (`resolved`, no approval needed)."""
    import check_questions  # noqa: PLC0415
    anchors = load_anchors(root)
    if not anchors:
        return 2
    files = check_questions.collect(root=root)
    q_map = anchors.setdefault("questions", {})
    pub = anchors.get("approver_pub")
    rname = anchors.get("repo") or repo_id(root)
    revoked = anchors.get("revoked_ids") or []
    rec = load_receipt(root=root)
    for rel, text in sorted(files.items()):
        if rel not in q_map:
            probs = verify_receipt(
                rec, repo_name=rname, action="question.create", target=rel,
                prev_sha256="NONE", target_sha256=sha256_text(text),
                pub_b64=pub, revoked_ids=revoked,
            )
            if probs:
                print(probs[0], file=sys.stderr)
                return 1
            q_map[rel] = question_snapshot(text)
            continue
        if q_map[rel].get("sha256") == sha256_text(text):
            continue
        if not is_legal_settlement(text, q_map[rel]):
            print(M("approval.receipt_required", action="question.modify", target=rel), file=sys.stderr)
            return 2
        q_map[rel] = question_snapshot(text)
    with open(os.path.join(root, ANCHORS_FILE), "w", encoding="utf-8") as fh:
        json.dump(anchors, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    print(M("approval.anchors_synced", count=len(q_map)))
    return 0


def _norm_rel(raw):
    return str(raw or "").replace("\\", "/").lstrip("./")


def _is_controlled_path(rel):
    norm = _norm_rel(rel)
    return norm in CONTROLLED_FILES or any(norm.startswith(p) for p in CONTROLLED_PREFIXES)


def _classify_action(rel, text=None, prev_sha="NONE"):
    if rel == "zreflect/doc.py":
        return "seal.doc"
    if rel.startswith(("zreflect/", "reflect-hooks/")) or rel == "ruff.toml":
        return "seal.core"
    if rel == "PRINCIPLES.md":
        return "principles.edit"
    if rel.startswith("questions/"):
        if prev_sha == "NONE":
            return "question.create"
        return "question.wontfix" if _field_val(text, "Status").lower() == "wontfix" else "question.modify"
    return "gate.off"


def _git_prev_sha_and_diff(root, rel):
    import subprocess  # noqa: PLC0415
    prev_sha = "NONE"
    diff_txt = ""
    try:
        r1 = subprocess.run(["git", "-C", root, "show", "HEAD:" + rel],
                            capture_output=True, timeout=10)
        if r1.returncode == 0:
            prev_sha = sha256_bytes(r1.stdout)
        r2 = subprocess.run(["git", "-C", root, "diff", "HEAD", "--", rel],
                            capture_output=True, text=True, timeout=10)
        if r2.returncode == 0:
            diff_txt = r2.stdout[:2000]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return prev_sha, diff_txt


def init_anchors(root=None):
    base = root or gate.GATE_REPO
    p = os.path.join(base, ANCHORS_FILE)
    if os.path.isfile(p):
        return 1
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(_build_anchors(base, pub_b64=pinned_approver_pub()), fh,
                  indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return 0


def build_requests(changed_paths, root=None, repo_name=None, diff_fn=None, sha_fn=None):
    """Build purely mechanical controlled-scope approval request payloads (zero agent-authored prose)."""
    base = root or gate.GATE_REPO
    rname = repo_name or repo_id(base)
    out = []
    for raw in sorted(set(changed_paths or ())):
        rel = _norm_rel(raw)
        if not _is_controlled_path(rel):
            continue
        full = os.path.join(base, rel)
        text = None
        if os.path.isfile(full):
            try:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                text = None
        target_sha = sha_fn(full) if sha_fn else (sha256_file(full) or "DELETED")
        prev_sha, diff_sum = diff_fn(base, rel) if diff_fn else _git_prev_sha_and_diff(base, rel)
        out.append({
            "repo": rname,
            "agent_id": os.environ.get("USER", "agent"),
            "action": _classify_action(rel, text, prev_sha=prev_sha),
            "target_path": rel,
            "prev_sha256": prev_sha,
            "target_sha256": target_sha,
            "target_content": (text or "")[:32000],
            "diff_summary": diff_sum or ("(new or binary file %s)" % rel),
        })
    return out


def _poll_request(url, resp):
    import time as _time  # noqa: PLC0415
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    deadline = _time.time() + 300
    while _time.time() < deadline:
        _time.sleep(3)
        try:
            with urllib.request.urlopen(f"{url}/requests/{resp['id']}", timeout=10) as r:
                polled = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            continue
        if polled.get("status") != "pending":
            return polled
    return resp


def _post_one_request(url, payload, wait):
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    req = urllib.request.Request(url + "/requests", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(M("approval.receipt_required", action=payload["action"], target=payload["target_path"]) + f" ({exc})", file=sys.stderr)
        return False
    label = resp.get("display_id") or resp.get("id", "")
    print(M("approval.request_submitted", id=label, status=resp.get("status", ""),
            action=payload["action"], target=payload["target_path"], url=url))
    if wait and resp.get("status") == "pending":
        resp = _poll_request(url, resp)
    if resp.get("status") in ("denied", "rejected_duplicate") or (wait and resp.get("status") == "pending"):
        extra = f" ({resp.get('deny_reason') or resp.get('status')})"
        print(M("approval.receipt_required", action=payload["action"], target=payload["target_path"]) + extra, file=sys.stderr)
        return False
    if resp.get("receipt"):
        out_path = os.environ.get(RECEIPT_ENV) or _default_receipt_path(gate.GATE_REPO)
        _save_receipt_to_bundle(resp["receipt"], out_path)
    return True


def _submit_all(argv):
    import impact  # noqa: PLC0415
    reqs = build_requests(impact.git_changed_files(gate.GATE_REPO), root=gate.GATE_REPO)
    if not reqs:
        print(M("approval.no_controlled_changes"))
        return 0
    url = (os.environ.get(APPROVER_URL_ENV) or DEFAULT_APPROVER_URL).rstrip("/")
    wait = "--wait" in argv
    return 0 if all(_post_one_request(url, p, wait) for p in reqs) else 2


def _sign_fixture(priv, payload_dict):
    raw = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    rec = dict(payload_dict)
    rec["sig"] = base64.b64encode(priv.sign(raw)).decode("ascii")
    return rec


def _cases():
    from datetime import timedelta  # noqa: PLC0415

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: PLC0415
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    future = (now + timedelta(hours=1)).isoformat()
    past = (now - timedelta(hours=1)).isoformat()
    q_open = "# 26: test\n\n**Status:** ready-for-agent\n\n**Settling:** python3 zreflect/gate.py --selftest\n\n## Items\n1. keep\n"
    q_settled = q_open.replace("ready-for-agent", "resolved")
    q_weak = q_open.replace("python3 zreflect/gate.py --selftest", "python3 -c 'pass'")
    q_wontfix = q_open.replace("ready-for-agent", "wontfix")
    anc = question_snapshot(q_open)
    pr_anc = {"repo": "Einfacht", "approver_pub": pub_b64, "revoked_ids": ["r-rev"],
              "principles": {"doc_py_sha256": "d1", "principles_md_sha256": "p1", "no_principles": False}}
    valid_rec = _sign_fixture(priv, {
        "id": "r-1", "repo": "Einfacht", "action": "question.modify", "target": "q/26.md",
        "prev_sha256": anc["sha256"], "target_sha256": sha256_text(q_weak), "expires_at": future,
    })
    expired_rec = _sign_fixture(priv, {
        "id": "r-2", "repo": "Einfacht", "action": "question.modify", "target": "q/26.md",
        "prev_sha256": anc["sha256"], "target_sha256": sha256_text(q_weak), "expires_at": past,
    })
    revoked_rec = _sign_fixture(priv, {
        "id": "r-rev", "repo": "Einfacht", "action": "question.modify", "target": "q/26.md",
        "prev_sha256": anc["sha256"], "target_sha256": sha256_text(q_weak), "expires_at": future,
    })
    create_rec = _sign_fixture(priv, {
        "id": "r-create", "repo": "Einfacht", "action": "question.create", "target": "q/99.md",
        "prev_sha256": "NONE", "target_sha256": sha256_text(q_open), "expires_at": future,
    })
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    daemon_payload = {
        "receipt_id": "rec-daemon-1", "repo": "Einfacht", "agent_id": "worker",
        "action": "question.modify", "target_path": "q/26.md",
        "prev_sha256": anc["sha256"], "target_sha256": sha256_text(q_weak),
        "delegation_id": None, "issued_at": int(now.timestamp()), "expires_at": int(now.timestamp()) + 600,
    }
    daemon_rec = {
        "payload": daemon_payload,
        "sig": base64.b64encode(priv.sign(
            json.dumps(daemon_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )).decode("ascii"),
    }
    return [
        ("approval.settling_needs_no_receipt",
         lambda: check_question_change("q/26.md", q_settled, anc, pub_b64=pub_b64, repo_name="Einfacht", now=now) == []),
        ("★ approval.weakening_settling_blocked",
         lambda: [p.code for p in check_question_change(
             "q/26.md", q_weak, anc, pub_b64=pub_b64, repo_name="Einfacht", now=now)] == ["approval.receipt_required"]),
        ("★ approval.wontfix_blocked_without_receipt",
         lambda: [p.code for p in check_question_change(
             "q/26.md", q_wontfix, anc, pub_b64=pub_b64, repo_name="Einfacht", now=now)] == ["approval.receipt_required"]),
        ("★ approval.new_question_blocked_without_receipt",
         lambda: [p.code for p in check_question_change(
             "q/99.md", q_open, None, pub_b64=pub_b64, repo_name="Einfacht", now=now)] == ["approval.receipt_required"]
         and check_question_change(
             "q/99.md", q_open, None, receipt=create_rec, pub_b64=pub_b64, repo_name="Einfacht", now=now) == []),
        ("★ approval.principles_tamper_and_disable_blocked",
         lambda: [p.code for p in check_principles_anchor(
             pr_anc, doc_py_sha="d2", principles_md_sha="p2", no_principles=True, now=now)]
         == ["approval.receipt_required"] * 3),
        ("★ approval.tampered_target_hash_rejected",
         lambda: [p.code for p in check_question_change(
             "q/26.md", q_weak + "tamper", anc, receipt=valid_rec, pub_b64=pub_b64, repo_name="Einfacht", now=now)]
         == ["approval.hash_mismatch"]),
        ("★ approval.expired_and_revoked_rejected",
         lambda: [p.code for p in check_question_change(
             "q/26.md", q_weak, anc, receipt=expired_rec, pub_b64=pub_b64, repo_name="Einfacht", now=now)]
         == ["approval.expired"]
         and [p.code for p in check_question_change(
             "q/26.md", q_weak, anc, receipt=revoked_rec, pub_b64=pub_b64, repo_name="Einfacht",
             revoked_ids=["r-rev"], now=now)] == ["approval.revoked"]),
        ("approval.valid_ed25519_receipt_passes",
         lambda: check_question_change(
             "q/26.md", q_weak, anc, receipt=valid_rec, pub_b64=pub_b64, repo_name="Einfacht", now=now) == []
         and check_question_change(
             "q/26.md", q_weak, anc, receipt=daemon_rec, pub_b64=pub_pem, repo_name="Einfacht", now=now) == []),
        ("approval.mechanical_request_scope_and_ticket",
         lambda: [r["target_path"] for r in build_requests(
             ["src/app.py", "zreflect/doc.py", "questions/26.md"],
             root=".", repo_name="Einfacht",
             diff_fn=lambda _r, _p: ("p1", "+diff"), sha_fn=lambda _p: "t1")]
         == ["questions/26.md", "zreflect/doc.py"]
         and "reason" not in build_requests(
             ["zreflect/doc.py"], root=".", repo_name="Einfacht",
             diff_fn=lambda _r, _p: ("p1", "+diff"), sha_fn=lambda _p: "t1")[0]
         and verify_receipt(
             {"receipts": [daemon_rec, valid_rec]},
             repo_name="Einfacht", action="question.modify", target="q/26.md",
             prev_sha256=anc["sha256"], target_sha256=sha256_text(q_weak),
             pub_b64=pub_pem, now=now) == []
         and _bundle_fallback_case(daemon_rec)),
        ("★ approval.multi_repo_multi_approver_e2e", _multi_repo_e2e_case),
        ("★ approval.anchors_rm_and_tamper_blocked", _anchors_rm_and_tamper_case),
        ("★ approval.auto_sync_submits_pulls_and_surfaces_deny", _auto_sync_and_deny_case),
    ]


def _bundle_fallback_case(rec):
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, ".git"))
        p = os.path.join(d, ".git", "einfacht-receipt.json")
        _save_receipt_to_bundle(rec, p)
        loaded = load_receipt(root=d)
        return isinstance(loaded, dict) and len(loaded.get("receipts") or []) == 1
    finally:
        shutil.rmtree(d, True)


def _e2e_http_json(url, method, body=None, pw=None):
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if pw is not None:
        headers["X-Approver-Pass"] = pw
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def _e2e_compile(approver_lines):
    out = []
    for ln in approver_lines:
        parts = ln.split(":", 2)
        if len(parts) == 3:
            name, repos_csv, sec = parts[0], parts[1], parts[2]
            repos = frozenset(r.strip() for r in repos_csv.split(",") if r.strip()) or frozenset({"*"})
        else:
            name, repos, sec = parts[0], frozenset({"*"}), parts[1]
        salt = os.urandom(16)
        out.append((name, repos, salt, hashlib.pbkdf2_hmac("sha256", sec.encode("utf-8"), salt, 10_000)))
    return out


def _e2e_who(compiled, pw):
    import hmac  # noqa: PLC0415
    for name, repos, salt, dig in compiled:
        if hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 10_000), dig):
            return name, repos
    return None


def _e2e_can_access(repos, repo):
    return "*" in repos or repo in repos


def _e2e_submit_req(reqs, seq, body):
    key = (body["repo"], body["action"], body["target_path"], body["prev_sha256"], body["target_sha256"])
    for old in reversed(list(reqs.values())):
        if (old["repo"], old["action"], old["target_path"], old["prev_sha256"], old["target_sha256"]) == key:
            return 200, {"id": old["id"], "display_id": old["display_id"],
                         "status": old["status"], "deny_reason": old.get("deny_reason", ""),
                         "receipt": old.get("receipt")}
    repo = body["repo"]
    n = seq.get(repo, 0) + 1
    seq[repo] = n
    rid = f"req-{len(reqs) + 1}"
    rec = {**body, "id": rid, "display_id": f"{repo}#{n}", "status": "pending", "receipt": None}
    reqs[rid] = rec
    return 200, {"id": rid, "display_id": rec["display_id"], "status": "pending", "receipt": None}


def _e2e_decide_req(priv, reqs, body, ident):
    who, repos = ident
    r = reqs.get(body.get("req_id"))
    if not r:
        return 404, {"error": "not_found"}
    if not _e2e_can_access(repos, r["repo"]):
        return 403, {"error": "repo_forbidden", "approver": who, "repo": r["repo"]}
    if body.get("mode") == "deny":
        r["status"], r["decided_by"], r["deny_reason"] = "denied", who, str(body.get("deny_reason") or "")
        return 200, {"ok": True, "decided_by": who, "status": "denied"}
    ts = int(datetime.now(timezone.utc).timestamp())
    r["status"], r["decided_by"] = "approved_single", who
    r["receipt"] = _sign_fixture(priv, {
        "receipt_id": f"rec-{r['id']}", "repo": r["repo"], "action": r["action"],
        "target_path": r["target_path"], "prev_sha256": r["prev_sha256"],
        "target_sha256": r["target_sha256"], "decided_by": who, "issued_at": ts, "expires_at": ts + 600,
    })
    return 200, {"ok": True, "decided_by": who}


def _e2e_handle_post(priv, compiled, reqs, seq, lock, path, body, auth_pw):
    if path == "/requests":
        with lock:
            return _e2e_submit_req(reqs, seq, body)
    if path == "/api/decide":
        ident = _e2e_who(compiled, auth_pw)
        if not ident:
            return 403, {"error": "forbidden"}
        with lock:
            return _e2e_decide_req(priv, reqs, body, ident)
    return 404, {"error": "not_found"}


def _make_e2e_server(priv, approver_lines):
    import http.server  # noqa: PLC0415
    import threading  # noqa: PLC0415
    compiled = _e2e_compile(approver_lines)
    reqs: dict[str, dict] = {}
    seq: dict[str, int] = {}
    lock = threading.Lock()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send(self, code, obj):
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/api/pending":
                ident = _e2e_who(compiled, self.headers.get("X-Approver-Pass") or "")
                if not ident:
                    return self._send(403, {"error": "forbidden"})
                with lock:
                    rows = [r for r in reqs.values()
                            if r["status"] == "pending" and _e2e_can_access(ident[1], r["repo"])]
                return self._send(200, {"approver": ident[0], "pending": rows})
            rid = self.path.rsplit("/", 1)[-1]
            with lock:
                r = reqs.get(rid)
            return self._send(200 if r else 404, r or {"error": "not_found"})

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
            body = json.loads(raw.decode("utf-8") or "{}")
            code, obj = _e2e_handle_post(
                priv, compiled, reqs, seq, lock, self.path, body, self.headers.get("X-Approver-Pass") or "")
            self._send(code, obj)

    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)


def _e2e_init_repo(base, name, remote_url, pub_b64, q_text):
    import subprocess  # noqa: PLC0415
    rt = os.path.join(base, name)
    os.makedirs(os.path.join(rt, "questions"), exist_ok=True)
    subprocess.run(["git", "init", "-q", rt], check=True)
    subprocess.run(["git", "-C", rt, "remote", "add", "origin", remote_url], check=True)
    with open(os.path.join(rt, "questions", "01.md"), "w", encoding="utf-8") as fh:
        fh.write(q_text)
    anc = {"schema": 1, "repo": repo_id(rt), "approver_pub": pub_b64, "revoked_ids": [],
           "questions": {"questions/01.md": question_snapshot(q_text)}}
    with open(os.path.join(rt, ANCHORS_FILE), "w", encoding="utf-8") as fh:
        json.dump(anc, fh)
    return rt, anc["questions"]["questions/01.md"]["sha256"]


def _e2e_check_rbac_and_approve(url, r1, r2, r3):
    if _e2e_http_json(url + "/api/decide", "POST", {"req_id": r1["id"]}, pw="wrong")[0] != 403:
        return False
    pa_code, pa = _e2e_http_json(url + "/api/pending", "GET", pw="pass-alice")
    pb_code, pb = _e2e_http_json(url + "/api/pending", "GET", pw="pass-bob")
    if (pa_code, pb_code) != (200, 200) or len(pa["pending"]) != 2 or len(pb["pending"]) != 1:
        return False
    if _e2e_http_json(url + "/api/decide", "POST", {"req_id": r3["id"]}, pw="pass-alice")[0] != 403:
        return False
    if _e2e_http_json(url + "/api/decide", "POST", {"req_id": r1["id"]}, pw="pass-bob")[0] != 403:
        return False
    c1, d1 = _e2e_http_json(url + "/api/decide", "POST", {"req_id": r1["id"]}, pw="pass-alice")
    c2, d2 = _e2e_http_json(url + "/api/decide", "POST", {"req_id": r2["id"]}, pw="pass-owner")
    c3, d3 = _e2e_http_json(url + "/api/decide", "POST", {"req_id": r3["id"]}, pw="pass-bob")
    return (c1, c2, c3) == (200, 200, 200) and (d1["decided_by"], d2["decided_by"], d3["decided_by"]) == ("alice", "owner", "bob")


def _multi_repo_e2e_case():
    import tempfile  # noqa: PLC0415
    import threading  # noqa: PLC0415

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: PLC0415
    global PINNED_APPROVER_PUB
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    srv = _make_e2e_server(priv, ["alice:OrgA/app:pass-alice", "bob:OrgB/app:pass-bob", "owner:*:pass-owner"])
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    old_pub = PINNED_APPROVER_PUB
    PINNED_APPROVER_PUB = pub_b64
    try:
        with tempfile.TemporaryDirectory() as tmp:
            q_base = "# 01: t\n\n**Status:** ready-for-agent\n\n**Settling:** python3 -c 'pass'\n"
            q_new = "# 02: new\n\n**Status:** ready-for-agent\n\n**Settling:** python3 -c 'pass'\n"
            q_mod = q_base.replace("pass", "pass;1")
            ra, prev_a = _e2e_init_repo(tmp, "RepoA", "https://github.com/OrgA/app.git", pub_b64, q_base)
            rb, prev_b = _e2e_init_repo(tmp, "RepoB", "https://github.com/OrgB/app.git", pub_b64, q_base)
            req1 = {"repo": repo_id(ra), "action": "question.modify", "target_path": "questions/01.md",
                    "prev_sha256": prev_a, "target_sha256": sha256_text(q_mod)}
            _, r1 = _e2e_http_json(url + "/requests", "POST", req1)
            _, r1_dup = _e2e_http_json(url + "/requests", "POST", req1)
            _, r2 = _e2e_http_json(url + "/requests", "POST", {
                "repo": repo_id(ra), "action": "question.create", "target_path": "questions/02.md",
                "prev_sha256": "NONE", "target_sha256": sha256_text(q_new)})
            _, r3 = _e2e_http_json(url + "/requests", "POST", {
                "repo": repo_id(rb), "action": "question.modify", "target_path": "questions/01.md",
                "prev_sha256": prev_b, "target_sha256": sha256_text(q_mod)})
            if r1["id"] != r1_dup["id"] or (r1["display_id"], r2["display_id"], r3["display_id"]) != ("OrgA/app#1", "OrgA/app#2", "OrgB/app#1"):
                return False
            if not _e2e_check_rbac_and_approve(url, r1, r2, r3):
                return False
            _, r1_cached = _e2e_http_json(url + "/requests", "POST", req1)
            if r1_cached["status"] != "approved_single" or not r1_cached.get("receipt"):
                return False
            rec1 = _e2e_http_json(url + "/requests/" + r1["id"], "GET")[1]["receipt"]
            rec2 = _e2e_http_json(url + "/requests/" + r2["id"], "GET")[1]["receipt"]
            rec3 = _e2e_http_json(url + "/requests/" + r3["id"], "GET")[1]["receipt"]
            if _receipt_body(rec1).get("decided_by") != "alice":
                return False
            _save_receipt_to_bundle(rec1, os.path.join(ra, ".git", "einfacht-receipt.json"))
            _save_receipt_to_bundle(rec2, os.path.join(ra, ".git", "einfacht-receipt.json"))
            _save_receipt_to_bundle(rec3, os.path.join(rb, ".git", "einfacht-receipt.json"))
            files_a = {"questions/01.md": q_mod, "questions/02.md": q_new}
            return check_questions_against_anchor(files_a, root=ra) == [] and bool(
                check_questions_against_anchor(files_a, root=ra, receipt=rec3))
    finally:
        PINNED_APPROVER_PUB = old_pub
        srv.shutdown()
        srv.server_close()


def _anchors_rm_and_tamper_case():
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    from datetime import timedelta  # noqa: PLC0415

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: PLC0415
    global PINNED_APPROVER_PUB
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    old_pub = PINNED_APPROVER_PUB
    PINNED_APPROVER_PUB = pub_b64
    try:
        with tempfile.TemporaryDirectory() as tmp:
            q_text = "# 01: t\n\n**Status:** ready-for-agent\n\n**Settling:** python3 -c 'pass'\n"
            rt, _ = _e2e_init_repo(tmp, "Repo", "https://github.com/Org/app.git", pub_b64, q_text)
            anc_p = os.path.join(rt, ANCHORS_FILE)
            with open(anc_p, encoding="utf-8") as fh:
                anc = json.load(fh)
            anc["lock_core"] = True
            with open(anc_p, "w", encoding="utf-8") as fh:
                json.dump(anc, fh)
            subprocess.run(["git", "-C", rt, "config", "user.email", "t@e.com"], check=True)
            subprocess.run(["git", "-C", rt, "config", "user.name", "t"], check=True)
            subprocess.run(["git", "-C", rt, "add", "."], check=True)
            subprocess.run(["git", "-C", rt, "commit", "-q", "-m", "init"], check=True)
            anc["lock_core"] = False
            with open(anc_p, "w", encoding="utf-8") as fh:
                json.dump(anc, fh)
            if not check_anchors_integrity(load_anchors(rt), root=rt):
                return False
            subprocess.run(["git", "-C", rt, "rm", "-q", "-f", ANCHORS_FILE], check=True)
            if load_anchors(rt) != {}:
                return False
            wt = os.path.join(tmp, "wt")
            subprocess.run(["git", "-C", rt, "worktree", "add", "-q", "-b", "wt-b", wt], check=True)
            rec = _sign_fixture(priv, {
                "id": "r-wt", "repo": "Org/app", "action": "question.modify", "target": "questions/01.md",
                "prev_sha256": "a", "target_sha256": "b",
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            })
            _save_receipt_to_bundle(rec, _default_receipt_path(wt))
            loaded = load_receipt(root=wt)
            return isinstance(loaded, dict) and len(loaded.get("receipts") or []) == 1
    finally:
        PINNED_APPROVER_PUB = old_pub


def _auto_sync_and_deny_case():
    import io  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    import threading  # noqa: PLC0415

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: PLC0415
    global PINNED_APPROVER_PUB
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    srv = _make_e2e_server(priv, ["owner:*:po"])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    old_pub, old_url = PINNED_APPROVER_PUB, os.environ.get(APPROVER_URL_ENV)
    PINNED_APPROVER_PUB = pub_b64
    os.environ[APPROVER_URL_ENV] = url
    try:
        with tempfile.TemporaryDirectory() as tmp:
            q1 = "# 01: t\n\n**Status:** ready-for-agent\n\n**Settling:** python3 -c 'pass'\n"
            q2 = "# 02: new\n\n**Status:** ready-for-agent\n\n**Settling:** python3 -c 'pass'\n"
            q3 = "# 03: deny\n\n**Status:** ready-for-agent\n\n**Settling:** python3 -c 'pass'\n"
            rt, _ = _e2e_init_repo(tmp, "RepoA", "https://github.com/OrgA/app.git", pub_b64, q1)
            with open(os.path.join(rt, "questions", "02.md"), "w", encoding="utf-8") as fh:
                fh.write(q2)
            files = {"questions/01.md": q1, "questions/02.md": q2}
            if [p.code for p in check_questions_against_anchor(files, root=rt)] != ["approval.receipt_required"]:
                return False
            _, pend = _e2e_http_json(url + "/api/pending", "GET", pw="po")
            rows = pend.get("pending") or []
            if len(rows) != 1 or rows[0]["target_path"] != "questions/02.md":
                return False
            _e2e_http_json(url + "/api/decide", "POST", {"req_id": rows[0]["id"]}, pw="po")
            if check_questions_against_anchor(files, root=rt) != []:
                return False
            with open(os.path.join(rt, "questions", "03.md"), "w", encoding="utf-8") as fh:
                fh.write(q3)
            files["questions/03.md"] = q3
            check_questions_against_anchor(files, root=rt)
            _, pend2 = _e2e_http_json(url + "/api/pending", "GET", pw="po")
            _e2e_http_json(url + "/api/decide", "POST", {
                "req_id": pend2["pending"][0]["id"], "mode": "deny", "deny_reason": "weakening_blocked"}, pw="po")
            buf, old_err = io.StringIO(), sys.stderr
            sys.stderr = buf
            try:
                probs = check_questions_against_anchor(files, root=rt)
            finally:
                sys.stderr = old_err
            return bool(probs) and "approval.denied" in buf.getvalue() and "weakening_blocked" in buf.getvalue()
    finally:
        PINNED_APPROVER_PUB = old_pub
        if old_url is None:
            os.environ.pop(APPROVER_URL_ENV, None)
        else:
            os.environ[APPROVER_URL_ENV] = old_url
        srv.shutdown()
        srv.server_close()


def main(argv):
    rc = gate.activate_or_fatal()
    if rc:
        return rc
    if "--selftest" in argv:
        return selftest(M("approval.title"), _cases())
    if "--request" in argv:
        return _submit_all(argv)
    if "--sync-settled" in argv:
        return _sync_settled(gate.GATE_REPO)
    if "--init-anchors" in argv:
        if init_anchors(gate.GATE_REPO) != 0:
            print(M("approval.anchors_exist", path=ANCHORS_FILE), file=sys.stderr)
            return 2
        print(M("approval.anchors_initialized", path=ANCHORS_FILE))
        return 0
    return 0


MODULE = module_meta("Approval & anchor verifier",
                     "offline Ed25519 receipt verification and tamper-evident anchors for questions/PRINCIPLES",
                     selftest=True)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
