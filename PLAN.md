# PLAN.md — Phases, dates, progress

Today is 11 Nov 2026. Build window: **10 Nov – 6 Dec 2026**. Aim to **submit by 5 Dec evening**; keep 6 Dec as buffer only.

## Key dates
| Date | Event |
|---|---|
| 10 Nov | Launch, registration open |
| 19 Nov | Problem statement explainer (attend; ask the open questions) |
| 6 Dec | Submissions due |
| 7–15 Dec | Judging |
| 14 Dec | Finalists announced (top 10–14) |
| 15 Dec | Finalists meet mentors |
| 20 Dec | Grand Finale, live pitch, New Delhi |

## Team and ownership (FILL; team must be 3–4 people)
| Area | Owner |
|---|---|
| Pipeline core, gates (G1–G4) | |
| Mutation + solver (G6–G7) | |
| Planner/generator + LLM layer | |
| Packaging, verify, docs, demo | |

## Phase 0 — Recon (target: by 14 Nov)
- [ ] Register team, confirm Track 1, receive repo + spec
- [ ] Put repo in `./target_repo`, spec in `./docs/supplied/`
- [ ] Run baseline tests on the repo; record result
- [ ] Fill `docs/OPEN_QUESTIONS.md`
- [ ] Write `docs/PHASE0_REPORT.md`
- [ ] Human approval of plan
- [ ] Confirm API access and usage limits; set `.env`

## Phase 1 — Skeleton and gates G1–G4 (by 24 Nov)
- [ ] Project scaffold, config, CLI skeleton
- [ ] `repo.py`: profile, baseline, repo map, worktrees
- [ ] `gates.py`: G1 clean apply, G2 fail-to-pass, G3 no regressions, G4 determinism
- [ ] One hand-made known-good and known-bad task fixture; gate tests accept/reject
- [ ] **Check:** gates correctly accept the good fixture and reject the bad one

## Phase 2 — LLM generation and planner (by 29 Nov)
- [ ] `llm.py` with cache and usage ledger
- [ ] `planner.py` coverage grid
- [ ] `generator.py` requirements + reference patch + tests + regression checks
- [ ] Repair loop (max 2 repairs)
- [ ] **Check:** at least 3 tasks generated end to end and validated by G1–G4 on the real repo

## Phase 3 — Gates G5–G7 (by 1 Dec)
- [ ] G5 traceability
- [ ] G6 mutation check on lines added by the reference patch
- [ ] G7 independent solve with fixed attempt budget
- [ ] **Check:** mutation kill rate and solver result recorded in validation reports

> If behind schedule, cut stretch items and reduce task count. Never cut validation.

## Phase 4 — Distinctness, packaging, verify (by 2 Dec)
- [ ] `distinct.py` behavioural overlap matrix
- [ ] `packager.py` in the official interface format
- [ ] `factory verify` from a clean checkout
- [ ] **Check:** verify passes for every accepted package

## Phase 5 — Scale run and evidence (target: 2–3 Dec)
- [ ] Run N = 10–15 planned tasks; accept what truly passes
- [ ] `factory report` with real numbers; rejected tasks kept with reasons
- [ ] `samples/` holds best real packages
- [ ] `factory demo` and `--replay` working
- [ ] **Human approval before hardening**

## Phase 6 — Hardening and submission (4–5 Dec)
- [ ] Fresh-clone test of README quickstart
- [ ] Secret scan on repo and git history
- [ ] Fill `docs/VALIDATION.md` and `docs/LIMITATIONS.md` from real data
- [ ] `MANUAL_STEPS.md` complete and honest
- [ ] Walk through `docs/SUBMISSION_CHECKLIST.md`
- [ ] **Submit**

## Rolling rules
- If a phase check fails, fix it before moving on.
- Keep scope small. If time is short, reduce task count, never validation quality.
- Update this file at the end of every work session.
