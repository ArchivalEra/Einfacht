---
name: einfacht
description: >
  Invoke when working in any repository containing zreflect/, reflect-hooks/,
  FACTS.json, or SEAL.json; installing or configuring Einfacht (knobs.json,
  measure()); authoring questions/*.md or retractions.json; adding unsealed
  check_*.py gates; or diagnosing OFF:/FATAL:/DRIFT/guard.refuse_changed/
  replay.mismatch/seal.* errors, even when the repo's AGENTS.md omits Einfacht.
---

# Einfacht Contract & Failure-Delta Router

Deterministic verification-gate & fact-ledger state machine (`rc=0` pass or `OFF:`, `rc=1` criterion fail, `rc=2` `FATAL:` config/guard/seal). **`OFF:` is never a pass.**

- **CLI without reading `zreflect/*.py`**: Core emits raw i18n codes (`facts.usage`, `knobs.sem.*`) when `REFLECT_LANG` is unset. Prefix `REFLECT_LANG=en` (or `zh`) on `--help` and `knobs.py --list`.
- **Unified entry points** (legacy `render`/`guard`/`ledger` scripts, `--legacy`, `core.hooksPath`, `lang/<lang>/` dirs, and `check_*.py` globbing are gone):
  - Install: copy `zreflect/`, `reflect-hooks/`, and `ruff.toml` (`SEAL.json` hashes `ruff.toml`), then run `facts.py --init && facts.py && facts.py --render-doc && reflect-hooks/hook.py --chain .`.
  - Run: `registry.py --run commit` (live phase) · `harness.py` (all gates prove red + self-proof) · `doctor.py` (live preflight).
- **Guard trap (`FATAL: guard.refuse_changed`)**: never hand-edit `FACTS.json` or `<!-- AUTO:* -->`. Pass `--accept-changes` as the **first** arg (`python3 zreflect/facts.py --accept-changes[=k1,k2]`, adding `--allow-drop` when swapping collectors), then `facts.py --render-doc`.
- **Collector & replay (`WARN: facts.measure_placeholder_used`)**: add unsealed `zreflect/measure_<name>.py` (`from facts import fact`; `def measure(): return {key: fact(val, cmd, src)}`) and `"REFLECT_MEASURE_MODULE": "measure_<name>"` in `knobs.json`. `cmd` stdout stripped must equal `value` verbatim; `replay: false` is rejected (`replay.skip_is_gone`) — adjust `REFLECT_REPLAY_TIMEOUT` or move non-replayable claims to `HISTORY.md` (`calibrate`/`calibrate_expect` runs alongside `cmd`, never skips it).
- **Knobs (`os.environ > knobs.json > REGISTRY`)**: `knobs.json` rejects empty `""` (`knobs.config_invalid_value`). In `knobs.json`, set `"REFLECT_READMES": "README.md"` to disable trilingual cross-links, or `"REFLECT_NO_PRINCIPLES": "1"` to skip `PRINCIPLES.md` replay (don't delete the file); full `OFF:` for `REFLECT_READMES` requires `REFLECT_READMES=""` in env.
- **Sealed core vs. extensions (`SEAL.json`)**: consumer repos extend only via unsealed `zreflect/measure_<name>.py`, unsealed `zreflect/check_<name>.py` (`GATE = meta(...)`), `knobs.json`, and root policy specs — never edit `SEAL.json`-locked files (`registry.py --reseal=<comma-paths>` is suite maintenance only).
- **Ledgers**: `questions/*.md` requires `**Status:**` (`needs-triage|needs-info|ready-for-agent|ready-for-human|wontfix|resolved`, never delete to close) and `**Settling:** <exec> -- rc=0 => ...; rc!=0 => ...` starting with a known interpreter (`python3`, `bash`, `git`, `/...`; prose fails `gate.py` `exec_position_problems`). `retractions.json` requires `{"retractions": [{"id","text","evidence","fixed_in"}]}` (**no `why` field**; runnable `evidence`).
