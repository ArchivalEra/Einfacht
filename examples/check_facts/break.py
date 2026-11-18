from pathlib import Path

path = Path("STATE.md")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("<!-- AUTO:FACTS -->", "> The unmeasured total is 9999.\n\n<!-- AUTO:FACTS -->", 1), encoding="utf-8")
