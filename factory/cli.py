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
    console.print("[bold]tessera profile[/bold]")
    t = Table(show_header=False, box=None)
    t.add_row("repo path",    cfg.repo.path)
    t.add_row("base ref",     cfg.repo.base_ref)
    t.add_row("setup cmd",    cfg.repo.setup_cmd or "(none)")
    t.add_row("test cmd",     cfg.repo.test_cmd  or "(not set — required)")
    t.add_row("docker image", cfg.repo.docker_image or "(not set — will build)")
    t.add_row("result fmt",   cfg.repo.result_format)
    t.add_row("timeout",      f"{cfg.repo.timeout_s}s")
    console.print(t)
    console.print("[yellow]⏳ repo.py not yet built — waiting for stand-in repo approval.[/yellow]")


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
) -> None:
    """Clean-room re-validation of one Harbor task package (G1–G4, G6)."""
    _load(config)
    console.print(f"[bold]tessera verify[/bold] — {package_path}")
    if not package_path.exists():
        console.print(f"[red]✗ Package path does not exist: {package_path}[/red]")
        raise typer.Exit(code=1)
    required = ["instruction.md", "task.toml", "solution/solve.sh", "tests/test.sh"]
    for fname in required:
        exists = (package_path / fname).exists()
        mark = "[green]✓[/green]" if exists else "[red]✗[/red]"
        console.print(f"  {mark} {fname}")
    console.print("[yellow]⏳ Full verify not yet built.[/yellow]")


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
