# REQUIREMENTS.md

**Source:** Official Hackathon Guide (`Innodata AI Hackathon - Participant Guide & Technical Specifications`, 25 Nov 2026). Supersedes all earlier assumptions.

---

## 1. Problem Statement
Build **one automated, reusable task factory pipeline** (`Tessera`) that reads a single public software repository and continuously produces realistic, validated feature-development task packages formatted for the **Harbor framework (v0.25.x)**.

### Target Repository
Participants choose exactly one of three designated open-source repositories:
- **Selected Target:** **`pallets/click`** (Python CLI toolkit, `pip install -e .`, `pytest`)
- *Alternative allowed options:* `colinhacks/zod` (TypeScript), `open-source-parsers/jsoncpp` (C++)
- *Arbitrary repositories (e.g. Django, Flask, FastAPI, React, Java, Kotlin) are strictly forbidden.*

### Task Scope
- **Features & Behaviour Changes Only:** Tasks must represent new feature-development tasks or changes to existing behaviour. **Bug-fix tasks are strictly out of scope.**
- **Starting Point:** Every task must start from a real, recent, stable commit of the chosen repository (release tag ideal) where all existing tests pass cleanly. Tasks cannot start from a modified repository.
- **Upstream Novelty:** Generated features must **not already exist upstream**.

---

## 2. Deliverables & Core Objectives
1. **Automated Pipeline:** Fully reproducible Python CLI (`tessera`) generating packages end-to-end.
2. **At Least 5 Accepted Tasks:** Distinct, substantively different tasks from `pallets/click` differing in behaviour, rules, or interactions (not mere rewording).
3. **Harbor 0.25.x Package Format:** Each package contains `instruction.md`, `solution/`, `tests/` (with `fail_to_pass.json` and `pass_to_pass.json`), `environment/Dockerfile`, and `task.toml`.
4. **Validation Proof:** Every task must demonstrably achieve:
   - `harbor run -p <task_dir> -a nop -k 1 -o <out_dir> --no-delete -y` $\rightarrow$ Reward **0.0**
   - `harbor run -p <task_dir> -a oracle -k 1 -o <out_dir> --no-delete -y` $\rightarrow$ Reward **1.0**
   - Mutation testing kill rate evidence proving feature tests detect broken implementations.
5. **Technical Explanation & Video Demo:** `docs/TECHNICAL_EXPLANATION.md` detailing design, model choices (`docs/MODELS.md`), variation strategy, and a 5-minute end-to-end video.

---

## 3. Evaluation Criteria
1. **Implementation & Repeatability:** Pipeline runs reliably without manual intervention; standardized Docker evaluation by judges.
2. **Validity & Validation Evidence:** Strict adherence to validation matrix (nop 0.0, oracle 1.0), mutation kill rates, test suite integrity.
3. **Task Quality & Novelty:** Realistic features, clear requirements in `instruction.md`, verified upstream novelty, and substantive behavioural variation.

---

## 4. Key Deadlines
- **Build Window:** 10 Nov – 6 Dec 2026
- **Target Submission:** **5 Dec 2026**
- **Hard Deadline:** **6 Dec 2026**
- **Finalists Announced:** 14 Dec 2026
- **Grand Finale (Live Pitch):** 20 Dec 2026 in New Delhi
