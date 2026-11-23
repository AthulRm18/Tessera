# docs/ORGANIZER_BRIEF.md

Summary of everything we know from the organizers. **VERIFIED** = confirmed source.
**UNVERIFIED** = AI summary of Q&A recording; team must confirm before relying on it.

---

## VERIFIED — official hackathon page and FAQ

- **Problem:** Using a supplied working repo and task interface, build ONE reusable strategy that generates realistic feature-development tasks. Each package: clear achievable requirements, a reference implementation, tests that verify the new feature while protecting existing functionality; packages identify their starting repo version and follow the supplied task interface.
- **Big question:** How can we automatically create realistic software-development tasks that are clear, solvable and reliably testable? The hard part is NOT writing descriptions with an LLM; it is making tasks solvable, consistent with the repo, meaningfully different, and reliably testable.
- **Stand out:** Prove each implementation meets its requirements; show tests catch missing or incorrect behaviour; vary behaviour, rules or interactions — not names; "meaningful variation beats a high task count."
- **Submit:** Reusable pipeline; sample task packages; validation evidence (tests, runs, results); runnable source with setup and run instructions; technical explanation (list reused open-source components and any manual steps); live demo that generates and validates a package. Never include API keys or secrets.
- **Format:** A command-line tool is enough; a focused, reliable prototype, not production-ready. No polished frontend. No special hardware. Any language.
- **Judging weights:**
  - 25% Working implementation and repeatability — runs end-to-end on the supplied repo; generalises beyond one hand-prepared example.
  - 25% Validity and evidence — tasks solvable, reference passes, feature tests detect missing/wrong behaviour, regression checks protect existing functionality.
  - 20% Meaningful variation — behaviour, rules, interactions; not wording.
  - 15% Original approach and engineering judgement — design choices, sensible scope, responsible resource use, honest limitations.
  - 15% Practical impact and communication — value for evaluating AI coding systems; demo clarity.
- **Timeline:** Build 10 Nov – 6 Dec; judging 7–15 Dec; finalists 14 Dec; Grand Finale 20 Dec, live pitch New Delhi.
- **Team:** 3–4 members. Organizer-provided Claude Code and model API access within usage limits (not yet issued as of 23 Nov 2026).

---

## VERIFIED — direct email, Klent Abistado, Hack2Skill (personal email reply)

- Hack2Skill will provide the repo link, task interface spec, and Claude Code credits after finalization. No date given.
- **We do NOT have to wait:** pick any repo to work on and swap in the official one later.
- **The task interface follows the Harbor format** (harborframework.com).

> Action: Confirm in writing with Hack2Skill to get official email/documentation.

---

## UNVERIFIED — AI summary of Q&A recording (team must confirm)

> All items below are unverified. Do NOT build assumptions on them until confirmed.
> Each is also listed in docs/OPEN_QUESTIONS.md.

1. Three candidate repos to choose from (not one fixed repo).
2. The factory must work across repos without hard-coding (consistent with our config.yaml approach).
3. Tasks may be feature implementations OR bug fixes (bug-fix as an optional extra axis).
4. Organizers' validation checks: (a) original repo works as-is; (b) tests pass after the implementation; (c) the feature test fails when the feature is removed.
5. Originality includes checkpointing (unclear what this means — ask organizers).
6. Reference code may be AI-generated.
7. Background context: SWE-bench, SWE-bench Verified, LiveCodeBench.

---

## What we're doing without the official repo

We have chosen two stand-in repos (see docs/DECISIONS.md) in different languages. All repo-specific details live in config.yaml. Swapping to the official repo is a config change + rerun. See PLAN.md for schedule.
