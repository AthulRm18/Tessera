# OPEN_QUESTIONS.md

Status of questions against official organizer communications. Updated: 25 Nov 2026.

## Official Confirmations from PDF (Resolved)
- [x] **Which repositories are permitted?** Confirmed: Exactly three allowed (`pallets/click`, `colinhacks/zod`, `open-source-parsers/jsoncpp`). Arbitrary repos not permitted.
- [x] **Task type scope?** Confirmed: Features and behaviour changes ONLY. Bug fixes are strictly OUT OF SCOPE.
- [x] **Can tasks start from a modified repo?** Confirmed: NO. Every task starts from a real commit of the chosen repository where all tests pass.
- [x] **Harbor version?** Confirmed: Harbor 0.25.x (`pip install "harbor==0.25.*"`).
- [x] **Task package structure?** Confirmed: 5 core components per task folder: `instruction.md`, `solution/`, `tests/` (with `fail_to_pass.json` and `pass_to_pass.json`), `environment/Dockerfile`, `task.toml`.
- [x] **Official validation commands?** Confirmed: `harbor run -p <task_dir> -a nop -k 1 -o <out_dir> --no-delete -y` (reward 0.0) and `harbor run -p <task_dir> -a oracle -k 1 -o <out_dir> --no-delete -y` (reward 1.0).
- [x] **Required task count?** Confirmed: Minimum 5 distinct, substantively different tasks from a single repository.

---

## UNCONFIRMED / Pending Questions (Tracked for Organizers)

1. **Pipeline Execution vs Package Evaluation:**
   - *Question:* Will the judges re-run the entire task-generation pipeline from scratch, or will they only run `harbor run` on the committed sample task packages in `samples/`?
   - *Impact on Tessera:* We ensure BOTH paths work seamlessly: the pipeline generates tasks reproducibly via CLI, and every sample task package in `samples/` runs independently via Harbor 0.25.x.

2. **Standardized Docker Environment Definition:**
   - *Question:* What does the "standardized Docker environment" used by judges entail (e.g. OS base image, resource limits, Docker daemon configuration, host architecture x86_64)?
   - *Impact on Tessera:* All `environment/Dockerfile` definitions will be self-contained on standard Debian/Ubuntu multi-arch with pinned dependencies.

3. **Criteria Weights Discrepancy:**
   - *Question:* The official hackathon FAQ previously listed 5 weighted criteria (25% Implementation, 25% Validity, 20% Variation, 15% Engineering Judgement, 15% Impact/Communication). The new PDF lists 3 primary categories: (1) Implementation & Repeatability, (2) Validity & Validation Evidence, (3) Task Quality & Novelty. What are the official percentage weights?
   - *Impact on Tessera:* Satisfy both frameworks by maintaining rigor across implementation, proof/validity, and variation.

4. **Team Size Conflict:**
   - *Question:* The original FAQ stated teams must be 3–4 members (solo not accepted). The new PDF states "Teams of 1 to 4 individuals are allowed, and solo participants are accepted." Which rule governs final eligibility?
   - *Impact on Tessera:* Our team structure complies with both (1–4 members).

5. **Organizer Credit Availability:**
   - *Question:* Will Claude Code or model API access credits be issued before submission, or should teams rely entirely on their own API keys?
   - *Impact on Tessera:* We use our own environment-variable driven LLM providers (Gemini/Claude) with strict budget guards.

6. **Video & Deck Specifics:**
   - *Question:* Are there strict length limits on the walkthrough video (e.g., max 5 minutes)? Is the submission deck restricted to a specific slide count in the organizer template?
   - *Impact on Tessera:* Target a concise 5-minute screencast and tight slide deck mapped directly to the criteria.
