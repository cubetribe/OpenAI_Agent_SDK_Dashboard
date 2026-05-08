# Project Instructions

## Purpose

This repository contains an open-source, self-hosted dashboard for observing OpenAI Agents SDK
workflows in real time. The dashboard is read-only: it visualizes agent, tool, handoff, status, and
error events without controlling or mutating the upstream workflow.

## Privacy Boundary

- Treat `Context/` as local-only input material. It must not be committed or published.
- Do not publish customer names, project relic names, phone numbers, prompts, trace payloads, or any
  other customer-specific source material.
- Public examples must use neutral sample names and generic workflow labels.
- Before committing, run the public-term scan with the private terms provided locally or through CI
  secrets.

## Architecture Rules

- Keep the service self-hostable and Docker-first.
- Keep the dashboard read-only. Any endpoint that can mutate upstream agent state is out of scope.
- Keep authentication centralized in the API layer.
- Keep configuration data-driven; tenant-specific graph labels, colors, nodes, and tools belong in
  config files, not source code.
- Do not add external SaaS dependencies to the runtime path without an architecture note and an
  explicit privacy review.
- Prefer small explicit modules over hidden import-time side effects.

## Web and Python Rules

- The backend is FastAPI with WebSocket delivery.
- Browser assets should remain static and dependency-light unless a documented product need justifies
  a build pipeline.
- Keep Python code typed and covered by focused tests.
- Validate changes with the narrowest relevant command set: lint, typecheck, tests, then Docker build
  when container behavior changes.

## Release Law

- Versioning follows SemVer.
- The release process is manual until the repository adopts a release automation tool.
- Maintain `CHANGELOG.md` using Keep a Changelog sections.
- Normal development updates `[Unreleased]`; tagged releases move entries under the released version.

## GitHub Flow

- `main` is the protected base branch.
- Use short-lived topic branches after the initial seed commit.
- Prefer squash merges and linear history.
- Do not commit secrets, local context, generated state, or customer data.
- Do not force-push shared branches.
