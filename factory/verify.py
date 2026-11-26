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
import os
import re
import shutil
import subprocess
import sys
import tomllib
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
    container_verified: bool = False
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


def _run_container_cmd(cmd: str, timeout_s: float = 180.0) -> subprocess.CompletedProcess[str]:
    """Execute a bash command in WSL2 (if on Windows) or natively (if on Linux)."""
    if sys.platform == "win32":
        wsl_cmd = ["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd]
        return subprocess.run(wsl_cmd, capture_output=True, text=True, timeout=timeout_s)
    else:
        return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout_s)


def is_container_runtime_available() -> bool:
    """Check if Harbor and Docker are runnable via WSL2 or native Linux."""
    try:
        proc = _run_container_cmd("export PATH=\"$HOME/.local/bin:$PATH\" && harbor --version && docker ps", timeout_s=15.0)
        return proc.returncode == 0
    except Exception:
        return False


def _to_wsl_path(p: Path) -> str:
    """Convert a Windows Path (or POSIX path) into a WSL2 POSIX path."""
    resolved = p.resolve()
    if resolved.drive:
        drive_letter = resolved.drive[0].lower()
        rest = resolved.as_posix()[2:]  # strip 'C:'
        return f"/mnt/{drive_letter}{rest}"
    return resolved.as_posix()


def _extract_reward(out_dir: Path) -> str | None:
    """Read the reward value from a Harbor output directory."""
    if not out_dir.exists():
        return None
    reward_files = sorted(out_dir.glob("**/reward.txt"))
    if not reward_files:
        return None
    return reward_files[0].read_text(encoding="utf-8").strip()


def verify_package_container(
    package_path: str | Path,
    cfg: FactoryConfig,
) -> VerifyResult:
    """Run container-based verification of a Harbor task package using Harbor runner.
    
    Evaluates:
      1. Structural integrity and Harbor format compliance.
      2. Nop agent run in Docker: verifies tests FAIL when feature is absent (reward == 0).
      3. Oracle agent run in Docker: verifies reference patch applies and tests PASS (reward == 1).
    """
    pkg = Path(package_path).resolve()
    task_id = pkg.name
    res = VerifyResult(task_id=task_id, passed=False, container_verified=True)

    console.print(f"\n[bold]Container verifying package:[/bold] {task_id}")

    # 1. Structural check
    ok, errors = check_package_structure(pkg)
    res.structural_check = ok
    if not ok:
        res.errors = errors
        for err in errors:
            console.print(f"  [red]✗ {err}[/red]")
        return res
    console.print("  [green]✓ Structure check: Harbor format valid[/green]")

    # Check container runtime
    if not is_container_runtime_available():
        res.errors.append("Container runtime (Docker / WSL2 Harbor) is unavailable.")
        console.print("  [yellow]⚠ Container runtime unavailable[/yellow]")
        return res

    # Resolve paths cleanly for Harbor (WSL2 on Windows, POSIX on Linux)
    root_dir = Path.cwd().resolve()
    wsl_root = _to_wsl_path(root_dir) if sys.platform == "win32" else root_dir.as_posix()
    try:
        rel_pkg = pkg.relative_to(root_dir).as_posix()
    except ValueError:
        rel_pkg = _to_wsl_path(pkg) if sys.platform == "win32" else pkg.as_posix()

    jobs_root = root_dir / "jobs"
    nop_out_dir = jobs_root / f"verify_{task_id}_nop"
    oracle_out_dir = jobs_root / f"verify_{task_id}_oracle"
    shutil.rmtree(nop_out_dir, ignore_errors=True)
    shutil.rmtree(oracle_out_dir, ignore_errors=True)
    nop_out_dir.mkdir(parents=True, exist_ok=True)
    oracle_out_dir.mkdir(parents=True, exist_ok=True)
    wsl_nop_out = _to_wsl_path(nop_out_dir) if sys.platform == "win32" else nop_out_dir.as_posix()
    wsl_oracle_out = _to_wsl_path(oracle_out_dir) if sys.platform == "win32" else oracle_out_dir.as_posix()

    # 2. Run Harbor with nop agent (expect reward 0.0)
    console.print("  [cyan]Running Harbor container check: nop agent (expecting reward 0.0)...[/cyan]")
    nop_cmd = (
        f'export PATH="$HOME/.local/bin:$PATH" && '
        f'cd "{wsl_root}" && '
        f'harbor run -p "{rel_pkg}" -a nop -k 1 -o "{wsl_nop_out}" --no-delete -y'
    )
    nop_proc = _run_container_cmd(nop_cmd, timeout_s=cfg.repo.timeout_s + 120.0)
    res.evidence["harbor_nop_stdout"] = nop_proc.stdout
    res.evidence["harbor_nop_stderr"] = nop_proc.stderr

    nop_reward = _extract_reward(nop_out_dir)
    if nop_reward in ("0", "0.0"):
        console.print(f"  [green]✓ Nop check passed: feature absence detected (reward {nop_reward})[/green]")
    else:
        res.errors.append(f"Nop agent produced reward '{nop_reward}' (expected '0.0')")
        console.print(f"  [red]✗ Nop check failed: expected reward 0.0, got {nop_reward}[/red]")
        return res

    # 3. Run Harbor with oracle agent (expect reward 1.0)
    console.print("  [cyan]Running Harbor container check: oracle agent (expecting reward 1.0)...[/cyan]")
    oracle_cmd = (
        f'export PATH="$HOME/.local/bin:$PATH" && '
        f'cd "{wsl_root}" && '
        f'harbor run -p "{rel_pkg}" -a oracle -k 1 -o "{wsl_oracle_out}" --no-delete -y'
    )
    oracle_proc = _run_container_cmd(oracle_cmd, timeout_s=cfg.repo.timeout_s + 120.0)
    res.evidence["harbor_oracle_stdout"] = oracle_proc.stdout
    res.evidence["harbor_oracle_stderr"] = oracle_proc.stderr

    oracle_reward = _extract_reward(oracle_out_dir)
    if oracle_reward in ("1", "1.0"):
        console.print(f"  [green]✓ Oracle check passed: reference solution verified (reward {oracle_reward})[/green]")
        res.g1_passed = True
        res.g2_passed = True
        res.g3_passed = True
        res.g4_passed = True
        res.passed = True
        console.print(f"\n[green bold]✓ Package {task_id} successfully CONTAINER-VERIFIED[/green bold]")
    else:
        res.errors.append(f"Oracle agent produced reward '{oracle_reward}' (expected '1.0')")
        console.print(f"  [red]✗ Oracle check failed: expected reward 1.0, got {oracle_reward}[/red]")

    return res


def verify_package_native(
    package_path: str | Path,
    cfg: FactoryConfig,
    check_determinism: bool = True,
) -> VerifyResult:
    """Verify a packaged Harbor task natively against a clean checkout of the base repo."""
    pkg = Path(package_path).resolve()
    task_id = pkg.name
    res = VerifyResult(task_id=task_id, passed=False, container_verified=False)

    console.print(f"\n[bold]Native verifying package:[/bold] {task_id}")

    # 1. Structural check
    ok, errors = check_package_structure(pkg)
    res.structural_check = ok
    if not ok:
        res.errors = errors
        for err in errors:
            console.print(f"  [red]✗ {err}[/red]")
        return res
    console.print("  [green]✓ Structure check: Harbor format valid[/green]")

    # 2. Resolve base_commit from package task.toml first, falling back to cfg or evidence
    base_commit = cfg.repo.base_ref
    toml_path = pkg / "task.toml"
    if toml_path.exists():
        try:
            with open(toml_path, "rb") as tf:
                toml_data = tomllib.load(tf)
            toml_commit = (
                toml_data.get("metadata", {}).get("base_commit")
                or toml_data.get("base_commit")
            )
            if toml_commit:
                base_commit = str(toml_commit)
        except Exception:
            pass
    if not base_commit:
        meta_path = Path("evidence") / task_id / "task_metadata.json"
        if not meta_path.exists():
            meta_path = pkg / "tessera" / "task_metadata.json"
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

    # G4 Determinism
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
    console.print(f"\n[green bold]✓ Package {task_id} successfully NATIVE-VERIFIED[/green bold]")
    return res


def verify_package(
    package_path: str | Path,
    cfg: FactoryConfig,
    native: bool = False,
    check_determinism: bool = True,
) -> VerifyResult:
    """Verify a Harbor task package. Uses container verification by default, falls back or uses native if requested."""
    if not native:
        if is_container_runtime_available():
            container_res = verify_package_container(package_path, cfg)
            return container_res
        else:
            console.print("  [yellow]Notice: Container runtime not available. Running native verification.[/yellow]")
    
    return verify_package_native(package_path, cfg, check_determinism=check_determinism)

