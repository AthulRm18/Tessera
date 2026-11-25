"""Tessera CLI — `tessera` and `tess` entry points.

No repo names, paths, or language assumptions here — all driven by config.yaml.
Supports resumable runs, `--replay` mode via committed LLM cache, and full G1–G7 + N1 + Harbor validation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from factory.config import FactoryConfig, load_config

app = typer.Typer(
    name="tessera",
    help=(
        "Tessera — turn a codebase into validated coding tasks for evaluating AI.\n\n"
        "Only ships tasks that pass proof (G1–G7, N1, and Harbor nop/oracle)."
    ),
    no_args_is_help=True,
)
console = Console()


def _resolve_config_path(config: str) -> str:
    if Path(config).exists():
        return config
    if config == "config.yaml" and Path("configs/click.yaml").exists():
        return "configs/click.yaml"
    return config


def _load(config_path: str) -> FactoryConfig:
    resolved = _resolve_config_path(config_path)
    cfg = load_config(resolved)
    console.print(f"[dim]config: {resolved} | repo: {cfg.repo.path} | n_tasks: {cfg.generation.n_tasks}[/dim]")
    return cfg


def _check_distinctness_matrix(
    accepted_task_dirs: list[tuple[str, Path, Path]],
    cfg: FactoryConfig,
) -> dict[str, Any]:
    """Run each accepted task's feature tests against every other accepted task's patch."""
    if len(accepted_task_dirs) < 2:
        return {"checked": False, "reason": "Fewer than 2 accepted tasks"}

    import shutil
    import tempfile
    from factory.gates import _run_feature_tests, GateContext
    from factory.repo import apply_patch, create_worktree, remove_worktree

    console.print("\n[bold]5. Cross-task behavioural distinctness check[/bold]")
    repo_root = Path(cfg.repo.path).resolve()
    matrix: dict[str, dict[str, bool]] = {}
    distinct = True

    for patch_id, patch_path, _ in accepted_task_dirs:
        matrix[patch_id] = {}
        parent = Path(tempfile.mkdtemp(prefix="tessera_dist_"))
        wt: Path | None = None
        try:
            wt = create_worktree(repo_root, cfg.repo.base_ref, "dist_wt", parent_dir=parent)
            apply_patch(patch_path, wt)
            for test_id, _, test_path in accepted_task_dirs:
                ctx = GateContext(
                    repo_path=repo_root,
                    base_commit=cfg.repo.base_ref,
                    patch_path=patch_path,
                    feature_test_paths=[test_path],
                    regression_test_paths=[],
                    test_cmd=cfg.repo.test_cmd,
                    result_format=cfg.repo.result_format,
                    timeout_s=cfg.repo.timeout_s,
                )
                tr = _run_feature_tests(ctx, wt)
                passed = tr.passed and tr.n_failed == 0
                matrix[patch_id][test_id] = passed
                if patch_id == test_id and not passed:
                    distinct = False
                elif patch_id != test_id and passed:
                    distinct = False
        finally:
            if wt is not None:
                try:
                    remove_worktree(repo_root, wt)
                except Exception:
                    pass
            shutil.rmtree(parent, ignore_errors=True)

    color = "green" if distinct else "red"
    console.print(f"  [{color}]Distinctness diagonal={distinct}: {matrix}[/{color}]")
    return {"checked": True, "distinct": distinct, "matrix": matrix}


# ── profile ────────────────────────────────────────────────────────────────

@app.command()
def profile(
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml"),
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
    n: int = typer.Option(5, "-n", help="Number of candidate tasks to plan and run"),
    run_id: str = typer.Option("", "--run-id", help="Resume an existing run id"),
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml"),
    replay: bool = typer.Option(False, "--replay", help="Replay deterministically from cached LLM responses without API keys"),
    cache_dir: str = typer.Option("", "--cache-dir", help="Override LLM disk cache directory (useful with --replay)"),
) -> None:
    """Plan, generate, validate (G1–G7, N1, Harbor nop/oracle), and package N tasks. Resumable."""
    import time
    from datetime import datetime
    from factory.generator import BudgetExceededError, generate_and_validate_task
    from factory.llm import UsageLedger
    from factory.packager import update_manifest
    from factory.planner import build_coverage_grid
    from factory.repo import build_symbol_repo_map, capture_baseline_pass_to_pass, run_tests

    if replay:
        os.environ["TESSERA_REPLAY"] = "1"
        console.print("[bold yellow]REPLAY MODE ENABLED (TESSERA_REPLAY=1): reading cached LLM responses only[/bold yellow]")

    start_time = time.time()
    cfg = _load(config)
    if cache_dir:
        cfg.output.cache_dir = cache_dir

    rid = run_id or datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    run_dir = Path(cfg.output.runs_dir) / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]tessera run[/bold] — run_id: [cyan]{rid}[/cyan] (targeting {n} tasks)")
    console.print(f"  repo: {cfg.repo.path} (base_ref: {cfg.repo.base_ref})")
    console.print(f"  behaviour axes: {', '.join(cfg.generation.behaviour_axes)}")
    console.print(f"  max repairs per task: {cfg.generation.max_repairs}")
    console.print(f"  budget limits: max {cfg.budget.max_tokens_per_run:,} tokens, max estimated ${cfg.budget.max_cost_per_run:.2f} (run) / ${cfg.budget.max_cost_per_task:.2f} (task)")

    ledger = UsageLedger(ledger_path=run_dir / "ledger.json")

    # 1. Baseline verification on base repo
    console.print("\n[bold]1. Verifying baseline tests & capturing pass_to_pass nodes...[/bold]")
    baseline = run_tests(Path(cfg.repo.path), cfg.repo.test_cmd, cfg.repo.timeout_s, cfg.repo.result_format)
    if not baseline.passed:
        console.print(f"[red bold]✗ Baseline tests failed ({baseline.n_failed} failed)[/red bold]")
        raise typer.Exit(code=1)
    console.print(f"  [green]✓ Clean baseline passed: {baseline.n_passed} tests in {baseline.duration_s:.2f}s[/green]")

    p2p_cache_file = run_dir / "pass_to_pass.json"
    if p2p_cache_file.exists():
        pass_to_pass = json.loads(p2p_cache_file.read_text(encoding="utf-8"))
        console.print(f"  [cyan]Resuming:[/cyan] loaded {len(pass_to_pass)} pass_to_pass node IDs")
    else:
        pass_to_pass = capture_baseline_pass_to_pass(
            repo_path=cfg.repo.path,
            base_commit=cfg.repo.base_ref,
            test_cmd=cfg.repo.test_cmd,
            docker_image=cfg.repo.docker_image,
            timeout_s=cfg.repo.timeout_s + 60,
        )
        p2p_cache_file.write_text(json.dumps(pass_to_pass, indent=2) + "\n", encoding="utf-8", newline="\n")
        console.print(f"  [green]✓ Derived {len(pass_to_pass)} pass_to_pass node IDs from real baseline run[/green]")

    # 2. Build or load repo map
    console.print("\n[bold]2. Mapping repository symbols...[/bold]")
    repo_map = build_symbol_repo_map(Path(cfg.repo.path))
    console.print(f"  [green]✓ Mapped {len(repo_map)} files across repository[/green]")

    # 3. Planning: Coverage Grid
    grid_file = run_dir / "coverage_grid.json"
    if grid_file.exists():
        console.print(f"  [cyan]Resuming:[/cyan] loading existing coverage grid from {grid_file.name}")
        from factory.schemas import CoverageGrid
        grid = CoverageGrid.model_validate_json(grid_file.read_text(encoding="utf-8"))
    else:
        console.print("\n[bold]3. Generating coverage grid...[/bold]")
        grid = build_coverage_grid(repo_map, cfg, n_tasks=n, ledger=ledger)
        grid_file.write_text(grid.model_dump_json(indent=2), encoding="utf-8", newline="\n")

    # 4. Generation and validation loop
    console.print(f"\n[bold]4. Generating and validating up to {n} candidate tasks...[/bold]")
    accepted_count = 0
    rejected_count = 0
    accepted_tasks: list[str] = []
    rejected_tasks: list[str] = []
    accepted_artifacts: list[tuple[str, Path, Path]] = []

    try:
        for plan in grid.plans[:n]:
            accepted, pkg_path, _ = generate_and_validate_task(
                plan=plan,
                cfg=cfg,
                run_id=rid,
                baseline=baseline,
                ledger=ledger,
                pass_to_pass=pass_to_pass,
            )
            if accepted and pkg_path is not None:
                accepted_count += 1
                accepted_tasks.append(plan.plan_id)
                test_files = list((pkg_path / "tests" / "feature").glob("test_*.py"))
                if test_files:
                    accepted_artifacts.append((plan.plan_id, pkg_path / "solution" / "reference.patch", test_files[0]))
            else:
                rejected_count += 1
                rejected_tasks.append(plan.plan_id)

    except BudgetExceededError as e:
        console.print(f"\n[red bold]⚠ Hard Budget Limit Reached:[/red bold] {e}")

    distinctness = _check_distinctness_matrix(accepted_artifacts, cfg)
    update_manifest(cfg.output.packages_dir)

    wall_time = time.time() - start_time
    summary = ledger.summary()

    # 5. Run Summary
    run_summary = {
        "run_id": rid,
        "replay": replay,
        "repo": cfg.repo.path,
        "base_commit": cfg.repo.base_ref,
        "n_targeted": n,
        "accepted": accepted_count,
        "rejected": rejected_count,
        "accepted_tasks": accepted_tasks,
        "rejected_tasks": rejected_tasks,
        "distinctness": distinctness,
        "wall_time_s": round(wall_time, 2),
        "total_calls": summary["total_calls"],
        "cache_hits": summary["cache_hits"],
        "total_input_tokens": summary["total_input_tokens"],
        "total_output_tokens": summary["total_output_tokens"],
        "total_tokens": summary["total_input_tokens"] + summary["total_output_tokens"],
        "estimated_cost_usd": summary["estimated_cost_usd"],
    }

    (run_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8", newline="\n")

    console.print("\n" + "=" * 60)
    console.print(f"[bold]RUN COMPLETE — SUMMARY ({rid})[/bold]")
    console.print(f"  Accepted tasks : [green bold]{accepted_count}[/green bold]")
    console.print(f"  Rejected tasks : [red bold]{rejected_count}[/red bold]")
    console.print(f"  Wall time      : {wall_time:.2f}s")
    console.print(f"  Total tokens   : {summary['total_input_tokens'] + summary['total_output_tokens']:,} (in: {summary['total_input_tokens']:,}, out: {summary['total_output_tokens']:,})")
    console.print(f"  Estimated cost : ${summary['estimated_cost_usd']:.4f} USD (estimated)")
    console.print(f"  Cache hits     : {summary['cache_hits']} / {summary['total_calls']}")
    console.print("=" * 60 + "\n")


# ── verify ─────────────────────────────────────────────────────────────────

@app.command()
def verify(
    package_path: Path = typer.Argument(..., help="Path to a Harbor task package folder"),
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml"),
    quick: bool = typer.Option(False, "--quick", help="Skip 3-run determinism check (1 run only)"),
    native: bool = typer.Option(False, "--native", help="Run native verification instead of container verification"),
) -> None:
    """Clean-room re-validation of one Harbor task package (G1–G4 / Harbor)."""
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
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml"),
) -> None:
    """Aggregate real metrics from run logs. Never fabricates numbers."""
    cfg = _load(config)
    runs_dir = Path(cfg.output.runs_dir)
    console.print(f"[bold]tessera report[/bold] — scanning {runs_dir}")
    if not runs_dir.exists():
        console.print("[yellow]No runs directory yet — run 'tessera run' first.[/yellow]")
        raise typer.Exit(code=0)
    for summary_file in sorted(runs_dir.glob("*/run_summary.json")):
        console.print(f"\n[cyan]{summary_file}[/cyan]")
        console.print(summary_file.read_text(encoding="utf-8"))


# ── demo ───────────────────────────────────────────────────────────────────

@app.command()
def demo(
    replay: bool = typer.Option(False, "--replay", help="Replay a real cached run (clearly labelled)"),
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml"),
) -> None:
    """Live generate+validate demo (`tessera run -n 2`)."""
    run(n=2, run_id="", config=config, replay=replay, cache_dir="")


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
