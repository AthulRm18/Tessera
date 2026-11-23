"""Tessera CLI — `tessera` and `tess` entry points.

Commands are stubbed and replaced with real implementations as each module is built.
No repo names, paths or language assumptions here — all from config.yaml.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from factory.config import FactoryConfig, load_config

app = typer.Typer(
    name="tessera",
    help=(
        "Tessera — turn a codebase into validated coding tasks for evaluating AI.\n\n"
        "Only ships tasks that pass proof (G1–G7 validation gates)."
    ),
    no_args_is_help=True,
)
console = Console()


def _load(config_path: str) -> FactoryConfig:
    """Load config and print a one-line summary."""
    cfg = load_config(config_path)
    console.print(f"[dim]config: {config_path} | repo: {cfg.repo.path} | n_tasks: {cfg.generation.n_tasks}[/dim]")
    return cfg


# ── profile ────────────────────────────────────────────────────────────────

@app.command()
def profile(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Detect stack, run baseline tests, build repo map. Baseline MUST be green."""
    cfg = _load(config)
    from factory.repo import profile_repo, save_profile

    prof = profile_repo(cfg)
    out_dir = Path(cfg.output.runs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_profile(prof, out_dir / "profile.json")


# ── run ────────────────────────────────────────────────────────────────────

@app.command()
def run(
    n: int = typer.Option(6, "-n", help="Number of tasks to attempt (target: 5–6 strong)"),
    run_id: str = typer.Option("", "--run-id", help="Resume an existing run id"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Plan, generate, validate (G1–G4), and package N tasks. Resumable."""
    import time
    from datetime import datetime
    from factory.generator import BudgetExceededError, generate_and_validate_task
    from factory.llm import UsageLedger
    from factory.planner import build_coverage_grid
    from factory.repo import build_symbol_repo_map, run_tests

    start_time = time.time()
    cfg = _load(config)
    rid = run_id or datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    run_dir = Path(cfg.output.runs_dir) / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]tessera run[/bold] — run_id: [cyan]{rid}[/cyan] (targeting {n} tasks)")
    console.print(f"  repo: {cfg.repo.path} (base_ref: {cfg.repo.base_ref})")
    console.print(f"  behaviour axes: {', '.join(cfg.generation.behaviour_axes)}")
    console.print(f"  max repairs per task: {cfg.generation.max_repairs}")
    console.print(f"  budget limits: max {cfg.budget.max_tokens_per_run:,} tokens, max ${cfg.budget.max_cost_per_run:.2f}")

    ledger = UsageLedger(ledger_path=run_dir / "ledger.json")

    # 1. Baseline verification on base repo
    console.print("\n[bold]1. Verifying baseline tests on base repository...[/bold]")
    baseline = run_tests(Path(cfg.repo.path), cfg.repo.test_cmd, cfg.repo.timeout_s, cfg.repo.result_format)
    if not baseline.passed:
        console.print(f"[red bold]✗ Baseline tests failed ({baseline.n_failed} failed)[/red bold]")
        raise typer.Exit(code=1)
    console.print(f"  [green]✓ Clean baseline passed: {baseline.n_passed} tests in {baseline.duration_s:.2f}s[/green]")

    # 2. Build or load repo map
    console.print("\n[bold]2. Mapping repository symbols...[/bold]")
    repo_map = build_symbol_repo_map(Path(cfg.repo.path))
    console.print(f"  [green]✓ Mapped {len(repo_map)} files across repository[/green]")

    # 3. Planning: Coverage Grid
    grid_file = run_dir / "coverage_grid.json"
    if grid_file.exists():
        console.print(f"  [cyan]Resuming:[/cyan] loading existing coverage grid from {grid_file.name}")
        from factory.schemas import CoverageGrid
        with open(grid_file, encoding="utf-8") as f:
            grid = CoverageGrid.model_validate_json(f.read())
    else:
        console.print("\n[bold]3. Generating coverage grid...[/bold]")
        grid = build_coverage_grid(repo_map, cfg, n_tasks=n, ledger=ledger)
        with open(grid_file, "w", encoding="utf-8") as f:
            f.write(grid.model_dump_json(indent=2))

    # 4. Generation and validation loop
    console.print(f"\n[bold]4. Generating and validating up to {n} candidate tasks...[/bold]")
    accepted_count = 0
    rejected_count = 0
    accepted_tasks: list[str] = []
    rejected_tasks: list[str] = []

    try:
        for plan in grid.plans[:n]:
            accepted, pkg_path, report = generate_and_validate_task(
                plan=plan,
                cfg=cfg,
                run_id=rid,
                baseline=baseline,
                ledger=ledger,
            )
            if accepted:
                accepted_count += 1
                accepted_tasks.append(plan.plan_id)
            else:
                rejected_count += 1
                rejected_tasks.append(plan.plan_id)

    except BudgetExceededError as e:
        console.print(f"\n[red bold]⚠ Hard Budget Limit Reached:[/red bold] {e}")

    wall_time = time.time() - start_time
    summary = ledger.summary()

    # 5. Run Summary
    run_summary = {
        "run_id": rid,
        "repo": cfg.repo.path,
        "base_commit": cfg.repo.base_ref,
        "n_targeted": n,
        "accepted": accepted_count,
        "rejected": rejected_count,
        "accepted_tasks": accepted_tasks,
        "rejected_tasks": rejected_tasks,
        "wall_time_s": round(wall_time, 2),
        "total_calls": summary["total_calls"],
        "cache_hits": summary["cache_hits"],
        "total_input_tokens": summary["total_input_tokens"],
        "total_output_tokens": summary["total_output_tokens"],
        "total_tokens": summary["total_input_tokens"] + summary["total_output_tokens"],
        "estimated_cost_usd": summary["estimated_cost_usd"],
    }

    with open(run_dir / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2)

    console.print("\n" + "=" * 60)
    console.print(f"[bold]RUN COMPLETE — SUMMARY ({rid})[/bold]")
    console.print(f"  Accepted tasks : [green bold]{accepted_count}[/green bold]")
    console.print(f"  Rejected tasks : [red bold]{rejected_count}[/red bold]")
    console.print(f"  Wall time      : {wall_time:.2f}s")
    console.print(f"  Total tokens   : {summary['total_input_tokens'] + summary['total_output_tokens']:,} (in: {summary['total_input_tokens']:,}, out: {summary['total_output_tokens']:,})")
    console.print(f"  Estimated cost : ${summary['estimated_cost_usd']:.4f} USD")
    console.print(f"  Cache hits     : {summary['cache_hits']} / {summary['total_calls']}")
    console.print("=" * 60 + "\n")


# ── verify ─────────────────────────────────────────────────────────────────

@app.command()
def verify(
    package_path: Path = typer.Argument(..., help="Path to a Harbor task package folder"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
    quick: bool = typer.Option(False, "--quick", help="Skip 3-run determinism check (1 run only)"),
    native: bool = typer.Option(False, "--native", help="Run native verification instead of container verification"),
) -> None:
    """Clean-room re-validation of one Harbor task package (G1–G4).
    
    Uses container verification by default; use --native for local worktree verification.
    """
    cfg = _load(config)
    if not package_path.exists():
        console.print(f"[red]✗ Package path does not exist: {package_path}[/red]")
        raise typer.Exit(code=1)

    from factory.verify import verify_package

    res = verify_package(package_path, cfg, native=native, check_determinism=not quick)
    if not res.passed:
        console.print(f"[red bold]✗ Verification failed for {package_path.name}[/red bold]")
        raise typer.Exit(code=1)


# ── report ─────────────────────────────────────────────────────────────────

@app.command()
def report(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Aggregate real metrics from run logs. Never fabricates numbers."""
    cfg = _load(config)
    runs_dir = Path(cfg.output.runs_dir)
    console.print(f"[bold]tessera report[/bold] — scanning {runs_dir}")
    if not runs_dir.exists():
        console.print("[yellow]No runs directory yet — run 'tessera run' first.[/yellow]")
        raise typer.Exit(code=0)
    console.print("[yellow]⏳ Report not yet built.[/yellow]")


# ── demo ───────────────────────────────────────────────────────────────────

@app.command()
def demo(
    replay: bool = typer.Option(False, "--replay", help="Replay a real cached run (clearly labelled)"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Live generate+validate one package; shows three organizer checks and ≥1 real rejection."""
    _load(config)
    if replay:
        console.print("[bold]tessera demo --replay[/bold] [yellow](REPLAY of real earlier run — not live)[/yellow]")
    else:
        console.print("[bold]tessera demo[/bold] [cyan](live)[/cyan]")
    console.print("  Organizer checks shown explicitly:")
    console.print("    (a) original repo works as-is")
    console.print("    (b) tests pass with the implementation")
    console.print("    (c) tests fail when the feature is absent")
    console.print("[yellow]⏳ Demo not yet built.[/yellow]")


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
