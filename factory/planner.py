"""Task planner — generates deterministic coverage grid grounded in real repo symbols.

Builds a grid over (module × behaviour_axis × interaction_partner) from the repo map.
Rejects plans whose (module, axis, partner) combination is already used.
Grounds every plan in real symbols extracted from the repo map.
Uses the cheapest adequate model configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.config import FactoryConfig, LLMConfig
from factory.llm import UsageLedger, call_llm
from factory.repo import FileSymbols
from factory.schemas import CoverageGrid, TaskPlan

console = Console()

PLAN_SYSTEM_PROMPT = """You are a senior software engineer designing realistic feature-development coding tasks for an AI coding benchmark.
Given an existing source code module, its real symbols, and a targeted behaviour axis:
Propose a realistic, grounded feature addition or rule extension that builds naturally on existing code.
Constraints:
- Only reference real symbols that exist in the module.
- Do NOT propose trivial documentation changes or variable renaming.
- Propose a genuine behavioral rule, limit, validation, state transition, or interaction.
- Respond ONLY with a valid JSON object matching the requested schema.
"""


def _select_source_modules(repo_map: list[FileSymbols]) -> list[FileSymbols]:
    """Filter repo map down to primary source modules (excluding tests, migrations, etc.)."""
    source_modules = []
    for fs in repo_map:
        path_lower = fs.path.lower().replace("\\", "/")
        # Exclude test files, setup, build scripts
        if any(skip in path_lower for skip in ["test", "setup.py", "conftest", "docs", "scripts"]):
            continue
        # Module must have classes or functions
        if fs.classes or fs.functions or fs.exports:
            source_modules.append(fs)
    return source_modules


def plan_task_with_llm(
    plan_id: str,
    module: FileSymbols,
    axis: str,
    partner: FileSymbols | None,
    llm_cfg: LLMConfig,
    ledger: UsageLedger | None = None,
    cache_dir: Path | str | None = None,
) -> TaskPlan:
    """Ground a (module, axis, partner) grid cell into a concrete TaskPlan using LLM."""
    existing_symbols = [
        f"class {c}" for c in module.classes
    ] + [
        f"def {fn}" for fn in module.functions
    ] + [
        f"export {e}" for e in module.exports
    ]
    
    partner_path = partner.path if partner else None
    prompt = (
        f"Module: {module.path}\n"
        f"Existing Symbols in Module: {', '.join(existing_symbols[:15])}\n"
        f"Targeted Behaviour Axis: {axis}\n"
        f"Interaction Partner Module: {partner_path or 'None (isolated)'}\n\n"
        "Return a JSON object with:\n"
        '{\n'
        '  "title": "<short descriptive task title>",\n'
        '  "description": "<detailed problem description explaining the requirement and behavior>",\n'
        '  "target_symbols": ["<1-3 real symbol names from the module that will be extended or used>"]\n'
        '}\n'
    )

    data = call_llm(
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider_env=llm_cfg.provider_env,
        model_env=llm_cfg.model_env,
        ledger=ledger,
        cache_dir=cache_dir,
        expect_json=True,
    )
    
    title = data.get("title", f"Feature on {Path(module.path).stem} ({axis})")
    description = data.get("description", f"Add {axis} behavior to {module.path}")
    target_symbols = data.get("target_symbols", [])

    return TaskPlan(
        plan_id=plan_id,
        module=module.path,
        behaviour_axis=axis,
        interaction_partner=partner_path,
        title=title,
        description=description,
        target_symbols=target_symbols,
    )


def build_coverage_grid(
    repo_map: list[FileSymbols],
    cfg: FactoryConfig,
    n_tasks: int | None = None,
    ledger: UsageLedger | None = None,
) -> CoverageGrid:
    """Build a deterministic coverage grid (module × axis × partner).
    
    Rejects any plans whose (module, axis, partner) tuple is already in use.
    """
    target_n = n_tasks or cfg.generation.n_tasks
    source_modules = _select_source_modules(repo_map)
    if not source_modules:
        source_modules = repo_map  # Fallback to all files if no filtered sources

    axes = cfg.generation.behaviour_axes
    seen_cells: set[tuple[str, str, str | None]] = set()
    grid_plans: list[TaskPlan] = []

    console.print(f"[bold]Building coverage grid[/bold]: targeting {target_n} tasks across {len(source_modules)} modules and {len(axes)} axes")

    plan_idx = 1
    # Deterministic round-robin iteration over modules and axes
    for mod_i, module in enumerate(source_modules):
        for axis_i, axis in enumerate(axes):
            if len(grid_plans) >= target_n:
                break

            # Deterministic partner selection: either another module or None
            partner: FileSymbols | None = None
            if len(source_modules) > 1 and (mod_i + axis_i) % 2 == 1:
                partner_idx = (mod_i + 1) % len(source_modules)
                partner = source_modules[partner_idx]

            partner_path = partner.path if partner else None
            cell_key = (module.path, axis, partner_path)

            # Rejection rule: reject if cell already used
            if cell_key in seen_cells:
                console.print(f"  [yellow]Skipping duplicate cell:[/yellow] {cell_key}")
                continue

            seen_cells.add(cell_key)
            plan_id = f"task_{plan_idx:03d}_{Path(module.path).stem}_{axis[:12]}"
            
            console.print(f"  Planning {plan_id}: [cyan]{module.path}[/cyan] × [magenta]{axis}[/magenta] (partner: {partner_path or 'none'})")

            plan = plan_task_with_llm(
                plan_id=plan_id,
                module=module,
                axis=axis,
                partner=partner,
                llm_cfg=cfg.llm,
                ledger=ledger,
                cache_dir=cfg.output.cache_dir,
            )
            grid_plans.append(plan)
            plan_idx += 1

        if len(grid_plans) >= target_n:
            break

    grid = CoverageGrid(plans=grid_plans)
    console.print(f"[green]✓ Generated {len(grid.plans)} unique, grounded plans in coverage grid[/green]")
    return grid
