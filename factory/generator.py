"""Task generator & full gate validation orchestrator.

Gate order (cheapest first, fail fast):
1. G1: Clean apply + syntax compile
2. Pre-check (G2 F2P, G3 P2P, G4 determinism)
3. G5: Traceability & interface completeness
4. G6: Scoped container mutation (added src/ lines only; survivors trigger repair)
5. Harbor 0.25.x packaging + Official `harbor run` `nop` (0.0) & `oracle` (1.0)
6. N1: Upstream-novelty check against live fetched default branch
7. G7: Independent solver using distinct capable model (sees ONLY instruction.md + base repo)

Supports resumable stages under `runs/<run_id>/<task_id>/`, max 2 automated repairs,
hard run/task budget guards, and automatic `fail_to_pass.json` / `pass_to_pass.json` extraction.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.config import FactoryConfig
from factory.gates import GateContext, run_g1, run_g2, run_g3, run_g4
from factory.gates_advanced import run_g5_traceability, run_g6_mutation, run_g7_solver, run_n1_upstream_novelty
from factory.llm import UsageLedger, call_llm
from factory.packager import package_task
from factory.repo import TestResult
from factory.schemas import (
    AcceptanceCriterion,
    TaskMetadata,
    TaskPlan,
    ValidationReport,
)

console = Console()


class BudgetExceededError(Exception):
    """Raised when token or estimated cost budget limit is reached."""


def check_budget_guard(
    cfg: FactoryConfig,
    ledger: UsageLedger,
    task_tokens: int = 0,
    task_cost: float = 0.0,
) -> None:
    """Check run-level and task-level budget limits; raises BudgetExceededError if exceeded."""
    run_tokens = ledger.total_input_tokens + ledger.total_output_tokens
    if run_tokens >= cfg.budget.max_tokens_per_run:
        raise BudgetExceededError(
            f"Run token budget reached: {run_tokens} >= {cfg.budget.max_tokens_per_run}"
        )
    if ledger.total_cost_usd >= cfg.budget.max_cost_per_run:
        raise BudgetExceededError(
            f"Run cost budget reached: estimated ${ledger.total_cost_usd:.4f} >= ${cfg.budget.max_cost_per_run:.2f}"
        )
    if task_tokens >= cfg.budget.max_tokens_per_task:
        raise BudgetExceededError(
            f"Task token budget reached: {task_tokens} >= {cfg.budget.max_tokens_per_task}"
        )
    if task_cost >= cfg.budget.max_cost_per_task:
        raise BudgetExceededError(
            f"Task cost budget reached: estimated ${task_cost:.4f} >= ${cfg.budget.max_cost_per_task:.2f}"
        )


REQUIREMENTS_SYSTEM_PROMPT = """You are a senior technical specifications writer creating coding benchmark tasks for evaluating AI coding systems.
Write clear, unambiguous, achievable requirements for a NEW feature or behaviour extension to an existing repository.
Strict rules:
1. Include a numbered list of Acceptance Criteria (AC1, AC2, AC3, ...).
2. Include a thorough `Interface` specification listing EVERY public symbol name, exact signature, parameter names/types, defaults, return types, and the EXACT error/exception strings or CLI output formats that automated tests will assert against.
3. Explicitly specify that the entire existing repository test suite must continue passing without regression (avoid adding top-level eager stdlib imports if the repository restricts startup imports).
4. Include an `Out of Scope` section bounding the task.
5. Absolutely NO implementation hints, pseudocode, solution code snippets, or file diffs. Specify WHAT, never HOW.
6. Respond ONLY with a valid JSON object:
{
  "title": "<task title>",
  "problem_description": "<clear description of the feature and rationale>",
  "acceptance_criteria": [
    {"id": "AC1", "text": "<criterion 1>"},
    {"id": "AC2", "text": "<criterion 2>"}
  ],
  "interface": {
    "symbols": ["<symbol1>", "<symbol2>"],
    "details": "<exact signatures, parameter defaults, return values, and exact error/output templates>"
  },
  "out_of_scope": "<boundaries and exclusions>"
}
"""

IMPLEMENTATION_SYSTEM_PROMPT = """You are an expert software developer and test engineer.
Given a repository module (plus package exports & test style example) and `instruction.md`:
Produce:
1. Search-and-replace edit blocks ONLY on `src/` files using exact verbatim lines from the supplied source (our tooling applies them cleanly and generates `git diff`).
   - NEVER modify existing test files.
   - Respect lightweight module import rules (lazy-import any new stdlib modules inside functions/methods rather than at module top-level).
2. Comprehensive pytest feature tests verifying EVERY numbered acceptance criterion.
   - Tag every test function directly with its criterion ID comment immediately above `def test_...` (e.g., `# AC1`).
   - Follow Click's testing style (`import click`, `from click.testing import CliRunner`, `pytest.raises`).
   - CRITICAL: Do NOT fail pytest collection when the feature is absent on the base commit! Look up newly added symbols inside each test body (e.g. `assert hasattr(click, "...")` or inner `from ... import ...`) rather than top-level module imports of brand-new symbols. That ensures collection succeeds and each test FAILS cleanly on the base commit with `AssertionError` / `AttributeError` / `ImportError`.
   - Assert observable behaviour, exact specified error messages, and contracts (NEVER private internal attributes). Include 2-5 inline edge/adjacent assertions.

Format your response using these exact delimiter tags (do NOT wrap inside JSON):

<<<TEST_FILENAME>>>
test_feature_name.py
<<<END_TEST_FILENAME>>>

<<<EDIT file="src/path/to/file.py">>>
<<<FIND>>>
exact existing source lines copied verbatim
<<<END_FIND>>>
<<<REPLACE>>>
new replacement source lines
<<<END_REPLACE>>>
<<<END_EDIT>>>

<<<TEST_CODE>>>
from __future__ import annotations
...
<<<END_TEST_CODE>>>
"""

REPAIR_SYSTEM_PROMPT = """You are an expert software developer and test engineer repairing a benchmark task that failed an automated gate.
Review the exact gate failure feedback (e.g. edit mismatch, fail-to-pass error, regression failure, traceability gap, or surviving mutation lines), `instruction.md`, previous patch, and previous tests.
Fix the edits and/or tests (keeping `instruction.md` contracts exact and consistent) so that:
1. All `<<<EDIT>>>` blocks match verbatim base lines in `src/` ONLY (or provide a complete corrected unified diff).
2. Feature tests collect cleanly without collection-time ImportError on base repo, FAIL on base repo, and PASS on patched repo.
3. Zero baseline regression tests fail (watch out for Click's `test_light_imports` startup import checks!).
4. Every AC (`AC1`..) has a `# ACn` tagged test, and tests kill code mutants (strengthen assertions if mutants survived!).

Format your response using these exact delimiter tags (do NOT wrap inside JSON):

<<<NOTES>>>
Summary of fixes made
<<<END_NOTES>>>

<<<EDIT file="src/path/to/file.py">>>
<<<FIND>>>
exact existing base lines
<<<END_FIND>>>
<<<REPLACE>>>
replacement lines
<<<END_REPLACE>>>
<<<END_EDIT>>>

<<<TEST_CODE>>>
from __future__ import annotations
...
<<<END_TEST_CODE>>>
"""


def _extract_tagged_sections(
    raw_content: str,
    fallback_filename: str,
    repo_path: Path | None = None,
    base_commit: str = "",
    fallback_patch: str = "",
) -> tuple[str, str, str]:
    """Extract/synthesize patch, test_code, and optional filename from edit/patch blocks."""
    def _between(tag: str) -> str | None:
        m = re.search(rf"<<<{tag}>>>\s*(.*?)\s*<<<END_{tag}>>>", raw_content, re.DOTALL)
        return m.group(1) if m else None

    test_code = _between("TEST_CODE")
    fname = _between("TEST_FILENAME")
    patch = ""

    if repo_path is not None and base_commit and "<<<EDIT" in raw_content:
        from factory.repo import synthesize_patch_from_response
        ok, synth_patch, err = synthesize_patch_from_response(repo_path, base_commit, raw_content)
        if ok:
            patch = synth_patch
        else:
            console.print(f"  [yellow]Edit synthesis note:[/yellow] {err}")

    if not patch:
        p_raw = _between("PATCH")
        if p_raw is not None:
            patch = _clean_diff_text(p_raw)
        elif test_code is None:
            try:
                obj = json.loads(raw_content, strict=False)
                patch = _clean_diff_text(str(obj.get("patch", "")))
                test_code = str(obj.get("test_code", ""))
                fname = obj.get("test_filename", fallback_filename)
            except Exception:
                patch = fallback_patch
        else:
            patch = fallback_patch

    return (
        patch,
        (test_code or "").strip().replace("\r\n", "\n") + "\n",
        (fname or fallback_filename).strip(),
    )


def _read_repo_context(repo_path: Path, rel_path: str, max_chars: int = 55000) -> str:
    p = repo_path / rel_path
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        half = max_chars // 2
        return text[:half] + "\n\n# ... [middle omitted for size] ...\n\n" + text[-half:]
    return text


def generate_requirements(
    plan: TaskPlan,
    module_code: str,
    cfg: FactoryConfig,
    ledger: UsageLedger,
    task_dir: Path,
) -> tuple[str, list[AcceptanceCriterion], list[str]]:
    """Stage 1: Generate requirements.md (`instruction.md`) with ACs and exact Interface contract."""
    req_file = task_dir / "requirements.md"
    meta_file = task_dir / "requirements_meta.json"

    if req_file.exists() and meta_file.exists():
        console.print(f"  [cyan]Resuming Stage 1:[/cyan] requirements loaded from {task_dir.name}")
        with open(meta_file, encoding="utf-8") as f:
            data = json.load(f)
            criteria = [AcceptanceCriterion(**c) for c in data.get("criteria", [])]
            symbols = data.get("symbols", [])
            return req_file.read_text(encoding="utf-8"), criteria, symbols

    check_budget_guard(cfg, ledger)

    prompt = (
        f"Task Title: {plan.title}\n"
        f"Target Module: {plan.module}\n"
        f"Target Symbols: {', '.join(plan.target_symbols)}\n"
        f"Behaviour Axis: {plan.behaviour_axis}\n"
        f"Interaction Partner: {plan.interaction_partner or 'None'}\n"
        f"Problem Summary: {plan.description}\n\n"
        f"Context from existing module ({plan.module}):\n```\n{module_code[:6000]}\n```\n"
    )

    data = call_llm(
        messages=[
            {"role": "system", "content": REQUIREMENTS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider_env=cfg.llm.provider_env,
        model_env=cfg.llm.model_env,
        ledger=ledger,
        cache_dir=cfg.output.cache_dir,
        max_tokens=cfg.llm.max_tokens,
        temperature=cfg.llm.temperature,
        expect_json=True,
    )

    md_text = data.get("markdown_text")
    if not md_text:
        criteria_lines = "\n".join(
            f"- **{c.get('id', f'AC{i}')}**: {c.get('text', '')}"
            for i, c in enumerate(data.get("acceptance_criteria", []), 1)
        )
        iface = data.get("interface", {})
        symbols_str = "\n".join(f"- `{s}`" for s in iface.get("symbols", []))
        details_str = iface.get("details", "")
        out_scope = data.get("out_of_scope", "Do not alter unrelated modules or break existing CLI tests.")
        md_text = (
            f"# {data.get('title', plan.title)}\n\n"
            f"## Problem Description\n\n{data.get('problem_description', plan.description)}\n\n"
            f"## Acceptance Criteria\n\n{criteria_lines}\n\n"
            f"## Interface\n\n### Symbols\n{symbols_str}\n\n### Contract Details\n{details_str}\n\n"
            f"## Compatibility & Out of Scope\n\n{out_scope}\n"
            "- The entire existing repository test suite must continue to pass with zero regressions.\n"
        )

    criteria_raw = data.get("acceptance_criteria", [])
    criteria = [
        AcceptanceCriterion(id=c.get("id", f"AC{i}"), text=c.get("text", str(c)))
        for i, c in enumerate(criteria_raw, 1)
    ] or [AcceptanceCriterion(id="AC1", text=plan.description)]

    symbols = data.get("interface", {}).get("symbols", plan.target_symbols)

    req_file.write_text(md_text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    with open(meta_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"criteria": [c.model_dump() for c in criteria], "symbols": symbols}, f, indent=2)

    return md_text, criteria, symbols


def generate_implementation_and_tests(
    plan: TaskPlan,
    requirements_md: str,
    module_code: str,
    extra_context: str,
    cfg: FactoryConfig,
    ledger: UsageLedger,
    task_dir: Path,
) -> tuple[str, str, str]:
    """Stage 2: Generate reference patch and feature tests."""
    patch_file = task_dir / "reference.patch"
    test_meta_file = task_dir / "test_meta.json"

    if patch_file.exists() and test_meta_file.exists():
        console.print(f"  [cyan]Resuming Stage 2:[/cyan] implementation and tests loaded from {task_dir.name}")
        with open(test_meta_file, encoding="utf-8") as f:
            data = json.load(f)
            test_file = task_dir / data["test_filename"]
            if test_file.exists():
                return patch_file.read_text(encoding="utf-8"), test_file.read_text(encoding="utf-8"), data["test_filename"]

    check_budget_guard(cfg, ledger)

    prompt = (
        f"Task Title: {plan.title}\n"
        f"Module: {plan.module}\n"
        f"Test Framework: {cfg.repo.result_format}\n\n"
        f"Specification (`instruction.md`):\n{requirements_md}\n\n"
        f"Base Source (`{plan.module}`):\n```\n{module_code[:55000]}\n```\n\n"
        f"Additional Repository Context:\n{extra_context[:10000]}\n"
    )

    data = call_llm(
        messages=[
            {"role": "system", "content": IMPLEMENTATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider_env=cfg.llm.provider_env,
        model_env=cfg.llm.model_env,
        ledger=ledger,
        cache_dir=cfg.output.cache_dir,
        max_tokens=cfg.llm.max_tokens,
        temperature=cfg.llm.temperature,
        expect_json=False,
    )

    default_fname = f"test_{plan.plan_id}.py"
    patch, test_code, test_filename = _extract_tagged_sections(
        str(data.get("content", "")),
        default_fname,
        repo_path=Path(cfg.repo.path).resolve(),
        base_commit=cfg.repo.base_ref,
    )
    if test_code.startswith("```"):
        tlines = test_code.splitlines()
        test_code = "\n".join(tlines[1:-1] if tlines and tlines[-1].startswith("```") else tlines[1:]) + "\n"
    if "/" in test_filename or "\\" in test_filename:
        test_filename = Path(test_filename).name
    if not test_filename.startswith("test_"):
        test_filename = f"test_{test_filename}"
    if not test_filename.endswith(".py"):
        test_filename += ".py"

    patch_file.write_text(patch, encoding="utf-8", newline="\n")
    test_path = task_dir / test_filename
    test_path.write_text(test_code.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    with open(test_meta_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"test_filename": test_filename}, f, indent=2)

    return patch, test_code, test_filename


def _clean_diff_text(patch: str) -> str:
    p = patch.strip().replace("\r\n", "\n")
    if p.startswith("```"):
        lines = p.splitlines()
        p = "\n".join(lines[1:-1] if lines and lines[-1].startswith("```") else lines[1:])
    if p and not p.endswith("\n"):
        p += "\n"
    return p


def repair_task(
    plan: TaskPlan,
    requirements_md: str,
    failing_gate: str,
    error_msg: str,
    prev_patch: str,
    prev_test: str,
    test_filename: str,
    module_code: str,
    cfg: FactoryConfig,
    ledger: UsageLedger,
    task_dir: Path,
    repair_idx: int,
) -> tuple[str, str]:
    """Execute one repair iteration with structured gate feedback."""
    check_budget_guard(cfg, ledger)
    console.print(f"  [yellow]Executing repair #{repair_idx}[/yellow] after {failing_gate} failure...")

    prompt = (
        f"Task: {plan.title}\n"
        f"Module: {plan.module}\n"
        f"Failing Gate: {failing_gate}\n"
        f"Gate Failure Feedback:\n{error_msg}\n\n"
        f"Specification (`instruction.md`):\n{requirements_md}\n\n"
        f"Base Source (`{plan.module}`):\n```\n{module_code[:50000]}\n```\n\n"
        f"Previous Patch:\n```diff\n{prev_patch}\n```\n\n"
        f"Previous Test Code:\n```\n{prev_test}\n```\n"
    )

    data = call_llm(
        messages=[
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider_env=cfg.llm.provider_env,
        model_env=cfg.llm.model_env,
        ledger=ledger,
        cache_dir=cfg.output.cache_dir,
        max_tokens=cfg.llm.max_tokens,
        temperature=cfg.llm.temperature,
        expect_json=False,
    )

    new_patch, new_test, _ = _extract_tagged_sections(
        str(data.get("content", "")),
        test_filename,
        repo_path=Path(cfg.repo.path).resolve(),
        base_commit=cfg.repo.base_ref,
        fallback_patch=prev_patch,
    )
    if new_test.startswith("```"):
        tlines = new_test.splitlines()
        new_test = "\n".join(tlines[1:-1] if tlines and tlines[-1].startswith("```") else tlines[1:]) + "\n"
    if not new_patch.strip():
        new_patch = prev_patch
    if not new_test.strip():
        new_test = prev_test

    (task_dir / "reference.patch").write_text(new_patch, encoding="utf-8", newline="\n")
    (task_dir / test_filename).write_text(new_test, encoding="utf-8", newline="\n")
    return new_patch, new_test


def _run_official_harbor_check(
    pkg_path: Path,
    run_dir: Path,
    task_id: str,
    timeout_s: int,
) -> dict[str, Any]:
    """Run official `harbor run` nop and oracle commands and parse reward files."""
    harbor_out = run_dir / "harbor" / task_id
    nop_dir = harbor_out / "nop"
    oracle_dir = harbor_out / "oracle"
    shutil.rmtree(nop_dir, ignore_errors=True)
    shutil.rmtree(oracle_dir, ignore_errors=True)

    def _run_agent(agent: str, out_dir: Path) -> dict[str, Any]:
        if sys.platform == "win32":
            from factory.gates_advanced import _to_wsl_path
            pkg_arg = _to_wsl_path(pkg_path)
            out_arg = _to_wsl_path(out_dir)
            cmd = [
                "wsl", "-d", "Ubuntu",
                "/home/athul/.local/bin/harbor", "run",
                "-p", pkg_arg, "-a", agent, "-k", "1", "-o", out_arg, "--no-delete", "-y",
            ]
        else:
            cmd = [
                "harbor", "run",
                "-p", str(pkg_path), "-a", agent, "-k", "1", "-o", str(out_dir), "--no-delete", "-y",
            ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 180)
        rewards = list(out_dir.glob("**/reward.txt"))
        summaries = list(out_dir.glob("**/grading_summary.json"))
        reward_val: float | None = None
        if rewards:
            try:
                reward_val = float(rewards[0].read_text(encoding="utf-8").strip())
            except ValueError:
                reward_val = None
        summary_data = {}
        if summaries:
            summary_data = json.loads(summaries[0].read_text(encoding="utf-8"))
        return {
            "agent": agent,
            "returncode": proc.returncode,
            "reward": reward_val,
            "reward_file": str(rewards[0]) if rewards else None,
            "grading_summary": summary_data,
        }

    console.print("\n[bold]Harbor Official Validation[/bold] (`nop` & `oracle`)")
    nop_res = _run_agent("nop", nop_dir)
    console.print(f"  harbor nop    -> reward={nop_res['reward']} (expected 0.0)")
    if nop_res["reward"] != 0.0:
        return {"passed": False, "nop": nop_res, "oracle": None, "reason": f"Harbor nop reward={nop_res['reward']}, expected 0.0"}

    oracle_res = _run_agent("oracle", oracle_dir)
    console.print(f"  harbor oracle -> reward={oracle_res['reward']} (expected 1.0)")
    passed = oracle_res["reward"] == 1.0
    if not passed:
        return {"passed": False, "nop": nop_res, "oracle": oracle_res, "reason": f"Harbor oracle reward={oracle_res['reward']}, expected 1.0"}

    console.print("  [green]✓ Official Harbor nop (0.0) & oracle (1.0) passed[/green]")
    return {"passed": True, "nop": nop_res, "oracle": oracle_res, "reason": "ok"}


def generate_and_validate_task(
    plan: TaskPlan,
    cfg: FactoryConfig,
    run_id: str,
    baseline: TestResult,
    ledger: UsageLedger,
    pass_to_pass: list[str] | None = None,
) -> tuple[bool, Path | None, ValidationReport]:
    """Generate, validate (cheapest first: G1 -> G2/G3/G4 -> G5 -> G6 -> Harbor -> N1 -> G7), and package a task."""
    run_dir = Path(cfg.output.runs_dir) / run_id
    task_dir = run_dir / plan.plan_id
    task_dir.mkdir(parents=True, exist_ok=True)

    report_path = task_dir / "validation_report.json"
    if report_path.exists():
        prev = ValidationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        pkg_candidate = Path(cfg.output.packages_dir) / plan.plan_id
        if prev.accepted and pkg_candidate.exists():
            console.print(f"\n[cyan]Resuming {plan.plan_id}: already ACCEPTED and packaged.[/cyan]")
            return True, pkg_candidate, prev
        elif not prev.accepted and (task_dir / "rejected.json").exists():
            console.print(f"\n[yellow]Resuming {plan.plan_id}: previously REJECTED ({prev.reject_reason}).[/yellow]")
            return False, None, prev

    console.print(f"\n[bold]Generating Task:[/bold] [cyan]{plan.plan_id}[/cyan] ({plan.title})")

    repo_root = Path(cfg.repo.path).resolve()
    module_code = _read_repo_context(repo_root, plan.module)
    init_ctx = _read_repo_context(repo_root, "src/click/__init__.py", max_chars=4000)
    imports_test_ctx = _read_repo_context(repo_root, "tests/test_imports.py", max_chars=2500)
    extra_ctx = f"--- src/click/__init__.py ---\n{init_ctx}\n\n--- tests/test_imports.py ---\n{imports_test_ctx}"

    tok_start = ledger.total_input_tokens + ledger.total_output_tokens
    cost_start = ledger.total_cost_usd

    def _task_usage() -> tuple[int, float]:
        return (
            (ledger.total_input_tokens + ledger.total_output_tokens) - tok_start,
            ledger.total_cost_usd - cost_start,
        )

    # Stage 1: Requirements
    requirements_md, criteria, interface_symbols = generate_requirements(
        plan=plan,
        module_code=module_code,
        cfg=cfg,
        ledger=ledger,
        task_dir=task_dir,
    )
    t_tok, t_cost = _task_usage()
    check_budget_guard(cfg, ledger, t_tok, t_cost)

    # Stage 2: Implementation & Tests
    patch_text, test_code, test_filename = generate_implementation_and_tests(
        plan=plan,
        requirements_md=requirements_md,
        module_code=module_code,
        extra_context=extra_ctx,
        cfg=cfg,
        ledger=ledger,
        task_dir=task_dir,
    )

    repairs = 0
    max_repairs = cfg.generation.max_repairs
    g6_repaired_survivors = False
    docker_img = cfg.repo.docker_image or "tessera-click-hardened:cf19179"
    p2p_list = pass_to_pass or []
    f2p_list: list[str] = []

    validation_report = ValidationReport(
        task_id=plan.plan_id,
        base_commit=cfg.repo.base_ref,
        repairs=0,
    )

    # Phase A: Pre-Harbor cheapest gates + Repair loop (G1 -> G2 -> G3 -> G4 -> G5 -> G6)
    preflight_passed = False
    while True:
        t_tok, t_cost = _task_usage()
        check_budget_guard(cfg, ledger, t_tok, t_cost)

        patch_file = task_dir / "reference.patch"
        test_file = task_dir / test_filename

        ctx = GateContext(
            repo_path=repo_root,
            base_commit=cfg.repo.base_ref,
            patch_path=patch_file,
            feature_test_paths=[test_file],
            regression_test_paths=[],
            test_cmd=cfg.repo.test_cmd,
            result_format=cfg.repo.result_format,
            timeout_s=cfg.repo.timeout_s,
            determinism_runs=cfg.gates.determinism_runs,
            setup_cmd=cfg.repo.setup_cmd,
            docker_image=docker_img,
        )

        # 1. G1: Clean Apply
        g1 = run_g1(ctx)
        validation_report.gates["G1"] = g1.model_dump()
        if not g1.passed:
            if repairs < max_repairs:
                repairs += 1
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G1 (Clean Apply)",
                    f"Patch apply/syntax error: {g1.evidence}",
                    patch_text, test_code, test_filename, module_code, cfg, ledger, task_dir, repairs,
                )
                continue
            validation_report.reject_reason = f"G1 failed after {repairs} repairs: {g1.evidence}"
            validation_report.first_failing_gate = "G1"
            break

        # 2. G2: Native Fail-to-Pass pre-check
        g2 = run_g2(ctx)
        validation_report.gates["G2"] = g2.model_dump()
        if not g2.passed:
            if repairs < max_repairs:
                repairs += 1
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G2 (Fail-to-Pass)",
                    f"{g2.evidence} | base_failed={g2.base_failed} | patched_passed={g2.patched_passed} | failure_types={g2.failure_types}",
                    patch_text, test_code, test_filename, module_code, cfg, ledger, task_dir, repairs,
                )
                continue
            validation_report.reject_reason = f"G2 failed after {repairs} repairs: {g2.evidence}"
            validation_report.first_failing_gate = "G2"
            break

        # Derive fail_to_pass.json automatically from real G2 node IDs
        # Format: tests/feature/<test_filename>::<test_fn_name>
        raw_f2p = [nid for nid in g2.patched_passed if nid in set(g2.base_failed)] or list(g2.patched_passed)
        f2p_list = []
        for nid in raw_f2p:
            tail = nid.split("::", 1)[-1] if "::" in nid else nid
            f2p_list.append(f"tests/feature/{test_filename}::{tail}")

        # 3. G3: No Regressions pre-check
        g3 = run_g3(ctx, baseline)
        validation_report.gates["G3"] = g3.model_dump()
        if not g3.passed:
            if repairs < max_repairs:
                repairs += 1
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G3 (No Regressions)",
                    f"Baseline regressions detected: {g3.evidence}",
                    patch_text, test_code, test_filename, module_code, cfg, ledger, task_dir, repairs,
                )
                continue
            validation_report.reject_reason = f"G3 failed after {repairs} repairs: {g3.evidence}"
            validation_report.first_failing_gate = "G3"
            break

        # 4. G4: Determinism (3 runs)
        g4 = run_g4(ctx, runs=cfg.gates.determinism_runs)
        validation_report.gates["G4"] = g4.model_dump()
        if not g4.passed:
            validation_report.reject_reason = f"G4 failed: flaky tests {g4.flaky_tests}"
            validation_report.first_failing_gate = "G4"
            break

        # 5. G5: Traceability & Interface Completeness
        g5 = run_g5_traceability(requirements_md, criteria, interface_symbols, test_code, patch_text)
        validation_report.gates["G5"] = g5.model_dump()
        if not g5.passed:
            if repairs < max_repairs:
                repairs += 1
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G5 (Traceability)",
                    f"Uncovered ACs: {g5.uncovered_criteria}; Orphan tests: {g5.orphan_tests}; Missing symbols: {g5.undeclared_symbols}",
                    patch_text, test_code, test_filename, module_code, cfg, ledger, task_dir, repairs,
                )
                continue
            validation_report.reject_reason = f"G5 failed after {repairs} repairs: uncovered={g5.uncovered_criteria}"
            validation_report.first_failing_gate = "G5"
            break

        # 6. G6: Scoped Container Mutation (added src/ lines only)
        g6 = run_g6_mutation(
            repo_path=repo_root,
            base_commit=cfg.repo.base_ref,
            patch_path=patch_file,
            feature_test_path=test_file,
            docker_image=docker_img,
            kill_threshold=cfg.gates.mutation_kill_threshold,
        )
        validation_report.gates["G6"] = g6.model_dump()
        needs_g6_repair = (not g6.passed) or (len(g6.survivors) > 0 and not g6_repaired_survivors)
        if needs_g6_repair:
            if repairs < max_repairs:
                repairs += 1
                g6_repaired_survivors = True
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G6 (Mutation Survivors)",
                    f"Kill rate={g6.kill_rate:.1%} (threshold={cfg.gates.mutation_kill_threshold:.0%}). Surviving mutants to kill with stronger tests: {g6.survivors[:6]}",
                    patch_text, test_code, test_filename, module_code, cfg, ledger, task_dir, repairs,
                )
                continue
            if not g6.passed:
                validation_report.reject_reason = f"G6 kill rate {g6.kill_rate:.1%} < {cfg.gates.mutation_kill_threshold:.0%}"
                validation_report.first_failing_gate = "G6"
                break

        preflight_passed = True
        break

    validation_report.repairs = repairs

    if not preflight_passed:
        _persist_rejection(task_dir, plan, validation_report, cfg)
        return False, None, validation_report

    # Phase B: Package in clean Harbor 0.25.x format + Official nop/oracle Harbor runs
    metadata = TaskMetadata(
        task_id=plan.plan_id,
        title=plan.title,
        module=plan.module,
        behaviour_axis=plan.behaviour_axis,
        interaction_partner=plan.interaction_partner,
        behaviour_signature=plan.description[:140],
        acceptance_criteria=criteria,
        interface=interface_symbols,
        base_commit=cfg.repo.base_ref,
        base_tag="8.5.1",
    )

    pkg_path = package_task(
        task_id=plan.plan_id,
        output_dir=cfg.output.packages_dir,
        requirements_md=requirements_md,
        patch_path=task_dir / "reference.patch",
        feature_test_paths=[task_dir / test_filename],
        metadata=metadata,
        validation_report=validation_report,
        test_cmd=cfg.repo.test_cmd,
        timeout_sec=float(max(cfg.repo.timeout_s, 300)),
        repository_url="https://github.com/pallets/click",
        license_name="BSD-3-Clause",
        fail_to_pass=f2p_list,
        pass_to_pass=p2p_list,
    )

    harbor_res = _run_official_harbor_check(pkg_path, run_dir, plan.plan_id, cfg.repo.timeout_s)
    validation_report.gates["Harbor_official"] = harbor_res
    if not harbor_res["passed"]:
        validation_report.reject_reason = f"Official Harbor check failed: {harbor_res['reason']}"
        validation_report.first_failing_gate = "Harbor_official"
        _persist_rejection(task_dir, plan, validation_report, cfg)
        return False, None, validation_report

    # Phase C: N1 Upstream-Novelty Check
    n1 = run_n1_upstream_novelty(
        repo_path=repo_root,
        patch_text=patch_text,
        feature_test_path=task_dir / test_filename,
        timeout_s=cfg.repo.timeout_s,
        docker_image=docker_img,
    )
    validation_report.gates["N1_upstream_novelty"] = n1.model_dump()
    if not n1.passed:
        validation_report.reject_reason = f"N1 upstream-novelty failed: {n1.evidence}"
        validation_report.first_failing_gate = "N1_upstream_novelty"
        _persist_rejection(task_dir, plan, validation_report, cfg)
        return False, None, validation_report

    # Phase D: G7 Independent Solver (sees ONLY instruction.md + base repo)
    t_tok, t_cost = _task_usage()
    check_budget_guard(cfg, ledger, t_tok, t_cost)
    g7 = run_g7_solver(
        repo_path=repo_root,
        base_commit=cfg.repo.base_ref,
        instruction_md=requirements_md,
        target_module=plan.module,
        feature_test_path=task_dir / test_filename,
        fail_to_pass=f2p_list,
        pass_to_pass=p2p_list,
        cfg=cfg,
        ledger=ledger,
        docker_image=docker_img,
    )
    validation_report.gates["G7_solver"] = g7.model_dump()
    if not g7.passed:
        validation_report.reject_reason = f"G7 independent solver failed: {g7.notes}"
        validation_report.first_failing_gate = "G7_solver"
        _persist_rejection(task_dir, plan, validation_report, cfg)
        return False, None, validation_report

    # Accepted! Update evidence files outside package
    validation_report.accepted = True
    t_tok, t_cost = _task_usage()
    validation_report.run = {
        "run_id": run_id,
        "task_tokens": t_tok,
        "task_estimated_cost_usd": round(t_cost, 6),
    }

    report_path.write_text(validation_report.model_dump_json(indent=2), encoding="utf-8", newline="\n")
    ev_dir = Path("evidence") / plan.plan_id
    ev_dir.mkdir(parents=True, exist_ok=True)
    (ev_dir / "validation_report.json").write_text(
        validation_report.model_dump_json(indent=2), encoding="utf-8", newline="\n"
    )
    (ev_dir / "task_metadata.json").write_text(
        metadata.model_dump_json(indent=2), encoding="utf-8", newline="\n"
    )

    console.print(f"  [green bold]✓ Task {plan.plan_id} ACCEPTED across G1–G7, N1, and Harbor nop/oracle[/green bold]")
    return True, pkg_path, validation_report


def _persist_rejection(task_dir: Path, plan: TaskPlan, report: ValidationReport, cfg: FactoryConfig) -> None:
    report.accepted = False
    (task_dir / "validation_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8", newline="\n")
    (task_dir / "rejected.json").write_text(
        json.dumps(
            {
                "task_id": plan.plan_id,
                "reason": report.reject_reason,
                "first_failing_gate": report.first_failing_gate,
                "gates": report.gates,
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    ev_dir = Path("evidence") / plan.plan_id
    ev_dir.mkdir(parents=True, exist_ok=True)
    (ev_dir / "rejected.json").write_text(
        (task_dir / "rejected.json").read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    console.print(f"  [red]✗ Task {plan.plan_id} REJECTED at {report.first_failing_gate}:[/red] {report.reject_reason}")
