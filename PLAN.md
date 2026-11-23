# PLAN.md — Phases, dates, progress

**Project:** Tessera — Coding Task Factory (Innodata Frontier AI Hackathon 2026, Track 1).
**Today:** 23 Nov 2026. **Build window:** 10 Nov – 6 Dec 2026. **Target submit:** 5 Dec.

## Key dates
| Date | Event |
|---|---|
| 10 Nov | Launch, registration open |
| 19 Nov | Problem statement explainer (attended) |
| 6 Dec | Submissions due |
| 7–15 Dec | Judging |
| 14 Dec | Finalists announced (top 10–14) |
| 15 Dec | Finalists meet mentors |
| 20 Dec | Grand Finale, live pitch, New Delhi |

## Team and ownership
| Area | Owner |
|---|---|
| Pipeline core, gates G1–G4 | TBD |
| Mutation + solver G6–G7 | TBD |
| Planner/generator + LLM layer | TBD |
| Packaging (Harbor), verify, docs, demo | TBD |

## Revised schedule (re-baselined 23 Nov)
| By | Target |
|---|---|
| 26 Nov | scaffold ✔ partial, config ✔, schemas ✔, CLI ✔, llm.py, two stand-in repos approved, fixtures, gates G1–G4 with accept+reject tests |
| 30 Nov | generation end-to-end on a stand-in repo; Harbor packaging |
| 2 Dec | G5–G7, distinctness, clean-room verify |
| 4 Dec | scale run (5–6 tasks), report, demo, README, all docs filled from real data |
| 5 Dec | **Submit** |
| 6 Dec | Buffer only |

## Phase 0 — Recon
- [x] Register team, confirm Track 1
- [ ] Official repo + spec received (pending from Hack2Skill/Klent Abistado)
- [x] Task interface identified: **Harbor format** (verified by Klent Abistado email)
- [x] Stand-in repos strategy: pick two, swap in official repo via config change
- [x] Fill docs/OPEN_QUESTIONS.md
- [ ] Write docs/PHASE0_REPORT.md
- [ ] Confirm API access and usage limits (not yet issued by organizers)

## Phase 1 — Skeleton and gates G1–G4 (by 26 Nov)
- [x] Project scaffold (pyproject.toml, .env.example, config.yaml, .gitignore)
- [x] factory/config.py (Pydantic config)
- [x] factory/schemas.py (Pydantic models)
- [x] factory/cli.py skeleton (all commands stubbed; rename: `tessera` / `tess`)
- [ ] factory/llm.py with disk cache and usage ledger
- [ ] Stand-in repo shortlist → human approval → two repos
- [ ] tests/fixtures: known-good and known-bad task per gate
- [ ] factory/repo.py: profile, baseline, repo map, worktrees (config-driven)
- [ ] factory/gates.py: G1–G4, cheapest-first, stop at first failure
- [ ] **Check:** gates accept good fixture, reject bad fixture (pytest accept + reject tests)

## Phase 2 — LLM generation and planner (by 30 Nov)
- [ ] factory/planner.py: coverage grid (module × axis × partner)
- [ ] factory/generator.py: requirements, reference patch, tests, regression checks; repair loop
- [ ] Harbor packager: emits task directories (instruction.md, task.toml, solution/solve.sh, tests/test.sh)
- [ ] **Check:** ≥2 tasks generated end-to-end, validated G1–G4, packaged as Harbor

## Phase 3 — Gates G5–G7 (by 2 Dec)
- [ ] G5 traceability (every criterion tested, every test mapped, every symbol declared)
- [ ] G6 mutation check (patch lines only; kill-rate; one repair for survivors)
- [ ] G7 independent solve (separate session; fixed budget; flag unclear requirements)
- [ ] factory/distinct.py: behavioural overlap matrix; drop duplicates
- [ ] factory/verify.py: clean-room re-run of a package
- [ ] **Check:** kill rate and solver result in every validation_report.json

## Phase 4 — Scale run and evidence (by 4 Dec)
- [ ] Run 5–6 tasks; accept only fully validated
- [ ] factory/report.py: real metrics table
- [ ] samples/ holds best accepted packages
- [ ] tessera demo and --replay working
- [ ] README: criteria map, quickstart, reused components
- [ ] **Human approval before hardening**

## Phase 5 — Hardening and submission (4–5 Dec)
- [ ] Fresh-clone test of README quickstart
- [ ] Secret scan (output saved)
- [ ] All docs filled from real run data only
- [ ] MANUAL_STEPS.md honest and complete
- [ ] Walk through SUBMISSION_CHECKLIST.md
- [ ] **Submit**

## Rolling rules
- Commit after every step; imperative messages.
- If a phase check fails, fix before moving on.
- Quality over count: 5–6 strong tasks beats 15 weak ones.
- Update this file at the end of every work session.
