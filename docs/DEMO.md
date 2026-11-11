# DEMO.md — 5-minute live demo

Judging weight: 15% impact and communication, plus the demo must "generate and validate a package live". Rehearse this twice. Keep terminal font large.

## Pre-demo checklist
- [ ] Fresh terminal, venv active, `.env` loaded, network checked
- [ ] `factory profile` already run; baseline green
- [ ] Warm LLM cache for the demo plan (`factory demo --replay` works as backup)
- [ ] Sample packages and report open in a second window
- [ ] Battery, charger, screen sharing tested

## Script
**0:00 – 0:30 · The problem.**
"AI labs need coding tasks that are solvable and reliably testable. Generating a description is easy. Proving the task is valid is the hard part. We built a pipeline that generates tasks and only accepts those that pass automated proof."

**0:30 – 1:00 · Show the repo and the pipeline diagram** (one slide or `ARCHITECTURE.md` diagram). Name the gates in one sentence.

**1:00 – 3:30 · Live run.** `factory demo`
Narrate each stage as it prints:
- plan: which module and behaviour axis was chosen and why it differs from earlier tasks
- generate: requirements, reference patch, tests
- G2: tests fail on base, pass with reference
- G3/G4: no regressions, deterministic
- G6: mutation result, say the kill rate out loud
- G7: independent solver result
If a task is rejected live, say why. That demonstrates the gates are real.

**3:30 – 4:15 · Show evidence.** Open the package folder and `validation_report.json`. Show the distinctness matrix and the `factory report` numbers (real totals: planned, accepted, mean kill rate, solver pass rate).

**4:15 – 4:45 · Clean-room verify.** `factory verify packages/<id>` on a fresh checkout.

**4:45 – 5:00 · Impact and honesty.** "Solver pass rates give a difficulty signal for evaluating coding AIs. Limits: equivalent mutants and shared LLM blind spots. All in `LIMITATIONS.md`."

## Backup plan
1. Network fails: `factory demo --replay` (state clearly it is a replay of a real earlier run).
2. Live run stalls past 3 minutes: stop, show the last real run's package and report.
3. Never fake output.

## Likely questions (prepare answers from real data)
- How do you know tests aren't trivially passing? (G2 failure types, mutation kill rate)
- How are tasks different from each other? (behavioural matrix, coverage)
- Does it work beyond this repo? (config-only repo specifics; fixture repo result)
- What did you fix manually? (`MANUAL_STEPS.md`)
- What does it cost per task? (usage ledger)
- What would you do next? (`LIMITATIONS.md` future work)
