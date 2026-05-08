# Release Process

## Release Law

This repository uses manual SemVer releases and Keep a Changelog.

Version impact:

- `major`: breaking API, event, config, deployment, or security contract changes.
- `minor`: backward-compatible features.
- `patch`: backward-compatible fixes.
- `none`: documentation, tests, chores, or internal-only changes.

## Release Steps

1. Ensure CI is green on `main`.
2. Move relevant entries from `[Unreleased]` to the release version in `CHANGELOG.md`.
3. Confirm the version in `pyproject.toml`.
4. Create a signed tag when signing is available.
5. Publish GitHub release notes from the changelog entry.

## Current Baseline

The initial public baseline is `0.1.0`. Until release automation is adopted, maintainers must update
the changelog manually.
