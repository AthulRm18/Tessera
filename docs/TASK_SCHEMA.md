# TASK_SCHEMA.md — Harbor Task Format (v0.25.x)

> **Official Task Interface:** Track 1 strictly adheres to the Harbor framework (version 0.25.x).
> Source: Official PDF "Innodata AI Hackathon - Participant Guide & Technical Specifications" (25 Nov 2026).
> Harbor CLI installation: `pip install "harbor==0.25.*"`.

---

## Harbor Task Directory Layout

Each generated task package is contained in a single self-contained directory:

```
packages/<task_id>/
├── instruction.md          # Complete requirement document; ONLY file visible to the evaluated AI
├── task.toml               # Task metadata (schema_version = "1.4", repo details, base_commit)
├── environment/
│   └── Dockerfile          # Builds the repo starting at base_commit (runs baseline tests)
├── solution/
│   ├── solve.sh            # Reference solution apply script
│   └── reference.patch     # Clean unified diff patch
└── tests/
    ├── test.sh             # Test runner executing tests inside container; emits reward
    ├── test_feature.py     # Feature test file asserting acceptance criteria
    ├── fail_to_pass.json   # SWE-bench style array of test IDs failing on base, passing on reference
    └── pass_to_pass.json   # SWE-bench style array of existing tests passing on both
```

Alongside each package, Tessera maintains internal verification evidence:
```
packages/<task_id>/
└── tessera/
    ├── task_metadata.json      # Structured task metadata (module, axis, criteria, interface)
    └── validation_report.json  # Comprehensive evidence across Gates G1–G7
```

---

## 1. `instruction.md`

The **ONLY** file exposed to the agent under evaluation. Must be clear, unambiguous, and solvable.
Strict content rules:
- **Title and Problem Description**: What feature or behavioural change is required and why.
- **Numbered Acceptance Criteria**: `AC1`, `AC2`, `AC3`, ...
- **Interface Specification**: Exact symbols, signatures, parameter types, return types, and exception classes the test suite asserts against.
- **Out of Scope**: Explicit boundaries to prevent unintended side effects.
- **Zero Implementation Hints**: No code snippets for the solution, no internal private details, no patch leakage.

---

## 2. `task.toml` (Harbor 0.25.x / schema_version "1.4")

```toml
schema_version = "1.4"

[task]
name = "tessera/<task_id>"
description = "<task summary>"
authors = [
  { name = "Tessera Factory", email = "tessera@frontier-ai.org" }
]

[metadata]
category = "software-engineering"
difficulty_explanation = "Generated and verified by Tessera Coding Task Factory."
tags = ["python", "cli", "pallets/click", "feature"]
repository = "https://github.com/pallets/click"
base_commit = "<full 40-character commit hash>"

[verifier]
timeout_sec = 300.0
environment_mode = "shared"

[agent]
timeout_sec = 300.0

[environment]
# Default for Harbor 0.25.x DockerEnvironment (unless egress sidecar enabled); all tests are offline-safe
network_mode = "public"
build_timeout_sec = 600.0
```

---

## 3. `environment/Dockerfile`

Every task has its own `environment/Dockerfile` that builds the target repository from scratch starting at `base_commit`. Identical Dockerfiles across tasks from the same repo base commit share Docker layer cache automatically.

```dockerfile
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    less \
    && rm -rf /var/lib/apt/lists/*

# Clone repository and checkout exact base_commit
RUN git clone https://github.com/pallets/click.git /app && \
    git checkout cf19179e8e2fd54c601378cec9e0d21bb12b6fb1

# Install dependencies and package in editable mode
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir pytest
```

---

## 4. `solution/solve.sh`

Applies the reference implementation patch cleanly to the container's `/app` workspace:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_FILE="$SCRIPT_DIR/reference.patch"

if [ -f "$PATCH_FILE" ]; then
    echo "Applying reference implementation patch..."
    git apply "$PATCH_FILE" || patch -p1 < "$PATCH_FILE"
    echo "Reference patch applied successfully."
else
    echo "Error: Patch file $PATCH_FILE not found." >&2
    exit 1
fi
```

---

## 5. `tests/` Structure

- `test.sh`: The test execution script run by Harbor verifier. Runs both the feature test and regression suite, and outputs the numeric reward to `/logs/verifier/reward.txt`.
- `tests/fail_to_pass.json`: Array of test IDs (e.g. `["tests/test_feature.py::test_new_param_validation"]`) that FAIL on the unpatched base repo and PASS with the reference solution.
- `tests/pass_to_pass.json`: Array of baseline regression test IDs that PASS both before and after the solution.

---

## Validation Matrix Verification

Every task package must pass both official passes:
1. **Nop check:** `harbor run -p <task_dir> -a nop -k 1 -o <out_dir> --no-delete -y` $\rightarrow$ Reward `0.0`.
2. **Oracle check:** `harbor run -p <task_dir> -a oracle -k 1 -o <out_dir> --no-delete -y` $\rightarrow$ Reward `1.0`.
