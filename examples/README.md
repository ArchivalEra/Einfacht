# Runnable examples

Every declared gate has a same-named directory here. The additional directories
cover the suite's core seams: bootstrap, custom collectors, custom gates and
phases, git hooks, next-turn collection, CI result recording, environment
probing, and the registry / knob / machine-line / i18n / harness entry points.

`--check` enforces the gate coverage: adding a gate without an example is a
red criterion, so an example cannot quietly become decoration.

```bash
python3 zreflect/examples.py --list       # discovered examples
python3 zreflect/examples.py --check      # gate/example coverage only
python3 zreflect/examples.py --all        # execute every example in isolation
python3 zreflect/examples.py quickstart   # execute one
```

An example contains an `example.json` manifest and the files copied into its
temporary repo. The suite and `ruff.toml` are copied first; `facts.py --init`
then creates the ordinary skeleton unless the manifest sets `"init": false`.
Payload files are copied last. `README.md` files are documentation and are not
copied into the temporary repo.

Each manifest step has an `argv` array, an expected `rc` (default `0`), and
optional `contains` / `not_contains` output assertions. `{python}` selects the
current interpreter and `{repo}` selects the temporary repo. Environment at the
manifest level applies to every step; step-level `env` extends it. Inherited
`REFLECT_*` variables are deliberately removed so an example does not depend on
the caller's checkout.

The generated `Einfacht.env` is loaded before each step, then manifest and step
environment override it. This matches the hook carrier without requiring a
particular shell. Phase aggregation prints ran/off/failed lists; successful
gates' stdout is not relayed, so examples assert the phase summary rather than
expecting an individual gate's success line.

Step-level `timeout` defaults to 120 seconds. A step that times out keeps its
partial output and reports it, rather than discarding the one case where the
output matters most.

`platforms` defaults to `["posix"]`. A manifest needing `sh` or a Unix-only
binary says so, and is skipped on Windows with the skip counted in the summary —
a skip is never reported as a pass.

Red paths are first-class examples: a step that expects `rc: 1` passes only when
the gate really rejects the supplied input. Dynamic fixtures may use a small
Python preparation script; no gate-specific case belongs in the runner.
