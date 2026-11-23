# TASK_SCHEMA.md — Harbor Task Format

> **The official task interface is the Harbor format** (harborframework.com).
> This file documents the Harbor structure as we understand it from the docs.
> The supplied organizer spec overrides this file wherever they differ.
> Phase 0 must confirm every field against the official spec; packager emits the Harbor format only.
>
> Source: https://docs.harborframework.com/llms.txt (tasks/overview, tasks/configuration,
> tasks/instruction, tasks/environment, tasks/solution, tasks/verifier,
> tutorials/create-a-task, jobs/run-a-job) — read and quoted; never guessed.

---

## Harbor task directory layout

```
packages/<task_id>/
├── instruction.md          # Task description shown to the solver
├── task.toml               # Task configuration (Harbor schema)
├── environment/            # (Optional if docker_image set in task.toml)
│   └── Dockerfile
├── solution/
│   └── solve.sh            # Reference implementation script
└── tests/
    └── test.sh             # Test runner; writes reward to /logs/verifier/reward.txt
```

Plus our internal metadata alongside each package:
```
packages/<task_id>/
└── tessera/
    ├── task_metadata.json      # Tessera task.json (module, axis, criteria, etc.)
    └── validation_report.json  # Gate evidence G1–G7
```

And a top-level manifest:
```
packages/
└── manifest.json
```

---

## task.toml fields (Harbor)

> Fields quoted from Harbor docs. Mark any field as [UNVERIFIED] if not confirmed from docs.

```toml
schema_version = "..."          # Harbor schema version — MUST be exact; read from docs, never guess

[task]
name = "..."                    # Short task name
description = "..."             # One-line description

[environment]
docker_image = "..."            # Pre-built image (omit environment/ folder when set)
# OR use environment/Dockerfile instead

[verifier]
# Verifier writes a numeric reward to /logs/verifier/reward.txt (or reward.json)
# Exact fields TBD from docs — [UNVERIFIED beyond reward file path]
```

> **[UNVERIFIED]:** Exact `schema_version` value, full set of `[task]`, `[environment]`, `[verifier]`
> fields — must be read from https://docs.harborframework.com before packager is finalised.
> Do not write packager code that guesses these fields.

---

## instruction.md structure (our content, within Harbor's container)

1. **Context** — what part of the repo this touches (real file and symbol names).
2. **Feature** — plain-language goal.
3. **Acceptance criteria** — numbered `AC1…ACn`, each testable and unambiguous.
4. **Interface** — exact names, signatures, return values and error types tests will call. Prevents false failures from naming mismatches.
5. **Out of scope** — what must not change.

No implementation hints. No leaking of the reference solution.

---

## solution/solve.sh

The reference implementation. Runs inside the Harbor container. Applies the patch or writes the implementation directly. Must make all feature tests pass without breaking existing tests.

---

## tests/test.sh

Runs the test suite inside the container. Final line writes the reward:
```bash
echo "1" > /logs/verifier/reward.txt   # 1 = pass, 0 = fail
```
Or writes JSON to `/logs/verifier/reward.json` (confirm format from docs).

---

## tessera/validation_report.json (our internal evidence)

```json
{
  "task_id": "...",
  "base_commit": "...",
  "gates": {
    "G1_clean_apply":      {"passed": true,  "evidence": "patch applied cleanly"},
    "G2_fail_to_pass":     {"passed": true,  "base_failed": ["test_x"], "patched_passed": ["test_x"],
                            "organizer_checks": {
                              "original_repo_works": true,
                              "tests_pass_with_implementation": true,
                              "tests_fail_without_feature": true
                            }},
    "G3_no_regressions":   {"passed": true,  "suite_before": {}, "suite_after": {}},
    "G4_determinism":      {"passed": true,  "runs": 3, "flaky_tests": []},
    "G5_traceability":     {"passed": true,  "uncovered_criteria": [], "orphan_tests": [], "undeclared_symbols": []},
    "G6_mutation":         {"passed": true,  "mutants": 10, "killed": 8, "kill_rate": 0.80, "survivors": []},
    "G7_independent_solve":{"solved": true,  "attempts": 1, "notes": ""}
  },
  "repairs": 0,
  "accepted": true,
  "reject_reason": null,
  "run": {"tokens": 0, "est_cost": 0.0, "duration_s": 0.0, "tool_versions": {}, "cache_hits": 0}
}
```

All values come from real executions. Never fabricate.

---

## tessera/task_metadata.json

```json
{
  "task_id": "task_001_cart_discount_threshold",
  "title": "Add discount threshold to cart",
  "base_commit": "<exact SHA>",
  "base_tag": "<tag or ref>",
  "module": "cart",
  "behaviour_axis": "threshold_or_limit",
  "interaction_partner": null,
  "behaviour_signature": "apply discount when subtotal exceeds threshold",
  "interface": ["Cart.apply_discount(code: str, threshold: float, pct: float) -> float"],
  "acceptance_criteria": [
    {"id": "AC1", "text": "..."},
    {"id": "AC2", "text": "..."}
  ],
  "test_map": {"test_discount_applied": ["AC1"], "test_no_discount_below_threshold": ["AC2"]},
  "generator": {"model": "<from env>", "seed": 42, "run_id": "...", "prompt_hash": "..."},
  "created_at": "2026-11-23T..."
}
```
