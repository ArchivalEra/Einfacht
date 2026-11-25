---
name: einfacht
description: On-demand Trust v2 layout and entry-point reference for Einfacht.
disable-model-invocation: true
---

# Einfacht

- **Core vs. extensions**: `zreflect/` + `ruff.toml` are sealed (`SEAL.json`, upgrade via `python3 zreflect/trust.py --upgrade <suite>`). Put consumer extensions (`measure_*.py`, `check_*.py`, `principles.json`) in `reflect-local/`.
- **Entry points**: `facts.py --init` · `facts.py [--accept-changes]` · `facts.py --render-doc` · `registry.py --run commit` · `harness.py` · `trust.py --init|--submit|--pull|--release|--sync` · `reflect-local/hook.py --chain`.
- **Language & status**: Prefix `REFLECT_LANG=en|zh|de` for human-readable `--help` / `knobs.py --list`; `OFF:` is never a pass. Never bypass `SEAL.json` / `ANCHORS.json`; raise suite bugs as issues.
