"""Tests for factory/verify.py — clean-room package verification."""

from __future__ import annotations

from pathlib import Path

from factory.config import FactoryConfig
from factory.packager import package_task
from factory.schemas import AcceptanceCriterion, TaskMetadata, ValidationReport
from factory.verify import check_package_structure, verify_package


def test_check_package_structure_missing_files(tmp_path: Path) -> None:
    empty_pkg = tmp_path / "empty_pkg"
    empty_pkg.mkdir()
    ok, errors = check_package_structure(empty_pkg)
    assert not ok
    assert len(errors) > 0


def test_verify_good_package_end_to_end(
    fixture_git_repo: Path,
    fixture_base_commit: str,
    good_patch: Path,
    feature_test_dir: Path,
    tmp_path: Path,
) -> None:
    """Package a known-good task and run clean-room verification on it."""
    out_dir = tmp_path / "packages"
    meta = TaskMetadata(
        task_id="task_cart_discount",
        title="Add apply_discount to Cart",
        base_commit=fixture_base_commit,
        acceptance_criteria=[
            AcceptanceCriterion(id="AC1", text="apply_discount returns discounted subtotal"),
        ],
    )
    report = ValidationReport(task_id="task_cart_discount", accepted=True)

    pkg_dir = package_task(
        task_id="task_cart_discount",
        output_dir=out_dir,
        requirements_md="# Context\nCart module\n# AC1\napply_discount",
        patch_path=good_patch,
        feature_test_paths=[feature_test_dir / "test_apply_discount.py"],
        metadata=meta,
        validation_report=report,
        test_cmd="python -m pytest -v --tb=short --no-header",
        evidence_dir=tmp_path / "evidence",
    )

    cfg = FactoryConfig()
    cfg.repo.path = str(fixture_git_repo)
    cfg.repo.base_ref = fixture_base_commit
    cfg.repo.test_cmd = "python -m pytest test_baseline.py -v --tb=short --no-header"
    cfg.repo.result_format = "pytest"

    result = verify_package(pkg_dir, cfg, native=True, check_determinism=False)
    assert result.passed, f"Verify should pass for good package; errors: {result.errors}"
    assert result.structural_check
    assert result.g1_passed
    assert result.g2_passed
    assert result.g3_passed
