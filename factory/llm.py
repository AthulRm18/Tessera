"""LLM access layer — the ONLY place that calls an LLM.

Rules (from AGENTS.md):
- One function: call_llm() returning structured JSON.
- Provider, model, and key come from environment variables only. Never hardcode.
- Every call is cached to disk keyed by hash(model, prompt, params).
- Usage ledger: tokens, estimated cost, cache hits per run.
- Mock provider allowed ONLY in tests; any run using it is flagged.
- G7 solver uses a DIFFERENT model/session env var than the generator.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type["BaseProvider"]] = {}


def _register(cls: type["BaseProvider"]) -> type["BaseProvider"]:
    _PROVIDERS[cls.name] = cls
    return cls


class BaseProvider:
    name: str = ""

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        """Return a dict with keys: content (str), input_tokens (int), output_tokens (int)."""
        raise NotImplementedError


@_register
class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> dict[str, Any]:
        try:
            import anthropic  # type: ignore[import]
        except ImportError:
            raise RuntimeError("anthropic package not installed; run: pip install anthropic")

        key = os.environ.get("LLM_API_KEY", "")
        if not key:
            raise RuntimeError("LLM_API_KEY not set in environment")

        client = anthropic.Anthropic(api_key=key)
        # Separate system message if present
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=user_messages,
        )
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)
        return {
            "content": resp.content[0].text,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }


@_register
class OpenAIProvider(BaseProvider):
    name = "openai"

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> dict[str, Any]:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError:
            raise RuntimeError("openai package not installed; run: pip install openai")

        key = os.environ.get("LLM_API_KEY", "")
        if not key:
            raise RuntimeError("LLM_API_KEY not set in environment")

        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
        )
        usage = resp.usage
        return {
            "content": resp.choices[0].message.content or "",
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        }


@_register
class MockProvider(BaseProvider):
    """Test-only mock. Any run using this is excluded from real reports."""

    name = "mock"

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> dict[str, Any]:
        # Return a minimal valid structured response for tests
        return {
            "content": json.dumps({"mock": True, "message": "mock response for testing"}),
            "input_tokens": 10,
            "output_tokens": 5,
        }


# ---------------------------------------------------------------------------
# Cost estimates (USD per 1K tokens — update when official rates confirmed)
# ---------------------------------------------------------------------------

_COST_PER_1K: dict[str, dict[str, float]] = {
    # input, output
    "claude-sonnet-4-20250514": {"input": 0.003,  "output": 0.015},
    "claude-opus-4-20250514":   {"input": 0.015,  "output": 0.075},
    "gpt-4o":                   {"input": 0.005,  "output": 0.015},
    "gpt-4o-mini":              {"input": 0.00015,"output": 0.0006},
    "default":                  {"input": 0.003,  "output": 0.015},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _COST_PER_1K.get(model, _COST_PER_1K["default"])
    return (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------

def _cache_key(model: str, messages: list[dict[str, str]], params: dict[str, Any]) -> str:
    payload = json.dumps({"model": model, "messages": messages, "params": params}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def _load_cache(path: Path) -> dict[str, Any] | None:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Usage ledger
# ---------------------------------------------------------------------------

class UsageLedger:
    """Tracks tokens, cost, cache hits across a run. Thread-safe for single-process use."""

    def __init__(self, ledger_path: Path | None = None) -> None:
        self.ledger_path = ledger_path
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.cache_hits = 0
        self.calls = 0
        self.mock_calls = 0
        self._entries: list[dict[str, Any]] = []

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cache_hit: bool,
        mock: bool,
        prompt_hash: str,
        duration_s: float,
    ) -> None:
        self.calls += 1
        if cache_hit:
            self.cache_hits += 1
        if mock:
            self.mock_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost_usd
        entry = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6),
            "cache_hit": cache_hit,
            "mock": mock,
            "prompt_hash": prompt_hash,
            "duration_s": round(duration_s, 3),
        }
        self._entries.append(entry)
        if self.ledger_path:
            self._flush()

    def _flush(self) -> None:
        assert self.ledger_path is not None
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "total_calls": self.calls,
            "cache_hits": self.cache_hits,
            "mock_calls": self.mock_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "entries": self._entries,
        }
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def summary(self) -> dict[str, Any]:
        return {
            "total_calls": self.calls,
            "cache_hits": self.cache_hits,
            "mock_calls": self.mock_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
        }

    @property
    def mock_provider_used(self) -> bool:
        return self.mock_calls > 0


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def call_llm(
    messages: list[dict[str, str]],
    *,
    ledger: UsageLedger,
    cache_dir: Path,
    provider_env: str = "LLM_PROVIDER",
    model_env: str = "LLM_MODEL",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    expect_json: bool = True,
) -> dict[str, Any]:
    """Call the LLM and return structured JSON.

    - Provider and model come from environment variables.
    - Every call is cached by hash(model, prompt, params).
    - Usage is recorded in the ledger.
    - If expect_json=True, parses and returns the JSON content; raises ValueError on failure.
    - Any call using the mock provider sets ledger.mock_provider_used = True.
    """
    provider_name = os.environ.get(provider_env, "mock").lower()
    model = os.environ.get(model_env, "mock-model")

    if provider_name not in _PROVIDERS:
        raise RuntimeError(
            f"Unknown LLM provider '{provider_name}' (from env {provider_env}). "
            f"Available: {list(_PROVIDERS)}"
        )

    provider = _PROVIDERS[provider_name]()
    is_mock = provider_name == "mock"

    params = {"max_tokens": max_tokens, "temperature": temperature}
    key = _cache_key(model, messages, params)
    cpath = _cache_path(cache_dir, key)

    # Cache hit?
    cached = _load_cache(cpath)
    if cached is not None:
        ledger.record(
            model=model,
            input_tokens=cached.get("input_tokens", 0),
            output_tokens=cached.get("output_tokens", 0),
            cost_usd=0.0,   # already paid; don't double-count
            cache_hit=True,
            mock=is_mock,
            prompt_hash=key[:12],
            duration_s=0.0,
        )
        console.print(f"[dim]llm cache hit: {key[:12]}[/dim]")
        raw = cached["content"]
    else:
        t0 = time.monotonic()
        result = provider.complete(model, messages, max_tokens, temperature)
        duration = time.monotonic() - t0

        raw = result["content"]
        in_tok = result["input_tokens"]
        out_tok = result["output_tokens"]
        cost = _estimate_cost(model, in_tok, out_tok)

        _save_cache(cpath, {
            "content": raw,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "model": model,
            "prompt_hash": key,
        })

        ledger.record(
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            cache_hit=False,
            mock=is_mock,
            prompt_hash=key[:12],
            duration_s=duration,
        )
        console.print(
            f"[dim]llm call: {model} | {in_tok}+{out_tok} tok | "
            f"${cost:.4f} | {duration:.1f}s[/dim]"
        )

    if not expect_json:
        return {"content": raw}

    # Parse JSON — strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening fence (```json or ```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        # Remove closing fence
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM response was not valid JSON.\n"
            f"Model: {model}\nPrompt hash: {key[:12]}\n"
            f"Raw response (first 500 chars): {raw[:500]}"
        ) from exc
