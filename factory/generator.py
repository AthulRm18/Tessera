"""Task generator — generates requirements, reference patch, feature tests, and regression checks.

Runs each candidate task in an isolated worktree through Gates G1–G4.
Executes an automated repair loop (max 2 repairs) with structured gate failure feedback.
Enforces hard budget guards on tokens and estimated costs.
Maintains resumable stages under runs/<run_id>/<task_id>/.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.config import FactoryConfig
from factory.gates import GateContext, run_g1, run_g2, run_g3, run_g4
from factory.llm import UsageLedger, call_llm
from factory.packager import package_task
from factory.repo import FileSymbols, TestResult, run_tests
from factory.schemas import (
    AcceptanceCriterion,
    GateResult,
    OrganizerChecks,
    TaskMetadata,
    TaskPlan,
    ValidationReport,
)

console = Console()


class BudgetExceededError(Exception):
    """Raised when token or cost budget limit is reached."""
    pass


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
            f"Run cost budget reached: ${ledger.total_cost_usd:.4f} >= ${cfg.budget.max_cost_per_run:.2f}"
        )
    if task_tokens >= cfg.budget.max_tokens_per_task:
        raise BudgetExceededError(
            f"Task token budget reached: {task_tokens} >= {cfg.budget.max_tokens_per_task}"
        )
    if task_cost >= cfg.budget.max_cost_per_task:
        raise BudgetExceededError(
            f"Task cost budget reached: ${task_cost:.4f} >= ${cfg.budget.max_cost_per_task:.2f}"
        )


REQUIREMENTS_SYSTEM_PROMPT = """You are a senior technical specifications writer creating coding benchmark tasks for evaluating AI coding systems.
Write clear, unambiguous, achievable requirements for a feature addition to an existing repository.
Strict rules:
1. Include a numbered list of Acceptance Criteria (AC1, AC2, AC3, ...).
2. Include an '## Interface' section listing the exact symbol names, signatures, parameters, return types, and exception classes the tests will expect.
3. Absolutely NO implementation hints, pseudocode, code snippets for the solution, or file patches in the requirements. Specify WHAT the software must do, NOT HOW to implement it.
4. Respond ONLY with a valid JSON object:
{
  "title": "<task title>",
  "problem_description": "<clear description of the feature and rationale>",
  "acceptance_criteria": [
    {"id": "AC1", "text": "<criterion 1>"},
    {"id": "AC2", "text": "<criterion 2>"}
  ],
  "interface": {
    "symbols": ["<symbol1>", "<symbol2>"],
    "details": "<signature and contract description>"
  },
  "markdown_text": "<full requirements markdown document with description, numbered criteria, and Interface section>"
}
"""

IMPLEMENTATION_SYSTEM_PROMPT = """You are an expert software developer and test engineer.
Given a repository module and feature requirements:
Produce:
1. A reference implementation patch in standard unified diff format (git diff format with `--- a/...` and `+++ b/...`).
2. Comprehensive feature tests asserting that each numbered acceptance criterion is satisfied.
   - Tag each test with the criterion ID it verifies (e.g. # AC1 or @pytest.mark.ac('AC1')).
   - Follow the repo's existing test style and framework.
   - Assert observable behavior and contracts, NEVER internal private variables or implementation details.
3. 2-5 regression checks on adjacent existing behavior.

Respond ONLY with a valid JSON object:
{
  "patch": "<unified diff string starting with --- a/...>",
  "test_code": "<full test file code>",
  "test_filename": "<filename for test, e.g. test_feature.py or test/feature.js>",
  "regression_test_code": "<optional additional regression tests or empty string>"
}
"""

REPAIR_SYSTEM_PROMPT = """You are an expert software developer and test engineer repairing a benchmark task.
The previous patch and/or test failed automated validation gates.
Review the gate failure feedback, the requirements, the previous patch, and previous tests.
Fix the patch and/or tests so that:
1. The patch applies cleanly (G1).
2. Feature tests FAIL on the unpatched base repo (missing feature detected, G2).
3. Feature tests PASS on the patched repo (G2).
4. No existing baseline tests regress (G3).

Respond ONLY with a valid JSON object:
{
  "patch": "<corrected unified diff string>",
  "test_code": "<corrected test file code>",
  "test_filename": "<filename for test>",
  "notes": "<explanation of fixes made>"
}
"""


def generate_requirements(
    plan: TaskPlan,
    module_code: str,
    cfg: FactoryConfig,
    ledger: UsageLedger,
    task_dir: Path,
) -> tuple[str, list[AcceptanceCriterion], list[str]]:
    """Stage 1: Generate requirements.md with numbered acceptance criteria and interface section."""
    req_file = task_dir / "requirements.md"
    meta_file = task_dir / "requirements_meta.json"

    # Resumable check
    if req_file.exists() and meta_file.exists():
        console.print(f"  [cyan]Resuming:[/cyan] requirements already generated in {task_dir.name}")
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
        f"Problem Summary: {plan.description}\n\n"
        f"Context from existing module:\n```\n{module_code[:3000]}\n```\n"
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
        expect_json=True,
    )

    md_text = data.get("markdown_text")
    if not md_text:
        # Build markdown text from parts if not provided as single string
        criteria_lines = "\n".join(f"{c.get('id', f'AC{i}')}. {c.get('text', '')}" for i, c in enumerate(data.get("acceptance_criteria", []), 1))
        md_text = (
            f"# Task: {data.get('title', plan.title)}\n\n"
            f"## Problem Description\n{data.get('problem_description', plan.description)}\n\n"
            f"## Acceptance Criteria\n{criteria_lines}\n\n"
            f"## Interface\n{json.dumps(data.get('interface', {}), indent=2)}\n"
        )

    criteria_raw = data.get("acceptance_criteria", [])
    criteria = [
        AcceptanceCriterion(id=c.get("id", f"AC{i}"), text=c.get("text", str(c)))
        for i, c in enumerate(criteria_raw, 1)
    ]
    if not criteria:
        criteria = [AcceptanceCriterion(id="AC1", text=plan.description)]

    symbols = data.get("interface", {}).get("symbols", plan.target_symbols)

    req_file.write_text(md_text, encoding="utf-8")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"criteria": [c.model_dump() for c in criteria], "symbols": symbols}, f, indent=2)

    return md_text, criteria, symbols


def generate_implementation_and_tests(
    plan: TaskPlan,
    requirements_md: str,
    module_code: str,
    cfg: FactoryConfig,
    ledger: UsageLedger,
    task_dir: Path,
) -> tuple[str, str, str]:
    """Stage 2: Generate reference patch and feature tests."""
    patch_file = task_dir / "reference.patch"
    test_meta_file = task_dir / "test_meta.json"

    if patch_file.exists() and test_meta_file.exists():
        console.print(f"  [cyan]Resuming:[/cyan] implementation and tests already generated in {task_dir.name}")
        with open(test_meta_file, encoding="utf-8") as f:
            data = json.load(f)
            test_file = task_dir / data["test_filename"]
            return patch_file.read_text(encoding="utf-8"), test_file.read_text(encoding="utf-8"), data["test_filename"]

    check_budget_guard(cfg, ledger)

    prompt = (
        f"Task Title: {plan.title}\n"
        f"Module: {plan.module}\n"
        f"Test Framework: {cfg.repo.result_format}\n\n"
        f"Requirements:\n{requirements_md}\n\n"
        f"Current Module Source:\n```\n{module_code[:4000]}\n```\n"
    )

    data = call_llm(
        messages=[
            {"role": "system", "content": IMPLEMENTATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider_env=cfg.llm.provider_env,
        model_env=cfg.llm.model_env,
        ledger=ledger,
        expect_json=True,
    )

    patch = data.get("patch", "")
    test_code = data.get("test_code", "")
    test_filename = data.get("test_filename", f"test_{Path(plan.module).stem}_feature.py")

    # Clean unified diff patch: strip leading/trailing markdown blocks if present
    patch = patch.strip()
    if patch.startswith("```"):
        lines = patch.splitlines()
        patch = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    # Save artifacts
    patch_file.write_text(patch, encoding="utf-8")
    test_path = task_dir / test_filename
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(test_code, encoding="utf-8")

    with open(test_meta_file, "w", encoding="utf-8") as f:
        json.dump({"test_filename": test_filename}, f, indent=2)

    return patch, test_code, test_filename


def repair_task(
    plan: TaskPlan,
    requirements_md: str,
    failing_gate: str,
    error_msg: str,
    prev_patch: str,
    prev_test: str,
    test_filename: str,
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
        f"Gate Error Feedback:\n{error_msg}\n\n"
        f"Requirements:\n{requirements_md}\n\n"
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
        expect_json=True,
    )

    new_patch = data.get("patch", prev_patch).strip()
    if new_patch.startswith("```"):
        lines = new_patch.splitlines()
        new_patch = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    new_test = data.get("test_code", prev_test)

    # Overwrite patch and test in task_dir
    (task_dir / "reference.patch").write_text(new_patch, encoding="utf-8")
    (task_dir / test_filename).write_text(new_test, encoding="utf-8")

    return new_patch, new_test


def generate_and_validate_task(
    plan: TaskPlan,
    cfg: FactoryConfig,
    run_id: str,
    baseline: TestResult,
    ledger: UsageLedger,
) -> tuple[bool, Path | None, ValidationReport]:
    """Generate and validate a single task from a plan through Gates G1–G4.
    
    Returns (accepted, package_path, validation_report).
    """
    task_dir = Path(cfg.output.runs_dir) / run_id / plan.plan_id
    task_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]Generating Task:[/bold] [cyan]{plan.plan_id}[/cyan] ({plan.title})")

    # Read target module source code from base repo
    module_full_path = Path(cfg.repo.path) / plan.module
    module_code = ""
    if module_full_path.exists():
        module_code = module_full_path.read_text(encoding="utf-8", errors="replace")

    # Stage 1: Requirements
    requirements_md, criteria, interface_symbols = generate_requirements(
        plan=plan,
        module_code=module_code,
        cfg=cfg,
        ledger=ledger,
        task_dir=task_dir,
    )

    # Stage 2: Implementation & Tests
    patch_text, test_code, test_filename = generate_implementation_and_tests(
        plan=plan,
        requirements_md=requirements_md,
        module_code=module_code,
        cfg=cfg,
        ledger=ledger,
        task_dir=task_dir,
    )

    repairs = 0
    max_repairs = cfg.generation.max_repairs
    validation_report = ValidationReport(
        task_id=plan.plan_id,
        base_commit=cfg.repo.base_ref,
        repairs=0,
    )

    while True:
        patch_file = task_dir / "reference.patch"
        test_file = task_dir / test_filename

        ctx = GateContext(
            repo_path=Path(cfg.repo.path).resolve(),
            base_commit=cfg.repo.base_ref,
            patch_path=patch_file,
            feature_test_paths=[test_file],
            regression_test_paths=[],
            test_cmd=cfg.repo.test_cmd,
            result_format=cfg.repo.result_format,
            timeout_s=cfg.repo.timeout_s,
            determinism_runs=cfg.gates.determinism_runs,
            setup_cmd=cfg.repo.setup_cmd,
        )

        # Gate G1: Clean Apply
        g1 = run_g1(ctx)
        validation_report.gates["G1"] = g1.model_dump()
        if not g1.passed:
            if repairs < max_repairs:
                repairs += 1
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G1 (Clean Apply)",
                    f"git apply rejected patch: {g1.evidence.get('stdout', '')} {g1.evidence.get('stderr', '')}",
                    patch_text, test_code, test_filename, cfg, ledger, task_dir, repairs
                )
                continue
            else:
                validation_report.reject_reason = f"G1 failed after {repairs} repairs"
                validation_report.first_failing_gate = "G1"
                break

        # Gate G2: Fail to Pass
        g2 = run_g2(ctx)
        validation_report.gates["G2"] = g2.model_dump()
        if not g2.passed:
            if repairs < max_repairs:
                repairs += 1
                base_info = f"Base tests on unpatched: {g2.evidence.get('base_passed')} passed, {g2.evidence.get('base_failed')} failed."
                patch_info = f"Patched tests: {g2.evidence.get('patched_passed')} passed, {g2.evidence.get('patched_failed')} failed."
                repair_msg = f"Fail-to-pass gate failed. {base_info} {patch_info}"
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G2 (Fail-to-Pass)",
                    repair_msg, patch_text, test_code, test_filename, cfg, ledger, task_dir, repairs
                )
                continue
            else:
                validation_report.reject_reason = f"G2 failed after {repairs} repairs"
                validation_report.first_failing_gate = "G2"
                break

        # Gate G3: No Regressions
        g3 = run_g3(ctx, baseline)
        validation_report.gates["G3"] = g3.model_dump()
        if not g3.passed:
            if repairs < max_repairs:
                repairs += 1
                repair_msg = f"Regression detected: {g3.evidence.get('n_new_failures')} tests failed after patch."
                patch_text, test_code = repair_task(
                    plan, requirements_md, "G3 (No Regressions)",
                    repair_msg, patch_text, test_code, test_filename, cfg, ledger, task_dir, repairs
                )
                continue
            else:
                validation_report.reject_reason = f"G3 failed after {repairs} repairs"
                validation_report.first_failing_gate = "G3"
                break

        # Gate G4: Determinism
        g4 = run_g4(ctx, runs=cfg.gates.determinism_runs)
        validation_report.gates["G4"] = g4.model_dump()
        if not g4.passed:
            validation_report.reject_reason = "G4 (Determinism) failed — flaky test detected"
            validation_report.first_failing_gate = "G4"
            break

        # All gates passed!
        validation_report.accepted = True
        validation_report.repairs = repairs
        validation_report.organizer_checks = OrganizerChecks(
            original_repo_works_as_is=True,
            tests_pass_after_implementation=True,
            feature_test_fails_without_feature=True,
        )
        break

    # Save validation report
    with open(task_dir / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump(validation_report.model_dump(), f, indent=2)

    if not validation_report.accepted:
        console.print(f"  [red]✗ Task {plan.plan_id} REJECTED:[/red] {validation_report.reject_reason}")
        with open(task_dir / "rejected.json", "w", encoding="utf-8") as f:
            json.dump({
                "task_id": plan.plan_id,
                "reason": validation_report.reject_reason,
                "gates": validation_report.gates,
            }, f, indent=2)
        return False, None, validation_report

    # Package accepted task
    metadata = TaskMetadata(
        task_id=plan.plan_id,
        title=plan.title,
        module=plan.module,
        behaviour_axis=plan.behaviour_axis,
        interaction_partner=plan.interaction_partner,
        acceptance_criteria=criteria,
        interface_symbols=interface_symbols,
        base_commit=cfg.repo.base_ref,
        repo_name=Path(cfg.repo.path).name,
    )

    # Command for test.sh in container:
    # Runs the feature tests located in /tests/feature/
    if cfg.repo.result_format == "mocha":
        test_cmd = f'SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"\nnpx mocha --require @babel/register "$SCRIPT_DIR/feature/{test_filename}"'
    else:
        test_cmd = f'SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"\npytest "$SCRIPT_DIR/feature/{test_filename}" -v'

    pkg_path = package_task(
        task_id=plan.plan_id,
        output_dir=cfg.output.packages_dir,
        requirements_md=requirements_md,
        patch_path=task_dir / "reference.patch",
        feature_test_paths=[task_dir / test_filename],
        metadata=metadata,
        validation_report=validation_report,
        test_cmd=test_cmd,
        docker_image=cfg.repo.docker_image,
        timeout_sec=float(cfg.repo.timeout_s),
    )

    console.print(f"  [green bold]✓ Task {plan.plan_id} ACCEPTED and PACKAGED[/green bold]")
    return True, pkg_path, validation_report
