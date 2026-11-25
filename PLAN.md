# PLAN.md — Phases, Schedule, and Milestone Tracking

**Project:** Tessera — Coding Task Factory (Innodata AI Hackathon 2026, Track 1).
**Today:** 25 Nov 2026. **Target Repository:** `pallets/click`.
**Build Window:** 10 Nov – 6 Dec 2026. **Target Submit:** 5 Dec 2026. **Hard Deadline:** 6 Dec 2026.

---

## Revised Schedule (Re-baselined 25 Nov 2026 — Official PDF Alignment)

| Date Window | Target Milestones | Status |
|---|---|:---:|
| **26–27 Nov** | Hardening (shallow pinned Dockerfile, package hygiene, stronger solver); planner & generator; first 2 generated tasks passing G1–G7, N1, and Harbor `nop`/`oracle`. | **IN PROGRESS** |
| **28 Nov** | Complete G5–G7, N1 upstream-novelty, and behavioural distinctness matrix across tasks. | Pending |
| **29–30 Nov** | Full scale run generating 7–8 candidates to yield at least 5 accepted tasks from `pallets/click`. | Pending |
| **1–2 Dec** | Full validation evidence, deterministic `--replay` mode via committed secret-free LLM cache, fresh-machine test. | Pending |
| **3–4 Dec** | Walkthrough demo video, submission slide deck, `docs/TECHNICAL_EXPLANATION.md`. | Pending |
| **5 Dec** | Final verification checklist, tag commit `submission`, submit. | Pending |
| **6 Dec** | Buffer / contingency day. | Pending |

---

## Milestone Details

### Milestone 1 — Spec, Click Pinned Commit & Harbor 0.25.x Reality Check (25–26 Nov)
- [x] Record official PDF specifications in `docs/ORGANIZER_BRIEF.md`
- [x] Record open questions & discrepancies in `docs/OPEN_QUESTIONS.md`
- [x] Update `docs/TASK_SCHEMA.md` to Harbor 0.25.x with per-task `environment/Dockerfile`
- [x] Create `docs/MODELS.md` declaring all models and tools
- [x] Select recent stable release tag of `pallets/click` and record full 40-char hash (`8.5.1` / `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1`)
- [x] Build Docker image from `environment/Dockerfile` and verify clean green baseline tests (3x offline runs: 2434 passed, 24 skipped, 31000 deselected, 1 xfailed)
- [x] **Approval checkpoint 1:** Show tag, hash, license, Python version, container test count & runtime, and green baseline
- [x] Install `harbor==0.25.*` and verify `harbor --version` in WSL2 / Linux (`0.25.0`)
- [x] Hand-build 1 Click task (`ip_address_type`) in Harbor 0.25.x format; verify `nop` = 0.0 and `oracle` = 1.0 in Docker
- [x] Show `tests/fail_to_pass.json` and `tests/pass_to_pass.json`
- [ ] **Approval checkpoint 2:** Harbor reality check verification (awaiting user OK)

### Milestone 2 — Generation & Planner End-to-End (27–29 Nov)
- [ ] `configs/click.yaml` tuned for Click symbols and behaviour axes (feature additions only; bug fixes disabled)
- [ ] Coverage grid: module $\times$ axis $\times$ partner combinations for Click
- [ ] Requirements generator producing `instruction.md` with numbered ACs and interface contracts
- [ ] Reference patch generator with unified diff formatting
- [ ] Automated repair loop (max 2 repairs with structured gate feedback)
- [ ] First live run: generate 2 tasks on Click; verify G1–G4
- [ ] **Approval checkpoint 3:** Review first 2 generated tasks

### Milestone 3 — Gates G5–G7, Upstream Novelty & 5 Accepted Tasks (30 Nov – 1 Dec)
- [ ] G5 Traceability check (every AC tested; interface symbols verified)
- [ ] G6 Scoped mutation check on patch lines (mutation kill rate reported)
- [ ] G7 Independent solver pass (separate model session seeing only `instruction.md`)
- [ ] Upstream-novelty gate: run tests against Click default branch without patch
- [ ] Behavioural distinctness matrix: verify cross-test non-overlap
- [ ] Generate 7–8 candidates to yield at least 5 fully validated accepted tasks

### Milestone 4 — Packaging, Evidence & Fresh Replay (2–3 Dec)
- [ ] Generate Harbor 0.25.x packages with `fail_to_pass.json` and `pass_to_pass.json`
- [ ] Official container verification: `nop` 0.0, `oracle` 1.0 on all 5 packages
- [ ] Gather evidence logs, mutation reports, ledger summaries into `runs/`
- [ ] Replay test on clean WSL2 / Linux environment

### Milestone 5 — Documentation, Video, Deck & Submission (4–5 Dec)
- [ ] Technical explanation (`docs/TECHNICAL_EXPLANATION.md`)
- [ ] Script and record 5-minute walkthrough demo video (`docs/DEMO.md`)
- [ ] Complete submission slide deck following organizer template
- [ ] Complete `docs/SUBMISSION_CHECKLIST.md`
- [ ] Tag git commit `submission` and submit before 5 Dec 23:59
