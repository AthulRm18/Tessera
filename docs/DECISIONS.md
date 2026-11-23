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

### D-006 · Harbor as the task package format · 2026-11-23
Context: Klent Abistado (Hack2Skill) confirmed via email that the task interface follows the Harbor format (harborframework.com).
Decision: Packager emits Harbor task directories: instruction.md, task.toml, environment/ (or docker_image in task.toml), solution/solve.sh, tests/test.sh; verifier writes reward to /logs/verifier/reward.txt.
Alternatives: Custom format (would conflict with the supplied spec).
Consequences: We must read Harbor docs carefully and quote fields exactly; never guess schema_version.

### D-007 · Harbor CLI not installed; use Docker directly for now · 2026-11-23
Context: `harbor --version` is not recognised on this machine. Docker 29.3.1 is installed.
Decision: Build Harbor-compatible task directories and validate their structure manually + via Docker until Harbor CLI is confirmed available. Document as a gap in LIMITATIONS.md. Revisit once official environment is provided.
Alternatives: Install Harbor CLI now — but no confirmed install path for Windows; risk of version mismatch with organizer environment.
Consequences: We cannot run `harbor job run` locally yet; `tessera verify` will re-run the Docker container directly.

### D-008 · Two stand-in repos in different languages · 2026-11-23
Context: Official repo not yet provided; Klent confirmed we can work with any repo and swap later.
Decision: Choose two stand-in repos (shortlist to be proposed and approved by human). All repo specifics in config.yaml only.
Alternatives: Wait for official repo — wastes ~2 weeks of build time.
Consequences: Must prove pipeline is not hard-coded: "swapping repo = only config.yaml change + rerun."

### D-009 · CLI renamed tessera / tess (not factory) · 2026-11-23
Context: Project is called Tessera; `factory` as the CLI name is inconsistent and confusing.
Decision: CLI entry point is `tessera` with alias `tess`. The Python package folder stays `factory/` to avoid churn until all modules are built, then rename in one commit.
Alternatives: Rename package now — risks breaking import chains mid-build.
Consequences: pyproject.toml `[project.scripts]` updated: `tessera = "factory.cli:app"`.

### D-010 · Gates run cheapest-first; stop at first failure · 2026-11-23
Context: LLM calls (G7) are expensive; deterministic gates are free.
Decision: Order: G1 → G2 → G3 → G4 → G5 → G6 → G7. Stop and log at first failure. G7 only runs on tasks that passed G1–G6.
Alternatives: Run all gates always.
Consequences: Saves tokens; rejected tasks still logged with the first failing gate.

### D-011 · Mock LLM provider only in tests · 2026-11-23
Context: Official API access not yet issued; need to build and test without real calls.
Decision: A mock provider is allowed ONLY in tests. Any run using it is flagged and excluded from reports. Real runs require real credentials.
Alternatives: Use free-tier models — may not be available or permitted.
Consequences: Pipeline works end-to-end in tests without credentials; production runs need .env set up.
