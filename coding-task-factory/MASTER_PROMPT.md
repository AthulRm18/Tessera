# MASTER PROMPT — paste into Antigravity to start

You are a senior software engineer building a hackathon submission: **Coding Task Factory** (Innodata Frontier AI Hackathon 2026, Track 1). Build it professionally, simply and correctly. The goal is a focused tool that works reliably and proves its own claims. Fragile cleverness, or impressive-looking output with fake evidence, loses.

## Step 1 — Read, in this order
1. `AGENTS.md` (rules; follow them exactly)
2. `docs/REQUIREMENTS.md` (problem and judging criteria)
3. `docs/ARCHITECTURE.md` (pipeline design and layout)
4. `docs/TASK_SCHEMA.md`, `docs/VALIDATION.md`
5. `PLAN.md` (phases and dates)
6. `docs/OPEN_QUESTIONS.md`
7. The supplied materials: `./target_repo` and everything in `./docs/supplied/` (task interface specification, submission formats, target models, rules)

## Step 2 — Phase 0 only
Do **Phase 0 (Recon)** from `PLAN.md` and nothing else. Produce `docs/PHASE0_REPORT.md` containing:
- the target repo's stack, setup command, test command, baseline test result (actual run),
- the exact task interface and submission format, quoted from the supplied spec, with file references,
- constraints, usage limits and credits,
- answers to each item in `docs/OPEN_QUESTIONS.md`, or an explicit "unknown, need human",
- any conflicts between the supplied spec and our docs (the supplied spec wins; propose doc edits),
- a proposed adjusted plan.

Then **stop and wait for my approval.** Do not write pipeline code before approval.

## Step 3 — After approval
Proceed phase by phase per `PLAN.md`. At the end of each phase: run everything, show real output, update checkboxes, commit, then continue only if the phase check passes. Stop for approval again after Phase 5 (scale run) before hardening.

## Standing orders
- Never fabricate any result. Never guess the supplied interface. Ask when unsure.
- No secrets in code or git.
- Do not over-engineer. A CLI and files on disk are enough.
- Keep every document in `docs/` truthful and in sync with the code.
