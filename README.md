# Coding Task Factory

Turn a real codebase into **solvable, testable, meaningfully different** feature-development tasks for evaluating AI coding systems. Every task ships with requirements, a reference implementation, feature tests and regression checks, and is only accepted if it passes automated validation gates.

**Status:** pre-development. Fill the sections marked `FILL` from real runs only. Never write a number you did not measure.

## What it does
1. **Profiles** the supplied repo (stack, test command, baseline health, repo map).
2. **Plans** a coverage grid of distinct tasks (module x behaviour axis x interaction).
3. **Generates** requirements, a reference patch and tests with an LLM, inside isolated git worktrees.
4. **Validates** each task through gates G1-G7 (fail-to-pass, no regressions, determinism, traceability, mutation check, independent solve).
5. **Checks distinctness** behaviourally (task A's tests vs task B's patch).
6. **Packages** accepted tasks in the official interface format, plus a clean-room `verify` command.
7. **Reports** real numbers: acceptance rate, mutation kill rate, solver pass rate, coverage, cost.

## Quickstart (FILL after Phase 1)
```bash
# 1. clone and enter
# 2. python -m venv .venv && source .venv/bin/activate
# 3. pip install -e .
# 4. cp .env.example .env   # add keys locally, never commit
# 5. place the supplied repo at ./target_repo and spec files in ./docs/supplied/
factory profile
factory run -n 10
factory verify packages/<task_id>
factory report
factory demo
```

## Commands
| Command | Purpose |
|---|---|
| `factory profile` | Detect stack, run baseline tests, build repo map |
| `factory run -n N` | Plan, generate, validate, package N tasks |
| `factory verify PATH` | Clean-room re-validation of one package |
| `factory report` | Aggregate real metrics from run logs |
| `factory demo [--replay]` | Live generate+validate one package (or replay cached run) |

## Documentation map
| File | Read it for |
|---|---|
| `AGENTS.md` | Rules for every coding agent and teammate |
| `PLAN.md` | Phases, dates, owners, progress tracker |
| `docs/REQUIREMENTS.md` | Problem statement, judging criteria, submission contents |
| `docs/ARCHITECTURE.md` | Pipeline design and repo layout |
| `docs/TASK_SCHEMA.md` | Task package format |
| `docs/VALIDATION.md` | Gate definitions, metrics, results (FILL) |
| `docs/LIMITATIONS.md` | Honest limits |
| `docs/DEMO.md` | Demo script and backup plan |
| `docs/DECISIONS.md` | Design decision log |
| `docs/OPEN_QUESTIONS.md` | Unknowns to resolve after registration |
| `docs/SUBMISSION_CHECKLIST.md` | Final pre-submit checklist |
| `MANUAL_STEPS.md` | Log of any manual intervention |

## Reused open-source components (FILL)
List every library or tool reused, with licence.

## Team (FILL)
Names and roles.
