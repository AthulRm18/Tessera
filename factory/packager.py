"""Harbor format packager (v0.25.x compliant).

Emits standard Harbor task directories:
  packages/<task_id>/
  ├── instruction.md         # ONLY file exposed to the evaluated AI
  ├── task.toml              # Harbor task configuration (schema_version = "1.4")
  ├── environment/           # Self-contained Dockerfile building from base_commit
  │   └── Dockerfile
  ├── solution/              # Reference solution
  │   ├── solve.sh           # Executable script applying reference.patch cleanly
  │   └── reference.patch    # Unified diff patch
  ├── tests/                 # Verifier scripts and SWE-bench JSON test splits
  │   ├── test.sh            # Verifier script outputting reward to /logs/verifier/reward.txt
  │   ├── grade.py           # Exact reward calculator (fail_to_pass + pass_to_pass)
  │   ├── fail_to_pass.json  # Feature test node IDs (must FAIL on base, PASS on oracle)
  │   ├── pass_to_pass.json  # Regression test node IDs (must PASS on base & oracle)
  │   └── feature/           # Feature test files
  └── tessera/               # Internal Tessera evidence (judges/evaluators)
      ├── task_metadata.json
      └── validation_report.json
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from factory.schemas import TaskMetadata, ValidationReport

console = Console()

HARBOR_SCHEMA_VERSION = "1.4"


DEFAULT_CLICK_DOCKERFILE = """FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    build-essential \\
    less \\
    && rm -rf /var/lib/apt/lists/*

RUN git clone {repository} /app && \\
    git checkout {base_commit}

RUN pip install --no-cache-dir -e . && \\
    pip install --no-cache-dir pytest
"""


def generate_task_toml(
    task_id: str,
    title: str,
    description: str = "",
    docker_image: str = "",
    timeout_sec: float = 300.0,
    repository: str = "https://github.com/pallets/click",
    base_commit: str = "",
    license_name: str = "BSD-3-Clause",
) -> str:
    """Generate task.toml content matching Harbor 0.25.x schema_version 1.4."""
    desc = (description or title).replace('"', '\\"').replace("\n", " ").strip()
    task_name = task_id if "/" in task_id else f"tessera/{task_id}"
    lines = [
        f'schema_version = "{HARBOR_SCHEMA_VERSION}"',
        "",
        "[task]",
        f'name = "{task_name}"',
        f'description = "{desc}"',
        "authors = [",
        '  { name = "Tessera Factory", email = "tessera@frontier-ai.org" }',
        "]",
        "",
        "[metadata]",
        'category = "software-engineering"',
        f'difficulty_explanation = "{desc}"',
        'tags = ["python", "cli", "pallets/click", "feature"]',
        f'repository = "{repository}"',
        f'base_commit = "{base_commit}"',
        f'license = "{license_name}"',
        "",
        "[verifier]",
        f"timeout_sec = {timeout_sec}",
        'environment_mode = "shared"',
        "",
        "[agent]",
        f"timeout_sec = {timeout_sec}",
        "",
        "[environment]",
        'network_mode = "public"',
        "build_timeout_sec = 600.0",
    ]
    if docker_image:
        lines.append(f'docker_image = "{docker_image}"')

    return "\n".join(lines) + "\n"


def generate_grade_py() -> str:
    """Generate tests/grade.py evaluating feature and regression tests per Harbor reward contract."""
    return '''#!/usr/bin/env python3
"""Exact verifier grading script for Harbor 0.25.x.

Grading rules (Official Hackathon PDF):
- If ANY regression test in pass_to_pass.json fails or errors -> reward = 0.0
- Else if ALL feature tests in fail_to_pass.json pass -> reward = 1.0
- Else -> reward = passed_feature / total_feature (share of passing feature tests)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class OutcomeCollector:
    """Collect exact per-nodeid outcomes during pytest execution."""

    def __init__(self, prefix_to_prepend: str = "") -> None:
        self.outcomes: dict[str, str] = {}
        self.prefix_to_prepend = prefix_to_prepend

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" or (report.when == "setup" and report.failed):
            nid = report.nodeid
            if nid.startswith("/tests/"):
                nid = "tests/" + nid[len("/tests/"):]
            elif self.prefix_to_prepend and not nid.startswith(self.prefix_to_prepend):
                nid = self.prefix_to_prepend + nid
            self.outcomes[nid] = report.outcome


def main() -> int:
    import os

    tests_dir = Path("/tests")
    verifier_dir = Path("/logs/verifier")
    verifier_dir.mkdir(parents=True, exist_ok=True)

    f2p_file = tests_dir / "fail_to_pass.json"
    p2p_file = tests_dir / "pass_to_pass.json"
    fail_to_pass: list[str] = json.loads(f2p_file.read_text(encoding="utf-8")) if f2p_file.exists() else []
    pass_to_pass: list[str] = json.loads(p2p_file.read_text(encoding="utf-8")) if p2p_file.exists() else []

    # 1. Run feature tests with --rootdir=/tests so node IDs preserve feature/<file>::<test>
    feature_dir = tests_dir / "feature"
    f2p_collector = OutcomeCollector(prefix_to_prepend="tests/")
    feature_targets = sorted(str(p) for p in feature_dir.glob("test_*.py"))
    if feature_targets:
        os.chdir("/tests")
        try:
            pytest.main(
                [*feature_targets, "-v", "--tb=short", "--no-header", "--rootdir=/tests", "--import-mode=importlib"],
                plugins=[f2p_collector],
            )
        finally:
            os.chdir("/app")

    # 2. Run upstream regression suite from /app
    p2p_collector = OutcomeCollector()
    if pass_to_pass:
        os.chdir("/app")
        pytest.main(["-q", "--tb=short", "--no-header"], plugins=[p2p_collector])

    # Evaluate regression gate
    reg_failures = [
        nid for nid in pass_to_pass
        if p2p_collector.outcomes.get(nid) != "passed"
    ]

    # Evaluate feature gate
    if fail_to_pass:
        f2p_passed = [
            nid for nid in fail_to_pass
            if f2p_collector.outcomes.get(nid) == "passed"
        ]
        f2p_total = len(fail_to_pass)
    else:
        f2p_passed = [nid for nid, out in f2p_collector.outcomes.items() if out == "passed"]
        f2p_total = len(f2p_collector.outcomes)

    if reg_failures:
        reward = 0.0
    elif f2p_total > 0 and len(f2p_passed) == f2p_total:
        reward = 1.0
    elif f2p_total > 0:
        reward = round(len(f2p_passed) / f2p_total, 4)
    else:
        reward = 0.0

    (verifier_dir / "reward.txt").write_text(f"{reward}\\n", encoding="utf-8")
    summary = {
        "reward": reward,
        "fail_to_pass_passed": len(f2p_passed),
        "fail_to_pass_total": f2p_total,
        "pass_to_pass_total": len(pass_to_pass),
        "regression_failures_count": len(reg_failures),
        "regression_failures_sample": reg_failures[:10],
        "feature_outcomes": f2p_collector.outcomes,
    }
    (verifier_dir / "grading_summary.json").write_text(json.dumps(summary, indent=2) + "\\n", encoding="utf-8")
    print(f"VERIFIER GRADING: reward={reward} (feature={len(f2p_passed)}/{f2p_total}, regressions_failed={len(reg_failures)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def generate_test_sh(test_cmd: str, use_grade_py: bool = False) -> str:
    """Generate tests/test.sh verifier script following the Harbor reward contract."""
    if use_grade_py:
        return """#!/bin/bash
# Verifier script generated by Tessera for Harbor 0.25.x
set -o pipefail
mkdir -p /logs/verifier

export PYTHONPATH=/app:${PYTHONPATH:-}
python /tests/grade.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ] && [ ! -f /logs/verifier/reward.txt ]; then
    echo "0.0" > /logs/verifier/reward.txt
fi
exit $EXIT_CODE
"""

    return f"""#!/bin/bash
# Verifier script generated by Tessera for Harbor
# Evaluates task completion and outputs reward (1 for pass, 0 for fail)

set -o pipefail
mkdir -p /logs/verifier

echo "Running verifier test suite..."
{test_cmd}
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "1" > /logs/verifier/reward.txt
    echo "VERIFIER: PASS (reward 1)"
else
    echo "0" > /logs/verifier/reward.txt
    echo "VERIFIER: FAIL (reward 0, exit code $EXIT_CODE)"
fi

exit $EXIT_CODE
"""


def generate_solve_sh(patch_filename: str = "reference.patch") -> str:
    """Generate solution/solve.sh oracle reference script."""
    return f"""#!/bin/bash
# Oracle reference solution generated by Tessera for Harbor
set -e

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PATCH_FILE="$SCRIPT_DIR/{patch_filename}"

if [ -f "$PATCH_FILE" ]; then
    echo "Applying reference patch..."
    if git apply "$PATCH_FILE" 2>/dev/null; then
        echo "Reference patch applied successfully with git apply."
    elif patch -p1 < "$PATCH_FILE"; then
        echo "Reference patch applied successfully with patch."
    else
        echo "Error: Failed to apply reference patch." >&2
        exit 1
    fi
else
    echo "Error: Patch file $PATCH_FILE not found." >&2
    exit 1
fi
"""


def package_task(
    task_id: str,
    output_dir: str | Path,
    requirements_md: str,
    patch_path: str | Path,
    feature_test_paths: list[str | Path],
    metadata: TaskMetadata,
    validation_report: ValidationReport,
    test_cmd: str,
    docker_image: str = "",
    timeout_sec: float = 300.0,
    dockerfile_content: str | None = None,
    repository_url: str = "https://github.com/pallets/click",
    license_name: str = "BSD-3-Clause",
    fail_to_pass: list[str] | None = None,
    pass_to_pass: list[str] | None = None,
) -> Path:
    """Package an accepted task into a standard Harbor 0.25.x task directory.

    Returns the path to the packaged directory.
    """
    pkg_dir = Path(output_dir) / task_id
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # 1. instruction.md (ONLY file exposed to evaluated agent) - LF normalized
    with open(pkg_dir / "instruction.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(requirements_md.replace("\r\n", "\n"))

    # 2. task.toml (Harbor configuration) - LF normalized
    toml_content = generate_task_toml(
        task_id=task_id,
        title=metadata.title,
        description=metadata.behaviour_signature or metadata.title,
        docker_image=docker_image,
        timeout_sec=timeout_sec,
        repository=repository_url,
        base_commit=metadata.base_commit,
        license_name=license_name,
    )
    with open(pkg_dir / "task.toml", "w", encoding="utf-8", newline="\n") as f:
        f.write(toml_content.replace("\r\n", "\n"))

    # 3. environment/Dockerfile (always emit when provided or base_commit available)
    df_text = dockerfile_content
    if not df_text and metadata.base_commit:
        df_text = DEFAULT_CLICK_DOCKERFILE.format(
            repository=repository_url,
            base_commit=metadata.base_commit,
        )
    if df_text:
        env_dir = pkg_dir / "environment"
        env_dir.mkdir(exist_ok=True)
        with open(env_dir / "Dockerfile", "w", encoding="utf-8", newline="\n") as f:
            f.write(df_text.replace("\r\n", "\n"))

    # 4. solution/ - LF normalized
    sol_dir = pkg_dir / "solution"
    sol_dir.mkdir(exist_ok=True)
    with open(sol_dir / "solve.sh", "w", encoding="utf-8", newline="\n") as f:
        f.write(generate_solve_sh("reference.patch").replace("\r\n", "\n"))
    patch_text = Path(patch_path).read_text(encoding="utf-8", errors="replace")
    with open(sol_dir / "reference.patch", "w", encoding="utf-8", newline="\n") as f:
        f.write(patch_text.replace("\r\n", "\n"))

    # 5. tests/ - LF normalized
    tests_dir = pkg_dir / "tests"
    tests_dir.mkdir(exist_ok=True)

    use_grade = fail_to_pass is not None or pass_to_pass is not None
    with open(tests_dir / "test.sh", "w", encoding="utf-8", newline="\n") as f:
        f.write(generate_test_sh(test_cmd, use_grade_py=use_grade).replace("\r\n", "\n"))

    if use_grade:
        with open(tests_dir / "grade.py", "w", encoding="utf-8", newline="\n") as f:
            f.write(generate_grade_py().replace("\r\n", "\n"))
        with open(tests_dir / "fail_to_pass.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(fail_to_pass or [], f, indent=2)
            f.write("\n")
        with open(tests_dir / "pass_to_pass.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(pass_to_pass or [], f, indent=2)
            f.write("\n")

    feature_dir = tests_dir / "feature"
    feature_dir.mkdir(exist_ok=True)
    for p in feature_test_paths:
        src = Path(p)
        if src.is_file():
            content = src.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            with open(feature_dir / src.name, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        elif src.is_dir():
            for item in list(src.glob("*.py")) + list(src.glob("*.js")):
                content = item.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
                with open(feature_dir / item.name, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)

    # 6. tessera/ (evidence & metadata) - LF normalized
    tessera_dir = pkg_dir / "tessera"
    tessera_dir.mkdir(exist_ok=True)
    with open(tessera_dir / "task_metadata.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(metadata.model_dump(), f, indent=2)
        f.write("\n")
    with open(tessera_dir / "validation_report.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(validation_report.model_dump(), f, indent=2)
        f.write("\n")

    console.print(f"  [green]✓ Packaged Harbor task:[/green] [cyan]{pkg_dir}[/cyan]")
    return pkg_dir


def update_manifest(packages_dir: str | Path, manifest_path: str | Path | None = None) -> Path:
    """Create or update manifest.json listing all packaged tasks."""
    p_dir = Path(packages_dir)
    m_path = Path(manifest_path) if manifest_path else p_dir / "manifest.json"

    package_ids = []
    if p_dir.exists():
        for d in sorted(p_dir.iterdir()):
            if d.is_dir() and (d / "task.toml").exists():
                package_ids.append(d.name)

    manifest_data = {
        "packages": package_ids,
        "count": len(package_ids),
        "harbor_schema_version": HARBOR_SCHEMA_VERSION,
    }
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return m_path
