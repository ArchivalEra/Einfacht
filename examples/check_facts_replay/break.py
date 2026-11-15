import json
from pathlib import Path

path = Path("FACTS.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["facts"]["py_files"]["value"] += 1
path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
