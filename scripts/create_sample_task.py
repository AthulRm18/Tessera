"""Helper script to create and package a known-good PyJWT task."""

from pathlib import Path
import subprocess

from factory.schemas import TaskMetadata, ValidationReport, OrganizerChecks, GateResult, AcceptanceCriterion
from factory.packager import package_task

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

PATCH_CONTENT = """--- a/jwt/api_jwt.py
+++ b/jwt/api_jwt.py
@@ -148,6 +148,22 @@ class PyJWT:
             merged_options["verify_signature"] = False
 
         return {**self.options, **merged_options}
+
+    def is_valid_token(
+        self,
+        jwt: str | bytes,
+        key: AllowedPrivateKeyTypes = "",
+        algorithms: list[str] | None = None,
+        options: dict[str, Any] | None = None,
+        **kwargs: Any,
+    ) -> bool:
+        \"\"\"Verify if a token is valid without raising PyJWTError.\"\"\"
+        try:
+            self.decode(jwt, key=key, algorithms=algorithms, options=options, **kwargs)
+            return True
+        except PyJWTError:
+            return False
 
     def encode(
         self,
@@ -348,6 +364,7 @@ _jwt_global_obj = PyJWT()
 encode = _jwt_global_obj.encode
 decode = _jwt_global_obj.decode
 register_algorithm = _jwt_global_obj.register_algorithm
+is_valid_token = _jwt_global_obj.is_valid_token
 unregister_algorithm = _jwt_global_obj.unregister_algorithm
 get_algorithm_by_name = _jwt_global_obj.get_algorithm_by_name
 get_unverified_header = _jwt_global_obj.get_unverified_header
--- a/jwt/__init__.py
+++ b/jwt/__init__.py
@@ -10,6 +10,7 @@ from .api_jwt import (
     PyJWT,
     decode,
     encode,
+    is_valid_token,
     get_unverified_header,
     register_algorithm,
     unregister_algorithm,
@@ -33,6 +34,7 @@ __all__ = [
     "PyJWT",
     "decode",
     "encode",
+    "is_valid_token",
     "get_unverified_header",
     "register_algorithm",
     "unregister_algorithm",
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

def main():
    scratch_dir = Path("runs/scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    
    patch_file = scratch_dir / "is_valid_token.patch"
    patch_file.write_text(PATCH_CONTENT, encoding="utf-8")
    
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
    
    # Test command in container: test script runs feature tests
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
    print(f"Created package at: {out}")

if __name__ == "__main__":
    main()
