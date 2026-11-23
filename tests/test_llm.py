"""Tests for factory/llm.py — uses mock provider only. Never makes real LLM calls."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from factory.llm import UsageLedger, call_llm, _cache_key, _cache_path, _save_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_cache(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture()
def ledger(tmp_path: Path) -> UsageLedger:
    return UsageLedger(ledger_path=tmp_path / "ledger.json")


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force mock provider for all tests."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")


# ---------------------------------------------------------------------------
# Basic call
# ---------------------------------------------------------------------------

def test_mock_returns_json(tmp_cache: Path, ledger: UsageLedger) -> None:
    result = call_llm(
        [{"role": "user", "content": "hello"}],
        ledger=ledger,
        cache_dir=tmp_cache,
        expect_json=True,
    )
    assert isinstance(result, dict)
    assert result.get("mock") is True


def test_mock_records_in_ledger(tmp_cache: Path, ledger: UsageLedger) -> None:
    call_llm([{"role": "user", "content": "hello"}], ledger=ledger, cache_dir=tmp_cache)
    assert ledger.calls == 1
    assert ledger.mock_calls == 1
    assert ledger.mock_provider_used is True


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------

def test_cache_hit_on_second_call(tmp_cache: Path, ledger: UsageLedger) -> None:
    msgs = [{"role": "user", "content": "cache test"}]
    call_llm(msgs, ledger=ledger, cache_dir=tmp_cache)
    call_llm(msgs, ledger=ledger, cache_dir=tmp_cache)
    assert ledger.calls == 2
    assert ledger.cache_hits == 1


def test_different_messages_different_cache_keys(tmp_cache: Path, ledger: UsageLedger) -> None:
    call_llm([{"role": "user", "content": "msg A"}], ledger=ledger, cache_dir=tmp_cache)
    call_llm([{"role": "user", "content": "msg B"}], ledger=ledger, cache_dir=tmp_cache)
    assert ledger.cache_hits == 0
    assert ledger.calls == 2


def test_cache_file_created(tmp_cache: Path, ledger: UsageLedger) -> None:
    msgs = [{"role": "user", "content": "file test"}]
    call_llm(msgs, ledger=ledger, cache_dir=tmp_cache)
    key = _cache_key("mock-model", msgs, {"max_tokens": 4096, "temperature": 0.2})
    assert _cache_path(tmp_cache, key).exists()


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def test_json_with_markdown_fence(tmp_cache: Path, ledger: UsageLedger, monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM wrapping JSON in ```json ... ``` fences is stripped correctly."""
    raw = '```json\n{"key": "value"}\n```'
    # Inject a fake cache entry
    msgs = [{"role": "user", "content": "fence test"}]
    key = _cache_key("mock-model", msgs, {"max_tokens": 4096, "temperature": 0.2})
    _save_cache(_cache_path(tmp_cache, key), {"content": raw, "input_tokens": 5, "output_tokens": 5})
    result = call_llm(msgs, ledger=ledger, cache_dir=tmp_cache)
    assert result == {"key": "value"}


def test_invalid_json_raises_value_error(tmp_cache: Path, ledger: UsageLedger) -> None:
    msgs = [{"role": "user", "content": "bad json test"}]
    key = _cache_key("mock-model", msgs, {"max_tokens": 4096, "temperature": 0.2})
    _save_cache(_cache_path(tmp_cache, key), {"content": "not json at all", "input_tokens": 1, "output_tokens": 1})
    with pytest.raises(ValueError, match="not valid JSON"):
        call_llm(msgs, ledger=ledger, cache_dir=tmp_cache)


# ---------------------------------------------------------------------------
# expect_json=False
# ---------------------------------------------------------------------------

def test_expect_json_false_returns_raw(tmp_cache: Path, ledger: UsageLedger) -> None:
    result = call_llm(
        [{"role": "user", "content": "raw"}],
        ledger=ledger,
        cache_dir=tmp_cache,
        expect_json=False,
    )
    assert "content" in result
    assert isinstance(result["content"], str)


# ---------------------------------------------------------------------------
# Unknown provider
# ---------------------------------------------------------------------------

def test_unknown_provider_raises(tmp_cache: Path, ledger: UsageLedger, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "nonexistent_provider")
    with pytest.raises(RuntimeError, match="Unknown LLM provider"):
        call_llm([{"role": "user", "content": "hi"}], ledger=ledger, cache_dir=tmp_cache)


# ---------------------------------------------------------------------------
# Ledger summary
# ---------------------------------------------------------------------------

def test_ledger_summary_keys(tmp_cache: Path, ledger: UsageLedger) -> None:
    call_llm([{"role": "user", "content": "s"}], ledger=ledger, cache_dir=tmp_cache)
    s = ledger.summary()
    assert "total_calls" in s
    assert "cache_hits" in s
    assert "mock_calls" in s
    assert "total_cost_usd" in s


def test_ledger_written_to_disk(tmp_path: Path, tmp_cache: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    l = UsageLedger(ledger_path=ledger_path)
    call_llm([{"role": "user", "content": "disk"}], ledger=l, cache_dir=tmp_cache)
    assert ledger_path.exists()
    data = json.loads(ledger_path.read_text())
    assert data["total_calls"] == 1
