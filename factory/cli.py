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
    """Plan, generate, validate (G1–G7), and package N tasks. Resumable."""
    cfg = _load(config)
    label = f"resuming {run_id}" if run_id else f"new run, targeting {n} tasks"
    console.print(f"[bold]tessera run[/bold] — {label}")
    console.print(f"  axes: {', '.join(cfg.generation.behaviour_axes)}")
    console.print(f"  max repairs per task: {cfg.generation.max_repairs}")
    console.print(f"  gate order: G1→G2→G3→G4→G5→G6→G7 (stop at first failure)")
    console.print("[yellow]⏳ Pipeline not yet built.[/yellow]")


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
