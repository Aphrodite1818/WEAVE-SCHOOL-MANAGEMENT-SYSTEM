#!/usr/bin/env python3
"""Fail CI when high-risk generated credentials or demo artifacts are tracked."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SELF_PATH = Path(__file__).resolve()
MAX_SCAN_BYTES = 2 * 1024 * 1024
TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

FORBIDDEN_PATH_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)", re.IGNORECASE),
    re.compile(r"credentials.*\.json$", re.IGNORECASE),
    re.compile(r"weave_demo_credentials\.json$", re.IGNORECASE),
    re.compile(r"seed_live_demo\.py$", re.IGNORECASE),
)

FORBIDDEN_CONTENT_MARKERS = (
    "password_for_" + "all_accounts",
    "taiwoayimora623" + "@gmail.com",
    "All generated accounts use password" + ":",
    "-----BEGIN " + "PRIVATE KEY-----",
)
AWS_ACCESS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return [
        REPOSITORY_ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def path_is_forbidden(path: Path) -> bool:
    relative = path.relative_to(REPOSITORY_ROOT).as_posix()
    if relative.endswith(".env.example"):
        return False
    return any(pattern.search(relative) for pattern in FORBIDDEN_PATH_PATTERNS)


def should_scan(path: Path) -> bool:
    if path == SELF_PATH or not path.is_file():
        return False
    if path.stat().st_size > MAX_SCAN_BYTES:
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.endswith(".env.example")


def main() -> int:
    violations: list[str] = []

    for path in tracked_files():
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        if path_is_forbidden(path):
            violations.append(f"forbidden tracked path: {relative}")
            continue
        if not should_scan(path):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for marker in FORBIDDEN_CONTENT_MARKERS:
            if marker in content:
                violations.append(f"forbidden credential/demo marker in: {relative}")
                break
        if AWS_ACCESS_KEY_PATTERN.search(content):
            violations.append(f"possible AWS access key in: {relative}")

    if violations:
        print("Repository hygiene verification failed:")
        for violation in sorted(set(violations)):
            print(f"- {violation}")
        return 1

    print("Repository hygiene verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
