#!/usr/bin/env python3
"""Committer roster: every identity on HEAD must be one of the known children.

The allowlist below is the whole policy. Granting amnesty to a new collaborator
means adding their email here (and to `principles.json`'s description if the
roster grows past the two children) -- there is no second place to edit.
"""

import re
import subprocess
import sys

ALLOW = frozenset({
    "archivalera@users.noreply.github.com",
    "yaochenli083@gmail.com",
    "356470020+plumhelper@users.noreply.github.com",
    "noreply@github.com",
})

_EMAIL = re.compile(r"<([^>]+)>")


def identities(fmt_repo="."):
    """Return every lowercased email in author, committer and `Co-authored-by` fields."""
    fmt = "%ae%n%ce%n%(trailers:key=Co-authored-by,valueonly)"
    r = subprocess.run(["git", "-C", fmt_repo, "log", "HEAD", "--format=" + fmt],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = set()
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _EMAIL.search(line)
        out.add((m.group(1) if m else line).strip().lower())
    return out


def violations(root="."):
    """Return the sorted identities on HEAD that the allowlist does not cover."""
    return sorted(identities(root) - ALLOW)


if __name__ == "__main__":
    bad = violations(sys.argv[1] if len(sys.argv) > 1 else ".")
    if bad:
        print("FOREIGN: " + ", ".join(bad))
        sys.exit(1)
    print("roster ok: %d identities" % len(identities(sys.argv[1] if len(sys.argv) > 1 else ".")))
    sys.exit(0)
