# Taste

## Communication
- Writes and expects replies in Chinese (Simplified). Confidence: 0.7
- Gives ultra-terse instructions — a bare file path plus a one-word verb (e.g. `.../HANDOFF.md  读`) — and expects the agent to infer the full intent and act immediately, without asking clarifying questions. Confidence: 0.6

## Tooling & workflow
- Prefers live ground-truth over docs: before acting, tells the agent to first query real repo state with the `gh` CLI (e.g. `gh issue list --state=all`) rather than relying on a handoff document's snapshot. Confidence: 0.6
