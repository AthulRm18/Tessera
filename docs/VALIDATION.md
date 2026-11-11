# VALIDATION.md

Validation is half the score. This file defines every gate precisely and holds the **real** results. Sections marked FILL are completed only from actual runs.

## Acceptance rule
A task is accepted only if **G1–G6 pass**. G7 is recorded as solvability evidence and triggers one repair when it suggests unclear requirements or over-specified tests.

## Gate definitions
**G1 Clean apply** — Reference patch applies cleanly to the base commit. Code imports/compiles. Run lint/type checks only if the repo already uses them.

**G2 Fail-to-pass** — Feature tests FAIL on the base commit and PASS with the reference patch. Failures on base must be assertion failures about missing behaviour, not import or syntax errors that would pass trivially for the wrong reason (record the failure type).

**G3 No regressions** — Full existing suite result after the patch equals or improves the baseline. Characterization tests pass both before and after.

**G4 Determinism** — Feature tests run 3 times (configurable) with identical results. Any flaky test rejects the task.

**G5 Traceability** — Every acceptance criterion has at least one test. Every test maps to a criterion. Every new symbol used by tests appears in the requirements' Interface section.

**G6 Mutation check** — Apply simple mutants only to lines added by the reference patch: flip comparison operators, shift boundaries by one, swap and/or, negate conditions, remove a branch, replace a return with a constant. Discard mutants that do not compile. `kill_rate = killed / valid_mutants`. Threshold in `config.yaml` (default 0.70). Survivors go to one repair round asking for stronger tests. Known limit: equivalent mutants are not detectable automatically.

**G7 Independent solve** — A separate model session sees only the requirements and the base repo (never the reference or tests) and has a fixed attempt budget. Tests are then run on its result. Record pass/fail and attempts. If a reasonable solution fails the tests, flag possible over-specified tests or ambiguous requirements and repair once.

## Repair policy
Max 2 repair rounds with structured failure feedback, then reject with a logged reason. Rejections stay in the report.

## Distinctness validation
For every accepted pair (A, B): run A's feature tests against base + B's reference patch. If A's tests pass, the pair overlaps; keep one. Output the full matrix. Also report coverage by module and behaviour axis.

## Verify (clean-room replay)
`factory verify PACKAGE` takes only the package folder and a clean checkout of the base commit and re-runs G1–G4 (and G6 if enabled). Judges can run it themselves.

## Metrics to report (all from real runs)
- tasks planned / generated / accepted; acceptance rate per gate
- rejection reasons histogram
- mutation kill rate: mean, min, per task
- solver pass rate and attempts
- distinctness matrix; coverage by module and axis
- repairs per task
- tokens, estimated cost, wall time per task and total

## Results (FILL from `factory report` only)
| Metric | Value | Run id | Date |
|---|---|---|---|
| Tasks planned | | | |
| Tasks accepted | | | |
| Mean mutation kill rate | | | |
| Solver pass rate | | | |
| Overlapping pairs found | | | |
| Total est. cost | | | |

## How to reproduce (FILL)
Exact commands and run ids.
