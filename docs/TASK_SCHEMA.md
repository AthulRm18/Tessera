# TASK_SCHEMA.md

> **The official task interface supplied by the organisers overrides this file.** This is our internal schema. Phase 0 must map it to the official format; the packager emits the official format.

## Package folder
```
packages/<task_id>/
├── task.json                # metadata (below)
├── requirements.md          # numbered acceptance criteria + Interface section
├── reference.patch          # unified diff against the base commit
├── tests/
│   ├── feature/             # tests for the new behaviour
│   └── regression/          # characterization tests for adjacent existing behaviour
└── validation_report.json   # evidence for every gate
```
plus a top-level `manifest.json` listing all packages.

## task.json
| Field | Type | Notes |
|---|---|---|
| `task_id` | string | stable, e.g. `task_007_cart_discount_threshold` |
| `title` | string | short |
| `base_commit` | string | exact hash of starting repo version |
| `base_tag` | string | repo tag or ref used |
| `module` | string | target module or area |
| `behaviour_axis` | string | from the taxonomy |
| `interaction_partner` | string or null | other feature involved |
| `behaviour_signature` | string | short description of the distinct behaviour, used for coverage |
| `interface` | list | every new function/class/signature/error the tests rely on |
| `acceptance_criteria` | list | `{id: "AC1", text: "..."}` |
| `test_map` | object | test id → list of criterion ids |
| `generator` | object | model id, seed, run id, prompt hash |
| `created_at` | string | ISO timestamp |

## requirements.md structure
1. **Context** — what part of the repo this touches (real file and symbol names).
2. **Feature** — plain-language goal.
3. **Acceptance criteria** — numbered `AC1…ACn`, each testable and unambiguous.
4. **Interface** — exact names, signatures, return values and error types tests will call. Prevents false failures from naming mismatches.
5. **Out of scope** — what must not change.
No implementation hints. No leaking of the reference solution.

## validation_report.json
```
{
  "task_id": "...",
  "base_commit": "...",
  "gates": {
    "G1_clean_apply":      {"passed": bool, "evidence": "..."},
    "G2_fail_to_pass":     {"passed": bool, "base_failed": [..], "patched_passed": [..]},
    "G3_no_regressions":   {"passed": bool, "suite_before": {...}, "suite_after": {...}},
    "G4_determinism":      {"passed": bool, "runs": 3, "flaky_tests": []},
    "G5_traceability":     {"passed": bool, "uncovered_criteria": [], "orphan_tests": [], "undeclared_symbols": []},
    "G6_mutation":         {"passed": bool, "mutants": N, "killed": K, "kill_rate": float, "survivors": [..]},
    "G7_independent_solve":{"solved": bool, "attempts": n, "notes": "..."}
  },
  "repairs": n,
  "accepted": bool,
  "reject_reason": null,
  "run": {"tokens": n, "est_cost": x, "duration_s": y}
}
```
All values come from real executions.
