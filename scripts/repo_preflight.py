#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize repository governance and release state."
    )
    parser.add_argument("--path", default=".", help="Repository path.")
    parser.add_argument("--task", default="", help="Short task summary.")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    report: dict[str, Any] = {
        "root": str(root),
        "task": args.task,
        "is_git_repo": _git(root, "rev-parse", "--is-inside-work-tree") == "true",
        "branch": _git(root, "branch", "--show-current") or "not present",
        "release_workflow": _release_workflow(root),
        "governance_files": _present(
            root,
            ["AGENTS.md", "README.md", "CONTRIBUTING.md", "CHANGELOG.md", "SECURITY.md"],
        ),
        "version_sources": _present(root, ["pyproject.toml", "VERSION"]),
        "ci_workflows": sorted(
            str(path.relative_to(root)) for path in (root / ".github" / "workflows").glob("*.yml")
        )
        if (root / ".github" / "workflows").exists()
        else [],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.strip()


def _present(root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (root / path).exists()]


def _release_workflow(root: Path) -> str:
    if (root / ".release-please-manifest.json").exists():
        return "release-please"
    if (root / ".changeset").exists():
        return "changesets"
    package = root / "package.json"
    if package.exists() and "semantic-release" in package.read_text(encoding="utf-8"):
        return "semantic-release"
    if (root / "CHANGELOG.md").exists():
        return "manual"
    return "unknown"


if __name__ == "__main__":
    sys.exit(main())
