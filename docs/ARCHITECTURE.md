# ARCHITECTURE.md

Principle: **validate first, generate second.** The LLM proposes; deterministic gates decide.

## Pipeline
```
 target_repo ──► PROFILE ──► PLAN ──► GENERATE ──► VALIDATE (G1..G7) ──► DISTINCT ──► PACKAGE ──► REPORT
                  │          │          │              │  ▲                  │            │
              baseline    coverage   worktree      repair loop            overlap      official
              + repo map    grid     per task      (max 2)                matrix       format
                                                                                          │
                                                         VERIFY (clean-room replay) ◄─────┘
```

## Stages
| Stage | Module | Input | Output |
|---|---|---|---|
| Profile | `repo.py` | repo path, config | profile.json: commands, baseline result, repo map, base commit/tag |
| Plan | `planner.py` | profile, N | plans.json: distinct (module, axis, partner) plans grounded in real symbols |
| Generate | `generator.py` | plan, worktree | requirements, reference patch, feature tests, regression checks |
| Validate | `gates.py`, `mutation.py`, `solver.py` | candidate task | per-gate evidence; accept or reject |
| Distinct | `distinct.py` | accepted tasks | overlap matrix; drops duplicates |
| Package | `packager.py` | accepted tasks | package folders in the official format + manifest |
| Verify | `verify.py` | package + clean checkout | re-run of all gates; pass or fail |
| Report | `report.py` | run logs | real metrics tables |

## Gates (summary; full spec in `VALIDATION.md`)
G1 clean apply · G2 fail-to-pass · G3 no regressions · G4 determinism · G5 traceability · G6 mutation check · G7 independent solve.

## Repository layout (target)
```
coding-task-factory/
├── README.md  AGENTS.md  PLAN.md  MANUAL_STEPS.md  MASTER_PROMPT.md
├── config.yaml            # repo commands, thresholds, counts, env var names
├── .env.example           # variable names only
├── pyproject.toml
├── docs/                  # these docs; supplied/ holds organiser materials
├── factory/
│   ├── cli.py             # typer commands
│   ├── config.py          # pydantic config
│   ├── schemas.py         # pydantic models for plan, task, evidence
│   ├── llm.py             # single LLM function, disk cache, usage ledger
│   ├── repo.py            # profile, baseline, repo map, worktrees
│   ├── planner.py
│   ├── generator.py
│   ├── gates.py           # G1-G5
│   ├── mutation.py        # G6
│   ├── solver.py          # G7
│   ├── distinct.py
│   ├── packager.py
│   ├── verify.py
│   └── report.py
├── tests/                 # pipeline's own pytest suite and fixtures
├── samples/               # best real accepted packages (committed deliberately)
├── runs/                  # per-run logs and caches (gitignored)
└── target_repo/           # supplied repo (not modified in place; worktrees only)
```

## Key design choices
1. **Worktrees, not copies.** Each task runs in an isolated `git worktree` at the tagged base commit. Cheap, clean, reproducible.
2. **Fail-to-pass as the core proof.** Feature tests must fail before and pass after the reference patch.
3. **Mutation scoped to the patch.** Mutants only on lines the reference added. Fast and meaningful; shows tests catch wrong behaviour.
4. **Independent solver.** A separate session sees requirements and base repo only. Gives a solvability and difficulty signal and reveals unclear requirements.
5. **Behavioural distinctness.** Cross-run each task's tests against every other task's patch.
6. **Cache everything.** LLM calls hashed to disk; runs are resumable, cheap and replayable for the demo.
7. **Repo specifics in config.** Setup command, test command, result parsing, language hints. No repo names in code.
8. **Simple failure policy.** Failing gate triggers at most 2 repairs with structured feedback, then reject and log the reason.

## Config (`config.yaml`) fields
```
repo: {path, base_ref, setup_cmd, test_cmd, result_format, timeout_s}
generation: {n_tasks, behaviour_axes, max_repairs}
gates: {determinism_runs, mutation_kill_threshold, solver_attempts}
llm: {provider_env, model_env, key_env, max_tokens, temperature}
output: {runs_dir, packages_dir}
```

## Behaviour axes (generic taxonomy)
new business rule · threshold or limit · state transition · validation and error policy · ordering or priority · interaction between two existing features · idempotency · rounding or units. Planner picks combinations not yet used.

## Out of scope (deliberately)
Web UI, hosted service, database, queues, multi-language mutation frameworks, vector stores, learning loops.
