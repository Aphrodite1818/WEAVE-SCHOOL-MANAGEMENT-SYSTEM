"""Fail CI when production-dangerous generated artifacts are committed."""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent

FORBIDDEN_PATHS = (
    BACKEND_DIR / "weave_demo_credentials.json",
    BACKEND_DIR / "scripts" / "seed_live_demo.py",
)

FORBIDDEN_GLOBS = (
    "*credentials*.json",
    "*.pem",
    "*.key",
)

IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def find_violations() -> list[str]:
    violations: set[str] = set()

    for path in FORBIDDEN_PATHS:
        if path.exists():
            violations.add(path.relative_to(BACKEND_DIR).as_posix())

    for pattern in FORBIDDEN_GLOBS:
        for path in BACKEND_DIR.rglob(pattern):
            if path.is_file() and not _is_ignored(path.relative_to(BACKEND_DIR)):
                violations.add(path.relative_to(BACKEND_DIR).as_posix())

    return sorted(violations)


def main() -> int:
    violations = find_violations()
    if violations:
        print("Repository hygiene check failed. Remove these sensitive artifacts:")
        for path in violations:
            print(f"- {path}")
        return 1

    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
