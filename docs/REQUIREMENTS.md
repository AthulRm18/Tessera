# REQUIREMENTS.md

Source: the hackathon page and Track 1 description. The **supplied spec** (shared after registration) overrides this file wherever they differ.

## Problem statement
Using a supplied repository and task interface, build **one reusable strategy** that generates feature-development tasks. Each task has:
1. clear, achievable requirements for a new feature,
2. a reference implementation that runs in the repo's stack,
3. feature tests plus regression checks for existing code,
4. a tag to its starting repo version.

Example: a shopping-cart app gets a generated task to add discount codes with eligibility rules and spending thresholds, plus tests that prove it works.

**The big question:** how can we automatically create realistic software-development tasks that are clear, solvable and reliably testable?

**The hard part (per organisers' SME review)** is not generating descriptions with an LLM. It is making tasks:
- solvable,
- consistent with the repository,
- meaningfully different from each other,
- reliably testable.

## Judging criteria (indicative weights)
| # | Criterion | Weight | What the jury looks for | Our evidence |
|---|---|---|---|---|
| 1 | Working implementation and repeatability | 25% | Pipeline runs end to end on the supplied repo; generalises beyond one hand-prepared example | `factory run`, clean-room `verify`, multiple accepted tasks, second fixture repo (stretch) |
| 2 | Validity and validation evidence | 25% | Tasks solvable; reference passes; feature tests detect missing or wrong behaviour; regression checks protect existing functionality | Gates G1–G7, per-task validation reports, mutation kill rates, solver results |
| 3 | Meaningful variation | 20% | Tasks differ in behaviour, rules or interactions, not wording or names | Behavioural distinctness matrix, coverage grid report |
| 4 | Original approach and engineering judgement | 15% | Design choices, sensible scope, responsible resource use, honest limitations | `DECISIONS.md`, usage ledger, `LIMITATIONS.md` |
| 5 | Practical impact and communication | 15% | Value for evaluating AI coding systems; clarity of demo | Solver pass rates as difficulty signal, `DEMO.md` |

Rule of thumb: half the score is "does it work and can you prove tasks are valid". Spend time accordingly.

## What to submit
- Runnable source code with setup and run instructions
- Sample task packages judges can inspect
- Validation evidence: tests, runs, results
- Technical explanation (including reused components and any manual steps)
- A live demo that generates and validates a package

## Constraints and rules
- One team, one track, one reusable pipeline for that track.
- Team size 3–4. Solo not accepted. Age 18+.
- Any programming language. Python is our choice for the pipeline.
- Organiser-provided Claude Code subscription and model API access, within usage limits.
- Open-source libraries and existing tools are allowed; state what was reused.
- Never include API keys, passwords or secrets in the submission.
- Manual fixes to generated outputs are allowed but must be recorded transparently.
- No polished UI needed: a command-line tool or lightweight app is enough. A focused, reliable prototype is expected, not a production product.
- No special hardware; a standard development machine is enough.
- Repository, target models, detailed rules, interface specification and submission formats are shared with registered participants.

## Timeline
Build 10 Nov – 6 Dec · Judging 7–15 Dec · Finalists 14 Dec · Finale 20 Dec in New Delhi (in person, live pitch).

## Interpretation notes (our decisions)
- "Task interface": we treat it as the fixed format our packages must fit. We adapt to it, never redefine it.
- "Reusable strategy": one pipeline with repo specifics isolated in `config.yaml`.
- "Meaningfully different": judged behaviourally (tests of one task against the patch of another), not by text similarity.
- "Tagged to starting repo version": every package records the exact base commit hash and tag.
