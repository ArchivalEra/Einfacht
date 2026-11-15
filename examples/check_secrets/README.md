# Secrets example

The credential-shaped string in `app/leaked.txt` is the public AWS documentation
example, not a credential. It exists to make the gate go red inside a temporary
repo. Findings print path, line, and rule only; the matched value must not appear
in runner output. `allowed.json` demonstrates a narrow exemption and
`stale-allow.json` proves that an unused exemption is itself rejected.
