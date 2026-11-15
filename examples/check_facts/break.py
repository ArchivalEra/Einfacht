from pathlib import Path

path = Path("STATE.md")
path.write_text(path.read_text(encoding="utf-8") + "\nThe unmeasured total is 9999.\n", encoding="utf-8")
