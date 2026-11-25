---
name: einfacht
description: >
  Trust v2 contract, out-of-band approvals (`trust.py --submit/--pull/--sync`),
  painless suite upgrades (`--upgrade` via `SUITE.sig`), extensions, knobs, and
  ledgers for Einfacht repos. Use whenever working with `zreflect/`, `ANCHORS.json`,
  `SEAL.json`, `FACTS.json`, `knobs.json`, or `approval.*`/`seal.*` gate errors.
disable-model-invocation: true
---

# Einfacht

Deterministic gate & fact-ledger suite (`rc=0` pass or `OFF:`, `rc=1` criterion fail / pending `--submit`, `rc=2` `FATAL:`). **`OFF:` is never a pass.** Prefix `REFLECT_LANG=en|zh|de` for human-readable `--help` and `knobs.py --list`.

## 1. Suite vs. Consumer Boundary

- **Sealed core (`zreflect/` + `ruff.toml`)**: Verified by `zreflect/SEAL.json`. Consumers **never** edit files inside `zreflect/`, never place custom scripts in `zreflect/`, and never run `registry.py --reseal` or `trust.py --release` (both are upstream `ArchivalEra/Einfacht` maintainer-only; `--release` hardcodes `repo="ArchivalEra/Einfacht"`).
- **Consumer extensions (`reflect-local/` or `REFLECT_LOCAL_DIR`)**: Put `measure_*.py` (`from facts import fact; def measure(): ...`), custom `check_*.py` (`GATE = meta(...)`), `principles.json`, and `hook.py` here. Guarded by `ANCHORS.json` (`local_scripts`) when `lock_core=true`.
- **Root carriers & config**: `knobs.json` · `ANCHORS.json` · `FACTS.json` · `STATE.md` · `PRINCIPLES.md` · `HISTORY.md` (or folder under `REFLECT_HISTORY_MODE=fold`) · `AGENTS.md` · `questions/*.md` · `retractions.json` · `secrets.json`.

## 2. Install & Upgrade Suite (`SUITE.sig`, Zero Manual Requests)

- **Bootstrap a new consumer repo**:
  ```bash
  cp -r <suite>/zreflect <suite>/reflect-local <suite>/ruff.toml <repo>/
  python3 zreflect/facts.py --init && python3 zreflect/facts.py && python3 zreflect/facts.py --render-doc
  python3 zreflect/trust.py --init && python3 reflect-local/hook.py --chain
  ```
- **Upgrade an existing consumer repo** (**never hand-copy `zreflect/` or manually file `seal.core`/`seal.doc`/`principles.edit` requests**):
  ```bash
  python3 zreflect/trust.py --upgrade <path-to-Einfacht>
  ```
  Verifies `<suite>/zreflect/SEAL.json` + `<suite>/zreflect/SUITE.sig` (`suite.release`), blocks `suite_seq` downgrades, swaps `zreflect/` + `ruff.toml`, preserves `reflect-local/`, refreshes `FACTS.json` / `STATE.md` / `PRINCIPLES.md` / `hook.py --chain`, and updates `ANCHORS.json`.
  - If `--upgrade` fails with `approval.receipt_required` (`suite.release`) or `trust.suite_downgrade`, the source checkout lacks a valid `SUITE.sig` (not released upstream) or has an older `suite_seq` than `ANCHORS.json`.

## 3. Filing & Landing Approval Requests (`--submit` / `--pull` / `--sync`)

Gates and git hooks verify **purely read-only** (`auto_sync=False`) and never contact the approver. Re-running gates on `approval.*` or `seal.*` errors never files a request. Use the explicit 4-step loop:

```bash
python3 zreflect/trust.py --submit    # 1. POST missing requests; rc=1 while pending is expected
# 2. Approver approves out-of-band (Web UI or authorized approver thread for this repo)
python3 zreflect/trust.py --pull      # 3. GET /receipts?repo=<id> -> .git/einfacht-receipt.json
python3 zreflect/trust.py --sync      # 4. Verify receipts locally & advance ANCHORS.json
python3 zreflect/registry.py --run commit
```

- **`rc=1` on `--submit` is normal**: `--submit` prints `approval.request_submitted` (`req-...`, URL) and exits `1` whenever requests stay `pending` (only zero changes or auto-delegated `delegate_30m` hits exit `0`). Do not fall back to manual `POST /requests`. Re-running `--submit` supersedes pending requests cleanly; denied targets have a 2-minute cooldown (`approval.request_rejected_duplicate`).
- **Preflight traps before `--submit` can file**:
  - `seal.file_tampered` / `seal.unlisted_file`: `--submit` validates `zreflect/SEAL.json` on disk first and aborts if anything in `zreflect/` changed or is unlisted. Restore `zreflect/` (`--upgrade` or git checkout) and move custom code to `reflect-local/`.
  - `approval.anchors_broken`: never hand-edit or `git rm ANCHORS.json` (`HEAD:ANCHORS.json` enforces unchanged `repo`, `approver_pub`, `lock_core`, `questions_dir`, and monotonic `suite_seq` / `revoked_ids`). Only `--init`, `--migrate`, `--upgrade`, and `--sync` modify `ANCHORS.json`.
- **Automatic target-to-action mapping in `--submit`**:
  - `knobs.json`, or added `REFLECT_OFF_GATES` basenames (`check_*.py`, `doctor.py`) -> `gate.off`
  - `REFLECT_NO_PRINCIPLES` -> `principles.disable`
  - `reflect-local/*.py` & `reflect-local/principles.json` -> `seal.core`
  - `PRINCIPLES.md` -> `principles.edit` · `zreflect/doc.py` -> `seal.doc` *(exempt on signed `SUITE.sig` `--upgrade`)*
  - `questions/*.md` -> `question.create` / `question.modify` / `question.delete` *(exempt: settling -> `resolved`, or toggling `ready-for-human` <-> `ready-for-agent` with identical body & `Settling:`)*
  - `zreflect/SEAL.json` -> `seal.core` *(only when `SUITE.sig` absent; prefer `--upgrade`)*
- **Env & paths**: `EINFACHT_APPROVER_URL` (default `http://127.0.0.1:18443`), `EINFACHT_APPROVAL_RECEIPT` (default `<git-common-dir>/einfacht-receipt.json`, shared across worktrees), `EINFACHT_APPROVER_PUB` / `/etc/einfacht-approver/signing_pub.pem`. `ANCHORS.json["repo"]` (`<owner>/<repo>` from `origin`, else dirname) must match the bound approver keychain.

## 4. Facts, Knobs & Ledgers

- **Facts (`guard.refuse_changed`)**: Never hand-edit `FACTS.json` or `<!-- AUTO:* -->`. Run `python3 zreflect/facts.py --accept-changes[=k1,k2]` (`--allow-drop` when changing keys), then `python3 zreflect/facts.py --render-doc`. Set `"REFLECT_MEASURE_MODULE": "measure_<name>"` in `knobs.json`.
- **Knobs (`os.environ > knobs.json > REGISTRY`)**: `knobs.json` rejects `""` except `"REFLECT_READMES": ""` (off). Use `"REFLECT_READMES": "README.md"` for single-README; `"REFLECT_NO_PRINCIPLES": "1"` to disable principles (with approval).
- **Questions (`questions/NN-slug.md`)**: `**Status:**` in `{ready-for-agent, ready-for-human, resolved}` (never delete to close); `**Settling:**` must start with a runnable command/path (never prose; or `none`/`does not exist` while unbuilt).
- **Retractions (`retractions.json`)**: `{"schema": 1, "retractions": [{"id", "text", "evidence", "fixed_in"}]}` (runnable `evidence`, no `why`).
- **Verification**: `registry.py --run commit` · `registry.py --run start-of-work` · `harness.py` · `examples.py --all` · `trust.py --migrate` (schema v1 -> v2). Report suite bugs upstream (`ArchivalEra/Einfacht`), never patch core locally.
