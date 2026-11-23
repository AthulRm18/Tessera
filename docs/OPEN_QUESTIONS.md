# OPEN_QUESTIONS.md

Resolve in Phase 0 and at the 19 Nov explainer. Mark each: **answered** (with source) or **unknown, need human**.

## Supplied materials
- [x] **What is the task interface?** ANSWERED: Harbor format (harborframework.com). Source: Klent Abistado email.
- [ ] What language, framework and size is the official supplied repo? How are dependencies installed? **unknown, need human (Hack2Skill)**
- [ ] What is the test command and how are per-test results exposed (JUnit XML, JSON, text)? **unknown, need human**
- [ ] Is the baseline test suite green on a clean checkout? Any slow or flaky tests? **unknown, need human**
- [ ] What are the submission formats? One file, a folder, an archive, a repo link? **unknown, need human**
- [ ] Which target models are named? Is solver testing against them expected or optional? **unknown, need human**

## Rules and limits
- [ ] Usage limits for the Claude Code subscription and model API (tokens, requests, rate limits)? **unknown — API not yet issued**
- [x] Is a minimum number of tasks expected, or is quality over count? ANSWERED: "meaningful variation beats a high task count." (official page)
- [ ] Are tasks required to be of a certain difficulty or size? **unknown, need human**
- [ ] Are there IP and licensing terms for what we build? Who owns the code after the event? **unknown, need human**
- [ ] Can the repo be modified in place, or must tasks be diffs only? **unknown, need human**
- [ ] Is a hidden test repo used to check generalisation? **unknown, need human**

## UNVERIFIED items (from Q&A recording — confirm before relying on)
- [ ] Are there three candidate repos to choose from? **unverified**
- [ ] Can tasks be bug-fix tasks (not only feature tasks)? **unverified**
- [ ] Organizers' validation checks: (a) original repo works as-is; (b) tests pass after implementation; (c) tests fail when feature removed — are these the exact three checks? **unverified**
- [ ] What does "originality includes checkpointing" mean exactly? **unverified**
- [ ] Background context is SWE-bench, SWE-bench Verified, LiveCodeBench — any formal connection/benchmark alignment required? **unverified**

## Logistics
- [ ] Is travel to New Delhi for the 20 Dec finale covered for finalists? **unknown, need human**
- [ ] How and where do we submit? Deadline time zone on 6 Dec? **unknown, need human**
- [ ] Is the demo expected to be live against the supplied repo? **unknown, need human**
- [ ] Is the track choice locked after registration? **unknown, need human**

## Team
- [ ] Team of 3–4 confirmed? Roles assigned? **in progress — see PLAN.md**
- [ ] Everyone has API access and working dev environment? **API not yet issued**

## Answers log
| Question | Answer | Source / person | Date |
|---|---|---|---|
| Task interface format | Harbor (harborframework.com) | Klent Abistado, Hack2Skill (email) | Before 23 Nov 2026 |
| Must we wait for official repo? | No — pick any repo; swap later | Klent Abistado, Hack2Skill (email) | Before 23 Nov 2026 |
| Quality vs count | Quality wins ("meaningful variation beats high task count") | Official hackathon page | 10 Nov 2026 |
