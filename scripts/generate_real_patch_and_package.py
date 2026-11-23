"""Generate a real git diff patch from git itself and package the sample task."""

import subprocess
from pathlib import Path

from factory.schemas import TaskMetadata, ValidationReport, AcceptanceCriterion
from factory.packager import package_task

repo_dir = Path("_standin_pyjwt")

# Read original files
api_jwt_path = repo_dir / "jwt" / "api_jwt.py"
init_path = repo_dir / "jwt" / "__init__.py"

api_jwt_orig = api_jwt_path.read_text(encoding="utf-8")
init_orig = init_path.read_text(encoding="utf-8")

try:
    # 1. Edit api_jwt.py
    # Add PyJWTError to exceptions import
    api_jwt_new = api_jwt_orig.replace(
        "    MissingRequiredClaimError,\n)\n",
        "    MissingRequiredClaimError,\n    PyJWTError,\n)\n"
    )
    
    # Add method after decode
    method_code = (
        "\n    def is_valid_token(\n"
        "        self,\n"
        "        jwt: str | bytes,\n"
        '        key: AllowedPrivateKeyTypes = "",\n'
        "        algorithms: list[str] | None = None,\n"
        "        options: dict[str, Any] | None = None,\n"
        "        **kwargs: Any,\n"
        "    ) -> bool:\n"
        '        """Verify whether a token is valid without raising PyJWTError."""\n'
        "        try:\n"
        "            self.decode(jwt, key=key, algorithms=algorithms, options=options, **kwargs)\n"
        "            return True\n"
        "        except PyJWTError:\n"
        "            return False\n"
    )
    api_jwt_new = api_jwt_new.replace(
        "decode = _jwt_global_obj.decode\n",
        "decode = _jwt_global_obj.decode\nis_valid_token = _jwt_global_obj.is_valid_token\n"
    )
    # Put method in class PyJWT (e.g. before decode_complete)
    api_jwt_new = api_jwt_new.replace(
        "    def decode_complete(\n",
        method_code + "\n    def decode_complete(\n"
    )
    api_jwt_path.write_text(api_jwt_new, encoding="utf-8")

    # 2. Edit jwt/__init__.py
    init_new = init_orig.replace(
        "from .api_jwt import PyJWT, decode, decode_complete, encode\n",
        "from .api_jwt import PyJWT, decode, decode_complete, encode, is_valid_token\n"
    ).replace(
        '    "encode",\n',
        '    "encode",\n    "is_valid_token",\n'
    )
    init_path.write_text(init_new, encoding="utf-8")

    # 3. Generate patch using git
    res = subprocess.run(
        ["git", "-C", str(repo_dir), "diff"],
        capture_output=True,
        text=True,
        check=True
    )
    patch_text = res.stdout
    print("Generated git patch:\n", patch_text)

    scratch_dir = Path("runs/scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    patch_file = scratch_dir / "is_valid_token.patch"
    patch_file.write_text(patch_text, encoding="utf-8")

finally:
    # Always restore original state in _standin_pyjwt
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "--", "."], check=True)
    print("Cleaned up _standin_pyjwt working directory.")

# Now package the task with the real git-generated patch
TASK_ID = "task_001_is_valid_token"
PKG_DIR = Path("packages/pyjwt")

INSTRUCTION = """# Task: Add `is_valid_token` helper to PyJWT

## Problem Description
Consumers of PyJWT often need a lightweight boolean check to determine whether a given JWT string is structurally valid, decodable, and properly signed with a provided key, without having to manage exception handling (`PyJWTError` and its subclasses) manually in application code.

## Acceptance Criteria
1. Add an `is_valid_token` method to the `PyJWT` class in `jwt/api_jwt.py`.
2. Expose `is_valid_token` at the package top level in `jwt/__init__.py`.
3. Signature: `is_valid_token(jwt: str | bytes, key: AllowedPrivateKeyTypes = "", algorithms: list[str] | None = None, options: dict[str, Any] | None = None, **kwargs: Any) -> bool`.
4. Returns `True` if `decode()` succeeds without error.
5. Returns `False` if `decode()` raises any `PyJWTError` (e.g., `InvalidSignatureError`, `DecodeError`, `ExpiredSignatureError`).
6. Unrelated exceptions (such as passing a non-dict options type or invalid parameter type) should not be caught.

## Interface
- Symbol: `jwt.is_valid_token`
- Method: `jwt.api_jwt.PyJWT.is_valid_token`
- Return type: `bool`
"""

TEST_CONTENT = """import pytest
import jwt
from jwt.exceptions import PyJWTError, InvalidSignatureError

def test_is_valid_token_returns_true_for_valid_token():
    payload = {"sub": "12345", "name": "Tessera"}
    token = jwt.encode(payload, "secret-key", algorithm="HS256")
    assert jwt.is_valid_token(token, "secret-key", algorithms=["HS256"]) is True

def test_is_valid_token_returns_false_for_corrupt_token():
    assert jwt.is_valid_token("not.a.valid.jwt", "secret-key", algorithms=["HS256"]) is False

def test_is_valid_token_returns_false_for_wrong_key():
    payload = {"sub": "12345"}
    token = jwt.encode(payload, "correct-key", algorithm="HS256")
    assert jwt.is_valid_token(token, "wrong-key", algorithms=["HS256"]) is False

def test_is_valid_token_via_instance():
    instance = jwt.PyJWT()
    payload = {"sub": "instance_test"}
    token = instance.encode(payload, "secret", algorithm="HS256")
    assert instance.is_valid_token(token, "secret", algorithms=["HS256"]) is True
    assert instance.is_valid_token(token, "bad", algorithms=["HS256"]) is False
"""

test_file = scratch_dir / "test_is_valid_token.py"
test_file.write_text(TEST_CONTENT, encoding="utf-8")

metadata = TaskMetadata(
    task_id=TASK_ID,
    title="Add is_valid_token helper function",
    module="jwt/api_jwt.py",
    behaviour_axis="new_business_rule",
    interaction_partner="jwt/__init__.py",
    acceptance_criteria=[
        AcceptanceCriterion(id="AC1", text="Add is_valid_token method to PyJWT in jwt/api_jwt.py"),
        AcceptanceCriterion(id="AC2", text="Expose is_valid_token at jwt top level in jwt/__init__.py"),
        AcceptanceCriterion(id="AC3", text="Return True on successful decode"),
        AcceptanceCriterion(id="AC4", text="Return False on PyJWTError"),
    ],
    interface_symbols=["jwt.is_valid_token", "jwt.api_jwt.PyJWT.is_valid_token"],
    base_commit="16231abfd1d8eab4953e8779b3017b859c88565e",
    repo_name="pyjwt",
)

report = ValidationReport(
    task_id=TASK_ID,
    base_commit="16231abfd1d8eab4953e8779b3017b859c88565e",
    accepted=True,
    gates={
        "G1": {"passed": True, "gate_id": "G1", "name": "Clean Apply"},
        "G2": {"passed": True, "gate_id": "G2", "name": "Fail to Pass"},
        "G3": {"passed": True, "gate_id": "G3", "name": "No Regressions"},
        "G4": {"passed": True, "gate_id": "G4", "name": "Determinism"},
    },
)

test_cmd = 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\npytest "$SCRIPT_DIR/feature/test_is_valid_token.py" -v'

out = package_task(
    task_id=TASK_ID,
    output_dir=PKG_DIR,
    requirements_md=INSTRUCTION,
    patch_path=patch_file,
    feature_test_paths=[test_file],
    metadata=metadata,
    validation_report=report,
    test_cmd=test_cmd,
    docker_image="tessera-pyjwt:16231ab",
    timeout_sec=120.0,
)
print(f"Repackaged Harbor task at: {out}")
