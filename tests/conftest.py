"""pytest conftest.py — shared fixtures for gate integration tests.

Sets up a tiny git repo from tests/fixtures/sample_repo, commits it as
the base, then produces a known-good patch and several known-bad patches.
No LLM calls. No network. Pure local git operations.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

SAMPLE_REPO = Path(__file__).parent / "fixtures" / "sample_repo"


def _git(cmd: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    return subprocess.run(
        cmd, shell=True, cwd=str(cwd), capture_output=True, text=True, check=check
    )


@pytest.fixture(scope="session")
def fixture_git_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fresh git repo initialized from sample_repo, committed as base state."""
    repo = tmp_path_factory.mktemp("fixture_repo")

    # Copy sample_repo files
    for src in SAMPLE_REPO.iterdir():
        if src.name in (".pytest_cache", "__pycache__"):
            continue
        dst = repo / src.name
        if src.is_file():
            shutil.copy2(src, dst)

    # Init git repo
    _git("git init -b main", repo)
    _git('git config user.email "test@tessera.local"', repo)
    _git('git config user.name "Tessera Test"', repo)
    _git("git add -A", repo)
    _git('git commit -m "Base state"', repo)

    return repo


@pytest.fixture(scope="session")
def fixture_base_commit(fixture_git_repo: Path) -> str:
    result = _git("git rev-parse HEAD", fixture_git_repo)
    return result.stdout.strip()


@pytest.fixture(scope="session")
def good_patch(fixture_git_repo: Path) -> Path:
    """Patch that adds Cart.apply_discount — feature tests will fail without it, pass with it."""
    # Modify cart.py to add the method
    cart_path = fixture_git_repo / "cart.py"
    original = cart_path.read_text(encoding="utf-8")

    addition = textwrap.dedent("""
    def apply_discount(self, pct: float) -> float:
        \"\"\"Apply a percentage discount (0–100) and return the discounted subtotal.\"\"\"
        if not 0.0 <= pct <= 100.0:
            raise ValueError(f"Discount percentage must be 0–100, got {pct}")
        factor = 1.0 - (pct / 100.0)
        return round(self.subtotal * factor, 2)
    """)

    # Append before the last line of the class (after clear method)
    new_content = original.rstrip() + "\n" + textwrap.indent(addition, "    ") + "\n"
    cart_path.write_text(new_content, encoding="utf-8")

    # Generate patch
    result = _git("git diff cart.py", fixture_git_repo)
    patch_path = fixture_git_repo / "good_patch.patch"
    patch_path.write_text(result.stdout, encoding="utf-8")

    # Restore original
    cart_path.write_text(original, encoding="utf-8")

    return patch_path


@pytest.fixture(scope="session")
def bad_patch_no_apply(fixture_git_repo: Path) -> Path:
    """A patch that cannot apply cleanly (mangled line numbers)."""
    patch = textwrap.dedent("""\
        --- a/cart.py
        +++ b/cart.py
        @@ -9999,7 +9999,7 @@
        -    this_line_does_not_exist()
        +    replaced_with_garbage()
    """)
    p = fixture_git_repo / "bad_patch_g1.patch"
    p.write_text(patch, encoding="utf-8")
    return p


@pytest.fixture(scope="session")
def bad_patch_tests_pass_on_base(fixture_git_repo: Path) -> Path:
    """A patch that adds something harmless — but the 'feature tests' already pass on base."""
    # This patch just adds a comment — no real new feature
    patch = textwrap.dedent("""\
        --- a/cart.py
        +++ b/cart.py
        @@ -1,4 +1,5 @@
         \"\"\"A simple shopping cart for testing feature additions and regressions.\"\"\"
        +# trivial comment — no real feature
         
         from __future__ import annotations
    """)
    p = fixture_git_repo / "bad_patch_g2_trivial.patch"
    p.write_text(patch, encoding="utf-8")
    return p


@pytest.fixture(scope="session")
def feature_test_dir(fixture_git_repo: Path) -> Path:
    """Feature tests for the apply_discount feature — FAIL on base, PASS with good_patch."""
    test_dir = fixture_git_repo / "feature_tests"
    test_dir.mkdir(exist_ok=True)

    test_code = textwrap.dedent("""\
        \"\"\"Feature tests for Cart.apply_discount.
        AC1: apply_discount returns subtotal reduced by pct percent.
        AC2: apply_discount raises ValueError for pct outside 0–100.
        AC3: apply_discount(0) returns unchanged subtotal.
        \"\"\"
        import pytest
        from cart import Cart

        def test_discount_applied():
            \"\"\"AC1\"\"\"
            cart = Cart()
            cart.add_item("Widget", 10.0, 2)   # subtotal = 20.0
            result = cart.apply_discount(10)    # 10% off = 18.0
            assert result == pytest.approx(18.0)

        def test_discount_zero_percent():
            \"\"\"AC3\"\"\"
            cart = Cart()
            cart.add_item("Widget", 10.0)
            assert cart.apply_discount(0) == pytest.approx(10.0)

        def test_discount_full():
            \"\"\"AC1 boundary\"\"\"
            cart = Cart()
            cart.add_item("Widget", 10.0)
            assert cart.apply_discount(100) == pytest.approx(0.0)

        def test_discount_invalid_over_100():
            \"\"\"AC2\"\"\"
            cart = Cart()
            cart.add_item("Widget", 5.0)
            with pytest.raises(ValueError, match="0–100"):
                cart.apply_discount(110)

        def test_discount_invalid_negative():
            \"\"\"AC2\"\"\"
            cart = Cart()
            cart.add_item("Widget", 5.0)
            with pytest.raises(ValueError):
                cart.apply_discount(-5)
    """)

    (test_dir / "test_apply_discount.py").write_text(test_code, encoding="utf-8")
    return test_dir


@pytest.fixture(scope="session")
def trivial_feature_test_dir(fixture_git_repo: Path) -> Path:
    """Feature tests that PASS even without any patch — for testing G2 reject."""
    test_dir = fixture_git_repo / "trivial_feature_tests"
    test_dir.mkdir(exist_ok=True)

    test_code = textwrap.dedent("""\
        \"\"\"Trivial test that always passes — no feature needed.\"\"\"
        def test_always_passes():
            assert 1 + 1 == 2
    """)
    (test_dir / "test_trivial.py").write_text(test_code, encoding="utf-8")
    return test_dir
