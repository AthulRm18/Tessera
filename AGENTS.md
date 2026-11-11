# AGENTS.md — Rules for every coding agent and teammate

Project: **Coding Task Factory** (Innodata Frontier AI Hackathon 2026, Track 1).
Read this file fully before touching anything. Then read `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `PLAN.md`.

## Non-negotiable rules
1. **Never fabricate.** Every number, report, sample and claim must come from a real run. If a run fails, report the failure.
2. **Never invent the supplied task interface or repo details.** The real ones live in `./target_repo` and `./docs/supplied/`. If anything is missing or ambiguous, STOP and ask a human.
3. **No secrets in code or git.** Keys go in `.env` (gitignored). Maintain `.env.example`. Run the secret scan before every release commit.
4. **Do not over-engineer.** No web UI, database, queue, microservice, plugin framework, or abstraction with a single implementation. Allowed: Python CLI, JSON/YAML files, git worktrees, subprocess with timeouts.
5. **Work in phases** (see `PLAN.md`). Finish, run, show output, commit. Do not start the next phase until the current one demonstrably works.
6. **Manual fixes** to generated output must be logged in `MANUAL_STEPS.md`. The pipeline itself should need zero manual steps.
7. **Reuse open source freely** but list every reused component in `README.md`.
8. **Ask when unsure.** A wrong assumption costs more than a question.

## Stack and conventions
- Python 3.11+, typed, small functions, clear names, no dead code, no TODO placeholders in merged code.
- Libraries: `typer`, `pydantic`, `rich`, `pytest`, `PyYAML`. Add others only with a one-line justification in `docs/DECISIONS.md`.
- Target repo may be any language. Repo-specific knowledge lives only in `config.yaml`, never in pipeline code.
- LLM access only through `llm.py` (single function returning structured JSON). Model names and keys come from environment variables. Never hardcode a model name.
- Cache every LLM call on disk keyed by hash of (model, prompt, params). Log tokens and estimated cost in a usage ledger.
- All subprocesses have timeouts. All task work happens in isolated git worktrees at the tagged starting commit.
- Every run writes a folder with seeds, model identifiers, config snapshot and logs.

## Git workflow
- Small commits, imperative messages (`Add fail-to-pass gate`).
- One feature branch per phase, merge to `main` only when the phase passes its check.
- Never commit `.env`, caches, worktrees, or large run artefacts. Sample packages are committed deliberately under `samples/`.

## Testing the pipeline itself
- The pipeline has its own `pytest` suite under `tests/`, using a tiny fixture repo plus one hand-made known-good task and one known-bad task per gate.
- A gate is only "done" when it has a passing test for accept AND a passing test for reject.

## Phase protocol
At the end of each phase: run everything, paste the output, update `PLAN.md` checkboxes, commit. Then stop and wait for human approval for Phases 0 and 5.

## Definition of done
See `docs/SUBMISSION_CHECKLIST.md`. Do not claim "finished" until every item is verified with evidence.

## Escalate to a human when
- the spec conflicts with these docs,
- usage limits or credits look insufficient,
- baseline tests of the target repo are not green,
- a gate cannot be made reliable,
- you are about to assume something.
