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

### D-012 · Official repo switch to pallets/click · 2026-11-25
Context: Official PDF restricts Track 1 to three designated repos only: pallets/click, colinhacks/zod, open-source-parsers/jsoncpp.
Decision: Select `pallets/click` (Python, pytest) as Tessera's submission repository. Stand-ins (PyJWT, validator.js) are retired from submission scope and kept only as local tests/fixtures.
Alternatives: colinhacks/zod (TypeScript), open-source-parsers/jsoncpp (C++).
Consequences: Pipeline core remains 100% config-driven via `configs/click.yaml`.

### D-013 · Bug-fix tasks strictly excluded · 2026-11-25
Context: Official PDF explicitly specifies: "Tasks must represent new feature-development tasks or changes to existing behaviour. Bug-fix tasks are out of scope."
Decision: Strictly disable any bug-fix axis in generation. Tasks focus entirely on feature additions, parameter validation, new ParamTypes, option interactions, and behaviour policies.
Alternatives: Allow bug-fix tasks (would violate official requirements).
Consequences: All generated candidate tasks represent genuine additive feature capabilities.

### D-014 · Pin Harbor framework to v0.25.x with per-task Dockerfile · 2026-11-25
Context: Official PDF specifies: "Track 1 tasks strictly adhere to the Harbor framework (version 0.25.x). Harbor is installed via pip install 'harbor==0.25.*'." Each task folder must contain an `environment/Dockerfile`.
Decision: Pin Harbor version to 0.25.x. Each task package includes its own `environment/Dockerfile` building from the exact base commit.
Alternatives: Relying on generic `docker_image` tag without `environment/` (prohibited by PDF spec).
Consequences: Harbor task packages are 100% compliant with organizer specifications and Docker layer caching ensures fast re-builds.

### D-015 · Upstream-novelty gate and SWE-bench test split artifacts · 2026-11-25
Context: Official PDF requires that generated features must not exist upstream, and test packages must include `tests/fail_to_pass.json` and `tests/pass_to_pass.json`.
Decision: Implement an upstream-novelty gate testing candidate feature tests against click's latest default branch; automatically generate `fail_to_pass.json` and `pass_to_pass.json` from real test node IDs.
Alternatives: Hand-curating test lists (error-prone, violates reproducibility).
Consequences: Proven originality and full SWE-bench benchmark interoperability.

### D-016 · Computation of `pass_to_pass.json` from upstream baseline · 2026-11-25
Context: Running `pytest` on `pallets/click` at `8.5.1` (`cf19179e8e2fd54c601378cec9e0d21bb12b6fb1`) inside Debian Linux Docker yields 2,434 passed, 24 skipped (all Windows-only `msvcrt`/editor/fd checks), 1 `xfailed` (`tests/test_chain.py::test_group_chaining`), and 31,000 deselected (`addopts = "-m 'not stress'"` in `pyproject.toml`).
Decision: Compute `pass_to_pass.json` from the exact 2,434 pytest node IDs that have outcome `passed` under upstream's default test command (`pytest`) inside the pinned Linux container, excluding Windows-only skips, `xfailed` tests, and `stress` iterations.
Alternatives: Including skipped tests (breaks cross-OS parity) or overriding `addopts` to run 31,000 stress iterations (adds ~5+ min per container evaluation).
Consequences: Every regression check protects 100% of Click's deterministic Linux baseline suite in ~12s per run (`configs/click_pass_to_pass.json`).

### D-017 · Harbor `[environment].network_mode = "public"` for local Docker compatibility · 2026-11-25
Context: Harbor 0.25.0 `harbor run` failed with `ValueError: network_mode='no-network' is not supported by EnvironmentType.DOCKER environment` unless dynamic egress sidecar is enabled; `harbor task init` explicitly emits `network_mode = "public"`.
Decision: Set `network_mode = "public"` in `task.toml` `[environment]` (matching `harbor task init`) and `environment_mode = "shared"` in `[verifier]` so `solve.sh` changes are visible to `test.sh`. Test offline safety separately via `docker run --network none`.
Alternatives: `"no-network"` (crashes local `harbor run` with Docker driver).
Consequences: Both `harbor run -a nop` and `harbor run -a oracle` execute cleanly in Docker, while test hermeticity is independently verified with `--network none`.
