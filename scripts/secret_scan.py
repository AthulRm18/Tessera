"""Secret scan over working tree and full git log history."""

import re
import subprocess
from pathlib import Path

PATTERNS = [
    (r"(?:AIza[0-9A-Za-z_-]{35})", "Google API Key"),
    (r"(?:sk-[a-zA-Z0-9_-]{30,})", "OpenAI / Generic Secret Key"),
    (r"(?:sk-ant-[a-zA-Z0-9_-]{20,})", "Anthropic Secret Key"),
    (r"(?:ghp_[a-zA-Z0-9]{36})", "GitHub Personal Access Token"),
    (r"(?:gho_[a-zA-Z0-9]{36})", "GitHub OAuth Access Token"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    (r"(?:password|passwd|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]", "Hardcoded Secret/Password"),
]

def scan_text(text: str, source_label: str) -> list[str]:
    findings = []
    for line_num, line in enumerate(text.splitlines(), start=1):
        for pattern, label in PATTERNS:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for m in matches:
                # Ignore placeholders in documentation or comments
                val = m.group(0)
                if any(placeholder in val.lower() for placeholder in ["dummy", "fake", "example", "secret-key", "placeholder", "your_api_key"]):
                    continue
                findings.append(f"[{label}] {source_label}:{line_num} -> {val[:12]}...")
    return findings

def main():
    print("=== TESSERA HYGIENE & SECRET SCAN ===\n")

    # 1. Check git ls-files
    print("1. Checking git ls-files for forbidden tracked paths...")
    res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    tracked = res.stdout.splitlines()

    forbidden_patterns = [
        r"^\.env(\.local)?$",
        r"^_standin_",
        r"^runs/",
        r"^packages/",
        r"^\.venv/",
        r"^jobs/",
        r"^temp_harbor_init/",
        r"\.pyc$",
        r"__pycache__",
    ]
    
    forbidden_found = []
    for f in tracked:
        for pat in forbidden_patterns:
            if re.search(pat, f):
                forbidden_found.append((f, pat))
    
    if forbidden_found:
        print("  [FAIL] Forbidden files tracked in git:")
        for f, pat in forbidden_found:
            print(f"    - {f} (matched {pat})")
    else:
        print("  [PASS] Clean git ls-files. Zero stand-in repos, .env, runs, or caches tracked.")
        print(f"  Total tracked files: {len(tracked)}")

    # 2. Secret scan on working tree
    print("\n2. Scanning working tree files for secrets...")
    working_tree_findings = []
    root = Path(".")
    for path in root.rglob("*"):
        if path.is_file():
            # Skip git internals, virtual environment, and stand-in repos
            rel = path.as_posix()
            if any(skip in rel for skip in [".git/", ".venv/", "_standin_", "jobs/", "node_modules/"]):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                findings = scan_text(content, rel)
                working_tree_findings.extend(findings)
            except Exception:
                pass

    if working_tree_findings:
        print("  [FAIL] Secrets found in working tree:")
        for f in working_tree_findings:
            print(f"    - {f}")
    else:
        print("  [PASS] Zero secrets found in working tree.")

    # 3. Secret scan on full git history
    print("\n3. Scanning full git log history (git log -p)...")
    git_log_res = subprocess.run(["git", "log", "-p"], capture_output=True, text=True, check=True)
    git_findings = scan_text(git_log_res.stdout, "git-history")

    if git_findings:
        print("  [FAIL] Secrets found in git history:")
        for f in git_findings:
            print(f"    - {f}")
    else:
        print("  [PASS] Zero secrets found in entire git commit history.")

    print("\n=== SCAN COMPLETE ===")

if __name__ == "__main__":
    main()
