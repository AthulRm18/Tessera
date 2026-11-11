"""Pydantic models for plans, tasks, and validation evidence."""

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
    description: str = ""
    target_symbols: list[str] = Field(default_factory=list)


class CoverageGrid(BaseModel):
    """Collection of planned tasks covering module × axis combinations."""

    plans: list[TaskPlan] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------

class AcceptanceCriterion(BaseModel):
    """One numbered acceptance criterion inside a task."""

    id: str  # e.g. "AC1"
    text: str


# ---------------------------------------------------------------------------
# Task models
# ---------------------------------------------------------------------------

class TaskMetadata(BaseModel):
    """Metadata for a generated task — written to task.json."""

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
# Validation evidence
# ---------------------------------------------------------------------------

class GateResult(BaseModel):
    """Result of a single validation gate."""

    passed: bool
    evidence: Any = None


class G2Result(GateResult):
    """Fail-to-pass evidence."""

    base_failed: list[str] = Field(default_factory=list)
    patched_passed: list[str] = Field(default_factory=list)


class G3Result(GateResult):
    """No-regressions evidence."""

    suite_before: dict[str, Any] = Field(default_factory=dict)
    suite_after: dict[str, Any] = Field(default_factory=dict)


class G4Result(GateResult):
    """Determinism evidence."""

    runs: int = 3
    flaky_tests: list[str] = Field(default_factory=list)


class G5Result(GateResult):
    """Traceability evidence."""

    uncovered_criteria: list[str] = Field(default_factory=list)
    orphan_tests: list[str] = Field(default_factory=list)
    undeclared_symbols: list[str] = Field(default_factory=list)


class G6Result(GateResult):
    """Mutation check evidence."""

    mutants: int = 0
    killed: int = 0
    kill_rate: float = 0.0
    survivors: list[str] = Field(default_factory=list)


class G7Result(GateResult):
    """Independent solve evidence."""

    solved: bool = False
    attempts: int = 0
    notes: str = ""


class ValidationReport(BaseModel):
    """Full validation report for a task — written to validation_report.json."""

    task_id: str
    base_commit: str = ""
    gates: dict[str, GateResult] = Field(default_factory=dict)
    repairs: int = 0
    accepted: bool = False
    reject_reason: str | None = None
    run: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Run and manifest
# ---------------------------------------------------------------------------

class RunInfo(BaseModel):
    """Metadata for a single pipeline run."""

    run_id: str
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    tasks_planned: int = 0
    tasks_accepted: int = 0
    tasks_rejected: int = 0
    total_tokens: int = 0
    est_cost: float = 0.0
    duration_s: float = 0.0


class Manifest(BaseModel):
    """Top-level manifest listing all packages."""

    packages: list[str] = Field(default_factory=list)
    run: RunInfo | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
