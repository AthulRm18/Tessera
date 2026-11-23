"""Tests for factory/generator.py."""

import json
from pathlib import Path
import pytest

from factory.config import FactoryConfig
from factory.generator import (
    BudgetExceededError,
    check_budget_guard,
    generate_requirements,
)
from factory.llm import UsageLedger
from factory.schemas import TaskPlan


def test_budget_guard_token_limit():
    cfg = FactoryConfig()
    cfg.budget.max_tokens_per_run = 1000
    ledger = UsageLedger()
    ledger.total_input_tokens = 600
    ledger.total_output_tokens = 500

    with pytest.raises(BudgetExceededError, match="Run token budget reached"):
        check_budget_guard(cfg, ledger)


def test_budget_guard_cost_limit():
    cfg = FactoryConfig()
    cfg.budget.max_cost_per_run = 0.10
    ledger = UsageLedger()
    ledger.total_cost_usd = 0.15

    with pytest.raises(BudgetExceededError, match="Run cost budget reached"):
        check_budget_guard(cfg, ledger)


def test_generate_requirements_resumable(tmp_path: Path):
    cfg = FactoryConfig()
    ledger = UsageLedger()
    plan = TaskPlan(
        plan_id="task_resumable",
        module="jwt/api_jwt.py",
        behaviour_axis="new_business_rule",
        title="Existing Task",
    )

    task_dir = tmp_path / "task_resumable"
    task_dir.mkdir(parents=True)
    (task_dir / "requirements.md").write_text("# Existing Requirements\n", encoding="utf-8")
    with open(task_dir / "requirements_meta.json", "w", encoding="utf-8") as f:
        json.dump({"criteria": [{"id": "AC1", "text": "Do something"}], "symbols": ["sym1"]}, f)

    md, criteria, symbols = generate_requirements(plan, "code", cfg, ledger, task_dir)
    assert md == "# Existing Requirements\n"
    assert len(criteria) == 1
    assert criteria[0].id == "AC1"
    assert ledger.calls == 0  # No LLM call on resume!


def test_generate_requirements_with_mock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    mock_resp = {
        "title": "Validate Header",
        "problem_description": "Validate header fields rigorously",
        "acceptance_criteria": [
            {"id": "AC1", "text": "Reject missing alg"},
            {"id": "AC2", "text": "Accept valid alg"}
        ],
        "interface": {"symbols": ["jwt.api_jwt.validate_header"]},
        "markdown_text": "# Validate Header\n\n## Acceptance Criteria\n1. Reject missing alg\n"
    }
    monkeypatch.setenv("LLM_MOCK_RESPONSE", json.dumps(mock_resp))

    cfg = FactoryConfig()
    cfg.output.cache_dir = str(tmp_path / "cache")
    ledger = UsageLedger()
    plan = TaskPlan(
        plan_id="task_mock",
        module="jwt/api_jwt.py",
        behaviour_axis="new_business_rule",
        title="Validate Header",
    )

    task_dir = tmp_path / "task_mock"
    task_dir.mkdir(parents=True)

    md, criteria, symbols = generate_requirements(plan, "code", cfg, ledger, task_dir)
    assert len(criteria) == 2
    assert criteria[0].id == "AC1"
    assert criteria[1].id == "AC2"
    assert "jwt.api_jwt.validate_header" in symbols
    assert (task_dir / "requirements.md").exists()
    assert ledger.calls == 1
