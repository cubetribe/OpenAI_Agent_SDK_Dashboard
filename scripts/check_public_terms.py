#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan publishable files for private terms supplied at runtime."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Private term or regular text pattern to block. Can be repeated.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    env_patterns = [
        item.strip()
        for item in os.environ.get("PRIVATE_TERM_PATTERNS", "").split(";")
        if item.strip()
    ]
    patterns = [*args.pattern, *env_patterns]

    if not patterns:
        print("No private term patterns supplied; skipping public-term scan.")
        return 0

    files = _publishable_files(root)
    failures: list[str] = []

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = file_path.relative_to(root)
        lowered = content.lower()
        for pattern in patterns:
            if pattern.lower() in lowered:
                failures.append(f"{relative}: contains a private term pattern")

    if failures:
        print("Public-term scan failed:")
        print("\n".join(failures))
        return 1

    print(f"Public-term scan passed across {len(files)} files.")
    return 0


def _publishable_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return [
            path
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts
        ]

    return [root / line for line in result.stdout.splitlines() if line.strip()]


if __name__ == "__main__":
    sys.exit(main())
