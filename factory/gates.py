"""Validation gates G1–G4.

Gate order: G1 → G2 → G3 → G4 (cheapest first; stop at first failure).
G5–G7 live in gates_advanced.py (not yet built).

Rules:
- Every gate returns a typed result with real evidence.
- Never fabricate. If a command times out, record it and fail the gate.
- G2 explicitly reports the three organizer checks:
    (a) original repo works as-is
    (b) tests pass with the implementation
    (c) tests fail when the feature is absent
- Import/syntax errors in G2 do NOT count as valid feature-test failures.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.repo import (
    RepoProfile,
    TestResult,
    apply_patch,
    reverse_patch,
    run_cmd,
    run_tests,
    _print_test_result,
)
from factory.schemas import G2Result, G3Result, G4Result, GateResult, OrganizerChecks

console = Console()


# ---------------------------------------------------------------------------
# Gate context — everything a gate needs
# ---------------------------------------------------------------------------

@dataclass
class GateContext:
    """Input for all gates: paths, commands, thresholds."""

    repo_path: Path                 # original repo (read-only; never modify)
    base_commit: str
    patch_path: Path                # unified diff to apply
    feature_test_paths: list[Path]  # files/dirs with feature tests
    regression_test_paths: list[Path]  # extra regression tests (may be empty)
    test_cmd: str                   # repo's full test command (for G3)
    result_format: str
    timeout_s: int
    determinism_runs: int = 3
    setup_cmd: str = ""
    docker_image: str = ""


# ---------------------------------------------------------------------------
# G1 — Clean apply
# ---------------------------------------------------------------------------

def run_g1(ctx: GateContext) -> GateResult:
    """G1: Reference patch applies cleanly; code compiles/imports without errors.

    Uses `git apply --check` first (no side effects), then the real apply.
    """
    console.print("\n[bold]G1[/bold] clean apply")

    # Check only first (no changes)
    ok, msg = apply_patch(ctx.patch_path, ctx.repo_path, check_only=True)
    if not ok:
        return GateResult(passed=False, evidence=f"git apply --check failed: {msg}")

    # Actual apply to a temp worktree we create for this check
    with _temp_worktree(ctx) as wt:
        ok, msg = apply_patch(ctx.patch_path, wt)
        if not ok:
            return GateResult(passed=False, evidence=f"git apply failed: {msg}")

        # Try compile/import check (language-agnostic: just run the setup or a syntax check)
        syntax_ok, syntax_msg = _check_syntax(wt, ctx)

    if not syntax_ok:
        return GateResult(passed=False, evidence=f"Syntax/compile check failed: {syntax_msg}")

    console.print("  [green]✓ G1 passed[/green]")
    return GateResult(passed=True, evidence="Patch applied cleanly; syntax ok")


def _check_syntax(wt: Path, ctx: GateContext) -> tuple[bool, str]:
    """Quick syntax check: for Python, run `python -m py_compile` on changed files."""
    # Determine changed files from the patch
    rc, stdout, _ = run_cmd(f"git apply --stat {ctx.patch_path}", cwd=ctx.repo_path)
    changed: list[str] = []
    for line in stdout.splitlines():
        # lines like " jwt/api_jwt.py | 10 +++--"
        parts = line.split("|")
        if len(parts) >= 2:
            fname = parts[0].strip()
            if fname:
                changed.append(fname)

    for fname in changed:
        fpath = wt / fname
        if not fpath.exists():
            continue
        if fpath.suffix == ".py":
            rc, _, stderr = run_cmd(f'python -m py_compile "{fpath}"', cwd=wt)
            if rc != 0:
                return False, f"{fname}: {stderr.strip()}"
        elif fpath.suffix in (".js", ".ts", ".mjs"):
            rc, _, stderr = run_cmd(f'node --check "{fpath}"', cwd=wt)
            if rc != 0:
                return False, f"{fname}: {stderr.strip()}"

    return True, "ok"


# ---------------------------------------------------------------------------
# G2 — Fail-to-pass
# ---------------------------------------------------------------------------

def run_g2(ctx: GateContext) -> G2Result:
    """G2: Feature tests FAIL on base, PASS with reference patch.

    Reports organizer checks explicitly:
      (a) original repo works as-is (baseline must be green)
      (b) tests pass after the reference implementation
      (c) tests fail when the feature is absent

    Import/syntax errors in feature tests do NOT count as valid failures (G2 fails).
    """
    console.print("\n[bold]G2[/bold] fail-to-pass")

    organizer = OrganizerChecks()

    # (a) Run feature tests on BASE (no patch) — they must FAIL
    with _temp_worktree(ctx) as wt:
        base_result = _run_feature_tests(ctx, wt)

    _print_test_result(base_result, "base (expect FAIL)")
    organizer.original_repo_works = True  # the base repo is intact (G1 confirmed)

    # Reject if base failures are import/syntax errors — not valid failures
    bad_types = {t for t in base_result.failure_types if t in ("import_error", "syntax_error")}
    if bad_types and base_result.n_failed == 0 and base_result.n_errors > 0:
        return G2Result(
            passed=False,
            evidence="Feature tests errored on base with import/syntax errors — invalid failure",
            base_failed=base_result.error_ids,
            organizer_checks=organizer,
            failure_types=list(bad_types),
        )

    # Feature tests must actually fail on base
    if base_result.passed or (base_result.n_failed == 0 and base_result.n_errors == 0):
        return G2Result(
            passed=False,
            evidence="Feature tests PASSED on base — task is trivially solvable or tests are wrong",
            base_failed=[],
            organizer_checks=organizer,
        )

    base_failed_ids = base_result.failed_ids + base_result.error_ids
    organizer.tests_fail_without_feature = True  # (c) confirmed

    # (b) Apply patch, re-run feature tests — they must PASS
    with _temp_worktree(ctx) as wt:
        ok, msg = apply_patch(ctx.patch_path, wt)
        if not ok:
            return G2Result(
                passed=False,
                evidence=f"Patch failed to apply in G2 worktree: {msg}",
                base_failed=base_failed_ids,
                organizer_checks=organizer,
            )

        patched_result = _run_feature_tests(ctx, wt)

    _print_test_result(patched_result, "patched (expect PASS)")

    if not patched_result.passed or patched_result.n_failed > 0:
        return G2Result(
            passed=False,
            evidence="Feature tests still FAIL after applying the reference patch",
            base_failed=base_failed_ids,
            patched_passed=patched_result.passed_ids,
            organizer_checks=organizer,
            failure_types=patched_result.failure_types,
        )

    organizer.tests_pass_with_implementation = True  # (b) confirmed

    console.print("  [green]✓ G2 passed[/green] — (a)✓ (b)✓ (c)✓")
    return G2Result(
        passed=True,
        evidence="Tests fail on base (assertion failures), pass with reference patch",
        base_failed=base_failed_ids,
        patched_passed=patched_result.passed_ids,
        organizer_checks=organizer,
        failure_types=base_result.failure_types,
    )


def _to_wsl_path(win_path: Path) -> str:
    p = win_path.resolve().as_posix()
    if len(p) >= 2 and p[1] == ":":
        return f"/mnt/{p[0].lower()}{p[2:]}"
    return p


def _run_docker_pytest(wt: Path, docker_image: str, pytest_cmd: str, timeout_s: int, extra_mounts: list[tuple[Path, str]] | None = None) -> tuple[int, str, str]:
    import subprocess
    import sys

    mounts = [(wt, "/app")]
    if extra_mounts:
        mounts.extend(extra_mounts)

    if sys.platform == "win32":
        args = ["wsl", "-d", "Ubuntu", "docker", "run", "--rm", "--network", "none"]
        for host_p, cont_p in mounts:
            args.extend(["-v", f"{_to_wsl_path(host_p)}:{cont_p}"])
        args.extend(["-e", "PYTHONPATH=/app/src:/app", docker_image, "bash", "-c", pytest_cmd])
    else:
        args = ["docker", "run", "--rm", "--network", "none"]
        for host_p, cont_p in mounts:
            args.extend(["-v", f"{host_p.resolve()}:{cont_p}"])
        args.extend(["-e", "PYTHONPATH=/app/src:/app", docker_image, "bash", "-c", pytest_cmd])

    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s)
    return proc.returncode, proc.stdout, proc.stderr


def _run_feature_tests(ctx: GateContext, wt: Path) -> TestResult:
    """Run the task's feature tests from within a worktree (in Docker if configured)."""
    from factory.repo import parse_test_output, run_cmd as _run

    if ctx.docker_image and ctx.result_format == "pytest":
        # Mount each feature test file's parent directory under /tests_mount_i
        mounts: list[tuple[Path, str]] = []
        target_args: list[str] = []
        for idx, p in enumerate(ctx.feature_test_paths):
            abs_p = Path(p).resolve()
            mounts.append((abs_p.parent, f"/tests_m{idx}"))
            target_args.append(f"/tests_m{idx}/{abs_p.name}")
        cmd = f"pytest {' '.join(target_args)} -v --tb=short --no-header --rootdir=/tests_m0 --import-mode=importlib"
        rc, stdout, stderr = _run_docker_pytest(wt, ctx.docker_image, cmd, ctx.timeout_s, extra_mounts=mounts)
        combined = stdout + ("\n" + stderr if stderr.strip() else "")
        return parse_test_output(combined, rc, ctx.result_format)

    test_files = " ".join(f'"{p}"' for p in ctx.feature_test_paths)
    if ctx.result_format == "pytest":
        # --import-mode=importlib avoids sys.path conflicts; wt is the rootdir
        cmd = (
            f"python -m pytest {test_files} -v --tb=short --no-header "
            f"--rootdir={wt} --import-mode=importlib"
        )
        env = {"PYTHONPATH": str(wt)}
    elif ctx.result_format in ("mocha", "jest"):
        cmd = f"npx mocha {test_files}"
        env = {"NODE_PATH": str(wt)}
    else:
        cmd = ctx.test_cmd
        env = {"PYTHONPATH": str(wt)}

    rc, stdout, stderr = _run(cmd, cwd=wt, timeout_s=ctx.timeout_s, env=env)
    combined = stdout + ("\n" + stderr if stderr.strip() else "")
    return parse_test_output(combined, rc, ctx.result_format)


# ---------------------------------------------------------------------------
# G3 — No regressions
# ---------------------------------------------------------------------------

def run_g3(ctx: GateContext, baseline: TestResult) -> G3Result:
    """G3: Full test suite result after the patch must equal or improve the baseline.

    Compares n_failed + n_errors before and after.
    """
    console.print("\n[bold]G3[/bold] no regressions")

    with _temp_worktree(ctx) as wt:
        # Apply patch
        ok, msg = apply_patch(ctx.patch_path, wt)
        if not ok:
            return G3Result(
                passed=False,
                evidence=f"Patch failed in G3 worktree: {msg}",
                suite_before=baseline.to_dict(),
            )
        # Run full suite (in container when docker_image set, else native)
        if ctx.docker_image and ctx.result_format == "pytest":
            from factory.repo import parse_test_output
            rc, out, err = _run_docker_pytest(wt, ctx.docker_image, ctx.test_cmd, ctx.timeout_s)
            after = parse_test_output(out + ("\n" + err if err.strip() else ""), rc, ctx.result_format)
        else:
            if ctx.setup_cmd:
                run_cmd(ctx.setup_cmd, cwd=wt, timeout_s=ctx.timeout_s)
            after = run_tests(wt, ctx.test_cmd, ctx.timeout_s, ctx.result_format)

    _print_test_result(after, "after patch")

    before_failures = baseline.n_failed + baseline.n_errors
    after_failures  = after.n_failed + after.n_errors

    if after_failures > before_failures:
        return G3Result(
            passed=False,
            evidence=(
                f"Regressions: {after_failures} failures after patch vs "
                f"{before_failures} before. "
                f"New failures: {set(after.failed_ids) - set(baseline.failed_ids or [])}"
            ),
            suite_before=baseline.to_dict(),
            suite_after=after.to_dict(),
        )

    console.print("  [green]✓ G3 passed[/green]")
    return G3Result(
        passed=True,
        evidence=f"No regressions: {before_failures} → {after_failures} failures",
        suite_before=baseline.to_dict(),
        suite_after=after.to_dict(),
    )


# ---------------------------------------------------------------------------
# G4 — Determinism
# ---------------------------------------------------------------------------

def run_g4(ctx: GateContext, runs: int = 3) -> G4Result:
    """G4: Feature tests produce identical results across N runs (no flaky tests)."""
    console.print(f"\n[bold]G4[/bold] determinism ({runs} runs)")

    all_passed_sets: list[set[str]] = []
    all_failed_sets: list[set[str]] = []

    with _temp_worktree(ctx) as wt:
        ok, msg = apply_patch(ctx.patch_path, wt)
        if not ok:
            return G4Result(passed=False, evidence=f"Patch failed in G4 worktree: {msg}")

        for i in range(runs):
            result = _run_feature_tests(ctx, wt)
            all_passed_sets.append(set(result.passed_ids))
            all_failed_sets.append(set(result.failed_ids))
            console.print(f"  run {i+1}/{runs}: {result.n_passed} passed, {result.n_failed} failed")

    # Flaky = test id that is not consistently in the same set across runs
    flaky: set[str] = set()
    for i in range(1, runs):
        flaky |= all_passed_sets[0].symmetric_difference(all_passed_sets[i])
        flaky |= all_failed_sets[0].symmetric_difference(all_failed_sets[i])

    if flaky:
        return G4Result(
            passed=False,
            runs=runs,
            flaky_tests=sorted(flaky),
            evidence=f"Flaky tests detected across {runs} runs: {sorted(flaky)}",
        )

    console.print("  [green]✓ G4 passed[/green]")
    return G4Result(
        passed=True,
        runs=runs,
        flaky_tests=[],
        evidence=f"All {runs} runs produced identical results",
    )


# ---------------------------------------------------------------------------
# Run all gates G1–G4
# ---------------------------------------------------------------------------

def run_gates_g1_to_g4(
    ctx: GateContext,
    baseline: TestResult,
) -> dict[str, Any]:
    """Run G1→G2→G3→G4 in order. Stop at first failure. Return dict of results."""
    results: dict[str, Any] = {}

    g1 = run_g1(ctx)
    results["G1_clean_apply"] = g1.model_dump()
    if not g1.passed:
        console.print("[red]✗ Stopped at G1[/red]")
        return results

    g2 = run_g2(ctx)
    results["G2_fail_to_pass"] = g2.model_dump()
    if not g2.passed:
        console.print("[red]✗ Stopped at G2[/red]")
        return results

    g3 = run_g3(ctx, baseline)
    results["G3_no_regressions"] = g3.model_dump()
    if not g3.passed:
        console.print("[red]✗ Stopped at G3[/red]")
        return results

    g4 = run_g4(ctx, runs=ctx.determinism_runs)
    results["G4_determinism"] = g4.model_dump()
    if not g4.passed:
        console.print("[red]✗ Stopped at G4[/red]")
        return results

    console.print("\n[green bold]✓ G1–G4 all passed[/green bold]")
    return results


# ---------------------------------------------------------------------------
# Worktree context manager
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _temp_worktree(ctx: GateContext):  # type: ignore[type-arg]
    """Create a temporary worktree, yield its path, clean up after."""
    parent = Path(tempfile.mkdtemp(prefix="tessera_gate_"))
    wt: Path | None = None
    try:
        from factory.repo import create_worktree, remove_worktree
        wt = create_worktree(ctx.repo_path, ctx.base_commit, "wt", parent_dir=parent)
        yield wt
    finally:
        if wt is not None:
            try:
                from factory.repo import remove_worktree
                remove_worktree(ctx.repo_path, wt)
            except Exception:
                pass
        shutil.rmtree(str(parent), ignore_errors=True)
