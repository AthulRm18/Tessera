# DECISIONS.md — Design decision log

Add an entry whenever you choose between real alternatives or add a dependency. Short and dated.

## Template
```
### D-NNN · Title · YYYY-MM-DD
Context:
Decision:
Alternatives considered:
Consequences:
```

### D-001 · Python CLI, files on disk · 2026-11-11
Context: Organisers say a command-line tool or lightweight app is enough; reliability beats polish.
Decision: Python 3.11+, typer CLI, JSON/YAML artefacts, no UI, no database.
Alternatives: web dashboard, service with queue.
Consequences: Faster to build and verify; demo is terminal-based, so it must be clean and narrated.

### D-002 · Validate-first gates decide acceptance · 2026-11-11
Context: Hard part is validity, not generation.
Decision: LLM proposes; deterministic gates (G1–G7) accept or reject.
Alternatives: LLM-as-judge for validity.
Consequences: More engineering up front, much stronger evidence.

### D-003 · Mutation limited to lines added by the reference patch · 2026-11-11
Context: Full-repo mutation is slow and irrelevant to the task.
Decision: Mutate only the patch's added lines with simple operators.
Alternatives: third-party mutation tools per language.
Consequences: Fast and language-agnostic; weaker than full mutation tools (documented in limitations).

### D-004 · Behavioural distinctness via cross-running tests · 2026-11-11
Context: "Different" must mean behaviour, not wording.
Decision: Run each task's tests against every other task's patch.
Alternatives: embedding similarity of descriptions.
Consequences: Directly proves variation; O(n²) runs, fine for ≤15 tasks.

### D-005 · Disk cache for every LLM call · 2026-11-11
Context: Cost limits, resumable runs, reliable demo.
Decision: Hash (model, prompt, params) → cached response; usage ledger.
Alternatives: none cheaper.
Consequences: Enables `demo --replay`; cache must never be used to hide failures in reported runs (record cache hits in the report).
