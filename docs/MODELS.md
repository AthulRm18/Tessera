# docs/MODELS.md — Declared Models & Tools Register

> **Requirement:** Official Hackathon PDF specifies: "Participants may use any coding agents or models for Track 1 pipelines, provided all tools and models are declared in the technical documentation."

This document declares all LLMs, coding agents, and tools used by the Tessera pipeline.

---

## 1. Declared Model Roles in Tessera

| Role | Default Model | Provider | Temperature | Max Tokens | Purpose |
|---|---|---|---|---|---|
| **Planner** | `gemini-3.5-flash` | Google Gemini | 0.2 | 4,096 | Builds coverage grid (module $\times$ behaviour axis $\times$ partner), grounds in real AST symbols. |
| **Generator** | `gemini-3.5-flash` | Google Gemini | 0.2 | 8,192 | Produces `instruction.md`, reference patches (`solve.sh`), and feature test suites. |
| **Repair Agent** | `gemini-3.5-flash` | Google Gemini | 0.2 | 8,192 | Automated repair loop: consumes structured gate failure feedback (git apply errors, test failures). |
| **Independent Solver (G7)** | `gemini-3.5-flash-lite` | Google Gemini | 0.2 | 4,096 | Evaluates solvability and requirement clarity; sees **ONLY** `instruction.md` and base repo (zero test/patch leakage). |
| **Alternative Provider** | `claude-sonnet-4-20250514` | Anthropic | 0.2 | 8,192 | Supported via `LLM_PROVIDER=anthropic` for cross-model validation. |

*Note on Model Independence (G7):* G7 solver uses a separate model identifier (`LLM_SOLVER_MODEL=gemini-3.5-flash-lite`) and isolated prompt session from the generator (`LLM_MODEL=gemini-3.5-flash`).

---

## 2. Declared Frameworks & Core Tools

| Tool / Framework | Version | License | Role in Pipeline |
|---|---|---|---|
| **Harbor Framework** | `0.25.x` | Apache-2.0 | Task execution, container isolation, and official validation matrix (`nop` 0.0, `oracle` 1.0). |
| **Docker Engine** | `29.x`+ | Apache-2.0 | Standardized hermetic task containerization. |
| **Python** | `>=3.11` | PSF | Pipeline runtime and CLI orchestrator. |
| **typer** | `>=0.9.0` | MIT | CLI interface (`tessera` / `tess`). |
| **pydantic** | `>=2.0.0` | MIT | Strict schema validation, task metadata, and gate result contracts. |
| **pytest** | `>=7.0.0` | MIT | Test runner for Click tasks, fixture gates, and internal unit tests. |
| **PyYAML** | `>=6.0` | MIT | Configuration loader (`configs/click.yaml`). |
| **rich** | `>=13.0.0` | MIT | Terminal rendering and run reporting. |
| **google-genai** | `>=3.0.0` | Apache-2.0 | Official Google GenAI SDK for Gemini API integration. |
