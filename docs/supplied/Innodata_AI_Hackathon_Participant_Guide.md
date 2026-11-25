# Innodata AI Hackathon — Participant Guide & Technical Specifications

**Source:** Official Organizer PDF (`Innodata AI Hackathon - Participant Submission Process and Guidelines`), saved 25 Nov 2026.

---

## Track Architectures & Core Objectives

### Track 1: Coding Task Factory
- **Objective:** Participants must build an automated task factory pipeline rather than hand-crafting individual tasks. The pipeline reads a supplied software repository and continuously produces realistic feature-development task packages.
- **Task Scope:** Tasks must represent new feature-development tasks or changes to existing behaviour. Bug-fix tasks are out of scope, and tasks cannot start from a modified repository. Every task starts from a real commit of the chosen repository where all existing tests pass.
- **Pipeline Input:** The pipeline runs on a local clone of one of the three public starting repositories checked out at a chosen starting commit.
- **Task Variation Strategy:** The factory must produce 5 distinct, substantively different tasks from a single repository. Tasks must differ in behaviour, rules, or interactions; simple rewording or renaming does not constitute variation.

---

## Track 1 Starter Repositories & Execution Environments

Participants choose **exactly one of three public open-source GitHub repositories** as their foundation. Arbitrary repositories or projects built in Django, Flask, FastAPI, React, Java, or Kotlin are not permitted.

1. **`pallets/click`**
   - Language: Python
   - Core Domain: Toolkit for command-line interfaces
   - Test Runner: `pytest`
   - Development Commands: `pip install -e .` and `pytest`
2. **`colinhacks/zod`**
   - Language: JavaScript / TypeScript
   - Core Domain: Schema-validation library
   - Test Runner: `vitest`
   - Development Commands: Node.js, `pnpm install && pnpm build`, and `vitest`
3. **`open-source-parsers/jsoncpp`**
   - Language: C++
   - Core Domain: JSON library
   - Test Runner: CMake and `ctest`
   - Development Commands: C++ compiler, CMake, and `ctest`

---

## Commit Selection & Pipeline Language

- **Starting Commit:** Teams select a real, recent, stable commit (a release tag is ideal). The repository must build and pass its existing test suite at this commit. The full 40-character commit hash must be recorded in `task.toml` under `base_commit`. Generated features must not exist upstream.
- **Pipeline Implementation:** The pipeline itself can be written in any programming language (Python is suggested). However, every generated task must run using the chosen repository's own language, dependencies, and test runner.

---

## Task Package Specification & Harbor Interface

Track 1 tasks strictly adhere to the Harbor framework (version 0.25.x). Harbor is installed via `pip install "harbor==0.25.*"`.

### Local Environment Requirements
- **Docker:** Must be running. Harbor builds every task environment and executes all tests inside Docker containers.
- **Harbor CLI:** Version 0.25.x available on PATH.
- **Git:** Installed to clone target repositories and generate patches.
- **Model API Access:** Maintained within event usage limits with keys kept in environment variables.

### Task Package Directory Structure
Each task is contained in a single folder containing five core components:
1. `instruction.md`: The complete requirement document; this is the only file visible to the AI coding system being evaluated.
2. `solution/`: The reference implementation provided as a code patch.
3. `tests/`: Contains new feature tests, list of existing regression tests, and test runners. Includes SWE-bench-style `tests/fail_to_pass.json` and `tests/pass_to_pass.json` files.
4. `environment/`: A Dockerfile that builds the repository starting at the recorded commit.
5. `task.toml`: Task metadata including repository details, base commit hash, and licensing.

---

## Validation Matrix & Automated Grading

Harbor evaluates submission task packages inside isolated Docker containers by executing two standard validation passes:
- **Baseline (nop) Check:**
  `harbor run -p <task_dir> -a nop -k 1 -o <out_dir> --no-delete -y`
  Leaves the repository untouched. Expected reward is `0.0` (feature tests fail, existing regression tests pass).
- **Oracle (oracle) Check:**
  `harbor run -p <task_dir> -a oracle -k 1 -o <out_dir> --no-delete -y`
  Applies the reference implementation. Expected reward is `1.0` (all feature and regression tests pass).

**Reward values:**
- If any regression test fails, reward is `0.0`.
- If all feature tests pass, reward is `1.0`.
- Otherwise, reward reflects the share of passing feature tests.
- A `null` reward indicates an environmental crash.

---

## Submission Deliverables & Evaluation Criteria

Both tracks must submit a complete project package consisting of five key components:
1. **Runnable Source Code:** Clean repository containing complete setup and execution instructions.
2. **Sample Outputs:** Inspectable task packages tagged to starting commits for Track 1 (minimum 5 accepted tasks from chosen repo).
3. **Validation Evidence:** Test logs, execution metrics, failure cases, and documented manual fixes. Mutation testing (proving tests detect deliberately broken implementations) is strongly recommended.
4. **Technical Explanation:** Document detailing design decisions, core assumptions, reused components, model choices, and task variation strategies.
5. **Walkthrough Demo:** A video demonstration showing the pipeline operating end-to-end.

### Judging Criteria
- **Implementation & Repeatability:** Judges will execute submissions in a standardized Docker environment. Automated pipeline reliability takes precedence over manual output corrections.
- **Validity & Validation Evidence:** Measured by strict adherence to the validation matrix and test suite integrity.
- **Task Quality & Novelty:** Evaluation of feature realisticness, requirement clarity, and meaningful task variation.

---

## Administrative Rules & Security Scope

- **Team Structure:** Teams of 1 to 4 individuals are allowed, and solo participants are accepted.
- **Security Feature Scope:** Security-related features are permitted if they represent standard feature development. Out of scope: tasks that create or exploit vulnerabilities, malicious code, or tests requiring external network access or real credentials.
- **Model & Tool Usage:** Participants may use any coding agents or models for Track 1 pipelines, provided all tools and models are declared in the technical documentation.
- **Finalist Presentation:** Finalist teams will present live on December 20.
