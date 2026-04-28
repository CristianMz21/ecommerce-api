#!/usr/bin/env python3
"""
STRICT Suppression Detection Script
===================================
This script enforces ZERO SUPPRESSIONS rule.

Any suppression found = FAILED (exit 1)

PROTECTED FILE: Do not modify this script.
It is executed by pre-commit on every commit.

Usage:
    python scripts/check_suppressions.py          # Check all
    python scripts/check_suppressions.py --code    # Check code only
    python scripts/check_suppressions.py --toml    # Check pyproject.toml only
    python scripts/check_suppressions.py --strict # Required for pre-commit

EXIT CODES:
    0 = No suppressions found (PASS)
    1 = Suppressions found (FAIL)
"""

import argparse
import re
import sys
from pathlib import Path

PYTHON_SUPPRESSION_PATTERNS = [
    (r"#\s*noqa\b", "noqa comment"),
    (r"#\s*type:\s*ignore", "type: ignore comment"),
    (r"#\s*pylint:\s*disable", "pylint disable comment"),
    (r"#\s*nosec", "nosec comment"),
    (r"@pytest\.mark\.skip\b", "pytest.mark.skip decorator"),
    (r"@pytest\.mark\.skipif\b", "pytest.mark.skipif decorator"),
    (r"@pytest\.mark\.xfail\b", "pytest.mark.xfail decorator"),
    (r"coverage:\s*ignore", "coverage ignore comment"),
    (r"coverage:\s*no-cover", "coverage no-cover comment"),
    (r"#\s*ignore:\s*\[", "ignore comment with list"),
    (r"#\s*disable\s*=\s*\[", "disable comment with list"),
    (r"@unittest\.skip\b", "unittest.skip decorator"),
    (r"@unittest\.skipIf\b", "unittest.skipIf decorator"),
    (r"skip\(reason=", "skip with reason"),
]

TOML_SUPPRESSION_PATTERNS = [
    (r'extend-ignore\s*=', "extend-ignore (ruff suppression)"),
    (r'extend-select\s*=\s*\[\s*\]', "extend-select with empty array"),
    (r'per-file-ignores\s*=', "per-file-ignores (suppression)"),
    (r'strict\s*=\s*false', "strict = false (mypy suppression)"),
    (r'strict\s*=\s*0', "strict = 0 (mypy suppression)"),
    (r'ignore_missing_imports\s*=\s*true', "ignore_missing_imports = true"),
    (r'ignore_missing_imports\s*=\s*1', "ignore_missing_imports = 1"),
    (r'allowlist_descriptions', "allowlist_descriptions"),
    (r'disable_error_code', "disable_error_code"),
    (r'exclude\s*=\s*\[', "exclude array in ruff config"),
    (r'fail_on\:\s*none', "fail_on: none (suppression)"),
    (r'ignore\s*=\s*\[', "ignore array (suppression)"),
]

IGNORED_PATHS = [
    "migrations",
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
]

IGNORED_FILES = [
    "tests.py",
    "test_*.py",
    "*_test.py",
    "conftest.py",
    "__init__.py",
]

CHECKED_DIRS = ["store", "ecommerce_api"]


def is_path_ignored(file_path: str) -> bool:
    """Check if path should be ignored."""
    path_str = str(file_path)
    for ignored in IGNORED_PATHS:
        if f"/{ignored}/" in path_str or path_str.endswith(f"/{ignored}"):
            return True
    for ignored in IGNORED_FILES:
        if ignored in path_str:
            return True
    return False


def check_python_files(base_path: Path) -> list:
    """Scan Python files for suppressions. Returns list of (file, line, pattern)."""
    findings = []

    for dir_name in CHECKED_DIRS:
        dir_path = base_path / dir_name
        if not dir_path.is_dir():
            continue

        for py_file in dir_path.rglob("*.py"):
            if is_path_ignored(str(py_file)):
                continue

            try:
                content = py_file.read_text()
            except Exception:
                continue

            for line_num, line in enumerate(content.split("\n"), 1):
                for pattern, description in PYTHON_SUPPRESSION_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        rel_path = str(py_file.relative_to(base_path))
                        findings.append((rel_path, line_num, description))

    return findings


def check_toml_file(base_path: Path) -> list:
    """Scan pyproject.toml for suppressions. Returns list of (file, line, pattern)."""
    findings = []
    toml_path = base_path / "pyproject.toml"

    if not toml_path.is_file():
        return findings

    try:
        content = toml_path.read_text()
    except Exception:
        return findings

    lines = content.split("\n")
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue

        for pattern, description in TOML_SUPPRESSION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(("pyproject.toml", line_num, description))

    return findings


def print_banner() -> None:
    """Print the report banner."""
    print()
    print("=" * 70)
    print("SUPPRESSION DETECTION REPORT")
    print("=" * 70)


def print_findings(code_findings: list, toml_findings: list) -> None:
    """Print suppression findings."""
    if not code_findings and not toml_findings:
        print("NO SUPPRESSIONS FOUND")
        print("   - Python code: clean")
        print("   - pyproject.toml: clean")
        print("=" * 70)
        return

    if code_findings:
        print(f"\nCODE SUPPRESSIONS: {len(code_findings)} found")
        print("-" * 70)

        by_file = {}
        for file_path, line_num, pattern in code_findings:
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append((line_num, pattern))

        for file_path, items in sorted(by_file.items()):
            print(f"\n{file_path}")
            for line_num, pattern in items:
                print(f"   L{line_num}: {pattern}")

    if toml_findings:
        print(f"\nTOML SUPPRESSIONS: {len(toml_findings)} found")
        print("-" * 70)
        for file_path, line_num, pattern in toml_findings:
            print(f"   {file_path}:{line_num} - {pattern}")

    print()
    print("=" * 70)
    print("ZERO SUPPRESSIONS RULE VIOLATED")
    print("   Errors must be FIXED, not silenced!")
    print("=" * 70)


def run(strict: bool) -> bool:
    """
    Run suppression check.

    Returns:
        True if suppressions found (FAIL), False if clean (PASS)
    """
    script_path = Path(__file__)

    print_banner()

    base_path = script_path.parent.parent

    code_findings = check_python_files(base_path)
    toml_findings = check_toml_file(base_path)

    print_findings(code_findings, toml_findings)

    has_suppressions = bool(code_findings or toml_findings)

    if has_suppressions:
        print("\nFAILED: Suppressions detected!")
        if strict:
            print("   Exiting with error code 1 (strict mode)")
            return True
    else:
        print("\nPASSED: No suppressions found")

    return has_suppressions


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect code suppressions (ZERO SUPPRESSIONS rule)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python check_suppressions.py              # Check all
    python check_suppressions.py --strict    # Exit 1 if suppressions (for CI)
    python check_suppressions.py --code      # Python code only
    python check_suppressions.py --toml      # pyproject.toml only

Exit codes:
    0 - No suppressions found (PASS)
    1 - Suppressions found (FAIL)
        """,
    )
    parser.add_argument(
        "--code",
        action="store_true",
        help="Check Python code only",
    )
    parser.add_argument(
        "--toml",
        action="store_true",
        help="Check pyproject.toml only",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if suppressions found (required for pre-commit)",
    )

    args = parser.parse_args()

    has_failures = run(args.strict)

    if has_failures and args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()