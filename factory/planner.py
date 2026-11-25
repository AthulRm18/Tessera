"""Task planner — generates deterministic coverage grid grounded in real repo symbols.

Builds a balanced grid over (module × behaviour_axis × interaction_partner) from the repo map.
Enforces:
- Zero duplicate (module, axis, partner) cells.
- Maximum 2 tasks from the same module in a selection.
- Tasks span distinct behaviour axes across the selection.
- Cheapest adequate model configured (`LLM_PLANNER_MODEL`, falling back to `LLM_MODEL`).
- Strictly reads only the target repository's AST/repo map and config.yaml (never external shortlists).
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from factory.config import FactoryConfig, LLMConfig
from factory.llm import UsageLedger, call_llm
from factory.repo import FileSymbols
from factory.schemas import CoverageGrid, TaskPlan

console = Console()

PLAN_SYSTEM_PROMPT = """You are a senior software engineer designing realistic feature-development coding tasks for an AI coding benchmark.
Given an existing source code module, its real symbols, and a targeted behaviour axis:
Propose a realistic, grounded feature addition or behaviour extension that builds naturally on existing code.
Constraints:
- Only propose NEW features or behaviour extensions; NEVER propose bug fixes or code cleanups.
- Reference ONLY real symbols that exist in the module.
- Do NOT propose trivial documentation changes, logging-only tweaks, or variable renaming.
- Propose a concrete, deterministic, testable behavioral capability, validation rule, option interaction, formatting rule, or state transition.
- Do NOT propose features requiring network I/O, external credentials, or non-deterministic wall-clock sleeps.
- Respond ONLY with a valid JSON object matching the requested schema.
"""


def _select_source_modules(repo_map: list[FileSymbols]) -> list[FileSymbols]:
    """Filter repo map down to primary non-private source modules with real symbols."""
    source_modules: list[FileSymbols] = []
    for fs in repo_map:
        path_norm = fs.path.replace("\\", "/")
        path_lower = path_norm.lower()
        name = Path(path_norm).name
        # Exclude test files, package init re-export wrappers, setup, docs, scripts
        if any(skip in path_lower for skip in ["test", "setup.py", "conftest", "docs", "scripts"]):
            continue
        if name == "__init__.py" or name.startswith("_"):
            continue
        # Module must define meaningful public classes or functions
        pub_classes = [c for c in fs.classes if not c.startswith("_")]
        pub_funcs = [fn for fn in fs.functions if not fn.startswith("_")]
        if len(pub_classes) + len(pub_funcs) >= 2 or fs.exports:
            source_modules.append(fs)

    # Sort deterministically by symbol richness (more public classes+funcs first), tie-broken by path
    source_modules.sort(
        key=lambda m: (-(len(m.classes) + len(m.functions) + len(m.exports)), m.path)
    )
    return source_modules


def plan_task_with_llm(
    plan_id: str,
    module: FileSymbols,
    axis: str,
    partner: FileSymbols | None,
    llm_cfg: LLMConfig,
    ledger: UsageLedger | None = None,
    cache_dir: Path | str | None = None,
    prior_titles: list[str] | None = None,
) -> TaskPlan:
    """Ground a (module, axis, partner) grid cell into a concrete TaskPlan using LLM."""
    existing_symbols = [
        f"class {c}" for c in module.classes if not c.startswith("_")
    ] + [
        f"def {fn}" for fn in module.functions if not fn.startswith("_")
    ] + [
        f"export {e}" for e in module.exports if not e.startswith("_")
    ]

    partner_path = partner.path if partner else None
    avoid_str = ""
    if prior_titles:
        avoid_str = f"Avoid overlapping with already planned tasks: {', '.join(prior_titles)}\n"

    outline = ""
    if Path("target_repo", module.path).exists():
        from factory.repo import extract_module_outline
        outline = extract_module_outline("target_repo", module.path, max_chars=3000)

    prompt = (
        f"Module: {module.path}\n"
        f"Existing Public Symbols & Signatures (DO NOT re-propose parameters or features already present!):\n"
        f"{outline or ', '.join(existing_symbols[:18])}\n\n"
        f"Targeted Behaviour Axis: {axis}\n"
        f"Interaction Partner Module: {partner_path or 'None (isolated within module)'}\n"
        f"{avoid_str}\n"
        "Return a JSON object with:\n"
        '{\n'
        '  "title": "<short descriptive NEW feature title>",\n'
        '  "description": "<clear description of the NEW feature/behaviour rule and expected CLI/API contract>",\n'
        '  "target_symbols": ["<1-3 real public symbol names from the module that will be extended or referenced>"]\n'
        '}\n'
    )

    model_env = getattr(llm_cfg, "planner_model_env", llm_cfg.model_env)
    data = call_llm(
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider_env=llm_cfg.provider_env,
        model_env=model_env,
        ledger=ledger,
        cache_dir=cache_dir,
        max_tokens=4096,
        temperature=llm_cfg.temperature,
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

    Guarantees:
    - Each (module, axis, partner) cell is unique.
    - Tasks span distinct modules and distinct axes first (max 2 tasks per module).
    """
    target_n = n_tasks or cfg.generation.n_tasks
    source_modules = _select_source_modules(repo_map)
    if not source_modules:
        source_modules = [m for m in repo_map if "test" not in m.path.lower()] or repo_map

    axes = list(cfg.generation.behaviour_axes)
    seen_cells: set[tuple[str, str, str | None]] = set()
    module_counts: dict[str, int] = {}
    used_axes: set[str] = set()
    grid_plans: list[TaskPlan] = []
    prior_titles: list[str] = []

    console.print(
        f"[bold]Building coverage grid[/bold]: targeting {target_n} tasks across "
        f"{len(source_modules)} modules and {len(axes)} axes (max 2 per module, distinct axes)"
    )

    plan_idx = 1
    # Round 1: distinct modules & distinct axes across sorted module list; allow round 2 (up to max 2/module)
    for round_idx in range(2):
        for mod_i, module in enumerate(source_modules):
            if len(grid_plans) >= target_n:
                break
            if module_counts.get(module.path, 0) >= 2:
                continue

            # Pick first unused axis for this round (wrap only if target_n > len(axes))
            chosen_axis: str | None = None
            for offset in range(len(axes)):
                ax = axes[(mod_i + round_idx * 3 + offset) % len(axes)]
                if len(used_axes) < len(axes):
                    if ax not in used_axes:
                        chosen_axis = ax
                        break
                else:
                    chosen_axis = ax
                    break
            if chosen_axis is None:
                continue

            partner: FileSymbols | None = None
            if len(source_modules) > 1 and (mod_i + round_idx) % 2 == 1:
                partner_idx = (mod_i + 1) % len(source_modules)
                if source_modules[partner_idx].path != module.path:
                    partner = source_modules[partner_idx]

            partner_path = partner.path if partner else None
            cell_key = (module.path, chosen_axis, partner_path)
            if cell_key in seen_cells:
                continue

            seen_cells.add(cell_key)
            used_axes.add(chosen_axis)
            module_counts[module.path] = module_counts.get(module.path, 0) + 1
            plan_id = f"task_{plan_idx:03d}_{Path(module.path).stem}_{chosen_axis[:12]}"

            console.print(
                f"  Planning {plan_id}: [cyan]{module.path}[/cyan] × "
                f"[magenta]{chosen_axis}[/magenta] (partner: {partner_path or 'none'})"
            )

            plan = plan_task_with_llm(
                plan_id=plan_id,
                module=module,
                axis=chosen_axis,
                partner=partner,
                llm_cfg=cfg.llm,
                ledger=ledger,
                cache_dir=cfg.output.cache_dir,
                prior_titles=prior_titles,
            )
            prior_titles.append(plan.title)
            grid_plans.append(plan)
            plan_idx += 1

        if len(grid_plans) >= target_n:
            break

    grid = CoverageGrid(plans=grid_plans)
    console.print(f"[green]✓ Generated {len(grid.plans)} unique, grounded plans in coverage grid[/green]")
    return grid
