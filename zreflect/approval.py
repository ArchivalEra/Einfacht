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
    lines = []
    for ln in (text or "").splitlines():
        if re.match(r"^\*\*(Status|Settling):\*\*", ln.strip()):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()


def _field_val(text, name):
    m = re.search(r"(?m)^\*\*%s:\*\*\s*(.+)$" % re.escape(name), text or "")
    return m.group(1).strip() if m else ""


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
    body = {k: v for k, v in receipt.items() if k != "sig"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_iso(ts):
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _verify_sig(payload, sig_b64, pub_b64):
    try:
        from cryptography.exceptions import InvalidSignature  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: PLC0415
    except ImportError:
        return False, "crypto_unavailable"
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
        pub.verify(base64.b64decode(sig_b64), payload)
        return True, None
    except (InvalidSignature, ValueError, TypeError):
        return False, "signature_invalid"


def verify_receipt(receipt, *, repo_name, action, target, prev_sha256, target_sha256,
                   pub_b64, revoked_ids=(), now=None):
    """Verify an Ed25519 approval receipt offline. Returns list of `Message` (empty = valid)."""
    if not isinstance(receipt, dict) or not pub_b64:
        return [M("approval.receipt_required", action=action, target=target)]
    if str(receipt.get("id") or "") in set(revoked_ids):
        return [M("approval.revoked", id=str(receipt.get("id") or ""))]
    exp = _parse_iso(receipt.get("expires_at"))
    cur = now or datetime.now(timezone.utc)
    if exp is None or exp <= cur:
        return [M("approval.expired", id=str(receipt.get("id") or ""))]
    if (receipt.get("repo") != repo_name or receipt.get("action") != action
            or receipt.get("target") != target):
        return [M("approval.scope_mismatch", action=action, target=target)]
    if (receipt.get("prev_sha256") != prev_sha256
            or receipt.get("target_sha256") != target_sha256):
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
             "q/26.md", q_weak, anc, receipt=valid_rec, pub_b64=pub_b64, repo_name="Einfacht", now=now) == []),
    ]


def main(argv):
    rc = gate.activate_or_fatal()
    if rc:
        return rc
    if "--selftest" in argv:
        return selftest(M("approval.title"), _cases())
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
