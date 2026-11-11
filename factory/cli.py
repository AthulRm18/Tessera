"""Typer CLI — all commands stubbed, wired to real modules as they are built."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from factory.config import FactoryConfig, load_config

app = typer.Typer(
    name="factory",
    help="Coding Task Factory — generate solvable, testable coding tasks.",
    no_args_is_help=True,
)
console = Console()


def _load(config_path: str) -> FactoryConfig:
    """Load config and print a summary line."""
    cfg = load_config(config_path)
    console.print(f"[dim]config loaded from {config_path}[/dim]")
    return cfg


# ── profile ────────────────────────────────────────────────────────────────

@app.command()
def profile(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Detect stack, run baseline tests, build repo map."""
    cfg = _load(config)
    console.print("[bold]factory profile[/bold]")
    console.print(f"  repo path : {cfg.repo.path}")
    console.print(f"  base ref  : {cfg.repo.base_ref}")
    console.print(f"  test cmd  : {cfg.repo.test_cmd or '(not set)'}")
    console.print("[yellow]⏳ repo.py not yet implemented — waiting for target repo stack confirmation.[/yellow]")


# ── run ────────────────────────────────────────────────────────────────────

@app.command()
def run(
    n: int = typer.Option(10, "-n", help="Number of tasks to generate"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Plan, generate, validate, and package N tasks."""
    cfg = _load(config)
    console.print(f"[bold]factory run[/bold] — planning {n} tasks")
    console.print(f"  axes      : {', '.join(cfg.generation.behaviour_axes)}")
    console.print(f"  max repairs: {cfg.generation.max_repairs}")
    console.print("[yellow]⏳ Planner, generator, and gates not yet implemented.[/yellow]")


# ── verify ─────────────────────────────────────────────────────────────────

@app.command()
def verify(
    package_path: Path = typer.Argument(..., help="Path to a task package folder"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Clean-room re-validation of one package."""
    _load(config)
    console.print(f"[bold]factory verify[/bold] — {package_path}")
    if not package_path.exists():
        console.print(f"[red]✗ Package path does not exist: {package_path}[/red]")
        raise typer.Exit(code=1)
    console.print("[yellow]⏳ Verify not yet implemented.[/yellow]")


# ── report ─────────────────────────────────────────────────────────────────

@app.command()
def report(
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Aggregate real metrics from run logs."""
    cfg = _load(config)
    runs_dir = Path(cfg.output.runs_dir)
    console.print(f"[bold]factory report[/bold] — scanning {runs_dir}")
    if not runs_dir.exists():
        console.print("[red]✗ No runs directory found. Run 'factory run' first.[/red]")
        raise typer.Exit(code=1)
    console.print("[yellow]⏳ Report not yet implemented.[/yellow]")


# ── demo ───────────────────────────────────────────────────────────────────

@app.command()
def demo(
    replay: bool = typer.Option(False, "--replay", help="Replay a cached run"),
    config: str = typer.Option("config.yaml", help="Path to config.yaml"),
) -> None:
    """Live generate+validate one package (or replay a cached run)."""
    _load(config)
    mode = "replay" if replay else "live"
    console.print(f"[bold]factory demo[/bold] — mode: {mode}")
    console.print("[yellow]⏳ Demo not yet implemented.[/yellow]")


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
