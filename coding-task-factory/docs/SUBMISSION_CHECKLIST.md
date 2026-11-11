# SUBMISSION_CHECKLIST.md

Tick only with evidence (command output, file path). Aim to submit by **5 Dec**; deadline is **6 Dec 2026**.

## Working implementation (25%)
- [ ] Fresh clone + README quickstart works on a clean machine
- [ ] `factory run -n N` completes on the supplied repo
- [ ] Pipeline contains no repo-specific hard-coding (repo details only in `config.yaml`)
- [ ] Second fixture repo (stretch) runs, or limitation documented

## Validity evidence (25%)
- [ ] Every accepted task has `validation_report.json` with G1–G6 passed and G7 recorded
- [ ] `factory verify` passes for every accepted package from a clean checkout
- [ ] Mutation kill rates and survivors reported honestly
- [ ] Rejected tasks and reasons included in the report

## Variation (20%)
- [ ] Distinctness matrix generated; no overlapping accepted pairs
- [ ] Coverage table by module and behaviour axis in the report

## Engineering judgement (15%)
- [ ] `DECISIONS.md` current
- [ ] `LIMITATIONS.md` honest and matches observed behaviour
- [ ] Usage ledger shows tokens and estimated cost
- [ ] Reused open-source components listed in `README.md`

## Impact and communication (15%)
- [ ] `DEMO.md` rehearsed twice; `demo` and `demo --replay` both work
- [ ] Technical explanation written and readable in 5 minutes
- [ ] Sample packages in `samples/` are real and inspectable

## Format and rules
- [ ] Package format matches the supplied interface, checked line by line against the spec
- [ ] Submission format followed exactly
- [ ] No API keys or secrets in repo or git history (scan output saved)
- [ ] `MANUAL_STEPS.md` complete
- [ ] Pipeline's own `pytest` suite passes
- [ ] No dead code, no TODO placeholders, type hints present
- [ ] Every number in the docs traces to a real run id

## Submit
- [ ] Final commit tagged `submission`
- [ ] Submitted via the official channel; confirmation saved
- [ ] Finale prep: pitch slides (optional), demo environment tested, travel confirmed
