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
DUPLICATE_COOLDOWN_SECONDS = 120


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return sha256_bytes((text or "").encode("utf-8"))


def sha256_file(path):
    try:
        return sha256_bytes(open(path, "rb").read())
    except OSError:
        return None


def _strip_status_settling(text):
    lines = (text or "").splitlines()
    out = []
    skip_cont = False
    for ln in lines:
        if re.match(r"^(?:\*\*)?(Status|Settling)(?:\*\*)?:\s*(?:\*\*)?", ln.strip()):
            skip_cont = ln.strip().lstrip("*").startswith("Settling")
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
    if isinstance(receipt.get("payload"), dict):
        body = receipt["payload"]
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body = {k: v for k, v in receipt.items() if k != "sig"}
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


def verify_receipt(receipt, *, repo_name, action, target, prev_sha256, target_sha256,
                   pub_b64, revoked_ids=(), now=None):
    """Verify an Ed25519 approval receipt offline. Returns list of `Message` (empty = valid)."""
    if not isinstance(receipt, dict) or not pub_b64:
        return [M("approval.receipt_required", action=action, target=target)]
    body = _receipt_body(receipt)
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
    ok, err = _verify_sig(canonical_payload(receipt), str(receipt.get("sig") or ""), pub_b64)
    if not ok:
        if err == "crypto_unavailable":
            return [M("approval.crypto_unavailable", target=target)]
        return [M("approval.signature_invalid", target=target)]
    return []


def load_receipt(path=None):
    p = path or os.environ.get(RECEIPT_ENV)
    if not p or not os.path.isfile(p):
        return None
    try:
        data = json.load(open(p, encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def load_anchors(root=None):
    base = root or gate.GATE_REPO
    p = os.path.join(base, ANCHORS_FILE)
    if not os.path.isfile(p):
        import subprocess  # noqa: PLC0415
        try:
            r = subprocess.run(["git", "-C", base, "ls-files", "--error-unmatch", ANCHORS_FILE],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return {}
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None
    try:
        data = json.load(open(p, encoding="utf-8"))
        return data if isinstance(data, dict) else None
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
    """Check one question against its anchor. Settling needs NO receipt; tampering DOES."""
    if not anchor_entry:
        return []
    cur_sha = sha256_text(cur_text) if cur_text is not None else "DELETED"
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


def check_questions_against_anchor(files, root=None, receipt=None):
    anchors = load_anchors(root)
    if anchors is None:
        return []
    if not anchors:
        return [M("approval.anchors_broken")]
    q_map = anchors.get("questions") or {}
    pub = anchors.get("approver_pub")
    rname = anchors.get("repo") or os.path.basename(os.path.abspath(root or gate.GATE_REPO))
    revoked = anchors.get("revoked_ids") or []
    rec = receipt if receipt is not None else load_receipt()
    out = []
    for rel in sorted(set(q_map) | set(files)):
        out += check_question_change(
            rel, files.get(rel), q_map.get(rel),
            receipt=rec, pub_b64=pub, repo_name=rname, revoked_ids=revoked,
        )
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
    rec = receipt if receipt is not None else load_receipt()
    return check_principles_anchor(
        anchors,
        doc_py_sha=sha256_file(os.path.join(gate.zdir(), "doc.py")),
        principles_md_sha=sha256_file(os.path.join(base, "PRINCIPLES.md")),
        no_principles=knobs.flag("REFLECT_NO_PRINCIPLES") is True,
        receipt=rec,
    )


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
    rec = receipt if receipt is not None else load_receipt()
    pub = anchors.get("approver_pub")
    rname = anchors.get("repo") or os.path.basename(os.path.abspath(base))
    revoked = anchors.get("revoked_ids") or []
    out = []
    for name in extra:
        out += verify_receipt(
            rec, repo_name=rname, action="gate.off", target=name,
            prev_sha256="on", target_sha256="off",
            pub_b64=pub, revoked_ids=revoked, now=now)
    return out


def _build_anchors(root, pub_b64=None):
    import check_questions  # noqa: PLC0415
    files = check_questions.collect(root=root)
    q_map = {k: question_snapshot(v) for k, v in sorted(files.items())}
    off_list = sorted(x.strip() for x in (knobs.get("REFLECT_OFF_GATES") or "").split(",") if x.strip())
    return {
        "schema": 1,
        "repo": os.path.basename(os.path.abspath(root)),
        "approver_pub": pub_b64,
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
    for rel, text in sorted(files.items()):
        if rel not in q_map:
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


def _is_controlled_path(rel):
    norm = str(rel or "").replace("\\", "/").lstrip("./")
    return norm in CONTROLLED_FILES or any(norm.startswith(p) for p in CONTROLLED_PREFIXES)


def _classify_action(rel, text=None):
    if rel == "zreflect/doc.py":
        return "seal.doc"
    if rel.startswith(("zreflect/", "reflect-hooks/")) or rel == "ruff.toml":
        return "seal.core"
    if rel == "PRINCIPLES.md":
        return "principles.edit"
    if rel.startswith("questions/"):
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


def build_requests(changed_paths, root=None, repo_name=None, diff_fn=None, sha_fn=None):
    """Build controlled-scope approval request payloads from changed paths (purely mechanical)."""
    base = root or gate.GATE_REPO
    rname = repo_name or os.path.basename(os.path.abspath(base))
    out = []
    for raw in sorted(set(changed_paths or ())):
        rel = str(raw or "").replace("\\", "/").lstrip("./")
        if not _is_controlled_path(rel):
            continue
        full = os.path.join(base, rel)
        text = None
        if os.path.isfile(full):
            try:
                text = open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                text = None
        target_sha = sha_fn(full) if sha_fn else (sha256_file(full) or "DELETED")
        prev_sha, diff_sum = diff_fn(base, rel) if diff_fn else _git_prev_sha_and_diff(base, rel)
        out.append({
            "repo": rname,
            "agent_id": os.environ.get("USER", "agent"),
            "action": _classify_action(rel, text),
            "target_path": rel,
            "prev_sha256": prev_sha,
            "target_sha256": target_sha,
            "diff_summary": diff_sum or ("(new or binary file %s)" % rel),
        })
    return out


def check_duplicate_cooldown(existing_requests, candidate, now_ts=None, cooldown_seconds=DUPLICATE_COOLDOWN_SECONDS):
    """Enforce per-repo 2-minute duplicate/denied cooldown without blocking other repos."""
    import time as _time  # noqa: PLC0415
    now = int(_time.time()) if now_ts is None else int(now_ts)
    key = (
        candidate.get("repo"), candidate.get("action"), candidate.get("target_path"),
        candidate.get("prev_sha256"), candidate.get("target_sha256"),
    )
    for req in reversed(list(existing_requests or ())):
        rkey = (req.get("repo"), req.get("action"), req.get("target_path"),
                req.get("prev_sha256"), req.get("target_sha256"))
        if rkey != key:
            continue
        st = req.get("status")
        if st == "pending":
            return "duplicate_pending", req
        if st == "denied":
            ts = int(req.get("denied_at") or req.get("created_at") or 0)
            if (now - ts) < cooldown_seconds:
                return "rejected_duplicate_2m", req
        if str(st or "").startswith("approved") and req.get("receipt"):
            exp = _parse_iso(_receipt_body(req["receipt"]).get("expires_at"))
            if exp and exp.timestamp() > now:
                return "already_approved", req
    return "new", None


def _post_one_request(url, payload, wait):
    import time as _time  # noqa: PLC0415
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    req = urllib.request.Request(url + "/requests", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(M("approval.receipt_required", action=payload["action"], target=payload["target_path"]) + f" ({exc})", file=sys.stderr)
        return False
    if resp.get("status") == "rejected_duplicate_2m":
        print(M("approval.request_rejected_duplicate", target=payload["target_path"]), file=sys.stderr)
        return False
    print(M("approval.request_submitted", id=resp.get("id", ""), status=resp.get("status", ""),
            action=payload["action"], target=payload["target_path"], url=url))
    if wait and resp.get("status") == "pending":
        deadline = _time.time() + 300
        while _time.time() < deadline:
            _time.sleep(3)
            polled = json.loads(urllib.request.urlopen(f"{url}/requests/{resp['id']}", timeout=10).read().decode("utf-8"))
            if polled.get("status") != "pending":
                resp = polled
                break
    if resp.get("receipt"):
        out_path = os.environ.get(RECEIPT_ENV) or os.path.join(gate.GATE_REPO, ".git", "einfacht-receipt.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(resp["receipt"], fh, indent=2)
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
        ("approval.request_scope_and_2m_cooldown",
         lambda: [r["target_path"] for r in build_requests(
             ["src/app.py", "zreflect/doc.py", "questions/26.md"],
             root=".", repo_name="Einfacht",
             diff_fn=lambda _r, _p: ("p1", "+diff"), sha_fn=lambda _p: "t1")]
         == ["questions/26.md", "zreflect/doc.py"]
         and check_duplicate_cooldown(
             [{"repo": "Einfacht", "action": "seal.doc", "target_path": "zreflect/doc.py",
               "prev_sha256": "p1", "target_sha256": "t1", "status": "denied", "denied_at": 1000}],
             {"repo": "Einfacht", "action": "seal.doc", "target_path": "zreflect/doc.py",
              "prev_sha256": "p1", "target_sha256": "t1"}, now_ts=1060)[0] == "rejected_duplicate_2m"
         and check_duplicate_cooldown(
             [{"repo": "Einfacht", "action": "seal.doc", "target_path": "zreflect/doc.py",
               "prev_sha256": "p1", "target_sha256": "t1", "status": "denied", "denied_at": 1000}],
             {"repo": "OtherRepo", "action": "seal.doc", "target_path": "zreflect/doc.py",
              "prev_sha256": "p1", "target_sha256": "t1"}, now_ts=1060)[0] == "new"),
    ]


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
        p = os.path.join(gate.GATE_REPO, ANCHORS_FILE)
        if os.path.isfile(p):
            print(M("approval.anchors_exist", path=ANCHORS_FILE), file=sys.stderr)
            return 2
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: PLC0415
        pub = base64.b64encode(
            Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode("ascii")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(_build_anchors(gate.GATE_REPO, pub_b64=pub), fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        print(M("approval.anchors_initialized", path=ANCHORS_FILE))
        return 0
    return 0


MODULE = module_meta("Approval & anchor verifier",
                     "offline Ed25519 receipt verification and tamper-evident anchors for questions/PRINCIPLES",
                     selftest=True)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
