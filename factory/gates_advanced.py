"""Advanced validation gates: G5 (Traceability), G6 (Container Mutation), N1 (Upstream Novelty), G7 (Independent Solver)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.config import FactoryConfig
from factory.llm import UsageLedger, call_llm
from factory.repo import apply_patch, create_worktree, remove_worktree, run_cmd
from factory.schemas import AcceptanceCriterion, G5Result, G6Result, G7Result, GateResult

console = Console()


# ---------------------------------------------------------------------------
# G5 — Traceability & Interface Completeness
# ---------------------------------------------------------------------------

def run_g5_traceability(
    requirements_md: str,
    criteria: list[AcceptanceCriterion],
    declared_symbols: list[str],
    test_code: str,
    patch_text: str,
) -> G5Result:
    """G5: Verify every AC has tagged tests, no orphan tests, and declared symbols match code & tests."""
    console.print("\n[bold]G5[/bold] traceability & interface contract")

    # 1. Extract AC tags referenced in test_code (e.g., # AC1, # AC1 & AC2, mark.ac("AC1"))
    found_test_defs = re.findall(r"^def (test_[A-Za-z0-9_]+)", test_code, re.MULTILINE)
    ac_ids = [c.id for c in criteria]
    covered_acs: set[str] = set()

    # Check comments/lines above or inside each test
    lines = test_code.splitlines()
    orphan_tests: list[str] = []
    for i, line in enumerate(lines):
        m = re.match(r"^def (test_[A-Za-z0-9_]+)", line)
        if not m:
            continue
        test_name = m.group(1)
        window_start = max(0, i - 5)
        window_end = min(len(lines), i + 12)
        window_text = "\n".join(lines[window_start:window_end])
        tags_here = [ac for ac in ac_ids if re.search(rf"\b{re.escape(ac)}\b", window_text)]
        if not tags_here:
            orphan_tests.append(test_name)
        covered_acs.update(tags_here)

    uncovered = [ac for ac in ac_ids if ac not in covered_acs]

    # 2. Check declared interface symbols appear in requirements_md and added patch lines or test_code
    added_lines = "\n".join(
        l[1:] for l in patch_text.splitlines() if l.startswith("+") and not l.startswith("+++")
    )
    missing_symbols: list[str] = []
    for sym in declared_symbols:
        base_sym = sym.split("(")[0].split(".")[-1].strip()
        if not base_sym:
            continue
        if base_sym not in requirements_md:
            missing_symbols.append(f"{sym} (missing from instruction.md)")
        elif base_sym not in added_lines and base_sym not in test_code:
            missing_symbols.append(f"{sym} (unused in patch and tests)")

    passed = (not uncovered) and (not missing_symbols) and (len(found_test_defs) > 0)
    if passed:
        console.print(f"  [green]✓ G5 passed[/green] ({len(ac_ids)}/{len(ac_ids)} ACs covered, {len(found_test_defs)} tests)")
    else:
        console.print(f"  [red]✗ G5 failed[/red]: uncovered={uncovered}, missing_symbols={missing_symbols}")

    return G5Result(
        passed=passed,
        uncovered_criteria=uncovered,
        orphan_tests=orphan_tests,
        undeclared_symbols=missing_symbols,
        evidence={
            "total_acs": len(ac_ids),
            "covered_acs": sorted(covered_acs),
            "test_count": len(found_test_defs),
            "orphan_tests": orphan_tests,
            "missing_symbols": missing_symbols,
        },
    )


# ---------------------------------------------------------------------------
# G6 — Scoped Mutation Check (Added lines under src/ only, run inside container)
# ---------------------------------------------------------------------------

def _generate_line_mutants(wt: Path, patch_text: str, max_mutants: int = 12) -> list[dict[str, Any]]:
    """Generate targeted single-line mutants ONLY on lines added by reference.patch under src/."""
    # Parse added (file, line_no_approx, line_content) from unified diff
    mutants: list[dict[str, Any]] = []
    current_file: str | None = None
    new_line_no = 0

    candidates: list[tuple[str, int, str]] = []
    for raw in patch_text.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:].strip()
        elif raw.startswith("@@ "):
            m = re.search(r"\+(\d+)", raw)
            if m:
                new_line_no = int(m.group(1)) - 1
        elif raw.startswith("+") and not raw.startswith("+++"):
            new_line_no += 1
            if current_file and current_file.startswith("src/") and current_file.endswith(".py"):
                candidates.append((current_file, new_line_no, raw[1:]))
        elif not raw.startswith("-"):
            new_line_no += 1

    # Mutation rules on executable Python statements (skip blanks, comments, imports, docstrings, defs)
    operators: list[tuple[str, str, str]] = [
        ("eq_to_neq", " == ", " != "),
        ("neq_to_eq", " != ", " == "),
        ("lt_to_ge", " < ", " >= "),
        ("gt_to_le", " > ", " <= "),
        ("is_none_flip", " is None", " is not None"),
        ("is_not_none_flip", " is not None", " is None"),
        ("return_true_flip", "return True", "return False"),
        ("return_false_flip", "return False", "return True"),
        ("return_val_none", r"^(\s*)return (?!None\b|True\b|False\b)(.+)$", r"\1return None"),
        ("not_in_flip", " not in ", " in "),
        ("raise_remove", r"^(\s*)raise .+$", r"\1pass"),
        ("self_fail_remove", r"^(\s*)self\.fail\(", r"\1# mutated fail("),
    ]

    for rel_path, _, line_code in candidates:
        stripped = line_code.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
            or stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("class ")
            or stripped.startswith("def ")
        ):
            continue

        target_file = wt / rel_path
        if not target_file.exists():
            continue
        file_lines = target_file.read_text(encoding="utf-8").splitlines()
        # Find exact matching line index in patched file
        matching_indices = [idx for idx, fl in enumerate(file_lines) if fl == line_code]
        if not matching_indices:
            continue
        line_idx = matching_indices[0]

        for op_name, pat, repl in operators:
            if op_name in ("return_val_none", "raise_remove", "self_fail_remove"):
                mutated_line, n_subs = re.subn(pat, repl, line_code)
                if n_subs == 0:
                    continue
            else:
                if pat not in line_code:
                    continue
                mutated_line = line_code.replace(pat, repl, 1)

            mutants.append({
                "id": f"M{len(mutants)+1:02d}_{op_name}",
                "file": rel_path,
                "line_idx": line_idx,
                "original": line_code.strip(),
                "mutated": mutated_line.strip(),
                "mutated_full_line": mutated_line,
            })
            break  # one clean mutant per added executable line

        if len(mutants) >= max_mutants:
            break

    return mutants


def _to_wsl_path(win_path: Path) -> str:
    p = win_path.resolve().as_posix()
    if len(p) >= 2 and p[1] == ":":
        return f"/mnt/{p[0].lower()}{p[2:]}"
    return p


def run_g6_mutation(
    repo_path: Path,
    base_commit: str,
    patch_path: Path,
    feature_test_path: Path,
    docker_image: str = "tessera-click-hardened:cf19179",
    kill_threshold: float = 0.70,
    max_mutants: int = 12,
) -> G6Result:
    """G6: Generate mutants on patch-added lines under src/ and run feature tests per mutant inside Docker."""
    console.print("\n[bold]G6[/bold] scoped mutation check (inside container)")

    parent = Path(tempfile.mkdtemp(prefix="tessera_g6_"))
    wt: Path | None = None
    try:
        wt = create_worktree(repo_path, base_commit, "g6_wt", parent_dir=parent)
        ok, msg = apply_patch(patch_path, wt)
        if not ok:
            return G6Result(passed=False, evidence=f"Failed to apply patch for G6: {msg}")

        patch_text = patch_path.read_text(encoding="utf-8")
        mutants = _generate_line_mutants(wt, patch_text, max_mutants=max_mutants)
        if not mutants:
            return G6Result(
                passed=False,
                mutants=0,
                killed=0,
                kill_rate=0.0,
                evidence="No executable lines added under src/ to mutate",
            )

        # Copy feature test into temp dir mounted at /tests in container
        test_stage = parent / "tests_stage"
        test_stage.mkdir(exist_ok=True)
        shutil.copy2(feature_test_path, test_stage / feature_test_path.name)

        # Build single batch python runner executed once inside Docker container for speed
        batch_script = test_stage / "run_mutants.py"
        mutants_meta = []
        for m in mutants:
            mutants_meta.append({
                "id": m["id"],
                "file": m["file"],
                "line_idx": m["line_idx"],
                "mutated_full_line": m["mutated_full_line"],
                "original": m["original"],
                "mutated": m["mutated"],
            })
        (test_stage / "mutants.json").write_text(json.dumps(mutants_meta), encoding="utf-8")

        batch_code = f'''import json, shutil, subprocess
from pathlib import Path

mutants = json.loads(Path("/mutants/mutants.json").read_text())
results = []
for m in mutants:
    target = Path("/app") / m["file"]
    orig_text = target.read_text()
    lines = orig_text.splitlines()
    lines[m["line_idx"]] = m["mutated_full_line"]
    target.write_text("\\n".join(lines) + "\\n")
    try:
        r = subprocess.run(
            ["pytest", "/mutants/{feature_test_path.name}", "-x", "-q", "--tb=no", "--no-header", "--rootdir=/mutants", "--import-mode=importlib"],
            cwd="/mutants",
            env={{"PYTHONPATH": "/app", "PATH": "/usr/local/bin:/usr/bin:/bin"}},
            capture_output=True,
            text=True,
            timeout=30,
        )
        killed = (r.returncode != 0)
        results.append({{"id": m["id"], "killed": killed, "rc": r.returncode, "desc": f"{{m[\x27file\x27]}}: {{m[\x27original\x27]}} -> {{m[\x27mutated\x27]}}"}})
    finally:
        target.write_text(orig_text)

print(json.dumps(results))
'''
        batch_script.write_text(batch_code, encoding="utf-8", newline="\n")

        if sys.platform == "win32":
            wt_mnt = _to_wsl_path(wt)
            mut_mnt = _to_wsl_path(test_stage)
            cmd = [
                "wsl", "-d", "Ubuntu", "docker", "run", "--rm", "--network", "none",
                "-v", f"{wt_mnt}:/app",
                "-v", f"{mut_mnt}:/mutants",
                docker_image,
                "python", "/mutants/run_mutants.py",
            ]
        else:
            cmd = [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{wt.resolve()}:/app",
                "-v", f"{test_stage.resolve()}:/mutants",
                docker_image,
                "python", "/mutants/run_mutants.py",
            ]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return G6Result(
                passed=False,
                mutants=len(mutants),
                evidence=f"Container mutation runner failed (rc={proc.returncode}): {proc.stderr[:400]}",
            )

        # Parse JSON from last line of stdout
        last_line = proc.stdout.strip().splitlines()[-1]
        outcomes = json.loads(last_line)
        killed_count = sum(1 for o in outcomes if o["killed"])
        survivors = [f"{o['id']} ({o['desc']})" for o in outcomes if not o["killed"]]
        kill_rate = killed_count / len(outcomes) if outcomes else 0.0
        passed = kill_rate >= kill_threshold

        color = "green" if passed else "red"
        mark = "✓" if passed else "✗"
        console.print(
            f"  [{color}]{mark} G6 mutation kill rate: {killed_count}/{len(outcomes)} ({kill_rate:.1%}, threshold {kill_threshold:.0%})[/{color}]"
        )
        if survivors:
            console.print(f"  Survivors: {survivors[:5]}")

        return G6Result(
            passed=passed,
            mutants=len(outcomes),
            killed=killed_count,
            kill_rate=round(kill_rate, 4),
            survivors=survivors,
            evidence={"outcomes": outcomes, "threshold": kill_threshold},
        )
    finally:
        if wt is not None:
            try:
                remove_worktree(repo_path, wt)
            except Exception:
                pass
        shutil.rmtree(parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# N1 — Upstream Novelty Gate
# ---------------------------------------------------------------------------

def run_n1_upstream_novelty(
    repo_path: Path,
    patch_text: str,
    feature_test_path: Path,
    timeout_s: int = 120,
    docker_image: str = "",
) -> GateResult:
    """N1: Fetch upstream default branch, grep new symbols, and verify feature tests fail against it."""
    console.print("\n[bold]N1[/bold] upstream-novelty check")

    # 1. Fetch latest origin (best-effort network; record status explicitly)
    fetch_rc, _, fetch_err = run_cmd("git fetch origin", cwd=repo_path, timeout_s=60)
    fetched = (fetch_rc == 0)

    # Resolve upstream default branch ref
    rc_ref, upstream_ref_out, _ = run_cmd("git rev-parse --verify origin/HEAD", cwd=repo_path)
    upstream_ref = "origin/HEAD" if rc_ref == 0 else "origin/main"

    # 2. Extract newly added public symbols from patch
    new_symbols: list[str] = []
    for line in patch_text.splitlines():
        if not (line.startswith("+") and not line.startswith("+++")):
            continue
        code = line[1:]
        m_cls = re.match(r"^class\s+([A-Z][A-Za-z0-9_]*)", code)
        if m_cls:
            new_symbols.append(m_cls.group(1))
        m_def = re.match(r"^def\s+([a-z][A-Za-z0-9_]*)", code)
        if m_def and not m_def.group(1).startswith("_"):
            new_symbols.append(m_def.group(1))
        m_const = re.match(r"^([A-Z][A-Z0-9_]{2,})\b", code)
        if m_const:
            new_symbols.append(m_const.group(1))

    new_symbols = sorted(set(new_symbols))

    symbol_hits: dict[str, list[str]] = {}
    inconclusive_notes: list[str] = []
    for sym in new_symbols:
        rc_g, out_g, _ = run_cmd(
            f'git grep -n -w "{sym}" {upstream_ref} -- src/ docs/ CHANGES.md',
            cwd=repo_path,
        )
        if rc_g == 0 and out_g.strip():
            hits = out_g.strip().splitlines()
            src_hits = [h for h in hits if ":src/" in h]
            if src_hits:
                symbol_hits[sym] = src_hits[:5]
            else:
                inconclusive_notes.append(f"{sym} mentioned in docs/CHANGES only: {hits[0][:100]}")

    # 3. Run feature tests WITHOUT patch on upstream default branch worktree
    parent = Path(tempfile.mkdtemp(prefix="tessera_n1_"))
    wt: Path | None = None
    upstream_tests_passed = False
    try:
        wt = create_worktree(repo_path, upstream_ref, "n1_wt", parent_dir=parent)
        if docker_image:
            from factory.gates import _run_docker_pytest
            rc_t, out_t, err_t = _run_docker_pytest(
                wt,
                docker_image,
                f"pytest /tests_n1/{feature_test_path.name} -v --tb=short --no-header --rootdir=/tests_n1 --import-mode=importlib",
                timeout_s,
                extra_mounts=[(feature_test_path.resolve().parent, "/tests_n1")],
            )
        else:
            cmd = (
                f'python -m pytest "{feature_test_path.resolve()}" -v --tb=short --no-header '
                f'--rootdir={wt} --import-mode=importlib'
            )
            rc_t, out_t, err_t = run_cmd(cmd, cwd=wt, timeout_s=timeout_s, env={"PYTHONPATH": str(wt)})
        upstream_tests_passed = (rc_t == 0)
    finally:
        if wt is not None:
            try:
                remove_worktree(repo_path, wt)
            except Exception:
                pass
        shutil.rmtree(parent, ignore_errors=True)

    passed = (not symbol_hits) and (not upstream_tests_passed)
    if passed:
        console.print(f"  [green]✓ N1 passed[/green] (fetched={fetched}, {len(new_symbols)} new symbols absent from upstream, feature tests FAIL on {upstream_ref})")
    else:
        console.print(f"  [red]✗ N1 failed[/red] (symbol_hits={list(symbol_hits)}, upstream_tests_passed={upstream_tests_passed})")

    return GateResult(
        passed=passed,
        evidence={
            "fetched_origin": fetched,
            "fetch_error": fetch_err.strip() if not fetched else "",
            "upstream_ref": upstream_ref,
            "checked_symbols": new_symbols,
            "src_symbol_hits": symbol_hits,
            "inconclusive_notes": inconclusive_notes,
            "feature_tests_passed_on_upstream": upstream_tests_passed,
        },
    )


# ---------------------------------------------------------------------------
# G7 — Independent Solver Gate (Provider-agnostic, sees ONLY instruction.md + base repo)
# ---------------------------------------------------------------------------

SOLVER_SYSTEM_PROMPT = """You are an independent software engineer solving a feature development task on an existing open-source repository.
You are given ONLY the task specification (instruction.md) and the base source files of the repository.
Implement the specification faithfully so that all acceptance criteria and existing tests pass.
Rules:
- Respect the repository's existing conventions, types, and import constraints (never add eager top-level stdlib imports if tests guard startup import footprint).
- Output exact search-and-replace edit blocks ONLY on files under `src/` using this exact format (one block per replacement; copy FIND text verbatim from the base source):

<<<REASONING>>>
Brief summary of implementation
<<<END_REASONING>>>

<<<EDIT file="src/path/to/file.py">>>
<<<FIND>>>
exact existing source lines to match verbatim
<<<END_FIND>>>
<<<REPLACE>>>
new replacement source lines
<<<END_REPLACE>>>
<<<END_EDIT>>>
"""


def _read_untruncated_context(wt: Path, target_module: str, max_chars: int = 55000) -> str:
    """Provide clean verbatim source context (no line numbers) for accurate search-replace edits."""
    parts: list[str] = []
    for rel in sorted({target_module, "src/click/__init__.py"}):
        p = wt / rel
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > max_chars:
                head = text[: max_chars // 2]
                tail = text[-(max_chars // 2) :]
                text = head + "\n\n# ... [middle truncated] ...\n\n" + tail
            parts.append(f"=== FILE: {rel} ===\n{text}")
    return "\n\n".join(parts)


def run_g7_solver(
    repo_path: Path,
    base_commit: str,
    instruction_md: str,
    target_module: str,
    feature_test_path: Path,
    fail_to_pass: list[str],
    pass_to_pass: list[str],
    cfg: FactoryConfig,
    ledger: UsageLedger,
    docker_image: str = "tessera-click-hardened:cf19179",
) -> G7Result:
    """G7: Independent solver sees ONLY instruction.md and base repo; graded offline in container."""
    solver_provider = os.environ.get(cfg.gates.solver_provider_env) or os.environ.get(cfg.llm.provider_env, "mock")
    solver_model = os.environ.get(cfg.gates.solver_model_env) or os.environ.get(cfg.llm.model_env, "mock-model")
    console.print(f"\n[bold]G7[/bold] independent solver ({solver_provider}/{solver_model}, max {cfg.gates.solver_attempts} attempts)")

    # Provide ONLY base source files mentioned / target module + __init__.py (NO tests, NO reference patch!)
    parent = Path(tempfile.mkdtemp(prefix="tessera_g7_"))
    wt: Path | None = None
    try:
        wt = create_worktree(repo_path, base_commit, "g7_base", parent_dir=parent)
        solver_source_context = _read_untruncated_context(wt, target_module)
    finally:
        if wt is not None:
            try:
                remove_worktree(repo_path, wt)
            except Exception:
                pass
        shutil.rmtree(parent, ignore_errors=True)
    feedback = ""
    attempts_used = 0
    solved = False
    last_grading: dict[str, Any] = {}
    attempts_log: list[dict[str, Any]] = []
    last_patch = ""

    for attempt in range(1, cfg.gates.solver_attempts + 1):
        attempts_used = attempt
        prompt = (
            f"## Task Specification (instruction.md)\n{instruction_md}\n\n"
            f"## Base Repository Source Files (commit {base_commit[:12]})\n{solver_source_context}\n"
        )
        if feedback:
            prompt += f"\n## Previous Attempt Feedback\n{feedback}\n"

        # Temporarily measure ledger delta for solver call cost reporting
        cost_before = ledger.total_cost_usd
        tok_in_before = ledger.total_input_tokens
        tok_out_before = ledger.total_output_tokens

        data = call_llm(
            messages=[
                {"role": "system", "content": SOLVER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            provider_env=cfg.gates.solver_provider_env,
            model_env=cfg.gates.solver_model_env,
            ledger=ledger,
            cache_dir=cfg.output.cache_dir,
            max_tokens=cfg.llm.max_tokens,
            temperature=0.2,
            expect_json=False,
        )

        from factory.repo import synthesize_patch_from_response
        raw_text = str(data.get("content", ""))
        ok_synth, patch, err_synth = synthesize_patch_from_response(repo_path, base_commit, raw_text)
        if not ok_synth:
            feedback = f"Attempt {attempt} edits did not apply cleanly: {err_synth}. Ensure verbatim FIND blocks."
            last_grading = {"reward": 0.0, "error": err_synth}
            console.print(f"  [yellow]G7 attempt {attempt}: edit synthesis failed ({err_synth[:80]})[/yellow]")
            continue
        last_patch = patch

        # Grade candidate patch cleanly in isolated worktree + Docker container
        grade_parent = Path(tempfile.mkdtemp(prefix="tessera_g7_eval_"))
        eval_wt: Path | None = None
        try:
            eval_wt = create_worktree(repo_path, base_commit, "g7_eval", parent_dir=grade_parent)
            pfile = grade_parent / "solver.patch"
            pfile.write_text(patch, encoding="utf-8", newline="\n")
            ok_apply, msg_apply = apply_patch(pfile, eval_wt)
            if not ok_apply:
                feedback = f"Attempt {attempt} patch failed `git apply`:\n{msg_apply}\nCheck exact context lines and line numbers."
                last_grading = {"reward": 0.0, "error": f"git apply failed: {msg_apply}"}
                console.print(f"  [yellow]G7 attempt {attempt}: patch apply failed[/yellow]")
                continue

            # Grade inside container using official-style grading_summary logic
            tests_stage = grade_parent / "tests_stage"
            (tests_stage / "feature").mkdir(parents=True, exist_ok=True)
            (grade_parent / "logs_verifier").mkdir(parents=True, exist_ok=True)
            shutil.copy2(feature_test_path, tests_stage / "feature" / feature_test_path.name)
            (tests_stage / "fail_to_pass.json").write_text(json.dumps(fail_to_pass, indent=2), encoding="utf-8")
            (tests_stage / "pass_to_pass.json").write_text(json.dumps(pass_to_pass, indent=2), encoding="utf-8")

            from factory.packager import generate_grade_py
            (tests_stage / "grade.py").write_text(generate_grade_py(), encoding="utf-8", newline="\n")

            if sys.platform == "win32":
                cmd = [
                    "wsl", "-d", "Ubuntu", "docker", "run", "--rm", "--network", "none",
                    "-v", f"{_to_wsl_path(eval_wt)}:/app",
                    "-v", f"{_to_wsl_path(tests_stage)}:/tests",
                    "-v", f"{_to_wsl_path(grade_parent / 'logs_verifier')}:/logs/verifier",
                    docker_image,
                    "bash", "-c", "PYTHONPATH=/app python /tests/grade.py",
                ]
            else:
                cmd = [
                    "docker", "run", "--rm", "--network", "none",
                    "-v", f"{eval_wt.resolve()}:/app",
                    "-v", f"{tests_stage.resolve()}:/tests",
                    "-v", f"{(grade_parent / 'logs_verifier').resolve()}:/logs/verifier",
                    docker_image,
                    "bash", "-c", "PYTHONPATH=/app python /tests/grade.py",
                ]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            summary_file = grade_parent / "logs_verifier" / "grading_summary.json"
            if summary_file.exists():
                last_grading = json.loads(summary_file.read_text(encoding="utf-8"))
                reward = float(last_grading.get("reward", 0.0))
                last_grading["solver_model"] = solver_model
                last_grading["attempt_tokens"] = (ledger.total_input_tokens - tok_in_before) + (ledger.total_output_tokens - tok_out_before)
                last_grading["attempt_estimated_cost_usd"] = round(ledger.total_cost_usd - cost_before, 6)
                attempts_log.append({"attempt": attempt, **last_grading})
                if reward >= 1.0:
                    solved = True
                    console.print(f"  [green]✓ G7 solved on attempt {attempt}[/green] (reward=1.0)")
                    break
                else:
                    # Only leak regression errors / non-feature failures to avoid leaking hidden feature tests
                    reg_n = last_grading.get("regression_failures_count", 0)
                    feedback = (
                        f"Attempt {attempt} graded reward={reward} "
                        f"(existing baseline regressions failed: {reg_n}; sample: {last_grading.get('regression_failures_sample', [])}). "
                        f"Re-verify every acceptance criterion, exact error message template, and startup import rules in instruction.md."
                    )
                    console.print(f"  [yellow]G7 attempt {attempt}: partial/fail reward={reward}[/yellow]")
            else:
                last_grading = {"reward": 0.0, "stderr": proc.stderr[:400]}
                feedback = f"Container evaluation crashed (rc={proc.returncode}): {proc.stderr[:300]}"
        finally:
            if eval_wt is not None:
                try:
                    remove_worktree(repo_path, eval_wt)
                except Exception:
                    pass
            shutil.rmtree(grade_parent, ignore_errors=True)

    return G7Result(
        passed=solved,
        solved=solved,
        attempts=attempts_used,
        notes=f"model={solver_provider}/{solver_model} | reward={last_grading.get('reward', 0.0)}",
        evidence={"grading": last_grading, "attempts_log": attempts_log, "last_patch": last_patch},
    )
