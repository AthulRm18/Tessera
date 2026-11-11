"""Pydantic configuration models loaded from config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RepoConfig(BaseModel):
    """Repository-specific settings."""

    path: str = "./target_repo"
    base_ref: str = "main"
    setup_cmd: str = ""
    test_cmd: str = ""
    result_format: str = "pytest"
    timeout_s: int = Field(default=120, ge=10)


class GenerationConfig(BaseModel):
    """Task generation settings."""

    n_tasks: int = Field(default=10, ge=1)
    behaviour_axes: list[str] = Field(default_factory=lambda: [
        "new_business_rule",
        "threshold_or_limit",
        "state_transition",
        "validation_and_error_policy",
        "ordering_or_priority",
        "interaction_between_features",
        "idempotency",
        "rounding_or_units",
    ])
    max_repairs: int = Field(default=2, ge=0)


class GatesConfig(BaseModel):
    """Validation gate thresholds."""

    determinism_runs: int = Field(default=3, ge=1)
    mutation_kill_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    solver_attempts: int = Field(default=3, ge=1)


class LLMConfig(BaseModel):
    """LLM access configuration — values come from environment variables."""

    provider_env: str = "LLM_PROVIDER"
    model_env: str = "LLM_MODEL"
    key_env: str = "LLM_API_KEY"
    max_tokens: int = Field(default=4096, ge=256)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class OutputConfig(BaseModel):
    """Output directory paths."""

    runs_dir: str = "./runs"
    packages_dir: str = "./packages"
    samples_dir: str = "./samples"
    cache_dir: str = "./runs/cache"


class FactoryConfig(BaseModel):
    """Top-level configuration combining all sections."""

    repo: RepoConfig = Field(default_factory=RepoConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    gates: GatesConfig = Field(default_factory=GatesConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(config_path: str | Path = "config.yaml") -> FactoryConfig:
    """Load and validate configuration from a YAML file.

    Falls back to defaults if the file does not exist.
    """
    path = Path(config_path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        return FactoryConfig(**raw)
    return FactoryConfig()

