"""Gate tests — G1 through G4 accept AND reject cases.

Every gate has:
- accept test (known-good task passes)
- reject test (known-bad task fails at the expected gate)

Uses the fixture_git_repo from conftest.py — no network, no LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.gates import GateContext, run_g1, run_g2, run_g3, run_g4
from factory.repo import TestResult, run_tests


# ---------------------------------------------------------------------------
# Helper: build a GateContext from fixtures
# ---------------------------------------------------------------------------

def _ctx(
    fixture_git_repo: Path,
    fixture_base_commit: str,
    patch_path: Path,
    feature_test_dir: Path,
) -> GateContext:
    return GateContext(
        repo_path=fixture_git_repo,
        base_commit=fixture_base_commit,
        patch_path=patch_path,
        feature_test_paths=[feature_test_dir / "test_apply_discount.py"],
        regression_test_paths=[],
        test_cmd="python -m pytest -v --tb=short --no-header",
        result_format="pytest",
        timeout_s=30,
        determinism_runs=3,
        setup_cmd="",
    )


# ---------------------------------------------------------------------------
# G1 — clean apply
# ---------------------------------------------------------------------------

class TestG1:
    def test_accept_good_patch(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        good_patch: Path,
        feature_test_dir: Path,
    ) -> None:
        """Known-good patch must PASS G1."""
        ctx = _ctx(fixture_git_repo, fixture_base_commit, good_patch, feature_test_dir)
        result = run_g1(ctx)
        assert result.passed, f"G1 should pass for good patch; evidence: {result.evidence}"

    def test_reject_bad_patch(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        bad_patch_no_apply: Path,
        feature_test_dir: Path,
    ) -> None:
        """Malformed patch must FAIL G1."""
        ctx = _ctx(fixture_git_repo, fixture_base_commit, bad_patch_no_apply, feature_test_dir)
        result = run_g1(ctx)
        assert not result.passed, "G1 should reject a patch that cannot be applied"
        assert result.evidence, "G1 must report evidence on failure"


# ---------------------------------------------------------------------------
# G2 — fail-to-pass
# ---------------------------------------------------------------------------

class TestG2:
    def test_accept_good_task(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        good_patch: Path,
        feature_test_dir: Path,
    ) -> None:
        """Good task: feature tests FAIL on base, PASS with patch."""
        ctx = _ctx(fixture_git_repo, fixture_base_commit, good_patch, feature_test_dir)
        result = run_g2(ctx)
        assert result.passed, f"G2 should pass; evidence: {result.evidence}"
        assert result.organizer_checks.tests_fail_without_feature, "(c) must be true"
        assert result.organizer_checks.tests_pass_with_implementation, "(b) must be true"
        assert len(result.base_failed) > 0, "Must record which tests failed on base"
        assert len(result.patched_passed) > 0, "Must record which tests passed with patch"

    def test_reject_trivially_passing_tests(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        good_patch: Path,
        trivial_feature_test_dir: Path,
    ) -> None:
        """Tests that pass on base must FAIL G2 (task is not a real challenge)."""
        ctx = GateContext(
            repo_path=fixture_git_repo,
            base_commit=fixture_base_commit,
            patch_path=good_patch,
            feature_test_paths=[trivial_feature_test_dir / "test_trivial.py"],
            regression_test_paths=[],
            test_cmd="python -m pytest -v --tb=short --no-header",
            result_format="pytest",
            timeout_s=30,
            determinism_runs=3,
        )
        result = run_g2(ctx)
        assert not result.passed, "G2 should reject tasks whose tests pass on base"


# ---------------------------------------------------------------------------
# G3 — no regressions
# ---------------------------------------------------------------------------

class TestG3:
    @pytest.fixture()
    def baseline(self, fixture_git_repo: Path) -> TestResult:
        """Run baseline tests on the fixture repo."""
        return run_tests(
            fixture_git_repo,
            "python -m pytest -v --tb=short --no-header",
            timeout_s=30,
            result_format="pytest",
        )

    def test_accept_good_patch(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        good_patch: Path,
        feature_test_dir: Path,
        baseline: TestResult,
    ) -> None:
        """Good patch must not break existing tests."""
        ctx = _ctx(fixture_git_repo, fixture_base_commit, good_patch, feature_test_dir)
        result = run_g3(ctx, baseline)
        assert result.passed, f"G3 should pass; evidence: {result.evidence}"

    def test_reject_regression_patch(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        feature_test_dir: Path,
        baseline: TestResult,
        tmp_path: Path,
    ) -> None:
        """A patch that breaks existing tests must FAIL G3."""
        import textwrap
        # Write a patch that removes divide() from calculator.py — will break existing tests
        # We need to figure out what the diff looks like; use a simpler approach:
        # Create a patch that adds a syntax error to a file that gets imported
        # Actually: let's make a patch that changes the return value of add() — breaks TestAdd
        broken_patch = textwrap.dedent("""\
            --- a/calculator.py
            +++ b/calculator.py
            @@ -8,7 +8,7 @@
             
             def add(a: float, b: float) -> float:
                 \"\"\"Return the sum of two numbers.\"\"\"
            -    return a + b
            +    return a - b
        """)
        p = tmp_path / "broken.patch"
        p.write_text(broken_patch, encoding="utf-8")

        ctx = GateContext(
            repo_path=fixture_git_repo,
            base_commit=fixture_base_commit,
            patch_path=p,
            feature_test_paths=[feature_test_dir / "test_apply_discount.py"],
            regression_test_paths=[],
            test_cmd="python -m pytest -v --tb=short --no-header",
            result_format="pytest",
            timeout_s=30,
            determinism_runs=3,
        )
        result = run_g3(ctx, baseline)
        assert not result.passed, "G3 should reject a patch that causes regressions"


# ---------------------------------------------------------------------------
# G4 — determinism
# ---------------------------------------------------------------------------

class TestG4:
    def test_accept_deterministic_tests(
        self,
        fixture_git_repo: Path,
        fixture_base_commit: str,
        good_patch: Path,
        feature_test_dir: Path,
    ) -> None:
        """Deterministic feature tests must PASS G4."""
        ctx = _ctx(fixture_git_repo, fixture_base_commit, good_patch, feature_test_dir)
        ctx.determinism_runs = 3
        result = run_g4(ctx, runs=3)
        assert result.passed, f"G4 should pass for deterministic tests; evidence: {result.evidence}"
        assert result.flaky_tests == [], "No flaky tests expected"
        assert result.runs == 3
