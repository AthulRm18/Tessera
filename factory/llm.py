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


def load_dotenv_if_present(env_path: Path | str = ".env") -> None:
    """Load key-value pairs from .env into os.environ if not already set."""
    p = Path(env_path)
    if not p.is_file():
        return
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


load_dotenv_if_present()

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
        expect_json: bool = False,
    ) -> dict[str, Any]:
        """Return a dict with keys: content (str), input_tokens (int), output_tokens (int)."""
        raise NotImplementedError


@_register
class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, expect_json: bool = False) -> dict[str, Any]:
        try:
            import anthropic  # type: ignore[import]
        except ImportError:
            raise RuntimeError("anthropic package not installed; run: pip install anthropic")

        key = os.environ.get("ANTHROPIC_API_KEY", os.environ.get("LLM_API_KEY", ""))
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY (or LLM_API_KEY) not set in environment")

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

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, expect_json: bool = False) -> dict[str, Any]:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError:
            raise RuntimeError("openai package not installed; run: pip install openai")

        key = os.environ.get("OPENAI_API_KEY", os.environ.get("LLM_API_KEY", ""))
        if not key:
            raise RuntimeError("OPENAI_API_KEY (or LLM_API_KEY) not set in environment")

        client = OpenAI(api_key=key)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,  # type: ignore[arg-type]
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        usage = resp.usage
        return {
            "content": resp.choices[0].message.content or "",
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        }


@_register
class GeminiProvider(BaseProvider):
    """Google Gemini via the official google-genai SDK (v2+)."""

    name = "gemini"

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, expect_json: bool = False) -> dict[str, Any]:
        try:
            from google import genai  # type: ignore[import]
            from google.genai import types  # type: ignore[import]
        except ImportError:
            raise RuntimeError("google-genai package not installed; run: pip install google-genai")

        key = os.environ.get("GEMINI_API_KEY", os.environ.get("LLM_API_KEY", ""))
        if not key:
            raise RuntimeError("GEMINI_API_KEY (or LLM_API_KEY) not set in environment")

        client = genai.Client(api_key=key)

        # Separate system message; convert roles: assistant -> model
        system_parts: list[str] = []
        contents: list[types.Content] = []
        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"])
            elif m["role"] == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
            elif m["role"] == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part(text=m["content"])]))

        cfg_kwargs: dict[str, Any] = {
            "max_output_tokens": max(max_tokens, 8192),
            "temperature": temperature,
            "system_instruction": "\n\n".join(system_parts) if system_parts else None,
            "response_mime_type": "application/json" if expect_json else None,
        }
        # Only pass thinking_budget=0 on non-lite models that support it
        if "lite" not in model.lower():
            try:
                cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass

        cfg = types.GenerateContentConfig(**cfg_kwargs)

        last_err: Exception | None = None
        for delay_s in (5.0, 12.0, 25.0, 45.0, 60.0, None):
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                usage = resp.usage_metadata
                return {
                    "content": resp.text or "",
                    "input_tokens": usage.prompt_token_count or 0 if usage else 0,
                    "output_tokens": usage.candidates_token_count or 0 if usage else 0,
                }
            except Exception as exc:
                last_err = exc
                msg = str(exc)
                if ("400" in msg or "INVALID_ARGUMENT" in msg) and "thinking_config" in cfg_kwargs:
                    cfg_kwargs.pop("thinking_config", None)
                    cfg = types.GenerateContentConfig(**cfg_kwargs)
                    continue
                transient = any(code in msg for code in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
                if not transient or delay_s is None:
                    raise
                console.print(f"[yellow]Transient Gemini API error; retrying in {delay_s:.0f}s...[/yellow]")
                time.sleep(delay_s)

        assert last_err is not None
        raise last_err


@_register
class MockProvider(BaseProvider):
    """Test-only mock. Any run using this is excluded from real reports."""

    name = "mock"

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, expect_json: bool = False) -> dict[str, Any]:
        # Return custom mock if set in environment, else default minimal response
        content = os.environ.get("LLM_MOCK_RESPONSE") or json.dumps({"mock": True, "message": "mock response for testing"})
        return {
            "content": content,
            "input_tokens": 10,
            "output_tokens": 5,
        }


# ---------------------------------------------------------------------------
# Cost estimates (USD per 1K tokens — update when official rates confirmed)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Estimated cost rates (USD per 1K tokens)
# Source: Public pricing pages as of November 2026 (ai.google.dev/pricing,
# docs.anthropic.com/en/docs/pricing). All computed costs are estimates only.
# ---------------------------------------------------------------------------

_ESTIMATED_COST_PER_1K: dict[str, dict[str, float]] = {
    # Anthropic Claude (source: anthropic.com/pricing, Nov 2026)
    "claude-sonnet-4-20250514":  {"input": 0.003,    "output": 0.015},
    "claude-opus-4-20250514":    {"input": 0.015,    "output": 0.075},
    # OpenAI (source: openai.com/pricing, Nov 2026)
    "gpt-4o":                    {"input": 0.005,    "output": 0.015},
    "gpt-4o-mini":               {"input": 0.00015,  "output": 0.0006},
    # Google Gemini (estimated fallback rates based on ai.google.dev/pricing, Nov 2026)
    "gemini-3.6-flash":          {"input": 0.00010,  "output": 0.0004},
    "gemini-3.5-flash":          {"input": 0.000075, "output": 0.0003},
    "gemini-3.5-flash-lite":     {"input": 0.00002,  "output": 0.00008},
    "gemini-2.5-flash":          {"input": 0.000075, "output": 0.0003},
    "gemini-2.5-flash-lite":     {"input": 0.00001,  "output": 0.00004},
    "gemini-2.5-pro":            {"input": 0.00125,  "output": 0.005},
    "gemini-2.0-flash":          {"input": 0.000075, "output": 0.0003},
    "gemini-2.0-flash-lite":     {"input": 0.00001,  "output": 0.00004},
    "gemini-1.5-pro":            {"input": 0.00125,  "output": 0.005},
    "gemini-1.5-flash":          {"input": 0.000075, "output": 0.0003},
    "default":                   {"input": 0.003,    "output": 0.015},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute estimated cost in USD based on public pricing estimates."""
    rates = _ESTIMATED_COST_PER_1K.get(model, _ESTIMATED_COST_PER_1K["default"])
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
            "estimated_cost_usd": round(self.total_cost_usd, 6),
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
            "estimated_cost_usd": round(self.total_cost_usd, 6),
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
    ledger: UsageLedger | None = None,
    cache_dir: Path | str | None = None,
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
    if ledger is None:
        ledger = UsageLedger()
    cdir = Path(cache_dir) if cache_dir is not None else Path("runs/cache")

    provider_name = (os.environ.get(provider_env) or os.environ.get("LLM_PROVIDER", "mock")).lower()
    model = os.environ.get(model_env) or os.environ.get("LLM_MODEL", "mock-model")

    if provider_name not in _PROVIDERS:
        raise RuntimeError(
            f"Unknown LLM provider '{provider_name}' (from env {provider_env}). "
            f"Available: {list(_PROVIDERS)}"
        )

    provider = _PROVIDERS[provider_name]()
    is_mock = provider_name == "mock"

    params = {"max_tokens": max_tokens, "temperature": temperature}
    key = _cache_key(model, messages, params)
    cpath = _cache_path(cdir, key)

    replay_only = os.environ.get("TESSERA_REPLAY", "").lower() in ("1", "true", "yes")

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
    elif replay_only:
        raise RuntimeError(
            f"TESSERA_REPLAY=1 enabled, but cache miss occurred for model={model}, key={key[:12]} in {cdir}"
        )
    else:
        t0 = time.monotonic()
        result = provider.complete(model, messages, max_tokens, temperature, expect_json=expect_json)
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
            f"estimated ${cost:.4f} | {duration:.1f}s[/dim]"
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
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Attempt 1: strict=False tolerates unescaped control characters in JSON strings
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Extract substring between first '{' and last '}'
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"LLM response was not valid JSON.\n"
        f"Model: {model}\nPrompt hash: {key[:12]}\n"
        f"Raw response (first 500 chars): {raw[:500]}"
    )
