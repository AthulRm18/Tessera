# docs/ORGANIZER_BRIEF.md

Summary of everything we know from the organizers. **VERIFIED** = confirmed official source.
**UNCONFIRMED / OPEN QUESTIONS** = pending confirmation; tracked in `docs/OPEN_QUESTIONS.md`.

---

## Official PDF (VERIFIED) — Participant Guide & Technical Specifications (25 Nov 2026)

This official PDF supersedes all earlier assumptions and informal communications.

- **Three Designated Repositories Only:** Teams must choose **exactly one** of:
  1. `pallets/click` (Python, CLI toolkit, `pip install -e .` and `pytest`)
  2. `colinhacks/zod` (TypeScript/JavaScript, schema validation, `pnpm install && pnpm build`, `vitest`)
  3. `open-source-parsers/jsoncpp` (C++, JSON library, CMake and `ctest`)
  *Arbitrary repositories or projects built in Django, Flask, FastAPI, React, Java, or Kotlin are strictly NOT permitted.*
- **Target Selection:** Tessera chooses **`pallets/click`** as our target repository.
- **Task Volume & Variation:** Must produce **at least 5 distinct, substantively different tasks** from the chosen single repository. Tasks must differ in behaviour, rules, or interactions; simple rewording or renaming does not constitute variation.
- **Task Scope:** Features and behaviour changes **only**. Bug-fix tasks are strictly **OUT OF SCOPE**. Tasks cannot start from a modified repository. Generated features must **not exist upstream**.
- **Starting Commit:** Real, recent, stable commit (release tag ideal) where build and all existing tests pass. Full 40-character commit hash must be recorded in `task.toml` under `base_commit`.
- **Harbor Specification:** Strictly adheres to **Harbor framework version 0.25.x** (`pip install "harbor==0.25.*"`). Docker must be running.
- **Package Architecture (5 Core Components in each task folder):**
  1. `instruction.md`: Complete requirements document. This is the **ONLY** file visible to the evaluated AI coding system. Must declare all symbols, signatures, errors, and observable behaviour without leaking implementation hints.
  2. `solution/`: Reference implementation provided as a code patch.
  3. `tests/`: New feature tests, existing regression tests list, test runners, plus SWE-bench-style `tests/fail_to_pass.json` and `tests/pass_to_pass.json` (using exact test runner node IDs).
  4. `environment/`: Dockerfile that builds the repository starting at the recorded `base_commit`. Each task has its own `environment/Dockerfile` (identical Dockerfiles leverage Docker layer cache).
  5. `task.toml`: Task metadata including repo details, full 40-char `base_commit` hash, and licensing.
- **Official Validation & Scoring:**
  - Baseline (`nop`) check: `harbor run -p <task_dir> -a nop -k 1 -o <out_dir> --no-delete -y` $\rightarrow$ must yield reward **`0.0`** (feature tests fail, existing regression tests pass).
  - Oracle (`oracle`) check: `harbor run -p <task_dir> -a oracle -k 1 -o <out_dir> --no-delete -y` $\rightarrow$ must yield reward **`1.0`** (all feature and regression tests pass).
  - **Reward function:** If any regression test fails, reward = `0.0`. If all feature tests pass, reward = `1.0`. Otherwise, reward = share of passing feature tests. `null` indicates an environmental crash.
- **Hermetic & Secure:** No tests requiring external network access or real credentials. Security feature tasks that create or exploit vulnerabilities are out of scope.
- **Automated Reliability:** Judges execute submissions in a standardized Docker environment. Automated pipeline reliability takes precedence over manual output corrections.
- **Mutation Testing:** Strongly recommended by organizers to prove tests detect deliberately broken implementations.
- **Model & Tool Declaration:** Participants may use any coding agents or models for Track 1 pipelines, provided **ALL** tools and models (planner, generator, solver) are declared in `docs/MODELS.md` and technical documentation.
- **Submission Deliverables:**
  1. Runnable source code with setup and run instructions.
  2. Sample task packages (minimum 5 accepted tasks from `pallets/click`) tagged to commits.
  3. Validation evidence (logs, metrics, failure cases, documented manual fixes).
  4. Technical explanation (`docs/TECHNICAL_EXPLANATION.md`) covering design decisions, assumptions, reused components, model choices, and variation strategy.
  5. Walkthrough video demonstrating the pipeline end to end (including a real rejection).
  6. Submission deck following organizer template.
- **Finals & Team:** Teams of 1 to 4 individuals allowed (solo accepted). Finalist teams present live in New Delhi on 20 December 2026.

---

## Earlier Verified Items (Maintained)
- Klent Abistado (Hack2Skill email): Task interface is Harbor format.
- Timeline: Submission due 6 Dec 2026 (target submit 5 Dec).
