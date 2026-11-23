"""Tests for factory/planner.py."""

from pathlib import Path
from factory.config import FactoryConfig
from factory.llm import UsageLedger
from factory.planner import build_coverage_grid, _select_source_modules, plan_task_with_llm
from factory.repo import FileSymbols


def test_select_source_modules_filters_tests():
    symbols = [
        FileSymbols(path="jwt/api_jwt.py", classes=["PyJWT"], functions=["encode"]),
        FileSymbols(path="tests/test_jwt.py", functions=["test_encode"]),
        FileSymbols(path="setup.py", functions=["setup"]),
    ]
    sources = _select_source_modules(symbols)
    assert len(sources) == 1
    assert sources[0].path == "jwt/api_jwt.py"


def test_build_coverage_grid_uniqueness_and_count(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MOCK_RESPONSE", '{"title": "Test Title", "description": "Test Desc", "target_symbols": ["encode"]}')

    symbols = [
        FileSymbols(path="jwt/api_jwt.py", classes=["PyJWT"], functions=["encode"]),
        FileSymbols(path="jwt/api_jws.py", classes=["PyJWS"], functions=["sign"]),
    ]
    cfg = FactoryConfig()
    grid = build_coverage_grid(symbols, cfg, n_tasks=4)

    assert len(grid.plans) == 4
    # Check all (module, axis, partner) tuples are unique
    tuples = [(p.module, p.behaviour_axis, p.interaction_partner) for p in grid.plans]
    assert len(tuples) == len(set(tuples))


def test_plan_task_with_mock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MOCK_RESPONSE", '{"title": "Limit Token Lifetime", "description": "Add max age limit", "target_symbols": ["decode"]}')

    cfg = FactoryConfig()
    cfg.output.cache_dir = str(tmp_path / "cache")
    ledger = UsageLedger()
    mod = FileSymbols(path="jwt/api_jwt.py", classes=["PyJWT"], functions=["decode"])
    plan = plan_task_with_llm(
        plan_id="task_001",
        module=mod,
        axis="threshold_or_limit",
        partner=None,
        llm_cfg=cfg.llm,
        ledger=ledger,
        cache_dir=cfg.output.cache_dir,
    )

    assert plan.plan_id == "task_001"
    assert plan.title == "Limit Token Lifetime"
    assert plan.behaviour_axis == "threshold_or_limit"
    assert plan.target_symbols == ["decode"]
    assert ledger.calls == 1
