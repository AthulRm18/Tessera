"""Tests for factory/packager.py — packaging into Harbor task directories."""

from __future__ import annotations

import json
from pathlib import Path

from factory.packager import (
    HARBOR_SCHEMA_VERSION,
    generate_solve_sh,
    generate_task_toml,
    generate_test_sh,
    package_task,
    update_manifest,
)
from factory.schemas import AcceptanceCriterion, TaskMetadata, ValidationReport
from factory.verify import check_package_structure


def test_generate_task_toml() -> None:
    content = generate_task_toml(
        task_id="task_001_test",
        title="Test Task",
        description="A test description",
        timeout_sec=90.0,
    )
    assert f'schema_version = "{HARBOR_SCHEMA_VERSION}"' in content
    assert 'name = "task_001_test"' in content
    assert 'category = "software-engineering"' in content
    assert "timeout_sec = 90.0" in content


def test_generate_solve_sh() -> None:
    sh = generate_solve_sh("reference.patch")
    assert "#!/bin/bash" in sh
    assert "git apply" in sh
    assert "reference.patch" in sh


def test_generate_test_sh() -> None:
    sh = generate_test_sh("pytest tests/feature")
    assert "#!/bin/bash" in sh
    assert "/logs/verifier/reward.txt" in sh
    assert 'echo "1" > /logs/verifier/reward.txt' in sh
    assert 'echo "0" > /logs/verifier/reward.txt' in sh


def test_package_task_full(tmp_path: Path) -> None:
    out_dir = tmp_path / "packages"
    patch_file = tmp_path / "test.patch"
    patch_file.write_text("dummy patch content", encoding="utf-8")
    test_file = tmp_path / "test_feature.py"
    test_file.write_text("def test_dummy(): pass", encoding="utf-8")

    meta = TaskMetadata(
        task_id="task_001",
        title="Add discount",
        acceptance_criteria=[AcceptanceCriterion(id="AC1", text="discount works")],
    )
    report = ValidationReport(task_id="task_001", accepted=True)

    pkg_dir = package_task(
        task_id="task_001",
        output_dir=out_dir,
        requirements_md="# Context\nAdd discount feature",
        patch_path=patch_file,
        feature_test_paths=[test_file],
        metadata=meta,
        validation_report=report,
        test_cmd="pytest",
    )

    assert pkg_dir.exists()
    assert (pkg_dir / "instruction.md").exists()
    assert (pkg_dir / "task.toml").exists()
    assert (pkg_dir / "solution" / "solve.sh").exists()
    assert (pkg_dir / "solution" / "reference.patch").exists()
    assert (pkg_dir / "tests" / "test.sh").exists()
    assert (pkg_dir / "tests" / "feature" / "test_feature.py").exists()
    assert (pkg_dir / "tessera" / "task_metadata.json").exists()
    assert (pkg_dir / "tessera" / "validation_report.json").exists()

    # Structural check helper
    ok, errors = check_package_structure(pkg_dir)
    assert ok, f"Structural check should pass; errors: {errors}"


def test_update_manifest(tmp_path: Path) -> None:
    packages_dir = tmp_path / "packages"
    task_dir = packages_dir / "task_001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text('schema_version = "1.4"', encoding="utf-8")

    m_path = update_manifest(packages_dir)
    assert m_path.exists()
    data = json.loads(m_path.read_text(encoding="utf-8"))
    assert "task_001" in data["packages"]
    assert data["count"] == 1
