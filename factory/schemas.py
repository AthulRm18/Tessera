"""Pydantic models for plans, tasks, gates, and validation evidence.

These are Tessera-internal models. The Harbor task directory is emitted
by the packager using these; the packager never guesses Harbor field names.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Plan models
# ---------------------------------------------------------------------------

class TaskPlan(BaseModel):
    """A single planned task before generation."""

    plan_id: str
    module: str
    behaviour_axis: str
    interaction_partner: str | None = None
    title: str = ""
    description: str = ""
    target_symbols: list[str] = Field(default_factory=list)


class CoverageGrid(BaseModel):
    """Collection of planned tasks — module × axis × partner."""

    plans: list[TaskPlan] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------

class AcceptanceCriterion(BaseModel):
    """One numbered acceptance criterion (AC1, AC2, …)."""

    id: str
    text: str


# ---------------------------------------------------------------------------
# Task models
# ---------------------------------------------------------------------------

class TaskMetadata(BaseModel):
    """Internal Tessera metadata for a generated task — written to tessera/task_metadata.json."""

    task_id: str
    title: str
    base_commit: str = ""
    base_tag: str = ""
    module: str = ""
    behaviour_axis: str = ""
    interaction_partner: str | None = None
    behaviour_signature: str = ""
    interface: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    test_map: dict[str, list[str]] = Field(default_factory=dict)
    generator: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Validation evidence (gate results)
# ---------------------------------------------------------------------------

class GateResult(BaseModel):
    """Base result of a single validation gate."""

    passed: bool
    evidence: Any = None


class OrganizerChecks(BaseModel):
    """The three explicit organizer validation checks (G2)."""

    original_repo_works: bool = False         # (a) baseline suite green before patch
    tests_pass_with_implementation: bool = False  # (b) feature tests pass with reference patch
    tests_fail_without_feature: bool = False  # (c) feature tests fail without the patch


class G2Result(GateResult):
    """Fail-to-pass evidence — includes the three organizer checks explicitly."""

    base_failed: list[str] = Field(default_factory=list)
    patched_passed: list[str] = Field(default_factory=list)
    failure_types: list[str] = Field(default_factory=list)   # must be assertion, not import/syntax
    organizer_checks: OrganizerChecks = Field(default_factory=OrganizerChecks)


class G3Result(GateResult):
    """No-regressions evidence."""

    suite_before: dict[str, Any] = Field(default_factory=dict)
    suite_after: dict[str, Any] = Field(default_factory=dict)


class G4Result(GateResult):
    """Determinism evidence — 3 runs, no flaky tests."""

    runs: int = 3
    flaky_tests: list[str] = Field(default_factory=list)


class G5Result(GateResult):
    """Traceability evidence."""

    uncovered_criteria: list[str] = Field(default_factory=list)
    orphan_tests: list[str] = Field(default_factory=list)
    undeclared_symbols: list[str] = Field(default_factory=list)


class G6Result(GateResult):
    """Mutation check evidence (patch lines only)."""

    mutants: int = 0
    killed: int = 0
    kill_rate: float = 0.0
    survivors: list[str] = Field(default_factory=list)


class G7Result(GateResult):
    """Independent solve evidence (separate session, never sees reference or tests)."""

    solved: bool = False
    attempts: int = 0
    notes: str = ""


class ValidationReport(BaseModel):
    """Full validation report — written to tessera/validation_report.json inside the package."""

    task_id: str
    base_commit: str = ""
    gates: dict[str, Any] = Field(default_factory=dict)
    repairs: int = 0
    accepted: bool = False
    reject_reason: str | None = None
    first_failing_gate: str | None = None   # cheapest-first; stop here
    run: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Run and manifest
# ---------------------------------------------------------------------------

class RunInfo(BaseModel):
    """Metadata for a single pipeline run."""

    run_id: str
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    repo_name: str = ""          # human label only; never hard-coded in logic
    base_commit: str = ""
    tasks_planned: int = 0
    tasks_generated: int = 0
    tasks_accepted: int = 0
    tasks_rejected: int = 0
    total_tokens: int = 0
    est_cost_usd: float = 0.0
    cache_hits: int = 0
    duration_s: float = 0.0
    mock_provider_used: bool = False   # True → excluded from real reports


class Manifest(BaseModel):
    """Top-level manifest listing all packages."""

    packages: list[str] = Field(default_factory=list)
    run: RunInfo | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
