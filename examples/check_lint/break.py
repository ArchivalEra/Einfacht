from pathlib import Path

Path("zreflect/check_temporary.py").write_text(
    "from gate import meta\n\n"
    "def run():\n"
    "    unused = 1\n"
    "    return 0\n\n"
    "GATE = meta('temporary', 'lint example')\n",
    encoding="utf-8")
