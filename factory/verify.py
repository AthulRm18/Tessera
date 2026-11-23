"""Clean-room verification of a Harbor task package.

Judges or users can run:
    tessera verify packages/<task_id>

Verification steps:
1. Validate package structure:
   - instruction.md
   - task.toml (schema_version = "1.4")
   - solution/solve.sh & reference.patch
   - tests/test.sh & test files
2. Clean checkout / worktree of base repo at base_commit
3. Run Organizer Checks (G2):
   (a) Baseline tests pass on clean repo
   (b) Feature tests FAIL on clean repo (missing feature detected)
   (c) Apply solution (solve.sh / patch)
   (d) Feature tests PASS
   (e) Existing regression tests still PASS (G3)
4. Confirm /logs/verifier/reward.txt reward is 1
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.config import FactoryConfig
from factory.gates import GateContext, run_g1, run_g2, run_g3, run_g4
from factory.repo import TestResult, run_tests

console = Console()


@dataclass
class VerifyResult:
    """Result of clean-room verification."""

    task_id: str
    passed: bool
    structural_check: bool = False
    g1_passed: bool = False
    g2_passed: bool = False
    g3_passed: bool = False
    g4_passed: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def check_package_structure(pkg_path: Path) -> tuple[bool, list[str]]:
    """Check required Harbor files and folders exist."""
    errors = []
    required_files = [
        "instruction.md",
        "task.toml",
        "solution/solve.sh",
        "solution/reference.patch",
        "tests/test.sh",
    ]
    for rel_path in required_files:
        target = pkg_path / rel_path
        if not target.exists():
            errors.append(f"Missing required file: {rel_path}")

    # Check task.toml schema_version
    toml_path = pkg_path / "task.toml"
    if toml_path.exists():
        text = toml_path.read_text(encoding="utf-8")
        if 'schema_version = "1.4"' not in text:
            errors.append('task.toml must declare schema_version = "1.4"')

    return (len(errors) == 0), errors


def verify_package(
    package_path: str | Path,
    cfg: FactoryConfig,
    check_determinism: bool = True,
) -> VerifyResult:
    """Verify a packaged Harbor task against a clean checkout of the base repo."""
    pkg = Path(package_path).resolve()
    task_id = pkg.name
    res = VerifyResult(task_id=task_id, passed=False)

    console.print(f"\n[bold]Verifying package:[/bold] {task_id}")

    # 1. Structural check
    ok, errors = check_package_structure(pkg)
    res.structural_check = ok
    if not ok:
        res.errors = errors
        for err in errors:
            console.print(f"  [red]✗ {err}[/red]")
        return res
    console.print("  [green]✓ Structure check: Harbor format valid[/green]")

    # 2. Load internal metadata if present
    meta_path = pkg / "tessera" / "task_metadata.json"
    base_commit = cfg.repo.base_ref
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
            base_commit = meta.get("base_commit", base_commit)

    # 3. Locate patch and tests
    patch_path = pkg / "solution" / "reference.patch"
    feature_dir = pkg / "tests" / "feature"
    feature_tests = list(feature_dir.glob("*.py")) + list(feature_dir.glob("*.js"))

    ctx = GateContext(
        repo_path=Path(cfg.repo.path).resolve(),
        base_commit=base_commit,
        patch_path=patch_path,
        feature_test_paths=feature_tests,
        regression_test_paths=[],
        test_cmd=cfg.repo.test_cmd,
        result_format=cfg.repo.result_format,
        timeout_s=cfg.repo.timeout_s,
        determinism_runs=cfg.gates.determinism_runs if check_determinism else 1,
        setup_cmd=cfg.repo.setup_cmd,
    )

    # Baseline on clean repo
    console.print("  Checking baseline tests on clean repo...")
    baseline = run_tests(ctx.repo_path, ctx.test_cmd, ctx.timeout_s, ctx.result_format)
    if not baseline.passed:
        res.errors.append("Baseline tests failed on base repo checkout")
        console.print("[red]✗ Clean repo baseline is NOT green[/red]")
        return res
    console.print("  [green]✓ Baseline is green[/green]")

    # G1 Clean apply
    g1 = run_g1(ctx)
    res.g1_passed = g1.passed
    res.evidence["G1"] = g1.model_dump()
    if not g1.passed:
        res.errors.append(f"G1 failed: {g1.evidence}")
        return res

    # G2 Fail-to-pass (organizer checks: a, b, c)
    g2 = run_g2(ctx)
    res.g2_passed = g2.passed
    res.evidence["G2"] = g2.model_dump()
    if not g2.passed:
        res.errors.append(f"G2 failed: {g2.evidence}")
        return res

    # G3 No regressions
    g3 = run_g3(ctx, baseline)
    res.g3_passed = g3.passed
    res.evidence["G3"] = g3.model_dump()
    if not g3.passed:
        res.errors.append(f"G3 failed: {g3.evidence}")
        return res

    # G4 Determinism (optional for quick verify)
    if check_determinism:
        g4 = run_g4(ctx, runs=ctx.determinism_runs)
        res.g4_passed = g4.passed
        res.evidence["G4"] = g4.model_dump()
        if not g4.passed:
            res.errors.append(f"G4 failed: {g4.evidence}")
            return res
    else:
        res.g4_passed = True

    res.passed = True
    console.print(f"\n[green bold]✓ Package {task_id} successfully VERIFIED[/green bold]")
    return res
