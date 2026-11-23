"""Repository profiling, baseline testing, repo map, and git worktree management.

All repo-specific details come from config.yaml only.
No repo names, paths, language assumptions, or hard-coding anywhere in this file.
Swapping repos = only config.yaml change + rerun.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from factory.config import FactoryConfig

console = Console()


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: str,
    cwd: str | Path,
    timeout_s: int = 120,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a shell command with timeout. Returns (returncode, stdout, stderr).

    Never raises on non-zero exit — callers decide what to do.
    Returns (-1, "", error_msg) on timeout.
    """
    merged = {**os.environ, **(env or {})}
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=merged,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"[TIMEOUT] Command exceeded {timeout_s}s: {cmd}"
    except Exception as exc:
        return -2, "", f"[ERROR] {exc}"


# ---------------------------------------------------------------------------
# Test result model
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    """Parsed results from one test run."""

    __test__ = False  # Prevent pytest from treating this dataclass as a test suite
    passed: bool           # overall: return code 0 and no unexpected failures
    total: int = 0
    n_passed: int = 0
    n_failed: int = 0
    n_errors: int = 0
    n_skipped: int = 0
    duration_s: float = 0.0
    return_code: int = 0
    raw_output: str = ""
    # Individual test ids — populated when parseable
    passed_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    error_ids: list[str] = field(default_factory=list)
    # Failure types: "assertion" | "import_error" | "syntax_error" | "unknown"
    failure_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total": self.total,
            "n_passed": self.n_passed,
            "n_failed": self.n_failed,
            "n_errors": self.n_errors,
            "n_skipped": self.n_skipped,
            "duration_s": self.duration_s,
            "return_code": self.return_code,
            "passed_ids": self.passed_ids,
            "failed_ids": self.failed_ids,
            "error_ids": self.error_ids,
            "failure_types": self.failure_types,
        }


# ---------------------------------------------------------------------------
# Result parsers (one per result_format; add more here as needed)
# ---------------------------------------------------------------------------

def _parse_pytest(output: str, return_code: int) -> TestResult:
    """Parse pytest -v text output."""
    result = TestResult(passed=(return_code == 0), return_code=return_code, raw_output=output)

    # Individual test lines: e.g. "tests/foo.py::test_bar PASSED [ 20%]" or without percentage
    line_re = re.compile(r"^(.*?)\s+(PASSED|FAILED|ERROR)(\s*\[\s*\d+%\s*\])?$")
    for line in output.splitlines():
        line = line.strip()
        m = line_re.match(line)
        if m:
            tid = m.group(1).strip()
            status = m.group(2)
            if status == "PASSED":
                result.passed_ids.append(tid)
                result.n_passed += 1
            elif status == "FAILED":
                result.failed_ids.append(tid)
                result.n_failed += 1
            elif status == "ERROR":
                result.error_ids.append(tid)
                result.n_errors += 1

    # Summary line: "5 passed, 2 failed, 1 skipped in 0.32s"
    summary_re = re.compile(
        r"(\d+) passed|(\d+) failed|(\d+) error|(\d+) skipped|in ([\d.]+)s"
    )
    for m in summary_re.finditer(output):
        if m.group(1):
            result.n_passed = max(result.n_passed, int(m.group(1)))
        if m.group(2):
            result.n_failed = max(result.n_failed, int(m.group(2)))
        if m.group(3):
            result.n_errors = max(result.n_errors, int(m.group(3)))
        if m.group(4):
            result.n_skipped = int(m.group(4))
        if m.group(5):
            result.duration_s = float(m.group(5))

    result.total = result.n_passed + result.n_failed + result.n_errors + result.n_skipped

    # Classify failure types (import_error, syntax_error, assertion, unknown)
    for line in output.splitlines():
        if "ImportError" in line or "ModuleNotFoundError" in line:
            result.failure_types.append("import_error")
        elif "SyntaxError" in line:
            result.failure_types.append("syntax_error")
        elif "AssertionError" in line:
            result.failure_types.append("assertion")

    if result.n_failed > 0 and not result.failure_types:
        result.failure_types.append("unknown")

    return result


def _parse_mocha(output: str, return_code: int) -> TestResult:
    """Parse mocha --reporter dot or spec output (npm test)."""
    result = TestResult(passed=(return_code == 0), return_code=return_code, raw_output=output)

    # "323 passing (273ms)" or "5 failing"
    m_pass = re.search(r"(\d+) passing", output)
    m_fail = re.search(r"(\d+) failing", output)
    m_pend = re.search(r"(\d+) pending", output)
    m_dur  = re.search(r"\((\d+)ms\)", output)

    if m_pass:
        result.n_passed = int(m_pass.group(1))
    if m_fail:
        result.n_failed = int(m_fail.group(1))
    if m_pend:
        result.n_skipped = int(m_pend.group(1))
    if m_dur:
        result.duration_s = int(m_dur.group(1)) / 1000.0

    result.total = result.n_passed + result.n_failed + result.n_skipped
    return result


def _parse_junit_xml(output: str, return_code: int) -> TestResult:
    """Parse JUnit XML output (placeholder; extends when needed)."""
    # For now, fall back to exit-code only
    return TestResult(passed=(return_code == 0), return_code=return_code, raw_output=output)


def _parse_text(output: str, return_code: int) -> TestResult:
    """Fallback: just use return code."""
    return TestResult(passed=(return_code == 0), return_code=return_code, raw_output=output)


_PARSERS = {
    "pytest":    _parse_pytest,
    "mocha":     _parse_mocha,
    "jest":      _parse_mocha,   # jest output is similar enough
    "junit_xml": _parse_junit_xml,
    "text":      _parse_text,
}


def parse_test_output(output: str, return_code: int, fmt: str) -> TestResult:
    """Dispatch to the right parser based on result_format from config."""
    parser = _PARSERS.get(fmt, _parse_text)
    return parser(output, return_code)


# ---------------------------------------------------------------------------
# Repo operations
# ---------------------------------------------------------------------------

def get_base_commit(repo_path: str | Path, ref: str) -> str:
    """Resolve a git ref (branch, tag, or commit hash) to a full commit hash."""
    rc, stdout, stderr = run_cmd(f"git rev-parse {ref}", cwd=repo_path)
    if rc != 0:
        console.print(f"[red]✗ Cannot resolve ref '{ref}': {stderr.strip()}[/red]")
        return ""
    return stdout.strip()


def build_repo_map(repo_path: str | Path) -> list[str]:
    """Return list of all tracked files (relative paths)."""
    rc, stdout, _ = run_cmd("git ls-files", cwd=repo_path)
    if rc != 0:
        return []
    return sorted(line.strip() for line in stdout.splitlines() if line.strip())


def detect_languages(repo_map: list[str]) -> list[str]:
    """Infer languages from tracked file extensions."""
    ext_lang: dict[str, str] = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".java": "Java", ".rb": "Ruby", ".go": "Go", ".rs": "Rust",
        ".cpp": "C++", ".c": "C", ".cs": "C#", ".php": "PHP",
        ".kt": "Kotlin", ".swift": "Swift",
    }
    seen: set[str] = set()
    for f in repo_map:
        lang = ext_lang.get(Path(f).suffix.lower())
        if lang:
            seen.add(lang)
    return sorted(seen)


def run_setup(repo_path: str | Path, setup_cmd: str, timeout_s: int) -> bool:
    """Run the repo's setup command. Returns True on success."""
    if not setup_cmd:
        console.print("[dim]  no setup command — skipping[/dim]")
        return True
    console.print(f"  setup: [cyan]{setup_cmd}[/cyan]")
    rc, _, stderr = run_cmd(setup_cmd, cwd=repo_path, timeout_s=timeout_s)
    if rc != 0:
        console.print(f"[red]✗ Setup failed (exit {rc}): {stderr[:200]}[/red]")
        return False
    console.print("[green]  ✓ setup done[/green]")
    return True


def run_tests(
    repo_path: str | Path,
    test_cmd: str,
    timeout_s: int,
    result_format: str,
    extra_env: dict[str, str] | None = None,
) -> TestResult:
    """Run the test command and return a parsed TestResult."""
    if not test_cmd:
        return TestResult(passed=False, raw_output="No test_cmd set in config")
    rc, stdout, stderr = run_cmd(test_cmd, cwd=repo_path, timeout_s=timeout_s, env=extra_env)
    combined = stdout + ("\n" + stderr if stderr.strip() else "")
    return parse_test_output(combined, rc, result_format)


# ---------------------------------------------------------------------------
# Repo profile
# ---------------------------------------------------------------------------

@dataclass
class RepoProfile:
    """Everything known about the target repo after profiling."""

    repo_path: str
    base_ref: str
    base_commit: str = ""
    setup_cmd: str = ""
    test_cmd: str = ""
    result_format: str = "pytest"
    timeout_s: int = 120
    baseline: TestResult | None = None
    repo_map: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "repo_path": self.repo_path,
            "base_ref": self.base_ref,
            "base_commit": self.base_commit,
            "setup_cmd": self.setup_cmd,
            "test_cmd": self.test_cmd,
            "result_format": self.result_format,
            "timeout_s": self.timeout_s,
            "languages": self.languages,
            "repo_map_size": len(self.repo_map),
        }
        if self.baseline:
            d["baseline"] = self.baseline.to_dict()
        return d


def profile_repo(cfg: FactoryConfig) -> RepoProfile:
    """Profile the target repo. Baseline MUST be green; stops and reports if not."""
    repo_path = Path(cfg.repo.path).resolve()
    console.print(f"\n[bold]Profiling repo:[/bold] {repo_path}")

    if not repo_path.exists():
        console.print(f"[red]✗ Repo path does not exist: {repo_path}[/red]")
        return RepoProfile(repo_path=str(repo_path), base_ref=cfg.repo.base_ref)

    base_commit = get_base_commit(repo_path, cfg.repo.base_ref)
    console.print(f"  base commit : [cyan]{base_commit[:12] if base_commit else '(unresolved)'}[/cyan]")

    repo_map = build_repo_map(repo_path)
    languages = detect_languages(repo_map)
    console.print(f"  files       : {len(repo_map)} | languages: {', '.join(languages) or '?'}")

    if not run_setup(repo_path, cfg.repo.setup_cmd, cfg.repo.timeout_s):
        console.print("[red]✗ Setup failed — cannot proceed[/red]")

    console.print(f"  running baseline: [cyan]{cfg.repo.test_cmd}[/cyan]")
    baseline = run_tests(repo_path, cfg.repo.test_cmd, cfg.repo.timeout_s, cfg.repo.result_format)
    _print_test_result(baseline, "baseline")

    if not baseline.passed:
        console.print("[red bold]✗ BASELINE NOT GREEN — fix the repo before generating tasks[/red bold]")

    return RepoProfile(
        repo_path=str(repo_path),
        base_ref=cfg.repo.base_ref,
        base_commit=base_commit,
        setup_cmd=cfg.repo.setup_cmd,
        test_cmd=cfg.repo.test_cmd,
        result_format=cfg.repo.result_format,
        timeout_s=cfg.repo.timeout_s,
        baseline=baseline,
        repo_map=repo_map,
        languages=languages,
    )


def save_profile(profile: RepoProfile, path: str | Path) -> None:
    """Write profile.json to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=2)
    console.print(f"  saved → [cyan]{p}[/cyan]")


def _print_test_result(r: TestResult, label: str) -> None:
    color = "green" if r.passed else "red"
    mark = "✓" if r.passed else "✗"
    console.print(
        f"  [{color}]{mark} {label}[/{color}]: "
        f"{r.n_passed} passed, {r.n_failed} failed, "
        f"{r.n_errors} errors, {r.n_skipped} skipped "
        f"| {r.duration_s:.2f}s | rc={r.return_code}"
    )


# ---------------------------------------------------------------------------
# Patch application
# ---------------------------------------------------------------------------

def apply_patch(
    patch_path: str | Path,
    repo_path: str | Path,
    *,
    check_only: bool = False,
) -> tuple[bool, str]:
    """Apply (or check) a unified diff patch.

    Returns (success, message).
    With check_only=True, uses git apply --check (no changes made).
    """
    flag = "--check" if check_only else ""
    cmd = f"git apply {flag} {patch_path}"
    rc, stdout, stderr = run_cmd(cmd, cwd=repo_path)
    msg = (stdout + stderr).strip()
    return (rc == 0), msg


def reverse_patch(patch_path: str | Path, repo_path: str | Path) -> tuple[bool, str]:
    """Reverse-apply a patch (undo it)."""
    cmd = f"git apply --reverse {patch_path}"
    rc, stdout, stderr = run_cmd(cmd, cwd=repo_path)
    return (rc == 0), (stdout + stderr).strip()


# ---------------------------------------------------------------------------
# Git worktree management
# ---------------------------------------------------------------------------

def create_worktree(
    repo_path: str | Path,
    base_commit: str,
    name: str,
    parent_dir: str | Path | None = None,
) -> Path:
    """Create an isolated git worktree at the given commit.

    Returns the path to the new worktree. Raises RuntimeError on failure.
    All task work happens inside worktrees — never modify the repo in place.
    """
    repo_path = Path(repo_path).resolve()
    if parent_dir is None:
        parent_dir = Path(tempfile.mkdtemp(prefix="tessera_wt_"))
    wt_path = Path(parent_dir) / name

    rc, _, stderr = run_cmd(
        f"git worktree add {wt_path} {base_commit} --detach",
        cwd=repo_path,
    )
    if rc != 0:
        raise RuntimeError(f"Failed to create worktree at {wt_path}: {stderr.strip()}")
    console.print(f"  worktree: [cyan]{wt_path}[/cyan]")
    return wt_path


def remove_worktree(repo_path: str | Path, wt_path: str | Path) -> None:
    """Remove a git worktree and prune the reference."""
    rc, _, stderr = run_cmd(f"git worktree remove {wt_path} --force", cwd=repo_path)
    if rc != 0:
        console.print(f"[yellow]⚠ Could not remove worktree {wt_path}: {stderr.strip()}[/yellow]")
        # Try manual removal as fallback
        shutil.rmtree(str(wt_path), ignore_errors=True)
    run_cmd("git worktree prune", cwd=repo_path)


def list_worktrees(repo_path: str | Path) -> list[str]:
    """List all worktree paths for this repo."""
    rc, stdout, _ = run_cmd("git worktree list --porcelain", cwd=repo_path)
    if rc != 0:
        return []
    return [
        line.split(" ", 1)[1]
        for line in stdout.splitlines()
        if line.startswith("worktree ")
    ]
