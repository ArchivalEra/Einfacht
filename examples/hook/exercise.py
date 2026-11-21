import subprocess
import sys
from pathlib import Path

hooks = Path(".git/hooks")
for name in ("pre-commit", "pre-push"):
    text = (hooks / name).read_text(encoding="utf-8")
    if "Einfacht chain wrapper" not in text:
        raise SystemExit(1)
subprocess.run([sys.executable, "reflect-local/hook.py", "--uninstall", str(Path.cwd())], check=True)
if any((hooks / name).exists() for name in ("pre-commit", "pre-push")):
    raise SystemExit(1)
print("hooks example ok")
