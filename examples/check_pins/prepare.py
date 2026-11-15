import json
import subprocess
from pathlib import Path

root = Path("upstream")
root.mkdir()
subprocess.run(["git", "init", "-q", str(root)], check=True)
(root / "source.txt").write_text("upstream\n", encoding="utf-8")
subprocess.run(["git", "-C", str(root), "add", "source.txt"], check=True)
subprocess.run(["git", "-C", str(root), "-c", "user.name=example", "-c", "user.email=example@invalid", "commit", "-qm", "source"], check=True)
head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
base = {"name": "demo", "kind": "tree", "worktree": "upstream"}
good = {"pins": [dict(base, stamp_read=f"python3 -c \"print('demo main {head} 0')\"")]}
bad = {"pins": [dict(base, stamp_read=f"python3 -c \"print('demo main {'0' * 40} 0')\"")]}
Path("pins.json").write_text(json.dumps(good), encoding="utf-8")
Path("bad-pins.json").write_text(json.dumps(bad), encoding="utf-8")
