# SUBMISSION_CHECKLIST.md

Tick only with verifiable evidence (command output, file path, run id).
Aim to submit by **5 Dec 2026**; hard deadline is **6 Dec 2026**.

---

## 1. Implementation & Repeatability
- [ ] Pipeline runs end-to-end on `pallets/click` via `tessera run -n 5 --config configs/click.yaml`
- [ ] Clean repository: no hard-coded paths or repo names in core code (repo details strictly in `configs/click.yaml`)
- [ ] Automated pipeline reliability demonstrated (runs without manual fixes)
- [ ] Fresh-machine clone and README quickstart passes on clean Linux / WSL2 environment

---

## 2. Validity & Validation Evidence
- [ ] Minimum 5 distinct accepted task packages from `pallets/click` in `samples/`
- [ ] Every package passes official Harbor 0.25.x validation inside Docker:
  - `harbor run -p <pkg> -a nop -k 1 -o <out> --no-delete -y` $\rightarrow$ Reward **0.0**
  - `harbor run -p <pkg> -a oracle -k 1 -o <out> --no-delete -y` $\rightarrow$ Reward **1.0**
- [ ] Every task package contains:
  - `instruction.md` (zero patch/solution leakage; complete interface specification)
  - `solution/solve.sh` and `solution/reference.patch`
  - `tests/` with feature tests, test runners, `fail_to_pass.json`, and `pass_to_pass.json`
  - `environment/Dockerfile` building repo starting at full 40-char `base_commit`
  - `task.toml` (Harbor schema_version = "1.4", repo details, base_commit)
- [ ] Hermetic tests: zero external network calls or real credentials required at test time
- [ ] Gates G1–G7 evidence saved in `validation_report.json` for each package
- [ ] Mutation testing (G6) kill rates reported for all accepted tasks
- [ ] All failure cases and rejected tasks documented honestly in run logs
- [ ] `MANUAL_STEPS.md` is empty / zero manual edits required

---

## 3. Task Quality & Novelty
- [ ] Tasks represent genuine feature additions / behaviour changes (bug fixes strictly excluded)
- [ ] Upstream-novelty verified: feature tests run and fail against Click default branch without patch
- [ ] Meaningful variation: at least 5 tasks substantively differing in behaviour, rules, or interactions
- [ ] Behavioural distinctness matrix generated proving non-overlapping test coverage

---

## 4. Documentation & Declarations
- [ ] `docs/MODELS.md` declares all tools, agents, and models used across planner, generator, and solver
- [ ] `docs/TECHNICAL_EXPLANATION.md` covers design decisions, assumptions, reused components, and variation strategy
- [ ] Walkthrough demo video (5-minute end-to-end screencast including a real rejection)
- [ ] Submission slide deck completed following organizer template
- [ ] `DECISIONS.md` and `OPEN_QUESTIONS.md` up to date

---

## 5. Security & Hygiene Scan
- [ ] Secret scan passes: zero API keys, secrets, or credentials in working tree or git history
- [ ] `.gitignore` covers `.env`, worktrees, local caches, and temporary runs
- [ ] Git commit tagged `submission`
- [ ] Submission delivered and confirmed through official hackathon portal
